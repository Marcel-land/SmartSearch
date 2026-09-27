#!/usr/bin/env python3
"""
einstellungen.py - alles, was sich SmartSearch ueber den Nutzer merkt:
ueberwachte Ordner, Sprache und Zaehler (config.json), Favoriten und
Suchverlauf. Dazu Export und Import der Einrichtung.

Die Dateien liegen im Datenordner des Systems, siehe pfade.py.
"""

import json
import os

from smartsearch.kern.pfade import CONFIG_FILE, FAVORITEN_FILE, VERLAUF_FILE

def lade_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"ordner": []}


def speichere_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def ueberwachte_ordner():
    """Aktuell in der config.json eingetragene Ordner, absolut."""
    return [
        os.path.abspath(os.path.expanduser(o))
        for o in lade_config().get("ordner", [])
    ]


# ---------- FAVORITEN ----------

def lade_favoriten():
    """Gibt die Menge der als Favorit markierten Dateipfade zurück."""
    if os.path.exists(FAVORITEN_FILE):
        try:
            with open(FAVORITEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[Warnung] Favoriten konnten nicht geladen werden: {e}")
            return set()
    return set()


def speichere_favoriten(favoriten):
    try:
        with open(FAVORITEN_FILE, "w") as f:
            json.dump(sorted(favoriten), f, indent=2)
    except Exception as e:
        print(f"[Warnung] Favoriten konnten nicht gespeichert werden: {e}")


def favorit_umschalten(pfad):
    """Fügt pfad zu den Favoriten hinzu oder entfernt ihn.

    Gibt True zurück, wenn die Datei danach ein Favorit ist, sonst False.
    """
    favoriten = lade_favoriten()
    if pfad in favoriten:
        favoriten.remove(pfad)
        ist_favorit = False
    else:
        favoriten.add(pfad)
        ist_favorit = True
    speichere_favoriten(favoriten)
    return ist_favorit


# ---------- SUCHVERLAUF ----------

MAX_VERLAUF = 20


def lade_verlauf():
    """Die letzten Suchanfragen, neueste zuerst."""
    if os.path.exists(VERLAUF_FILE):
        try:
            with open(VERLAUF_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def speichere_verlauf(verlauf):
    try:
        with open(VERLAUF_FILE, "w") as f:
            json.dump(verlauf, f, indent=2)
    except Exception:
        pass


def verlauf_ergaenzen(verlauf, anfrage):
    """Setzt die Anfrage an den Anfang (ohne Doppelungen, hoechstens
    MAX_VERLAUF Eintraege), speichert und gibt die neue Liste zurueck."""
    verlauf = [v for v in verlauf if v != anfrage]
    verlauf.insert(0, anfrage)
    verlauf = verlauf[:MAX_VERLAUF]
    speichere_verlauf(verlauf)
    return verlauf


def exportiere_konfiguration(zielpfad):
    """Schreibt überwachte Ordner + Favoriten als lesbare JSON-Datei.

    Praktisch als Backup oder um die eigene Einrichtung auf einen anderen
    Mac zu übertragen, ohne den kompletten (oft sehr großen) Suchindex
    mitnehmen zu müssen - der wird beim nächsten 'Index aktualisieren'
    einfach neu aufgebaut.
    """
    daten = {
        "ordner": lade_config().get("ordner", []),
        "favoriten": sorted(lade_favoriten()),
    }
    with open(zielpfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)


def importiere_konfiguration(quellpfad):
    """Liest eine mit exportiere_konfiguration() erzeugte JSON-Datei ein
    und fügt überwachte Ordner + Favoriten zur bestehenden Einrichtung
    hinzu (überschreibt nichts, ergänzt nur). Gibt (anzahl_ordner,
    anzahl_favoriten) aus der importierten Datei zurück."""
    with open(quellpfad, "r", encoding="utf-8") as f:
        daten = json.load(f)

    importierte_ordner = daten.get("ordner", [])
    config = lade_config()
    for ordner in importierte_ordner:
        if ordner not in config["ordner"]:
            config["ordner"].append(ordner)
    speichere_config(config)

    importierte_favoriten = daten.get("favoriten", [])
    favoriten = lade_favoriten()
    favoriten.update(importierte_favoriten)
    speichere_favoriten(favoriten)

    return len(importierte_ordner), len(importierte_favoriten)
