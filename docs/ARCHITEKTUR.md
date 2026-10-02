# Architektur

## Grundsatz

```
            ┌──────────── Vorschau (labelary.com, optional)
Produkt ──► ZPL-Text ──┤
 + MHD                 └──────────── Druckweg ──► Citizen
 + Menge
```

Es gibt **eine** Stelle, an der das Etikett entsteht (`zpl.py`), und **einen**
ZPL-Text, der sowohl in die Vorschau als auch zum Drucker geht. Der Druckweg
überträgt Bytes und verändert nichts.

## Schichten

| Modul | Aufgabe | Kennt |
|-------|---------|-------|
| `config.py` | `config.toml` laden, mit Standardwerten zusammenführen | – |
| `produkte.py` | CSV lesen, EAN-13 prüfen | – |
| `mhd.py` | Datum + Monate | – |
| `zpl.py` | Layout (mm) → ZPL (Druckpunkte), Titel umbrechen und Schrift anpassen, Testetikett | config |
| `drucker.py` | Druckwege `usb`, `cups`, `tcp`, `datei`, jeweils mit `pruefen()` und `senden(bytes)` | config |
| `dienst.py` | `Druckdienst`: der Ablauf, also Produkt suchen, MHD vorschlagen, ZPL erzeugen, senden, protokollieren, Vorschau | alle oben |
| `server.py` | HTTP: Oberfläche und JSON-API | dienst |
| `cli.py` | Kommandozeile | dienst, server |
| `static/` | Browser-Oberfläche ohne Build-Schritt | API |

Oberfläche, Kommandozeile und ein späteres Enterprise-System sind gleichwertige
**Aufrufer des `Druckdienst`**. Keine Drucklogik steckt in der Oberfläche.

## Maße

Das Layout steht in `config.toml` in **Millimetern**. `zpl.Layout.punkte()`
rechnet mit der dpi-Zahl des Druckers um. Ein 300-dpi-Gerät braucht daher
nur `dpi = 300`. Der Kalibrier-Versatz wird auf alle Koordinaten addiert.

Bekannte Eigenheit von ZPL: Bei `^BE` (EAN-13) steht die erste Ziffer **links vor**
dem `^FO`-Punkt, am Anfang der Ruhezone. `zpl.py` verschiebt den Barcode deshalb
um 12 Module, damit `layout.barcode.x` die linke Kante der Ziffer ist.

Die Titelschrift wird über eine geschätzte Zeichenbreite gewählt (`textbreite`).
Die Schätzung ist absichtlich großzügig. Dadurch bricht der Drucker nie selbst
um, was zu überlappenden Zeilen führen würde.

## HTTP-API

Alle Anfragen und Antworten sind JSON (außer der Vorschau, die ein PNG liefert). Fehler
kommen als `{"ok": false, "fehler": "…"}`, mit Status 400 bei falscher Eingabe, 502 bei
Vorschaufehlern und 503 bei Druckfehlern.

| Methode & Pfad | Eingabe | Antwort |
|----------------|---------|---------|
| `GET /api/status` | – | `{drucker:{ok,meldung,hinweis}, drucker_name, transport, vorschau}` |
| `GET /api/produkte` | – | `[{id,name,gtin,mhd_monate}]` |
| `GET /api/mhd?produkt=ID&abgepackt=JJJJ-MM-TT` | – | `{mhd}` |
| `POST /api/zpl` | `{produkt, mhd?, menge?}` | `{ok, zpl}` |
| `POST /api/vorschau` | `{produkt, mhd?}` | PNG |
| `POST /api/drucken` | `{produkt, mhd?, menge?}` | `{ok, meldung}` |
| `POST /api/testdruck` | – | `{ok, meldung}` |

`mhd` fehlt → wird berechnet. `menge` fehlt → 1.

Beispiel:

```sh
curl -X POST localhost:8077/api/drucken -H 'Content-Type: application/json' \
     -d '{"produkt":"kolumbien","menge":6}'
```

## Erweiterungen

**Druckdienst auf einem Raspberry Pi / anderem Rechner.** Das Programm ist
bereits ein Druckdienst. Auf dem Rechner am Drucker mit `host = "0.0.0.0"`
starten, dann können alle Geräte im Netz `http://<rechner>:8077` im Browser
öffnen oder die API aufrufen. Am Code ändert sich nichts. Vor dem Öffnen ins Netz
bedenken: Es gibt **keine Anmeldung**. Jeder im lokalen Netz kann drucken.
Für ein vertrauenswürdiges Rösterei-Netz ist das in Ordnung, ins Internet gehört
der Dienst nicht.

**Enterprise-System.** Entweder die HTTP-API aufrufen oder in Python direkt:

```python
from etiketten import config
from etiketten.dienst import Druckdienst
Druckdienst(config.laden()).drucken("kolumbien", menge=6)
```

Soll das Enterprise-System auch die Produktdaten liefern, wird `Druckdienst.produkte()`
durch eine andere Quelle ersetzt. Alles andere bleibt.

**Neuer Druckweg** (z. B. Windows-Rohdruck): in `drucker.py` eine Klasse mit
`pruefen()`/`senden()` ergänzen und in `transport()` eintragen.

**Komplexere Etiketten** (Konzept, `fragen/02-etikettenkonzept.md`): ein
weiterer Erzeuger neben `zpl.erzeugen()`, z. B. mit Röstdatum, Herkunft und
QR-Code (`^BQ`). Die Produkt-CSV bekommt dafür weitere Spalten.

**Mehrere Drucker:** heute bewusst nur einer. Wenn nötig, wird `[drucker]` zu
einer Liste, und der Auftrag bekommt ein Feld `drucker`.
