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

    def anfrage(self, pfad, daten=None):
        body = None if daten is None else json.dumps(daten).encode()
        req = urllib.request.Request(self.basis + pfad, data=body,
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

    def test_kein_zugriff_ausserhalb_static(self):
        status, _, _ = self.anfrage("/static/../server.py")
        self.assertEqual(status, 404)

    def test_produkte_und_status(self):
        _, _, inhalt = self.anfrage("/api/produkte")
        self.assertEqual(json.loads(inhalt)[1]["name"], "Espresso Guatemala")
        _, _, inhalt = self.anfrage("/api/status")
        self.assertTrue(json.loads(inhalt)["drucker"]["ok"])

    def test_mhd(self):
        _, _, inhalt = self.anfrage("/api/mhd?produkt=kolumbien&abgepackt=2026-10-02")
        self.assertEqual(json.loads(inhalt)["mhd"], "2027-10-02")

    def test_drucken(self):
        status, _, inhalt = self.anfrage("/api/drucken", {"produkt": "kolumbien", "menge": 2})
        self.assertEqual(status, 200, inhalt)
        self.assertTrue(json.loads(inhalt)["ok"])

    def test_fehlerhafte_eingaben(self):
        for daten in ({}, {"produkt": "x"}, {"produkt": "kolumbien", "menge": "viele"},
                      {"produkt": "kolumbien", "mhd": "morgen"}, {"produkt": "kolumbien", "menge": 0}):
            status, _, inhalt = self.anfrage("/api/drucken", daten)
            self.assertEqual(status, 400, daten)
            self.assertFalse(json.loads(inhalt)["ok"])

    def test_vorschau_aus_gibt_502_druck_bleibt_moeglich(self):
        status, _, _ = self.anfrage("/api/vorschau", {"produkt": "kolumbien"})
        self.assertEqual(status, 502)


if __name__ == "__main__":
    unittest.main()
