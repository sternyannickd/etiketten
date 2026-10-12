# tosto → labels

> Diese Datei schreibt **tosto** (`../tosto`). labels liest sie nur und antwortet
> in `../tosto/schnittstelle/labels.md`. Regeln: `../tosto/schnittstelle/README.md`.
> Steht diese Datei in `git status` als geändert, gibt es Neues: lesen, umsetzen
> oder antworten, dann mitcommitten.

## Das gemeinsame Ziel

**TOSTO** (*Tools Of Specialty Tasting & rOasting*) ist das Portal der Rösterei.
Es macht alle Apps unter **einer Adresse mit einem Login** erreichbar, nur im Netz
der Rösterei: `https://tosto.internal.stern-kaffee.de` (Schreibweise wird noch
bestätigt).

- **Hosting: der Firmenserver** (Minisforum, AlmaLinux 10.2, Python 3.12, FreeIPA).
  Die Apps laufen dort als **Podman-Container**. Entschieden am 12.10.2026.
- **Der Drucker hängt direkt per USB am Server.** labels läuft dort als Dienst und
  druckt direkt, so wie heute am Mint-PC. Einen Druckagenten oder eine
  Warteschlange über das Internet gibt es nicht.
- **labels bleibt Python.** Die Anmeldung übernimmt tosto, labels bekommt keine
  eigene Anmeldung.
- Die Oberfläche `<etiketten-app>` (Web Component, `api`-Attribut, CSS-Variablen)
  ist die Vorlage für alle Apps im Portal. Den Vertrag beschreibt
  `../tosto/KONVENTIONEN.md` (Entwurf).

labels wird weiter **hier** entwickelt. tosto baut den Rahmen: Anmeldung, Design,
HTTPS, Betrieb auf dem Server.

## Was jetzt zu tun ist (in dieser Reihenfolge)

1. **Einrichten** (einmalig), siehe unten.
2. **Lage prüfen:** Was müsste sich an labels ändern, damit es hinter tosto auf dem
   Server läuft? Zum Beispiel: Python-Version (der Server hat 3.12), Pfade für
   Daten und Konfiguration, Lauf als systemd-Dienst ohne Browser-Start, Adresse
   (`127.0.0.1` hinter dem Webserver von tosto), Druckweg `usb` auf AlmaLinux,
   Vorschau über labelary.com (braucht Internet vom Server aus).
3. **Antworten** in `../tosto/schnittstelle/labels.md`:
   - unter „Gilt dauerhaft“: was tosto über labels wissen muss (Start, Port, API,
     Status-Endpunkt, Daten, Abhängigkeiten, Drucker),
   - unter „Nachrichten“: die Ergebnisse aus Schritt 2 und Antworten auf die
     offenen Punkte unten (L1, L2, …).
4. **Noch nicht umbauen.** Größere Änderungen erst, wenn der Plan in tosto
   freigegeben ist (`../tosto/docs/ENTSCHEIDUNGEN.md`). Kleine Dinge, die ohnehin
   sinnvoll sind, gerne.

## Einrichten (einmalig)

1. In die `CLAUDE.md` von labels übernehmen:

   ```markdown
   ## Einbindung in tosto

   labels wird über das Portal tosto (`../tosto`) auf dem Firmenserver
   bereitgestellt. Gemeinsames Ziel und Aufgaben: `TOSTO.md`.
   - Zu Beginn jeder Sitzung `git status` prüfen. Ist `TOSTO.md` geändert, zuerst
     lesen.
   - Vor Änderungen an API, Oberfläche, Datenformat oder Start/Betrieb
     `../tosto/KONVENTIONEN.md` und `../tosto/docs/ENTSCHEIDUNGEN.md` lesen.
   - Antworten und alles, was tosto über labels wissen muss, gehören nach
     `../tosto/schnittstelle/labels.md`. Das ist die einzige Datei in tosto, die
     von hier aus geschrieben werden darf. Dort nicht committen, das macht tosto.
   ```

2. `../tosto/.claude/hooks/schnittstelle.py` unverändert nach
   `.claude/hooks/schnittstelle.py` kopieren.
3. `.claude/schnittstelle.json` anlegen:
   `{"fremde_projekte": {"../tosto": ["schnittstelle/labels.md"]}}`
4. In `.claude/settings.json` `../tosto` unter `additionalDirectories` freigeben
   und den Hook eintragen wie in `../tosto/.claude/settings.json`.
5. `TOSTO.md`, `CLAUDE.md` und `.claude/` committen.

## Nachrichten

| Nr | Datum | Thema | Inhalt | Status |
|----|-------|-------|--------|--------|
| T1 | 07.10.2026 | Druckagent | ~~Druckagent mit Geräte-Token und Warteschlange über das Internet.~~ **Entfällt**, da labels auf dem Server direkt am Drucker läuft (T4). | info |
| T2 | 08.10.2026 | Vorschau | Die Web-App soll eine Vorschau haben. Mit dem Betrieb auf dem Server bleibt die heutige Lösung (labelary.com, optional). Bitte prüfen, ob etwas dagegen spricht. | offen |
| T3 | 08.10.2026 | Verfall | Falls es je eine Warteschlange gibt (z. B. Drucker kurz offline): Aufträge verfallen nach 30 Minuten und werden danach nie gedruckt. Bitte sagen, ob das heute schon zutrifft oder nötig ist. | offen |
| T4 | 12.10.2026 | Hosting | Entschieden: Firmenserver, Drucker per USB am Server, labels als Python-Dienst. Siehe „Das gemeinsame Ziel“. | info |
| T5 | 12.10.2026 | Lage prüfen | Bitte Schritt 2 und 3 aus „Was jetzt zu tun ist“ erledigen. | offen |
| T6 | 12.10.2026 | Entwicklermodus | Gewünscht: labels lässt sich lokal starten und sieht dabei genauso aus wie in tosto (tosto-Rahmen, Design, Kopfzeile). Vorschlag in `../tosto/KONVENTIONEN.md` Abschnitt 9. Bitte prüfen, was dafür in labels nötig ist, und Rückmeldung geben. | offen |
| T7 | 12.10.2026 | Zweite Etikettenart | Große Verpackungsetiketten (erste Infos liegen schon in labels). **Empfehlung von tosto: in labels als zweite Etikettenart, kein eigenes Projekt**, damit es nur eine Produktliste (GTIN, MHD) gibt. In tosto darf sie eine eigene Kachel bekommen. Entscheidung beim Nutzer (Frage N4 in `../tosto/fragen/02-nachfragen.md`). | offen |
| T8 | 12.10.2026 | Zweiter Drucker | Der Drucker für die Verpackungsetiketten (ebenfalls Citizen CL-S521, anderes Gerät) hängt an einem **Client-PC**, nicht am Server. ZPL soll vom Client-PC aus an diesen Drucker gehen. Empfehlung: Ein kleines Programm auf dem Client-PC holt die Aufträge beim Server ab (Druckagent wie ursprünglich geplant), dann kann man von jedem Gerät aus drucken und der Status steht zentral. Druckagent mit Geräte-Token, strukturierte Aufträge, Verfall nach 30 Minuten (T3). Details entscheidet labels (Frage N5). | offen |
