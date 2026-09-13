#!/bin/bash
#
# FEHLER AUSLESEN.command
#
# Schreibt den Fehlerspeicher der Anwendung in eine Datei im
# Projektordner, damit er von aussen einsehbar ist. Der Index selbst
# liegt in der Benutzerbibliothek und ist von dort nicht erreichbar.
#
# Per Doppelklick oeffnen. Das Ergebnis steht in fehlerspeicher.txt.

cd "$(dirname "$0")" || exit 1
exec > >(tee fehlerspeicher.txt) 2>&1

echo "=========================================="
echo " SmartSearch - Fehlerspeicher"
echo " $(date '+%d.%m.%Y %H:%M:%S')"
echo "=========================================="
echo

[ -d venv ] && source venv/bin/activate

python3 - <<'PYEOF'
import os, pickle, collections
from pfade import INDEX_FILE, DATEN_ORDNER

print(f"Datenordner: {DATEN_ORDNER}")
if not os.path.exists(INDEX_FILE):
    print("\nKein Index vorhanden. Bitte einmal 'Index aktualisieren' ausfuehren.")
    raise SystemExit(0)

groesse = os.path.getsize(INDEX_FILE) / 1_000_000
print(f"Index:       {groesse:.1f} MB\n")

with open(INDEX_FILE, "rb") as f:
    eintraege = pickle.load(f)

dateien = {e["datei"] for e in eintraege}
mit_vektor = {e["datei"] for e in eintraege if "vektor" in e}
ohne = sorted({e["datei"] for e in eintraege if e.get("ohne_inhalt")})

print(f"Abschnitte:        {len(eintraege)}")
print(f"Dateien gesamt:    {len(dateien)}")
print(f"davon durchsuchbar:{len(mit_vektor)}")
print(f"nicht lesbar:      {len(ohne)}")
print()

# Verteilung nach Dateityp - zeigt, ob ein Format komplett fehlt.
nach_typ = collections.Counter(os.path.splitext(d)[1].lower() or "(ohne)" for d in dateien)
print("Nach Dateityp:")
for endung, anzahl in nach_typ.most_common():
    print(f"  {endung:8s} {anzahl}")
print()

if ohne:
    print("NICHT LESBARE DATEIEN")
    print("-" * 42)
    # Nach vermutlicher Ursache gruppieren.
    gruppen = collections.defaultdict(list)
    for d in ohne:
        name = os.path.basename(d)
        endung = os.path.splitext(d)[1].lower()
        if not os.path.exists(d):
            gruppen["Datei existiert nicht mehr"].append(d)
        elif name.startswith("~$"):
            gruppen["Sperrdatei von Word/Excel"].append(d)
        elif ".download" in d:
            gruppen["Abgebrochener Download"].append(d)
        elif endung == ".pdf":
            try:
                mb = os.path.getsize(d) / 1_000_000
                gruppen[f"PDF ohne erkennbaren Text (Scan?)"].append(f"{d}  [{mb:.1f} MB]")
            except OSError:
                gruppen["PDF, Groesse nicht lesbar"].append(d)
        else:
            gruppen[f"Sonstiges ({endung})"].append(d)

    for ursache, liste in sorted(gruppen.items(), key=lambda x: -len(x[1])):
        print(f"\n{ursache} ({len(liste)}):")
        for eintrag in liste:
            print(f"  {eintrag}")
else:
    print("Keine unlesbaren Dateien.")

print()
print("Anteil durchsuchbarer Dateien: "
      f"{100 * len(mit_vektor) / max(len(dateien), 1):.1f} %")
PYEOF

echo
echo "=========================================="
echo " Fenster kann geschlossen werden."
echo " (Bericht in fehlerspeicher.txt)"
echo "=========================================="
