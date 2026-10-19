# Änderungen

## Unveröffentlicht

- **Sicherheit:** Eine fremde Webseite, die im Browser am Druckrechner geöffnet
  ist, konnte unbemerkt Druckaufträge an `localhost:8077` schicken. Der Server
  nimmt POST/PUT jetzt nur noch als `application/json` und ohne fremden `Origin`
  an und lehnt unbekannte Hostnamen ab (Schutz gegen DNS-Rebinding). Neue Option
  `[server] erlaubte_namen`: dort den Rechnernamen im Netz bzw. **den Namen des
  Portals tosto** eintragen, wenn labels hinter tosto läuft.
- Name der App: **Etiketta**. Kopfzeile der lokalen Seiten mit „Edeka Etiketten“ (`/`)
  und „Probeetikett Verpackung“ (`/verpackung`).
- Erster Druck auf dem Drucker für Verpackungsetiketten (100 × 150 mm): Testetikett
  und Probeetikett Stern Espresso. Der Drucker schaltet beim ersten ZPL-Auftrag selbst
  von Datamax auf Zebra um, siehe `docs/DRUCKER.md` Abschnitt 3a.
- Fehler behoben: `testdruck --verpackung` brach ab (kein Barcode im Layout).
- Info fürs Verpackungsetikett: bis 600 Zeichen, `#` am Zeilenanfang = Überschrift
  (`ueberschrift_schrift`), `||` = Leerzeile. Fließtext jetzt 3,4 mm.
- Info für Stern Espresso eingetragen.
- `qr_adresse` jetzt `https://stern-kaffee.de`.
- Verpackungsetikett in drei **Gestaltungen**: Schlicht, Klassisch (Rahmen, Stern)
  und Banner (schwarzes Band), umschaltbar in der Oberfläche. API-Feld `stil`,
  Kommandozeile `--stil`, Voreinstellung `stil` und `kopfzeile` unter `[verpackung]`.
  Entwürfe dazu in `docs/entwuerfe/`.
- `.claude/settings.json`: war kein gültiges JSON (Windows-Pfad). Jetzt `../tosto`,
  Hook läuft unter Linux (`python3`) und Windows (`python`).

- **Verpackungsetikett** als zweite Etikettenart (Seite `/verpackung`, Component
  `<verpackung-app>`): Name, Info, Röstdatum, Charge (`RöJJMMTT-NN`), MHD und QR-Code,
  zurzeit 100 × 150 mm. Eigene Größe, eigenes Layout und eigener Drucker unter
  `[verpackung]` in `config.toml`. API unter `/api/verpackung/…`, Kommandozeile
  `verpackung` und `testdruck --verpackung`, eigenes Protokoll.
- Kaffee hat ein optionales Feld **`info`** (Reiter Produkte).
- **Entwicklermodus** `python -m etiketten dev`: Testdaten in `var/dev/`, druckt in
  Dateien, übernimmt das Design aus `../tosto/rahmen/theme.css`.
- `config.lokal.toml` für Einstellungen nur eines Rechners (nicht im Git).
- `GET /api/status` liefert zusätzlich `ok` und `meldung` (Konvention von tosto).
- Oberfläche schickt das CSRF-Token der einbindenden Seite mit und meldet
  abgelaufene Sitzungen (401) verständlich.
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
