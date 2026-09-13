#!/bin/bash
#
# BUNDLE PRUEFEN.command
#
# Der vorige Test hat gezeigt, dass die App startet und stabil laeuft.
# Das genuegt aber nicht: Sie startet versteckt und laedt das Suchmodell
# erst beim ersten Suchvorgang. Module wie sentence-transformers wuerden
# also erst dann fehlen - lange nach dem Start.
#
# Dieses Skript prueft deshalb direkt im mitgelieferten Archiv nach, ob
# alle noetigen Bausteine im Bundle stecken, und oeffnet die App danach
# sichtbar zum Nachtesten.

cd "$(dirname "$0")" || exit 1

LOG="pruef_log.txt"
BINARY="dist/SmartSearch.app/Contents/MacOS/SmartSearch"

exec > >(tee "$LOG") 2>&1

echo "=========================================="
echo " SmartSearch - Inhalt des Bundles pruefen"
echo " $(date '+%d.%m.%Y %H:%M:%S')"
echo "=========================================="
echo

if [ ! -f "$BINARY" ]; then
    echo "FEHLER: Kein gebautes Programm gefunden."
    exit 1
fi

# shellcheck disable=SC1091
[ -d venv ] && source venv/bin/activate

# ---------------------------------------------------------------------------
# Laeuft schon eine Kopie?
# ---------------------------------------------------------------------------
# Seit die Anwendung sich nur noch einmal starten laesst, wuerde ein
# "open dist/SmartSearch.app" bei bereits laufender Kopie einfach diese nach
# vorne holen - man testet dann versehentlich die ALTE Fassung und haelt sie
# fuer die neue. Deshalb hier vorher nachsehen.
if pgrep -f "SmartSearch.app/Contents/MacOS/SmartSearch" >/dev/null 2>&1; then
    printf "\033[1;31m%s\033[0m\n" "SmartSearch laeuft bereits."
    echo
    echo "  Bitte zuerst beenden: Lupensymbol in der Menueleiste anklicken"
    echo "  und 'Beenden' waehlen. Sonst wird die bereits laufende Fassung"
    echo "  nach vorne geholt statt der gerade gebauten."
    echo
    echo "  Danach dieses Skript erneut ausfuehren."
    exit 1
fi

echo "------------------------------------------"
echo " Bausteine im Bundle - echter Importtest"
echo "------------------------------------------"
echo
# Das gebaute Programm wird hier mit --selbsttest aufgerufen und
# importiert dabei alles, was es spaeter braucht. Das ist der einzige
# aussagekraeftige Test: er laeuft in genau der Umgebung, die auch beim
# Nutzer laeuft. Die frueher hier stehende Suche nach Zeichenketten im
# Archiv hat einen fehlenden Baustein durchgehen lassen - die App startete
# und scheiterte erst auf einem fremden Mac beim Laden des Suchmodells.
"$BINARY" --selbsttest
SELBSTTEST=$?
echo

if [ $SELBSTTEST -ne 0 ]; then
    echo "  ACHTUNG: Das Bundle ist unvollstaendig (siehe oben)."
    echo "  Diese Fassung darf nicht ausgeliefert werden."
    echo
fi

echo "------------------------------------------"
echo " Signatur und Bundle-Angaben"
echo "------------------------------------------"
echo
# Der frueher hier stehende zweite Test durchsuchte die Programmdatei nach
# Modulnamen als Zeichenketten. Das war doppelt unbrauchbar: Er hat einen
# echten Fehler durchgelassen (das fehlende torchgen), und er meldete
# umgekehrt reihenweise Bausteine als fehlend, die tatsaechlich im Bundle
# stecken - bei einem Bundle mit ausgelagerten Bibliotheken liegen die
# Module gar nicht in der Programmdatei. Ein Bericht, der bei einer
# einwandfreien App vierzehnmal "FEHLT" schreibt, verunsichert nur.
# Der Importtest oben beantwortet die Frage abschliessend.

codesign --verify --deep --verbose=2 dist/SmartSearch.app 2>&1 | sed 's/^/  /'
echo
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" \
    dist/SmartSearch.app/Contents/Info.plist 2>/dev/null \
    | sed 's/^/  Version: /'
du -sh dist/SmartSearch.app | sed 's/^/  Groesse: /'


echo
echo "------------------------------------------"
echo " Das Programm wird jetzt geoeffnet"
echo "------------------------------------------"
echo
echo " Bitte selbst pruefen:"
echo "   1. Mit Befehl-Umschalt-F das Fenster holen"
echo "   2. Nach etwas suchen, das sicher gefunden wird"
echo "   3. Ein Ergebnis per Doppelklick oeffnen"
echo
echo " Kommen Treffer, ist das Bundle vollstaendig."
echo

open dist/SmartSearch.app

echo "=========================================="
echo " Fenster kann geschlossen werden."
echo " (Bericht in pruef_log.txt)"
echo "=========================================="
