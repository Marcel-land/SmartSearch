#!/bin/bash
#
# SUCHE PRUEFEN.command - misst die Suchqualitaet an den Testdokumenten.
#
# Baut jedes Mal einen frischen Index aus tests/testdokumente in einem
# eigenen, leeren Ordner. Der Index, mit dem die App arbeitet, bleibt
# unberuehrt. Ergebnis: such-diagnose.txt im Projektordner.
#
# Liegt das grosse float32-Modell vor (modell_holen --alle), wird es
# zusaetzlich gemessen: such-diagnose-float32.txt.

# Liegt zwei Ebenen unter dem Projektordner - dort wird gearbeitet.
cd "$(dirname "$0")/../.." || exit 1

venv/bin/python -m werkzeuge.such_diagnose --testdokumente 2>&1 | tee such-diagnose.txt

if [ -f ressourcen/modell/granite-embedding-97m-multilingual-r2/onnx/model.onnx ]; then
    echo
    echo "=== Zum Vergleich: volle Genauigkeit (float32) ==="
    SMARTSEARCH_MODELLDATEI=onnx/model.onnx venv/bin/python -m werkzeuge.such_diagnose --testdokumente 2>&1 | tee such-diagnose-float32.txt
fi

echo
echo "Fertig. Das Ergebnis steht in such-diagnose.txt - Fenster kann zu."
