#!/bin/bash
#
# BUILD STARTEN.command
#
# Diese Datei per Doppelklick oeffnen. Sie erledigt alles Noetige und
# schreibt einen vollstaendigen Bericht in build_log.txt, damit Fehler
# nachvollzogen werden koennen, ohne etwas abtippen zu muessen.

cd "$(dirname "$0")" || exit 1

LOG="build_log.txt"

# Alles, was ab hier ausgegeben wird, landet gleichzeitig auf dem
# Bildschirm UND in der Protokolldatei.
exec > >(tee "$LOG") 2>&1

echo "=========================================="
echo " SmartSearch - Bau des Programms"
echo " $(date '+%d.%m.%Y %H:%M:%S')"
echo "=========================================="
echo
echo "System:"
sw_vers 2>/dev/null
echo "Architektur: $(uname -m)"
echo

if [ ! -d "venv" ]; then
    echo "FEHLER: Kein venv im Projektordner gefunden."
    echo "Fenster kann geschlossen werden."
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate
echo "Python: $(python3 --version)  ($(which python3))"
echo

# ---------------------------------------------------------------------------
echo "------------------------------------------"
echo " Schritt 1 von 2: Fehlende Pakete nachziehen"
echo "------------------------------------------"

# Vision wird fuer die Texterkennung in eingescannten PDF-Dateien
# gebraucht. Ohne das Paket faellt die Erkennung aus.
if python3 -c "import Vision" 2>/dev/null; then
    echo "pyobjc-framework-Vision: bereits vorhanden"
else
    echo "pyobjc-framework-Vision wird installiert..."
    pip install --quiet pyobjc-framework-Vision 2>&1 | tail -5
    if python3 -c "import Vision" 2>/dev/null; then
        echo "  erfolgreich installiert"
    else
        echo "  FEHLGESCHLAGEN - Texterkennung wird nicht verfuegbar sein"
    fi
fi

for paket in pypdfium2 pyinstaller; do
    modul="$paket"
    [ "$paket" = "pyinstaller" ] && modul="PyInstaller"
    if python3 -c "import $modul" 2>/dev/null; then
        echo "$paket: bereits vorhanden"
    else
        echo "$paket wird installiert..."
        pip install --quiet "$paket" 2>&1 | tail -3
    fi
done
echo

# Welche Version welcher Bausteine verwendet wird - hilft bei der
# Fehlersuche, falls der Build spaeter woanders anders ausfaellt.
echo "Verwendete Versionen:"
pip list 2>/dev/null | grep -i -E "^(torch|sentence-transformers|customtkinter|pypdfium2|pyobjc-framework-Vision|pyinstaller|watchdog|pdfplumber) " || true
echo

# ---------------------------------------------------------------------------
echo "------------------------------------------"
echo " Schritt 2 von 2: Programm bauen"
echo "------------------------------------------"
echo "Das dauert einige Minuten. Fenster bitte offen lassen."
echo

# build.sh fragt nach, wenn Vision fehlt - hier soll nichts nachfragen,
# deshalb wird die Antwort gleich mitgegeben.
echo "j" | bash build.sh
ERGEBNIS=$?

echo
echo "=========================================="
if [ $ERGEBNIS -eq 0 ]; then
    echo " Fertig."
    echo
    ls -lh ./*.dmg 2>/dev/null
else
    echo " Mit Fehler beendet (Code $ERGEBNIS)."
    echo " Das vollstaendige Protokoll steht in build_log.txt."
fi
echo "=========================================="
echo
echo "Dieses Fenster kann jetzt geschlossen werden."
echo "(Der Bericht liegt in build_log.txt im Projektordner.)"
