"""Druckwege: fertige ZPL-Bytes unverändert zum Drucker bringen.

Jeder Druckweg ("Transport") hat nur zwei Aufgaben:
  pruefen()  → ist der Drucker erreichbar? (für Statusanzeige und `check`)
  senden(b)  → Bytes übertragen

Neue Druckwege (z. B. ein entfernter Druckdienst auf einem Raspberry Pi)
werden hier ergänzt, ohne dass Layout oder Oberfläche sich ändern.
"""

from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import Konfig


class DruckFehler(Exception):
    pass


@dataclass
class Status:
    ok: bool
    meldung: str
    hinweis: str = ""

    def als_dict(self) -> dict:
        return {"ok": self.ok, "meldung": self.meldung, "hinweis": self.hinweis}


# --- USB direkt (/dev/usb/lp*) ------------------------------------------------

def usb_geraete() -> list[tuple[str, str]]:
    """Alle USB-Drucker als (Gerätedatei, IEEE-1284-Kennung)."""
    ergebnis = []
    for geraet in sorted(glob.glob("/dev/usb/lp*")):
        kennung = ""
        sys_pfad = Path("/sys/class/usbmisc") / Path(geraet).name / "device" / "ieee1284_id"
        try:
            kennung = sys_pfad.read_text(errors="replace").strip()
        except OSError:
            pass
        ergebnis.append((geraet, kennung))
    return ergebnis


class UsbTransport:
    """Schreibt direkt auf die Gerätedatei des Druckers – kein CUPS, kein Treiber."""

    def __init__(self, geraet: str = "auto", kennung: str = "CITIZEN"):
        self.geraet = geraet
        self.kennung = kennung

    def finden(self) -> str:
        if self.geraet and self.geraet != "auto":
            return self.geraet
        geraete = usb_geraete()
        for pfad, ieee in geraete:
            if self.kennung.lower() in ieee.lower():
                return pfad
        gefunden = ", ".join(f"{p} ({i or 'unbekannt'})" for p, i in geraete) or "keine"
        raise DruckFehler(
            f"Kein USB-Drucker mit Kennung {self.kennung!r} gefunden. "
            f"Gefundene Geräte: {gefunden}. Ist der Drucker eingeschaltet und per USB verbunden?"
        )

    def pruefen(self) -> Status:
        try:
            pfad = self.finden()
        except DruckFehler as e:
            return Status(False, str(e))
        if not os.path.exists(pfad):
            return Status(False, f"{pfad} existiert nicht.", "Drucker eingeschaltet und verbunden?")
        if not os.access(pfad, os.W_OK):
            return Status(
                False, f"Keine Schreibrechte auf {pfad}.",
                "Einmalig: sudo usermod -aG lp $USER – danach ab- und wieder anmelden.",
            )
        return Status(True, f"USB-Drucker bereit: {pfad}")

    def senden(self, daten: bytes) -> str:
        pfad = self.finden()
        try:
            # Ohne Puffer, damit ein Fehler sofort hier auftritt und nicht beim Schließen
            with open(pfad, "wb", buffering=0) as f:
                f.write(daten)
        except PermissionError as e:
            raise DruckFehler(
                f"Keine Schreibrechte auf {pfad}. Einmalig: sudo usermod -aG lp $USER, "
                "danach ab- und wieder anmelden."
            ) from e
        except OSError as e:
            raise DruckFehler(f"Schreiben auf {pfad} fehlgeschlagen: {e}") from e
        return f"an {pfad} gesendet"


# --- CUPS (Raw-Warteschlange) -------------------------------------------------

class CupsTransport:
    def __init__(self, warteschlange: str):
        self.warteschlange = warteschlange

    def pruefen(self) -> Status:
        if not shutil.which("lp"):
            return Status(False, "CUPS-Befehl 'lp' nicht gefunden.", "sudo apt install cups-client")
        try:
            aus = subprocess.run(["lpstat", "-p", self.warteschlange],
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as e:
            return Status(False, f"lpstat fehlgeschlagen: {e}")
        if aus.returncode != 0:
            return Status(False, f"CUPS-Warteschlange {self.warteschlange!r} nicht gefunden.",
                          "Einrichtung siehe docs/DRUCKER.md, Abschnitt CUPS.")
        return Status(True, f"CUPS-Warteschlange bereit: {self.warteschlange}")

    def senden(self, daten: bytes) -> str:
        try:
            aus = subprocess.run(["lp", "-d", self.warteschlange, "-o", "raw"],
                                 input=daten, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DruckFehler(f"lp fehlgeschlagen: {e}") from e
        if aus.returncode != 0:
            raise DruckFehler(f"lp: {aus.stderr.decode(errors='replace').strip()}")
        return aus.stdout.decode(errors="replace").strip() or "an CUPS übergeben"


# --- Netzwerk (Port 9100) -----------------------------------------------------

class TcpTransport:
    def __init__(self, host: str, port: int = 9100, timeout: float = 5):
        self.host, self.port, self.timeout = host, int(port), timeout

    def pruefen(self) -> Status:
        if not self.host:
            return Status(False, "Keine Drucker-Adresse (tcp_host) konfiguriert.")
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                pass
        except OSError as e:
            return Status(False, f"{self.host}:{self.port} nicht erreichbar: {e}")
        return Status(True, f"Netzwerkdrucker erreichbar: {self.host}:{self.port}")

    def senden(self, daten: bytes) -> str:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(daten)
        except OSError as e:
            raise DruckFehler(f"{self.host}:{self.port}: {e}") from e
        return f"an {self.host}:{self.port} gesendet"


# --- Trockenlauf --------------------------------------------------------------

class DateiTransport:
    """Druckt nicht, sondern legt jede Sendung als .zpl-Datei ab."""

    def __init__(self, ordner: Path):
        self.ordner = ordner

    def pruefen(self) -> Status:
        return Status(True, f"Trockenlauf: ZPL wird nach {self.ordner} geschrieben, nichts gedruckt.")

    def senden(self, daten: bytes) -> str:
        self.ordner.mkdir(parents=True, exist_ok=True)
        ziel = self.ordner / f"etikett_{datetime.now():%Y%m%d_%H%M%S_%f}.zpl"
        ziel.write_bytes(daten)
        return f"Trockenlauf – gespeichert als {ziel}"


def transport(konfig: Konfig):
    d = konfig["drucker"]
    art = d.get("transport", "usb")
    if art == "usb":
        return UsbTransport(d.get("usb_geraet", "auto"), d.get("usb_kennung", "CITIZEN"))
    if art == "cups":
        return CupsTransport(d["cups_warteschlange"])
    if art == "tcp":
        return TcpTransport(d.get("tcp_host", ""), d.get("tcp_port", 9100))
    if art == "datei":
        return DateiTransport(konfig.pfad("var/ausgabe"))
    raise DruckFehler(f"Unbekannter Druckweg {art!r} (erlaubt: usb, cups, tcp, datei)")
