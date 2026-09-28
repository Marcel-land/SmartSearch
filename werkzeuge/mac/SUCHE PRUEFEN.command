#!/bin/bash
#
# SUCHE PRUEFEN.command - misst die Suchqualitaet an den Testdokumenten.
#
# Baut jedes Mal einen frischen Index aus tests/testdokumente in einem
# eigenen, leeren Ordner. Der Index, mit dem die App arbeitet, bleibt
# unberuehrt. Ergebnis: such-diagnose.txt im Projektordner.
#
# Zusaetzlich wird das grosse Quellmodell gemessen, aus dem die
# ausgelieferte Fassung abgeleitet ist: such-diagnose-float32.txt. Beide
# muessen dasselbe Ergebnis liefern - sonst hat das Verkleinern geschadet.

# Liegt zwei Ebenen unter dem Projektordner - dort wird gearbeitet.
cd "$(dirname "$0")/../.." || exit 1

venv/bin/python -u -X faulthandler -m werkzeuge.such_diagnose --testdokumente 2>&1 | tee such-diagnose.txt

if [ -f ressourcen/modell/granite-embedding-97m-multilingual-r2/onnx/model.onnx ]; then
    echo
    echo "=== Zum Vergleich: volle Genauigkeit (float32) ==="
    SMARTSEARCH_MODELLDATEI=onnx/model.onnx venv/bin/python -u -X faulthandler -m werkzeuge.such_diagnose --testdokumente 2>&1 | tee such-diagnose-float32.txt
fi

echo
echo "Fertig. Das Ergebnis steht in such-diagnose.txt - Fenster kann zu."
