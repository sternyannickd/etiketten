"""Konfiguration laden: config.toml mit eingebauten Standardwerten zusammenführen."""

from __future__ import annotations

import copy
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJEKT_DIR = Path(__file__).resolve().parent.parent
STANDARD_PFAD = PROJEKT_DIR / "config.toml"

STANDARD: dict = {
    "produkte": "data/produkte.csv",
    "protokoll": "var/druckprotokoll.csv",
    "server": {"host": "127.0.0.1", "port": 8077},
    "drucker": {
        "name": "Citizen CL-S521",
        "dpi": 203,
        "transport": "usb",
        "usb_geraet": "auto",
        "usb_kennung": "CITIZEN",
        "cups_warteschlange": "Citizen_CL_S521_raw",
        "tcp_host": "",
        "tcp_port": 9100,
        "zeichensatz": "utf8",
    },
    "vorschau": {
        "aktiv": True,
        "url": "https://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{breite_zoll}x{hoehe_zoll}/0/",
        "timeout_s": 5,
    },
    "etikett": {"breite": 57.0, "hoehe": 32.0, "versatz_x": 0.0, "versatz_y": 0.0},
    "layout": {
        "titel": {
            "x": 2.0, "y": 2.0, "breite": 40.0, "hoehe": 9.0,
            "max_zeilen": 2, "schrift_max": 5.0, "schrift_min": 3.0,
        },
        "barcode": {"x": 2.0, "y": 12.0, "modul": 3, "balkenhoehe": 14.0},
        "mhd": {
            "x": 46.5, "y": 2.0, "laenge": 28.0, "einzeilig": True,
            "beschriftung": "MHD:", "beschriftung_schrift": 2.6,
            "datum_schrift": 4.6, "datumsformat": "%d.%m.%Y",
        },
    },
}


class KonfigFehler(Exception):
    pass


def _mischen(basis: dict, ueber: dict) -> dict:
    ergebnis = copy.deepcopy(basis)
    for schluessel, wert in ueber.items():
        if isinstance(wert, dict) and isinstance(ergebnis.get(schluessel), dict):
            ergebnis[schluessel] = _mischen(ergebnis[schluessel], wert)
        else:
            ergebnis[schluessel] = wert
    return ergebnis


@dataclass
class Konfig:
    daten: dict
    basis_dir: Path

    def __getitem__(self, schluessel: str):
        return self.daten[schluessel]

    def pfad(self, wert: str) -> Path | None:
        """Pfad aus der Konfiguration relativ zur Konfigurationsdatei auflösen."""
        if not wert:
            return None
        p = Path(wert).expanduser()
        return p if p.is_absolute() else self.basis_dir / p

    @property
    def produkte_pfad(self) -> Path:
        return self.pfad(self.daten["produkte"])

    @property
    def protokoll_pfad(self) -> Path | None:
        return self.pfad(self.daten.get("protokoll", ""))


def laden(pfad: str | os.PathLike | None = None) -> Konfig:
    """Konfiguration laden. Ohne Pfad: $ETIKETTEN_CONFIG oder config.toml im Projekt."""
    pfad = Path(pfad or os.environ.get("ETIKETTEN_CONFIG") or STANDARD_PFAD)
    if not pfad.exists():
        raise KonfigFehler(f"Konfigurationsdatei nicht gefunden: {pfad}")
    try:
        with pfad.open("rb") as f:
            eigene = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise KonfigFehler(f"{pfad}: {e}") from e
    return Konfig(_mischen(STANDARD, eigene), pfad.resolve().parent)


def standard() -> Konfig:
    """Nur die eingebauten Standardwerte (für Tests)."""
    return Konfig(copy.deepcopy(STANDARD), PROJEKT_DIR)
