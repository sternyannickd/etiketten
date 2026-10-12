"""Erlaubt Schreibzugriffe in fremde Projekte nur auf die Schnittstellen-Datei.

Läuft als PreToolUse-Hook vor Edit/Write/NotebookEdit. Welche fremden Projekte es
gibt und welche Datei dort jeweils beschrieben werden darf, steht in
`.claude/schnittstelle.json` (Pfade relativ zum Projektordner):

    {"fremde_projekte": {"../labels": ["TOSTO.md"]}}

Das Skript ist in jedem Projekt gleich, nur die JSON-Datei unterscheidet sich.
Exit-Code 2 blockiert den Zugriff, die Meldung geht an Claude.
"""

import json
import os
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]


def normal(pfad: Path) -> str:
    return os.path.normcase(os.path.abspath(pfad))


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    eingabe = json.load(sys.stdin)
    werkzeug = eingabe.get("tool_input", {})
    datei = werkzeug.get("file_path") or werkzeug.get("notebook_path")
    if not datei:
        return 0
    ziel = normal(Path(datei))

    regeln = json.loads((PROJEKT / ".claude" / "schnittstelle.json").read_text(encoding="utf-8"))
    for ordner, erlaubt in regeln["fremde_projekte"].items():
        fremd = normal(PROJEKT / ordner)
        if ziel == fremd or ziel.startswith(fremd + os.sep):
            if ziel in {normal(PROJEKT / ordner / name) for name in erlaubt}:
                return 0
            print(
                f"Gesperrt: {datei} gehört zu einem anderen Projekt. Von hier aus darf dort "
                f"nur {', '.join(erlaubt)} geschrieben werden (siehe schnittstelle/README.md).",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as fehler:  # im Zweifel sperren, nie still durchlassen
        print(f"Schnittstellen-Hook fehlgeschlagen, Schreiben gesperrt: {fehler}", file=sys.stderr)
        sys.exit(2)
