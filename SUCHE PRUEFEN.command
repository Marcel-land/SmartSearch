#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "Das Modell braucht beim ersten Start eine halbe Minute. Bitte warten."
echo
venv/bin/python such_diagnose.py 2>&1 | tee such-diagnose.txt
echo
echo "Fertig. Das Ergebnis steht in such-diagnose.txt - Fenster kann zu."
