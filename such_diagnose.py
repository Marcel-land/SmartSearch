"""Rechnet die Bewertung von suche_intern() offen vor.

Fuer jede Testanfrage wird JEDES Dokument aufgefuehrt - auch die, die
die Suche verwirft - zusammen mit allen Zwischenwerten und der Regel,
an der es gescheitert ist. Nur so laesst sich sehen, wo die Schwellen
sitzen muessen.

Aufruf:  venv/bin/python such_diagnose.py
"""
import os
import numpy as np

import search as s

ANFRAGEN = [
    "Vertrag",
    "Verträge",
    "Auto",
    "Fahrzeug",
    "Versicherung fürs Auto",
    "Unterlagen rund ums Fahrzeug",
    "Was zahle ich jeden Monat?",
    "Drucker",
    "Heizung gewartet",
    "Spende für die Steuererklärung",
    "Waschmaschine",
    "Strom",
]


def hauptteil():
    print("=" * 78)
    print("SUCHDIAGNOSE")
    print("=" * 78)
    print(f"Indexdatei: {s.INDEX_FILE}")
    print(f"vorhanden : {os.path.exists(s.INDEX_FILE)}")
    if os.path.exists(s.INDEX_FILE):
        import datetime
        stand = datetime.datetime.fromtimestamp(os.path.getmtime(s.INDEX_FILE))
        print(f"Stand     : {stand:%d.%m.%Y %H:%M}")
    print()
    print("Geltende Werte:")
    print(f"  SCORE_SCHWELLE                = {s.SCORE_SCHWELLE}")
    print(f"  SEMANTIK_MINDEST_OHNE_TREFFER = {s.SEMANTIK_MINDEST_OHNE_TREFFER}")
    print(f"  SEMANTIK_UNTERGRENZE          = {s.SEMANTIK_UNTERGRENZE}")
    print(f"  SEMANTIK_OBERGRENZE           = {s.SEMANTIK_OBERGRENZE}")
    print(f"  GEWICHT_SEMANTIK / STICHWORT  = {s.GEWICHT_SEMANTIK} / {s.GEWICHT_STICHWORT}")
    print(f"  RELATIVER_ABSTAND             = {s.RELATIVER_ABSTAND}")
    print()

    eintraege, matrix = s._index_mit_matrix()
    if not eintraege:
        print("Index ist leer oder unlesbar - bitte erst 'Index aktualisieren'.")
        return

    nach_datei = {}
    for i, e in enumerate(eintraege):
        nach_datei.setdefault(e["datei"], []).append((i, e))
    print(f"Dokumente im Index: {len(nach_datei)}   Textabschnitte: {len(eintraege)}")
    print()

    print("Modell wird geladen ...", flush=True)
    modell = s.geladenes_modell()
    print("geladen.\n")

    for anfrage in ANFRAGEN:
        woerter = s.anfrage_woerter(anfrage)
        vektor = np.asarray(
            modell.encode([anfrage], normalize_embeddings=True)[0], dtype="float32")
        werte = matrix @ vektor if matrix is not None else None

        zeilen = []
        for pfad, abschnitte in nach_datei.items():
            bester = -1.0
            for i, e in abschnitte:
                w = float(werte[i]) if werte is not None else float(np.dot(vektor, e["vektor"]))
                bester = max(bester, w)

            dateiname = os.path.basename(pfad).lower()
            gesamttext = " ".join(e.get("text", "") for _, e in abschnitte).lower()
            gefunden = 0
            im_namen = 0
            for w in woerter:
                if w in dateiname:
                    gefunden += 1; im_namen += 1
                elif w in gesamttext:
                    gefunden += 1

            sem_norm = (bester - s.SEMANTIK_UNTERGRENZE) / (
                s.SEMANTIK_OBERGRENZE - s.SEMANTIK_UNTERGRENZE)
            sem_norm = max(0.0, min(1.0, sem_norm))

            if woerter:
                stich = min(1.0, gefunden / len(woerter) + 0.15 * im_namen)
                gesamt = s.GEWICHT_SEMANTIK * sem_norm + s.GEWICHT_STICHWORT * stich
            else:
                stich = 0.0
                gesamt = sem_norm

            grund = ""
            if woerter and gefunden == 0 and bester < s.SEMANTIK_MINDEST_OHNE_TREFFER:
                grund = f"Semantik-Sperre ({bester:.3f} < {s.SEMANTIK_MINDEST_OHNE_TREFFER})"
            elif gesamt <= s.SCORE_SCHWELLE:
                grund = "unter SCORE_SCHWELLE"
            zeilen.append([os.path.basename(pfad), bester, sem_norm,
                           gefunden, len(woerter), stich, gesamt, grund])

        zeilen.sort(key=lambda z: -z[6])
        ueberlebende = [z for z in zeilen if not z[7]]
        if ueberlebende:
            grenze = ueberlebende[0][6] * s.RELATIVER_ABSTAND
            for z in ueberlebende[1:]:
                if z[6] < grenze:
                    z[7] = f"Abstandsregel (< {grenze:.3f})"

        gezeigt = sum(1 for z in zeilen if not z[7])
        print("-" * 78)
        print(f"ANFRAGE: {anfrage!r}")
        print(f"  Suchwoerter: {woerter}")
        print(f"  ergibt {gezeigt} Treffer")
        print(f"  {'Datei':26} {'roh':>6} {'semN':>6} {'wört':>6} {'stichN':>7} {'gesamt':>7}  Status")
        for name, roh, semn, gef, anz, stich, ges, grund in zeilen:
            status = "ANGEZEIGT" if not grund else "raus: " + grund
            print(f"  {name:26} {roh:6.3f} {semn:6.3f} {gef:3d}/{anz:<2d} "
                  f"{stich:7.3f} {ges:7.3f}  {status}")
        print()


if __name__ == "__main__":
    hauptteil()
