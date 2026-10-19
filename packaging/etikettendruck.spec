# PyInstaller-Bauplan für das fertige Programm (Linux und Windows).
# Aufruf aus dem Projektordner:  pyinstaller --noconfirm packaging/etikettendruck.spec
# Ergebnis: dist/etikettendruck/ (Programmordner, wird vom Installer verpackt)

import sys
from pathlib import Path

PROJEKT = Path(SPECPATH).parent

a = Analysis(
    [str(PROJEKT / "packaging" / "start.py")],
    pathex=[str(PROJEKT)],
    datas=[
        (str(PROJEKT / "etiketten" / "static"), "etiketten/static"),
        (str(PROJEKT / "config.toml"), "."),                 # Grundeinstellung, kommt mit jedem Update
        (str(PROJEKT / "data" / "produkte.csv"), "data"),     # Startliste für den ersten Start
    ],
    excludes=["tkinter", "_tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="etikettendruck",
    console=False,                       # kein schwarzes Fenster unter Windows
    icon=str(PROJEKT / "packaging" / "symbol.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="etikettendruck", upx=False)
