# Entscheidungen & offene Punkte

Grundlage: [`fragen/01-druckprogramm.md`](../fragen/01-druckprogramm.md)
(ausgefüllt am 02.10.2026) und [`assets/insights.md`](../assets/insights.md).

## Entschieden

| # | Thema | Entscheidung |
|---|-------|--------------|
| A1 | Druckersprache | ZPL, an den Drucker unverändert gesendet. Kein PDF, kein Treiber. |
| A2 | Drucker | CL-S521 (203 dpi) als Referenz. Layout in mm, dpi einstellbar. |
| A3 | Plattform | Browser-Oberfläche + kleiner Druckdienst. Läuft zunächst auf dem Linux-Mint-Rechner am Drucker und kann später ohne Codeänderung auf einen Pi oder anderen Rechner umziehen. |
| A4 | Anschluss | USB. Direkt auf `/dev/usb/lp*` (automatisch gefunden), CUPS-raw als Alternative. |
| A5 | Alte App | Neu angefangen. Übernommen wurden nur die Produkte/EANs und das Layout aus der SVG. |
| B1/B2 | Barcode | EAN-13 nativ vom Drucker (`^BE`). Die Nummern sind die vom Supermarkt vorgegebenen (siehe offene Punkte). |
| B3 | Inhalt | Für diese Version nur Titel, Barcode, MHD. |
| B4 | MHD | Berechnet aus Abpackdatum + `mhd_monate`, manuell überschreibbar. |
| B5 | MHD-Text | `MHD: 02.10.2027`, eine Zeile, senkrecht am rechten Rand. Die zweizeilige Variante ist per `einzeilig = false` umschaltbar. |
| B7 | Name | Max. 2 Zeilen, Schrift wird kleiner, `|` erzwingt einen Umbruch. UTF-8 (`^CI28`), `latin1` als Ausweichlösung. |
| C1 | Material | Das vorhandene Material wird verwendet. |
| C2/C3 | Größe | 57 × 32 mm, 2 mm Rand, Kalibrierung per Versatz. |
| C4 | Schrift | Druckerschrift `^A0`, keine eigenen Schriften. |
| D2 | Vorschau | labelary.com, optional. Fällt sie aus, wird trotzdem gedruckt. |
| D3 | Protokoll | CSV in `var/druckprotokoll.csv`. Fehler beim Protokollieren verhindern nie den Druck. |
| D4 | Daten | ~~`data/produkte.csv`~~, seit 0.3 `data/produkte.json` (siehe F3). |
| D5 | Drucker | einer. |
| E1 | Technik | Python ≥ 3.11, nur Standardbibliothek, Oberfläche ohne Build-Schritt. |
| E2 | Vorgehen | Alles auf einmal gebaut, Test direkt am Drucker. |
| F1 | Portal | Die App läuft im Portal **tosto** und soll später auch in die Website des Chefs passen. Dafür ist die Oberfläche ein Web Component mit API-Adresse als Attribut und Design über CSS-Variablen (08.10.2026). Seit 12.10.2026: tosto läuft auf dem **Firmenserver** (AlmaLinux, Podman), labels dort als **Python-Dienst** hinter tosto, Drucker 1 per USB am Server. Kein PHP mehr. Vorgaben: `../tosto/KONVENTIONEN.md`, Austausch über `TOSTO.md`. |
| F2 | Daten | Die Daten liegen auf dem Firmenserver (JSON-Dateien im Datenordner von tosto). |
| F3 | Produkte | Kaffee (Name, Haltbarkeit **pro Kaffee**) mit beliebig vielen **frei benennbaren Versionen** (Bezeichnung, GTIN, Layout). Pflege im Browser. Archivieren statt Löschen. Jede GTIN nur einmal. |
| F4 | Notbetrieb | Die lokale Python-Oberfläche bleibt erhalten, falls Internet oder Website ausfallen, und wird mit denselben Änderungen weiterentwickelt. Beide Server erfüllen dieselbe API ([API.md](API.md)). |
| F5 | Drucken über die Website | Drucker 1 hängt am Server, labels druckt dort direkt (keine Warteschlange). Nur für Drucker an Client-PCs (Verpackung, F7) kommt ein Druckagent, Vorschlag in `../tosto/schnittstelle/labels.md`. Noch nicht gebaut. |
| F6 | Entwicklermodus | Es gibt immer eine lokal startbare Entwicklerversion: `python -m etiketten dev`, Testdaten, druckt in Dateien, Design aus dem tosto-Rahmen (12.10.2026). |
| F7 | Verpackungsetikett | Zweite Etikettenart **in labels** (gleiche Produktliste), eigene Seite und eigenes Component `<verpackung-app>`. Inhalt: Name, Info (pro Kaffee), Röstdatum, Charge, MHD, QR-Code. Zurzeit 100 × 150 mm (Rolle des Versanddruckers), Layout in `config.toml` anpassbar. Drucker: ebenfalls Citizen CL-S521, an einem Client-PC mit Linux Mint (12.10.2026). |
| F8 | Charge | Format `RöJJMMTT-NN`, das Röstdatum steckt darin. Im Prototyp ein Eingabefeld, später Auswahl der verfügbaren Chargen des Kaffees. MHD = Röstdatum + Haltbarkeit des Kaffees. QR-Code führt auf eine feste Adresse (12.10.2026). |

Zusätzlich entschieden (ohne Rückfrage, leicht änderbar):

- **Barcode-Modulbreite 3 Punkte (0,375 mm).** 2 Punkte (0,25 mm) wären schmaler
  als die im Handel übliche Mindestgröße (ca. 0,26 mm). In der alten SVG lag der
  Wert bei ca. 0,30 mm, was ein 203-dpi-Drucker gar nicht exakt drucken kann.
- **Abpackdatum** statt „heute“ als Ausgangspunkt fürs MHD, Standardwert heute.
- **Rückfrage ab 50 Etiketten**, gegen Vertipper.
- **MHD in der Vergangenheit** wird abgelehnt.
- **Keine Anmeldung** in der Oberfläche, da der Dienst nur lokal läuft (`127.0.0.1`).

## Offene Punkte

Stand nach dem ersten Test am echten Drucker (06.10.2026).

**Erledigt:**

- ~~Emulation~~: Der CL-S521 meldet inzwischen `ACTIVE COMMAND:Z2` (Zebra, ZPL II)
  und druckt ZPL einwandfrei. Testetikett, Kolumbien-Etikett und 3 × Stern Espresso
  über die Weboberfläche sind korrekt herausgekommen.
- ~~Umlaute~~: „Größe Äthiopien Café“ auf dem Testetikett korrekt (`zeichensatz = "utf8"`).
- ~~Druckrechte~~: Benutzer ist in der Gruppe `lp`, direkter USB-Druck funktioniert.

**Noch offen:**

1. **Barcode scannen** mit dem Kassenscanner des Supermarkts und mit einer Handy-App.
   Der wichtigste offene Test.
2. **Haltbarkeit pro Kaffee:** Überall stehen 12 Monate als Platzhalter (im Reiter Produkte ändern).
3. **Herkunft der EANs:** Alle Nummern beginnen mit **2**. Dieser Bereich ist für
   händler- bzw. firmeninterne Nummern reserviert. Die Nummern gelten also
   vermutlich **nur bei diesem Supermarkt** (Edeka). Für weitere Händler braucht ihr
   eigene GTINs von GS1 Germany. Auffällig ist außerdem, dass es zwei Nummernkreise gibt
   (`2064200…` und `2064000…`). Möglicherweise steht das für zwei Größen oder Sortimente.
   Beim Supermarkt nachfragen.
4. **Thermodirekt-Material** verblasst unter Umständen vor Ablauf von 12 Monaten MHD.
   Ein Etikett ein paar Wochen ans Fenster kleben und beobachten.
5. *(Optional)* **Versatz:** Der Rahmen des Testetiketts sitzt links fast am Rand,
   rechts ca. 5 mm entfernt. Produktetiketten sehen trotzdem gut aus. Wer es mittig
   will: `versatz_x = 2` unter `[etikett]` in `config.toml`.
6. *(Optional)* **Aussehen wie das alte Muster:** zweispaltiges MHD
   („Mindesthaltbarkeit:“ + Datum, `einzeilig = false`) und gepunktete Trennlinie.
   Das aktuelle einzeilige `MHD: TT.MM.JJJJ` wurde beim Test für gut befunden.

**Offen für tosto:**

7. ~~Wer baut die Server-Seite (PHP)?~~ Entfällt: labels läuft selbst als Python-Dienst auf dem Server.
8. **Notbetrieb abgleichen:** Wie die lokale Produktliste vom Server aktualisiert wird
   (z. B. beim Start holen, dann `produkte_bearbeiten = false`).
9. ~~App-Name~~: **Etiketta** (12.10.2026). Seiten „Edeka Etiketten“ und „Probeetikett Verpackung“. Technische Namen (Paket `etiketten`, `<etiketten-app>`, API) bleiben.

**Offen für das Verpackungsetikett:**

10. ~~QR-Adresse~~: `https://stern-kaffee.de`, mit dem Handy getestet (12.10.2026).
11. **Chargen** pro Kaffee zur Auswahl anbieten statt Eingabefeld. Woher kommen sie
    (Röstprotokoll, Artisan, roast-archive)?
12. **Pflichtangaben** für verkaufte Ware (Nettofüllmenge, Anschrift, ggf. Los = Charge)
    und **endgültige Etikettengröße** mit dem künftigen Drucker.
13. **Info** pro Kaffee eintragen (Reiter Produkte). Stern Espresso hat sie seit 12.10.2026
    (Überschrift mit `#`, Fließtext 3,4 mm, passt ohne Kürzen).
14. **Aussehen:** Zwei Entwürfe in `docs/entwuerfe/` (A: Rahmen und Stern-Ornament,
    B: schwarzes Band). Auswahl steht aus. Eigene Schrift nur als Grafik möglich,
    der Drucker hat nur eine skalierbare Schrift.
15. **Windows-Versanddruck** nach der automatischen Umschaltung auf ZPL prüfen
    (`docs/DRUCKER.md` Abschnitt 3a).

## Für künftige Versionen / das Etikettenkonzept

- **Röstdatum muss auf komplexere Etiketten** (Antwort B6).
- Pflichtangaben (LMIV) für den Verkauf: Bezeichnung, Nettofüllmenge,
  Hersteller-Anschrift, ggf. Los. Siehe `fragen/02-etikettenkonzept.md`.
- QR-Code zur Website: ZPL kann ihn nativ (`^BQ`).
