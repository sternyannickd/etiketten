import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from etiketten import server
from etiketten.dienst import Druckdienst

from .hilfen import test_konfig


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.konfig = test_konfig()
        handler = server.handler_fuer(Druckdienst(cls.konfig))
        handler.log_message = lambda *args: None
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.basis = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def anfrage(self, pfad, daten=None, methode=None):
        body = None if daten is None else json.dumps(daten).encode()
        req = urllib.request.Request(self.basis + pfad, data=body, method=methode,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.headers.get("Content-Type"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type"), e.read()

    def test_startseite(self):
        status, typ, inhalt = self.anfrage("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", typ)
        self.assertIn(b"Etikettendruck", inhalt)

    def test_component_als_modul(self):
        status, typ, inhalt = self.anfrage("/static/etiketten-app.js")
        self.assertEqual(status, 200)
        self.assertTrue(typ.startswith("text/javascript"))
        self.assertIn(b'customElements.define("etiketten-app"', inhalt)
        _, typ, _ = self.anfrage("/static/etiketten-app.css")
        self.assertTrue(typ.startswith("text/css"))

    def test_kein_zugriff_ausserhalb_static(self):
        status, _, _ = self.anfrage("/static/../server.py")
        self.assertEqual(status, 404)

    def test_produkte_und_status(self):
        _, _, inhalt = self.anfrage("/api/produkte")
        kaffee = json.loads(inhalt)[1]
        self.assertEqual(kaffee["anzeigename"], "Espresso Guatemala")
        self.assertEqual(len(kaffee["versionen"]), 2)
        _, _, inhalt = self.anfrage("/api/status")
        self.assertTrue(json.loads(inhalt)["drucker"]["ok"])
        self.assertTrue(json.loads(inhalt)["produkte_bearbeiten"])

    def test_mhd(self):
        _, _, inhalt = self.anfrage("/api/mhd?kaffee=kolumbien&abgepackt=2026-10-02")
        self.assertEqual(json.loads(inhalt)["mhd"], "2027-10-02")

    def test_drucken(self):
        status, _, inhalt = self.anfrage("/api/drucken", {"kaffee": "kolumbien", "menge": 2})
        self.assertEqual(status, 200, inhalt)
        self.assertTrue(json.loads(inhalt)["ok"])

    def test_fehlerhafte_eingaben(self):
        for daten in ({}, {"kaffee": "x"}, {"kaffee": "kolumbien", "menge": "viele"},
                      {"kaffee": "kolumbien", "mhd": "morgen"}, {"kaffee": "kolumbien", "menge": 0},
                      {"kaffee": "espresso-guatemala"}, {"kaffee": "kolumbien", "version": "lidl"}):
            status, _, inhalt = self.anfrage("/api/drucken", daten)
            self.assertEqual(status, 400, daten)
            self.assertFalse(json.loads(inhalt)["ok"])

    def test_kaffee_anlegen_und_aendern(self):
        neu = {"name": "Peru", "mhd_monate": 12,
               "versionen": [{"bezeichnung": "Edeka", "gtin": "2064000001908"}]}
        status, _, inhalt = self.anfrage("/api/kaffees", neu)
        self.assertEqual(status, 200, inhalt)
        kaffee = json.loads(inhalt)["kaffee"]
        kaffee["versionen"][0]["archiviert"] = True
        status, _, inhalt = self.anfrage(f"/api/kaffees/{kaffee['id']}", kaffee, "PUT")
        self.assertEqual(status, 200, inhalt)
        _, _, inhalt = self.anfrage("/api/produkte")
        self.assertNotIn("peru", [k["id"] for k in json.loads(inhalt)])
        _, _, inhalt = self.anfrage("/api/produkte?alle=1")
        self.assertIn("peru", [k["id"] for k in json.loads(inhalt)])

    def test_kaffee_mit_falscher_gtin(self):
        status, _, inhalt = self.anfrage("/api/kaffees", {"name": "X", "mhd_monate": 12, "versionen": [
            {"bezeichnung": "A", "gtin": "123"}]})
        self.assertEqual(status, 400)
        self.assertIn("13 Ziffern", json.loads(inhalt)["fehler"])

    def test_vorschau_aus_gibt_502_druck_bleibt_moeglich(self):
        status, _, _ = self.anfrage("/api/vorschau", {"kaffee": "kolumbien"})
        self.assertEqual(status, 502)


if __name__ == "__main__":
    unittest.main()
