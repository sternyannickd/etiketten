# Citizen Etikettendruck – Project Overview

## 1. Ziel des Projekts

Das Projekt soll einen einfachen Etikettendruck für unsere Produkte ermöglichen.

Ein Mitarbeiter soll im Programm:

- ein Produkt auswählen
- eine Menge angeben
- ein MHD eingeben
- drucken

können.

Die Produktdaten sollen aus einer CSV kommen, damit neue Produkte später einfach ergänzt werden können.

Der verwendete Drucker ist ein:

**CITIZEN CL-S521 / CL-S521Z**

Die Etiketten sind ca. **57 × 32 mm** groß und werden über USB gedruckt.


## 2. Ursprüngliche Idee

Die ursprüngliche Umsetzung basierte auf einer vorhandenen SVG-Vorlage.

Die Idee war:

    SVG-Vorlage
        ↓
    Python/PySide6
        ↓
    Produktname + Barcode + MHD einsetzen
        ↓
    PDF
        ↓
    CUPS
        ↓
    CITIZEN

Die vorhandene Gestaltung sollte dabei möglichst genau erhalten bleiben.

Die PDF-Erzeugung und Vorschau funktionieren grundsätzlich gut und das Layout kann damit sehr präzise dargestellt werden.


## 3. Warum wir den Ansatz ändern

Beim tatsächlichen Druck über den Citizen gab es jedoch Probleme.

Die PDF konnte in der Vorschau korrekt aussehen, während der Ausdruck teilweise:

- verschoben war
- falsch skaliert war
- einzelne Seiten nicht korrekt druckte
- oder im schlimmsten Fall komplett schwarz herauskam

Der Grund ist, dass zwischen unserem Layout und dem eigentlichen Druck mehrere Übersetzungsschritte liegen:

    PDF
      ↓
    CUPS
      ↓
    PPD / Treiber
      ↓
    Rasterisierung
      ↓
    Citizen

Dadurch ist nicht garantiert, dass das, was in der PDF korrekt aussieht, auch exakt so auf dem Etikett landet.

Für einen Etikettendrucker erscheint dieser Ansatz daher unnötig kompliziert.


# 4. Neuer Ansatz: direkte Druckersprache

Der neue Ansatz soll deshalb direkt die Druckersprache des Citizen verwenden.

Der Citizen CL-S521 unterstützt unter anderem eine ZPL-Emulation.

Die Grundidee:

    Produktdaten
        ↓
    Python
        ↓
    ZPL
        ↓
    CITIZEN

Das Etikett soll nicht mehr als PDF oder gerastertes Bild an den Drucker geschickt werden.

Stattdessen soll der Drucker selbst Text und Barcode erzeugen.


## 5. Das eigentliche Etikett

Das Etikett besteht im Wesentlichen nur aus drei Elementen:

### Produktname

Oben links.

Der Text soll innerhalb eines definierten Bereichs liegen und bei Bedarf einen einzigen Zeilenumbruch machen können.

Beispiel:

    Espresso
    Guatemala


### EAN-13 Barcode

Unten links.

Der Barcode soll möglichst als **native EAN-13-Funktion des Druckers** erzeugt werden und nicht als vorher gerendertes Bild.

Damit bekommt der Drucker beispielsweise:

    4006381333931

und erzeugt daraus selbst den Barcode.


### MHD

Rechts am Etikett.

Das MHD soll vertikal gedruckt werden.

Die bisher vorhandene gestrichelte Linie ist optional und nicht zwingend notwendig.


# 6. ZPL als Layout

ZPL ermöglicht es, Elemente direkt auf dem Etikett zu positionieren.

Ein Element kann beispielsweise an einer bestimmten X/Y-Position platziert werden:

    ^FO20,20

Damit können wir das Etikett praktisch als Koordinatensystem behandeln.

Bei 203 dpi entsprechen 57 × 32 mm ungefähr:

    456 × 256 dots

Damit können Produktname, Barcode und MHD sehr präzise positioniert werden.


# 7. Vorschau

Ein wichtiger Bestandteil des neuen Ansatzes soll eine ZPL-Vorschau sein.

Für die Entwicklung verwenden wir zunächst die VS-Code-Extension:

**ZPL Language & Preview**

Damit kann eine `.zpl`-Datei direkt visualisiert werden.

Der Entwicklungsablauf wäre:

    ZPL
      ↓
    Vorschau
      ↓
    Layout korrigieren
      ↓
    echter Citizen
      ↓
    Ausdruck vergleichen

Dadurch können wir das Layout zunächst vollständig ohne Papier testen.


# 8. Wichtigstes Ziel

Die Vorschau und der echte Druck sollen auf exakt denselben ZPL-Daten basieren.

Also nicht:

    GUI → eigenes Layout
    PDF → anderes Layout
    Drucker → wieder anderes Layout

sondern:

    ZPL
      ├── Vorschau
      └── Druck

Wenn die ZPL korrekt ist, gibt es nur noch eine Quelle für das Layout.


# 9. Mögliche technische Probleme

Der neue Ansatz ist wesentlich direkter, aber nicht automatisch problemlos.

### Druckersprache

Wir müssen zunächst testen, wie gut die ZPL-Emulation des konkreten Citizen funktioniert.

Falls ZPL problematisch ist, könnte auch die alternative Druckersprache des Citizen untersucht werden.


### CUPS

Auch bei ZPL kann CUPS die Daten unter Umständen durch Filter oder Treiber verändern.

Entscheidend ist deshalb der Test:

    ZPL
      ↓
    CUPS / USB
      ↓
    Citizen

Die ZPL-Daten müssen möglichst unverändert beim Drucker ankommen.


### Windows

Unter Windows muss ebenfalls geklärt werden, wie rohe ZPL-Daten an den Citizen übertragen werden.

Der ZPL-Generator selbst soll plattformunabhängig bleiben.

Nur der eigentliche Drucktransport sollte sich unterscheiden:

    ZPL Generator
         │
         ├── Linux → CUPS / USB
         │
         └── Windows → Windows-Druckweg


### Fonts

Die bisherige SVG-Version verwendet eine bestimmte Schriftgestaltung.

Bei ZPL müssen wir prüfen, welcher Druckerfont dem bisherigen Aussehen am nächsten kommt.

Das ist zunächst eine Layoutfrage, kein grundlegendes Architekturproblem.


### Barcode

Der native EAN-13-Befehl des Citizen muss auf dem echten Drucker getestet werden.

Wichtig ist nicht nur, dass der Barcode gut aussieht, sondern dass er mit unserem tatsächlichen Scanner zuverlässig gelesen werden kann.


# 10. Enterprise-Integration

Langfristig soll die Druckfunktion in das Enterprise-Programm meines Chefs integriert werden.

Deshalb soll die eigentliche Drucklogik nicht fest an die GUI gekoppelt werden.

Ideal wäre:

    Enterprise-System
          ↓
      Produktdaten
          ↓
      Label-Druckmodul
          ↓
          ZPL
          ↓
       Citizen

Die GUI wäre damit nur eine mögliche Oberfläche für dieselbe Drucklogik.

Das genaue Integrationsmodell ist noch offen.


# 11. Nächster Schritt

Noch keine große Anwendung bauen.

Zuerst soll ein minimales statisches ZPL-Etikett entstehen:

    Produktname
    EAN-13
    MHD

Dieses soll:

1. in VS Code korrekt aussehen
2. als ZPL an den echten Citizen geschickt werden
3. auf dem echten Etikett korrekt positioniert sein
4. einen tatsächlich scanbaren Barcode erzeugen

Erst wenn dieser Test funktioniert, lohnt sich der Bau der eigentlichen Anwendung.


# 12. Offene Fragen

Vor der endgültigen Implementierung müssen insbesondere diese Punkte geklärt werden:

- Welche ZPL-Funktionen unterstützt der konkrete CL-S521 zuverlässig?
- Kann ZPL über CUPS unverändert an den Drucker übertragen werden?
- Wie sieht der zuverlässigste ZPL-Druckweg unter Linux aus?
- Wie sieht der zuverlässigste Druckweg unter Windows aus?
- Welcher Druckerfont passt am besten zum bisherigen Design?
- Welche exakten Koordinaten und Größen brauchen die drei Elemente?
- Ist der native EAN-13-Barcode des Citizen mit unserem Scanner zuverlässig lesbar?
- Soll die fertige Anwendung weiterhin eine Vorschau anzeigen?
- Wie soll die Integration in das Enterprise-System erfolgen?
- Wird später von einem oder mehreren Rechnern auf einen oder mehrere Citizen-Drucker gedruckt?


# Aktueller Stand

Der aktuelle Prototyp mit PySide6, CSV-Produkten, MHD-Eingabe und PDF-Vorschau existiert.

Die PDF-Erzeugung funktioniert grundsätzlich und das Layout lässt sich damit gut darstellen.

Der PDF-basierte direkte Druckweg wird jedoch nicht weiter als Grundlage für die finale Lösung verfolgt.

**Die neue Entwicklung beginnt deshalb mit einem minimalen ZPL-Prototypen.**