#!/usr/bin/env python3
"""
modell.py - das KI-Suchmodell: herunterladen, laden, im Speicher halten.

Hierher gehoert alles, was mit dem Modell selbst zu tun hat - und nur das.
Wird das Modell spaeter gewechselt (geplant: granite-embedding ueber
onnxruntime statt BGE-M3 ueber PyTorch), aendert sich diese eine Datei;
Suche, Index und Oberflaeche rufen weiterhin geladenes_modell() auf.
"""

import os
import socket
import threading

MODELL_NAME = "BAAI/bge-m3"


# Ungefaehre Groesse des BGE-M3-Modells auf der Festplatte. Dient NUR
# der Fortschrittsanzeige beim einmaligen Download - ein paar Prozent
# Abweichung sind egal, Hauptsache der Nutzer sieht, dass sich etwas tut.
MODELL_GROESSE_BYTES = 2_270_000_000


class ModellDownloadFehler(Exception):
    """Das Modell liegt noch nicht lokal vor und konnte nicht geladen
    werden - in aller Regel, weil beim allerersten Start keine
    Internetverbindung besteht. Eigene Klasse, damit die GUI diesen einen
    Fall verstaendlich erklaeren kann, statt einen rohen Netzwerkfehler
    anzuzeigen."""


class ProgrammUnvollstaendig(Exception):
    """Ein Baustein fehlt in der ausgelieferten App - nicht das Modell,
    sondern ein Programmteil, der beim Bauen haette mitkopiert werden
    muessen. Der Nutzer kann daran nichts aendern; ein Neuversuch oder
    eine bessere Internetverbindung helfen nicht. Eigene Klasse, damit
    die Oberflaeche das sagt, statt faelschlich auf die Verbindung zu
    zeigen."""


def _modell_cache_ordner():
    """Ordner, in dem huggingface das Modell ablegt. HF_HOME hat Vorrang,
    falls jemand den Cache verschoben hat."""
    basis = os.environ.get("HF_HOME")
    if basis:
        hub = os.path.join(basis, "hub")
    else:
        hub = os.path.expanduser("~/.cache/huggingface/hub")
    return os.path.join(hub, "models--" + MODELL_NAME.replace("/", "--"))


def _ordnergroesse(pfad):
    gesamt = 0
    for wurzel, _, dateien in os.walk(pfad):
        for name in dateien:
            try:
                # Symlinks nicht mitzaehlen: huggingface verlinkt die
                # Snapshot-Dateien auf den blobs-Ordner, sonst waere jede
                # Datei doppelt in der Summe.
                voll = os.path.join(wurzel, name)
                if not os.path.islink(voll):
                    gesamt += os.path.getsize(voll)
            except OSError:
                pass
    return gesamt


def modell_ist_vorhanden():
    """True, wenn das Modell vollstaendig genug lokal liegt, um ohne
    Internet zu starten. Die Groessenschwelle faengt einen frueher
    abgebrochenen Download ab - ein halb geladener Ordner existiert zwar,
    taugt aber nicht."""
    ordner = _modell_cache_ordner()
    if not os.path.isdir(ordner):
        return False
    return _ordnergroesse(ordner) > MODELL_GROESSE_BYTES * 0.9


# ---------------------------------------------------------------------------
# OFFLINE-BETRIEB ERZWINGEN, SOBALD DAS MODELL LOKAL LIEGT
#
# Gemessen am 18.09.2026 auf einem zweiten Mac: Die fertige App hat beim
# Start
#     HEAD https://huggingface.co/BAAI/bge-m3/resolve/main/adapter_config.json
# aufgerufen, fuenfmal wiederholt und dann das Vorladen abgebrochen. Das
# passiert bei JEDEM Start, auch wenn das Modell vollstaendig auf der
# Platte liegt: huggingface_hub fragt von sich aus nach, ob es eine
# neuere Fassung gibt.
#
# Fuer dieses Produkt ist das kein Schoenheitsfehler:
#   1. Wir verkaufen "nichts verlaesst Ihren Rechner". Eine Verbindung zu
#      einem Server in den USA bei jedem Start widerspricht dem, und in
#      der Datenschutzerklaerung steht sie nicht.
#   2. Auf einem Rechner ohne Internet - oder wenn das Netz bei der
#      Anmeldung noch nicht steht - kostet es Wartezeit und bricht das
#      Vorladen ab, obwohl alles Noetige da ist.
#
# Die beiden Schalter unten werden gesetzt, SOBALD das Modell vollstaendig
# vorliegt, und zwar beim Import - huggingface_hub liest sie einmalig beim
# eigenen Import ein, spaeter gesetzt wirken sie nicht mehr. Fehlt das
# Modell noch, bleiben sie aus, sonst koennte es nie heruntergeladen
# werden.
# ---------------------------------------------------------------------------

def _offline_erzwingen_wenn_moeglich():
    if modell_ist_vorhanden():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        return True
    return False


_OFFLINE_AKTIV = _offline_erzwingen_wenn_moeglich()


def _internet_erreichbar(timeout=5):
    try:
        with socket.create_connection(("huggingface.co", 443), timeout=timeout):
            return True
    except OSError:
        return False


def lade_modell(fortschritt_fn=None):
    """Laedt das BGE-M3 KI-Modell.

    WICHTIG: Laeuft bewusst auf der CPU statt auf MPS (Apples GPU-Backend).
    PyTorchs MPS-Speicherverwalter hat einen bekannten Bug, der bei
    laengeren Indexierungslaeufen mit "buffer_block INTERNAL ASSERT FAILED"
    abstuerzt (die ganze App wird dann vom Betriebssystem beendet - "zsh:
    abort"). Auf der CPU ist die Berechnung etwas langsamer, aber stabil.

    fortschritt_fn(geladene_bytes, gesamt_bytes) wird waehrend des
    EINMALIGEN Erst-Downloads regelmaessig aufgerufen. Ohne diese Rueckmeldung
    steht ein neuer Nutzer minutenlang vor einer scheinbar eingefrorenen
    App - das war die haeufigste Stelle, an der Leute die App wieder
    geloescht haben, bevor sie sie ueberhaupt einmal benutzt hatten.

    Wirft ModellDownloadFehler, wenn das Modell fehlt und nicht geladen
    werden kann.
    """
    muss_geladen_werden = not modell_ist_vorhanden()

    if muss_geladen_werden and not _internet_erreichbar():
        raise ModellDownloadFehler(
            "Das KI-Modell wurde noch nicht heruntergeladen und es besteht "
            "keine Internetverbindung."
        )

    beobachter_stoppen = threading.Event()

    def _beobachte_download():
        """Misst waehrend des Downloads einfach die Groesse des Cache-
        Ordners. Bewusst so simpel gehalten statt ueber die internen
        Fortschritts-Hooks von huggingface_hub zu gehen - die aendern sich
        zwischen Versionen, ein Ordner auf der Festplatte nicht."""
        ordner = _modell_cache_ordner()
        while not beobachter_stoppen.wait(1.0):
            try:
                geladen = _ordnergroesse(ordner) if os.path.isdir(ordner) else 0
                fortschritt_fn(geladen, MODELL_GROESSE_BYTES)
            except Exception:
                pass

    beobachter = None
    if muss_geladen_werden and fortschritt_fn is not None:
        beobachter = threading.Thread(target=_beobachte_download, daemon=True)
        beobachter.start()

    try:
        if not muss_geladen_werden:
            # Zweite Absicherung, falls der Import oben noch vor dem
            # Download gelaufen ist und das Modell erst danach kam.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        quelle = "lokal" if not muss_geladen_werden else "wird geladen"
        print(f"Lade KI-Modell (BGE-M3, CPU-Modus, {quelle})...")
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(MODELL_NAME, device="cpu")
    except ImportError as e:
        # Ein fehlendes Modul ist kein Netzwerkproblem. Frueher landete
        # dieser Fall in der Sammelbehandlung unten und wurde dem Nutzer
        # als "keine Internetverbindung" angezeigt - eine Fehlermeldung,
        # die in die falsche Richtung schickt und nicht loesbar ist.
        raise ProgrammUnvollstaendig(str(e)) from e
    except Exception as e:
        if muss_geladen_werden:
            # Beim Erst-Download ist ein Fehler fast immer ein Netzwerk-
            # oder Speicherplatzproblem - als solches weiterreichen, damit
            # die GUI es erklaeren kann.
            raise ModellDownloadFehler(str(e)) from e
        raise
    finally:
        beobachter_stoppen.set()
        if beobachter is not None:
            beobachter.join(timeout=2)


_modell_cache = None
_modell_lock = threading.Lock()


def geladenes_modell(fortschritt_fn=None):
    """Lädt das Modell einmalig und cached es (Thread-sicher).

    Ohne den Lock könnten Suche und Indexierung, wenn sie gleichzeitig zum
    allerersten Mal starten, beide parallel lade_modell() aufrufen und das
    Modell doppelt laden (unnötiger Speicher-/Zeitverbrauch, im schlimmsten
    Fall doppelte Downloads beim ersten Start).
    """
    global _modell_cache
    if _modell_cache is None:
        with _modell_lock:
            if _modell_cache is None:  # Doppelt geprüft: evtl. hat ein
                # anderer Thread es inzwischen schon geladen, während wir
                # auf den Lock gewartet haben.
                _modell_cache = lade_modell(fortschritt_fn=fortschritt_fn)
    return _modell_cache
