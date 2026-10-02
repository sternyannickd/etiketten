"""Kleiner Webserver (nur Standardbibliothek): Oberfläche + JSON-API.

API (alle Antworten JSON, außer /api/vorschau = PNG):
  GET  /api/status                         Drucker- und Vorschaustatus
  GET  /api/produkte                       Produktliste
  GET  /api/mhd?produkt=ID[&abgepackt=YYYY-MM-DD]   berechnetes MHD
  POST /api/zpl       {produkt, mhd?, menge?}  → {zpl}
  POST /api/vorschau  {produkt, mhd?, menge?}  → image/png
  POST /api/drucken   {produkt, mhd?, menge?}  → {ok, meldung}
  POST /api/testdruck                      Kalibrier-/Testetikett
"""

from __future__ import annotations

import json
import mimetypes
import sys
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .dienst import Druckdienst, EingabeFehler, VorschauFehler
from .drucker import DruckFehler
from .produkte import ProduktFehler

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024


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


def handler_fuer(dienst: Druckdienst):
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

        def _auftrag(self) -> tuple[str, date | None, int]:
            daten = self._body()
            produkt = str(daten.get("produkt") or "")
            if not produkt:
                raise EingabeFehler("Kein Produkt gewählt")
            return produkt, _datum(daten.get("mhd"), "MHD"), _menge(daten.get("menge"))

        # --- Routen ------------------------------------------------------------

        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path == "/api/status":
                    return self._json({
                        "drucker": dienst.status().als_dict(),
                        "drucker_name": dienst.konfig["drucker"].get("name", ""),
                        "transport": dienst.konfig["drucker"].get("transport", ""),
                        "vorschau": dienst.vorschau_aktiv,
                    })
                if url.path == "/api/produkte":
                    return self._json([p.als_dict() for p in dienst.produkte()])
                if url.path == "/api/mhd":
                    q = parse_qs(url.query)
                    produkt = (q.get("produkt") or [""])[0]
                    abgepackt = _datum((q.get("abgepackt") or [""])[0], "Abpackdatum")
                    return self._json({"mhd": dienst.mhd_vorschlag(produkt, abgepackt).isoformat()})
                return self._statisch(url.path)
            except (EingabeFehler, ProduktFehler) as e:
                return self._fehler(400, str(e))

        def do_POST(self):
            pfad = urlparse(self.path).path
            try:
                if pfad == "/api/zpl":
                    produkt, mhd, menge = self._auftrag()
                    return self._json({"ok": True, "zpl": dienst.etikett(produkt, mhd, menge)})
                if pfad == "/api/vorschau":
                    produkt, mhd, menge = self._auftrag()
                    # Für die Vorschau immer nur ein Etikett rendern
                    png = dienst.vorschau(dienst.etikett(produkt, mhd, 1))
                    return self._senden(200, png, "image/png")
                if pfad == "/api/drucken":
                    produkt, mhd, menge = self._auftrag()
                    meldung = dienst.drucken(produkt, mhd, menge)
                    return self._json({"ok": True, "meldung": f"{menge} Etikett(en) gedruckt – {meldung}"})
                if pfad == "/api/testdruck":
                    return self._json({"ok": True, "meldung": f"Testetikett: {dienst.testdruck()}"})
                return self._fehler(404, "Nicht gefunden")
            except (EingabeFehler, ProduktFehler, ValueError) as e:
                return self._fehler(400, str(e))
            except VorschauFehler as e:
                return self._fehler(502, str(e))
            except DruckFehler as e:
                return self._fehler(503, str(e))

        def _statisch(self, pfad: str):
            name = "index.html" if pfad in ("", "/") else pfad.removeprefix("/static/")
            datei = (STATIC_DIR / name).resolve()
            if STATIC_DIR.resolve() not in datei.parents or not datei.is_file():
                return self._fehler(404, "Nicht gefunden")
            typ = mimetypes.guess_type(datei.name)[0] or "application/octet-stream"
            if typ.startswith("text/") or typ == "application/javascript":
                typ += "; charset=utf-8"
            return self._senden(HTTPStatus.OK, datei.read_bytes(), typ)

    return Handler


def starten(dienst: Druckdienst, host: str | None = None, port: int | None = None) -> None:
    host = host or dienst.konfig["server"]["host"]
    port = int(port or dienst.konfig["server"]["port"])
    try:
        httpd = ThreadingHTTPServer((host, port), handler_fuer(dienst))
    except OSError as e:
        raise SystemExit(
            f"Server konnte nicht auf {host}:{port} starten: {e.strerror}. "
            "Läuft das Programm schon? Sonst anderen Port mit --port wählen."
        ) from None
    anzeige = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    print(f"Etikettendruck läuft: http://{anzeige}:{port}   (beenden mit Strg+C)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        httpd.server_close()
