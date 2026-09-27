#!/usr/bin/env python3
"""
pfade.py - zentrale Ablage aller Nutzerdaten von SmartSearch.

WARUM ES DIESE DATEI GIBT
-------------------------
Frueher lagen Index, Konfiguration, Favoriten und Suchverlauf direkt neben
gui.py, also im Programmordner. Solange man die App aus dem Quellcode
startet, faellt das nicht auf. In einer gebauten .app ist es aber ein
handfestes Problem:

1. Ein Update bedeutet auf dem Mac "alte .app in den Papierkorb, neue
   hineinziehen" - damit waeren alle Einstellungen und der komplette Index
   weg, und jeder Nutzer muesste nach jedem Update alles neu einlesen.
2. Sobald die App signiert ist, bricht jedes Schreiben ins eigene Bundle
   die Signatur. macOS verweigert den Start dann komplett.
3. Liegt die App in /Applications, hat ein normaler Nutzer dort gar keine
   Schreibrechte.

Deshalb liegt ab jetzt alles an dem Ort, den macOS dafuer vorsieht:

    ~/Library/Application Support/SmartSearch/

Der ueberlebt Updates, Verschieben der App und das Signieren.

MIGRATION
---------
Damit bestehende Installationen (und Marcels eigener Arbeitsordner) beim
Umstieg nicht bei null anfangen, werden vorhandene Dateien aus dem alten
Ort einmalig herueberkopiert - kopiert, nicht verschoben, damit ein
Fehlschlag nichts zerstoert. Passiert genau einmal; danach existiert die
Zieldatei und die Migration ueberspringt sie.
"""

import os
import shutil
import sys

APP_NAME = "SmartSearch"

# Projektordner (dort liegen ressourcen/, tests/, werkzeuge/ ...). Diese
# Datei liegt in smartsearch/kern/, also zwei Ebenen darunter.
PROJEKT_ORDNER = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Alter Ablageort der Nutzerdaten: bis zur Einfuehrung dieser Datei lagen
# index.pkl & Co. direkt im Projektordner neben gui.py.
_ALTER_ORDNER = PROJEKT_ORDNER


# ---------------------------------------------------------------------------
# PROGRAMM-RESSOURCEN (Symbole usw.)
#
# Nicht zu verwechseln mit den Nutzerdaten weiter unten: Ressourcen gehoeren
# zum Programm und werden mit ausgeliefert, Nutzerdaten entstehen beim
# Benutzen.
#
# Warum eine eigene Funktion: Beim Start aus dem Quelltext liegen die
# Symbole in ressourcen/ im Projektordner. In der gebauten App packt
# PyInstaller sie in einen eigenen Ordner, den es zur Laufzeit in
# sys._MEIPASS nennt. Vorher stand an drei Stellen im Code
# "os.path.dirname(__file__) + icon.png" - in der gebauten App zeigte das
# ins Leere, weil icon.png dort gar nicht mitgepackt war. Unter Windows
# haette das Fenster deshalb nie ein eigenes Symbol bekommen.
# ---------------------------------------------------------------------------

def ressource(relativer_pfad):
    """Absoluter Pfad einer mitgelieferten Datei, z. B. ressource("icons/icon.png")."""
    basis = getattr(sys, "_MEIPASS", None)
    if basis:
        return os.path.join(basis, "ressourcen", relativer_pfad)
    return os.path.join(PROJEKT_ORDNER, "ressourcen", relativer_pfad)


def _ermittle_daten_ordner():
    """Der Ort, den das jeweilige System fuer Programmdaten vorsieht.

    macOS:   ~/Library/Application Support/SmartSearch
    Windows: %LOCALAPPDATA%\\SmartSearch
    sonst:   ~/.smartsearch

    Unter Windows ist das nicht nur Geschmackssache: LOCALAPPDATA ist der
    Ordner, den ein Nutzer OHNE Administratorrechte beschreiben darf, und
    den eine Firma bei servergespeicherten Profilen bewusst NICHT mit
    synchronisiert. Ein Index von mehreren hundert Megabyte hat in einem
    wandernden Profil nichts zu suchen - er wuerde bei jeder Anmeldung
    durchs Netz kopiert.

    Faellt in allen Faellen auf ~/.smartsearch zurueck, wenn der
    vorgesehene Ort nicht existiert - besser ein unuebliches Verzeichnis
    als ein Absturz beim Start.
    """
    if os.name == "nt":
        basis = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if basis and os.path.isdir(basis):
            return os.path.join(basis, APP_NAME)
        return os.path.expanduser("~/.smartsearch")

    basis = os.path.expanduser("~/Library/Application Support")
    if not os.path.isdir(basis):
        return os.path.expanduser("~/.smartsearch")
    return os.path.join(basis, APP_NAME)


DATEN_ORDNER = _ermittle_daten_ordner()

INDEX_FILE = os.path.join(DATEN_ORDNER, "index.pkl")
CONFIG_FILE = os.path.join(DATEN_ORDNER, "config.json")
FAVORITEN_FILE = os.path.join(DATEN_ORDNER, "favoriten.json")
VERLAUF_FILE = os.path.join(DATEN_ORDNER, "verlauf.json")

# Dateiname -> Zielpfad. Reihenfolge egal, alle werden einzeln geprueft.
_ZU_MIGRIEREN = {
    "index.pkl": INDEX_FILE,
    "config.json": CONFIG_FILE,
    "favoriten.json": FAVORITEN_FILE,
    "verlauf.json": VERLAUF_FILE,
}


def stelle_datenordner_sicher():
    """Legt den Datenordner an und holt einmalig alte Daten herueber.

    Wird beim Import dieses Moduls aufgerufen, also automatisch beim
    Programmstart - egal ob ueber gui.py oder search.py. Schlaegt bewusst
    nie hart fehl: kann der Ordner nicht angelegt werden, laeuft die App
    trotzdem weiter und meldet das Problem erst dort, wo wirklich
    geschrieben wird.
    """
    try:
        os.makedirs(DATEN_ORDNER, exist_ok=True)
    except Exception as e:
        print(f"[Warnung] Datenordner konnte nicht angelegt werden ({DATEN_ORDNER}): {e}")
        return

    for dateiname, ziel in _ZU_MIGRIEREN.items():
        quelle = os.path.join(_ALTER_ORDNER, dateiname)
        # Nur migrieren, wenn es am alten Ort etwas gibt UND am neuen Ort
        # noch nichts steht - sonst wuerde ein spaeterer Start frische
        # Daten mit einem alten Stand ueberschreiben.
        if not os.path.exists(quelle) or os.path.exists(ziel):
            continue
        try:
            shutil.copy2(quelle, ziel)
            print(f"[Info] {dateiname} in den Datenordner uebernommen.")
        except Exception as e:
            print(f"[Warnung] {dateiname} konnte nicht uebernommen werden: {e}")


stelle_datenordner_sicher()
