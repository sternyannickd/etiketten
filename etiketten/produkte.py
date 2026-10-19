"""Produktliste aus CSV lesen, prüfen und schreiben."""

from __future__ import annotations

import csv
import os
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

PFLICHTSPALTEN = ("id", "name", "gtin", "mhd_monate")


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


@dataclass(frozen=True)
class Produkt:
    id: str
    name: str            # "|" erzwingt einen Zeilenumbruch, z. B. "Espresso|Guatemala"
    gtin: str
    mhd_monate: int

    @property
    def anzeigename(self) -> str:
        return " ".join(teil.strip() for teil in self.name.split("|"))

    def als_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.anzeigename,
            "etikett_name": self.name,   # mit "|" für den Zeilenumbruch, zum Bearbeiten
            "gtin": self.gtin,
            "mhd_monate": self.mhd_monate,
        }


def pruefen(pid: str, name: str, gtin: str, monate_text) -> tuple[Produkt | None, str | None]:
    """Ein Produkt aus Rohwerten bauen. Gibt (Produkt, None) oder (None, Fehlermeldung) zurück."""
    pid, name, gtin = pid.strip(), name.strip(), gtin.strip().replace(" ", "")
    monate_text = str(monate_text if monate_text is not None else "").strip()
    if not pid or not name:
        return None, "id und name dürfen nicht leer sein"
    if any(z in name for z in "\r\n\t"):
        return None, "Der Name darf keine Zeilenumbrüche enthalten (Umbruch erzwingen mit |)"
    if len(name) > 80:
        return None, "Der Name ist zu lang (max. 80 Zeichen)"
    if (meldung := ean13_pruefen(gtin)):
        return None, meldung
    try:
        monate = int(monate_text)
        if not 1 <= monate <= 60:
            raise ValueError
    except ValueError:
        return None, f"mhd_monate muss 1–60 sein, ist {monate_text!r}"
    return Produkt(pid, name, gtin, monate), None


def neue_id(name: str, vorhandene: set[str]) -> str:
    """Kurzname aus dem Produktnamen, z. B. "Espresso|Guatemala" → "espresso-guatemala"."""
    text = name.replace("|", " ").lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    basis = re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "produkt"
    kandidat, nr = basis, 2
    while kandidat in vorhandene:
        kandidat, nr = f"{basis}-{nr}", nr + 1
    return kandidat


def speichern(pfad: Path, liste: list[Produkt]) -> None:
    """Liste schreiben, ohne dass ein Absturz mittendrin die Datei zerstört.

    Die bisherige Datei bleibt als produkte.csv.bak erhalten. Die neue wird erst
    vollständig in eine Temp-Datei geschrieben und dann in einem Schritt ersetzt.
    """
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if pfad.exists():
        shutil.copy2(pfad, pfad.with_name(pfad.name + ".bak"))
    fd, temp = tempfile.mkstemp(prefix=".produkte-", suffix=".csv", dir=pfad.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(PFLICHTSPALTEN)
            for p in liste:
                w.writerow([p.id, p.name, p.gtin, p.mhd_monate])
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, pfad)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def laden(pfad: Path) -> list[Produkt]:
    """CSV lesen. Fehler in einzelnen Zeilen werden gesammelt und gemeinsam gemeldet."""
    if not pfad.exists():
        raise ProduktFehler(f"Produktliste nicht gefunden: {pfad}")
    with pfad.open(encoding="utf-8-sig", newline="") as f:
        leser = csv.DictReader(f)
        fehlend = [s for s in PFLICHTSPALTEN if s not in (leser.fieldnames or [])]
        if fehlend:
            raise ProduktFehler(f"{pfad.name}: Spalten fehlen: {', '.join(fehlend)}")
        produkte, fehler, ids = [], [], set()
        for nr, zeile in enumerate(leser, start=2):
            if not any((wert or "").strip() for wert in zeile.values()):
                continue
            pid = (zeile["id"] or "").strip()
            name = (zeile["name"] or "").strip()
            ort = f"{pfad.name} Zeile {nr}"
            if pid and pid in ids:
                fehler.append(f"{ort}: id {pid!r} kommt doppelt vor")
                continue
            produkt, meldung = pruefen(pid, name, zeile["gtin"] or "", zeile["mhd_monate"])
            if meldung:
                fehler.append(f"{ort}" + (f" ({name})" if name and pid else "") + f": {meldung}")
                continue
            ids.add(pid)
            produkte.append(produkt)
    if fehler:
        raise ProduktFehler("\n".join(fehler))
    if not produkte:
        raise ProduktFehler(f"{pfad.name} enthält keine Produkte")
    return produkte
