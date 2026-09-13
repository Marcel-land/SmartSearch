#!/bin/bash
#
# build.sh - Baut SmartSearch.app und daraus ein fertiges DMG zum Verteilen.
#
# Aufruf im Projektordner:
#     ./build.sh
#
# Das Skript macht der Reihe nach:
#   1. Voraussetzungen pruefen (venv, Pakete)
#   2. Alte Baureste entfernen
#   3. Mit PyInstaller das App-Bundle bauen
#   4. Ad-hoc signieren (siehe Erklaerung unten)
#   5. Ein DMG mit Programme-Verknuepfung erzeugen
#
# Nach dem Lauf liegt das Ergebnis in dist/ - die .app zum Selbsttesten
# und das DMG zum Weitergeben.

set -e

PROJEKT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJEKT"

NAME="SmartSearch"
VERSION="$(grep -m1 'APP_VERSION' gui.py | sed 's/[^0-9.]//g')"

# Bewusst OHNE Versionsnummer im Dateinamen.
#
# Der Downloadknopf auf der Website zeigt auf
#   .../releases/latest/download/SmartSearch.dmg
# GitHub loest "latest" selbst auf und liefert die Datei aus dem neuesten
# Release aus - aber nur, wenn sie immer gleich heisst. Mit
# "SmartSearch-1.0.1.dmg" muesste der Link bei jeder Fassung von Hand
# geaendert werden, und irgendwann vergisst man es und der Knopf zeigt
# ins Leere. Welche Version drinsteckt, steht im Release-Titel und in der
# App selbst.
DMG_NAME="${NAME}.dmg"

blau()  { printf "\033[1;34m%s\033[0m\n" "$1"; }
gruen() { printf "\033[1;32m%s\033[0m\n" "$1"; }
rot()   { printf "\033[1;31m%s\033[0m\n" "$1"; }

blau "SmartSearch $VERSION wird gebaut"
echo

# ---------------------------------------------------------------------------
# 1. Voraussetzungen
# ---------------------------------------------------------------------------
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
        echo "  venv aktiviert"
    else
        rot "Kein venv gefunden. Bitte zuerst anlegen und Pakete installieren."
        exit 1
    fi
fi

fehlt=""
for modul in PyInstaller sentence_transformers customtkinter pypdfium2; do
    python3 -c "import $modul" 2>/dev/null || fehlt="$fehlt $modul"
done
if [ -n "$fehlt" ]; then
    rot "Diese Pakete fehlen:$fehlt"
    echo "  pip install pyinstaller sentence-transformers customtkinter pypdfium2"
    exit 1
fi

# Vision ist kein harter Abbruchgrund - ohne das Paket laeuft die App, nur
# ohne Texterkennung fuer eingescannte PDF-Dateien. Da das eine beworbene
# Funktion ist, wird hier aber deutlich gewarnt.
if ! python3 -c "import Vision" 2>/dev/null; then
    rot "WARNUNG: pyobjc-framework-Vision fehlt."
    echo "  Ohne dieses Paket koennen eingescannte PDF-Dateien NICHT gelesen"
    echo "  werden - obwohl die Einfuehrung genau das verspricht."
    echo "  Beheben mit:  pip install pyobjc-framework-Vision"
    echo
    read -r -p "  Trotzdem weiterbauen? [j/N] " antwort
    [ "$antwort" = "j" ] || exit 1
fi

echo "  Alle Voraussetzungen erfuellt"
echo

# ---------------------------------------------------------------------------
# 2. Aufraeumen
# ---------------------------------------------------------------------------
blau "Alte Baureste entfernen"
rm -rf build dist "$DMG_NAME"
echo

# ---------------------------------------------------------------------------
# 3. Bauen
# ---------------------------------------------------------------------------
blau "PyInstaller laeuft (dauert einige Minuten)"
pyinstaller "${NAME}.spec" --noconfirm --log-level WARN
echo

if [ ! -d "dist/${NAME}.app" ]; then
    rot "Der Build hat kein App-Bundle erzeugt."
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. Signieren
# ---------------------------------------------------------------------------
# Ad-hoc-Signierung ("-" statt eines Zertifikats) ersetzt KEINE Beglaubigung
# durch Apple - der Nutzer muss die App beim ersten Start weiterhin ueber
# die Systemeinstellungen freigeben. Sie verhindert aber die Meldung
# "Die App ist beschaedigt und kann nicht geoeffnet werden", die auf
# Apple-Silicon-Macs sonst bei jedem unsignierten Bundle erscheint.
blau "App wird ad-hoc signiert"
codesign --force --deep --sign - "dist/${NAME}.app" 2>/dev/null
if codesign --verify --deep "dist/${NAME}.app" 2>/dev/null; then
    echo "  Signatur in Ordnung"
else
    rot "  Signatur konnte nicht geprueft werden - Build laeuft trotzdem weiter"
fi

# Das Quarantaene-Merkmal setzt macOS an alles, was aus dem Netz kommt.
# Auf dem eigenen Rechner stoert es beim Testen.
xattr -cr "dist/${NAME}.app" 2>/dev/null || true
echo

# ---------------------------------------------------------------------------
# 5. DMG bauen
# ---------------------------------------------------------------------------
blau "DMG wird erstellt"
STAGING="$(mktemp -d)"
cp -R "dist/${NAME}.app" "$STAGING/"
ln -s /Applications "$STAGING/Programme"
[ -f "INSTALLATION.md" ] && cp "INSTALLATION.md" "$STAGING/Bitte zuerst lesen.txt"
[ -f "LICENSE.txt" ] && cp "LICENSE.txt" "$STAGING/"

hdiutil create -volname "$NAME" -srcfolder "$STAGING" -ov -format UDZO \
    -quiet "$DMG_NAME"
rm -rf "$STAGING"
echo

# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------
APP_GROESSE="$(du -sh "dist/${NAME}.app" | cut -f1)"
DMG_GROESSE="$(du -sh "$DMG_NAME" | cut -f1)"

gruen "Fertig"
echo
echo "  App:  dist/${NAME}.app   ($APP_GROESSE)"
echo "  DMG:  ${DMG_NAME}   ($DMG_GROESSE)"
echo
echo "Naechste Schritte:"
echo "  1. Eigener Test:   open dist/${NAME}.app"
echo "  2. WICHTIG - auf einem ZWEITEN Mac testen, auf dem weder Python noch"
echo "     Homebrew installiert ist. Nur dort zeigt sich, ob wirklich alles"
echo "     im Bundle steckt."
echo "  3. Zum Weitergeben ausschliesslich das DMG verwenden."
