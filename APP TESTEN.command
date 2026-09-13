#!/bin/bash
#
# APP TESTEN.command
#
# Startet die gebaute App und protokolliert alles, was sie ausgibt.
# So laesst sich feststellen, ob im Bundle etwas fehlt - PyInstaller
# packt reine Python-Module in ein Archiv, von aussen ist also nicht
# erkennbar, ob wirklich alles mitgekommen ist. Erst der Start zeigt es.
#
# Per Doppelklick oeffnen. Der Bericht landet in test_log.txt.

cd "$(dirname "$0")" || exit 1

LOG="test_log.txt"
APP="dist/SmartSearch.app/Contents/MacOS/SmartSearch"

exec > >(tee "$LOG") 2>&1

echo "=========================================="
echo " SmartSearch - Funktionstest des Bundles"
echo " $(date '+%d.%m.%Y %H:%M:%S')"
echo "=========================================="
echo

if [ ! -f "$APP" ]; then
    echo "FEHLER: Kein gebautes Programm gefunden unter $APP"
    echo "Bitte zuerst 'BUILD STARTEN.command' ausfuehren."
    exit 1
fi

echo "Signatur:"
codesign --verify --verbose=2 "dist/SmartSearch.app" 2>&1 | sed 's/^/  /'
echo

echo "------------------------------------------"
echo " Das Programm wird gestartet."
echo
echo " Bitte im Fenster kurz etwas suchen, damit"
echo " auch die Suche selbst geprueft wird."
echo " Nach 60 Sekunden wird der Test beendet."
echo "------------------------------------------"
echo

# Die Anwendung direkt aus dem Bundle starten - nicht ueber 'open'.
# Nur so landet ihre Konsolenausgabe hier im Protokoll; 'open' wuerde
# sie abkoppeln und mit ihr jede Fehlermeldung.
"$APP" > app_ausgabe.txt 2>&1 &
APP_PID=$!

for i in $(seq 1 60); do
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        echo
        echo "!!! Das Programm hat sich nach $i Sekunden von selbst beendet."
        echo "!!! Das deutet auf einen Absturz hin. Ausgabe:"
        echo
        cat app_ausgabe.txt | sed 's/^/  /'
        echo
        echo "=========================================="
        echo " Test mit Fehler beendet."
        echo "=========================================="
        echo "Dieses Fenster kann geschlossen werden."
        exit 1
    fi
    sleep 1
done

echo "Das Programm laeuft seit 60 Sekunden stabil."
kill "$APP_PID" 2>/dev/null
sleep 2

echo
echo "------------------------------------------"
echo " Ausgabe des Programms"
echo "------------------------------------------"
if [ -s app_ausgabe.txt ]; then
    cat app_ausgabe.txt | sed 's/^/  /'
else
    echo "  (keine Ausgabe - unauffaellig)"
fi

echo
echo "------------------------------------------"
echo " Fehlerhinweise in der Ausgabe"
echo "------------------------------------------"
if grep -i -E "modulenotfound|importerror|traceback|no module|failed to" app_ausgabe.txt 2>/dev/null; then
    echo
    echo "  ^ Diese Zeilen deuten auf fehlende Bausteine im Bundle hin."
else
    echo "  Keine gefunden."
fi

echo
echo "=========================================="
echo " Test abgeschlossen."
echo "=========================================="
echo "Dieses Fenster kann geschlossen werden."
echo "(Bericht in test_log.txt)"
