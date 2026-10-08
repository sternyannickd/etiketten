"""Gemeinsame Test-Hilfen: eine Konfiguration im Temp-Ordner mit Trockenlauf-Druckweg."""

import copy
import json
import tempfile
from pathlib import Path

from etiketten import config


def version(vid, bezeichnung, gtin, **extra):
    return {"id": vid, "bezeichnung": bezeichnung, "gtin": gtin, "layout": "standard",
            "archiviert": False, **extra}


KAFFEES = [
    {"id": "kolumbien", "name": "Kolumbien", "mhd_monate": 12, "archiviert": False,
     "versionen": [version("edeka", "Edeka", "2064000002134")]},
    {"id": "espresso-guatemala", "name": "Espresso|Guatemala", "mhd_monate": 9, "archiviert": False,
     "versionen": [version("edeka", "Edeka", "2064200000138"),
                   version("rewe", "Rewe", "4006381333931")]},
]


def test_konfig(kaffees=None, roh: str | None = None) -> config.Konfig:
    """Konfiguration mit Produktliste. `roh` schreibt den Dateiinhalt unverändert."""
    ordner = Path(tempfile.mkdtemp(prefix="etiketten-test-"))
    inhalt = roh if roh is not None else json.dumps(
        {"format": 1, "kaffees": KAFFEES if kaffees is None else kaffees})
    (ordner / "produkte.json").write_text(inhalt, encoding="utf-8")
    daten = copy.deepcopy(config.STANDARD)
    daten["produkte"] = "produkte.json"
    daten["protokoll"] = "var/protokoll.csv"
    daten["drucker"]["transport"] = "datei"
    daten["vorschau"]["aktiv"] = False
    return config.Konfig(daten, ordner)
