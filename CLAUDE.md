# Etiketta (technisch: labels) – Etikettendruck

Python ≥ 3.11 (Server: 3.12), nur Standardbibliothek, Oberfläche als Web Components
ohne Build-Schritt. Überblick in `README.md`, Aufbau in `docs/ARCHITEKTUR.md`,
API-Vertrag in `docs/API.md`, Entscheidungen in `docs/ENTSCHEIDUNGEN.md`.
Doku und Code-Bezeichner auf Deutsch, schlicht.

- Tests: `python -m unittest discover -s tests -t .`
- Lokal entwickeln: `python -m etiketten dev` (Testdaten, druckt in Dateien).

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
