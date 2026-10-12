"""Kleiner Webserver (nur Standardbibliothek): Oberfläche + JSON-API.

API (alle Antworten JSON, außer /api/vorschau = PNG), ausführlich in docs/API.md:
  GET  /api/status                         Drucker- und Vorschaustatus
  GET  /api/produkte[?alle=1]              Kaffees mit Versionen (alle = inkl. archivierte)
  GET  /api/mhd?kaffee=ID[&abgepackt=YYYY-MM-DD]    berechnetes MHD
  POST /api/zpl       {kaffee, version?, mhd?, menge?}  → {zpl}
  POST /api/vorschau  {kaffee, version?, mhd?}          → image/png
  POST /api/drucken   {kaffee, version?, mhd?, menge?}  → {ok, meldung}
  POST /api/testdruck                      Kalibrier-/Testetikett
  POST /api/kaffees          {name, mhd_monate, versionen}  neuer Kaffee → {ok, kaffee}
  PUT  /api/kaffees/<id>     {name, mhd_monate, archiviert, versionen, info}  ändern → {ok, kaffee}

Verpackungsetikett (zweite Etikettenart, Oberfläche /verpackung):
  GET  /api/verpackung/status
  POST /api/verpackung/zpl       {kaffee, charge, mhd?, menge?}  → {zpl}
  POST /api/verpackung/vorschau  {kaffee, charge, mhd?}          → image/png
  POST /api/verpackung/drucken   {kaffee, charge, mhd?, menge?}  → {ok, meldung}
  POST /api/verpackung/testdruck
"""

from __future__ import annotations

import json
import mimetypes
import sys
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .dienst import Druckdienst, EingabeFehler, VorschauFehler
from .drucker import DruckFehler
from .produkte import ProduktFehler

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024
# Fest statt mimetypes: Unter Windows kann die Registry .js falsch zuordnen,
# und ES-Module lädt der Browser nur mit JavaScript-Typ.
# Seiten der Oberfläche: Produktetikett und Verpackungsetikett
SEITEN = {"/": "index.html", "/verpackung": "verpackung.html"}
TYPEN = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def _datum(wert, feld: str) -> date | None:
    if wert in (None, ""):
        return None
    try:
        return date.fromisoformat(str(wert))
    except ValueError:
        raise EingabeFehler(f"{feld}: ungültiges Datum {wert!r} (erwartet JJJJ-MM-TT)") from None


def _menge(wert) -> int:
    try:
        menge = int(wert if wert not in (None, "") else 1)
    except (TypeError, ValueError):
        raise EingabeFehler(f"Menge ungültig: {wert!r}") from None
    return menge


def _status(dienst: Druckdienst, konfig, drucker_status) -> dict:
    """Status im Format der Portal-Konvention ({ok, meldung}) plus Einzelheiten."""
    return {
        "ok": drucker_status.ok,
        "meldung": drucker_status.meldung,
        "drucker": drucker_status.als_dict(),
        "drucker_name": konfig["drucker"].get("name", ""),
        "transport": konfig["drucker"].get("transport", ""),
        "vorschau": dienst.vorschau_aktiv,
        "produkte_bearbeiten": dienst.bearbeiten_erlaubt,
        "verpackung": dienst.verpackung_aktiv,
    }


def einschuebe(rahmen: Path | None, entwickler: bool) -> dict[bytes, bytes]:
    """Was in den lokalen Seiten an Stelle der Platzhalter kommt: das Design von tosto
    (theme.css aus dem Rahmen-Ordner), im Entwicklermodus zusätzlich ein Hinweisband."""
    design = rahmen is not None and (rahmen / "theme.css").is_file()
    kopf = '<link rel="stylesheet" href="/rahmen/theme.css">' if design else ""
    band = ""
    if entwickler:
        quelle = "tosto-Design" if design else "eigenes Design (tosto-Rahmen nicht gefunden)"
        band = f'<div class="entwicklermodus">Entwicklermodus: Testdaten, druckt in Dateien (var/dev/) · {quelle}</div>'
    return {b"<!--rahmen-->": kopf.encode(), b"<!--entwicklermodus-->": band.encode()}


def handler_fuer(dienst: Druckdienst, rahmen: Path | None = None, entwickler: bool = False):
    """`rahmen`: Ordner mit dem tosto-Rahmen (theme.css), `entwickler`: Hinweisband zeigen."""
    ersetzen = einschuebe(rahmen, entwickler)

    class Handler(BaseHTTPRequestHandler):
        server_version = "Etiketten/1"

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

        # --- Antworten ---------------------------------------------------------

        def _senden(self, status: int, inhalt: bytes, typ: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(inhalt)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(inhalt)

        def _json(self, daten, status: int = 200) -> None:
            self._senden(status, json.dumps(daten, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _fehler(self, status: int, meldung: str) -> None:
            self._json({"ok": False, "fehler": meldung}, status)

        def _body(self) -> dict:
            laenge = int(self.headers.get("Content-Length") or 0)
            if laenge > MAX_BODY:
                raise EingabeFehler("Anfrage zu groß")
            roh = self.rfile.read(laenge) if laenge else b""
            if not roh:
                return {}
            try:
                daten = json.loads(roh)
            except json.JSONDecodeError:
                raise EingabeFehler("Anfrage ist kein gültiges JSON") from None
            if not isinstance(daten, dict):
                raise EingabeFehler("Anfrage muss ein JSON-Objekt sein")
            return daten

        def _auftrag(self) -> tuple[str, str | None, date | None, int]:
            daten = self._body()
            kaffee = str(daten.get("kaffee") or "")
            if not kaffee:
                raise EingabeFehler("Kein Kaffee gewählt")
            version = str(daten.get("version") or "") or None
            return kaffee, version, _datum(daten.get("mhd"), "MHD"), _menge(daten.get("menge"))

        def _verpackung_auftrag(self) -> tuple[str, str, date | None, int]:
            daten = self._body()
            kaffee = str(daten.get("kaffee") or "")
            if not kaffee:
                raise EingabeFehler("Kein Kaffee gewählt")
            charge = str(daten.get("charge") or "")
            if not charge:
                raise EingabeFehler("Keine Charge angegeben")
            return kaffee, charge, _datum(daten.get("mhd"), "MHD"), _menge(daten.get("menge"))

        # --- Routen ------------------------------------------------------------

        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path == "/api/status":
                    return self._json(_status(dienst, dienst.konfig, dienst.status()))
                if url.path == "/api/verpackung/status":
                    return self._json(_status(dienst, dienst.verpackung_konfig, dienst.verpackung_status()))
                q = parse_qs(url.query)
                if url.path == "/api/produkte":
                    alle = (q.get("alle") or [""])[0] in ("1", "true")
                    return self._json([k.als_dict(mit_archiv=alle) for k in dienst.kaffees(alle)])
                if url.path == "/api/mhd":
                    kaffee = (q.get("kaffee") or [""])[0]
                    abgepackt = _datum((q.get("abgepackt") or [""])[0], "Abpackdatum")
                    return self._json({"mhd": dienst.mhd_vorschlag(kaffee, abgepackt).isoformat()})
                return self._statisch(url.path)
            except (EingabeFehler, ProduktFehler) as e:
                return self._fehler(400, str(e))

        def do_POST(self):
            pfad = urlparse(self.path).path
            try:
                if pfad == "/api/zpl":
                    kaffee, version, mhd, menge = self._auftrag()
                    return self._json({"ok": True, "zpl": dienst.etikett(kaffee, version, mhd, menge)})
                if pfad == "/api/vorschau":
                    kaffee, version, mhd, _ = self._auftrag()
                    # Für die Vorschau immer nur ein Etikett rendern
                    png = dienst.vorschau(dienst.etikett(kaffee, version, mhd, 1))
                    return self._senden(200, png, "image/png")
                if pfad == "/api/drucken":
                    kaffee, version, mhd, menge = self._auftrag()
                    meldung = dienst.drucken(kaffee, version, mhd, menge)
                    return self._json({"ok": True, "meldung": f"{menge} Etikett(en) gedruckt – {meldung}"})
                if pfad == "/api/testdruck":
                    return self._json({"ok": True, "meldung": f"Testetikett: {dienst.testdruck()}"})
                if pfad == "/api/kaffees":
                    kaffee = dienst.kaffee_speichern(self._body())
                    return self._json({"ok": True, "kaffee": kaffee.als_dict()})
                if pfad == "/api/verpackung/zpl":
                    kaffee, charge, mhd, menge = self._verpackung_auftrag()
                    return self._json({"ok": True, "zpl": dienst.verpackung_etikett(kaffee, charge, mhd, menge)})
                if pfad == "/api/verpackung/vorschau":
                    kaffee, charge, mhd, _ = self._verpackung_auftrag()
                    text = dienst.verpackung_etikett(kaffee, charge, mhd, 1)
                    return self._senden(200, dienst.vorschau(text, dienst.verpackung_konfig), "image/png")
                if pfad == "/api/verpackung/drucken":
                    kaffee, charge, mhd, menge = self._verpackung_auftrag()
                    meldung = dienst.verpackung_drucken(kaffee, charge, mhd, menge)
                    return self._json({"ok": True,
                                       "meldung": f"{menge} Verpackungsetikett(en) gedruckt – {meldung}"})
                if pfad == "/api/verpackung/testdruck":
                    return self._json({"ok": True, "meldung": f"Testetikett: {dienst.verpackung_testdruck()}"})
                return self._fehler(404, "Nicht gefunden")
            except (EingabeFehler, ProduktFehler, ValueError) as e:
                return self._fehler(400, str(e))
            except VorschauFehler as e:
                return self._fehler(502, str(e))
            except DruckFehler as e:
                return self._fehler(503, str(e))

        def do_PUT(self):
            pfad = urlparse(self.path).path
            try:
                if pfad.startswith("/api/kaffees/"):
                    kaffee_id = unquote(pfad.removeprefix("/api/kaffees/"))
                    kaffee = dienst.kaffee_speichern(self._body(), kaffee_id)
                    return self._json({"ok": True, "kaffee": kaffee.als_dict()})
                return self._fehler(404, "Nicht gefunden")
            except (EingabeFehler, ProduktFehler) as e:
                return self._fehler(400, str(e))

        def _statisch(self, pfad: str):
            ordner = STATIC_DIR
            if pfad.startswith("/rahmen/") and rahmen:
                ordner, name = rahmen, pfad.removeprefix("/rahmen/")
            else:
                name = SEITEN.get(pfad.rstrip("/") or "/", pfad.removeprefix("/static/"))
            datei = (ordner / unquote(name)).resolve()
            if ordner.resolve() not in datei.parents or not datei.is_file():
                return self._fehler(404, "Nicht gefunden")
            typ = TYPEN.get(datei.suffix) or mimetypes.guess_type(datei.name)[0] or "application/octet-stream"
            inhalt = datei.read_bytes()
            if datei.suffix == ".html":
                for platzhalter, ersatz in ersetzen.items():
                    inhalt = inhalt.replace(platzhalter, ersatz)
            return self._senden(HTTPStatus.OK, inhalt, typ)

    return Handler


def starten(dienst: Druckdienst, host: str | None = None, port: int | None = None,
            rahmen: Path | None = None, entwickler: bool = False) -> None:
    host = host or dienst.konfig["server"]["host"]
    port = int(port or dienst.konfig["server"]["port"])
    try:
        httpd = ThreadingHTTPServer((host, port), handler_fuer(dienst, rahmen, entwickler))
    except OSError as e:
        raise SystemExit(
            f"Server konnte nicht auf {host}:{port} starten: {e.strerror}. "
            "Läuft das Programm schon? Sonst anderen Port mit --port wählen."
        ) from None
    anzeige = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"Etiketta läuft: http://{anzeige}:{port}   (beenden mit Strg+C)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        httpd.server_close()
