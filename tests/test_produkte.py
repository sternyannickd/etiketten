import unittest
from pathlib import Path

from etiketten import produkte
from etiketten.config import PROJEKT_DIR

from .hilfen import test_konfig


class EanTest(unittest.TestCase):
    def test_pruefziffer(self):
        self.assertEqual(produkte.ean13_pruefziffer("400638133393"), 1)
        self.assertEqual(produkte.ean13_pruefziffer("206400000213"), 4)

    def test_pruefen(self):
        self.assertIsNone(produkte.ean13_pruefen("4006381333931"))
        self.assertIn("Prüfziffer", produkte.ean13_pruefen("4006381333932"))
        self.assertIn("13 Ziffern", produkte.ean13_pruefen("123"))
        self.assertIn("13 Ziffern", produkte.ean13_pruefen("40063813339a1"))


class LadenTest(unittest.TestCase):
    def test_echte_produktliste_ist_gueltig(self):
        liste = produkte.laden(PROJEKT_DIR / "data" / "produkte.csv")
        self.assertGreaterEqual(len(liste), 6)

    def test_anzeigename_ohne_umbruchzeichen(self):
        k = test_konfig()
        p = produkte.laden(k.produkte_pfad)[1]
        self.assertEqual(p.name, "Espresso|Guatemala")
        self.assertEqual(p.anzeigename, "Espresso Guatemala")

    def test_fehler_werden_gesammelt(self):
        k = test_konfig("id,name,gtin,mhd_monate\n"
                        "a,A,2064000002135,12\n"
                        "b,B,2064000002134,0\n"
                        "a,C,2064000002134,12\n"
                        "a,D,2064000002134,12\n")
        with self.assertRaises(produkte.ProduktFehler) as ctx:
            produkte.laden(k.produkte_pfad)
        text = str(ctx.exception)
        self.assertIn("Zeile 2", text)
        self.assertIn("Zeile 3", text)
        self.assertIn("doppelt", text)

    def test_fehlende_spalte(self):
        k = test_konfig("id,name,gtin\na,A,2064000002134\n")
        with self.assertRaisesRegex(produkte.ProduktFehler, "mhd_monate"):
            produkte.laden(k.produkte_pfad)

    def test_fehlende_datei(self):
        with self.assertRaises(produkte.ProduktFehler):
            produkte.laden(Path("/gibt/es/nicht.csv"))


if __name__ == "__main__":
    unittest.main()
