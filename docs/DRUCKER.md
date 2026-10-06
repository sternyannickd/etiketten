# Drucker einrichten & Fehlersuche

Referenzgerät: **Citizen CL-S521** (203 dpi), per USB an einem Linux-Mint-Rechner.

## 1. Was am Rechner gefunden wurde

`python3 -m etiketten check` listet alle USB-Drucker mit ihrer Kennung. Bei
der Einrichtung am 02.10.2026 sah das so aus:

```
/dev/usb/lp1  MFG:SII;…;MDL:SLP620;…                       ← Seiko Smart Label Printer (nicht unserer)
/dev/usb/lp2  MANUFACTURER:CITIZEN;COMMAND SET:DMI,DM4,DPP;MODEL:CL-S521;…;ACTIVE COMMAND:DMI;
```

Die Nummer `lp1`/`lp2` kann sich nach einem Neustart oder Umstecken ändern.
Deshalb sucht das Programm standardmäßig (`usb_geraet = "auto"`) das Gerät,
dessen Kennung `CITIZEN` enthält.

## 2. Schreibrechte (einmalig)

`/dev/usb/lp*` gehört der Gruppe `lp`. Damit das Programm ohne `sudo` drucken
kann:

```sh
sudo usermod -aG lp $USER
```

Danach **ab- und wieder anmelden** (oder neu starten). Kontrolle: `groups`
muss `lp` enthalten.

## 3. ⚠️ Druckersprache (Emulation)

Am 02.10.2026 meldete der Drucker `ACTIVE COMMAND:DMI`, also die
**Datamax-Emulation**, nicht ZPL. Seit dem 06.10.2026 meldet er sich als
`CL-S521Z` mit `ACTIVE COMMAND:Z2` (Zebra, ZPL II) und druckt einwandfrei.
`check` warnt nur noch, wenn wieder Datamax aktiv ist. Citizen-Etikettendrucker können je nach Modell und Firmware zwischen Datamax
und Zebra (ZPL) umschalten, manche erkennen die Sprache auch automatisch.

**Test:** `python3 -m etiketten testdruck`

| Ergebnis | Bedeutung / nächster Schritt |
|----------|------------------------------|
| Testetikett mit Rahmen, Text und Barcode | ZPL wird verstanden. Weiter mit 4. |
| Nichts passiert, oder `^XA…` wird als Text gedruckt | Drucker steht auf Datamax. Emulation auf **Zebra** bzw. **Auto** umstellen: über das Bedienfeld bzw. Einstellmenü des Druckers oder mit dem Citizen-Einstellprogramm. Die genaue Tastenfolge steht in der Bedienungsanleitung des CL-S521 unter „Emulation“ bzw. „Command mode“. Danach Drucker aus- und einschalten und neu testen. |
| Viele leere Etiketten / Vorschub ohne Ende | Etikettensensor nicht kalibriert. Kalibrierung laut Anleitung durchführen (meist Taste beim Einschalten gedrückt halten). |

Falls der Drucker sich dauerhaft nicht auf ZPL stellen lässt: Die Architektur
erlaubt, `zpl.py` durch einen Erzeuger für Datamax (DPL) zu ergänzen. Oberfläche
und Druckwege bleiben gleich. Das wäre aber ein eigener Arbeitsschritt.

## 4. Testetikett auswerten

- **Rahmen:** soll ringsum ca. 2 mm vom Etikettenrand entfernt sein. Sonst in
  `config.toml` → `[etikett]` `versatz_x` / `versatz_y` (mm) anpassen.
- **Umlaute:** „Größe Äthiopien Café“ müssen korrekt erscheinen. Sonst
  `zeichensatz = "latin1"` probieren und neu testen.
- **Barcode:** mit dem Kassenscanner **und** einer Handy-App scannen.
  Ist der Barcode zu breit oder zu schmal: `[layout.barcode] modul`
  (3 = 0,375 mm pro Strich, Standard; 2 = 0,25 mm ist unter der
  Handels-Mindestgröße).
- **Schwärzung:** zu blass oder verlaufen → `schwaerzung` (−30…30) unter
  `[drucker]` setzen.

## 5. Alternative: über CUPS

Falls direktes USB-Schreiben nicht gewünscht ist (z. B. weil CUPS den Drucker
schon verwaltet), eine **Raw-Warteschlange** anlegen. Die reicht die Daten
unverändert durch:

```sh
lpinfo -v | grep -i citizen          # USB-Adresse herausfinden, z. B. usb://CITIZEN/CL-S521?serial=…
sudo lpadmin -p Citizen_CL_S521_raw -E -v 'usb://CITIZEN/CL-S521?serial=…' -m raw
```

Danach in `config.toml`: `transport = "cups"`. (`-m raw` gilt in neueren
CUPS-Versionen als veraltet, funktioniert unter Linux Mint 22 aber noch. Eine
Warnung beim Anlegen ist normal.)

Keinen Citizen-Treiber bzw. keine PPD für diese Warteschlange verwenden. Genau
diese Umwandlung hat beim alten PDF-Weg die Probleme verursacht.

## 6. Später: Netzwerk

Bekommt der Drucker eine Netzwerkschnittstelle, genügt in `config.toml`:

```toml
transport = "tcp"
tcp_host = "192.168.x.y"
```

Dann gehen die Daten an Port 9100, ohne Treiber und auf jedem Betriebssystem gleich.

## Fehlersuche

| Meldung | Lösung |
|---------|--------|
| „Keine Schreibrechte auf /dev/usb/lpX“ | Abschnitt 2 |
| „Kein USB-Drucker mit Kennung 'CITIZEN' gefunden“ | Drucker an? USB-Kabel? `ls /dev/usb/` |
| Druck „ok“, aber nichts kommt heraus | Abschnitt 3 (Emulation) |
| Etikett verschoben | Abschnitt 4, Versatz |
| Vorschau „nicht verfügbar“ | Kein Internet oder labelary.com nicht erreichbar. Drucken geht trotzdem. Abschalten mit `[vorschau] aktiv = false`. |
| „Server konnte nicht starten … Address already in use“ | Programm läuft schon (Browser auf http://localhost:8077), oder `--port` ändern |
