"""
werkzeuge/testdokumente - erzeugt die Testdokumente unter tests/testdokumente.

    venv/bin/python -m werkzeuge.testdokumente

Die fertigen Dateien liegen im Repository; neu erzeugen muss sie nur, wer
etwas an haushalt.py oder kanzlei.py aendert. Dafuer braucht es zusaetzlich
reportlab (pip install reportlab), das nicht zur App gehoert.

Zusammen mit den zehn urspruenglichen Dokumenten im Hauptordner sind es 50:
  - 25 aus einem Privathaushalt (haushalt.py + die zehn alten)
  - 25 aus einer Anwaltskanzlei (kanzlei.py)
  - Formate: PDF mit Text, gescannte PDFs ohne Text (brauchen die
    Texterkennung), Word, Excel, PowerPoint, .txt und .md

Welche Suchanfrage welches Dokument finden muss, steht in tests/suchfaelle.py.
Alles ist frei erfunden. Gerichte und Paragraphen sind echt, Personen,
Firmen, Aktenzeichen und Betraege nicht.
"""
