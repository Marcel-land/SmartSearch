#!/usr/bin/env python3
"""Zeigt das Update-Fenster, ohne dass es dafuer ein neues Release braucht.

Startet SmartSearch ganz normal - nur mit APP_VERSION auf "1.0.0"
heruntergesetzt. Die Pruefung findet daraufhin die echte, auf GitHub
veroeffentlichte Fassung und haelt sie fuer neuer. Angezeigt werden der
echte Aenderungstext aus dem Release und der echte Downloadknopf.

An smartsearch/version.py wird dabei NICHTS geaendert: die Nummer wird nur
im Arbeitsspeicher ueberschrieben, bevor der Rest des Programms sie liest.

Aufruf (im Projektordner):
    venv/bin/python -m tests.test_update_hinweis

Vorher die installierte SmartSearch beenden - sonst erkennt der Start die
laufende Kopie und holt nur deren Fenster nach vorne.
"""

from smartsearch import version

version.APP_VERSION = "1.0.0"
print("[Test] Laeuft als Fassung 1.0.0 - die Update-Pruefung muss anschlagen.\n")

from smartsearch.oberflaeche import hauptfenster  # noqa: E402  (erst NACH dem Ueberschreiben)

hauptfenster.starten()
