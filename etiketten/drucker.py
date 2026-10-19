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
import sys
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


def spricht_zpl(kennung: str) -> bool | None:
    """Ob die gemeldete aktive Druckersprache ZPL ist; None, wenn die Kennung nichts dazu sagt.

    Citizen meldet die Zebra-Emulation als "Z2" (ZPL II), Datamax als "DMI"/"DM4".
    """
    for feld in kennung.upper().split(";"):
        name, _, wert = feld.partition(":")
        if name.strip() == "ACTIVE COMMAND":
            wert = wert.strip()
            return "ZPL" in wert or wert.startswith("Z")
    return None


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


# --- Windows (Druckwarteschlange, Datentyp RAW) ---------------------------------

ERROR_INVALID_DATATYPE = 1804
WINDOWS_HINWEIS = ("Der Drucker muss unter Windows eingerichtet sein (Einstellungen → Bluetooth und "
                   "Geräte → Drucker und Scanner). Name und Einrichtung: docs/INSTALLATION.md.")


class _WinSpool:
    """Dünne Hülle um winspool.drv (Windows-Druck-API), nur Standardbibliothek (ctypes)."""

    def __init__(self):
        if sys.platform != "win32":
            raise DruckFehler("Der Druckweg 'windows' funktioniert nur unter Windows.")
        import ctypes
        from ctypes import wintypes

        self.ctypes, self.wt = ctypes, wintypes
        w = self.dll = ctypes.WinDLL("winspool.drv", use_last_error=True)

        class PRINTER_INFO_4W(ctypes.Structure):
            _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR),
                        ("Attributes", wintypes.DWORD)]

        class DOC_INFO_1W(ctypes.Structure):
            _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR),
                        ("pDatatype", wintypes.LPWSTR)]

        self.PRINTER_INFO_4W, self.DOC_INFO_1W = PRINTER_INFO_4W, DOC_INFO_1W
        h, dw, b = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL
        for name, rueck, argumente in (
            ("EnumPrintersW", b, [dw, wintypes.LPWSTR, dw, ctypes.c_void_p, dw,
                                  ctypes.POINTER(dw), ctypes.POINTER(dw)]),
            ("OpenPrinterW", b, [wintypes.LPWSTR, ctypes.POINTER(h), ctypes.c_void_p]),
            ("StartDocPrinterW", dw, [h, dw, ctypes.POINTER(DOC_INFO_1W)]),
            ("StartPagePrinter", b, [h]),
            ("WritePrinter", b, [h, ctypes.c_void_p, dw, ctypes.POINTER(dw)]),
            ("EndPagePrinter", b, [h]),
            ("EndDocPrinter", b, [h]),
            ("ClosePrinter", b, [h]),
        ):
            funktion = getattr(w, name)
            funktion.restype, funktion.argtypes = rueck, argumente

    def _fehler(self, was: str) -> DruckFehler:
        code = self.ctypes.get_last_error()
        text = self.ctypes.FormatError(code).strip()
        if code == ERROR_INVALID_DATATYPE:
            text += (" – der Druckertreiber nimmt keine Rohdaten an. Den Drucker stattdessen mit "
                     "dem Treiber „Generic / Text Only“ einrichten (docs/INSTALLATION.md).")
        return DruckFehler(f"{was}: {text} (Fehler {code})")

    def drucker_namen(self) -> list[str]:
        ct, wt = self.ctypes, self.wt
        flags = 2 | 4  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
        benoetigt, anzahl = wt.DWORD(), wt.DWORD()
        self.dll.EnumPrintersW(flags, None, 4, None, 0, ct.byref(benoetigt), ct.byref(anzahl))
        if not benoetigt.value:
            return []
        puffer = ct.create_string_buffer(benoetigt.value)
        if not self.dll.EnumPrintersW(flags, None, 4, puffer, benoetigt, ct.byref(benoetigt),
                                      ct.byref(anzahl)):
            raise self._fehler("Drucker auflisten")
        eintraege = ct.cast(puffer, ct.POINTER(self.PRINTER_INFO_4W))
        return [eintraege[i].pPrinterName for i in range(anzahl.value)]

    def roh_drucken(self, name: str, daten: bytes) -> None:
        ct, wt = self.ctypes, self.wt
        h = wt.HANDLE()
        if not self.dll.OpenPrinterW(name, ct.byref(h), None):
            raise self._fehler(f"Drucker {name!r} öffnen")
        try:
            dokument = self.DOC_INFO_1W("Etikett", None, "RAW")
            if not self.dll.StartDocPrinterW(h, 1, ct.byref(dokument)):
                raise self._fehler("Druckauftrag starten")
            try:
                if not self.dll.StartPagePrinter(h):
                    raise self._fehler("Seite starten")
                geschrieben = wt.DWORD()
                ok = self.dll.WritePrinter(h, daten, len(daten), ct.byref(geschrieben))
                self.dll.EndPagePrinter(h)
                if not ok or geschrieben.value != len(daten):
                    raise self._fehler("Daten senden")
            finally:
                self.dll.EndDocPrinter(h)
        finally:
            self.dll.ClosePrinter(h)


class WindowsTransport:
    """Schickt die ZPL über die Windows-Druckwarteschlange als Datentyp RAW.

    Windows reicht die Bytes dabei unverändert an den Drucker durch, der Treiber
    rastert nichts (wie die CUPS-Raw-Warteschlange unter Linux).
    """

    def __init__(self, drucker: str = "auto", kennung: str = "CITIZEN", api=None):
        self.drucker, self.kennung = drucker, kennung
        self._api = api   # in Tests durch eine Attrappe ersetzbar

    @property
    def api(self):
        if self._api is None:
            self._api = _WinSpool()
        return self._api

    def finden(self) -> str:
        namen = self.api.drucker_namen()
        vorhanden = ", ".join(namen) or "keine"
        if self.drucker and self.drucker != "auto":
            if self.drucker in namen:
                return self.drucker
            raise DruckFehler(f"Windows-Drucker {self.drucker!r} nicht gefunden. Vorhanden: {vorhanden}.")
        for name in namen:
            if self.kennung.lower() in name.lower():
                return name
        raise DruckFehler(f"Kein Windows-Drucker mit {self.kennung!r} im Namen gefunden. "
                          f"Vorhanden: {vorhanden}.")

    def pruefen(self) -> Status:
        try:
            return Status(True, f"Windows-Drucker bereit: {self.finden()}")
        except DruckFehler as e:
            return Status(False, str(e), WINDOWS_HINWEIS)

    def senden(self, daten: bytes) -> str:
        name = self.finden()
        self.api.roh_drucken(name, daten)
        return f"an {name} gesendet"


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
    art = d.get("transport", "auto")
    if art == "auto":
        art = "windows" if sys.platform == "win32" else "usb"
    if art == "windows":
        return WindowsTransport(d.get("windows_drucker", "auto"), d.get("windows_kennung", "CITIZEN"))
    if art == "usb":
        return UsbTransport(d.get("usb_geraet", "auto"), d.get("usb_kennung", "CITIZEN"))
    if art == "cups":
        return CupsTransport(d["cups_warteschlange"])
    if art == "tcp":
        return TcpTransport(d.get("tcp_host", ""), d.get("tcp_port", 9100))
    if art == "datei":
        return DateiTransport(konfig.pfad("var/ausgabe"))
    raise DruckFehler(f"Unbekannter Druckweg {art!r} (erlaubt: auto, windows, usb, cups, tcp, datei)")
