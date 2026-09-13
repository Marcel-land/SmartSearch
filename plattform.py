#!/usr/bin/env python3
"""
plattform.py - alles, was auf jedem Betriebssystem ANDERS funktioniert.

WARUM ES DIESE DATEI GIBT
-------------------------
SmartSearch war bis hierher eine reine Mac-Anwendung: Benachrichtigungen
ueber osascript, Vorschau ueber Quick Look, "im Finder zeigen" ueber
`open -R`, Autostart ueber einen LaunchAgent. Alles das steckte mitten in
gui.py. Auf Windows laesst sich so eine Datei nicht einmal starten.

Ab jetzt gilt die Regel: gui.py beschreibt, WAS passieren soll
("zeig mir die Datei im Dateimanager"), diese Datei weiss, WIE das auf dem
jeweiligen System geht. Kommt spaeter Windows oder Linux dazu, wird nur
hier ergaenzt - die Oberflaeche bleibt unveraendert.

Grundsatz fuer alle Funktionen hier: Sie duerfen NIE eine Ausnahme nach
oben durchreichen. Eine fehlgeschlagene Benachrichtigung darf die Suche
nicht abbrechen.
"""

import os
import sys
import subprocess

IST_MAC = sys.platform == "darwin"
IST_WINDOWS = os.name == "nt"
IST_LINUX = not IST_MAC and not IST_WINDOWS

# Quick Look gibt es so nur auf dem Mac. Die Oberflaeche fragt das ab, um
# den Vorschau-Knopf auf anderen Systemen gar nicht erst anzubieten.
VORSCHAU_VERFUEGBAR = IST_MAC


def _still_ausfuehren(befehl):
    """Startet ein Programm im Hintergrund und schluckt dessen Ausgabe."""
    subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- Hinweise

def benachrichtigung(titel, text):
    """Kurze Systemmeldung ("Indexierung fertig")."""
    try:
        if IST_MAC:
            def escape(s):
                return s.replace("\\", "\\\\").replace('"', '\\"')
            script = f'display notification "{escape(text)}" with title "{escape(titel)}"'
            subprocess.run(["osascript", "-e", script], check=False)
        elif IST_WINDOWS:
            # Ohne Zusatzpaket gibt es unter Windows keinen zuverlaessigen
            # Weg zu einer echten Toast-Meldung. Ist eines der ueblichen
            # Pakete installiert, wird es genutzt - sonst passiert einfach
            # nichts. Eine fehlende Meldung ist ein Schoenheitsfehler, kein
            # Grund fuer eine Fehlermeldung.
            try:
                from win11toast import notify  # type: ignore
                notify(titel, text)
            except Exception:
                try:
                    from plyer import notification as _n  # type: ignore
                    _n.notify(title=titel, message=text, timeout=5)
                except Exception:
                    print(f"[Hinweis] {titel}: {text}")
        else:
            subprocess.run(["notify-send", titel, text], check=False)
    except Exception as e:
        print(f"[Benachrichtigung fehlgeschlagen] {e}")


# ---------------------------------------------------------------- Dateien

def datei_oeffnen(pfad):
    """Oeffnet eine Datei mit dem Standardprogramm des Systems."""
    try:
        if IST_MAC:
            subprocess.run(["open", pfad], check=True)
        elif IST_WINDOWS:
            os.startfile(pfad)  # type: ignore[attr-defined]  # nur Windows
        else:
            subprocess.run(["xdg-open", pfad], check=True)
        return True
    except Exception as e:
        print(f"[Oeffnen fehlgeschlagen] {e}")
        return False


def im_dateimanager_zeigen(dateipfad):
    """Oeffnet den Ordner der Datei und markiert die Datei darin
    (Finder auf dem Mac, Explorer unter Windows)."""
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        if IST_MAC:
            _still_ausfuehren(["open", "-R", dateipfad])
        elif IST_WINDOWS:
            # Explorer erwartet genau diese Schreibweise mit Komma und
            # OHNE Leerzeichen danach - sonst oeffnet er "Dokumente".
            _still_ausfuehren(["explorer", "/select,", os.path.normpath(dateipfad)])
        else:
            _still_ausfuehren(["xdg-open", os.path.dirname(dateipfad)])
    except Exception as e:
        print(f"[Dateimanager Fehler] {e}")


def vorschau(dateipfad):
    """Schnellvorschau ohne die Datei wirklich zu oeffnen (Quick Look).

    Nur der Mac kann das von Haus aus. Ueberall sonst wird die Datei
    stattdessen normal geoeffnet - besser als ein Knopf, der nichts tut.
    """
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        if IST_MAC:
            _still_ausfuehren(["qlmanage", "-p", dateipfad])
        else:
            datei_oeffnen(dateipfad)
    except Exception as e:
        print(f"[Vorschau Fehler] {e}")


# ---------------------------------------------------------------- Programmpfad

def app_pfad():
    """Pfad, mit dem sich SmartSearch selbst erneut starten laesst.

    Auf dem Mac ist das das .app-Bundle (NICHT die Programmdatei tief
    darin - "open" braucht das Bundle). Unter Windows die .exe. Beim Start
    aus dem Quelltext heraus der Pfad des Skripts.
    """
    pfad = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
    marke = ".app" + os.sep + "Contents" + os.sep
    if marke in pfad:
        return pfad.split(marke)[0] + ".app"
    return pfad


# ---------------------------------------------------------------- Autostart

_MAC_PLIST = os.path.expanduser("~/Library/LaunchAgents/com.smartsearch.app.plist")
_WIN_RUN_SCHLUESSEL = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_WERT_NAME = "SmartSearch"


def autostart_aktiv():
    """Startet SmartSearch aktuell automatisch mit der Anmeldung?"""
    try:
        if IST_MAC:
            return os.path.exists(_MAC_PLIST)
        if IST_WINDOWS:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_SCHLUESSEL) as key:
                try:
                    winreg.QueryValueEx(key, _WIN_WERT_NAME)
                    return True
                except FileNotFoundError:
                    return False
    except Exception:
        pass
    return False


def autostart_setzen(einschalten):
    """Autostart ein- oder ausschalten.

    Rueckgabe: (True, "") bei Erfolg, sonst (False, Fehlertext) - die
    Oberflaeche zeigt den Text in der Statuszeile an.
    """
    try:
        if IST_MAC:
            if einschalten:
                inhalt = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartsearch.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>{app_pfad()}</string>
        <string>--args</string>
        <string>--autostart</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
                os.makedirs(os.path.dirname(_MAC_PLIST), exist_ok=True)
                with open(_MAC_PLIST, "w") as f:
                    f.write(inhalt)
            elif os.path.exists(_MAC_PLIST):
                os.remove(_MAC_PLIST)
            return True, ""

        if IST_WINDOWS:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_SCHLUESSEL, 0,
                                winreg.KEY_SET_VALUE) as key:
                if einschalten:
                    befehl = f'"{app_pfad()}" --autostart'
                    winreg.SetValueEx(key, _WIN_WERT_NAME, 0, winreg.REG_SZ, befehl)
                else:
                    try:
                        winreg.DeleteValue(key, _WIN_WERT_NAME)
                    except FileNotFoundError:
                        pass
            return True, ""

        return False, "Autostart wird auf diesem System nicht unterstuetzt."
    except Exception as e:
        return False, str(e)
