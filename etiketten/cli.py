"""Kommandozeile: python3 -m etiketten <befehl>"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from datetime import date, datetime

from . import config, drucker, server
from .dienst import Druckdienst, EingabeFehler, VorschauFehler
from .produkte import ProduktFehler


def _datum(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"Datum {text!r} nicht erkannt (z. B. 02.10.2027)")


def cmd_start(dienst: Druckdienst, args) -> int:
    if args.browser:
        port = args.port or dienst.konfig["server"]["port"]
        threading.Timer(0.8, webbrowser.open, [f"http://localhost:{port}"]).start()
    server.starten(dienst, args.host, args.port)
    return 0


def cmd_produkte(dienst: Druckdienst, args) -> int:
    for k in dienst.kaffees(alle=args.alle):
        archiv = "  (archiviert)" if k.archiviert else ""
        print(f"{k.id:<22} {k.mhd_monate:>2} Monate  {k.anzeigename}{archiv}")
        for v in (k.versionen if args.alle else k.aktive_versionen):
            archiv = "  (archiviert)" if v.archiviert else ""
            print(f"    {v.id:<18} {v.gtin}  {v.bezeichnung}{archiv}")
    return 0


def cmd_zpl(dienst: Druckdienst, args) -> int:
    sys.stdout.write(dienst.etikett(args.kaffee, args.version, args.mhd, args.menge))
    return 0


def cmd_drucken(dienst: Druckdienst, args) -> int:
    print(dienst.drucken(args.kaffee, args.version, args.mhd, args.menge))
    return 0


def cmd_testdruck(dienst: Druckdienst, args) -> int:
    print(dienst.testdruck())
    return 0


def cmd_check(dienst: Druckdienst, args) -> int:
    """Alles prüfen, was vor dem ersten Druck stimmen muss."""
    ok = True

    def zeile(gut: bool, text: str, hinweis: str = "") -> None:
        nonlocal ok
        ok &= gut
        print(f"  {'✔' if gut else '✘'} {text}")
        if hinweis:
            print(f"      → {hinweis}")

    k = dienst.konfig
    print("Konfiguration")
    zeile(True, f"geladen aus {k.basis_dir}")
    print("Produkte")
    try:
        liste = dienst.kaffees(alle=True)
        anzahl = sum(len(kf.versionen) for kf in liste)
        zeile(True, f"{len(liste)} Kaffees mit {anzahl} Versionen, alle EANs gültig ({k.produkte_pfad})")
    except ProduktFehler as e:
        zeile(False, str(e).replace("\n", "\n      "))
    print(f"Drucker (Druckweg: {k['drucker']['transport']})")
    status = dienst.status()
    zeile(status.ok, status.meldung, status.hinweis)
    gefunden = drucker.usb_geraete()
    for pfad, kennung in gefunden:
        print(f"      USB: {pfad}  {kennung or '(keine Kennung)'}")
        if "CITIZEN" in kennung.upper() and drucker.spricht_zpl(kennung) is False:
            print("      ⚠ Der Citizen meldet als aktive Druckersprache nicht ZPL. Falls der "
                  "Testdruck nur Zeichensalat oder nichts liefert: Emulation am Drucker auf "
                  "'Zebra' oder 'Auto' stellen (siehe docs/DRUCKER.md).")
    print("Vorschau (optional)")
    if dienst.vorschau_aktiv:
        try:
            dienst.vorschau("^XA^FO20,20^A0N,30,30^FDTest^FS^XZ")
            zeile(True, "labelary.com erreichbar")
        except VorschauFehler as e:
            print(f"  – {e} (Drucken funktioniert trotzdem)")
    else:
        print("  – ausgeschaltet")
    print()
    print("Alles bereit." if ok else "Es gibt Probleme – siehe oben.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="etiketten", description="Etikettendruck für Citizen-Drucker (ZPL)")
    parser.add_argument("--config", help="Pfad zur config.toml")
    sub = parser.add_subparsers(dest="befehl")

    p = sub.add_parser("start", help="Weboberfläche starten (Standard)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--kein-browser", dest="browser", action="store_false",
                   help="Browser nicht automatisch öffnen")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("produkte", help="Kaffees und Versionen anzeigen")
    p.add_argument("--alle", action="store_true", help="auch archivierte zeigen")
    p.set_defaults(func=cmd_produkte)
    sub.add_parser("check", help="Konfiguration, Produkte und Drucker prüfen").set_defaults(func=cmd_check)
    sub.add_parser("testdruck", help="Kalibrier-/Testetikett drucken").set_defaults(func=cmd_testdruck)

    for name, func, hilfe in (("zpl", cmd_zpl, "ZPL ausgeben, ohne zu drucken"),
                              ("drucken", cmd_drucken, "Etiketten drucken")):
        p = sub.add_parser(name, help=hilfe)
        p.add_argument("kaffee", help="Kaffee-ID (siehe 'produkte')")
        p.add_argument("--version", help="Versions-ID, nötig wenn der Kaffee mehrere hat")
        p.add_argument("--mhd", type=_datum, help="MHD, z. B. 02.10.2027 (Standard: berechnet)")
        p.add_argument("--menge", type=int, default=1)
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    if not args.befehl:
        args = parser.parse_args(["start", *(argv or sys.argv[1:])])

    try:
        dienst = Druckdienst(config.laden(args.config))
        return args.func(dienst, args)
    except (config.KonfigFehler, ProduktFehler, EingabeFehler, drucker.DruckFehler, ValueError) as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
