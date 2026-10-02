"""Produktliste aus CSV lesen und prüfen."""

from __future__ import annotations

import csv
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
            "gtin": self.gtin,
            "mhd_monate": self.mhd_monate,
        }


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
            gtin = (zeile["gtin"] or "").strip()
            monate_text = (zeile["mhd_monate"] or "").strip()
            ort = f"{pfad.name} Zeile {nr}"
            if not pid or not name:
                fehler.append(f"{ort}: id und name dürfen nicht leer sein")
                continue
            if pid in ids:
                fehler.append(f"{ort}: id {pid!r} kommt doppelt vor")
                continue
            if (meldung := ean13_pruefen(gtin)):
                fehler.append(f"{ort} ({name}): {meldung}")
                continue
            try:
                monate = int(monate_text)
                if not 1 <= monate <= 60:
                    raise ValueError
            except ValueError:
                fehler.append(f"{ort} ({name}): mhd_monate muss 1–60 sein, ist {monate_text!r}")
                continue
            ids.add(pid)
            produkte.append(Produkt(pid, name, gtin, monate))
    if fehler:
        raise ProduktFehler("\n".join(fehler))
    if not produkte:
        raise ProduktFehler(f"{pfad.name} enthält keine Produkte")
    return produkte
