#!/usr/bin/env python3
"""
plattform/andere.py - Ausweichweg fuer alle anderen Systeme (Linux).

SmartSearch wird fuer Linux nicht ausgeliefert. Diese Datei gibt es, damit
das Programm dort trotzdem startet - zum Testen auf einem Server oder in
einer Linux-VM. Sie bietet dieselben Funktionen wie mac.py und windows.py;
alles, was es hier nicht gibt, tut schlicht nichts.
"""

import locale
import os
import platform
import subprocess
import sys

# Kein Symbol in einer Menueleiste: die Oberflaeche laesst das Fenster dann
# offen, statt es beim Fokusverlust zu verstecken (sonst waere es
# unerreichbar).
VERFUEGBAR = False
VORSCHAU_VERFUEGBAR = False


def _still_ausfuehren(befehl):
    subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def benachrichtigung(titel, text):
    try:
        subprocess.run(["notify-send", titel, text], check=False)
    except Exception as e:
        print(f"[Benachrichtigung fehlgeschlagen] {e}")


def datei_oeffnen(pfad):
    try:
        subprocess.run(["xdg-open", pfad], check=True)
        return True
    except Exception as e:
        print(f"[Oeffnen fehlgeschlagen] {e}")
        return False


def im_dateimanager_zeigen(dateipfad):
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        _still_ausfuehren(["xdg-open", os.path.dirname(dateipfad)])
    except Exception as e:
        print(f"[Dateimanager Fehler] {e}")


def vorschau(dateipfad):
    if dateipfad and os.path.exists(dateipfad):
        datei_oeffnen(dateipfad)


def app_pfad():
    return os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])


def autostart_aktiv():
    return False


def autostart_setzen(einschalten):
    return False, "Autostart wird auf diesem System nicht unterstuetzt."


def systemsprache(unterstuetzt):
    try:
        kurz = (locale.getlocale()[0] or "")[:2].lower()
        return kurz if kurz in unterstuetzt else None
    except Exception:
        return None


def system_beschreibung():
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


# Bedienung (Menueleiste/Infobereich, Dock) gibt es hier nicht.

def menueleisten_symbol_anlegen(callback, beenden_callback=None, icon_pfad=None):
    return None


def registriere_globalen_hotkey(callback):
    return None


def fenster_nach_vorne():
    pass


def als_programm_im_dock_anmelden():
    pass


def aus_dem_dock_nehmen():
    return False


def dock_symbol_setzen(icon_pfad):
    pass


def programmnamen_setzen(name="SmartSearch"):
    return False


def app_ist_aktiv():
    return None


def laufende_instanz_aktivieren():
    return False
