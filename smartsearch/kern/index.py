#!/usr/bin/env python3
"""
index.py - der gespeicherte Suchindex (index.pkl): lesen, schreiben,
aufraeumen und fuer die Suche im Arbeitsspeicher bereithalten.

Ein Eintrag ist ein Textabschnitt einer Datei:
    {"datei": Pfad, "text": Abschnitt, "vektor": Zahlenfolge,
     "geaendert": Zeitstempel, "ohne_inhalt": True nur bei unlesbaren Dateien}
"""

import json
import os
import pickle
import threading

from smartsearch.kern.pfade import INDEX_FILE
from smartsearch.kern.modell import MODELL_NAME
from smartsearch.kern.einstellungen import ueberwachte_ordner

# Formatstand der Indexdatei. Wird hochgezaehlt, wenn sich der AUFBAU eines
# Eintrags aendert - nicht bei jeder Programmfassung.
#
# WARUM es das ueberhaupt gibt: Die Vektoren im Index stammen aus einem
# bestimmten Modell und sind nur mit Vektoren DESSELBEN Modells
# vergleichbar. Wird MODELL_NAME gewechselt - das ist bereits zweimal
# passiert - liefert ein alter Index keine Fehlermeldung, sondern
# stillschweigend falsche Treffer. Deshalb stehen Modellname und
# Formatstand seit Format 2 mit in der Datei und werden beim Laden
# geprueft. Passt etwas nicht, wird der Index verworfen und neu gebaut.
INDEX_FORMAT = 2

# Modellname und Formatstand stehen NEBEN der Indexdatei, nicht darin.
#
# Fassung 1.0.3 hatte sie in die index.pkl selbst geschrieben, als
# Woerterbuch statt als Liste. Das ging in eine Richtung gut und in die
# andere schief: eine aeltere Fassung liest die Datei weiterhin als Liste,
# laeuft dann ueber die Schluessel des Woerterbuchs und stuerzt beim Start
# ab. Ein Update, nach dem die vorherige Fassung nicht mehr startet, ist
# keine Option - schon gar nicht, wenn man zurueckrollen koennen muss.
#
# Deshalb bleibt index.pkl eine reine Liste, wie sie es immer war, und die
# Angaben wandern in eine kleine Datei daneben. Aeltere Fassungen sehen sie
# nicht und arbeiten wie gewohnt; neuere lesen sie und wissen Bescheid.
# Fehlt sie, gilt der Index als unbekannt und wird einmal neu gebaut.
INDEX_META_FILE = INDEX_FILE + ".meta.json"


# Wird auf True gesetzt, sobald ein nicht passender Index verworfen wurde -
# damit die Oberflaeche einmal darauf hinweisen kann statt gar nicht.
_index_verworfen = False


def _meta_lesen():
    """Die Angaben neben dem Index - leer, wenn es sie nicht gibt."""
    try:
        with open(INDEX_META_FILE, encoding="utf-8") as f:
            inhalt = json.load(f)
        return inhalt if isinstance(inhalt, dict) else {}
    except Exception:
        return {}


def _meta_schreiben():
    """Schreibt Modellname und Formatstand neben den Index.

    Wird NACH der Indexdatei geschrieben. Geht dabei etwas schief, gilt der
    Index beim naechsten Start als unbekannt und wird neu gebaut - der
    Fehler kostet also Rechenzeit, aber er kann keine falschen Treffer
    erzeugen. Andersherum waere es gefaehrlich.
    """
    try:
        temp_pfad = INDEX_META_FILE + ".tmp"
        with open(temp_pfad, "w", encoding="utf-8") as f:
            json.dump({"format": INDEX_FORMAT, "modell": MODELL_NAME}, f)
        os.replace(temp_pfad, INDEX_META_FILE)
    except Exception as e:
        print(f"[Index] Begleitdatei nicht schreibbar: {e}")


def _index_datei_lesen():
    """Liest index.pkl und gibt (eintraege, passend) zurueck.

    passend ist False, wenn die Datei mit einem anderen Modell oder in
    einem aelteren Format geschrieben wurde. Die Eintraege werden trotzdem
    mitgegeben; was damit geschieht, entscheidet der Aufrufer.
    """
    with open(INDEX_FILE, "rb") as f:
        inhalt = pickle.load(f)

    # Uebergangsfall: Fassung 1.0.3 hat die Angaben in die Datei selbst
    # geschrieben. Solche Indexdateien bleiben lesbar, damit niemand ohne
    # Grund neu indexieren muss.
    if isinstance(inhalt, dict) and "eintraege" in inhalt:
        passend = (inhalt.get("format") == INDEX_FORMAT
                   and inhalt.get("modell") == MODELL_NAME)
        return inhalt.get("eintraege") or [], passend

    eintraege = inhalt if isinstance(inhalt, list) else []
    meta = _meta_lesen()
    passend = (meta.get("format") == INDEX_FORMAT
               and meta.get("modell") == MODELL_NAME)
    return eintraege, passend


def index_ist_fremd():
    """True, wenn eine Indexdatei da ist, die nicht zum aktuellen Modell passt.

    Die Oberflaeche fragt das beim Start ab, um einmal darauf hinzuweisen
    und die Neuindexierung anzustossen - sonst stuende der Benutzer vor
    einer Suche, die grundlos nichts findet.
    """
    if not os.path.exists(INDEX_FILE):
        return False
    try:
        _, passend = _index_datei_lesen()
        return not passend
    except Exception:
        # Unlesbare Datei: wird beim naechsten Indexlauf ohnehin ersetzt.
        return True


def lade_bestehenden_index():
    """Die gespeicherten Eintraege - oder eine leere Liste, wenn der Index
    nicht zum aktuellen Suchmodell passt.

    Leer heisst fuer die Indexierung: alles neu einlesen. Genau das ist
    gewollt, denn Vektoren aus einem anderen Modell sind unbrauchbar.
    """
    global _index_verworfen
    if not os.path.exists(INDEX_FILE):
        return []
    try:
        eintraege, passend = _index_datei_lesen()
    except Exception as e:
        print(f"[Index] Datei nicht lesbar, wird neu aufgebaut: {e}")
        return []
    if not passend:
        if not _index_verworfen:
            print(f"[Index] Passt nicht zum Modell {MODELL_NAME} - wird neu aufgebaut.")
        _index_verworfen = True
        return []
    return eintraege


def speichere_index(eintraege):
    """Speichert den Index atomar: erst in eine temporäre Datei schreiben,
    dann per os.replace() an die Stelle der echten Datei verschieben.

    WICHTIG für die "Suche während der Indexierung"-Funktion: Ohne das
    könnte eine parallel laufende Suche exakt in dem Moment lesen, in dem
    hier gerade geschrieben wird, und eine unvollständige/kaputte Datei
    erwischen. os.replace() ist auf demselben Dateisystem atomar - Leser
    sehen immer entweder die alte oder die neue vollständige Datei, nie
    einen Zwischenzustand.
    """
    global _index_verworfen

    temp_pfad = INDEX_FILE + ".tmp"
    with open(temp_pfad, "wb") as f:
        pickle.dump(eintraege, f)
    os.replace(temp_pfad, INDEX_FILE)

    # Erst danach die Angaben daneben - siehe INDEX_META_FILE oben.
    _meta_schreiben()
    _index_verworfen = False


def fehlgeschlagene_dateien():
    """Gibt die Liste aller Dateipfade zurück, die beim letzten
    Indexierungslauf nicht gelesen werden konnten (ohne_inhalt-Flag).

    Für die "⚠️ X Dateien nicht lesbar"-Anzeige in der GUI, damit sowas
    nicht mehr stillschweigend im Terminal verschwindet.
    """
    eintraege = lade_bestehenden_index()
    gesehen = set()
    ergebnis = []
    for e in eintraege:
        if e.get("ohne_inhalt") and e["datei"] not in gesehen:
            gesehen.add(e["datei"])
            ergebnis.append(e["datei"])
    return sorted(ergebnis)


def entferne_fehlgeschlagene_markierung():
    """Entfernt alle 'ohne_inhalt'-Einträge komplett aus dem Index.

    Danach werden diese Dateien beim nächsten aktualisiere_index()-Lauf
    ganz normal erneut versucht (z.B. sinnvoll, nachdem man OCR
    nachinstalliert hat). Gibt die Anzahl der entfernten Einträge zurück.
    """
    eintraege = lade_bestehenden_index()
    verbleibend = [e for e in eintraege if not e.get("ohne_inhalt")]
    entfernt = len(eintraege) - len(verbleibend)
    if entfernt:
        speichere_index(verbleibend)
    return entfernt


# ------------------------------------------------------------------
# GUELTIGKEIT VON INDEX-EINTRAEGEN
#
# Der Index (index.pkl) ist ein Langzeitspeicher: einmal eingelesene
# Dateien bleiben dort stehen, bis sie ausdruecklich entfernt werden.
# Was in der config.json steht, ist dagegen die AKTUELLE Auswahl des
# Nutzers. Beides kann auseinanderlaufen - ein Ordner wird entfernt, eine
# Datei geloescht oder verschoben. Wird das beim Suchen nicht abgeglichen,
# zeigt SmartSearch Treffer aus Ordnern, die der Nutzer laengst entfernt
# hat. Deshalb laeuft jede Suche durch gueltige_paare() bzw.
# nur_gueltige_eintraege().
#
# Die Regel "liegt in einem ueberwachten Ordner UND existiert noch" stand
# frueher dreimal fast gleich im Code (Suche, aehnliche Dokumente,
# Aufraeumen). Jetzt steht sie einmal in _gueltigkeitspruefer().
# ------------------------------------------------------------------

def _liegt_in_ordnern(pfad, ordner_liste):
    for o in ordner_liste:
        if pfad == o or pfad.startswith(o + os.sep):
            return True
    return False


def _gueltigkeitspruefer():
    """Liefert eine Funktion pfad -> True/False, oder None, wenn gerade
    gar kein Ordner ueberwacht wird.

    Ob eine Datei existiert, wird je Pfad nur einmal nachgesehen - eine
    Datei hat meist viele Abschnitte, und jeder Blick auf die Platte kostet.
    """
    ordner_liste = ueberwachte_ordner()
    if not ordner_liste:
        return None

    existiert = {}

    def ist_gueltig(pfad):
        if not _liegt_in_ordnern(pfad, ordner_liste):
            return False
        if pfad not in existiert:
            existiert[pfad] = os.path.exists(pfad)
        return existiert[pfad]

    return ist_gueltig


def gueltige_paare(paare):
    """Wie nur_gueltige_eintraege, arbeitet aber auf (Position, Eintrag)-
    Paaren. Die Position wird fuer den Zugriff auf die Vektormatrix
    gebraucht (siehe index_mit_matrix)."""
    ist_gueltig = _gueltigkeitspruefer()
    if ist_gueltig is None:
        return []
    return [(i, e) for i, e in paare if ist_gueltig(e["datei"])]


def nur_gueltige_eintraege(eintraege):
    """Filtert eine frisch geladene Index-Liste auf das, was gerade zaehlt.

    Bewusst nur gefiltert und NICHT gespeichert: eine Suche darf den Index
    nie veraendern (es kann parallel indexiert werden). Das echte
    Aufraeumen uebernimmt bereinige_index() nach dem Indexlauf.
    """
    ist_gueltig = _gueltigkeitspruefer()
    if ist_gueltig is None:
        return []
    return [e for e in eintraege if ist_gueltig(e["datei"])]


def entferne_ordner_aus_index(ordner):
    """Loescht alle Index-Eintraege unterhalb von 'ordner'.

    Rueckgabe: Anzahl der entfernten Eintraege (Textabschnitte, nicht
    Dateien).
    """
    ordner = os.path.abspath(os.path.expanduser(ordner))
    eintraege = lade_bestehenden_index()
    uebrig = [
        e for e in eintraege
        if not (e["datei"] == ordner or e["datei"].startswith(ordner + os.sep))
    ]
    if len(uebrig) != len(eintraege):
        speichere_index(uebrig)
    return len(eintraege) - len(uebrig)


def bereinige_index():
    """Wirft alles aus dem Index, was nicht mehr gilt: Eintraege ausserhalb
    der ueberwachten Ordner und Dateien, die es nicht mehr gibt.

    Wird nach jedem Indexlauf aufgerufen, damit die Datei nicht endlos
    waechst und keine Karteileichen enthaelt.
    """
    eintraege = lade_bestehenden_index()
    if not eintraege:
        return 0

    uebrig = nur_gueltige_eintraege(eintraege)

    if len(uebrig) != len(eintraege):
        speichere_index(uebrig)
    return len(eintraege) - len(uebrig)


_such_cache = None                  # (kennung, eintraege, matrix)
_such_cache_lock = threading.Lock()

# Oberhalb dieser Groesse wird der Index NICHT im Arbeitsspeicher
# behalten - ein Suchwerkzeug darf nicht mehrere Gigabyte belegen, nur um
# ein paar Zehntelsekunden zu sparen.
CACHE_OBERGRENZE_BYTES = 1_500_000_000


def index_mit_matrix():
    """Gibt (eintraege, matrix) zurueck - den Index im Arbeitsspeicher.

    WARUM: Vorher las JEDE Suche die komplette index.pkl neu von der
    Platte und rechnete das Skalarprodukt anschliessend in einer
    Python-Schleife, einmal pro Textabschnitt. Beides waechst mit der
    Anzahl indexierter Dateien - bei einem groesseren Index vergehen
    dadurch mehrere Sekunden, bevor ueberhaupt gerechnet wird, und zwar
    bei jeder einzelnen Suche.

    Jetzt wird die Datei nur dann neu gelesen, wenn sie sich seit dem
    letzten Mal geaendert hat (Zeitstempel + Groesse), und alle Vektoren
    liegen zusaetzlich als eine einzige Zahlenmatrix bereit. Der Vergleich
    mit der Suchanfrage ist damit EINE Matrixmultiplikation statt
    zehntausender Einzelaufrufe.

    Der Zeitstempel-Vergleich ist die Verbindung zur Indexierung: sobald
    sie eine neue index.pkl geschrieben hat (siehe speichere_index, das
    atomar arbeitet), liest die naechste Suche automatisch die neue
    Fassung - ohne Neustart der App.
    """
    global _such_cache
    import numpy as np

    try:
        angaben = os.stat(INDEX_FILE)
        kennung = (angaben.st_mtime_ns, angaben.st_size)
    except OSError:
        return [], None

    with _such_cache_lock:
        if _such_cache is not None and _such_cache[0] == kennung:
            return _such_cache[1], _such_cache[2]

        eintraege, passend = _index_datei_lesen()
        if not passend:
            # Fremder Index: lieber keine Treffer als falsche. Der naechste
            # Indexlauf baut ihn neu auf.
            return [], None

        # Eintraege ohne Vektor (z.B. Dateien, die beim Indexieren nicht
        # gelesen werden konnten) lassen sich nicht durchsuchen.
        eintraege = [e for e in eintraege if "vektor" in e]

        matrix = None
        if eintraege:
            try:
                matrix = np.asarray([e["vektor"] for e in eintraege], dtype="float32")
            except Exception as e:
                # Ein alter Index mit unterschiedlich langen Vektoren laesst
                # sich nicht stapeln. Dann lieber ohne Matrix weiterarbeiten
                # als die Suche ganz scheitern lassen.
                print(f"[Suche] Vektormatrix nicht baubar: {e}")
                matrix = None

        if angaben.st_size <= CACHE_OBERGRENZE_BYTES:
            _such_cache = (kennung, eintraege, matrix)
        else:
            _such_cache = None

        return eintraege, matrix
