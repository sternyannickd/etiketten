import csv
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

from etiketten import charge, cli, config, mhd, server, zpl
from etiketten.dienst import Druckdienst, EingabeFehler

from .hilfen import KAFFEES, test_konfig

HEUTE = date.today()
CHARGE = f"Rö{HEUTE:%y%m%d}-01"


def daten(**extra):
    werte = dict(name="Espresso|Guatemala", info="Schokolade, Nuss|Huehuetenango",
                 charge="Rö261012-01", roestdatum=date(2026, 10, 12), mhd=date(2027, 10, 12),
                 qr="https://www.stern-kaffee.de")
    return zpl.VerpackungsDaten(**{**werte, **extra})


class ChargeTest(unittest.TestCase):
    def test_lesen(self):
        c = charge.lesen("Rö261012-03")
        self.assertEqual(c.roestdatum, date(2026, 10, 12))
        self.assertEqual(c.nummer, 3)
        self.assertEqual(c.text, "Rö261012-03")

    def test_schreibweisen_werden_vereinheitlicht(self):
        for text in ("ro261012-01", "RÖ261012-01", " Roe261012-01 "):
            self.assertEqual(charge.lesen(text).text, "Rö261012-01")

    def test_falsches_format(self):
        for text in ("", "261012-01", "Rö261012", "Rö261012-1", "Rö2610121-01", "Rö261012-00"):
            with self.assertRaises(charge.ChargeFehler, msg=text):
                charge.lesen(text)

    def test_ungueltiges_datum(self):
        with self.assertRaisesRegex(charge.ChargeFehler, "kein gültiges Datum"):
            charge.lesen("Rö261332-01")


class VerpackungZplTest(unittest.TestCase):
    def setUp(self):
        self.konfig = config.standard().fuer_verpackung()

    def test_groesse_100_x_150(self):
        text = zpl.verpackung_erzeugen(self.konfig, daten())
        self.assertIn("^PW799", text)
        self.assertIn("^LL1199", text)

    def test_inhalt(self):
        text = zpl.verpackung_erzeugen(self.konfig, daten())
        for teil in ("^FDEspresso^FS", "^FDGuatemala^FS", "^FDSchokolade, Nuss^FS", "^FDHuehuetenango^FS",
                     "^FDRö261012-01^FS", "^FD12.10.2026^FS", "^FD12.10.2027^FS",
                     "^FDMA,https://www.stern-kaffee.de^FS", "^FDwww.stern-kaffee.de^FS"):
            self.assertIn(teil, text)
        self.assertIn("^BQN,2,", text)

    def test_ohne_info_kein_infotext(self):
        text = zpl.verpackung_erzeugen(self.konfig, daten(info=""))
        self.assertNotIn("Schokolade", text)

    def test_lange_info_wird_gekuerzt(self):
        text = zpl.verpackung_erzeugen(self.konfig, daten(info="|".join(["Eine Zeile Text"] * 30)))
        self.assertEqual(text.count("Eine Zeile Text"), 9)
        self.assertIn("...^FS", text)

    def test_qr_groesse_passt_ins_feld(self):
        text = zpl.verpackung_erzeugen(self.konfig, daten())
        faktor = int(text.split("^BQN,2,")[1].split("^")[0])
        feld = round(36 * 203 / 25.4)
        self.assertLessEqual(zpl.qr_module("https://www.stern-kaffee.de") * faktor, feld)
        self.assertGreaterEqual(faktor, 5)

    def test_qr_mit_steuerzeichen_abgelehnt(self):
        with self.assertRaises(ValueError):
            zpl.verpackung_erzeugen(self.konfig, daten(qr="https://x.de/^XZ"))


class VerpackungDienstTest(unittest.TestCase):
    def setUp(self):
        kaffees = json.loads(json.dumps(KAFFEES))
        kaffees[0]["info"] = "Schokolade|Huila"
        self.konfig = test_konfig(kaffees)
        self.dienst = Druckdienst(self.konfig)

    def test_drucken_schreibt_zpl_und_protokoll(self):
        meldung = self.dienst.verpackung_drucken("kolumbien", CHARGE, menge=2)
        self.assertIn("Trockenlauf", meldung)
        dateien = list((self.konfig.basis_dir / "var" / "ausgabe").glob("*.zpl"))
        self.assertEqual(len(dateien), 1)
        inhalt = dateien[0].read_bytes().decode()
        self.assertIn("^PQ2,", inhalt)
        self.assertIn("^FDSchokolade^FS", inhalt)
        pfad = self.konfig.fuer_verpackung().protokoll_pfad
        with pfad.open(encoding="utf-8") as f:
            zeilen = list(csv.DictReader(f))
        self.assertEqual(zeilen[0]["charge"], CHARGE)
        self.assertEqual(zeilen[0]["ergebnis"], "ok")

    def test_mhd_aus_roestdatum(self):
        text = self.dienst.verpackung_etikett("espresso-guatemala", CHARGE)
        erwartet = mhd.berechnen(HEUTE, 9)   # Espresso Guatemala: 9 Monate
        self.assertIn(f"^FD{erwartet:%d.%m.%Y}^FS", text)

    def test_roestdatum_in_der_zukunft(self):
        morgen = HEUTE + timedelta(days=1)
        with self.assertRaisesRegex(EingabeFehler, "Zukunft"):
            self.dienst.verpackung_etikett("kolumbien", f"Rö{morgen:%y%m%d}-01")

    def test_falsche_charge(self):
        with self.assertRaisesRegex(EingabeFehler, "Format"):
            self.dienst.verpackung_etikett("kolumbien", "12345")

    def test_ausgeschaltet(self):
        self.konfig.daten["verpackung"]["aktiv"] = False
        with self.assertRaisesRegex(EingabeFehler, "ausgeschaltet"):
            self.dienst.verpackung_etikett("kolumbien", CHARGE)

    def test_eigener_drucker(self):
        self.konfig.daten["verpackung"]["drucker"] = {"transport": "tcp", "tcp_host": ""}
        self.assertEqual(self.konfig.fuer_verpackung()["drucker"]["transport"], "tcp")
        self.assertEqual(self.konfig["drucker"]["transport"], "datei")
        self.assertFalse(self.dienst.verpackung_status().ok)
        self.assertTrue(self.dienst.status().ok)

    def test_info_wird_gespeichert(self):
        k = self.dienst.kaffee_speichern({"name": "Brasilien", "mhd_monate": 10, "info": " Nuss|Karamell ",
                                          "versionen": [{"bezeichnung": "Laden", "gtin": "5901234123457"}]})
        self.assertEqual(k.info, "Nuss|Karamell")
        self.assertEqual(self.dienst.kaffee("brasilien").info, "Nuss|Karamell")

    def test_info_zu_lang(self):
        with self.assertRaisesRegex(Exception, "zu lang"):
            self.dienst.kaffee_speichern({"name": "X", "mhd_monate": 10, "info": "x" * 301,
                                          "versionen": [{"bezeichnung": "A", "gtin": "4006381333931"}]})


class KonfigTest(unittest.TestCase):
    def test_lokale_konfiguration_gilt_zusaetzlich(self):
        ordner = Path(tempfile.mkdtemp(prefix="etiketten-test-"))
        (ordner / "config.toml").write_text('[drucker]\ntransport = "usb"\ndpi = 203\n', encoding="utf-8")
        (ordner / "config.lokal.toml").write_text('[drucker]\ntransport = "datei"\n', encoding="utf-8")
        k = config.laden(ordner / "config.toml")
        self.assertEqual(k["drucker"]["transport"], "datei")
        self.assertEqual(k["drucker"]["dpi"], 203)

    def test_entwicklermodus_nutzt_testdaten_und_dateien(self):
        k = test_konfig()
        k.daten["drucker"]["transport"] = "usb"
        ordner = cli.entwicklermodus(k)
        self.assertTrue((ordner / "produkte.json").exists())
        self.assertEqual(Path(k.produkte_pfad), ordner / "produkte.json")
        self.assertEqual(k["drucker"]["transport"], "datei")
        self.assertEqual(k.fuer_verpackung()["drucker"]["transport"], "datei")
        Druckdienst(k).drucken("kolumbien")
        self.assertEqual(len(list((ordner / "ausgabe").glob("*.zpl"))), 1)


class VerpackungServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.konfig = test_konfig()
        rahmen = Path(tempfile.mkdtemp(prefix="rahmen-"))
        (rahmen / "theme.css").write_text(":root { --farbe-akzent: red; }", encoding="utf-8")
        handler = server.handler_fuer(Druckdienst(cls.konfig), rahmen, entwickler=True)
        handler.log_message = lambda *args: None
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.basis = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def anfrage(self, pfad, daten=None):
        body = None if daten is None else json.dumps(daten).encode()
        req = urllib.request.Request(self.basis + pfad, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_seite_mit_rahmen_und_hinweis(self):
        status, inhalt = self.anfrage("/verpackung")
        self.assertEqual(status, 200)
        self.assertIn(b"<verpackung-app", inhalt)
        self.assertIn(b'href="/rahmen/theme.css"', inhalt)
        self.assertIn(b"Entwicklermodus", inhalt)
        status, inhalt = self.anfrage("/rahmen/theme.css")
        self.assertEqual(status, 200)
        self.assertEqual(self.anfrage("/rahmen/../server.py")[0], 404)

    def test_status_nach_konvention(self):
        status, inhalt = self.anfrage("/api/verpackung/status")
        s = json.loads(inhalt)
        self.assertTrue(s["ok"])
        self.assertIn("meldung", s)
        s = json.loads(self.anfrage("/api/status")[1])
        self.assertTrue(s["ok"])
        self.assertTrue(s["verpackung"])

    def test_zpl_und_drucken(self):
        status, inhalt = self.anfrage("/api/verpackung/zpl", {"kaffee": "kolumbien", "charge": CHARGE})
        self.assertEqual(status, 200)
        self.assertIn(CHARGE, json.loads(inhalt)["zpl"])
        status, inhalt = self.anfrage("/api/verpackung/drucken", {"kaffee": "kolumbien", "charge": CHARGE, "menge": 3})
        self.assertEqual(status, 200)
        self.assertIn("3 Verpackungsetikett", json.loads(inhalt)["meldung"])

    def test_fehler(self):
        self.assertEqual(self.anfrage("/api/verpackung/drucken", {"kaffee": "kolumbien"})[0], 400)
        status, inhalt = self.anfrage("/api/verpackung/zpl", {"kaffee": "kolumbien", "charge": "x"})
        self.assertEqual(status, 400)
        self.assertIn("Format", json.loads(inhalt)["fehler"])


if __name__ == "__main__":
    unittest.main()
