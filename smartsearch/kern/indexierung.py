#!/usr/bin/env python3
"""
indexierung.py - Dateien einlesen und in den Index aufnehmen.

aktualisiere_index() arbeitet EINEN Ordner ab (nur neue und geaenderte
Dateien). alles_indexieren() ist der komplette Lauf ueber alle
ueberwachten Ordner, wie ihn die Oberflaeche anstoesst - mit Modell-
Download, Fortschritt, Restzeit, Abbruch und anschliessendem Aufraeumen.
Die Oberflaeche zeigt nur noch an, was hier gemeldet wird.
"""

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

from smartsearch.kern.dateien import dateien_im_ordner, in_abschnitte_teilen, lies_datei
from smartsearch.kern.index import bereinige_index, lade_bestehenden_index, speichere_index
from smartsearch.kern.modell import geladenes_modell, modell_ist_vorhanden

# Anzahl paralleler Threads beim Einlesen der Dateien (Text-Extraktion/OCR).
# Diese Arbeit ist größtenteils I/O bzw. läuft in C-Bibliotheken
# (pdfplumber, Tesseract), die während der Arbeit die Python-GIL freigeben -
# paralleles Lesen bringt hier also einen echten Geschwindigkeitsgewinn,
# unabhängig vom CPU-Modus des KI-Modells (siehe lade_modell()).
LESE_THREADS = 4


def aktualisiere_index(ordner, modell=None, still=False, fortschritt_fn=None):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    alle_eintraege = lade_bestehenden_index()

    eintraege_dieser_ordner = [e for e in alle_eintraege if e["datei"].startswith(ordner + os.sep)]
    andere_eintraege = [e for e in alle_eintraege if not e["datei"].startswith(ordner + os.sep)]

    bekannt = {e["datei"]: e.get("geaendert", 0) for e in eintraege_dieser_ordner}
    aktuelle_dateien = set(dateien_im_ordner(ordner))
    zu_verarbeiten = [p for p in aktuelle_dateien if p not in bekannt or os.path.getmtime(p) > bekannt[p]]

    eintraege_dieser_ordner = [
        e for e in eintraege_dieser_ordner
        if e["datei"] in aktuelle_dateien and e["datei"] not in zu_verarbeiten
    ]

    if not zu_verarbeiten:
        ergebnis = andere_eintraege + eintraege_dieser_ordner
        speichere_index(ergebnis)
        return ergebnis

    if modell is None:
        modell = geladenes_modell()

    neue_eintraege = []

    def _datei_verarbeiten(pfad):
        geaendert = os.path.getmtime(pfad)
        text = lies_datei(pfad)
        return pfad, geaendert, text

    fertig_zaehler = 0
    with ThreadPoolExecutor(max_workers=LESE_THREADS) as pool:
        for pfad, geaendert, text in pool.map(_datei_verarbeiten, zu_verarbeiten):
            fertig_zaehler += 1
            if fortschritt_fn:
                fortschritt_fn(fertig_zaehler, os.path.basename(pfad))

            if not text or not text.strip():
                # Datei konnte nicht gelesen werden oder ist leer (z.B.
                # kaputtes PDF, gescanntes Dokument ohne erkennbaren Text).
                # Trotzdem als "verarbeitet" markieren (mit geaendert-
                # Zeitstempel, aber ohne Vektor), damit sie beim nächsten
                # Lauf nicht erneut - erfolglos - verarbeitet wird. In der
                # Suche taucht sie wegen des fehlenden Vektors nicht auf
                # (siehe suche_intern-Filter). Über fehlgeschlagene_dateien()
                # kann man diese Liste einsehen, über
                # entferne_fehlgeschlagene_markierung() einen Neuversuch
                # erzwingen (z.B. nach nachträglicher OCR-Installation).
                neue_eintraege.append({
                    "datei": pfad,
                    "text": "",
                    "text_fuer_analyse": None,
                    "geaendert": geaendert,
                    "ohne_inhalt": True,
                })
                continue

            dateiname_ohne_endung = os.path.splitext(os.path.basename(pfad))[0]

            for abschnitt in in_abschnitte_teilen(text):
                text_fuer_analyse = f"Dokument: {dateiname_ohne_endung}\nInhalt: {abschnitt}"
                neue_eintraege.append({
                    "datei": pfad,
                    "text": abschnitt,
                    "text_fuer_analyse": text_fuer_analyse,
                    "geaendert": geaendert,
                })

    # KI-Vektoren in kleinen Batches berechnen statt alles auf einmal.
    # Vorher wurde modell.encode() einmal für ALLE gesammelten Textabschnitte
    # aufgerufen - bei vielen Dateien konnte das (besonders im CPU-Modus,
    # siehe lade_modell()) mehrere Minuten dauern, OHNE dass die GUI
    # währenddessen einen Fortschritt anzeigen konnte. Es sah dann so aus,
    # als sei die App eingefroren. Jetzt wird in Batches gerechnet und nach
    # jedem Batch fortschritt_fn(None, ...) aufgerufen, damit die GUI eine
    # eigene, laufende Statusmeldung für diese Phase zeigen kann.
    # Zwischenspeicherung alle SPEICHER_INTERVALL Batches - ermöglicht
    # "Suchen während der Indexierung": statt bis zum kompletten Abschluss
    # (kann bei vielen Dateien über eine Stunde dauern) zu warten, kann man
    # schon nach den ersten fertig verarbeiteten Batches danach suchen,
    # während der Rest im Hintergrund weiterläuft.
    SPEICHER_INTERVALL = 3
    BATCH_GROESSE = 16
    zu_kodierende = [e for e in neue_eintraege if e.get("text_fuer_analyse")]
    if zu_kodierende:
        gesamt_batches = math.ceil(len(zu_kodierende) / BATCH_GROESSE)
        for batch_start in range(0, len(zu_kodierende), BATCH_GROESSE):
            batch = zu_kodierende[batch_start:batch_start + BATCH_GROESSE]
            texte = [e["text_fuer_analyse"] for e in batch]
            vektoren = modell.encode(texte, show_progress_bar=False, normalize_embeddings=True)
            for e, v in zip(batch, vektoren):
                e["vektor"] = v
                del e["text_fuer_analyse"]

            aktueller_batch = batch_start // BATCH_GROESSE + 1
            if fortschritt_fn:
                # idx=None signalisiert: das ist die Berechnungs-Phase, nicht
                # ein neu gelesenes Dokument. Uebergeben werden die Zahlen,
                # nicht ein fertiger Satz - frueher stand hier ein deutscher
                # Text, den die Oberflaeche per Suchmuster wieder zerlegte,
                # und in der englischen Oberflaeche erschien er auf Deutsch.
                fortschritt_fn(None, (aktueller_batch, gesamt_batches))

            ist_letzter_batch = aktueller_batch == gesamt_batches
            if aktueller_batch % SPEICHER_INTERVALL == 0 or ist_letzter_batch:
                fertige_eintraege = [
                    e for e in neue_eintraege
                    if "vektor" in e or e.get("ohne_inhalt")
                ]
                zwischenstand = andere_eintraege + eintraege_dieser_ordner + fertige_eintraege
                speichere_index(zwischenstand)

    for e in neue_eintraege:
        e.pop("text_fuer_analyse", None)

    eintraege_dieser_ordner.extend(neue_eintraege)
    gesamt = andere_eintraege + eintraege_dieser_ordner
    speichere_index(gesamt)

    return gesamt


def alles_indexieren(ordner_liste, soll_abbrechen, melden):
    """Der komplette Indexlauf ueber alle ueberwachten Ordner.

    soll_abbrechen()  -> True, sobald der Nutzer abbrechen will. Wird
                         zwischen zwei Ordnern abgefragt.
    melden(ereignis)  -> bekommt den Fortschritt als Woerterbuch:

        {"art": "modell_download_start"}
        {"art": "modell_download", "anteil": 0..1, "geladen": Bytes, "gesamt": Bytes}
        {"art": "datei", "anteil": 0..1, "n": 3, "gesamt": 120, "name": "...",
         "restzeit_sek": 95.0}
        {"art": "vektoren", "batch": 4, "batches": 9, "restzeit_sek": 30.0}

    Rueckgabe: True, wenn der Lauf vollstaendig war, False bei Abbruch.

    Wirft modell.ModellDownloadFehler / modell.ProgrammUnvollstaendig,
    wenn das Modell nicht geladen werden kann - die Oberflaeche erklaert
    diese beiden Faelle eigens.

    Stand vorher in gui.py (_index_bg) und war dort mit dem Zeichnen der
    Statuszeile verwoben. Jetzt rechnet diese Funktion, die Oberflaeche
    zeigt nur an - bei der Umstellung auf eine neue Oberflaeche bleibt sie
    unveraendert.
    """
    # Beim allerersten Start muss erst das KI-Modell geladen werden
    # (einmalig ca. 2,3 GB). Ohne sichtbaren Fortschritt sieht die App
    # dabei minutenlang aus, als haenge sie - deshalb wird der Download
    # genauso gemeldet wie spaeter die Indexierung.
    def modell_fortschritt(geladen, gesamt):
        anteil = min(geladen / gesamt, 0.99) if gesamt else 0
        melden({"art": "modell_download", "anteil": anteil,
                "geladen": geladen, "gesamt": gesamt})

    if not modell_ist_vorhanden():
        melden({"art": "modell_download_start"})

    modell = geladenes_modell(fortschritt_fn=modell_fortschritt)

    # Gesamtzahl vorab zaehlen, fuer einen korrekten Prozentwert ueber alle
    # Ordner hinweg.
    alle_dateien = []
    for o in ordner_liste:
        if os.path.exists(o):
            alle_dateien.extend(dateien_im_ordner(o))

    gesamt = len(alle_dateien)
    if gesamt == 0:
        return True

    zaehler = {"n": 0}
    start_zeit = time.time()
    batch_phase_start = {"zeit": None}

    def fortschritt(idx, info):
        if idx is None:
            # KI-Berechnungsphase (Batch X von Y), kein neu gelesenes
            # Dokument. Restzeit anhand des Batch-Fortschritts schaetzen.
            aktueller_batch, gesamt_batches = info
            if batch_phase_start["zeit"] is None:
                batch_phase_start["zeit"] = time.time()
            vergangen = time.time() - batch_phase_start["zeit"]
            rest_sek = None
            if aktueller_batch > 0:
                rest_sek = vergangen / aktueller_batch * (gesamt_batches - aktueller_batch)
            melden({"art": "vektoren", "batch": aktueller_batch,
                    "batches": gesamt_batches, "restzeit_sek": rest_sek})
            return
        zaehler["n"] += 1
        vergangen = time.time() - start_zeit
        melden({
            "art": "datei",
            "anteil": min(zaehler["n"] / gesamt, 1.0),
            "n": zaehler["n"],
            "gesamt": gesamt,
            "name": info,
            "restzeit_sek": vergangen / zaehler["n"] * (gesamt - zaehler["n"]),
        })

    for o in ordner_liste:
        if soll_abbrechen():
            return False
        if not os.path.exists(o):
            continue
        aktualisiere_index(o, modell=modell, still=True, fortschritt_fn=fortschritt)

    # Karteileichen entfernen: Eintraege aus Ordnern, die nicht mehr
    # ueberwacht werden, und Dateien, die es nicht mehr gibt. Ohne das
    # waechst index.pkl endlos und liefert Treffer aus laengst entfernten
    # Ordnern.
    try:
        bereinige_index()
    except Exception as e:
        print(f"[Index] Aufraeumen uebersprungen: {e}")
    return True
