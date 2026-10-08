# Änderungen

## Unveröffentlicht

- Oberfläche ist jetzt ein Web Component `<etiketten-app>` und lässt sich in andere
  Seiten einbinden (Vorbereitung für das Portal TOSTO). Attribute `api`, `produkt`,
  `titel`. Aussehen über CSS-Variablen (`--farbe-akzent`, `--schrift`, `--radius` …).
- Beispielseite `static/beispiel-einbindung.html` mit fremdem Design.
- **Kaffees mit Versionen:** Ein Kaffee kann mehrere Versionen mit eigener GTIN haben
  (z. B. Edeka und Rewe). Beim Drucken wird die Version gewählt, wenn es mehrere gibt.
- **Produkte im Browser pflegen** (Reiter „Produkte“): Kaffees anlegen und ändern,
  Versionen hinzufügen, archivieren. GTIN-Prüfung schon beim Tippen.
  Ausschaltbar mit `produkte_bearbeiten = false`.
- Produktliste jetzt `data/produkte.json` statt `data/produkte.csv` (übernommen, jeweils
  Version „Edeka“).
- API: `kaffee` und `version` statt `produkt`, neu `POST /api/kaffees` und
  `PUT /api/kaffees/<id>`. Beschrieben in `docs/API.md`.
- Druckprotokoll mit Version. Ein Protokoll aus 0.2 wird beim ersten Druck in
  `druckprotokoll-bis-0.2.csv` umbenannt.
- Kommandozeile: `drucken`/`zpl` mit `--version`, `produkte --alle`.
- CSS-Variable `--farbschema` für dunkle Designs.
- Server liefert `.js`/`.css` mit festem MIME-Typ aus (unter Windows nötig für ES-Module).

## 0.2.0 – 2026-10-07

Erste am echten Drucker getestete Version, im Betrieb einsetzbar.

- Erster Test am echten CL-S521: Testetikett, Produktetikett und Druck über die
  Weboberfläche funktionieren.
- `check` erkennt die Zebra-Emulation `Z2` des Citizen und warnt nicht mehr
  fälschlich „nicht ZPL“.
- Offene Punkte in `docs/ENTSCHEIDUNGEN.md` auf den aktuellen Stand gebracht.

## 0.1.0 – 2026-10-02

Erste Version des Minimal-Etiketts (Titel, EAN-13, MHD).

- ZPL-Erzeugung mit Layout in mm, automatischer Titelgröße (max. 2 Zeilen) und
  nativem EAN-13 des Druckers
- Druckwege: USB direkt (automatische Erkennung des Citizen), CUPS-raw, Netzwerk (9100), Trockenlauf
- Weboberfläche: Produkt → Menge → Drucken, MHD berechnet/überschreibbar, Vorschau über labelary.com
- Kommandozeile: `start`, `check`, `testdruck`, `produkte`, `zpl`, `drucken`
- Druckprotokoll als CSV
