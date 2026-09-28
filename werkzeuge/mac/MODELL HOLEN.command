#!/bin/bash
#
# MODELL HOLEN.command - laedt das Suchmodell nach ressourcen/modell/.
# Einmal nach dem Klonen noetig. --alle holt zusaetzlich das grosse
# float32-Modell fuer den Vergleich in SUCHE PRUEFEN.command.

cd "$(dirname "$0")/../.." || exit 1
venv/bin/python -m werkzeuge.modell_holen --alle
echo
echo "Fenster kann zu."
