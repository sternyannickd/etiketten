"""Produktliste: Kaffees mit Versionen (je Version eine GTIN), gespeichert als JSON.

Aufbau von data/produkte.json:

    {"format": 1,
     "kaffees": [
       {"id": "kolumbien", "name": "Kolumbien", "mhd_monate": 12, "archiviert": false,
        "versionen": [
          {"id": "edeka", "bezeichnung": "Edeka", "gtin": "2064000002134",
           "layout": "standard", "archiviert": false}]}]}

Ein Kaffee hat eine Haltbarkeit und beliebig viele Versionen, z. B. eine für
Edeka und eine für Rewe. Gelöscht wird nichts, nur archiviert, damit das
Druckprotokoll lesbar bleibt.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

FORMAT = 1
LAYOUTS = ("standard",)   # später weitere Etikett-Designs
MHD_MONATE = (1, 60)
UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


class ProduktFehler(Exception):
    pass


def ean13_pruefziffer(zwoelf: str) -> int:
    """Prüfziffer für die ersten 12 Ziffern einer EAN-13."""
    summe = sum(int(z) * (3 if i % 2 else 1) for i, z in enumerate(zwoelf))
    return (10 - summe % 10) % 10


def ean13_pruefen(gtin: str) -> str | None:
    """Gibt eine Fehlermeldung zurück oder None, wenn die EAN-13 gültig ist."""
    if len(gtin) != 13 or not gtin.isdigit():
        return f"EAN muss genau 13 Ziffern haben, ist aber {gtin!r}"
    soll = ean13_pruefziffer(gtin[:12])
    if int(gtin[12]) != soll:
        return f"Prüfziffer von {gtin} falsch (müsste {soll} sein)"
    return None


def kurzname(text: str) -> str:
    """„Espresso|Guatemala“ → „espresso-guatemala“ (für IDs)."""
    text = text.lower().translate(UMLAUTE)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "x"


def _eindeutig(basis: str, vergeben: set[str]) -> str:
    kandidat, n = basis, 2
    while kandidat in vergeben:
        kandidat, n = f"{basis}-{n}", n + 1
    return kandidat


@dataclass(frozen=True)
class Version:
    id: str
    bezeichnung: str     # frei, z. B. „Edeka“, „Rewe 1 kg“
    gtin: str
    layout: str = "standard"
    archiviert: bool = False

    def als_dict(self) -> dict:
        return {"id": self.id, "bezeichnung": self.bezeichnung, "gtin": self.gtin,
                "layout": self.layout, "archiviert": self.archiviert}


@dataclass(frozen=True)
class Kaffee:
    id: str
    name: str            # "|" erzwingt einen Zeilenumbruch, z. B. "Espresso|Guatemala"
    mhd_monate: int
    versionen: tuple[Version, ...]
    archiviert: bool = False

    @property
    def anzeigename(self) -> str:
        return " ".join(teil.strip() for teil in self.name.split("|"))

    @property
    def aktive_versionen(self) -> tuple[Version, ...]:
        return tuple(v for v in self.versionen if not v.archiviert)

    def version(self, version_id: str | None) -> Version:
        """Version nach ID. Ohne ID: die einzige aktive Version, sonst Fehler."""
        if version_id:
            for v in self.versionen:
                if v.id == version_id:
                    return v
            raise ProduktFehler(f"{self.anzeigename}: unbekannte Version {version_id!r}")
        aktiv = self.aktive_versionen
        if len(aktiv) == 1:
            return aktiv[0]
        if not aktiv:
            raise ProduktFehler(f"{self.anzeigename} hat keine aktive Version")
        namen = ", ".join(v.bezeichnung for v in aktiv)
        raise ProduktFehler(f"{self.anzeigename}: bitte Version wählen ({namen})")

    def als_dict(self, mit_archiv: bool = True) -> dict:
        versionen = self.versionen if mit_archiv else self.aktive_versionen
        return {"id": self.id, "name": self.name, "anzeigename": self.anzeigename,
                "mhd_monate": self.mhd_monate, "archiviert": self.archiviert,
                "versionen": [v.als_dict() for v in versionen]}


# --- Eingaben prüfen ------------------------------------------------------------

def _text(daten: dict, feld: str, ort: str, fehler: list[str]) -> str:
    wert = daten.get(feld)
    if not isinstance(wert, str) or not wert.strip():
        fehler.append(f"{ort}: {feld} fehlt")
        return ""
    return wert.strip()


def _version(daten, ort: str, fehler: list[str]) -> Version | None:
    if not isinstance(daten, dict):
        fehler.append(f"{ort}: ungültige Angaben")
        return None
    bezeichnung = _text(daten, "bezeichnung", ort, fehler)
    ort = f"{ort} ({bezeichnung})" if bezeichnung else ort
    gtin = str(daten.get("gtin") or "").strip()
    if (meldung := ean13_pruefen(gtin)):
        fehler.append(f"{ort}: {meldung}")
    layout = daten.get("layout") or "standard"
    if layout not in LAYOUTS:
        fehler.append(f"{ort}: unbekanntes Layout {layout!r}")
    return Version(str(daten.get("id") or "").strip(), bezeichnung, gtin, layout,
                   bool(daten.get("archiviert")))


def kaffee_aus_dict(daten, ort: str = "Kaffee") -> Kaffee:
    """Einen Kaffee aus JSON-Daten bauen. Fehler werden gesammelt gemeldet.
    Fehlende IDs (neuer Kaffee, neue Version) bleiben leer und werden von
    `ids_vergeben` gesetzt."""
    if not isinstance(daten, dict):
        raise ProduktFehler(f"{ort}: ungültige Angaben")
    fehler: list[str] = []
    name = _text(daten, "name", ort, fehler)
    ort = f"{ort} „{name.replace('|', ' ')}“" if name else ort
    try:
        monate = int(daten.get("mhd_monate"))
        if not MHD_MONATE[0] <= monate <= MHD_MONATE[1]:
            raise ValueError
    except (TypeError, ValueError):
        fehler.append(f"{ort}: Haltbarkeit muss {MHD_MONATE[0]}–{MHD_MONATE[1]} Monate sein, "
                      f"ist {daten.get('mhd_monate')!r}")
        monate = 0
    roh = daten.get("versionen")
    if not isinstance(roh, list) or not roh:
        fehler.append(f"{ort}: braucht mindestens eine Version")
        roh = []
    versionen = [_version(v, f"{ort}, Version {i}", fehler) for i, v in enumerate(roh, start=1)]
    if fehler:
        raise ProduktFehler("\n".join(fehler))
    return Kaffee(str(daten.get("id") or "").strip(), name, monate,
                  tuple(v for v in versionen if v), bool(daten.get("archiviert")))


def ids_vergeben(kaffee: Kaffee, vergebene_kaffee_ids: set[str]) -> Kaffee:
    """Leere IDs aus Name bzw. Bezeichnung ableiten, eindeutig machen."""
    kid = kaffee.id or _eindeutig(kurzname(kaffee.name), vergebene_kaffee_ids)
    vergeben: set[str] = {v.id for v in kaffee.versionen if v.id}
    versionen = []
    for v in kaffee.versionen:
        if not v.id:
            v = replace(v, id=_eindeutig(kurzname(v.bezeichnung), vergeben))
            vergeben.add(v.id)
        versionen.append(v)
    return replace(kaffee, id=kid, versionen=tuple(versionen))


def pruefen(kaffees: list[Kaffee]) -> None:
    """Regeln über die ganze Liste: IDs eindeutig, jede GTIN nur einmal."""
    fehler, ids, gtins = [], set(), {}
    for k in kaffees:
        if k.id in ids:
            fehler.append(f"Kaffee-ID {k.id!r} kommt doppelt vor")
        ids.add(k.id)
        vids = set()
        for v in k.versionen:
            if v.id in vids:
                fehler.append(f"{k.anzeigename}: Version {v.id!r} kommt doppelt vor")
            vids.add(v.id)
            if v.gtin in gtins:
                fehler.append(f"GTIN {v.gtin} ist schon vergeben ({gtins[v.gtin]})")
            gtins[v.gtin] = f"{k.anzeigename} – {v.bezeichnung}"
    if fehler:
        raise ProduktFehler("\n".join(fehler))


# --- Datei ----------------------------------------------------------------------

def laden(pfad: Path) -> list[Kaffee]:
    if not pfad.exists():
        raise ProduktFehler(f"Produktliste nicht gefunden: {pfad}")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProduktFehler(f"{pfad.name} ist kein gültiges JSON: {e}") from None
    if not isinstance(daten, dict) or not isinstance(daten.get("kaffees"), list):
        raise ProduktFehler(f"{pfad.name}: Liste „kaffees“ fehlt")
    if daten.get("format") != FORMAT:
        raise ProduktFehler(f"{pfad.name}: unbekanntes Format {daten.get('format')!r}")
    kaffees, fehler = [], []
    for nr, eintrag in enumerate(daten["kaffees"], start=1):
        try:
            k = kaffee_aus_dict(eintrag, f"{pfad.name}, Kaffee {nr}")
            if not k.id or any(not v.id for v in k.versionen):
                raise ProduktFehler(f"{pfad.name}, Kaffee {nr}: IDs fehlen")
            kaffees.append(k)
        except ProduktFehler as e:
            fehler.append(str(e))
    if fehler:
        raise ProduktFehler("\n".join(fehler))
    pruefen(kaffees)
    return kaffees


def speichern(pfad: Path, kaffees: list[Kaffee]) -> None:
    """Atomar schreiben: erst Temp-Datei, dann umbenennen. Nie halb geschriebene Dateien."""
    pruefen(kaffees)
    eintraege = [{f: w for f, w in k.als_dict().items() if f != "anzeigename"} for k in kaffees]
    inhalt = json.dumps({"format": FORMAT, "kaffees": eintraege},
                        ensure_ascii=False, indent=2)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=pfad.parent, prefix=f".{pfad.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(inhalt + "\n")
        os.replace(tmp, pfad)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
