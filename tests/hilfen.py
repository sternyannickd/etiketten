"""Gemeinsame Test-Hilfen: eine Konfiguration im Temp-Ordner mit Trockenlauf-Druckweg."""

import copy
import tempfile
from pathlib import Path

from etiketten import config

PRODUKTE = """id,name,gtin,mhd_monate
kolumbien,Kolumbien,2064000002134,12
espresso-guatemala,Espresso|Guatemala,2064200000138,9
"""


def test_konfig(produkte_csv: str = PRODUKTE) -> config.Konfig:
    ordner = Path(tempfile.mkdtemp(prefix="etiketten-test-"))
    (ordner / "produkte.csv").write_text(produkte_csv, encoding="utf-8")
    daten = copy.deepcopy(config.STANDARD)
    daten["produkte"] = "produkte.csv"
    daten["protokoll"] = "var/protokoll.csv"
    daten["drucker"]["transport"] = "datei"
    daten["vorschau"]["aktiv"] = False
    return config.Konfig(daten, ordner)
