#!/bin/bash
#
# MODELL HOLEN.command - laedt das Suchmodell nach ressourcen/modell/ und
# verkleinert es fuer die App. Einmal nach dem Klonen noetig.

cd "$(dirname "$0")/../.." || exit 1
venv/bin/python -m werkzeuge.modell_holen
echo
echo "Fenster kann zu."
