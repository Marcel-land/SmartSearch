#!/bin/bash
# Liegt zwei Ebenen unter dem Projektordner - dort wird gearbeitet.
cd "$(dirname "$0")/../.." || exit 1
echo "Das Modell braucht beim ersten Start eine halbe Minute. Bitte warten."
echo
venv/bin/python -m werkzeuge.such_diagnose 2>&1 | tee such-diagnose.txt
echo
echo "Fertig. Das Ergebnis steht in such-diagnose.txt - Fenster kann zu."
