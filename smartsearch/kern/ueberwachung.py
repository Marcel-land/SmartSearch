#!/usr/bin/env python3
"""
ueberwachung.py - bemerkt Aenderungen in den ueberwachten Ordnern und
stoesst dann eine Aktualisierung des Index an.

Laeuft ueber watchdog. Fehlt das Paket, gibt es eben keine automatische
Aktualisierung - der Knopf "Index aktualisieren" funktioniert trotzdem.
"""

import os
import threading
import time

from smartsearch.kern.dateien import IGNORIERTE_ORDNERNAMEN, UNTERSTUETZT
from smartsearch.kern.einstellungen import lade_config

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_VERFUEGBAR = True
except ImportError:
    WATCHDOG_VERFUEGBAR = False


# Ordner-/Datei-Fragmente, die NIE einen Re-Index auslösen sollen. Das sind
# typische App-eigene Pfade (venv, .git, __pycache__) und die eigenen
# Datenablagen der App (verlauf.json, Index-/Cache-Dateien). Ohne diesen
# Filter löst die App durch ihr eigenes Schreiben (Index speichern, Verlauf
# speichern) ständig neue Watchdog-Events aus und indexiert sich selbst in
# eine Endlosschleife.
#
# Die Ordnernamen kommen aus dateien.IGNORIERTE_ORDNERNAMEN - dieselbe
# Liste, die auch das Einlesen benutzt. Frueher stand hier eine eigene,
# fast gleiche Liste; was in der einen fehlte, loeste in der anderen
# unnoetige Laeufe aus.
IGNORIERTE_PFAD_FRAGMENTE = {os.sep + name + os.sep for name in IGNORIERTE_ORDNERNAMEN}
IGNORIERTE_DATEINAMEN = {
    "verlauf.json",
    "favoriten.json",
    ".ds_store",
}


def ist_relevantes_event(dateipfad):
    """True nur für Dateien, die tatsächlich neu indexiert werden müssten
    (unterstützte Dokumenttypen) und die nicht zu App-eigenen Daten gehören."""
    name = os.path.basename(dateipfad).lower()
    if name in IGNORIERTE_DATEINAMEN or name.startswith("."):
        return False

    normiert = os.sep + dateipfad.replace("/", os.sep).strip(os.sep) + os.sep
    if any(frag in normiert for frag in IGNORIERTE_PFAD_FRAGMENTE):
        return False

    ext = os.path.splitext(name)[1]
    return ext in UNTERSTUETZT


if WATCHDOG_VERFUEGBAR:
    class OrdnerAenderungsHandler(FileSystemEventHandler):
        def __init__(self, callback_funktion):
            super().__init__()
            self.callback_funktion = callback_funktion
            self.letzte_aenderung = 0

        def on_any_event(self, event):
            if event.is_directory:
                return
            # Nur auf relevante Dokumenttypen reagieren - alles andere
            # (Index-Dateien, verlauf.json, venv, .git, ...) ignorieren,
            # sonst löst die App durch ihr eigenes Schreiben permanent
            # neue Re-Indexierungen aus.
            if not ist_relevantes_event(event.src_path):
                return
            jetzt = time.time()
            if jetzt - self.letzte_aenderung > 5:
                self.letzte_aenderung = jetzt
                self.callback_funktion()


class Ordnerwaechter:
    """Startet und stoppt die Ueberwachung aller Ordner aus config.json.

    bei_aenderung() wird aus einem FREMDEN Thread aufgerufen (dem von
    watchdog). Wer darin Fensterinhalte aendern will, muss das selbst in
    den Hauptthread umleiten - siehe Hauptfenster.automatische_reindexierung.
    """

    def __init__(self, bei_aenderung):
        self._bei_aenderung = bei_aenderung
        self._observer = None
        self._lock = threading.Lock()

    def _anhalten(self):
        """Nur mit gehaltenem Lock aufrufen."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass
            self._observer = None

    def neu_starten(self):
        """(Neu) starten - nach jeder Aenderung an der Ordnerliste aufrufen."""
        if not WATCHDOG_VERFUEGBAR:
            return
        with self._lock:
            self._anhalten()

            ordner_liste = lade_config().get("ordner", [])
            if not ordner_liste:
                return

            handler = OrdnerAenderungsHandler(callback_funktion=self._bei_aenderung)
            observer = Observer()

            ueberwachte = 0
            for o in ordner_liste:
                if os.path.exists(o):
                    observer.schedule(handler, path=o, recursive=True)
                    ueberwachte += 1

            if ueberwachte > 0:
                observer.start()
                self._observer = observer

    def stoppen(self):
        with self._lock:
            self._anhalten()
