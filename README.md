# Etikettendruck

Druckt einfache Produktetiketten mit **Titel, EAN-13-Barcode und MHD** auf einem
Citizen-Etikettendrucker (Referenz: CL-S521, 57 × 32 mm).

Das Programm erzeugt **ZPL**, die Druckersprache des Druckers, und schickt sie
unverändert an den Drucker. Es gibt kein PDF, keinen Treiber und kein Rastern.
Text und Barcode erzeugt der Drucker selbst. Vorschau und Druck verwenden denselben
ZPL-Text. Warum das so gelöst ist, steht in [`assets/insights.md`](assets/insights.md)
und [`docs/ENTSCHEIDUNGEN.md`](docs/ENTSCHEIDUNGEN.md).

![Etikett](docs/beispiel-etikett.png)

- **Nur Python-Standardbibliothek.** Python ≥ 3.11 genügt, nichts muss per `pip`
  installiert werden.
- **Bedienung im Browser** in drei Schritten: Kaffee (und Version) wählen → Menge → Drucken.
- **Produkte im Browser pflegen:** Kaffees anlegen, Versionen mit eigener GTIN
  (z. B. Edeka und Rewe), archivieren.
- **MHD** wird aus Abpackdatum und Haltbarkeit des Produkts berechnet und lässt
  sich überschreiben.
- **Vorschau** über labelary.com ist optional. Fehlt das Internet, wird trotzdem
  gedruckt.
- **Druckprotokoll** in `var/druckprotokoll.csv`.

---

## Schnellstart (Linux Mint, Drucker per USB)

```sh
# 1. Einmalig: Schreibrecht auf den USB-Drucker, danach ab- und wieder anmelden
sudo usermod -aG lp $USER

# 2. Prüfen, ob alles passt
python3 -m etiketten check

# 3. Testetikett drucken: Rahmen, Umlaute, Barcode
python3 -m etiketten testdruck

# 4. Oberfläche starten (öffnet den Browser auf http://localhost:8077)
./start.sh
```

Optional legt `scripts/desktop-verknuepfung.sh` einen Eintrag „Etikettendruck“
im Startmenü an.

> **Stand 06.10.2026:** Am echten CL-S521 getestet, Druck über USB und
> Weboberfläche funktioniert. **Offene Punkte** (u. a. Barcode am Kassenscanner
> prüfen, Haltbarkeiten eintragen) stehen in
> [`docs/ENTSCHEIDUNGEN.md`](docs/ENTSCHEIDUNGEN.md#offene-punkte).

## Bedienung

1. **Kaffee** antippen. Hat er mehrere Versionen (z. B. Edeka und Rewe), darunter
   die **Version** wählen.
2. **Abgepackt am** ist heute. Das **MHD** wird daraus berechnet
   (Haltbarkeit des Kaffees). Ein MHD von Hand ändern ist möglich, dann
   steht dort „manuell“. „wieder berechnen“ schaltet zurück.
3. **Anzahl** wählen und **Drucken** drücken. Ab 50 Etiketten wird nachgefragt.

Unter **Werkzeuge** gibt es das Testetikett und den erzeugten ZPL-Text.
Ein Direktlink geht so: `http://localhost:8077/?kaffee=kolumbien&version=edeka`.

## Produkte pflegen

Im Reiter **Produkte** oben in der Oberfläche:

- **+ Neuer Kaffee:** Name, Haltbarkeit in Monaten und mindestens eine Version.
- **Version:** eine Bezeichnung (frei, z. B. „Edeka“, „Rewe 1 kg“) und die GTIN
  (EAN-13). Die Prüfziffer wird schon beim Tippen geprüft. Bei 12 Ziffern zeigt
  das Feld die passende 13. an. Jede GTIN darf nur einmal vorkommen.
- **Layout** ist zurzeit immer „Standard“. Später lassen sich darüber andere
  Etikett-Designs pro Version wählen.
- **Name:** `|` erzwingt einen Zeilenumbruch auf dem Etikett (`Espresso|Guatemala`),
  sonst bricht das Programm selbst um (max. 2 Zeilen, die Schrift wird bei Bedarf kleiner).
- **Löschen gibt es nicht**, nur **archivieren** (Kaffee oder einzelne Version). Archiviertes
  wird nicht mehr zum Drucken angeboten, bleibt aber im Druckprotokoll lesbar.

Gespeichert wird in [`data/produkte.json`](data/produkte.json). Die Datei lässt
sich auch von Hand bearbeiten (Aufbau in [`docs/API.md`](docs/API.md#datenmodell)),
Änderungen gelten ohne Neustart. `python3 -m etiketten check` prüft sie.
Die sechs Kaffees und EANs stammen aus `assets/Edeka Barcodes.svg` und sind als
Version „Edeka“ angelegt. **Die 12 Monate Haltbarkeit sind ein Platzhalter. Bitte prüfen.**

Mit `produkte_bearbeiten = false` in `config.toml` ist der Reiter ausgeblendet
und die Liste nur lesbar (gedacht für den Notbetrieb).

## Konfiguration

Alles Einstellbare steht kommentiert in [`config.toml`](config.toml): Druckweg,
Etikettengröße, Kalibrierung, Layout in Millimetern, Zeichensatz und Vorschau.
Eine andere Datei lässt sich mit `--config pfad` oder `ETIKETTEN_CONFIG=pfad` verwenden.

**Kalibrieren:** Testetikett drucken. Der Rahmen sollte überall 2 mm Abstand
zum Rand haben. Falls nicht, `versatz_x` / `versatz_y` unter `[etikett]` in mm
anpassen (positiv = nach rechts/unten).

**Trockenlauf ohne Drucker:** `transport = "datei"` schreibt jede Sendung als
`.zpl`-Datei nach `var/ausgabe/`.

## Kommandozeile

```sh
python3 -m etiketten start [--port 8077] [--host 0.0.0.0] [--kein-browser]
python3 -m etiketten produkte [--alle]                         # Kaffees mit Versionen
python3 -m etiketten check
python3 -m etiketten testdruck
python3 -m etiketten zpl kolumbien --mhd 02.10.2027 --menge 3   # nur ausgeben
python3 -m etiketten drucken kolumbien --menge 12              # MHD berechnet
python3 -m etiketten drucken espresso-guatemala --version rewe # bei mehreren Versionen
```

## Projektstruktur

```
etiketten/
  zpl.py        Layout → ZPL (die einzige Stelle, an der das Etikett entsteht)
  drucker.py    Druckwege: usb, cups, tcp, datei
  dienst.py     verbindet Produkte, MHD, ZPL, Druckweg, Vorschau, Protokoll
  server.py     Weboberfläche + JSON-API
  cli.py        Kommandozeile
  produkte.py   Kaffees und Versionen: lesen, prüfen (EAN), speichern
  mhd.py        Datumsrechnung
  config.py     config.toml laden
  static/       Oberfläche ohne Build-Schritt: Web Component <etiketten-app>
                (etiketten-app.js/.css), index.html bindet es ein
data/produkte.json
config.toml
docs/           Architektur, Drucker-Einrichtung, Entscheidungen
fragen/         Fragenkataloge (Druckprogramm, Etikettenkonzept)
assets/         alte SVG-Vorlage und Erkenntnisse aus dem ersten Versuch
tests/
```

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

## Weitere Dokumentation

- [`docs/DRUCKER.md`](docs/DRUCKER.md): Drucker einrichten, Emulation, CUPS, Fehlersuche
- [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md): Aufbau, Einbindung in andere Seiten, Erweiterung (Raspberry Pi, Enterprise-System)
- [`docs/API.md`](docs/API.md): HTTP-API und Datenmodell, der Vertrag für jeden Server (lokal und TOSTO)
- [`docs/ENTSCHEIDUNGEN.md`](docs/ENTSCHEIDUNGEN.md): getroffene Entscheidungen und offene Punkte
