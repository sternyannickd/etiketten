# HTTP-API (Vertrag)

Diese API sprechen die Web Components `<etiketten-app>` und `<verpackung-app>`.
Sie stellt der Python-Server bereit (`etiketten/server.py`), lokal, im
Entwicklermodus und auf dem Firmenserver hinter tosto. **Jede Umsetzung muss sich
an dieses Dokument halten.**

Die Basisadresse übergibt die einbindende Seite: `<etiketten-app api="/api">`. Alle
Pfade unten gelten relativ dazu.

## Allgemein

- Anfragen und Antworten sind JSON (UTF-8). Ausnahme: `POST /vorschau` liefert ein PNG.
- Fehler: `{"ok": false, "fehler": "Meldung für Menschen"}`. Statuscodes:
  `400` falsche Eingabe, `404` unbekannter Pfad, `502` Vorschau nicht verfügbar,
  `503` Druckfehler. Die Meldung zeigt die Oberfläche unverändert an. Sie sollte
  deshalb verständlich und deutsch sein, mehrere Fehler stehen zeilenweise darin.
- Datumswerte als `JJJJ-MM-TT`.
- Schreibende Anfragen tragen `X-CSRF-Token`, wenn die einbindende Seite ein
  `<meta name="csrf-token">` hat. `401` = Sitzung abgelaufen (prüft tosto).

## Datenmodell

```json
{
  "id": "kolumbien",
  "name": "Kolumbien",
  "anzeigename": "Kolumbien",
  "mhd_monate": 12,
  "archiviert": false,
  "info": "Schokolade, Nuss|Huila, 1.700 m",
  "versionen": [
    {"id": "edeka", "bezeichnung": "Edeka", "gtin": "2064000002134",
     "layout": "standard", "archiviert": false}
  ]
}
```

| Feld | Regel |
|------|-------|
| `id` (Kaffee) | Vergibt der Server beim Anlegen aus dem Namen: klein, Umlaute ausgeschrieben (`ä`→`ae`, `ß`→`ss`), alles außer `a–z0–9` wird `-`. Bei Doppelung `-2`, `-3` … Ändert sich danach nie. |
| `name` | Pflicht, max. 60 Zeichen. `|` erzwingt einen Zeilenumbruch auf dem Etikett. |
| `anzeigename` | Nur in Antworten: `name` mit `|` → Leerzeichen. |
| `mhd_monate` | Ganzzahl 1–60. Gilt für alle Versionen des Kaffees. |
| `archiviert` | Archivierte Kaffees werden nicht mehr zum Drucken angeboten. Gelöscht wird nie, damit das Druckprotokoll lesbar bleibt. |
| `info` | Optional, max. 600 Zeichen. Text fürs Verpackungsetikett, `|` = neue Zeile, `||` = Leerzeile, `#` am Zeilenanfang = Überschrift. |
| `versionen` | Mindestens eine. |
| `id` (Version) | Wie die Kaffee-ID, aus `bezeichnung`, eindeutig innerhalb des Kaffees. |
| `bezeichnung` | Pflicht, frei wählbar (z. B. „Edeka“, „Rewe 1 kg“). |
| `gtin` | EAN-13 mit gültiger Prüfziffer. **Über alle Kaffees und Versionen eindeutig**, auch archivierte. |
| `layout` | Etikett-Design. Zurzeit nur `"standard"`. |
| `archiviert` (Version) | Archivierte Versionen werden nicht zum Drucken angeboten. Versionen werden nie gelöscht. |

Gespeichert wird die Liste als `{"format": 1, "kaffees": [...]}` (ohne `anzeigename`),
lokal in `data/produkte.json`.

## Endpunkte

### `GET /status`

```json
{"ok": true, "meldung": "…",
 "drucker": {"ok": true, "meldung": "…", "hinweis": ""},
 "drucker_name": "Citizen CL-S521", "transport": "usb",
 "vorschau": true, "produkte_bearbeiten": true, "verpackung": true}
```

`ok`/`meldung` sind das Statusmuster des Portals (Symbol auf der Kachel).

`produkte_bearbeiten = false` blendet den Reiter „Produkte“ aus (z. B. im Notbetrieb).

### `GET /produkte` und `GET /produkte?alle=1`

Liste von Kaffees (Datenmodell oben). Ohne `alle`: nur nicht archivierte Kaffees,
darin nur nicht archivierte Versionen, und nur Kaffees mit mindestens einer
aktiven Version. Mit `alle=1`: alles, für die Verwaltung.

### `GET /mhd?kaffee=ID&abgepackt=JJJJ-MM-TT`

`{"mhd": "2027-10-02"}`. Abpackdatum + `mhd_monate`. Gibt es den Tag im Zielmonat
nicht, wird der letzte Tag des Monats genommen (31.01. + 1 Monat = 28./29.02.).
`abgepackt` fehlt → heute.

### `POST /drucken`, `POST /zpl`, `POST /vorschau`

Eingabe:

```json
{"kaffee": "kolumbien", "version": "rewe", "mhd": "2027-10-02", "menge": 6}
```

- `version` darf fehlen, wenn der Kaffee genau eine aktive Version hat. Sonst `400`
  mit „bitte Version wählen (…)“.
- `mhd` fehlt → berechnet. Ein MHD in der Vergangenheit → `400`.
- `menge` 1–999, fehlt → 1.

Antworten: `/drucken` → `{"ok": true, "meldung": "6 Etikett(en) gedruckt – …"}`,
`/zpl` → `{"ok": true, "zpl": "^XA…"}`, `/vorschau` → PNG (immer ein Etikett).

### `POST /testdruck`

Testetikett zum Kalibrieren. `{"ok": true, "meldung": "…"}`.

### `POST /kaffees`

Neuen Kaffee anlegen. Eingabe wie das Datenmodell, ohne IDs:

```json
{"name": "Brasilien|Santos", "mhd_monate": 10,
 "versionen": [{"bezeichnung": "Edeka", "gtin": "2064000001908"}]}
```

Antwort: `{"ok": true, "kaffee": {…}}` mit vergebenen IDs.

### `PUT /kaffees/<id>`

Einen Kaffee komplett ersetzen (Name, Haltbarkeit, `archiviert`, Versionen).
Bestehende Versionen tragen ihre `id`, neue Versionen haben keine.

- Eine bestehende Version fehlt in der Liste → `400` („nur archiviert“).
- Eine unbekannte Versions-ID → `400`.

Antwort wie bei `POST /kaffees`.

## Verpackungsetikett

### `GET /verpackung/status`

Wie `GET /status`, aber für den Drucker der Verpackungsetiketten.

### `POST /verpackung/drucken`, `POST /verpackung/zpl`, `POST /verpackung/vorschau`

```json
{"kaffee": "kolumbien", "charge": "Rö261012-01", "mhd": "2027-10-12", "menge": 2}
```

- `charge` Pflicht, Format `RöJJMMTT-NN` (auch `Ro…`/`Roe…`, Groß/klein egal; auf dem
  Etikett steht immer `Rö…`). Das Röstdatum ist das Datum in der Charge, es darf
  nicht in der Zukunft liegen.
- `mhd` fehlt → Röstdatum + `mhd_monate` des Kaffees.
- Versionen spielen hier keine Rolle (kein Barcode).
- Antworten wie beim Produktetikett.

### `POST /verpackung/testdruck`

Testetikett in der Größe des Verpackungsetiketts.

## Noch nicht festgelegt

- **Anmeldung:** Lokal gibt es keine (nur `127.0.0.1`). Auf dem Firmenserver prüft
  tosto vor jeder Anfrage.
- **Druckagent für Drucker am Client-PC** (Verpackungsetiketten, tosto T8): Dann
  antwortet `POST /verpackung/drucken` mit einem Auftrag und seinem Status, statt
  sofort zu drucken. Wird hier ergänzt, sobald es gebaut wird.
