"""Misst die Suchqualitaet an den Testdokumenten und rechnet offen vor,
warum etwas gefunden wird oder nicht.

Aufruf (im Projektordner):

    venv/bin/python -m werkzeuge.such_diagnose --testdokumente
        DIE Messung: baut in einem eigenen, leeren Datenordner einen
        frischen Index aus tests/testdokumente (50 Dokumente) und prueft
        alle Suchfaelle aus tests/suchfaelle.py. Der echte Index der App
        bleibt unberuehrt.

    venv/bin/python -m werkzeuge.such_diagnose --testdokumente --klein
        nur die zehn urspruenglichen Dokumente und zwoelf Anfragen - zum
        Vergleich mit Messungen von vor September 2026 (docs/messungen).

    venv/bin/python -m werkzeuge.such_diagnose
        prueft den Index, mit dem die App gerade arbeitet.

    --ausfuehrlich
        zeigt je Anfrage ALLE Dokumente mit allen Zwischenwerten und der
        Regel, an der sie gescheitert sind. Nur so laesst sich sehen, wo
        die Schwellen in kern/suche.py sitzen muessen.

Welche Modelldatei benutzt wird, laesst sich fuer Messungen umstellen:
    SMARTSEARCH_MODELLDATEI=onnx/model.onnx venv/bin/python -m werkzeuge.such_diagnose --testdokumente

WAS "RICHTIG" HEISST
--------------------
Ob eine Anfrage richtig beantwortet wird, entscheidet hier dieselbe
Funktion, die auch die App benutzt (kern.suche.suche_intern). Frueher hat
dieses Werkzeug die Bewertung nachgebaut - dann misst es, wenn jemand die
Suche aendert und das Werkzeug vergisst, etwas anderes als die App. Die
Nachrechnung gibt es weiter, aber nur als Erklaerung (--ausfuehrlich), und
sie wird gegen die App geprueft.
"""
import os
import shutil
import sys
import tempfile
import time
from collections import defaultdict

# Muss VOR dem ersten Import aus smartsearch stehen: pfade.py legt den
# Datenordner beim Import fest.
TESTMODUS = "--testdokumente" in sys.argv
KLEIN = "--klein" in sys.argv
AUSFUEHRLICH = "--ausfuehrlich" in sys.argv
if TESTMODUS and not os.environ.get("SMARTSEARCH_DATENORDNER"):
    os.environ["SMARTSEARCH_DATENORDNER"] = tempfile.mkdtemp(prefix="smartsearch-messung-")

import numpy as np  # noqa: E402

from smartsearch.kern import modell as modell_modul  # noqa: E402
from smartsearch.kern import ocr  # noqa: E402
from smartsearch.kern import suche as s  # noqa: E402
from smartsearch.kern.index import gueltige_paare, index_mit_matrix  # noqa: E402
from smartsearch.kern.modell import geladenes_modell  # noqa: E402
from smartsearch.kern.pfade import INDEX_FILE, PROJEKT_ORDNER  # noqa: E402
from smartsearch.kern.sprache import anfrage_woerter, wort_trifft  # noqa: E402
from tests.suchfaelle import ALTE_FAELLE, ARTEN, FAELLE, URSPRUENGLICHE  # noqa: E402

TESTORDNER = os.path.join(PROJEKT_ORDNER, "tests", "testdokumente")
ANZEIGE_MAX = 10   # so viele Treffer zeigt die App hoechstens (suche_intern top_n)


# ---------------------------------------------------------------------------
# Index bauen
# ---------------------------------------------------------------------------

def _testindex_bauen():
    """Frischer Index im eigenen Datenordner. --klein: nur die zehn
    urspruenglichen Dokumente, dafuer in einen eigenen Ordner kopiert."""
    from smartsearch.kern import indexierung, ordner
    quelle = TESTORDNER
    if KLEIN:
        quelle = tempfile.mkdtemp(prefix="smartsearch-klein-")
        for name in URSPRUENGLICHE:
            shutil.copy2(os.path.join(TESTORDNER, name), quelle)
    ordner.befehl_ordner_hinzufuegen(quelle)
    start = time.time()
    indexierung.alles_indexieren([quelle], soll_abbrechen=lambda: False, melden=lambda e: None)
    return quelle, time.time() - start


# ---------------------------------------------------------------------------
# Bewertung
# ---------------------------------------------------------------------------

def _pruefen(fall, gezeigt):
    """(richtig?, Bemerkung, Fehlgriffe) fuer die Liste der angezeigten
    Dateinamen - in der Reihenfolge der App."""
    erlaubt = set(fall.erster) | set(fall.dabei) | set(fall.auch_ok)
    fehlgriffe = [n for n in gezeigt if n not in erlaubt]

    if fall.keine:
        if gezeigt:
            return False, f"sollte nichts zeigen, zeigt {len(gezeigt)}: {', '.join(gezeigt[:3])}", fehlgriffe
        return True, "", fehlgriffe

    fehler = []
    if fall.erster:
        if not gezeigt:
            fehler.append("kein Treffer")
        elif gezeigt[0] not in fall.erster:
            gesucht = next((d for d in fall.erster if d in gezeigt), None)
            if gesucht:
                fehler.append(f"{gesucht} erst auf Platz {gezeigt.index(gesucht) + 1}, "
                              f"davor {gezeigt[0]}")
            else:
                fehler.append(f"{' / '.join(fall.erster)} fehlt, vorn steht {gezeigt[0]}")
    fehlend = [d for d in fall.dabei if d not in gezeigt]
    if fehlend:
        fehler.append("fehlt: " + ", ".join(fehlend))
    return not fehler, "; ".join(fehler), fehlgriffe


def _nachrechnen(anfrage, vektor, werte, nach_datei):
    """Die Bewertung aus kern/suche.py Schritt fuer Schritt, fuer JEDES
    Dokument - auch die verworfenen, mit dem Grund. Nur zur Erklaerung."""
    woerter = anfrage_woerter(anfrage)
    zeilen = []
    for pfad, abschnitte in nach_datei.items():
        bester = max(float(werte[i]) if werte is not None
                     else float(np.dot(vektor, e["vektor"])) for i, e in abschnitte)
        dateiname = os.path.basename(pfad).lower()
        gesamttext = " ".join(e.get("text", "") for _, e in abschnitte).lower()
        gefunden = im_namen = 0
        for w in woerter:
            if wort_trifft(w, dateiname):
                gefunden += 1
                im_namen += 1
            elif wort_trifft(w, gesamttext):
                gefunden += 1
        sem_norm = (bester - s.SEMANTIK_UNTERGRENZE) / (s.SEMANTIK_OBERGRENZE - s.SEMANTIK_UNTERGRENZE)
        sem_norm = max(0.0, min(1.0, sem_norm))
        if woerter:
            stich = min(1.0, gefunden / len(woerter) + 0.15 * im_namen)
            gesamt = s.GEWICHT_SEMANTIK * sem_norm + s.GEWICHT_STICHWORT * stich
        else:
            stich, gesamt = 0.0, sem_norm
        grund = ""
        if woerter and gefunden == 0 and bester < s.SEMANTIK_MINDEST_OHNE_TREFFER:
            grund = f"Semantik-Sperre ({bester:.3f} < {s.SEMANTIK_MINDEST_OHNE_TREFFER})"
        elif gesamt <= s.SCORE_SCHWELLE:
            grund = "unter SCORE_SCHWELLE"
        zeilen.append([os.path.basename(pfad), bester, sem_norm, gefunden, len(woerter),
                       stich, gesamt, grund])
    zeilen.sort(key=lambda z: -z[6])
    ueberlebende = [z for z in zeilen if not z[7]]
    if ueberlebende:
        grenze = ueberlebende[0][6] * s.RELATIVER_ABSTAND
        for z in ueberlebende[1:]:
            if z[6] < grenze:
                z[7] = f"Abstandsregel (< {grenze:.3f})"
    gezeigt = [z for z in zeilen if not z[7]]
    for z in gezeigt[ANZEIGE_MAX:]:
        z[7] = f"nicht unter den ersten {ANZEIGE_MAX}"
    return woerter, zeilen


def _kurzname(name, breite=34):
    return name if len(name) <= breite else name[:breite - 1] + "…"


def hauptteil():
    print("=" * 78)
    print("SUCHDIAGNOSE")
    print("=" * 78)
    print(f"Modell    : {modell_modul.MODELL_NAME}")
    print(f"Datei     : {modell_modul.MODELL_DATEI}")
    print(f"Texterk.  : {ocr.verfuegbare_engine() or 'KEINE - Scans werden nicht gelesen'}")
    if TESTMODUS:
        t0 = time.time()
        geladenes_modell()
        print(f"Laden     : {time.time() - t0:.1f} s")
        quelle, dauer = _testindex_bauen()
        print(f"Testmodus : frischer Index aus {quelle}")
        print("            (eigener Datenordner, der echte Index bleibt unberuehrt)")
        print(f"Indexieren: {dauer:.1f} s")
    print(f"Indexdatei: {INDEX_FILE}")
    print()
    print("Geltende Werte (kern/suche.py):")
    print(f"  SCORE_SCHWELLE {s.SCORE_SCHWELLE} · SEMANTIK_MINDEST_OHNE_TREFFER "
          f"{s.SEMANTIK_MINDEST_OHNE_TREFFER} · SEMANTIK {s.SEMANTIK_UNTERGRENZE}–{s.SEMANTIK_OBERGRENZE}")
    print(f"  GEWICHT {s.GEWICHT_SEMANTIK}/{s.GEWICHT_STICHWORT} · RELATIVER_ABSTAND {s.RELATIVER_ABSTAND}")
    print()

    eintraege, matrix = index_mit_matrix()
    if not eintraege:
        print("Index ist leer oder unlesbar - bitte erst 'Index aktualisieren'.")
        return
    nach_datei = {}
    for i, e in gueltige_paare(list(enumerate(eintraege))):
        nach_datei.setdefault(e["datei"], []).append((i, e))
    if not nach_datei:
        print("Kein Eintrag gehoert zu einem ueberwachten Ordner, der noch existiert.")
        return
    im_index = {os.path.basename(p) for p in nach_datei}
    print(f"Dokumente im Index: {len(nach_datei)}   Textabschnitte: {len(eintraege)}")

    faelle = ALTE_FAELLE if KLEIN else FAELLE
    # Dokumente, die ein Fall erwartet, die aber gar nicht im Index sind -
    # z. B. ein Scan ohne Texterkennung. Vorher melden, sonst sucht man den
    # Fehler an der falschen Stelle.
    if TESTMODUS:
        erwartet = {d for f in faelle for d in f.erster + f.dabei}
        fehlen = sorted(erwartet - im_index)
        if fehlen:
            print(f"NICHT IM INDEX (kein Text gelesen?): {', '.join(fehlen)}")
    print()

    modell = geladenes_modell()
    ergebnisse = []   # (fall, richtig, bemerkung, fehlgriffe, gezeigt)
    roh_richtig, roh_uebrig = [], []
    zeiten = []
    abweichungen = []

    for fall in faelle:
        t0 = time.time()
        treffer = s.suche_intern(fall.anfrage, top_n=ANZEIGE_MAX) or []
        zeiten.append(time.time() - t0)
        gezeigt = [os.path.basename(a["datei"]) for _, a in treffer]
        richtig, bemerkung, fehlgriffe = _pruefen(fall, gezeigt)
        ergebnisse.append((fall, richtig, bemerkung, fehlgriffe, gezeigt))

        vektor = np.asarray(modell.encode([fall.anfrage], normalize_embeddings=True)[0], dtype="float32")
        werte = matrix @ vektor if matrix is not None else None
        woerter, zeilen = _nachrechnen(fall.anfrage, vektor, werte, nach_datei)
        if [z[0] for z in zeilen if not z[7]] != gezeigt:
            abweichungen.append(fall.anfrage)
        soll = set(fall.erster) | set(fall.dabei)
        for z in zeilen:
            (roh_richtig if z[0] in soll else roh_uebrig).append(z[1])

        # --- Ausgabe je Anfrage ------------------------------------------
        zeichen = "ok " if richtig else "XX "
        print(f"{zeichen}[{fall.art}] {fall.anfrage!r}  ->  {len(gezeigt)} Treffer"
              + (f", {len(fehlgriffe)} Fehlgriff(e)" if fehlgriffe else ""))
        if not richtig:
            print(f"      {bemerkung}")
        if AUSFUEHRLICH or not richtig:
            _tabelle(zeilen, woerter, soll, alle=AUSFUEHRLICH)

    _zusammenfassung(ergebnisse)
    _kalibrierung(roh_richtig, roh_uebrig, float(np.mean(zeiten)) if zeiten else 0.0)
    if abweichungen:
        print()
        print("WARNUNG: Die Nachrechnung weicht von der App ab bei:")
        for a in abweichungen:
            print(f"  {a!r}")
        print("  -> werkzeuge/such_diagnose.py (_nachrechnen) an kern/suche.py angleichen.")
        print("     Die Zaehlung oben stimmt trotzdem - sie kommt aus der App selbst.")


def _tabelle(zeilen, woerter, soll, alle):
    """Bei falschen Anfragen: die ersten Zeilen und jedes erwartete
    Dokument, damit man sieht, wo es haengen geblieben ist."""
    print(f"      Suchwoerter: {woerter}")
    print(f"      {'':2}{'Datei':34} {'roh':>6} {'semN':>6} {'wört':>5} {'gesamt':>7}  Status")
    for nr, (name, roh, semn, gef, anz, stich, ges, grund) in enumerate(zeilen):
        if not alle and nr >= 6 and name not in soll:
            continue
        markierung = "* " if name in soll else "  "
        status = "ANGEZEIGT" if not grund else "raus: " + grund
        print(f"      {markierung}{_kurzname(name):34} {roh:6.3f} {semn:6.3f} {gef:2d}/{anz:<2d} "
              f"{ges:7.3f}  {status}")
    print()


def _zusammenfassung(ergebnisse):
    """Die Zahlen, auf die es ankommt - ganz am Ende, damit sie im Terminal
    stehen bleiben."""
    print()
    print("=" * 78)
    richtig = sum(1 for _, ok, *_ in ergebnisse if ok)
    fehlgriffe = sum(len(f) for _, _, _, f, _ in ergebnisse)
    print(f"ERGEBNIS: {richtig} von {len(ergebnisse)} Anfragen richtig"
          f"   ·   {fehlgriffe} Fehlgriffe insgesamt")
    print("=" * 78)
    je_art = defaultdict(lambda: [0, 0, 0])
    for fall, ok, _, f, _ in ergebnisse:
        je_art[fall.art][0] += ok
        je_art[fall.art][1] += 1
        je_art[fall.art][2] += len(f)
    print(f"  {'Art':11} {'richtig':>9}  {'Fehlgriffe':>10}")
    for art in ARTEN:
        if art in je_art:
            r, n, fg = je_art[art]
            print(f"  {art:11} {r:>4} / {n:<3} {fg:>10}")
    falsch = [(fall, b) for fall, ok, b, _, _ in ergebnisse if not ok]
    if falsch:
        print()
        for fall, bemerkung in falsch:
            print(f"  FALSCH  [{fall.art}] {fall.anfrage!r}: {bemerkung}")
    print()
    print("Richtig = vorn steht das erwartete Dokument und alle Pflichtdokumente")
    print("sind dabei. Fehlgriff = angezeigt, obwohl es nicht dazugehoert.")
    print("Vor jeder Aenderung an Modell, Schwellen oder Aufteilung einmal messen,")
    print("danach vergleichen. Soll-Antworten: tests/suchfaelle.py")


def _kalibrierung(richtig, uebrig, zeit_je_anfrage):
    """Wo liegen die Rohwerte dieses Modells? Die Schwellen in
    kern/suche.py muessen zum Modell passen - jedes Modell hat seinen
    eigenen Bereich (BGE-M3: richtige 0,49-0,57, uebrige 0,30-0,47)."""
    if not richtig or not uebrig:
        return
    print()
    print("Rohwerte dieses Modells (Aehnlichkeit Anfrage <-> bester Abschnitt):")
    print(f"  erwartete Dokumente: {min(richtig):.3f} bis {max(richtig):.3f}  (Mittel {np.mean(richtig):.3f})")
    print(f"  uebrige Dokumente  : {min(uebrig):.3f} bis {max(uebrig):.3f}  (Mittel {np.mean(uebrig):.3f})")
    print(f"  Zeit je Suche      : {zeit_je_anfrage * 1000:.0f} ms (wie in der App, mit Bewertung)")


if __name__ == "__main__":
    hauptteil()
