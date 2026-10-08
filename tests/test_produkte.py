import copy
import json
import unittest
from pathlib import Path

from etiketten import produkte
from etiketten.config import PROJEKT_DIR

from .hilfen import KAFFEES, test_konfig, version


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
        liste = produkte.laden(PROJEKT_DIR / "data" / "produkte.json")
        self.assertGreaterEqual(len(liste), 6)

    def test_kaffee_mit_versionen(self):
        k = produkte.laden(test_konfig().produkte_pfad)[1]
        self.assertEqual(k.name, "Espresso|Guatemala")
        self.assertEqual(k.anzeigename, "Espresso Guatemala")
        self.assertEqual([v.bezeichnung for v in k.versionen], ["Edeka", "Rewe"])

    def test_version_waehlen(self):
        kolumbien, guatemala = produkte.laden(test_konfig().produkte_pfad)
        self.assertEqual(kolumbien.version(None).id, "edeka")      # nur eine aktive
        self.assertEqual(guatemala.version("rewe").gtin, "4006381333931")
        with self.assertRaisesRegex(produkte.ProduktFehler, "Version wählen"):
            guatemala.version(None)
        with self.assertRaises(produkte.ProduktFehler):
            guatemala.version("lidl")

    def test_archivierte_version_zaehlt_nicht(self):
        daten = copy.deepcopy(KAFFEES)
        daten[1]["versionen"][1]["archiviert"] = True
        guatemala = produkte.laden(test_konfig(daten).produkte_pfad)[1]
        self.assertEqual(guatemala.version(None).id, "edeka")

    def test_fehler_werden_gesammelt(self):
        daten = [
            {"id": "a", "name": "A", "mhd_monate": 0, "versionen": [version("x", "X", "2064000002135")]},
            {"id": "b", "name": "", "mhd_monate": 12, "versionen": []},
        ]
        with self.assertRaises(produkte.ProduktFehler) as ctx:
            produkte.laden(test_konfig(daten).produkte_pfad)
        text = str(ctx.exception)
        self.assertIn("Haltbarkeit", text)
        self.assertIn("Prüfziffer", text)
        self.assertIn("name fehlt", text)
        self.assertIn("mindestens eine Version", text)

    def test_doppelte_gtin(self):
        daten = copy.deepcopy(KAFFEES)
        daten[1]["versionen"][1]["gtin"] = "2064000002134"
        with self.assertRaisesRegex(produkte.ProduktFehler, "schon vergeben"):
            produkte.laden(test_konfig(daten).produkte_pfad)

    def test_kaputtes_json(self):
        with self.assertRaisesRegex(produkte.ProduktFehler, "JSON"):
            produkte.laden(test_konfig(roh="{kaputt").produkte_pfad)

    def test_fehlende_datei(self):
        with self.assertRaises(produkte.ProduktFehler):
            produkte.laden(Path("/gibt/es/nicht.json"))


class SpeichernTest(unittest.TestCase):
    def test_ids_aus_namen(self):
        k = produkte.kaffee_aus_dict({"name": "Äthiopien|Sidamo", "mhd_monate": 12, "versionen": [
            {"bezeichnung": "Rewe 1 kg", "gtin": "4006381333931"},
            {"bezeichnung": "Rewe 1 kg", "gtin": "2064000002134"}]})
        k = produkte.ids_vergeben(k, {"aethiopien-sidamo"})
        self.assertEqual(k.id, "aethiopien-sidamo-2")
        self.assertEqual([v.id for v in k.versionen], ["rewe-1-kg", "rewe-1-kg-2"])

    def test_speichern_und_wieder_laden(self):
        pfad = test_konfig().produkte_pfad
        liste = produkte.laden(pfad)
        produkte.speichern(pfad, liste)
        self.assertEqual(produkte.laden(pfad), liste)
        self.assertNotIn("anzeigename", json.loads(pfad.read_text(encoding="utf-8"))["kaffees"][0])
        self.assertEqual([p.name for p in pfad.parent.iterdir() if p.suffix == ".tmp"], [])


if __name__ == "__main__":
    unittest.main()
