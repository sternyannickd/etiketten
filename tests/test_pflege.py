"""Produkte anlegen, ändern, löschen – über Dienst und HTTP-API."""

import unittest

from etiketten import produkte
from etiketten.dienst import Druckdienst, EingabeFehler

from .hilfen import test_konfig


class NeueIdTest(unittest.TestCase):
    def test_aus_name(self):
        self.assertEqual(produkte.neue_id("Espresso|Guatemala", set()), "espresso-guatemala")
        self.assertEqual(produkte.neue_id("Äthiopien Café Größe", set()), "aethiopien-cafe-groesse")
        self.assertEqual(produkte.neue_id("!!!", set()), "produkt")

    def test_eindeutig(self):
        self.assertEqual(produkte.neue_id("Kolumbien", {"kolumbien", "kolumbien-2"}), "kolumbien-3")


class SpeichernTest(unittest.TestCase):
    def test_speichern_und_wieder_laden(self):
        k = test_konfig()
        liste = produkte.laden(k.produkte_pfad)
        liste.append(produkte.Produkt("neu", 'Mit, Komma und "Anführung"', "4006381333931", 6))
        produkte.speichern(k.produkte_pfad, liste)
        self.assertEqual(produkte.laden(k.produkte_pfad), liste)
        self.assertTrue(k.produkte_pfad.with_name("produkte.csv.bak").exists())

    def test_keine_temp_dateien_bleiben(self):
        k = test_konfig()
        produkte.speichern(k.produkte_pfad, produkte.laden(k.produkte_pfad))
        self.assertEqual([p.name for p in k.produkte_pfad.parent.glob(".produkte-*")], [])


class DienstPflegeTest(unittest.TestCase):
    def setUp(self):
        self.dienst = Druckdienst(test_konfig())

    def test_anlegen(self):
        p = self.dienst.produkt_speichern({"name": "Brasil|Santos", "gtin": "4006381333931",
                                           "mhd_monate": "18"})
        self.assertEqual(p.id, "brasil-santos")
        self.assertEqual(self.dienst.produkt("brasil-santos").mhd_monate, 18)
        # Das neue Produkt lässt sich sofort drucken
        self.assertIn("^BE", self.dienst.etikett("brasil-santos"))

    def test_aendern_behaelt_id(self):
        self.dienst.produkt_speichern({"name": "Kolumbien Supremo", "gtin": "2064000002134",
                                       "mhd_monate": 10}, alte_id="kolumbien")
        p = self.dienst.produkt("kolumbien")
        self.assertEqual((p.name, p.mhd_monate), ("Kolumbien Supremo", 10))
        self.assertEqual(len(self.dienst.produkte()), 2)

    def test_ungueltige_eingaben_aendern_nichts(self):
        vorher = self.dienst.produkte()
        for daten in ({"name": "", "gtin": "4006381333931", "mhd_monate": 12},
                      {"name": "X", "gtin": "4006381333932", "mhd_monate": 12},
                      {"name": "X", "gtin": "4006381333931", "mhd_monate": 0},
                      {"name": "X\nY", "gtin": "4006381333931", "mhd_monate": 12},
                      {"name": "X", "gtin": "2064000002134", "mhd_monate": 12}):  # EAN schon vergeben
            with self.assertRaises(EingabeFehler, msg=daten):
                self.dienst.produkt_speichern(daten)
        self.assertEqual(self.dienst.produkte(), vorher)

    def test_loeschen(self):
        self.dienst.produkt_loeschen("kolumbien")
        self.assertEqual([p.id for p in self.dienst.produkte()], ["espresso-guatemala"])
        with self.assertRaisesRegex(EingabeFehler, "letzte"):
            self.dienst.produkt_loeschen("espresso-guatemala")
        with self.assertRaises(EingabeFehler):
            self.dienst.produkt_loeschen("gibt-es-nicht")


if __name__ == "__main__":
    unittest.main()
