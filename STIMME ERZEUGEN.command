#!/bin/bash
# Erzeugt die Sprachaufnahme fuer das TikTok-Video mit einer der in macOS
# eingebauten Stimmen. Ergebnis landet als stimme.aiff neben dieser Datei.
#
# Doppelklick genuegt. Danach die Datei in den Chat ziehen.

cd "$(dirname "$0")" || exit 1

TEXT="Ich wusste nicht mehr, wie die Datei heißt. \
Also hab ich mir eine Suche gebaut, die liest, was drinsteht — nicht, wie die Datei heißt. \
Ich tippe einfach, worum es geht. Und da ist sie. \
Die App ist jetzt draußen. Ihr könnt sie euch ab sofort auf smartsearch app punkt com holen. \
Kostenlos, läuft komplett offline auf eurem Mac."

echo "Verfuegbare deutsche Stimmen auf diesem Mac:"
say -v '?' | grep de_DE | tee stimmen.txt
echo

# Die erste vorhandene aus dieser Rangfolge nehmen - die vorderen klingen
# deutlich natuerlicher, sind aber nicht auf jedem Mac installiert.
STIMME=""
for kandidat in "Markus (Premium)" "Anna (Premium)" "Petra (Premium)" \
                "Markus (Enhanced)" "Anna (Enhanced)" "Yannick" "Markus" "Anna"; do
  if say -v '?' | grep -q "^$kandidat "; then STIMME="$kandidat"; break; fi
done

if [ -z "$STIMME" ]; then
  echo "Keine deutsche Stimme gefunden."
  echo "Systemeinstellungen > Bedienungshilfen > Gesprochene Inhalte > Systemstimme"
  echo "dort eine deutsche Stimme laden, dann diese Datei erneut doppelklicken."
  read -n 1 -s -r -p "Taste druecken zum Schliessen"; exit 1
fi

echo "Benutze Stimme: $STIMME"
say -v "$STIMME" -r 168 -o stimme.aiff "$TEXT"

if [ -f stimme.aiff ]; then
  DAUER=$(afinfo stimme.aiff | awk -F': ' '/estimated duration/ {printf "%.1f", $2}')
  echo
  echo "Fertig: stimme.aiff  (${DAUER} Sekunden)"
  echo "Liegt im Ordner smartsearch_aktuell."
else
  echo "Es wurde keine Datei erzeugt."
fi

echo
read -n 1 -s -r -p "Taste druecken zum Schliessen"
