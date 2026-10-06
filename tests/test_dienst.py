import csv
import unittest
from datetime import date, timedelta

from etiketten import drucker
from etiketten.dienst import Druckdienst, EingabeFehler

from .hilfen import test_konfig


class DienstTest(unittest.TestCase):
    def setUp(self):
        self.konfig = test_konfig()
        self.dienst = Druckdienst(self.konfig)

    def test_mhd_vorschlag_nutzt_monate_des_produkts(self):
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
        self.assertEqual(zeilen[0]["produkt_id"], "kolumbien")
        self.assertEqual(zeilen[0]["ergebnis"], "ok")

    def test_unbekanntes_produkt(self):
        with self.assertRaises(EingabeFehler):
            self.dienst.etikett("gibtsnicht")

    def test_mhd_in_vergangenheit(self):
        with self.assertRaises(EingabeFehler):
            self.dienst.etikett("kolumbien", date.today() - timedelta(days=1))

    def test_druckfehler_wird_protokolliert(self):
        self.konfig.daten["drucker"].update(transport="usb", usb_geraet="/gibt/es/nicht/lp9")
        with self.assertRaises(drucker.DruckFehler):
            self.dienst.drucken("kolumbien")
        self.assertIn("FEHLER", self.konfig.protokoll_pfad.read_text(encoding="utf-8"))


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
