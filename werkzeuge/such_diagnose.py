"""Rechnet die Bewertung von suche_intern() offen vor.

Fuer jede Testanfrage wird JEDES Dokument aufgefuehrt - auch die, die
die Suche verwirft - zusammen mit allen Zwischenwerten und der Regel,
an der es gescheitert ist. Nur so laesst sich sehen, wo die Schwellen
sitzen muessen.

Aufruf (im Projektordner):  venv/bin/python -m werkzeuge.such_diagnose
"""
import os
import numpy as np

from smartsearch.kern import suche as s

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

# ---------------------------------------------------------------------------
# SOLL-ANTWORTEN
#
# Welches Dokument MUSS bei einer Anfrage an erster Stelle stehen. Ohne diese
# Angabe zeigt die Diagnose nur, WAS gefunden wurde - ob es RICHTIG war, muss
# man dann bei jedem Lauf im Kopf nachhalten. Beim Wechsel des Suchmodells ist
# das der Unterschied zwischen einer Messung und einem Gefuehl.
#
# Inhalt der zehn Demo-Dokumente (nachgelesen, nicht geraten):
#   Neues_Dokument_7.pdf    Kaufvertrag ueber einen gebrauchten PKW
#   dok_2024_02_18.pdf      Kfz-Versicherungsschein
#   Scan_20231114_0003.pdf  Mietvertrag ueber einen Garagenstellplatz
#   Scan2019-03-22_112.pdf  Auftragsbestaetigung Internet und Telefon
#   20220906_0001.pdf       Jahresabrechnung Strom
#   IMG_4471.pdf            Wartungsprotokoll Gasbrennwerttherme
#   Unbenannt-3.pdf         Garantiebestaetigung Waschvollautomat
#   CCF_000141.pdf          Spendenbescheinigung
#   0027_2607_001.pdf       Rechnung ueber ein Multifunktionssystem
#   0044_1802_002.pdf       Reisekostenabrechnung
#
# None bedeutet: mehrere Dokumente sind gleichermassen richtig, dann wird
# stattdessen geprueft, ob ALLE Dokumente aus MINDESTENS_DABEI gefunden wurden.
# ---------------------------------------------------------------------------

ERSTER_TREFFER = {
    "Vertrag": None,
    "Verträge": None,
    "Auto": "Neues_Dokument_7.pdf",
    "Fahrzeug": "Neues_Dokument_7.pdf",
    "Versicherung fürs Auto": "dok_2024_02_18.pdf",
    "Unterlagen rund ums Fahrzeug": "Neues_Dokument_7.pdf",
    "Was zahle ich jeden Monat?": "Scan_20231114_0003.pdf",
    "Drucker": "0027_2607_001.pdf",
    "Heizung gewartet": "IMG_4471.pdf",
    "Spende für die Steuererklärung": "CCF_000141.pdf",
    "Waschmaschine": "Unbenannt-3.pdf",
    "Strom": "20220906_0001.pdf",
}

# Diese Dokumente muessen unter den Treffern sein, egal an welcher Stelle.
MINDESTENS_DABEI = {
    "Vertrag": ["Neues_Dokument_7.pdf", "Scan_20231114_0003.pdf",
                "Scan2019-03-22_112.pdf"],
    "Verträge": ["Neues_Dokument_7.pdf", "Scan_20231114_0003.pdf",
                 "Scan2019-03-22_112.pdf"],
}


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

    bewertung = []   # (anfrage, bestanden, bemerkung)

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
            # WICHTIG: dieselbe Pruefung wie in search.suche_intern().
            # Hier stand frueher ein einfaches "w in text". Damit hat die
            # Diagnose etwas anderes gemessen als die Suche tatsaechlich
            # tut: "Vertraege" galt hier als nicht gefunden, obwohl die
            # Suche ueber die Grundform "Vertrag" sehr wohl trifft, und
            # "Auto" galt als gefunden, obwohl es nur in
            # "Waschvollautomat" mitten im Wort steckt. Wer die Grenzwerte
            # nach so einer Tabelle einstellt, stellt sie nach falschen
            # Zahlen ein.
            for w in woerter:
                if s.wort_trifft(w, dateiname):
                    gefunden += 1; im_namen += 1
                elif s.wort_trifft(w, gesamttext):
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

        # --- Abgleich mit der Soll-Antwort --------------------------------
        treffer_namen = [z[0] for z in zeilen if not z[7]]
        soll = ERSTER_TREFFER.get(anfrage)
        pflicht = MINDESTENS_DABEI.get(anfrage, [])
        if soll:
            if not treffer_namen:
                bestanden, bemerkung = False, f"kein Treffer, erwartet war {soll}"
            elif treffer_namen[0] == soll:
                bestanden, bemerkung = True, ""
            elif soll in treffer_namen:
                bestanden = False
                bemerkung = (f"{soll} nur auf Platz "
                             f"{treffer_namen.index(soll) + 1}, "
                             f"davor {treffer_namen[0]}")
            else:
                bestanden, bemerkung = False, f"{soll} fehlt ganz"
        elif pflicht:
            fehlend = [d for d in pflicht if d not in treffer_namen]
            bestanden = not fehlend
            bemerkung = "" if bestanden else "fehlt: " + ", ".join(fehlend)
        else:
            bestanden, bemerkung = True, "(keine Soll-Antwort hinterlegt)"
        bewertung.append((anfrage, bestanden, bemerkung))

        print("-" * 78)
        print(f"ANFRAGE: {anfrage!r}")
        print(f"  Suchwoerter: {woerter}")
        print(f"  ergibt {gezeigt} Treffer")
        print(f"  Soll       : {'RICHTIG' if bestanden else 'FALSCH - ' + bemerkung}")
        print(f"  {'Datei':26} {'roh':>6} {'semN':>6} {'wört':>6} {'stichN':>7} {'gesamt':>7}  Status")
        for name, roh, semn, gef, anz, stich, ges, grund in zeilen:
            status = "ANGEZEIGT" if not grund else "raus: " + grund
            print(f"  {name:26} {roh:6.3f} {semn:6.3f} {gef:3d}/{anz:<2d} "
                  f"{stich:7.3f} {ges:7.3f}  {status}")
        print()

    _zusammenfassung(bewertung)


def _zusammenfassung(bewertung):
    """Die eine Zahl, auf die es ankommt - ganz am Ende, damit sie im
    Terminal stehen bleibt."""
    richtig = sum(1 for _, ok, _ in bewertung if ok)
    print("=" * 78)
    print(f"ERGEBNIS: {richtig} von {len(bewertung)} Anfragen richtig")
    print("=" * 78)
    for anfrage, ok, bemerkung in bewertung:
        if not ok:
            print(f"  FALSCH  {anfrage!r}: {bemerkung}")
    if richtig == len(bewertung):
        print("  Alle Anfragen liefern das erwartete Dokument an erster Stelle.")
    print()
    print("Diese Zahl ist der Massstab. Vor jeder Aenderung an Modell,")
    print("Schwellenwerten oder Chunking einmal notieren, danach vergleichen.")


if __name__ == "__main__":
    hauptteil()
