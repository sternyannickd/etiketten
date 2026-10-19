"""Erzeugt das Programmsymbol (symbol.png für Linux, symbol.ico für Windows).

Nur Standardbibliothek. Einmalig ausführen, wenn sich das Symbol ändern soll:
    python3 packaging/symbol_erzeugen.py
"""

import struct
import zlib
from pathlib import Path

ZIEL = Path(__file__).parent
GROESSE = 256
BRAUN = (107, 62, 38, 255)
WEISS = (255, 255, 255, 255)
SCHWARZ = (42, 36, 32, 255)
LEER = (0, 0, 0, 0)


def zeichnen(n: int) -> list[list[tuple]]:
    """Etikett mit Barcode auf braunem, abgerundetem Grund – in n×n Pixeln, 4-fach überabgetastet."""
    s = 4
    g = n * s

    def farbe(x: float, y: float) -> tuple:
        # Abgerundetes Quadrat
        r, rand = 0.22, 0.02
        u, v = x / g, y / g
        dx = max(rand + r - u, 0, u - (1 - rand - r))
        dy = max(rand + r - v, 0, v - (1 - rand - r))
        if dx * dx + dy * dy > r * r or not (rand <= u <= 1 - rand and rand <= v <= 1 - rand):
            return LEER
        # Weißes Etikett
        if 0.17 <= u <= 0.83 and 0.24 <= v <= 0.76:
            # Barcode-Striche
            if 0.24 <= u <= 0.76 and 0.33 <= v <= 0.67:
                muster = "1101001100101101100110100101101"
                i = int((u - 0.24) / 0.52 * len(muster))
                return SCHWARZ if muster[min(i, len(muster) - 1)] == "1" else WEISS
            return WEISS
        return BRAUN

    bild = []
    for y in range(n):
        zeile = []
        for x in range(n):
            summe = [0, 0, 0, 0]
            for yy in range(s):
                for xx in range(s):
                    c = farbe(x * s + xx + 0.5, y * s + yy + 0.5)
                    for k in range(4):
                        summe[k] += c[k] * (c[3] if k < 3 else 255)
            a = summe[3] / (s * s * 255 * 255)
            if a == 0:
                zeile.append(LEER)
            else:
                zeile.append(tuple(round(summe[k] / (s * s * 255 * a)) for k in range(3)) + (round(a * 255),))
        bild.append(zeile)
    return bild


def png(bild) -> bytes:
    n = len(bild)
    roh = b"".join(b"\0" + bytes(c for px in zeile for c in px) for zeile in bild)

    def block(art: bytes, daten: bytes) -> bytes:
        return struct.pack(">I", len(daten)) + art + daten + struct.pack(">I", zlib.crc32(art + daten))

    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + block(b"IDAT", zlib.compress(roh, 9)) + block(b"IEND", b""))


def ico(bilder: dict[int, bytes]) -> bytes:
    kopf = struct.pack("<HHH", 0, 1, len(bilder))
    eintraege, daten = b"", b""
    versatz = 6 + 16 * len(bilder)
    for n, inhalt in bilder.items():
        eintraege += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(inhalt), versatz + len(daten))
        daten += inhalt
    return kopf + eintraege + daten


if __name__ == "__main__":
    pngs = {n: png(zeichnen(n)) for n in (256, 48, 32, 16)}
    (ZIEL / "symbol.png").write_bytes(pngs[256])
    (ZIEL / "symbol.ico").write_bytes(ico(pngs))
    print("symbol.png und symbol.ico geschrieben")
