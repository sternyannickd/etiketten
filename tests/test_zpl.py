import re
import unittest
from datetime import date

from etiketten import zpl

from .hilfen import test_konfig


def etikett(konfig=None, name="Kolumbien", menge=1):
    return zpl.erzeugen(konfig or test_konfig(),
                        zpl.EtikettDaten(name, "2064000002134", date(2027, 10, 2), menge))


class ErzeugenTest(unittest.TestCase):
    def test_grundgeruest(self):
        text = etikett(menge=5)
        self.assertTrue(text.startswith("^XA\n^CI28\n"))
        self.assertTrue(text.rstrip().endswith("^XZ"))
        self.assertIn("^PW456", text)     # 57 mm bei 203 dpi
        self.assertIn("^LL256", text)     # 32 mm bei 203 dpi
        self.assertIn("^PQ5,", text)

    def test_barcode_nativ_mit_12_ziffern(self):
        self.assertRegex(etikett(), r"\^BEN,\d+,Y,N\^FD206400000213\^FS")

    def test_mhd_text(self):
        self.assertIn("MHD: 02.10.2027", etikett())

    def test_mhd_zweizeilig(self):
        k = test_konfig()
        k.daten["layout"]["mhd"]["einzeilig"] = False
        text = etikett(k)
        self.assertIn("^FDMHD:^FS", text)
        self.assertIn("^FD02.10.2027^FS", text)

    def test_umbruchzeichen_erzwingt_zwei_zeilen(self):
        text = etikett(name="Espresso|Guatemala")
        self.assertIn("^FDEspresso^FS", text)
        self.assertIn("^FDGuatemala^FS", text)

    def test_steuerzeichen_werden_maskiert(self):
        text = etikett(name="A^B~C_D")
        self.assertIn("^FDA_5EB_7EC_5FD^FS", text)

    def test_menge_begrenzt(self):
        with self.assertRaises(ValueError):
            etikett(menge=0)
        with self.assertRaises(ValueError):
            etikett(menge=1000)

    def test_versatz_verschiebt_alles(self):
        k = test_konfig()
        normal = re.findall(r"\^FO(\d+),(\d+)", etikett(k))
        k.daten["etikett"]["versatz_x"] = 1.0  # 1 mm = 8 Punkte
        verschoben = re.findall(r"\^FO(\d+),(\d+)", etikett(k))
        for (x1, y1), (x2, y2) in zip(normal, verschoben):
            self.assertEqual(int(x2) - int(x1), 8)
            self.assertEqual(y1, y2)

    def test_300_dpi(self):
        k = test_konfig()
        k.daten["drucker"]["dpi"] = 300
        self.assertIn("^PW673", etikett(k))

    def test_latin1(self):
        k = test_konfig()
        k.daten["drucker"]["zeichensatz"] = "latin1"
        text = etikett(k, name="Äthiopien")
        self.assertIn("^CI27", text)
        self.assertIn("Äthiopien".encode("cp1252"), zpl.kodieren(k, text))


class TitelTest(unittest.TestCase):
    def test_kurzer_name_groesste_schrift(self):
        schrift, zeilen = zpl.titel_setzen("Kolumbien", 320, 72, 2, 40, 24)
        self.assertEqual((schrift, zeilen), (40, ["Kolumbien"]))

    def test_langer_name_hoechstens_zwei_zeilen(self):
        name = "Entkoffeinierter Hausespresso Brasilien Mogiana Spezial Edition Nummer Eins"
        schrift, zeilen = zpl.titel_setzen(name, 320, 72, 2, 40, 24)
        self.assertEqual(schrift, 24)
        self.assertEqual(len(zeilen), 2)
        self.assertTrue(zeilen[-1].endswith("..."))
        for z in zeilen:
            self.assertLessEqual(zpl.textbreite(z, schrift), 320)


class TestetikettTest(unittest.TestCase):
    def test_enthaelt_umlaute_und_rahmen(self):
        text = zpl.testetikett(test_konfig())
        self.assertIn("Größe", text)
        self.assertIn("^GB", text)


if __name__ == "__main__":
    unittest.main()
