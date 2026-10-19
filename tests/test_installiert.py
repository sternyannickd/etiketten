"""Installierte Betriebsart: Datenordner wird selbst angelegt, nichts geht kaputt."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etiketten import config, produkte


class InstalliertTest(unittest.TestCase):
    def setUp(self):
        self.ordner = Path(tempfile.mkdtemp(prefix="etiketten-daten-")) / "Etikettendruck"

    def laden(self):
        return config.laden_installiert(self.ordner)

    def test_erster_start_legt_alles_an(self):
        k = self.laden()
        self.assertTrue(k.installiert)
        self.assertTrue((self.ordner / "config.toml").exists())
        self.assertTrue((self.ordner / "var").is_dir())
        self.assertEqual(k.produkte_pfad, self.ordner / "data" / "produkte.csv")
        # Startliste aus dem Repo
        self.assertEqual(produkte.laden(k.produkte_pfad), produkte.laden(config.START_PRODUKTE))
        self.assertEqual(k.warnungen, [])

    def test_eigene_produkte_bleiben_beim_update(self):
        k = self.laden()
        produkte.speichern(k.produkte_pfad, [produkte.Produkt("eigen", "Eigen", "4006381333931", 3)])
        k = self.laden()   # nächster Start / nach Update
        self.assertEqual([p.id for p in produkte.laden(k.produkte_pfad)], ["eigen"])

    def test_lokale_einstellung_ueberschreibt_mitgelieferte(self):
        self.laden()
        (self.ordner / "config.toml").write_text('[drucker]\ntransport = "tcp"\ntcp_host = "1.2.3.4"\n',
                                                 encoding="utf-8")
        k = self.laden()
        self.assertEqual(k["drucker"]["transport"], "tcp")
        # Alles andere aus der mitgelieferten config.toml
        self.assertEqual(k["layout"]["barcode"]["modul"], 3)

    def test_kaputte_einstellungen_werden_ersetzt(self):
        self.laden()
        (self.ordner / "config.toml").write_text("[drucker\nkaputt", encoding="utf-8")
        k = self.laden()
        self.assertEqual(len(k.warnungen), 1)
        self.assertEqual(len(list(self.ordner.glob("config.toml.defekt-*"))), 1)
        self.assertEqual(k["drucker"]["transport"], "auto")

    def test_umgebungsvariable_waehlt_installierte_betriebsart(self):
        with mock.patch.dict(os.environ, {"ETIKETTEN_DATEN": str(self.ordner)}):
            os.environ.pop("ETIKETTEN_CONFIG", None)
            k = config.laden()
        self.assertTrue(k.installiert)
        self.assertEqual(k.basis_dir, self.ordner.resolve())

    def test_daten_dir_je_system(self):
        with mock.patch.object(config.sys, "platform", "win32"), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}):
            os.environ.pop("ETIKETTEN_DATEN", None)
            self.assertEqual(config.daten_dir().name, "Etikettendruck")
        with mock.patch.object(config.sys, "platform", "linux"), \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/home/x/.local/share"}):
            os.environ.pop("ETIKETTEN_DATEN", None)
            self.assertEqual(config.daten_dir(), Path("/home/x/.local/share/etikettendruck"))


if __name__ == "__main__":
    unittest.main()
