"""Windows-Druckweg mit einer Attrappe der Windows-Druck-API (läuft auf jedem System)."""

import unittest
from unittest import mock

from etiketten import config, drucker


class AttrappeApi:
    def __init__(self, namen):
        self.namen = namen
        self.gesendet = []

    def drucker_namen(self):
        return self.namen

    def roh_drucken(self, name, daten):
        self.gesendet.append((name, daten))


class WindowsTest(unittest.TestCase):
    def test_auto_findet_citizen(self):
        api = AttrappeApi(["Microsoft Print to PDF", "CITIZEN CL-S521Z", "Fax"])
        t = drucker.WindowsTransport(api=api)
        self.assertTrue(t.pruefen().ok)
        self.assertEqual(t.senden(b"^XA^XZ"), "an CITIZEN CL-S521Z gesendet")
        self.assertEqual(api.gesendet, [("CITIZEN CL-S521Z", b"^XA^XZ")])

    def test_fester_name(self):
        api = AttrappeApi(["Etiketten (Text Only)"])
        self.assertTrue(drucker.WindowsTransport("Etiketten (Text Only)", api=api).pruefen().ok)
        status = drucker.WindowsTransport("Anderer", api=api).pruefen()
        self.assertFalse(status.ok)
        self.assertIn("Etiketten (Text Only)", status.meldung)

    def test_kein_drucker(self):
        status = drucker.WindowsTransport(api=AttrappeApi(["Microsoft Print to PDF"])).pruefen()
        self.assertFalse(status.ok)
        self.assertIn("CITIZEN", status.meldung)
        with self.assertRaises(drucker.DruckFehler):
            drucker.WindowsTransport(api=AttrappeApi([])).senden(b"x")

    def test_auto_waehlt_druckweg_je_system(self):
        k = config.standard()
        with mock.patch.object(drucker.sys, "platform", "win32"):
            self.assertIsInstance(drucker.transport(k), drucker.WindowsTransport)
        with mock.patch.object(drucker.sys, "platform", "linux"):
            self.assertIsInstance(drucker.transport(k), drucker.UsbTransport)

    def test_ausserhalb_windows_klare_meldung(self):
        with mock.patch.object(drucker.sys, "platform", "linux"):
            status = drucker.WindowsTransport().pruefen()
        self.assertFalse(status.ok)
        self.assertIn("nur unter Windows", status.meldung)


if __name__ == "__main__":
    unittest.main()
