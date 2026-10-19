# Installation als fertiges Programm (Windows und Linux)

Im Ordner [`installer/`](../installer/) liegen zwei Installer. Beide installieren
**ohne Adminrechte** nur für den angemeldeten Benutzer. Python muss nicht
installiert sein.

| System | Datei | So starten |
|--------|-------|------------|
| Windows 10/11 (64 Bit) | `Etikettendruck-Installer-Windows.exe` | Doppelklick |
| Linux (Mint 21 oder neuer, 64 Bit) | `Etikettendruck-Installer-Linux.sh` | Doppelklick → „Ausführen“ |

Danach öffnet sich der Etikettendruck im Browser. Künftig startet man ihn über
das Startmenü oder das Symbol **Etikettendruck** auf dem Schreibtisch.

`installer/STAND.txt` zeigt, aus welchem Commit die Installer gebaut wurden.

## Bedienung

Wie in der [README](../README.md#bedienung) beschrieben, dazu:

- **+ Neues Produkt:** Name, EAN und Haltbarkeit eintragen. Die EAN wird schon
  beim Tippen geprüft, ein Zahlendreher fällt über die Prüfziffer auf.
- **Gewähltes Produkt bearbeiten:** Name, EAN, Haltbarkeit ändern oder das
  Produkt löschen.
- **Werkzeuge → Datenordner öffnen:** zeigt Produktliste, Druckprotokoll und
  Einstellungen im Dateimanager.
- **Werkzeuge → Programm beenden.** Ohne Beenden läuft das Programm unsichtbar
  weiter. Das schadet nicht: Ein erneuter Doppelklick öffnet einfach wieder den
  Browser.

## Wo liegt was?

| | Windows | Linux |
|-|---------|-------|
| Programm (wird bei jedem Update ersetzt) | `%LOCALAPPDATA%\Programs\Etikettendruck` | `~/.local/opt/etikettendruck` |
| **Eigene Daten** (bleiben immer erhalten) | `%LOCALAPPDATA%\Etikettendruck` | `~/.local/share/etikettendruck` |

Im Datenordner:

```
config.toml              eigene Einstellungen für diesen Rechner (anfangs alles auskommentiert)
data/produkte.csv        die Produktliste
data/produkte.csv.bak    Stand vor der letzten Änderung
var/druckprotokoll.csv   jeder Druck mit Zeitpunkt, Produkt, MHD, Menge
var/etikettendruck.log   Meldungen des Programms (für die Fehlersuche)
```

Das Programm legt fehlende Ordner und Dateien bei jedem Start selbst an.
Damit nichts kaputtgehen kann, gilt außerdem:

- Die Produktliste wird **nur beim allerersten Start** aus dem Repo kopiert
  (`data/produkte.csv`). Danach gilt ausschließlich die eigene Liste. Updates
  ändern sie nie.
- Gespeichert wird erst in eine Zwischendatei, die dann in einem Schritt die
  alte ersetzt. Ein Absturz mittendrin hinterlässt keine halbe Datei, und der
  vorige Stand liegt als `produkte.csv.bak` daneben.
- Eine beschädigte `config.toml` wird beiseitegelegt
  (`config.toml.defekt-<Datum>`) und neu angelegt. Die Oberfläche zeigt dann
  einen Hinweis.
- Löscht man `produkte.csv`, kommt beim nächsten Start wieder die Startliste.

## Update

1. Im Repo `git pull`.
2. Den Installer erneut doppelklicken.

Das laufende Programm wird dabei beendet, ersetzt und neu gestartet. Eigene
Produkte, Einstellungen und das Protokoll bleiben erhalten.

**Was mit einem Update ankommt:** alles am Programm, also Oberfläche, Layout,
Druckwege und die Grundeinstellungen aus der `config.toml` im Repo. Ausnahme ist
alles, was im lokalen `config.toml` eines Rechners ausdrücklich anders gesetzt ist.
**Was nicht ankommt:** Änderungen an `data/produkte.csv` im Repo. Die gelten nur
für Neuinstallationen. Ein bestehender Rechner pflegt seine Produkte selbst.

## Deinstallieren

- **Windows:** Einstellungen → Apps → Etikettendruck → Deinstallieren.
- **Linux:** `~/.local/opt/etikettendruck/deinstallieren.sh` ausführen.

Der Datenordner bleibt in beiden Fällen stehen. Wer ihn nicht mehr braucht,
löscht ihn von Hand.

## Drucker unter Windows einrichten

Unter Windows schickt das Programm die ZPL über die Windows-Druckwarteschlange,
und zwar als Rohdaten (Datentyp `RAW`). Windows reicht sie dann unverändert an
den Drucker durch, der Treiber rastert nichts. Dafür muss der Citizen einmal
unter Windows als Drucker eingerichtet sein:

1. Drucker per USB anschließen und einschalten. Windows richtet ihn oft von
   selbst ein. Kontrolle: **Einstellungen → Bluetooth und Geräte → Drucker und
   Scanner**. Dort sollte ein Eintrag mit **CITIZEN** im Namen stehen.
2. Falls nicht, den Windows-Treiber von der Citizen-Webseite für den CL-S521
   installieren. Dafür braucht es einmalig Adminrechte.
3. Im Etikettendruck oben rechts auf den Status klicken. Dort sollte
   „bereit“ stehen.

Das Programm sucht automatisch den ersten Drucker mit **CITIZEN** im Namen.
Heißt er anders, den Namen genau wie in Windows angezeigt in die eigene
`config.toml` eintragen (Werkzeuge → Datenordner öffnen):

```toml
[drucker]
windows_drucker = "Etikettendrucker Lager"
```

**Meldung „Treiber nimmt keine Rohdaten an“:** Manche neuere Treiber (Typ v4)
lassen keine Rohdaten durch. Dann den Drucker ein zweites Mal hinzufügen:
„Drucker hinzufügen → Der gewünschte Drucker ist nicht aufgeführt → Lokalen
Drucker hinzufügen → vorhandenen Anschluss `USB001` (o. ä.) → Hersteller
*Generic*, Drucker *Generic / Text Only*“. Diesem Drucker einen Namen mit
CITIZEN geben, z. B. „CITIZEN ZPL“. Er reicht alles unverändert durch.

Wie unter Linux muss der Citizen auf die Zebra-Emulation (ZPL) eingestellt sein,
siehe [DRUCKER.md](DRUCKER.md), Abschnitt 3. Das ist eine
Einstellung im Drucker selbst und gilt deshalb für jedes System.

**Windows SmartScreen:** Der Installer ist nicht digital signiert. Erscheint
„Der Computer wurde durch Windows geschützt“, auf **Weitere Informationen →
Trotzdem ausführen** klicken.

## Drucker unter Linux

Der Installer fragt einmalig nach dem Passwort, um den Benutzer in die Gruppe
`lp` aufzunehmen. Ohne diese Gruppe darf das Programm nicht direkt auf den
USB-Drucker schreiben. Ein neues Anmelden ist nicht nötig, das Startskript
nutzt die Gruppe sofort. Alles Weitere steht in [DRUCKER.md](DRUCKER.md).

---

## Für Entwickler: wie die Installer entstehen

Nach jedem Push auf `main` oder `installer`, der Programmcode, `config.toml`,
`data/` oder `packaging/` ändert, läuft
[`.github/workflows/installer.yml`](../.github/workflows/installer.yml):

1. Die Tests laufen unter Linux und Windows.
2. **PyInstaller** baut das Programm, jeweils auf dem eigenen System. Den
   Bauplan enthält `packaging/etikettendruck.spec`.
3. Die Installer werden gebaut: Linux mit `packaging/linux/bauen.sh`, ein
   Shell-Skript mit angehängtem Archiv; Windows mit **Inno Setup**
   (`packaging/windows/etikettendruck.iss`).
4. Beide Installer werden einmal echt gestartet und mit einem Probedruck im
   Trockenlauf getestet.
5. Die Installer werden als Commit `Installer … gebaut` in `installer/` abgelegt.

Das dauert etwa 5 Minuten. Danach `git pull`. Wichtig: **vor dem nächsten
eigenen Push erst pullen**, sonst lehnt GitHub den Push ab, weil der
Installer-Commit fehlt.

Lokal bauen (nur Linux, Windows geht nur auf Windows):

```sh
python3 -m venv .venv && .venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --noconfirm packaging/etikettendruck.spec
sh packaging/linux/bauen.sh        # → installer/Etikettendruck-Installer-Linux.sh
```

Die installierte Betriebsart lässt sich auch aus dem Quellcode ausprobieren:

```sh
ETIKETTEN_DATEN=/tmp/etiketten-test python3 -m etiketten.app
```
