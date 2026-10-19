"""Einstieg für das installierte Programm: Doppelklick → Server starten → Browser öffnen.

Ohne Argumente startet die Oberfläche. Läuft das Programm schon, wird nur der
Browser geöffnet. Mit Argumenten verhält es sich wie die Kommandozeile
(z. B. ``etikettendruck check``).

Das Programm läuft ohne Konsolenfenster. Ausgaben landen deshalb in
``var/etikettendruck.log`` im Datenordner, Fehler beim Start zusätzlich in einem
Hinweisfenster.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser

from . import cli, config, server
from .dienst import Druckdienst

LOG_MAX = 1_000_000   # Bytes; größere Logdatei wird beim Start neu begonnen
WEITERE_PORTS = 10    # ist der Port belegt, die nächsten probieren


def hinweis_fenster(text: str) -> None:
    """Meldung so zeigen, dass man sie auch ohne Konsole sieht."""
    print(text, file=sys.stderr, flush=True)
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "Etikettendruck", 0x10)
        else:
            for befehl in (["zenity", "--error", "--title=Etikettendruck", f"--text={text}"],
                           ["notify-send", "Etikettendruck", text]):
                try:
                    subprocess.run(befehl, timeout=600, check=False)
                    return
                except (OSError, subprocess.SubprocessError):
                    continue
    except Exception:  # Die Meldung darf nie selbst zum Absturz führen
        pass


def _log_umleiten(konfig: config.Konfig) -> None:
    """Ohne Konsole sind stdout/stderr leer (Windows) oder unsichtbar: in eine Datei schreiben."""
    if sys.stdout is not None and sys.stdout.isatty():
        return
    pfad = konfig.basis_dir / "var" / "etikettendruck.log"
    try:
        if pfad.exists() and pfad.stat().st_size > LOG_MAX:
            pfad.replace(pfad.with_suffix(".log.alt"))
        datei = pfad.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = datei


def starten() -> int:
    try:
        konfig = config.laden()
    except config.KonfigFehler as e:
        hinweis_fenster(f"Einstellungen fehlerhaft:\n{e}")
        return 1
    _log_umleiten(konfig)
    for warnung in konfig.warnungen:
        print(f"Warnung: {warnung}", flush=True)

    host = konfig["server"]["host"]
    port = int(konfig["server"]["port"])
    if server.laeuft_schon(port):
        webbrowser.open(f"http://localhost:{port}")
        return 0

    dienst = Druckdienst(konfig)
    httpd = None
    for versuch in range(port, port + WEITERE_PORTS + 1):
        try:
            httpd = server.erstellen(dienst, host, versuch)
            port = versuch
            break
        except OSError:
            continue
    if httpd is None:
        hinweis_fenster(f"Der Etikettendruck konnte nicht starten: Die Ports {port}–"
                        f"{port + WEITERE_PORTS} sind alle belegt.")
        return 1

    url = f"http://localhost:{port}"
    print(f"Etikettendruck {url} – Daten in {konfig.basis_dir}", flush=True)
    threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    print("Beendet.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return cli.main(argv)
    try:
        return starten()
    except Exception as e:  # letzte Rettung: lieber eine Meldung als stilles Nichts
        hinweis_fenster(f"Unerwarteter Fehler: {e!r}")
        raise


if __name__ == "__main__":
    sys.exit(main())
