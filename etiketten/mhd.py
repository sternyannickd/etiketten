"""Mindesthaltbarkeitsdatum berechnen."""

from __future__ import annotations

import calendar
from datetime import date


def plus_monate(start: date, monate: int) -> date:
    """Kalendermonate addieren; der Tag wird auf das Monatsende begrenzt (31.01. + 1 → 28./29.02.)."""
    index = start.month - 1 + monate
    jahr, monat = start.year + index // 12, index % 12 + 1
    tag = min(start.day, calendar.monthrange(jahr, monat)[1])
    return date(jahr, monat, tag)


def berechnen(abpackdatum: date, monate: int) -> date:
    return plus_monate(abpackdatum, monate)
