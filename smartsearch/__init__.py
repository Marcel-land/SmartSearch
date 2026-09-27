"""SmartSearch - lokale Dateisuche nach Inhalt statt nach Dateiname.

Aufbau (siehe docs/ARCHITEKTUR.md):

    kern/          alles, was auf JEDEM System gleich ist: Suche, Index,
                   Modell, Dateien lesen, Einstellungen, Updates
    oberflaeche/   Fenster, Dialoge, Texte, Farben
    plattform/     alles, was Mac und Windows UNTERSCHIEDLICH machen

Start aus dem Quelltext:   venv/bin/python -m smartsearch
"""
