"""Druckdienst: verbindet Produktliste, ZPL-Erzeugung, Druckweg, Vorschau und Protokoll.

Weboberfläche und Kommandozeile rufen nur diese Klasse auf. Ein späteres
Enterprise-System kann dasselbe tun (direkt in Python oder über die HTTP-API).
"""

from __future__ import annotations

import csv
import threading
import urllib.error
import urllib.request
from datetime import date, datetime

from . import drucker, mhd, produkte, zpl
from .config import Konfig


class EingabeFehler(Exception):
    pass


class VorschauFehler(Exception):
    pass


class Druckdienst:
    def __init__(self, konfig: Konfig):
        self.konfig = konfig
        self._sperre = threading.Lock()   # nie zwei Aufträge gleichzeitig an den Drucker
        self._produkt_sperre = threading.Lock()   # Produktliste nur nacheinander ändern

    # --- Produkte -------------------------------------------------------------

    def kaffees(self, alle: bool = False) -> list[produkte.Kaffee]:
        """Bei jedem Aufruf neu lesen: Änderungen an der Datei gelten ohne Neustart.
        Ohne `alle` nur aktive Kaffees, die mindestens eine aktive Version haben."""
        liste = produkte.laden(self.konfig.produkte_pfad)
        return liste if alle else [k for k in liste if not k.archiviert and k.aktive_versionen]

    def kaffee(self, kaffee_id: str) -> produkte.Kaffee:
        for k in self.kaffees(alle=True):
            if k.id == kaffee_id:
                return k
        raise EingabeFehler(f"Unbekannter Kaffee: {kaffee_id!r}")

    def mhd_vorschlag(self, kaffee_id: str, abpackdatum: date | None = None) -> date:
        return mhd.berechnen(abpackdatum or date.today(), self.kaffee(kaffee_id).mhd_monate)

    @property
    def bearbeiten_erlaubt(self) -> bool:
        return bool(self.konfig.daten.get("produkte_bearbeiten", True))

    def kaffee_speichern(self, daten: dict, kaffee_id: str | None = None) -> produkte.Kaffee:
        """Neuen Kaffee anlegen (ohne ID) oder einen bestehenden komplett ersetzen.
        Versionen werden nie entfernt, nur archiviert."""
        if not self.bearbeiten_erlaubt:
            raise EingabeFehler("Produkte bearbeiten ist hier ausgeschaltet (produkte_bearbeiten in config.toml)")
        if not isinstance(daten, dict):
            raise EingabeFehler("Ungültige Angaben")
        kaffee = produkte.kaffee_aus_dict({**daten, "id": kaffee_id or ""})
        with self._produkt_sperre:
            liste = self.kaffees(alle=True)
            if kaffee_id is None:
                kaffee = produkte.ids_vergeben(kaffee, {k.id for k in liste})
                liste.append(kaffee)
            else:
                nr = next((i for i, k in enumerate(liste) if k.id == kaffee_id), None)
                if nr is None:
                    raise EingabeFehler(f"Unbekannter Kaffee: {kaffee_id!r}")
                alte = {v.id for v in liste[nr].versionen}
                neue = {v.id for v in kaffee.versionen if v.id}
                if (unbekannt := neue - alte):
                    raise EingabeFehler(f"Unbekannte Version: {', '.join(sorted(unbekannt))}")
                if alte - neue:
                    raise EingabeFehler("Versionen können nicht gelöscht werden, nur archiviert")
                kaffee = produkte.ids_vergeben(kaffee, set())
                liste[nr] = kaffee
            produkte.speichern(self.konfig.produkte_pfad, liste)
        return kaffee

    # --- Etikett --------------------------------------------------------------

    def _auswahl(self, kaffee_id: str, version_id: str | None):
        k = self.kaffee(kaffee_id)
        return k, k.version(version_id)

    def etikett(self, kaffee_id: str, version_id: str | None = None,
                mhd_datum: date | None = None, menge: int = 1) -> str:
        k, v = self._auswahl(kaffee_id, version_id)
        if not isinstance(menge, int) or not 1 <= menge <= 999:
            raise EingabeFehler("Menge muss zwischen 1 und 999 liegen")
        if mhd_datum is None:
            mhd_datum = self.mhd_vorschlag(kaffee_id)
        if mhd_datum < date.today():
            raise EingabeFehler(f"MHD {mhd_datum:%d.%m.%Y} liegt in der Vergangenheit")
        return zpl.erzeugen(self.konfig, zpl.EtikettDaten(k.name, v.gtin, mhd_datum, menge))

    def drucken(self, kaffee_id: str, version_id: str | None = None,
                mhd_datum: date | None = None, menge: int = 1) -> str:
        k, v = self._auswahl(kaffee_id, version_id)
        mhd_datum = mhd_datum or self.mhd_vorschlag(kaffee_id)
        text = self.etikett(kaffee_id, v.id, mhd_datum, menge)
        try:
            with self._sperre:
                meldung = drucker.transport(self.konfig).senden(zpl.kodieren(self.konfig, text))
        except drucker.DruckFehler as e:
            self._protokollieren(k, v, mhd_datum, menge, f"FEHLER: {e}")
            raise
        self._protokollieren(k, v, mhd_datum, menge, "ok")
        return meldung

    def testdruck(self) -> str:
        with self._sperre:
            text = zpl.testetikett(self.konfig)
            return drucker.transport(self.konfig).senden(zpl.kodieren(self.konfig, text))

    def status(self) -> drucker.Status:
        try:
            return drucker.transport(self.konfig).pruefen()
        except drucker.DruckFehler as e:
            return drucker.Status(False, str(e))

    # --- Vorschau (optional, Online-Dienst labelary.com) -------------------------

    @property
    def vorschau_aktiv(self) -> bool:
        return bool(self.konfig["vorschau"].get("aktiv"))

    def vorschau(self, zpl_text: str) -> bytes:
        """PNG der Vorschau. Wirft VorschauFehler – der Druck ist davon nie betroffen."""
        v = self.konfig["vorschau"]
        if not v.get("aktiv"):
            raise VorschauFehler("Vorschau ist ausgeschaltet")
        e = self.konfig["etikett"]
        url = v["url"].format(
            dpmm=round(int(self.konfig["drucker"]["dpi"]) / 25.4),
            breite_zoll=round(float(e["breite"]) / 25.4, 3),
            hoehe_zoll=round(float(e["hoehe"]) / 25.4, 3),
        )
        anfrage = urllib.request.Request(
            url, data=zpl.kodieren(self.konfig, zpl_text),
            headers={"Accept": "image/png", "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=float(v.get("timeout_s", 5))) as antwort:
                return antwort.read()
        except (urllib.error.URLError, TimeoutError, OSError) as fehler:
            raise VorschauFehler(f"Vorschau nicht verfügbar: {fehler}") from fehler

    # --- Protokoll -------------------------------------------------------------

    PROTOKOLL_SPALTEN = ["zeitpunkt", "kaffee_id", "version_id", "name", "version",
                         "gtin", "mhd", "menge", "ergebnis"]

    def _protokollieren(self, k: produkte.Kaffee, v: produkte.Version, mhd_datum: date,
                        menge: int, ergebnis: str) -> None:
        pfad = self.konfig.protokoll_pfad
        if not pfad:
            return
        try:
            pfad.parent.mkdir(parents=True, exist_ok=True)
            if pfad.exists():
                with pfad.open(encoding="utf-8", newline="") as f:
                    kopf = next(csv.reader(f), [])
                if kopf != self.PROTOKOLL_SPALTEN:
                    # Protokoll aus Version 0.2 (ohne Versionen) beiseitelegen statt mischen
                    pfad.rename(pfad.with_name(f"{pfad.stem}-bis-0.2{pfad.suffix}"))
            neu = not pfad.exists()
            with pfad.open("a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if neu:
                    w.writerow(self.PROTOKOLL_SPALTEN)
                w.writerow([datetime.now().isoformat(timespec="seconds"), k.id, v.id, k.anzeigename,
                            v.bezeichnung, v.gtin, mhd_datum.isoformat(), menge, ergebnis])
        except OSError:
            pass  # Das Protokoll ist nützlich, darf aber nie den Druck verhindern.
