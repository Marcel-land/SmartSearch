# SmartSearch installieren

## 1. Programm in den Programme-Ordner ziehen

Ziehen Sie **SmartSearch** im geöffneten Fenster auf den Ordner **Programme**.
Danach können Sie das Fenster schließen und das geladene Abbild auswerfen.

## 2. Beim ersten Start: Freigabe erteilen

SmartSearch ist nicht von Apple beglaubigt. macOS öffnet das Programm deshalb
beim ersten Mal nicht sofort, sondern zeigt eine Warnung. Das ist kein Fehler
und kein Hinweis auf Schadsoftware — Apple verlangt für die Beglaubigung ein
kostenpflichtiges Entwicklerkonto, und SmartSearch wird derzeit kostenlos
abgegeben.

So geben Sie das Programm frei:

1. Öffnen Sie SmartSearch im Programme-Ordner per Doppelklick.
   Es erscheint eine Meldung, dass das Programm nicht geöffnet werden konnte.
2. Klicken Sie auf **Fertig**.
3. Öffnen Sie **Systemeinstellungen › Datenschutz & Sicherheit**.
4. Scrollen Sie nach unten. Dort steht: „SmartSearch wurde blockiert."
5. Klicken Sie daneben auf **Trotzdem öffnen**.
6. Bestätigen Sie mit Ihrem Kennwort oder Touch ID.

Diese Freigabe ist einmalig. Ab dem zweiten Start öffnet sich SmartSearch
wie jedes andere Programm.

## 3. Beim ersten Start: Suchmodell wird geladen

SmartSearch lädt einmalig ein Suchmodell von etwa 2,3 GB herunter. Je nach
Verbindung dauert das einige Minuten; den Fortschritt sehen Sie im Fenster.

Dieser Download ist der einzige Zeitpunkt, an dem SmartSearch eine
Internetverbindung benötigt. Danach arbeitet das Programm vollständig ohne
Verbindung. Ihre Dateien verlassen Ihren Mac zu keinem Zeitpunkt.

## 4. Ordner auswählen

Beim ersten Start führt Sie eine kurze Einführung durch die Einrichtung.
Wählen Sie dort die Ordner aus, die durchsucht werden sollen.

Beginnen Sie mit wenigen Ordnern — etwa Dokumente und Schreibtisch. Weitere
lassen sich jederzeit über **Ordner hinzufügen** ergänzen. Der Downloads-Ordner
ist bewusst nicht vorausgewählt, weil er bei den meisten Menschen sehr
umfangreich ist und die erste Indexierung entsprechend lange dauern würde.

## 5. Zugriff auf Ordner erlauben

Beim Einlesen fragt macOS, ob SmartSearch auf Dokumente, Schreibtisch oder
Downloads zugreifen darf. Ohne diese Erlaubnis findet das Programm dort
nichts. Bestätigen Sie die Abfrage mit **Erlauben**.

---

## Systemvoraussetzungen

- macOS 12 (Monterey) oder neuer
- Apple Silicon oder Intel
- Etwa 3 GB freier Speicherplatz (Programm und Suchmodell)
- Internetverbindung für den ersten Start

## Häufige Fragen

**Die Suche findet ein Dokument nicht.**
Prüfen Sie drei Dinge: Ist der Ordner unter *Ordner verwalten* eingetragen?
Ist die Indexierung abgeschlossen — der Stand steht unten im Fenster? Ist der
Dateityp in der Filterleiste oben vielleicht abgewählt? Gelesen werden PDF,
Word, Excel, PowerPoint, Text- und Markdown-Dateien.

**Beschreiben Sie den Inhalt, nicht den Dateinamen.**
SmartSearch sucht nach dem, was in einem Dokument steht. „Kündigung
Mobilfunkvertrag" führt weiter als ein einzelnes Stichwort. Wörter, die
wörtlich im Dokument vorkommen, wirken dabei am stärksten.

**Einige Dateien werden als nicht lesbar gemeldet.**
Das betrifft in der Regel beschädigte oder leere PDF-Dateien, abgebrochene
Downloads und reine Bilddateien ohne erkennbaren Text. Ein Klick auf die
Meldung zeigt, welche Dateien betroffen sind.

**Wo liegen meine Daten?**
Der Suchindex liegt in Ihrem Benutzerordner unter
`~/Library/Application Support/SmartSearch/`. Sie können ihn jederzeit
ansehen oder löschen; beim nächsten Einlesen wird er neu aufgebaut.

**Wie deinstalliere ich SmartSearch?**
Programm in den Papierkorb legen und den genannten Ordner löschen. Es bleiben
keine weiteren Dateien zurück.
