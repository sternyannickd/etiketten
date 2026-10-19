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
        self._schreibsperre = threading.Lock()   # nie zwei Änderungen gleichzeitig an der Produktliste

    # --- Produkte -------------------------------------------------------------

    def produkte(self) -> list[produkte.Produkt]:
        # Bei jedem Aufruf neu lesen: Änderungen an der CSV gelten ohne Neustart.
        return produkte.laden(self.konfig.produkte_pfad)

    def produkt(self, produkt_id: str) -> produkte.Produkt:
        for p in self.produkte():
            if p.id == produkt_id:
                return p
        raise EingabeFehler(f"Unbekanntes Produkt: {produkt_id!r}")

    def produkt_speichern(self, daten: dict, alte_id: str | None = None) -> produkte.Produkt:
        """Produkt anlegen (alte_id leer) oder ändern. Die id wird beim Anlegen aus dem Namen gebildet."""
        with self._schreibsperre:
            liste = self.produkte()
            ids = {p.id for p in liste}
            if alte_id and alte_id not in ids:
                raise EingabeFehler(f"Unbekanntes Produkt: {alte_id!r}")
            pid = alte_id or produkte.neue_id(str(daten.get("name") or ""), ids)
            neu, fehler = produkte.pruefen(pid, str(daten.get("name") or ""),
                                           str(daten.get("gtin") or ""), daten.get("mhd_monate"))
            if fehler:
                raise EingabeFehler(fehler)
            doppelt = next((p for p in liste if p.gtin == neu.gtin and p.id != pid), None)
            if doppelt:
                raise EingabeFehler(f"Die EAN {neu.gtin} gehört schon zu „{doppelt.anzeigename}“")
            if alte_id:
                liste = [neu if p.id == alte_id else p for p in liste]
            else:
                liste.append(neu)
            produkte.speichern(self.konfig.produkte_pfad, liste)
            return neu

    def produkt_loeschen(self, produkt_id: str) -> None:
        with self._schreibsperre:
            liste = self.produkte()
            rest = [p for p in liste if p.id != produkt_id]
            if len(rest) == len(liste):
                raise EingabeFehler(f"Unbekanntes Produkt: {produkt_id!r}")
            if not rest:
                raise EingabeFehler("Das letzte Produkt kann nicht gelöscht werden")
            produkte.speichern(self.konfig.produkte_pfad, rest)

    def mhd_vorschlag(self, produkt_id: str, abpackdatum: date | None = None) -> date:
        return mhd.berechnen(abpackdatum or date.today(), self.produkt(produkt_id).mhd_monate)

    # --- Etikett --------------------------------------------------------------

    def etikett(self, produkt_id: str, mhd_datum: date | None = None, menge: int = 1) -> str:
        p = self.produkt(produkt_id)
        if not isinstance(menge, int) or not 1 <= menge <= 999:
            raise EingabeFehler("Menge muss zwischen 1 und 999 liegen")
        if mhd_datum is None:
            mhd_datum = self.mhd_vorschlag(produkt_id)
        if mhd_datum < date.today():
            raise EingabeFehler(f"MHD {mhd_datum:%d.%m.%Y} liegt in der Vergangenheit")
        return zpl.erzeugen(self.konfig, zpl.EtikettDaten(p.name, p.gtin, mhd_datum, menge))

    def drucken(self, produkt_id: str, mhd_datum: date | None = None, menge: int = 1) -> str:
        p = self.produkt(produkt_id)
        mhd_datum = mhd_datum or self.mhd_vorschlag(produkt_id)
        text = self.etikett(produkt_id, mhd_datum, menge)
        try:
            with self._sperre:
                meldung = drucker.transport(self.konfig).senden(zpl.kodieren(self.konfig, text))
        except drucker.DruckFehler as e:
            self._protokollieren(p, mhd_datum, menge, f"FEHLER: {e}")
            raise
        self._protokollieren(p, mhd_datum, menge, "ok")
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

    def _protokollieren(self, p: produkte.Produkt, mhd_datum: date, menge: int, ergebnis: str) -> None:
        pfad = self.konfig.protokoll_pfad
        if not pfad:
            return
        try:
            pfad.parent.mkdir(parents=True, exist_ok=True)
            neu = not pfad.exists()
            with pfad.open("a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if neu:
                    w.writerow(["zeitpunkt", "produkt_id", "name", "gtin", "mhd", "menge", "ergebnis"])
                w.writerow([datetime.now().isoformat(timespec="seconds"), p.id, p.anzeigename,
                            p.gtin, mhd_datum.isoformat(), menge, ergebnis])
        except OSError:
            pass  # Das Protokoll ist nützlich, darf aber nie den Druck verhindern.
