#!/usr/bin/env python3
"""
plattform - alles, was auf jedem Betriebssystem ANDERS funktioniert.

REGEL: Die Oberflaeche und der Kern beschreiben, WAS passieren soll
("zeig die Datei im Dateimanager"). WIE das auf dem jeweiligen System geht,
steht in genau einer Datei:

    plattform/mac.py       macOS (Finder, Quick Look, Menueleiste, Dock, LaunchAgent)
    plattform/windows.py   Windows (Explorer, Infobereich, Registry)
    plattform/andere.py    Ausweichweg zum Testen unter Linux

Alle drei bieten DIESELBEN Funktionsnamen. Diese Datei waehlt beim Start
die passende aus und reicht ihre Funktionen weiter - im restlichen Code
steht deshalb nirgends "wenn Mac, dann ...". Wer an Windows arbeitet,
aendert windows.py und sonst (fast) nichts.

Grundsatz fuer alle Funktionen: Sie duerfen NIE eine Ausnahme nach oben
durchreichen. Eine fehlgeschlagene Benachrichtigung darf die Suche nicht
abbrechen.

Neue Funktion noetig? In ALLEN DREI Dateien anlegen (notfalls als "tut
nichts") und unten in der Liste ergaenzen.
"""

import os
import sys

IST_MAC = sys.platform == "darwin"
IST_WINDOWS = os.name == "nt"
IST_LINUX = not IST_MAC and not IST_WINDOWS

if IST_MAC:
    from smartsearch.plattform import mac as _system
elif IST_WINDOWS:
    from smartsearch.plattform import windows as _system
else:
    from smartsearch.plattform import andere as _system

# --- System-Handgriffe ------------------------------------------------------
benachrichtigung = _system.benachrichtigung
datei_oeffnen = _system.datei_oeffnen
im_dateimanager_zeigen = _system.im_dateimanager_zeigen
vorschau = _system.vorschau
app_pfad = _system.app_pfad
autostart_aktiv = _system.autostart_aktiv
autostart_setzen = _system.autostart_setzen
systemsprache = _system.systemsprache
system_beschreibung = _system.system_beschreibung

# Quick Look gibt es so nur auf dem Mac.
VORSCHAU_VERFUEGBAR = _system.VORSCHAU_VERFUEGBAR

# --- Bedienung: Symbol in Menueleiste/Infobereich, Dock, Tastenkuerzel -------
# SYMBOL_VERFUEGBAR sagt, ob die Grundlage dafuer da ist (PyObjC auf dem
# Mac, pystray unter Windows). Fehlt sie, gibt es kein Symbol zum
# Zurueckholen des Fensters - dann darf die Oberflaeche es nicht
# automatisch verstecken (siehe Hauptfenster.auf_fokus_verlust), und alle
# Funktionen dieses Abschnitts werden nicht aufgerufen.
SYMBOL_VERFUEGBAR = bool(getattr(_system, "VERFUEGBAR", False))

menueleisten_symbol_anlegen = _system.menueleisten_symbol_anlegen
registriere_globalen_hotkey = _system.registriere_globalen_hotkey
fenster_nach_vorne = _system.fenster_nach_vorne
als_programm_im_dock_anmelden = _system.als_programm_im_dock_anmelden
aus_dem_dock_nehmen = _system.aus_dem_dock_nehmen
dock_symbol_setzen = _system.dock_symbol_setzen
programmnamen_setzen = _system.programmnamen_setzen
app_ist_aktiv = _system.app_ist_aktiv
laufende_instanz_aktivieren = _system.laufende_instanz_aktivieren

if not SYMBOL_VERFUEGBAR and not IST_LINUX:
    print("[Start] Kein Symbol in Menueleiste/Infobereich - Fenster bleibt sichtbar.")
