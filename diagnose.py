#!/usr/bin/env python3
"""Diagnose-Skript: prüft, ob eine bestimmte Datei im SmartSearch-Index ist."""
import pickle
import sys
import os

INDEX_PFAD = os.path.expanduser("~/Downloads/smartsearch_aktuell/index.pkl")
GESUCHTE_DATEI = sys.argv[1] if len(sys.argv) > 1 else None

if not GESUCHTE_DATEI:
    print("Kein Dateipfad übergeben - liste stattdessen alle Dateien im Index auf,")
    print("bei denen das Lesen fehlgeschlagen ist (ohne_inhalt-Flag):\n")
    if not os.path.exists(INDEX_PFAD):
        print(f"Index-Datei nicht gefunden unter: {INDEX_PFAD}")
        sys.exit(1)
    with open(INDEX_PFAD, "rb") as f:
        eintraege = pickle.load(f)
    problematische = [e for e in eintraege if e.get("ohne_inhalt")]
    if not problematische:
        print("Keine Datei mit 'ohne_inhalt'-Flag gefunden.")
    else:
        for e in problematische:
            print(f"  - {e['datei']}")
    print("\nTipp: Skript mit Dateipfad aufrufen, um EINE Datei genau zu prüfen:")
    print('  python3.14 diagnose.py "/pfad/zur/datei.pdf"')
    sys.exit(0)

GESUCHTE_DATEI = os.path.abspath(os.path.expanduser(GESUCHTE_DATEI))

if not os.path.exists(INDEX_PFAD):
    print(f"Index-Datei nicht gefunden unter: {INDEX_PFAD}")
    sys.exit(1)

with open(INDEX_PFAD, "rb") as f:
    eintraege = pickle.load(f)

treffer = [e for e in eintraege if e["datei"] == GESUCHTE_DATEI]

if not treffer:
    print(f"❌ Diese Datei ist GAR NICHT im Index: {GESUCHTE_DATEI}")
    print("-> Wurde der Ordner wirklich hinzugefügt und 'Index aktualisieren' geklickt?")
else:
    print(f"✅ Datei ist im Index ({len(treffer)} Abschnitt(e)):")
    for e in treffer:
        hat_vektor = "vektor" in e
        text_laenge = len(e.get("text", ""))
        ohne_inhalt = e.get("ohne_inhalt", False)
        print(f"  - Vektor vorhanden: {hat_vektor} | Textlänge: {text_laenge} | ohne_inhalt-Flag: {ohne_inhalt}")
        if text_laenge > 0:
            print(f"    Textanfang: {e['text'][:150]!r}")
