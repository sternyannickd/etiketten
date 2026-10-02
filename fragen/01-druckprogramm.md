# Fragenkatalog 1 – Minimal-Etikett (Titel, MHD, Barcode)

Ziel: Ein Programm, das ein einfaches Etikett als ZPL erzeugt und roh an einen
Citizen-Drucker schickt – zuverlässig und von möglichst jeder Plattform aus.

Jede Frage hat eine **Empfehlung**. Wo du zustimmst, reicht ein „ok“ in der
Antwortzeile. Fragen mit ⚠️ blockieren den Bau – die zuerst klären.

---

## A. Grundannahmen hinterfragen

**A1. Ist ZPL die richtige Wahl?**
Empfehlung: **Ja.** ZPL ist der kleinste gemeinsame Nenner bei Etikettendruckern
(Citizen-Labeldrucker der CL-S/CL-E-Serie emulieren ZPL, Zebra spricht es nativ).
Der Drucker rendert Text und Barcode selbst – genau das, was beim PDF-Weg fehlte.
Aber: „jeder Citizen“ stimmt nicht ganz. Citizen-Bondrucker (CT-S…) können kein ZPL.
Gemeint sind also Citizen-*Etiketten*drucker.
→ Antwort: Ja

**A2. ⚠️ Welche Drucker genau, jetzt und absehbar?** (Modell, dpi, Anschlüsse)
Empfehlung: Den CL-S521 als Referenz nehmen (203 dpi). Das Layout trotzdem in **mm**
definieren und erst beim Erzeugen in Dots umrechnen, damit später ein
300-dpi-Gerät (z. B. CL-S531) ohne neues Layout funktioniert.
→ Antwort: Ja, den als Referenz nehmen

**A3. ⚠️ Was heißt „von jeder Plattform“?** Linux, Windows, macOS, Tablet, Handy?
Empfehlung: Den Drucker nicht von jedem Gerät aus direkt ansprechen. Stattdessen
**ein kleiner Druckdienst** auf einem Rechner (oder Raspberry Pi), der am Drucker
hängt, mit **Browser-Oberfläche**. Jedes Gerät mit Browser kann dann drucken, ohne
Treiber und ohne Installation. Plattformabhängig ist nur noch dieser eine
Druckweg.
→ Antwort: Genau so habe ich mir das vorgestellt, nur dass wir aktuell keinen Rasberry Pi haben. Deshalb in einem ersten Schritt bitte nur von einem Linux Mint Computer, aber das Programm so designen, dass man später einen Call an einen Computer oder RasberryPi easy umsetzen kann

**A4. ⚠️ Wie ist der Drucker angeschlossen – USB, LAN oder WLAN?**
Empfehlung: Wenn es geht, **LAN** (ggf. Schnittstellenkarte nachrüsten; ob das
für euer Modell geht, prüfen). Dann ist Drucken nur noch „ZPL-Bytes an
`IP:9100` senden“, ein paar Zeilen Code, ohne CUPS und ohne Windows-Treiber, und
auf jeder Plattform gleich. Bei USB: Druckdienst direkt am Druckerrechner,
Linux über eine CUPS-*raw*-Queue oder `/dev/usb/lp0`, Windows über die
Win32-RAW-Druck-API.
→ Antwort: USB

**A5. Die alte App (PySide6) weiterentwickeln oder neu anfangen?**
Empfehlung: **Neu und klein anfangen.** Brauchbar sind die Produkt-CSV und die
Erkenntnisse aus dem alten Versuch. PySide6 bringt Desktop-Pakete pro OS mit, was
dem Ziel „überall nutzbar“ widerspricht.
→ Antwort: neu anfangen

## B. Inhalt des Etiketts

**B1. Wofür ist der Barcode da?** Scannt *ihr* (Lager, Kasse) oder der Handel?
Empfehlung: Das klären, bevor das Layout steht. Davon hängt ab, welche Nummern
gültig sind:
- Für den **Handel/Supermarkt** braucht ihr echte **GTINs (EAN-13) von GS1
  Germany** (kostenpflichtige Mitgliedschaft). Selbst ausgedachte EANs sind
  dort nicht zulässig.
- Nur für den **internen Gebrauch** reicht EAN-13 mit Präfix **20–29**
  (für interne Zwecke reserviert) oder Code 128.
→ Antwort: Der Handel

**B2. Habt ihr schon GS1-Nummern?** Gehört die EAN zum Produkt oder auch zur Packungsgröße?
Empfehlung: Eine GTIN pro **verkaufbarer Einheit**, also pro Sorte *und* Größe
(250 g ≠ 1 kg). Die CSV braucht dafür eine Zeile pro Sorte × Größe.
→ Antwort: Weiß ich nicht. Aber wir haben irgendwas vom Supermarkt bekommen, womit wir wissen, welchen barcode wir auf die Etiketten drucken sollen

**B3. ⚠️ Ist dieses Etikett das einzige auf der Verpackung?**
Empfehlung: Wenn ja, ist es für den Verkauf **rechtlich nicht ausreichend**.
Die LMIV verlangt unter anderem Verkehrsbezeichnung, Nettofüllmenge, Name und
Anschrift des Herstellers und gegebenenfalls eine Losnummer. Das Minimal-Etikett ist
nur zusammen mit einem bedruckten Beutel oder einem zweiten Etikett zulässig. Bitte
bestätigen, wie das heute gelöst ist. Das führt direkt in Katalog 2.
→ Antwort: Ja, für das erste Programm  

**B4. MHD manuell eingeben oder berechnen?**
Empfehlung: **Berechnen** aus Röst- bzw. Abpackdatum + feste Frist pro Produkt
(z. B. 12 Monate, als Spalte in der CSV). Standardwert ist heute, er bleibt
überschreibbar. Das spart Tippfehler.
→ Antwort: Berechnen mit Option es manuell zu verändern.

**B5. Welches Datumsformat und welcher Text?**
Empfehlung: `Mindestens haltbar bis: 02.10.2027`. Das MHD mit Tag, Monat und Jahr
kann rechtlich auch als Loskennzeichnung dienen, dann braucht ihr keine eigene Losnummer.
Kürzere Varianten („MHD 02.10.27“) sind verbreitet, aber
„mindestens haltbar bis“ ist der vorgeschriebene Wortlaut.
→ Antwort: Ja, aber nicht so viel Text: "MHD: 02.10.2027"

**B6. Röstdatum zusätzlich drucken?**
Empfehlung: **Ja, wenn Platz ist.** Spezialitätenkunden achten mehr auf das Röstdatum
als auf das MHD. Für das Minimal-Etikett aber optional.
→ Antwort: Notiere das für künfitge Versionen und das Konzept. Wenn wir später komplexere Etiketten erstellen, muss das Röstdatum auf jeden Fall drauf.

**B7. Wie lang dürfen Produktnamen werden?** Umlaute (ä, ö, ü, ß), Sonderzeichen (é in „Café“)?
Empfehlung: Maximal 2 Zeilen, die Schrift automatisch verkleinern, wenn der Name nicht
passt (`^FB`-Feldblock). UTF-8 über `^CI28` verwenden und **Umlaute auf dem echten
Citizen testen**. Die Emulation ist an dieser Stelle die häufigste Fehlerquelle.
→ Antwort: Max 2 Zeilen, Umlaute nach deiner Empfehlung und wir testen es dann später

## C. Etikett & Material

**C1. ⚠️ Thermodirekt oder Thermotransfer (mit Farbband)?**
Empfehlung: Prüfen! Thermodirekt-Etiketten **verblassen** bei Wärme, Licht
und Fett, teilweise innerhalb von Monaten. Bei einem MHD von 12 Monaten und mehr kann
ein Barcode bis zum Verkauf unleserlich werden. Für Ware im Handel lieber
**Thermotransfer (Wachsband)** oder Thermodirekt-Material mit Schutzschicht
(„top-coated“).
→ Antwort:  Egal. Wir nehmen das was wir haben

**C2. Bleibt es bei 57 × 32 mm?** Wie breit ist der Abstand zwischen den Etiketten?
Erkennt der Drucker Lücken oder Schwarzmarken?
Empfehlung: Größe bleibt fürs Erste. Die Maße einmal genau nachmessen und als
`^PW` (Druckbreite) und `^LL` (Etikettenlänge) fest ins Etikett schreiben. Den
Sensor einmal kalibrieren.
→ Antwort: Für die erste Version ja

**C3. Wie sauber muss das Layout auf dem Etikett sitzen?**
Empfehlung: An allen Rändern **2 mm Sicherheitsabstand**, weil die Etiketten
in der Rolle um ±1 mm wandern. Der Nullpunkt kommt als Versatz in die
Druckerkonfiguration (`^LH`), nicht als Korrektur in jedes einzelne Feld.
→ Antwort: Ok gut

**C4. Welche Schrift?**
Empfehlung: Die eingebaute skalierbare Druckerschrift (`^A0`) nehmen und auf eine
Nachbildung des alten SVG-Designs verzichten. Eigene TrueType-Schriften lassen
sich zwar in manche Citizen laden, aber das kostet Komplexität und macht das
Wechseln des Druckers schwerer. Später neu bewerten (Katalog 2).
→ Antwort: Ok, ich prüfe dann

## D. Bedienung

**D1. Wer druckt, auf welchem Gerät, wie oft, wie viele Etiketten am Stück?**
Empfehlung: Ablauf mit 3 Klicks: Produkt wählen → Menge → Drucken. Das MHD ist
vorausgefüllt. Die Menge über `^PQ` an den Drucker geben, nicht N Druckaufträge
schicken.
→ Antwort: Ja genau so. Zunächst (siehe oben) nur an einem Linux Gerät, dass direkt am 

**D2. Braucht die App eine Vorschau?**
Empfehlung: **Ja, eine kleine.** Möglichkeiten:
- **Labelary-API** (Online-Dienst, rendert ZPL als PNG). Schnell eingebaut,
  braucht aber Internet und rendert „Zebra-genau“, nicht „Citizen-genau“.
- Eine **eigene, vereinfachte Vorschau** aus denselben Layoutdaten. Die ist
  offline, aber nur ungefähr.
Für den Anfang reicht Labelary. Der Testdruck bleibt die eigentliche Wahrheit.
→ Antwort: Ja bitte Labelary. Aber nur optional, soll nicht die Funktionalität beeinflussen.

**D3. Sollen Drucke protokolliert werden?** (wer, was, wann, welches MHD, wie viele)
Empfehlung: **Ja, ein einfaches Protokoll (CSV oder SQLite).** Kostet fast nichts
und hilft bei Reklamationen oder einem Rückruf, und für die Loskennzeichnung.
→ Antwort: Ok, aber nicht wichtig

**D4. Woher kommen die Produktdaten?** CSV jetzt, später Enterprise-System?
Empfehlung: Eine CSV mit festen Spalten (`id, name, gtin, groesse, mhd_monate`).
Druck-Kern als **eigenes Modul** mit einer Funktion
`render(produkt, mhd) → ZPL` und einer Funktion `send(zpl, drucker)`.
Oberfläche, CSV und später das Enterprise-System sind nur Aufrufer.
→ Antwort: Für die erste Version aus csv bzw. aus dem assets ordner.

**D5. Ein Drucker oder mehrere, ein Standort oder mehrere?**
Empfehlung: Mehrere Drucker in einer kleinen Konfigurationsdatei ermöglichen
(Name, Adresse, dpi), ab Tag 1 – das kostet nichts extra.
→ Antwort: ERstmal nur einer.

## E. Technik & Test

**E1. Programmiersprache?**
Empfehlung: **Python** wie bisher, Oberfläche als kleine Web-App (Flask oder FastAPI).
Das passt zu euren bisherigen Projekten.
→ Antwort: Deine Empfehlung

**E2. Was ist der erste Meilenstein?**
Empfehlung: Genau wie in `insights.md` §11, ergänzt um zwei Tests:
1. statische `.zpl`-Datei → Vorschau → echter Druck
2. Barcode mit **eurem** Scanner **und** einer Handy-App prüfen
3. Umlaute testen (`Größe`, `Café`)
4. Erst danach das Programm bauen.
→ Antwort: ne bau alles auf einmal und ich will es direkt am Drucker testen. Das sollte machbar sein.

**E3. Wer hat Zugriff auf den Drucker zum Testen, und wann?**
→ Antwort: Nur ich und ich hab eigentlich immer Zugriff, wieso?
