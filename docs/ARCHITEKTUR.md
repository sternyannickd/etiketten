# Architektur

## Grundsatz

```
            ┌──────────── Vorschau (labelary.com, optional)
Kaffee  ──► ZPL-Text ──┤
 + Version             └──────────── Druckweg ──► Citizen
 + MHD
 + Menge
```

Es gibt **eine** Stelle, an der das Etikett entsteht (`zpl.py`), und **einen**
ZPL-Text, der sowohl in die Vorschau als auch zum Drucker geht. Der Druckweg
überträgt Bytes und verändert nichts.

## Schichten

| Modul | Aufgabe | Kennt |
|-------|---------|-------|
| `config.py` | `config.toml` laden, mit Standardwerten zusammenführen | – |
| `produkte.py` | Kaffees mit Versionen: JSON lesen, prüfen (EAN-13, GTIN eindeutig), atomar speichern | – |
| `mhd.py` | Datum + Monate | – |
| `zpl.py` | Layout (mm) → ZPL (Druckpunkte), Titel umbrechen und Schrift anpassen, Testetikett | config |
| `drucker.py` | Druckwege `usb`, `cups`, `tcp`, `datei`, jeweils mit `pruefen()` und `senden(bytes)` | config |
| `dienst.py` | `Druckdienst`: der Ablauf, also Kaffee und Version suchen, Produkte ändern, MHD vorschlagen, ZPL erzeugen, senden, protokollieren, Vorschau | alle oben |
| `server.py` | HTTP: Oberfläche und JSON-API | dienst |
| `cli.py` | Kommandozeile | dienst, server |
| `static/` | Web Component `<etiketten-app>` ohne Build-Schritt, `index.html` bindet es ein | API |

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

Vollständig mit Datenmodell in [API.md](API.md). Kurz:

| Methode & Pfad | Zweck |
|----------------|-------|
| `GET /api/status` | Drucker, Vorschau, ob Produkte bearbeitbar sind |
| `GET /api/produkte[?alle=1]` | Kaffees mit Versionen |
| `GET /api/mhd?kaffee=ID&abgepackt=…` | berechnetes MHD |
| `POST /api/zpl`, `/api/vorschau`, `/api/drucken` | `{kaffee, version?, mhd?, menge?}` |
| `POST /api/testdruck` | Testetikett |
| `POST /api/kaffees`, `PUT /api/kaffees/<id>` | Kaffee anlegen bzw. ändern |

Beispiel:

```sh
curl -X POST localhost:8077/api/drucken -H 'Content-Type: application/json' \
     -d '{"kaffee":"kolumbien","version":"edeka","menge":6}'
```

## Einbinden in andere Seiten

Die Oberfläche ist ein Web Component. Jede Seite kann sie einbinden:

```html
<script type="module" src="https://<server>/static/etiketten-app.js"></script>
<etiketten-app api="https://<server>/api"></etiketten-app>
```

| Attribut | Bedeutung |
|----------|-----------|
| `api` | Basisadresse der HTTP-API (Standard `/api`) |
| `kaffee`, `version` | Kaffee und Version, die beim Start gewählt sind |
| `titel` | Überschrift, Standard „Etikettendruck“. `titel=""` blendet sie aus |

**Aussehen:** Das Component kapselt seine Stile (Shadow DOM), übernimmt aber
CSS-Variablen der Seite: `--farbe-flaeche`, `--farbe-text`, `--farbe-text-leise`,
`--farbe-linie`, `--farbe-akzent`, `--farbe-akzent-text`, `--farbe-akzent-hell`,
`--farbe-gut`, `--farbe-schlecht`, `--farbe-warn`, `--schrift`, `--radius`,
`--farbschema` (`dark` bei dunklem Design).
Nicht gesetzte Variablen fallen auf das bisherige Rösterei-Design zurück. Das
Layout richtet sich nach der Breite des Components (Container Query), nicht nach
dem Fenster. Es funktioniert also auch in einer schmalen Spalte.
`static/beispiel-einbindung.html` zeigt eine Einbindung mit fremdem Design.

Liegt die Seite auf einem anderen Server als die API, braucht die API CORS-Header
und eine Anmeldung. Das kommt mit der Einbindung in das Portal (TOSTO).

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
Druckdienst(config.laden()).drucken("kolumbien", "edeka", menge=6)
```

Soll das Enterprise-System auch die Produktdaten liefern, wird `Druckdienst.kaffees()`
durch eine andere Quelle ersetzt. Alles andere bleibt.

**Neuer Druckweg** (z. B. Windows-Rohdruck): in `drucker.py` eine Klasse mit
`pruefen()`/`senden()` ergänzen und in `transport()` eintragen.

**Komplexere Etiketten** (Konzept, `fragen/02-etikettenkonzept.md`): ein
weiterer Erzeuger neben `zpl.erzeugen()`, z. B. mit Röstdatum, Herkunft und
QR-Code (`^BQ`). Die Version wählt das Design über ihr Feld `layout`, der Kaffee bekommt dafür weitere Felder.

**Mehrere Drucker:** heute bewusst nur einer. Wenn nötig, wird `[drucker]` zu
einer Liste, und der Auftrag bekommt ein Feld `drucker`.
