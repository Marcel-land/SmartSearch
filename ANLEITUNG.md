# SmartSearch - Erste Schritte auf deinem Mac

Diese Anleitung geht davon aus, dass du noch nie das Terminal benutzt hast.
Jeder Schritt ist einzeln erklärt. Keine Sorge, du kannst nichts kaputt machen.

## Schritt 1: Terminal öffnen

1. Drücke `Cmd + Leertaste` (öffnet die Spotlight-Suche)
2. Tippe "Terminal"
3. Drücke Enter

Es öffnet sich ein schwarzes/weißes Fenster mit Text. Das ist das Terminal.
Hier tippst du ab jetzt Befehle ein und drückst nach jedem Enter.

## Schritt 2: Prüfen, ob Python installiert ist

Tippe das ein und drücke Enter:

```
python3 --version
```

- Steht da etwas wie "Python 3.x.x" → weiter zu Schritt 3
- Steht da "command not found" → installiere Python von https://www.python.org/downloads/
  (Lade die Version für macOS herunter, öffne die Datei, klicke dich durch die Installation)

## Schritt 3: Die Projekt-Dateien entpacken

1. Lade die Datei "smartsearch.zip" herunter (Link bekommst du von Claude)
2. Doppelklick auf die Datei im Downloads-Ordner → sie entpackt sich automatisch
3. Im Terminal eintippen (ersetzt den Pfad, falls dein Downloads-Ordner woanders liegt):

```
cd ~/Downloads/smartsearch
```

Das bedeutet: "wechsle in diesen Ordner". Drücke Enter.

## Schritt 4: Benötigte Bausteine installieren

Tippe ein und drücke Enter (das dauert 2-5 Minuten, da lädt er etwas herunter):

```
pip3 install sentence-transformers pypdf numpy
```

Du siehst viel Text durchlaufen - das ist normal. Warte, bis du wieder eine
neue Eingabezeile siehst.

## Schritt 5: Einen Ordner "einlesen" lassen

Wähle einen Test-Ordner mit ein paar Dateien, z.B. deinen Dokumente-Ordner.
Tippe ein (ersetzt den Pfad mit deinem eigenen):

```
python3 search.py index ~/Documents
```

Beim ersten Mal wird zusätzlich einmalig ein KI-Modell heruntergeladen
(ca. 80 MB, dauert 1-2 Minuten). Danach siehst du, wie die Dateien
eingelesen werden.

## Schritt 6: Suchen!

Jetzt kannst du in normaler Sprache suchen:

```
python3 search.py suche "Rechnung von letztem Monat"
```

Du bekommst eine Liste der inhaltlich passendsten Dateien mit Textvorschau.

## Was als Nächstes?

Das ist die einfachste Version - noch ohne Tastenkürzel, ohne Hintergrund-
Dienst, ohne hübsche Oberfläche. Aber der Kern funktioniert bereits: Dateien
"verstehen" und in normaler Sprache durchsuchen.

Wenn das bei dir läuft, sag Claude Bescheid - dann bauen wir Schritt für
Schritt die nächsten Teile: automatisches Neu-Indexieren bei Änderungen,
ein Tastenkürzel, eine grafische Oberfläche statt Terminal.
