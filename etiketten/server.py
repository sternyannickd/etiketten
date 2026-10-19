"""Kleiner Webserver (nur Standardbibliothek): Oberfläche + JSON-API.

API (alle Antworten JSON, außer /api/vorschau = PNG):
  GET  /api/status                         Drucker- und Vorschaustatus
  GET  /api/produkte                       Produktliste
  GET  /api/mhd?produkt=ID[&abgepackt=YYYY-MM-DD]   berechnetes MHD
  POST /api/zpl       {produkt, mhd?, menge?}  → {zpl}
  POST /api/vorschau  {produkt, mhd?, menge?}  → image/png
  POST /api/drucken   {produkt, mhd?, menge?}  → {ok, meldung}
  POST /api/testdruck                      Kalibrier-/Testetikett
  POST /api/produkt/speichern {alte_id?, name, gtin, mhd_monate}  anlegen/ändern → {produkt}
  POST /api/produkt/loeschen  {id}
  POST /api/ordner                         Datenordner im Dateimanager öffnen
  POST /api/beenden                        Programm beenden

Schutz gegen fremde Webseiten im selben Browser: POST nur mit
Content-Type application/json und ohne fremden Origin, und nur unter einem
bekannten Hostnamen (gegen DNS-Rebinding). Siehe _anfrage_erlaubt().
"""

from __future__ import annotations

import ipaddress
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import urllib.request
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__

from .dienst import Druckdienst, EingabeFehler, VorschauFehler
from .drucker import DruckFehler
from .produkte import ProduktFehler

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024
# Fest statt aus mimetypes: Unter Windows kommen die Typen sonst aus der
# Registry, und dort steht für .js mitunter "text/plain".
DATEITYPEN = {".html": "text/html", ".js": "application/javascript", ".css": "text/css",
              ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


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


def _hostname(host_kopf: str) -> str:
    """Hostname ohne Port aus dem Host-Header, z. B. "[::1]:8077" → "::1"."""
    host = host_kopf.strip().lower()
    if host.startswith("["):
        return host[1:].partition("]")[0]
    return host.rpartition(":")[0] if host.count(":") == 1 else host


def _host_erlaubt(host_kopf: str, erlaubte_namen) -> bool:
    """IP-Adressen, localhost, der eigene Rechnername und erlaubte_namen aus der Konfiguration.

    Andere Namen werden abgelehnt: Sonst könnte eine fremde Domain per
    DNS-Rebinding auf 127.0.0.1 zeigen und als "gleiche Herkunft" gelten.
    """
    name = _hostname(host_kopf)
    if not name:
        return False
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    return name in {"localhost", *rechnernamen(), *(n.lower() for n in erlaubte_namen)}


def rechnernamen() -> set[str]:
    """Namen dieses Rechners, voll und kurz, jeweils auch mit .local (Avahi/Bonjour).

    Beispiel "mint-test.server.lan" → mint-test.server.lan, mint-test, mint-test.local …
    """
    voll = socket.gethostname().lower()
    kurz = voll.split(".")[0]
    return {voll, kurz, f"{voll}.local", f"{kurz}.local"}


def handler_fuer(dienst: Druckdienst):
    erlaubte_namen = dienst.konfig["server"].get("erlaubte_namen", [])


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

        def _anfrage_erlaubt(self, post: bool) -> bool:
            """Lehnt Anfragen ab, die eine fremde Webseite im Browser auslösen könnte.

            Sendet die Antwort bei Ablehnung selbst.
            """
            host = self.headers.get("Host", "")
            if not _host_erlaubt(host, erlaubte_namen):
                self._fehler(403, f"Unbekannter Hostname {host!r} (siehe erlaubte_namen in config.toml)")
                return False
            if not post:
                return True
            origin = self.headers.get("Origin")
            if origin is not None and urlparse(origin).netloc.lower() != host.lower():
                self._fehler(403, "Anfrage von fremder Seite abgelehnt")
                return False
            typ = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if typ != "application/json":
                # Fremde Seiten können ohne Rückfrage des Browsers nur Formulare
                # bzw. text/plain senden – application/json nicht.
                self._fehler(415, "Content-Type muss application/json sein")
                return False
            return True

        def _auftrag(self) -> tuple[str, date | None, int]:
            daten = self._body()
            produkt = str(daten.get("produkt") or "")
            if not produkt:
                raise EingabeFehler("Kein Produkt gewählt")
            return produkt, _datum(daten.get("mhd"), "MHD"), _menge(daten.get("menge"))

        # --- Routen ------------------------------------------------------------

        def do_GET(self):
            if not self._anfrage_erlaubt(post=False):
                return
            url = urlparse(self.path)
            try:
                if url.path == "/api/status":
                    return self._json({
                        "drucker": dienst.status().als_dict(),
                        "drucker_name": dienst.konfig["drucker"].get("name", ""),
                        "transport": dienst.konfig["drucker"].get("transport", ""),
                        "vorschau": dienst.vorschau_aktiv,
                        "version": __version__,
                        "daten_ordner": str(dienst.konfig.basis_dir),
                        "warnungen": dienst.konfig.warnungen,
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
            if not self._anfrage_erlaubt(post=True):
                return
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
                if pfad == "/api/produkt/speichern":
                    daten = self._body()
                    p = dienst.produkt_speichern(daten, str(daten.get("alte_id") or "") or None)
                    return self._json({"ok": True, "produkt": p.als_dict()})
                if pfad == "/api/produkt/loeschen":
                    dienst.produkt_loeschen(str(self._body().get("id") or ""))
                    return self._json({"ok": True})
                if pfad == "/api/ordner":
                    ordner_oeffnen(dienst.konfig.basis_dir)
                    return self._json({"ok": True})
                if pfad == "/api/beenden":
                    self._json({"ok": True, "meldung": "Programm beendet."})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return None
                return self._fehler(404, "Nicht gefunden")
            except (EingabeFehler, ProduktFehler, ValueError) as e:
                return self._fehler(400, str(e))
            except VorschauFehler as e:
                return self._fehler(502, str(e))
            except DruckFehler as e:
                return self._fehler(503, str(e))
            except OSError as e:
                return self._fehler(500, f"Datei konnte nicht geschrieben werden: {e}. "
                                         "Ist sie gerade in einem anderen Programm (z. B. Excel) geöffnet?")

        def _statisch(self, pfad: str):
            name = "index.html" if pfad in ("", "/") else pfad.removeprefix("/static/")
            datei = (STATIC_DIR / name).resolve()
            if STATIC_DIR.resolve() not in datei.parents or not datei.is_file():
                return self._fehler(404, "Nicht gefunden")
            typ = (DATEITYPEN.get(datei.suffix.lower()) or mimetypes.guess_type(datei.name)[0]
                   or "application/octet-stream")
            if typ.startswith("text/") or typ == "application/javascript":
                typ += "; charset=utf-8"
            return self._senden(HTTPStatus.OK, datei.read_bytes(), typ)

    return Handler


def ordner_oeffnen(ordner: Path) -> None:
    """Ordner im Dateimanager dieses Rechners öffnen."""
    if sys.platform == "win32":
        os.startfile(ordner)  # noqa: S606 – nur der eigene Datenordner
    else:
        subprocess.Popen(["xdg-open", str(ordner)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def laeuft_schon(port: int) -> bool:
    """Ob auf diesem Port bereits der Etikettendruck antwortet (zweiter Doppelklick)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=3) as r:
            return r.headers.get("Server", "").startswith("Etiketten/")
    except (OSError, ValueError):
        return False


def erstellen(dienst: Druckdienst, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    host = host or dienst.konfig["server"]["host"]
    port = int(port or dienst.konfig["server"]["port"])
    return ThreadingHTTPServer((host, port), handler_fuer(dienst))


def starten(dienst: Druckdienst, host: str | None = None, port: int | None = None) -> None:
    host = host or dienst.konfig["server"]["host"]
    port = int(port or dienst.konfig["server"]["port"])
    try:
        httpd = erstellen(dienst, host, port)
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
