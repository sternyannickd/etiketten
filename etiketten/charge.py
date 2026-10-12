"""Chargennummer der Röstung: „Rö“ + Röstdatum JJMMTT + „-“ + laufende Nummer.

Beispiel: Rö261012-01 = erste Röstung am 12.10.2026. Das Röstdatum steckt in
der Nummer und wird daraus gelesen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MUSTER = re.compile(r"r[öo]e?(\d{2})(\d{2})(\d{2})-(\d{2})", re.IGNORECASE)
BEISPIEL = "Rö261012-01"


class ChargeFehler(ValueError):
    pass


@dataclass(frozen=True)
class Charge:
    roestdatum: date
    nummer: int

    @property
    def text(self) -> str:
        return f"Rö{self.roestdatum:%y%m%d}-{self.nummer:02d}"


def lesen(text: str) -> Charge:
    """Chargennummer prüfen und zerlegen. Toleriert „Ro“/„Roe“ und Kleinschreibung,
    das Ergebnis ist immer in der Schreibweise „Rö…“."""
    roh = (text or "").strip()
    treffer = MUSTER.fullmatch(roh)
    if not treffer:
        raise ChargeFehler(f"Charge {roh!r} hat nicht das Format RöJJMMTT-NN (z. B. {BEISPIEL})")
    jj, mm, tt, nr = (int(t) for t in treffer.groups())
    try:
        roestdatum = date(2000 + jj, mm, tt)
    except ValueError:
        raise ChargeFehler(f"Charge {roh}: {tt:02d}.{mm:02d}.{2000 + jj} ist kein gültiges Datum") from None
    if nr < 1:
        raise ChargeFehler(f"Charge {roh}: die laufende Nummer beginnt bei 01")
    return Charge(roestdatum, nr)
