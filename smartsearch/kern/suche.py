#!/usr/bin/env python3
"""
suche.py - die eigentliche Suche: eine Anfrage bewerten und die besten
Dokumente liefern, sowie "aehnliche Dokumente" zu einer Datei.

Die Bewertung mischt zwei Signale: inhaltliche Naehe (Vektor des Modells)
und woertliche Uebereinstimmung (sprache.py). Alle Schwellenwerte unten
sind gemessen - werkzeuge/such_diagnose.py rechnet sie jederzeit nach.
"""

import datetime
import os
import time

from smartsearch.kern.pfade import INDEX_FILE
from smartsearch.kern.index import gueltige_paare, index_mit_matrix, nur_gueltige_eintraege
from smartsearch.kern.modell import geladenes_modell
from smartsearch.kern.sprache import anfrage_woerter, wort_trifft

# Score-Schwelle für suche_intern(): Treffer unterhalb dieses kombinierten
# Semantik+Keyword-Scores werden verworfen. Empirisch ermittelt (v3.x):
# alles darunter waren in Tests fast immer thematisch irrelevante Treffer.
SCORE_SCHWELLE = 0.15

# ------------------------------------------------------------------
# ALLE WERTE HIER UNTEN SIND GEMESSEN, NICHT GESCHAETZT.
#
# Am 14.09.2026 wurden zwoelf Anfragen gegen die zehn Demo-Dokumente
# durchgerechnet und fuer JEDES Dokument der rohe Aehnlichkeitswert
# festgehalten (such_diagnose.py erzeugt diese Tabelle jederzeit neu).
# Ergebnis der alten Einstellung: von den erwarteten Treffern fehlten
# elf. "Verträge", "Drucker", "Waschmaschine" und "Spende fuer die
# Steuererklaerung" ergaben ueberhaupt nichts, obwohl fuer jede dieser
# Anfragen ein eindeutig passendes Dokument im Index liegt.
#
# Die Ursache war eine falsche Annahme ueber das Modell: die frueheren
# Kommentare gingen von Werten um 0,6 fuer unverwandte und bis 0,82 fuer
# sehr aehnliche Texte aus. Gemessen liegt der gesamte Wertebereich auf
# diesen Dokumenten zwischen 0,30 und 0,64 - passende Dokumente bei
# 0,49 bis 0,57, unverwandte bei 0,30 bis 0,47. Alle Grenzen standen
# also ueber dem Bereich, in dem die richtigen Antworten liegen.
#
# Mit den Werten unten und der Wortform-Erkennung in _wort_trifft()
# wird in derselben Messung jeder erwartete Treffer gefunden.
#
# NEU EINGESTELLT AM 28.09.2026 FUER granite-embedding (kern/modell.py).
# Jedes Modell hat seinen eigenen Wertebereich - die BGE-M3-Werte oben
# passen nicht mehr. Gemessen mit such_diagnose --testdokumente:
#     richtige Dokumente 0,785 bis 0,871, uebrige 0,670 bis 0,823,
#     gesamter Bereich 0,67 bis 0,87 (BGE-M3: 0,30 bis 0,64).
# Eine Rasterpruefung ueber 600 Kombinationen (Untergrenze 0,62-0,74,
# Obergrenze 0,84-0,90, Sperre 0,70-0,79, Abstand 0,55-0,80, Gewichte
# 0,65/0,75) ergab ueberall 11 von 12, ausser bei einer Sperre ab 0,79 -
# die Einstellung sitzt also nicht auf einer Messerkante. Innerhalb dieses
# Plateaus sind die Werte so gewaehlt, dass moeglichst wenige unpassende
# Dokumente mit angezeigt werden: 21 Treffer ueber alle zwoelf Anfragen
# (BGE-M3 vorher: 24). Einziger Fehler: "Auto" zeigt die Kfz-Versicherung
# vor dem Kaufvertrag - beide sind richtig, nur die Reihenfolge weicht von
# der Soll-Antwort ab. Dafuer findet "Drucker" jetzt die Rechnung ueber das
# Multifunktionssystem an erster Stelle, woran BGE-M3 scheiterte.
# Messprotokoll: docs/messungen/.
# ------------------------------------------------------------------

# 1. Enthaelt ein Dokument KEINES der Suchwoerter woertlich, muss es
#    semantisch ueberzeugen. Ein Dokument zu finden, in dem das gesuchte
#    Wort GAR NICHT vorkommt, ist der eigentliche Zweck dieser Anwendung -
#    wer "Drucker" sucht, soll auch die Rechnung finden, auf der
#    "Multifunktionssystem" steht. Genau dieser Fall scheiterte vorher:
#    die Rechnung kam auf 0,417 und lag damit unter der alten Sperre von
#    0,60. Der neue Wert liegt unter allen gemessenen richtigen Treffern
#    und ueber dem, was das Modell fuer voellig fremde Texte liefert.
SEMANTIK_MINDEST_OHNE_TREFFER = 0.75   # BGE-M3: 0.40

# Nutzbarer Wertebereich des Modells auf echten Dokumenten. Auf diesen
# Bereich wird der rohe Aehnlichkeitswert gespreizt, bevor er mit der
# Stichwortwertung verrechnet wird. Stimmt der Bereich nicht, wird die
# Semantik rechnerisch kleingehalten und die woertliche Suche gewinnt
# immer - vorher lag die Spreizung bei 0,42 bis 0,82, also fast
# vollstaendig oberhalb der tatsaechlichen Werte.
SEMANTIK_UNTERGRENZE = 0.72   # BGE-M3: 0.32
SEMANTIK_OBERGRENZE = 0.87    # BGE-M3: 0.62

# Verhaeltnis von inhaltlicher zu woertlicher Uebereinstimmung. Wer ein
# Wort eintippt, das woertlich im Dokument steht, erwartet es weit oben -
# deshalb wiegt die Stichwortwertung weiter mit. Sie darf aber nicht so
# schwer wiegen, dass ein woertlicher Treffer alle sinngemaessen
# Treffer aus der Liste draengt: genau das passierte bei 0,45.
GEWICHT_SEMANTIK = 0.65
GEWICHT_STICHWORT = 0.35

# 2. Alles, was klar hinter dem besten Treffer zurueckbleibt, fliegt raus.
#    Selbstjustierend: bei einer guten Anfrage bleiben mehrere Treffer
#    stehen, bei einer schlechten nur der beste - oder gar keiner. Diese
#    Regel erledigt die eigentliche Auslese; die absoluten Schwellen oben
#    halten nur noch offensichtlichen Unsinn fern.
RELATIVER_ABSTAND = 0.75   # BGE-M3: 0.65


def _zeitraum_cutoff(zeitraum):
    """Wandelt eine Zeitraum-Auswahl der GUI in einen Unix-Timestamp um,
    ab dem eine Datei als 'im Zeitraum' gilt. None = kein Filter.

    Erwartet einen SPRACHUNABHÄNGIGEN Code ("alle"/"7_tage"/"monat"/"jahr"),
    keinen angezeigten Text - seit es die App auf Deutsch UND Englisch gibt,
    würde ein Vergleich gegen den sichtbaren Menütext (z.B. "7 Tage") in der
    englischen Oberfläche ("7 Days") nie mehr treffen. Die GUI übersetzt die
    Auswahl in oberflaeche/hauptfenster.py (zeitraum_anzeige_zu_code) in einen dieser Codes, bevor sie
    hier ankommt."""
    if not zeitraum or zeitraum == "alle":
        return None

    heute = datetime.date.today()
    if zeitraum == "7_tage":
        return time.time() - 7 * 86400
    elif zeitraum == "monat":
        start = datetime.date(heute.year, heute.month, 1)
        return time.mktime(start.timetuple())
    elif zeitraum == "jahr":
        start = datetime.date(heute.year, 1, 1)
        return time.mktime(start.timetuple())
    return None


def suche_intern(anfrage, top_n=10, ausgeschlossene_typen=None, zeitraum=None):
    if not os.path.exists(INDEX_FILE):
        return None

    import numpy as np

    # Index aus dem Arbeitsspeicher statt von der Platte - siehe
    # index_mit_matrix(). Jeder Eintrag behaelt seine Position im
    # Gesamtindex, weil darueber gleich der fertig berechnete
    # Aehnlichkeitswert abgegriffen wird.
    alle_eintraege, matrix = index_mit_matrix()
    if not alle_eintraege:
        return []

    paare = list(enumerate(alle_eintraege))

    # Nur Treffer aus Ordnern, die JETZT ueberwacht werden, und nur
    # Dateien, die es noch gibt (siehe gueltige_paare).
    paare = gueltige_paare(paare)

    if ausgeschlossene_typen:
        paare = [
            (i, e) for i, e in paare
            if os.path.splitext(e["datei"])[1].lower() not in ausgeschlossene_typen
        ]

    cutoff = _zeitraum_cutoff(zeitraum)
    if cutoff is not None:
        paare = [(i, e) for i, e in paare if e.get("geaendert", 0) >= cutoff]

    if not paare:
        return []

    modell = geladenes_modell()
    anfrage_vektor = np.asarray(
        modell.encode([anfrage], normalize_embeddings=True)[0], dtype="float32")
    such_woerter = anfrage_woerter(anfrage)

    # EINE Matrixmultiplikation fuer den gesamten Index statt eines
    # np.dot() je Textabschnitt. Faellt die Matrix aus (alter Index mit
    # uneinheitlichen Vektoren), wird wie frueher einzeln gerechnet.
    if matrix is not None:
        alle_werte = matrix @ anfrage_vektor
    else:
        alle_werte = None

    # ------------------------------------------------------------------
    # Bewertung auf DOKUMENTEBENE, nicht je Textabschnitt.
    #
    # Der Fehler vorher: Jeder 700-Zeichen-Abschnitt wurde einzeln bewertet,
    # auch bei der Stichwortsuche. Bei einer Rechnung steht "Rechnung" aber
    # im Briefkopf und die Artikelbezeichnung ("Drucker", ein Modellname)
    # weiter unten in der Positionsliste - also in einem ANDEREN Abschnitt.
    # Kein einzelner Abschnitt enthielt beide Suchwoerter, deshalb bekam das
    # Dokument nie die volle Stichwort-Wertung und landete hinter
    # thematisch aehnlichen Dokumenten, die gar keines der Woerter
    # enthielten.
    #
    # Jetzt gilt: der semantische Wert stammt vom BESTEN Abschnitt, die
    # Stichwort-Wertung vom GESAMTEN Dokument.
    # ------------------------------------------------------------------
    nach_datei = {}
    for i, e in paare:
        eintrag_liste = nach_datei.setdefault(e["datei"], [])
        eintrag_liste.append((i, e))

    rohe_treffer = []
    for pfad, abschnitte in nach_datei.items():
        bester_abschnitt = None
        bester_semantik = -1.0
        for i, e in abschnitte:
            if alle_werte is not None:
                wert = float(alle_werte[i])
            else:
                wert = float(np.dot(anfrage_vektor, e["vektor"]))
            if wert > bester_semantik:
                bester_semantik = wert
                bester_abschnitt = e

        dateiname = os.path.basename(pfad).lower()
        gesamttext = " ".join(e.get("text", "") for _, e in abschnitte).lower()

        gefundene_woerter = 0
        im_dateinamen = 0
        if such_woerter:
            for w in such_woerter:
                if wort_trifft(w, dateiname):
                    gefundene_woerter += 1
                    im_dateinamen += 1
                elif wort_trifft(w, gesamttext):
                    gefundene_woerter += 1

        # Semantik auf 0..1 spreizen. BGE-M3 liefert selbst fuer voellig
        # unverwandte Texte noch Werte um 0,55 - der rohe Wert nutzt also
        # nur einen schmalen Ausschnitt der Skala. Ohne diese Spreizung
        # faellt ein Unterschied von 0,05 gegenueber der Stichwortwertung
        # kaum ins Gewicht, obwohl er inhaltlich erheblich ist.
        semantik_norm = (bester_semantik - SEMANTIK_UNTERGRENZE) / (
            SEMANTIK_OBERGRENZE - SEMANTIK_UNTERGRENZE)
        semantik_norm = max(0.0, min(1.0, semantik_norm))

        if such_woerter:
            stichwort_norm = gefundene_woerter / len(such_woerter)
            # Steht ein Wort im Dateinamen, ist das ein besonders klares
            # Signal - ein Mensch benennt Dateien nach ihrem Zweck.
            stichwort_norm = min(1.0, stichwort_norm + 0.15 * im_dateinamen)
        else:
            stichwort_norm = 0.0

        if such_woerter:
            gesamt_score = (GEWICHT_SEMANTIK * semantik_norm
                            + GEWICHT_STICHWORT * stichwort_norm)
        else:
            gesamt_score = semantik_norm

        # Kein einziges Suchwort im gesamten Dokument und semantisch nur
        # mittelmaessig - dann lieber nichts anzeigen als etwas Falsches.
        if such_woerter and gefundene_woerter == 0 and bester_semantik < SEMANTIK_MINDEST_OHNE_TREFFER:
            continue

        if gesamt_score > SCORE_SCHWELLE:
            rohe_treffer.append((gesamt_score, bester_abschnitt))

    rohe_treffer.sort(key=lambda x: x[0], reverse=True)

    # Abstand zum besten Treffer auswerten - siehe RELATIVER_ABSTAND.
    if rohe_treffer:
        mindestwert = rohe_treffer[0][0] * RELATIVER_ABSTAND
        rohe_treffer = [p for p in rohe_treffer if p[0] >= mindestwert]

    return rohe_treffer[:top_n]


def aehnliche_dateien(pfad, top_n=10):
    """Findet Dateien, die INHALTLICH ähnlich zu 'pfad' sind - per
    Vektor-Ähnlichkeit statt nur Dateiname-Textsuche.

    Nutzt den bereits vorhandenen Embedding-Vektor der Datei aus dem Index
    (kein neuer API-Call/keine neue Berechnung nötig) und vergleicht ihn
    per Kosinus-Ähnlichkeit (Skalarprodukt, da alle Vektoren normalisiert
    sind) gegen alle anderen indexierten Dateien.

    Gibt eine Liste von (score, eintrag) zurück, im selben Format wie
    suche_intern(), damit die GUI dieselbe Ergebnisanzeige wiederverwenden
    kann. None, wenn die Datei nicht (mit Vektor) im Index ist.
    """
    if not os.path.exists(INDEX_FILE):
        return None

    import numpy as np

    pfad = os.path.abspath(os.path.expanduser(pfad))

    # Denselben Arbeitsspeicher-Index benutzen wie die Suche.
    eintraege, _ = index_mit_matrix()
    eintraege = nur_gueltige_eintraege(eintraege)

    eigene_vektoren = [e["vektor"] for e in eintraege if e["datei"] == pfad]
    if not eigene_vektoren:
        return None

    # Bei mehreren Textabschnitten derselben Datei: Durchschnittsvektor als
    # Repräsentation der ganzen Datei verwenden.
    referenz_vektor = np.mean(eigene_vektoren, axis=0)
    referenz_vektor = referenz_vektor / np.linalg.norm(referenz_vektor)

    rohe_treffer = []
    for e in eintraege:
        if e["datei"] == pfad:
            continue  # Datei nicht mit sich selbst vergleichen
        score = float(np.dot(referenz_vektor, e["vektor"]))
        rohe_treffer.append((score, e))

    rohe_treffer.sort(key=lambda x: x[0], reverse=True)

    gesehene_dateien = set()
    eindeutige_ergebnisse = []
    for score, eintrag in rohe_treffer:
        datei_pfad = eintrag["datei"]
        if datei_pfad not in gesehene_dateien:
            gesehene_dateien.add(datei_pfad)
            eindeutige_ergebnisse.append((score, eintrag))
        if len(eindeutige_ergebnisse) >= top_n:
            break

    return eindeutige_ergebnisse
