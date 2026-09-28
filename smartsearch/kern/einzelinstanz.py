#!/usr/bin/env python3
"""
einzelinstanz.py - sorgt mit dafuer, dass SmartSearch hoechstens einmal
laeuft, und dass ein zweiter Start das vorhandene Fenster nach vorne holt.

Zwei kleine Dateien im Datenordner:

    laeuft.pid              Prozessnummer der laufenden Kopie
    fenster_zeigen.signal   "bitte zeig dein Fenster" - legt eine zweite,
                            gerade gestartete Kopie an; die laufende holt
                            es ab (Hauptfenster.check_toggle_loop).

Das ist der Ausweichweg. Der saubere Weg ueber das Betriebssystem steht in
plattform (laufende_instanz_aktivieren); zusammengesetzt wird beides in
smartsearch/start.py.
"""

import atexit
import os

from smartsearch.kern.pfade import DATEN_ORDNER

SPERRDATEI = os.path.join(DATEN_ORDNER, "laeuft.pid")

# Wird von einer zweiten, gerade gestarteten Kopie angelegt und von der
# bereits laufenden Kopie in check_toggle_loop() ausgewertet.
ZEIGEN_SIGNAL = os.path.join(DATEN_ORDNER, "fenster_zeigen.signal")


def bitte_fenster_zeigen():
    """Der laufenden Instanz mitteilen, dass sie sich zeigen soll."""
    try:
        os.makedirs(DATEN_ORDNER, exist_ok=True)
        with open(ZEIGEN_SIGNAL, "w") as f:
            f.write("zeigen")
    except Exception as e:
        print(f"[Start] Signal an laufende Instanz fehlgeschlagen: {e}")


def zeigen_signal_abholen():
    """True, wenn eine zweite Kopie um das Fenster gebeten hat. Das Signal
    wird dabei verbraucht."""
    try:
        if os.path.exists(ZEIGEN_SIGNAL):
            os.remove(ZEIGEN_SIGNAL)
            return True
    except Exception:
        pass
    return False


def zeigen_signal_verwerfen():
    try:
        if os.path.exists(ZEIGEN_SIGNAL):
            os.remove(ZEIGEN_SIGNAL)
    except Exception:
        pass


def andere_kopie_ueber_sperrdatei():
    """Ausweichweg ohne Betriebssystem-Hilfe: laeuft laut Sperrdatei schon
    eine Kopie? Wenn nicht, traegt sich diese Kopie ein.

    Rueckgabe: True, wenn eine andere Kopie laeuft (diese soll sich dann
    beenden).
    """
    try:
        if os.path.exists(SPERRDATEI):
            with open(SPERRDATEI) as f:
                alte_pid = int(f.read().strip() or 0)
            if alte_pid and alte_pid != os.getpid():
                try:
                    os.kill(alte_pid, 0)   # nur pruefen, nichts senden
                except OSError:
                    pass                   # Eintrag ist verwaist
                else:
                    bitte_fenster_zeigen()
                    print(f"[Start] SmartSearch laeuft bereits (Prozess {alte_pid}).")
                    return True
        os.makedirs(os.path.dirname(SPERRDATEI), exist_ok=True)
        with open(SPERRDATEI, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(lambda: os.path.exists(SPERRDATEI) and os.remove(SPERRDATEI))
    except Exception as e:
        # Eine fehlgeschlagene Pruefung darf den Start nie verhindern.
        print(f"[Start] Sperrdatei konnte nicht angelegt werden: {e}")
    return False


def aufraeumen():
    """Sperrdatei und Signal entfernen. Beim Beenden aufrufen: das Programm
    endet mit os._exit(0), und das geht an atexit vorbei. Bliebe die Datei
    liegen, koennte ein spaeterer Start sie faelschlich fuer eine laufende
    Instanz halten und sich wortlos beenden."""
    for datei in (SPERRDATEI, ZEIGEN_SIGNAL):
        try:
            if os.path.exists(datei):
                os.remove(datei)
        except Exception:
            pass
