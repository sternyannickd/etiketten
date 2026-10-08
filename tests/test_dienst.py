import csv
import unittest
from datetime import date, timedelta

from etiketten import drucker
from etiketten.dienst import Druckdienst, EingabeFehler
from etiketten.produkte import ProduktFehler

from .hilfen import test_konfig


class DienstTest(unittest.TestCase):
    def setUp(self):
        self.konfig = test_konfig()
        self.dienst = Druckdienst(self.konfig)

    def test_mhd_vorschlag_nutzt_monate_des_kaffees(self):
        self.assertEqual(self.dienst.mhd_vorschlag("espresso-guatemala", date(2026, 10, 2)),
                         date(2027, 7, 2))

    def test_drucken_schreibt_zpl_und_protokoll(self):
        meldung = self.dienst.drucken("kolumbien", menge=3)
        self.assertIn("Trockenlauf", meldung)
        dateien = list((self.konfig.basis_dir / "var" / "ausgabe").glob("*.zpl"))
        self.assertEqual(len(dateien), 1)
        self.assertIn(b"^PQ3,", dateien[0].read_bytes())
        with self.konfig.protokoll_pfad.open(encoding="utf-8") as f:
            zeilen = list(csv.DictReader(f))
        self.assertEqual(zeilen[0]["kaffee_id"], "kolumbien")
        self.assertEqual(zeilen[0]["version"], "Edeka")
        self.assertEqual(zeilen[0]["ergebnis"], "ok")

    def test_version_bestimmt_gtin(self):
        self.assertIn("^FD400638133393", self.dienst.etikett("espresso-guatemala", "rewe"))
        with self.assertRaisesRegex(ProduktFehler, "Version wählen"):
            self.dienst.etikett("espresso-guatemala")

    def test_altes_protokoll_wird_beiseitegelegt(self):
        pfad = self.konfig.protokoll_pfad
        pfad.parent.mkdir(parents=True)
        pfad.write_text("zeitpunkt,produkt_id,name,gtin,mhd,menge,ergebnis\n", encoding="utf-8")
        self.dienst.drucken("kolumbien")
        self.assertTrue(pfad.with_name("protokoll-bis-0.2.csv").exists())
        self.assertTrue(pfad.read_text(encoding="utf-8").startswith("zeitpunkt,kaffee_id,version_id"))

    def test_unbekannter_kaffee(self):
        with self.assertRaises(EingabeFehler):
            self.dienst.etikett("gibtsnicht")

    def test_mhd_in_vergangenheit(self):
        with self.assertRaises(EingabeFehler):
            self.dienst.etikett("kolumbien", mhd_datum=date.today() - timedelta(days=1))

    def test_druckfehler_wird_protokolliert(self):
        self.konfig.daten["drucker"].update(transport="usb", usb_geraet="/gibt/es/nicht/lp9")
        with self.assertRaises(drucker.DruckFehler):
            self.dienst.drucken("kolumbien")
        self.assertIn("FEHLER", self.konfig.protokoll_pfad.read_text(encoding="utf-8"))


class BearbeitenTest(unittest.TestCase):
    def setUp(self):
        self.konfig = test_konfig()
        self.dienst = Druckdienst(self.konfig)

    def test_neuer_kaffee(self):
        k = self.dienst.kaffee_speichern({"name": "Brasilien", "mhd_monate": 10, "versionen": [
            {"bezeichnung": "Edeka", "gtin": "2064000001908"}]})
        self.assertEqual(k.id, "brasilien")
        self.assertEqual(self.dienst.kaffee("brasilien").versionen[0].id, "edeka")
        self.assertEqual(self.dienst.mhd_vorschlag("brasilien", date(2026, 1, 1)), date(2026, 11, 1))

    def test_version_hinzufuegen_und_archivieren(self):
        k = self.dienst.kaffee("kolumbien").als_dict()
        k["versionen"][0]["archiviert"] = True
        k["versionen"].append({"bezeichnung": "Rewe", "gtin": "2064000001908"})
        neu = self.dienst.kaffee_speichern(k, "kolumbien")
        self.assertEqual([v.id for v in neu.versionen], ["edeka", "rewe"])
        self.assertEqual(self.dienst.kaffee("kolumbien").version(None).id, "rewe")

    def test_versionen_nicht_loeschbar(self):
        k = self.dienst.kaffee("espresso-guatemala").als_dict()
        k["versionen"].pop()
        with self.assertRaisesRegex(EingabeFehler, "nur archiviert"):
            self.dienst.kaffee_speichern(k, "espresso-guatemala")

    def test_archivierter_kaffee_fehlt_in_der_auswahl(self):
        k = self.dienst.kaffee("kolumbien").als_dict()
        k["archiviert"] = True
        self.dienst.kaffee_speichern(k, "kolumbien")
        self.assertEqual([x.id for x in self.dienst.kaffees()], ["espresso-guatemala"])
        self.assertEqual(len(self.dienst.kaffees(alle=True)), 2)

    def test_doppelte_gtin_wird_abgelehnt(self):
        with self.assertRaisesRegex(ProduktFehler, "schon vergeben"):
            self.dienst.kaffee_speichern({"name": "X", "mhd_monate": 12, "versionen": [
                {"bezeichnung": "Edeka", "gtin": "2064000002134"}]})

    def test_bearbeiten_ausgeschaltet(self):
        self.konfig.daten["produkte_bearbeiten"] = False
        with self.assertRaisesRegex(EingabeFehler, "ausgeschaltet"):
            self.dienst.kaffee_speichern({"name": "X", "mhd_monate": 12, "versionen": []})


class UsbTest(unittest.TestCase):
    def test_kennung_nicht_gefunden(self):
        t = drucker.UsbTransport("auto", "GIBT-ES-NICHT-12345")
        self.assertFalse(t.pruefen().ok)

    def test_fester_pfad_ohne_rechte(self):
        t = drucker.UsbTransport("/gibt/es/nicht/lp9")
        self.assertFalse(t.pruefen().ok)

    def test_druckersprache_aus_kennung(self):
        zebra = "MANUFACTURER:CITIZEN;COMMAND SET:Z2;MODEL:CL-S521Z;ACTIVE COMMAND:Z2;"
        datamax = "MANUFACTURER:CITIZEN;COMMAND SET:DMI,DM4,DPP;MODEL:CL-S521;ACTIVE COMMAND:DMI;"
        self.assertIs(drucker.spricht_zpl(zebra), True)
        self.assertIs(drucker.spricht_zpl(datamax), False)
        self.assertIsNone(drucker.spricht_zpl("MFG:SII;MDL:SLP620;"))


if __name__ == "__main__":
    unittest.main()
