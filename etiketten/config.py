"""Konfiguration laden: config.toml mit eingebauten Standardwerten zusammenführen.

Zwei Betriebsarten:

- **Aus dem Quellcode** (``./start.sh``, ``python3 -m etiketten``): wie bisher
  ``config.toml`` und ``data/produkte.csv`` im Projektordner.
- **Installiert** (fertiges Programm aus dem Installer): Alle eigenen Daten liegen
  in einem Datenordner pro Benutzer (siehe ``daten_dir``), den das Programm bei
  jedem Start selbst anlegt bzw. ergänzt. Die mitgelieferte ``config.toml`` gilt
  als Grundeinstellung und kommt mit jedem Update neu; die ``config.toml`` im
  Datenordner enthält nur Abweichungen für diesen Rechner. Die mitgelieferte
  Produktliste wird nur beim ersten Start kopiert; danach gilt die eigene.
"""

from __future__ import annotations

import copy
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

GEPACKT = bool(getattr(sys, "frozen", False))
# Mitgelieferte Dateien: im Quellcode der Projektordner, im fertigen Programm
# der Ordner, in dem PyInstaller sie ablegt.
PROJEKT_DIR = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent.parent)
STANDARD_PFAD = PROJEKT_DIR / "config.toml"
START_PRODUKTE = PROJEKT_DIR / "data" / "produkte.csv"

LOKALE_VORLAGE = """\
# Eigene Einstellungen für diesen Rechner.
#
# Alles, was hier nicht steht, kommt aus dem Programm selbst und wird bei
# Updates mit aktualisiert. Hier nur eintragen, was auf diesem Rechner anders
# sein soll. Zum Aktivieren das # am Zeilenanfang entfernen.
# Danach das Programm beenden (Werkzeuge → Programm beenden) und neu starten.

# [drucker]
# Druckweg: "auto" (Standard: Windows-Drucker bzw. USB unter Linux),
#           "windows", "usb", "cups", "tcp" oder "datei" (Trockenlauf)
# transport = "tcp"
# tcp_host = "192.168.1.50"
#
# Windows: Druckername genau wie unter Einstellungen → Drucker,
#          "auto" = erster Drucker mit CITIZEN im Namen
# windows_drucker = "CITIZEN CL-S521"
#
# Falls Umlaute falsch gedruckt werden:
# zeichensatz = "latin1"

# [etikett]
# Kalibrierung in mm (positiv = nach rechts/unten):
# versatz_x = 0.5
# versatz_y = 0.0

# [vorschau]
# aktiv = false
"""

STANDARD: dict = {
    "produkte": "data/produkte.csv",
    "protokoll": "var/druckprotokoll.csv",
    "server": {"host": "127.0.0.1", "port": 8077, "erlaubte_namen": []},
    "drucker": {
        "name": "Citizen CL-S521",
        "dpi": 203,
        "transport": "auto",
        "usb_geraet": "auto",
        "usb_kennung": "CITIZEN",
        "cups_warteschlange": "Citizen_CL_S521_raw",
        "windows_drucker": "auto",
        "windows_kennung": "CITIZEN",
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
    installiert: bool = False
    warnungen: list[str] = field(default_factory=list)

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


def _toml(pfad: Path) -> dict:
    try:
        with pfad.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise KonfigFehler(f"{pfad}: {e}") from e


def daten_dir() -> Path:
    """Datenordner des installierten Programms (überschreibbar mit $ETIKETTEN_DATEN)."""
    if os.environ.get("ETIKETTEN_DATEN"):
        return Path(os.environ["ETIKETTEN_DATEN"]).expanduser()
    if sys.platform == "win32":
        basis = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(basis) / "Etikettendruck"
    basis = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(basis) / "etikettendruck"


def _beiseitelegen(pfad: Path) -> Path:
    ziel = pfad.with_name(f"{pfad.name}.defekt-{datetime.now():%Y%m%d-%H%M%S}")
    pfad.replace(ziel)
    return ziel


def einrichten(ordner: Path) -> list[str]:
    """Fehlende Ordner und Dateien im Datenordner anlegen. Vorhandenes bleibt unangetastet.

    Gibt Warnungen zurück (z. B. wenn eine kaputte config.toml ersetzt wurde).
    """
    warnungen = []
    for unter in ("", "data", "var"):
        (ordner / unter).mkdir(parents=True, exist_ok=True)
    lokal = ordner / "config.toml"
    if lokal.exists():
        try:
            _toml(lokal)
        except KonfigFehler as e:
            ziel = _beiseitelegen(lokal)
            warnungen.append(f"Die Einstellungsdatei war fehlerhaft und wurde neu angelegt "
                             f"(alte Fassung: {ziel.name}). Fehler: {e}")
    if not lokal.exists():
        lokal.write_text(LOKALE_VORLAGE, encoding="utf-8")
    produkte = ordner / "data" / "produkte.csv"
    if not produkte.exists():
        if START_PRODUKTE.exists():
            shutil.copyfile(START_PRODUKTE, produkte)
        else:
            produkte.write_text("id,name,gtin,mhd_monate\n", encoding="utf-8")
    return warnungen


def laden_installiert(ordner: Path | None = None) -> Konfig:
    """Grundeinstellung des Programms + eigene config.toml aus dem Datenordner."""
    ordner = ordner or daten_dir()
    warnungen = einrichten(ordner)
    mitgeliefert = _toml(STANDARD_PFAD) if STANDARD_PFAD.exists() else {}
    # Die Pfade gelten immer im Datenordner, egal was mitgeliefert wird.
    mitgeliefert |= {"produkte": STANDARD["produkte"], "protokoll": STANDARD["protokoll"]}
    daten = _mischen(_mischen(STANDARD, mitgeliefert), _toml(ordner / "config.toml"))
    return Konfig(daten, ordner.resolve(), installiert=True, warnungen=warnungen)


def laden(pfad: str | os.PathLike | None = None) -> Konfig:
    """Konfiguration laden.

    Reihenfolge: ausdrücklicher Pfad bzw. $ETIKETTEN_CONFIG → Datenordner, wenn
    installiert (oder $ETIKETTEN_DATEN gesetzt) → config.toml im Projektordner.
    """
    pfad = pfad or os.environ.get("ETIKETTEN_CONFIG")
    if not pfad and (GEPACKT or os.environ.get("ETIKETTEN_DATEN") or not STANDARD_PFAD.exists()):
        return laden_installiert()
    pfad = Path(pfad or STANDARD_PFAD)
    if not pfad.exists():
        raise KonfigFehler(f"Konfigurationsdatei nicht gefunden: {pfad}")
    return Konfig(_mischen(STANDARD, _toml(pfad)), pfad.resolve().parent)


def standard() -> Konfig:
    """Nur die eingebauten Standardwerte (für Tests)."""
    return Konfig(copy.deepcopy(STANDARD), PROJEKT_DIR)
