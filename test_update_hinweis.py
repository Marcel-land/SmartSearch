#!/usr/bin/env python3
"""Zeigt das Update-Fenster, ohne dass es dafuer ein neues Release braucht.

Startet SmartSearch ganz normal - nur mit APP_VERSION auf "1.0.0"
heruntergesetzt. Die Pruefung findet daraufhin die echte, auf GitHub
veroeffentlichte Fassung und haelt sie fuer neuer. Angezeigt werden der
echte Aenderungstext aus dem Release und der echte Downloadknopf.

An gui.py wird dabei NICHTS geaendert: die Datei wird gelesen, die eine
Zeile im Arbeitsspeicher ersetzt und das Ergebnis ausgefuehrt. Auf der
Platte bleibt alles, wie es ist.

Aufruf:
    venv/bin/python test_update_hinweis.py

Vorher die installierte SmartSearch beenden - sonst erkennt der Start die
laufende Kopie und holt nur deren Fenster nach vorne.
"""

import pathlib
import re

quelle = pathlib.Path("gui.py").read_text(encoding="utf-8")
quelle, ersetzt = re.subn(r'APP_VERSION\s*=\s*"[^"]+"',
                          'APP_VERSION = "1.0.0"', quelle, count=1)
if not ersetzt:
    raise SystemExit("APP_VERSION nicht in gui.py gefunden.")

print("[Test] Laeuft als Fassung 1.0.0 - die Update-Pruefung muss anschlagen.\n")

# __file__ bleibt "gui.py", damit die Pfade zu Symbolen und Ressourcen
# weiterhin stimmen.
exec(compile(quelle, "gui.py", "exec"), {"__name__": "__main__", "__file__": "gui.py"})
