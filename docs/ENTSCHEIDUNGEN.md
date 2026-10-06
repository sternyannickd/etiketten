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
| D4 | Daten | `data/produkte.csv`. |
| D5 | Drucker | einer. |
| E1 | Technik | Python ≥ 3.11, nur Standardbibliothek, Oberfläche ohne Build-Schritt. |
| E2 | Vorgehen | Alles auf einmal gebaut, Test direkt am Drucker. |

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
2. **Haltbarkeit pro Produkt:** In der CSV stehen überall 12 Monate als Platzhalter.
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

## Für künftige Versionen / das Etikettenkonzept

- **Röstdatum muss auf komplexere Etiketten** (Antwort B6).
- Pflichtangaben (LMIV) für den Verkauf: Bezeichnung, Nettofüllmenge,
  Hersteller-Anschrift, ggf. Los. Siehe `fragen/02-etikettenkonzept.md`.
- QR-Code zur Website: ZPL kann ihn nativ (`^BQ`).
