#!/usr/bin/env python3
"""
diagnose.py - Werkzeug zur Fehlersuche im SmartSearch-Index.

Beantwortet die Frage, die bei "die Suche findet meine Datei nicht" immer
zuerst geklaert werden muss: Ist die Datei ueberhaupt im Index, und wenn
ja, mit welchem Text?

Aufrufe:

    python3.14 diagnose.py                      Ueberblick + nicht lesbare Dateien
    python3.14 diagnose.py drucker              Sucht "drucker" in Namen und Text
    python3.14 diagnose.py --datei /pfad.pdf    Prueft eine bestimmte Datei
    python3.14 diagnose.py --scores "drucker rechnung"
                                                Zeigt, wie die Suche bewertet
"""

import os
import pickle
import sys

from pfade import INDEX_FILE


def lade():
    if not os.path.exists(INDEX_FILE):
        print(f"Kein Index gefunden unter:\n  {INDEX_FILE}\n")
        print("Starten Sie SmartSearch und waehlen Sie 'Index aktualisieren'.")
        sys.exit(1)
    with open(INDEX_FILE, "rb") as f:
        return pickle.load(f)


def ueberblick(eintraege):
    dateien = {e["datei"] for e in eintraege}
    mit_vektor = {e["datei"] for e in eintraege if "vektor" in e}
    ohne_inhalt = sorted({e["datei"] for e in eintraege if e.get("ohne_inhalt")})

    print(f"Index:            {INDEX_FILE}")
    print(f"Abschnitte:       {len(eintraege)}")
    print(f"Dateien gesamt:   {len(dateien)}")
    print(f"davon durchsuchbar: {len(mit_vektor)}")
    print()

    # Verteilung nach Dateityp - zeigt schnell, ob ein ganzes Format fehlt.
    nach_typ = {}
    for d in dateien:
        endung = os.path.splitext(d)[1].lower() or "(ohne)"
        nach_typ[endung] = nach_typ.get(endung, 0) + 1
    print("Nach Dateityp:")
    for endung, anzahl in sorted(nach_typ.items(), key=lambda x: -x[1]):
        print(f"  {endung:8s} {anzahl}")
    print()

    if ohne_inhalt:
        print(f"NICHT LESBAR ({len(ohne_inhalt)}):")
        for d in ohne_inhalt:
            print(f"  {d}")
        print()
        print("Diese Dateien tauchen in keiner Suche auf. Uebliche Ursachen:")
        print("  - Beschaedigtes oder unvollstaendig geladenes PDF")
        print("  - Reiner Scan ohne Texterkennung (pyobjc-framework-Vision fehlt)")
        print("  - Temporaere Sperrdatei von Word/Excel (Name beginnt mit ~$)")
    else:
        print("Keine unlesbaren Dateien.")


def suche_begriff(eintraege, begriff):
    begriff = begriff.lower()
    im_namen, im_text = [], []

    for e in eintraege:
        pfad = e["datei"]
        if begriff in os.path.basename(pfad).lower() and pfad not in im_namen:
            im_namen.append(pfad)
        elif begriff in e.get("text", "").lower() and pfad not in im_text:
            im_text.append(pfad)

    print(f'Suche nach "{begriff}" im Index\n')
    print(f"Im DATEINAMEN ({len(im_namen)}):")
    for p in im_namen[:25]:
        print(f"  {p}")
    if not im_namen:
        print("  keine")
    print()
    print(f"Im TEXTINHALT ({len(im_text)}):")
    for p in im_text[:25]:
        print(f"  {p}")
    if not im_text:
        print("  keine")

    if not im_namen and not im_text:
        print()
        print("Der Begriff kommt im Index nicht vor. Das heisst entweder:")
        print("  - die Datei liegt in keinem ueberwachten Ordner,")
        print("  - sie wurde noch nicht indexiert,")
        print("  - oder ihr Inhalt konnte nicht gelesen werden (siehe Aufruf ohne Argument).")


def pruefe_datei(eintraege, pfad):
    pfad = os.path.abspath(os.path.expanduser(pfad))
    treffer = [e for e in eintraege if e["datei"] == pfad]

    if not treffer:
        print(f"Diese Datei ist NICHT im Index:\n  {pfad}\n")
        print("Pruefen Sie, ob ihr Ordner unter 'Ordner verwalten' eingetragen ist,")
        print("und lassen Sie den Index anschliessend aktualisieren.")
        return

    print(f"Im Index, {len(treffer)} Abschnitt(e):\n  {pfad}\n")
    for i, e in enumerate(treffer, 1):
        text = e.get("text", "")
        print(f"  Abschnitt {i}: Vektor={'ja' if 'vektor' in e else 'NEIN'}, "
              f"Zeichen={len(text)}, nicht lesbar={e.get('ohne_inhalt', False)}")
        if text:
            print(f"    Beginn: {text[:160]!r}")


def zeige_scores(anfrage, anzahl=15):
    """Fuehrt eine echte Suche aus und zeigt die Bewertung der besten
    Treffer - so laesst sich unterscheiden, ob eine Datei fehlt oder nur
    schlecht bewertet wird."""
    import search as smart_search

    print(f'Bewertung fuer "{anfrage}"\n')
    ergebnisse = smart_search.suche_intern(anfrage, top_n=anzahl)
    if not ergebnisse:
        print("Keine Treffer oberhalb der Schwelle.")
        return
    for score, e in ergebnisse:
        print(f"  {score:.3f}  {os.path.basename(e['datei'])}")


if __name__ == "__main__":
    argumente = sys.argv[1:]

    if not argumente:
        ueberblick(lade())
    elif argumente[0] == "--datei" and len(argumente) > 1:
        pruefe_datei(lade(), argumente[1])
    elif argumente[0] == "--scores" and len(argumente) > 1:
        zeige_scores(" ".join(argumente[1:]))
    else:
        suche_begriff(lade(), " ".join(argumente))
