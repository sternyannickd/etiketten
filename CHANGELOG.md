# Änderungen

## Unveröffentlicht

- **Sicherheit:** Eine fremde Webseite, die im Browser am Druckrechner geöffnet
  ist, konnte unbemerkt Druckaufträge an `localhost:8077` schicken. Der Server
  nimmt POST jetzt nur noch als `application/json` und ohne fremden `Origin` an
  und lehnt unbekannte Hostnamen ab (Schutz gegen DNS-Rebinding). Neue Option
  `[server] erlaubte_namen` für den Zugriff über einen Rechnernamen im Netz.

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
