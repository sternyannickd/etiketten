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

## 5a. Windows

Unter Windows geht die ZPL als Rohdaten (`RAW`) über die Windows-Druckwarteschlange.
Einrichtung siehe [INSTALLATION.md](INSTALLATION.md#drucker-unter-windows-einrichten).

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
| Zwei Aufträge auf einem Etikett, Drucker zieht das Etikett zurück und druckt Unsinn | Etikettensensor erkennt die Lücke nicht, siehe Abschnitt 7 |

## 7. Etikettensensor (Lücke wird nicht erkannt)

**Erfahrung vom 12.11.2026.** Zuerst lief alles normal, dann kamen Aufträge nur noch
teilweise richtig heraus. Der Drucker zog das Etikett zurück und druckte darüber,
sodass zwei Aufträge auf einem Etikett landeten (z. B. Kolumbien + Nicaragua). Das
betraf alle Sorten gleich. Der ZPL-Code war bei allen Sorten korrekt.

Ursache ist der Sensor des Druckers. Im Abreißmodus (`Function Select: Tear`) schiebt
der Drucker nach jedem Auftrag vor und vor dem nächsten wieder zurück. Dabei muss er
jedes Mal die Lücke finden. Gelingt das nicht, druckt er an der falschen Stelle.
Ein einzelner Auftrag mit mehreren Etiketten (`^PQ`) ist weniger anfällig, aber nicht
sicher.

**Diagnose vom Rechner aus** (Antwort kommt über dieselbe USB-Gerätedatei):

```sh
python3 - <<'PY'
import os, time
fd = os.open("/dev/usb/lp2", os.O_RDWR | os.O_NONBLOCK)
os.write(fd, b"~HS\r\n^XA^HH^XZ\r\n")   # Status + Konfiguration
time.sleep(3); print(os.read(fd, 16384).decode("latin1"))
PY
```

Wichtig sind `Media Sensor`, `Sensor Level` (Schaltschwelle) und `Sensor Monitor`
(aktueller Messwert). Gemessen wurde **0,70–0,77 V bei einer Schwelle von 0,7 V**. Der
Sensor sah also kaum einen Unterschied zwischen Etikett und Lücke. `~JC`
(Zebra-Kalibrierung) wird vom CL-S521 ignoriert.

**Die Etiketten haben schwarze Markierungen auf dem Trägerpapier.** Es gibt zwei
Sensorarten:

- **See Through (Durchlicht, Werkseinstellung):** misst die Lücke. Der Sensor muss
  **mittig unter dem Etikett** sitzen, **nicht auf der Spur der schwarzen Striche**.
  Diese blockieren das Licht und verwirren den Sensor.
- **Reflect (Reflex):** misst die schwarzen Striche. Die weiße Markierung des unteren
  Sensors muss **mittig auf der Spur der schwarzen Striche** liegen.

In beiden Fällen müssen die weißen Markierungen von oberem und unterem Sensor
übereinander stehen (Ausrichtung über die bewegliche Papierführung).

**Kalibrieren am Drucker** (Handbuch CL-S521, Kapitel 3, S. 39–41):

1. Einschalten mit **PAUSE + FEED + STOP** gedrückt, loslassen, wenn PRINT und
   CONDITION leuchten.
2. Sensorart prüfen: PRINT-LED **dauerhaft an = See Through**, **langsam blinkend =
   Reflect**. Umschalten mit **MODE/REPEAT halten + STOP**. Vorsicht, das passiert
   auch leicht aus Versehen.
3. Papier:
   - See Through: nur **Trägerpapier** (ca. 20 cm Etiketten abziehen). Weder Lücke
     noch schwarzer Strich darf beim Einlauf am Sensor vorbeikommen.
   - Reflect: normale Rolle. Über dem Sensor liegt weder Strich noch Lücke.
4. **MODE/REPEAT halten + PAUSE** drücken, das Papier läuft.
5. LEDs wieder normal = erfolgreich, mit **STOP** speichern. **CONDITION und ERROR
   blinken = „adjustment impossible“**: Sensorposition und Papier prüfen.
6. Probe: **FEED** muss genau ein Etikett vorschieben.

Falls die automatische Einstellung nie gelingt, nennt das Handbuch (S. 46) als letzten
Weg, den `Sensor Level` im Menü „System Setup“ von Hand zu setzen.

### Lösung (19.11.2026)

Die Rolle **N11354** (57 × 32 mm, **10 mm Lücke**, Trägerpapier 60 mm) hat auf der
Rückseite **4 schwarze Striche pro Etikett** etwa 9 mm vom Rand und ein Loch pro
Etikett am Rand. Die Striche sind **keine** Etikettenmarke. Mit „Reflect“ sieht der
Drucker 4 Etikettenanfänge pro Etikett. Mit „See Through“ auf der Strichspur
(Sensor stand 11 mm vom Rand) verwischt der Unterschied.

Richtig ist:

1. **See Through**, Sensor **mittig unter dem Etikett** (Pfeilspitze ca. 28–30 mm
   vom Rand, oben und unten übereinander).
2. **Sensor Level (Schwelle) zwischen den Messwerten.** Gemessen bei mittigem Sensor:
   **Etikett 0,69 V, Lücke 2,17 V**. Eingestellt war 0,7 V, also genau auf dem
   Etikett-Wert. Die Tastenkalibrierung hat die Schwelle nie geändert, `^SS` und `~JC`
   ignoriert der CL-S521. Gelöst durch **Zurücksetzen auf Werkseinstellung**, die
   Schwelle ist dann **1,5 V**. Danach liefert FEED zuverlässig genau ein Etikett, und
   6 Einzelaufträge plus ein 3er-Auftrag kamen sauber und deckungsgleich heraus.

**Werkseinstellung beim CL-S521 (ohne Display):** Drucker aus, **MODE/REPEAT
halten und einschalten**. Der Drucker druckt „Reset this printer? YES = PAUSE,
NO = STOP“, also **PAUSE** drücken, bei der Rückfrage noch einmal **PAUSE**. Danach aus
und wieder ein. Das Menü druckt jede Frage auf ein Etikett. **STOP** heißt dort
„Nein/weiter“, **MODE/REPEAT** verlässt das Menü. Druckersprache (Z2), Sensorart
und Etikettenlänge bleiben bzw. werden vom Programm mit jedem Druck gesetzt.

**Messen ohne Papierverbrauch:** Druckkopf öffnen, Etikett bzw. Lücke über den
Sensor legen, schließen und `Sensor Monitor` per `^HH` auslesen (siehe oben).
Die Schwelle muss deutlich zwischen beiden Werten liegen.

**Vorsicht bei eigenen Tests:** Wegen `AutoConfigure: On` speichert der Drucker
`^MN…` und `^LL…` aus jedem Auftrag dauerhaft. Ein Test mit `^MNN` (Endlospapier)
stellt den Drucker also auf „None“ um. Das Programm setzt beim nächsten Druck
wieder `^MNY`.
