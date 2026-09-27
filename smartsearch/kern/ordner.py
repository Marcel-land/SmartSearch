#!/usr/bin/env python3
"""
ordner.py - Ordner zur Suche hinzufuegen und wieder entfernen.

Eigene Datei, weil das Entfernen zwei Stellen betrifft: die Einstellungen
UND den Index. Stuende es in einer der beiden, muesste die eine die andere
kennen - und umgekehrt.
"""

import os

from smartsearch.kern.einstellungen import lade_config, speichere_config
from smartsearch.kern.index import entferne_ordner_aus_index

def befehl_ordner_hinzufuegen(ordner):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    if not os.path.isdir(ordner):
        print(f"Der Ordner '{ordner}' existiert nicht.")
        return
    config = lade_config()
    if ordner in config["ordner"]:
        return
    config["ordner"].append(ordner)
    speichere_config(config)


def befehl_ordner_entfernen(ordner):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    config = lade_config()
    if ordner not in config["ordner"]:
        return
    config["ordner"].remove(ordner)
    speichere_config(config)

    # WICHTIG: Ein entfernter Ordner muss auch aus dem Index verschwinden.
    # Vorher wurde nur die config.json angepasst - die bereits berechneten
    # Eintraege blieben in index.pkl liegen und tauchten weiter in den
    # Suchergebnissen auf. Genau das war der Fehler "ich finde Dateien aus
    # einem Ordner, den ich laengst entfernt habe".
    entfernt = entferne_ordner_aus_index(ordner)
    if entfernt:
        print(f"[Index] {entfernt} Eintraege aus '{ordner}' entfernt.")
