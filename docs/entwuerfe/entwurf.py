"""Entwürfe A und B für ein ansprechenderes Verpackungsetikett (12.10.2026).

Erzeugt entwurf_a/b.zpl und die Vorschau entwurf_a/b.png (labelary.com) in diesem Ordner:
    python3 docs/entwuerfe/entwurf.py
Noch nicht ins Programm übernommen, nur zum Vergleichen.
"""
import math, subprocess, sys
from pathlib import Path
ORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(ORDNER.parents[1]))
from etiketten import zpl
D = 8  # Punkte pro mm (203 dpi)
def mm(x): return round(x * D)

def stern_gf(groesse):
    """Fünfzackiger Stern als ^GF-Grafik (gefüllt)."""
    r_a, r_i = groesse / 2, groesse / 2 * 0.40
    pkt = []
    for i in range(10):
        r = r_a if i % 2 == 0 else r_i
        w = -math.pi / 2 + i * math.pi / 5
        pkt.append((groesse / 2 + r * math.cos(w), groesse / 2 + r * math.sin(w)))
    bpz = (groesse + 7) // 8
    daten = []
    for y in range(groesse):
        yy = y + 0.5
        xs = []
        for (x1, y1), (x2, y2) in zip(pkt, pkt[1:] + pkt[:1]):
            if (y1 <= yy) != (y2 <= yy):
                xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        zeile = [0] * (bpz * 8)
        for a, b in zip(xs[::2], xs[1::2]):
            for x in range(max(0, round(a)), min(groesse, round(b))):
                zeile[x] = 1
        for i in range(bpz):
            daten.append(int("".join(map(str, zeile[i*8:i*8+8])), 2))
    hexd = "".join(f"{b:02X}" for b in daten)
    return f"^GFA,{len(daten)},{len(daten)},{bpz},{hexd}"

OBEN = "  ".join(" ".join(w) for w in "STERN RÖSTEREI WISSMÜLLER".split())
INFO_T = "Ein Klassiker mit Geschichte"
INFO = ("Unser Stern Espresso ist das Herzstück unseres Hauses. Über Jahre hinweg haben wir das "
        "Geheimrezept immer weiter verfeinert, und unsere Kunden lieben es nach wie vor. Die mitteldunkle "
        "Röstung begeistert durch ihr leicht nussiges Aroma und ihre geringe Säure, die zusammen für ein "
        "besonders harmonisches Geschmackserlebnis sorgen.")

def text(x, y, b, s, t, a="L"):
    return f"^FO{x},{y}^A0N,{s},{s}^FB{b},1,0,{a}^FH^FD{zpl.feldtext(t)}^FS"

def absatz(x, y, b, s, t, abstand=1.3, a="L"):
    out = []
    for i, z in enumerate(zpl._umbrechen(t, b, s)):
        out.append(text(x, y + i * round(s * abstand), b, s, z, a))
    return out, y + len(zpl._umbrechen(t, b, s)) * round(s * abstand)

def kopf(): return ["^XA", "^CI28", "^PW799", "^LL1199", "^LH0,0"]

def unten(z, y0, x0=mm(9), qr_x=mm(60)):
    for i, (b, w) in enumerate((("RÖSTDATUM", "12.10.2026"), ("CHARGE", "Rö261012-01"), ("MINDESTENS HALTBAR BIS", "12.10.2027"))):
        y = y0 + i * mm(13.5)
        z.append(text(x0, y, mm(48), mm(2.6), b))
        z.append(text(x0, y + mm(3.4), mm(48), mm(5.2), w))
    z.append(f"^FO{qr_x},{y0 - mm(1)}^BQN,2,7^FDMA,https://stern-kaffee.de^FS")
    z.append(text(qr_x - mm(2), y0 + mm(32), mm(36), mm(2.6), "stern-kaffee.de", "C"))

# Entwurf A: Rahmen mit runden Ecken, Stern-Ornament, Kapitälchen-Zeile
def entwurf_a():
    z = kopf()
    z.append(f"^FO{mm(3)},{mm(3)}^GB{mm(94)},{mm(144)},{mm(0.6)},B,1^FS")
    z.append(f"^FO{mm(4.5)},{mm(4.5)}^GB{mm(91)},{mm(141)},2,B,1^FS")
    z.append(text(mm(6), mm(11), mm(88), mm(3.0), OBEN, "C"))
    z.append(text(mm(6), mm(18), mm(88), mm(11), "Stern Espresso", "C"))
    # Ornament: Linie – Stern – Linie
    s = mm(6)
    z.append(f"^FO{mm(18)},{mm(36)}^GB{mm(25)},2,2^FS")
    z.append(f"^FO{mm(50) - s//2},{mm(36) - s//2}{stern_gf(s)}^FS")
    z.append(f"^FO{mm(57)},{mm(36)}^GB{mm(25)},2,2^FS")
    z.append(text(mm(9), mm(44), mm(82), mm(4.6), INFO_T, "C"))
    teile, y = absatz(mm(10), mm(52), mm(80), mm(3.4), INFO, a="C")
    z += teile
    z.append(f"^FO{mm(9)},{mm(98)}^GB{mm(82)},2,2^FS")
    unten(z, mm(103))
    z.append("^XZ")
    return "\n".join(z)

# Entwurf B: schwarzes Band mit weißem Namen, Sterne, Daten in Kästchen
def entwurf_b():
    z = kopf()
    z.append(f"^FO0,0^GB799,{mm(40)},{mm(40)}^FS")
    s = mm(5)
    for x in (mm(12), mm(88) - s):
        z.append(f"^FO{x},{mm(8)}^FR{stern_gf(s)}^FS")
    z.append(f"^FO{mm(6)},{mm(7)}^FR" + text(0, 0, mm(88), mm(3.0), OBEN, "C").split("^FO0,0")[1])
    z.append(f"^FO{mm(6)},{mm(16)}^FR" + text(0, 0, mm(88), mm(11), "Stern Espresso", "C").split("^FO0,0")[1])
    z.append(text(mm(8), mm(47), mm(84), mm(4.8), INFO_T))
    z.append(f"^FO{mm(8)},{mm(53.5)}^GB{mm(20)},{mm(0.8)},{mm(0.8)}^FS")
    teile, y = absatz(mm(8), mm(57), mm(84), mm(3.4), INFO)
    z += teile
    z.append(f"^FO{mm(6)},{mm(99)}^GB{mm(52)},{mm(45)},2,B,2^FS")
    z.append(f"^FO{mm(60)},{mm(99)}^GB{mm(34)},{mm(45)},2,B,2^FS")
    unten(z, mm(103), x0=mm(10), qr_x=mm(62))
    z.append("^XZ")
    return "\n".join(z)

for name, f in (("a", entwurf_a), ("b", entwurf_b)):
    p = str(ORDNER / f"entwurf_{name}")
    open(p + ".zpl", "w", encoding="utf-8").write(f())
    subprocess.run(["curl", "-s", "-o", p + ".png", "-H", "Accept: image/png", "--data-binary", "@" + p + ".zpl",
                    "https://api.labelary.com/v1/printers/8dpmm/labels/3.937x5.906/0/"], check=True)
