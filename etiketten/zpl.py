"""ZPL-Erzeugung: Produkt + MHD + Menge → ZPL-Text.

Das ist die einzige Stelle, an der das Layout entsteht. Vorschau und Druck
verwenden exakt denselben Text.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .config import Konfig

# Geschätzte Zeichenbreite der Druckerschrift 0 (^A0) relativ zur Schrifthöhe.
# Bewusst etwas großzügig: lieber eine Stufe kleiner als ein Umbruch durch den Drucker.
_SCHMAL = set("iIjlrtf.,:;'|!() ")
_BREIT = set("MWmwÄÖÜ@%")
_BREITE_SCHMAL, _BREITE_NORMAL, _BREITE_BREIT = 0.30, 0.52, 0.80

ZEILENABSTAND = 1.08

# Die erste EAN-Ziffer steht links vor dem ersten Balken, am Anfang der Ruhezone
# (11 Module). So viel Platz wird links vom ersten Balken freigehalten.
VORZIFFER_MODULE = 12


@dataclass(frozen=True)
class EtikettDaten:
    name: str      # "|" = erzwungener Zeilenumbruch
    gtin: str      # 13 Ziffern, Prüfziffer bereits geprüft
    mhd: date
    menge: int = 1


def textbreite(text: str, hoehe: float) -> float:
    """Geschätzte Breite eines Textes in derselben Einheit wie hoehe."""
    summe = 0.0
    for z in text:
        if z in _SCHMAL:
            summe += _BREITE_SCHMAL
        elif z in _BREIT:
            summe += _BREITE_BREIT
        else:
            summe += _BREITE_NORMAL
    return summe * hoehe


def _umbrechen(absatz: str, breite: float, hoehe: float) -> list[str]:
    """Wortweiser Umbruch; zu lange Wörter werden hart getrennt."""
    zeilen: list[str] = []
    aktuell = ""
    for wort in absatz.split():
        while textbreite(wort, hoehe) > breite and len(wort) > 1:
            if aktuell:
                zeilen.append(aktuell)
                aktuell = ""
            n = len(wort)
            while n > 1 and textbreite(wort[:n], hoehe) > breite:
                n -= 1
            zeilen.append(wort[:n])
            wort = wort[n:]
        kandidat = f"{aktuell} {wort}" if aktuell else wort
        if textbreite(kandidat, hoehe) <= breite:
            aktuell = kandidat
        else:
            zeilen.append(aktuell)
            aktuell = wort
    if aktuell:
        zeilen.append(aktuell)
    return zeilen


def titel_setzen(name: str, breite: int, hoehe: int, max_zeilen: int,
                 schrift_max: int, schrift_min: int) -> tuple[int, list[str]]:
    """Größte Schrift (in Punkten) finden, bei der der Name in den Titelbereich passt.

    Passt er auch in der kleinsten Schrift nicht, wird er auf max_zeilen gekürzt.
    """
    absaetze = [a.strip() for a in name.split("|") if a.strip()] or [""]
    for schrift in range(schrift_max, schrift_min - 1, -1):
        zeilen = [z for a in absaetze for z in _umbrechen(a, breite, schrift)]
        hoch = len(zeilen) * schrift * ZEILENABSTAND
        if len(zeilen) <= max_zeilen and hoch <= hoehe:
            return schrift, zeilen
    zeilen = [z for a in absaetze for z in _umbrechen(a, breite, schrift_min)]
    if len(zeilen) > max_zeilen:
        zeilen = zeilen[:max_zeilen]
        letzte = zeilen[-1]
        while letzte and textbreite(letzte + "...", schrift_min) > breite:
            letzte = letzte[:-1]
        zeilen[-1] = letzte.rstrip() + "..."
    return schrift_min, zeilen


def feldtext(text: str) -> str:
    """Steuerzeichen von ZPL (^ ~) und das Hex-Zeichen (_) für ^FH maskieren."""
    return "".join(f"_{ord(z):02X}" if z in "_^~" else z for z in text)


class Layout:
    """Rechnet Millimeter aus der Konfiguration in Druckpunkte um."""

    def __init__(self, konfig: Konfig):
        self.k = konfig
        self.dpi = int(konfig["drucker"]["dpi"])
        etikett = konfig["etikett"]
        self.vx = float(etikett.get("versatz_x", 0))
        self.vy = float(etikett.get("versatz_y", 0))
        self.breite = self.punkte(etikett["breite"])
        self.hoehe = self.punkte(etikett["hoehe"])

    def punkte(self, mm: float) -> int:
        return round(float(mm) * self.dpi / 25.4)

    def pos(self, x_mm: float, y_mm: float) -> tuple[int, int]:
        return (max(0, self.punkte(x_mm + self.vx)), max(0, self.punkte(y_mm + self.vy)))


def erzeugen(konfig: Konfig, daten: EtikettDaten) -> str:
    """ZPL-Text für ein Etikett (in der gewünschten Menge) erzeugen."""
    if not 1 <= daten.menge <= 999:
        raise ValueError("Menge muss zwischen 1 und 999 liegen")
    if len(daten.gtin) != 13 or not daten.gtin.isdigit():
        raise ValueError(f"Ungültige EAN-13: {daten.gtin!r}")

    lay = Layout(konfig)
    drucker = konfig["drucker"]
    titel = konfig["layout"]["titel"]
    barcode = konfig["layout"]["barcode"]
    mhd = konfig["layout"]["mhd"]

    z: list[str] = ["^XA"]
    z.append("^CI28" if drucker.get("zeichensatz", "utf8") == "utf8" else "^CI27")
    z.append(f"^PW{lay.breite}")
    z.append(f"^LL{lay.hoehe}")
    z.append("^LH0,0")
    if drucker.get("schwaerzung") is not None:
        z.append(f"^MD{int(drucker['schwaerzung'])}")
    if drucker.get("geschwindigkeit") is not None:
        z.append(f"^PR{int(drucker['geschwindigkeit'])}")

    # Titel: ein bis max_zeilen zentrierte Zeilen, senkrecht im Titelbereich zentriert
    t_breite, t_hoehe = lay.punkte(titel["breite"]), lay.punkte(titel["hoehe"])
    schrift, zeilen = titel_setzen(
        daten.name, t_breite, t_hoehe, int(titel["max_zeilen"]),
        lay.punkte(titel["schrift_max"]), lay.punkte(titel["schrift_min"]),
    )
    zeilenhoehe = round(schrift * ZEILENABSTAND)
    tx, ty = lay.pos(titel["x"], titel["y"])
    ty += max(0, (t_hoehe - zeilenhoehe * len(zeilen)) // 2)
    for i, zeile in enumerate(zeilen):
        z.append(f"^FO{tx},{ty + i * zeilenhoehe}^A0N,{schrift},{schrift}"
                 f"^FB{t_breite},1,0,C^FH^FD{feldtext(zeile)}^FS")

    # Barcode: EAN-13 vom Drucker selbst erzeugt; er rechnet die Prüfziffer selbst.
    # ^FO bezeichnet den ersten Balken – die führende Ziffer steht links davor,
    # darum wird um VORZIFFER_MODULE verschoben, damit x die linke Kante der Ziffer ist.
    modul = int(barcode["modul"])
    bx, by = lay.pos(barcode["x"], barcode["y"])
    bx += VORZIFFER_MODULE * modul
    z.append(f"^FO{bx},{by}^BY{modul}"
             f"^BEN,{lay.punkte(barcode['balkenhoehe'])},Y,N^FD{daten.gtin[:12]}^FS")

    # MHD: senkrecht, von unten nach oben lesbar (Drehung B = 270°)
    datum = daten.mhd.strftime(mhd["datumsformat"])
    mx, my = lay.pos(mhd["x"], mhd["y"])
    laenge = lay.punkte(mhd["laenge"])
    d_schrift = lay.punkte(mhd["datum_schrift"])
    if mhd.get("einzeilig"):
        text = f"{mhd['beschriftung']} {datum}".strip()
        # eine Zeile: Schrift verkleinern, bis der Text in die Länge passt
        while d_schrift > 12 and textbreite(text, d_schrift) > laenge:
            d_schrift -= 1
        z.append(f"^FO{mx},{my}^A0B,{d_schrift},{d_schrift}"
                 f"^FB{laenge},1,0,C^FH^FD{feldtext(text)}^FS")
    else:
        b_schrift = lay.punkte(mhd["beschriftung_schrift"])
        z.append(f"^FO{mx},{my}^A0B,{b_schrift},{b_schrift}"
                 f"^FB{laenge},1,0,C^FH^FD{feldtext(mhd['beschriftung'])}^FS")
        z.append(f"^FO{mx + round(b_schrift * 1.1)},{my}^A0B,{d_schrift},{d_schrift}"
                 f"^FB{laenge},1,0,C^FH^FD{feldtext(datum)}^FS")

    z.append(f"^PQ{daten.menge},0,1,Y")
    z.append("^XZ")
    return "\n".join(z) + "\n"


# --- Verpackungsetikett ---------------------------------------------------------

@dataclass(frozen=True)
class VerpackungsDaten:
    name: str        # "|" = erzwungener Zeilenumbruch
    info: str        # "|" = neue Zeile, "#" am Zeilenanfang = Überschrift, darf leer sein
    charge: str      # bereits geprüft, z. B. "Rö261012-01"
    roestdatum: date
    mhd: date
    qr: str          # Inhalt des QR-Codes (Adresse)
    menge: int = 1
    stil: str = "schlicht"   # siehe STILE


# Gestaltung des Verpackungsetiketts: schlicht = Linien, klassisch = Rahmen mit
# Stern-Ornament (Entwurf A), banner = schwarzes Band oben (Entwurf B).
STILE = ("schlicht", "klassisch", "banner")


# Byte-Kapazität eines QR-Codes mit Fehlerkorrektur M, Version 1–10
_QR_KAPAZITAET = (14, 26, 42, 62, 84, 106, 122, 152, 180, 213)


def qr_module(text: str) -> int:
    """Kantenlänge des QR-Codes in Modulen (ohne Ruhezone), großzügig geschätzt."""
    laenge = len(text.encode("utf-8"))
    for version, kapazitaet in enumerate(_QR_KAPAZITAET, start=1):
        if laenge <= kapazitaet:
            return 17 + 4 * version
    raise ValueError(f"QR-Inhalt zu lang ({laenge} Bytes, höchstens {_QR_KAPAZITAET[-1]})")


def _kopf(konfig: Konfig, lay: Layout) -> list[str]:
    drucker = konfig["drucker"]
    z = ["^XA", "^CI28" if drucker.get("zeichensatz", "utf8") == "utf8" else "^CI27",
         f"^PW{lay.breite}", f"^LL{lay.hoehe}", "^LH0,0"]
    if drucker.get("schwaerzung") is not None:
        z.append(f"^MD{int(drucker['schwaerzung'])}")
    if drucker.get("geschwindigkeit") is not None:
        z.append(f"^PR{int(drucker['geschwindigkeit'])}")
    return z


def _zeile(x: int, y: int, breite: int, schrift: int, text: str, ausrichtung: str = "L") -> str:
    return f"^FO{x},{y}^A0N,{schrift},{schrift}^FB{breite},1,0,{ausrichtung}^FH^FD{feldtext(text)}^FS"


def _info(lay: Layout, info: dict, text: str, x: int, y: int, breite: int, hoehe: int,
          ausrichtung: str = "L") -> list[str]:
    """Infotext setzen: selbst umbrochen, überzählige Zeilen werden gekürzt.
    "|" = neue Zeile, "#" am Zeilenanfang = Überschrift (ueberschrift_schrift)."""
    if not text.strip():
        return []
    i_schrift = lay.punkte(info["schrift"])
    u_schrift = lay.punkte(info.get("ueberschrift_schrift", info["schrift"]))
    zeilen = []  # (Schrift, Text); leerer Text = Leerzeile
    for absatz in text.split("|"):
        absatz = absatz.strip()
        schrift = i_schrift
        if absatz.startswith("#"):
            absatz, schrift = absatz.lstrip("#").strip(), u_schrift
        zeilen += [(schrift, t) for t in _umbrechen(absatz, breite, schrift)] if absatz else [(i_schrift, "")]
    hoehen = [round(s * 1.3) for s, _ in zeilen]
    if sum(hoehen) > hoehe:
        while len(zeilen) > 1 and sum(hoehen[:len(zeilen)]) > hoehe:
            zeilen.pop()
        schrift, letzte = zeilen[-1]
        while letzte and textbreite(letzte + "...", schrift) > breite:
            letzte = letzte[:-1]
        zeilen[-1] = (schrift, letzte.rstrip() + "...")
    z = []
    for (schrift, zeile), h in zip(zeilen, hoehen):
        if zeile:
            z.append(_zeile(x, y, breite, schrift, zeile, ausrichtung))
        y += h
    return z


def stern(groesse: int) -> str:
    """Gefüllter fünfzackiger Stern als ZPL-Grafik (^GFA), Kantenlänge in Punkten."""
    r_aussen, r_innen = groesse / 2, groesse / 2 * 0.40
    ecken = []
    for i in range(10):
        r = r_aussen if i % 2 == 0 else r_innen
        w = -math.pi / 2 + i * math.pi / 5
        ecken.append((groesse / 2 + r * math.cos(w), groesse / 2 + r * math.sin(w)))
    bytes_zeile = (groesse + 7) // 8
    daten = bytearray()
    for y in range(groesse):
        mitte = y + 0.5
        schnitte = sorted(x1 + (mitte - y1) * (x2 - x1) / (y2 - y1)
                          for (x1, y1), (x2, y2) in zip(ecken, ecken[1:] + ecken[:1])
                          if (y1 <= mitte) != (y2 <= mitte))
        zeile = 0
        for a, b in zip(schnitte[::2], schnitte[1::2]):
            for x in range(max(0, round(a)), min(groesse, round(b))):
                zeile |= 1 << (bytes_zeile * 8 - 1 - x)
        daten += zeile.to_bytes(bytes_zeile, "big")
    return f"^GFA,{len(daten)},{len(daten)},{bytes_zeile},{daten.hex().upper()}"


def verpackung_erzeugen(konfig: Konfig, daten: VerpackungsDaten) -> str:
    """ZPL für das Verpackungsetikett. `konfig` ist `Konfig.fuer_verpackung()`."""
    if not 1 <= daten.menge <= 999:
        raise ValueError("Menge muss zwischen 1 und 999 liegen")
    if any(z in daten.qr for z in "^~"):
        raise ValueError("QR-Adresse darf weder ^ noch ~ enthalten")
    if daten.stil not in STILE:
        raise ValueError(f"Unbekannte Gestaltung {daten.stil!r} (möglich: {', '.join(STILE)})")
    if daten.stil != "schlicht":
        return _verpackung_gestaltet(konfig, daten)
    lay = Layout(konfig)
    lo = konfig["layout"]
    z = _kopf(konfig, lay)

    # Name: groß, zentriert, bis zu max_zeilen
    titel = lo["titel"]
    t_breite, t_hoehe = lay.punkte(titel["breite"]), lay.punkte(titel["hoehe"])
    schrift, zeilen = titel_setzen(
        daten.name, t_breite, t_hoehe, int(titel["max_zeilen"]),
        lay.punkte(titel["schrift_max"]), lay.punkte(titel["schrift_min"]),
    )
    zeilenhoehe = round(schrift * ZEILENABSTAND)
    tx, ty = lay.pos(titel["x"], titel["y"])
    ty += max(0, (t_hoehe - zeilenhoehe * len(zeilen)) // 2)
    for i, zeile in enumerate(zeilen):
        z.append(_zeile(tx, ty + i * zeilenhoehe, t_breite, schrift, zeile, "C"))

    # Trennlinien über die Breite des Namens
    for name in ("linie_oben", "linie_unten"):
        linie = lo.get(name)
        if linie:
            lx, ly = lay.pos(titel["x"], linie["y"])
            staerke = max(1, lay.punkte(linie["staerke"]))
            z.append(f"^FO{lx},{ly}^GB{t_breite},{staerke},{staerke}^FS")

    # Info: links bündig, selbst umbrochen, überzählige Zeilen werden gekürzt
    info = lo["info"]
    ix, iy = lay.pos(info["x"], info["y"])
    z += _info(lay, info, daten.info, ix, iy, lay.punkte(info["breite"]), lay.punkte(info["hoehe"]))

    # Daten links unten: Beschriftung klein, Wert groß darunter
    d = lo["daten"]
    qr = lo["qr"]
    dx, dy = lay.pos(d["x"], d["y"])
    d_breite = lay.punkte(qr["x"] - d["x"] - 2)
    b_schrift, w_schrift = lay.punkte(d["beschriftung_schrift"]), lay.punkte(d["wert_schrift"])
    fmt = d["datumsformat"]
    for n, (beschriftung, wert) in enumerate((
        ("Röstdatum", daten.roestdatum.strftime(fmt)),
        ("Charge", daten.charge),
        ("Mindestens haltbar bis", daten.mhd.strftime(fmt)),
    )):
        y = dy + n * lay.punkte(d["abstand"])
        z.append(_zeile(dx, y, d_breite, b_schrift, beschriftung))
        w = w_schrift
        while w > 12 and textbreite(wert, w) > d_breite:
            w -= 1
        z.append(_zeile(dx, y + round(b_schrift * 1.25), d_breite, w, wert))

    # QR-Code rechts unten, so groß wie möglich im Feld, darunter die Adresse lesbar
    if daten.qr:
        feld = lay.punkte(qr["groesse"])
        module = qr_module(daten.qr)
        faktor = max(1, min(10, feld // module))
        qx, qy = lay.pos(qr["x"], qr["y"])
        rand = (feld - module * faktor) // 2
        z.append(f"^FO{qx + rand},{qy + rand}^BQN,2,{faktor}^FDMA,{daten.qr}^FS")
        anzeige = konfig["verpackung"].get("qr_text") or daten.qr.split("://", 1)[-1].rstrip("/")
        t_schrift = lay.punkte(qr["text_schrift"])
        t_breite = feld + lay.punkte(6)
        while t_schrift > 10 and textbreite(anzeige, t_schrift) > t_breite:
            t_schrift -= 1
        z.append(_zeile(qx - lay.punkte(3), qy + feld + lay.punkte(1.5), t_breite, t_schrift, anzeige, "C"))

    z.append(f"^PQ{daten.menge},0,1,Y")
    z.append("^XZ")
    return "\n".join(z) + "\n"


def kodieren(konfig: Konfig, zpl_text: str) -> bytes:
    """ZPL-Text in die Bytes umwandeln, die zum Drucker gehen (passend zu ^CI)."""
    if konfig["drucker"].get("zeichensatz", "utf8") == "utf8":
        return zpl_text.encode("utf-8")
    return zpl_text.encode("cp1252", errors="replace")


def testetikett(konfig: Konfig) -> str:
    """Kalibrier- und Testetikett: Rahmen am Rand, Umlaute, Beispiel-Barcode, Zeichensatz."""
    lay = Layout(konfig)
    rand = lay.punkte(2)
    zs = konfig["drucker"].get("zeichensatz", "utf8")
    z = [
        "^XA",
        "^CI28" if zs == "utf8" else "^CI27",
        f"^PW{lay.breite}", f"^LL{lay.hoehe}", "^LH0,0",
    ]
    x0, y0 = lay.pos(0, 0)
    # Rahmen 2 mm vom Rand: sitzt er ungleichmäßig, versatz_x / versatz_y anpassen
    z.append(f"^FO{x0 + rand},{y0 + rand}^GB{lay.breite - 2 * rand},{lay.hoehe - 2 * rand},2^FS")
    groesse = lay.punkte(3.2)
    zeilen = [
        "TESTDRUCK " + konfig["drucker"].get("name", ""),
        "Umlaute: Größe Äthiopien Café",
        f"Zeichensatz: {zs}  dpi: {lay.dpi}",
    ]
    for i, zeile in enumerate(zeilen):
        z.append(f"^FO{x0 + rand + 10},{y0 + rand + 8 + i * round(groesse * 1.15)}"
                 f"^A0N,{groesse},{groesse}^FH^FD{feldtext(zeile)}^FS")
    # Das Verpackungsetikett hat keinen Barcode im Layout, dann gilt der Standard
    modul = int(konfig["layout"].get("barcode", {}).get("modul", 3))
    z.append(f"^FO{x0 + rand + 10 + VORZIFFER_MODULE * modul},{y0 + lay.punkte(17)}^BY{modul}"
             f"^BEN,{lay.punkte(8)},Y,N^FD400638133393^FS")
    z.append("^PQ1,0,1,Y")
    z.append("^XZ")
    return "\n".join(z) + "\n"


def _verpackung_gestaltet(konfig: Konfig, daten: VerpackungsDaten) -> str:
    """Stile „klassisch“ und „banner“ (Entwürfe A/B in docs/entwuerfe/). Feste Aufteilung
    für 100 × 150 mm, bei anderer Größe anteilig gestreckt. Schriftgrößen der Info aus
    [verpackung.layout.info]."""
    lay = Layout(konfig)
    sx, sy = float(konfig["etikett"]["breite"]) / 100, float(konfig["etikett"]["hoehe"]) / 150

    def p(x_mm: float, y_mm: float) -> tuple[int, int]:
        return lay.pos(x_mm * sx, y_mm * sy)

    def b(mm: float) -> int:
        return lay.punkte(mm * sx)

    def h(mm: float) -> int:
        return lay.punkte(mm * sy)

    banner = daten.stil == "banner"
    z = _kopf(konfig, lay)
    weiss = "^FR" if banner else ""  # im schwarzen Band: Farbe umkehren

    if banner:
        x, y = p(0, 0)
        z.append(f"^FO{x},{y}^GB{lay.breite},{h(40)},{h(40)}^FS")
        s = lay.punkte(5)
        for sx_mm in (12, 83):
            x, y = p(sx_mm, 8)
            z.append(f"^FO{x},{y}^FR{stern(s)}^FS")
    else:
        x, y = p(3, 3)
        z.append(f"^FO{x},{y}^GB{b(94)},{h(144)},{lay.punkte(0.6)},B,1^FS")
        x, y = p(4.5, 4.5)
        z.append(f"^FO{x},{y}^GB{b(91)},{h(141)},2,B,1^FS")

    # Kopfzeile, gesperrt in Großbuchstaben
    kopf = str(konfig["verpackung"].get("kopfzeile", "")).strip()
    if kopf:
        gesperrt = "  ".join(" ".join(wort) for wort in kopf.upper().split())
        k_schrift = lay.punkte(3.0)
        while k_schrift > 14 and textbreite(gesperrt, k_schrift) > b(76):
            k_schrift -= 1
        x, y = p(6, 7 if banner else 11)
        z.append(f"^FO{x},{y}{weiss}^A0N,{k_schrift},{k_schrift}^FB{b(88)},1,0,C^FH^FD{feldtext(gesperrt)}^FS")

    # Name groß, zentriert, bis zu zwei Zeilen
    t_breite, t_hoehe = b(84), h(20 if banner else 17)
    schrift, zeilen = titel_setzen(daten.name, t_breite, t_hoehe, 2, lay.punkte(11), lay.punkte(6))
    zh = round(schrift * ZEILENABSTAND)
    tx, ty = p(8, 14 if banner else 17)
    ty += max(0, (t_hoehe - zh * len(zeilen)) // 2)
    for i, zeile in enumerate(zeilen):
        z.append(f"^FO{tx},{ty + i * zh}{weiss}^A0N,{schrift},{schrift}^FB{t_breite},1,0,C"
                 f"^FH^FD{feldtext(zeile)}^FS")

    # Info
    info = konfig["layout"]["info"]
    if banner:
        ix, iy = p(8, 47)
        z += _info(lay, info, daten.info, ix, iy, b(84), h(48))
    else:
        x, y = p(18, 37)
        z.append(f"^FO{x},{y}^GB{b(25)},2,2^FS")
        s = lay.punkte(6)
        x, y = p(50, 37)
        z.append(f"^FO{x - s // 2},{y - s // 2}{stern(s)}^FS")
        x, y = p(57, 37)
        z.append(f"^FO{x},{y}^GB{b(25)},2,2^FS")
        ix, iy = p(9, 44)
        z += _info(lay, info, daten.info, ix, iy, b(82), h(51), "C")

    # Unten: Daten links, QR-Code rechts
    if banner:
        for x_mm, breite_mm in ((6, 52), (60, 34)):
            x, y = p(x_mm, 99)
            z.append(f"^FO{x},{y}^GB{b(breite_mm)},{h(45)},2,B,2^FS")
        dx_mm, qx_mm = 10, 62
    else:
        x, y = p(9, 98)
        z.append(f"^FO{x},{y}^GB{b(82)},2,2^FS")
        dx_mm, qx_mm = 9, 60
    fmt = konfig["layout"]["daten"]["datumsformat"]
    d_breite, b_schrift, w_schrift = b(48), lay.punkte(2.6), lay.punkte(5.2)
    for n, (beschriftung, wert) in enumerate((
        ("RÖSTDATUM", daten.roestdatum.strftime(fmt)),
        ("CHARGE", daten.charge),
        ("MINDESTENS HALTBAR BIS", daten.mhd.strftime(fmt)),
    )):
        x, y = p(dx_mm, 103 + n * 13.5)
        z.append(_zeile(x, y, d_breite, b_schrift, beschriftung))
        w = w_schrift
        while w > 12 and textbreite(wert, w) > d_breite:
            w -= 1
        z.append(_zeile(x, y + lay.punkte(3.4), d_breite, w, wert))
    if daten.qr:
        feld = min(b(30), h(30))
        module = qr_module(daten.qr)
        faktor = max(1, min(10, feld // module))
        rand = (feld - module * faktor) // 2
        x, y = p(qx_mm + 1, 102)
        z.append(f"^FO{x + rand},{y + rand}^BQN,2,{faktor}^FDMA,{daten.qr}^FS")
        anzeige = konfig["verpackung"].get("qr_text") or daten.qr.split("://", 1)[-1].rstrip("/")
        t_schrift, t_breite = lay.punkte(2.6), b(32)
        while t_schrift > 10 and textbreite(anzeige, t_schrift) > t_breite:
            t_schrift -= 1
        x, y = p(qx_mm, 135)
        z.append(_zeile(x, y, t_breite, t_schrift, anzeige, "C"))

    z.append(f"^PQ{daten.menge},0,1,Y")
    z.append("^XZ")
    return "\n".join(z) + "\n"
