#!/usr/bin/env python3
"""
modell_holen.py - laedt das Suchmodell nach ressourcen/modell/.

Das Modell gehoert zur App, aber nicht ins Git-Repository (rund 100 MB).
Einmal nach dem Klonen ausfuehren, dazu vor jedem Bauen (bauen/mac/build.sh
ruft es selbst auf, wenn etwas fehlt):

    venv/bin/python -m werkzeuge.modell_holen           nur, was die App braucht
    venv/bin/python -m werkzeuge.modell_holen --alle    zusaetzlich das grosse
                                                        float32-Modell (390 MB),
                                                        fuer werkzeuge/modellvergleich

Braucht keine Zusatzpakete - nur Pythons eigenes urllib. Vorhandene Dateien
werden nicht erneut geladen.
"""

import hashlib
import os
import sys
import urllib.request

from smartsearch.kern import modell

BASIS = f"https://huggingface.co/{modell.MODELL_NAME}/resolve/main/"

# Was die App braucht. README.md ist die Modellbeschreibung von IBM - sie
# wird mit ausgeliefert, weil die Apache-2.0-Lizenz verlangt, Herkunft und
# Lizenz weiterzugeben.
PFLICHT = [modell.TOKENIZER_DATEI, "config.json", "README.md", modell.MODELL_DATEI]
GROSS = ["onnx/model.onnx"]

LIZENZ_TEXT = f"""Suchmodell: {modell.MODELL_NAME}
Herkunft:   https://huggingface.co/{modell.MODELL_NAME}
Lizenz:     Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
Hersteller: IBM

Die Dateien in diesem Ordner sind unveraendert von der Adresse oben
uebernommen. SmartSearch nutzt das Modell, ohne es zu veraendern.
"""


def _laden(datei):
    ziel = modell.modell_pfad(datei)
    if os.path.isfile(ziel) and os.path.getsize(ziel) > 0:
        print(f"  vorhanden  {datei}")
        return ziel
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    teil = ziel + ".teil"
    print(f"  lade       {datei} ...", end="", flush=True)
    anfrage = urllib.request.Request(BASIS + datei, headers={"User-Agent": "SmartSearch-Bau"})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort, open(teil, "wb") as f:
        gesamt = int(antwort.headers.get("Content-Length") or 0)
        geladen = 0
        while True:
            stueck = antwort.read(1 << 20)
            if not stueck:
                break
            f.write(stueck)
            geladen += len(stueck)
            if gesamt:
                print(f"\r  lade       {datei} ... {geladen * 100 // gesamt:3d} %", end="", flush=True)
    os.replace(teil, ziel)
    print(f"\r  geladen    {datei} ({os.path.getsize(ziel) / 1e6:.1f} MB)        ")
    return ziel


def _pruefsumme(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for stueck in iter(lambda: f.read(1 << 20), b""):
            h.update(stueck)
    return h.hexdigest()


def main():
    dateien = PFLICHT + (GROSS if "--alle" in sys.argv else [])
    print(f"Suchmodell nach {modell.modell_pfad()}\n")
    for datei in dateien:
        _laden(datei)
    with open(modell.modell_pfad("LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ_TEXT)

    # Pruefsummen festhalten: so laesst sich spaeter nachweisen, welche
    # Modellfassung in einer ausgelieferten App steckt.
    with open(modell.modell_pfad("PRUEFSUMMEN.txt"), "w", encoding="utf-8") as f:
        for datei in dateien:
            f.write(f"{_pruefsumme(modell.modell_pfad(datei))}  {datei}\n")
    print("\nFertig. modell_ist_vorhanden():", modell.modell_ist_vorhanden())


if __name__ == "__main__":
    main()
