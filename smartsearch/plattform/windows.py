#!/usr/bin/env python3
"""
plattform/windows.py - das Windows-Gegenstueck zu plattform/mac.py.

Gleiche Aufgaben, andere Technik:

    Mac                              Windows
    ---------------------------      --------------------------------
    Lupe in der Menueleiste          Symbol im Infobereich (neben der Uhr)
    NSStatusBar (PyObjC)             pystray
    Cmd+Shift+F ueber NSEvent        Strg+Shift+F ueber RegisterHotKey
    Dock-Symbol                      Symbol in der Taskleiste
    Aktive Anwendung (NSApp)         Vordergrundfenster + Prozesskennung
    Finder / Quick Look              Explorer / normales Oeffnen
    LaunchAgent (Autostart)          Registry-Eintrag unter ...\\Run
    ~/Library/Application Support    %LOCALAPPDATA% (siehe kern/pfade.py)

Die Funktionsnamen sind absichtlich identisch mit denen in plattform/mac.py
- plattform/__init__.py laedt je nach System die eine oder die andere Datei,
und die Oberflaeche ruft ueberall dieselben Namen auf. So steht in der
Oberflaeche kein einziges "wenn Windows, dann..." mehr.

ABHAENGIGKEIT
-------------
Fuer das Symbol im Infobereich:  pip install pystray pillow
Fehlt es, laeuft SmartSearch trotzdem - dann ohne Symbol, und das Fenster
versteckt sich nicht mehr von selbst (sonst waere es unerreichbar, siehe
auf_fokus_verlust() in oberflaeche/hauptfenster.py).

Der Tastenkurzbefehl braucht KEIN Zusatzpaket: er geht ueber
RegisterHotKey aus der Windows-Systembibliothek user32, direkt per ctypes.
"""

import os
import subprocess
import sys
import threading

VERFUEGBAR = False

try:
    import pystray
    from PIL import Image
    VERFUEGBAR = True
except ImportError as e:  # pragma: no cover - nur ohne pystray
    print(f"[Infobereich] pystray/Pillow fehlt ({e}) - Symbol wird nicht angezeigt.")


def menueleisten_symbol_anlegen(callback, beenden_callback=None, icon_pfad=None):
    """Legt das Symbol im Infobereich an (unten rechts neben der Uhr).

    Ein Klick auf das Symbol ruft 'callback' auf (Fenster auf/zu), das
    Kontextmenue bietet zusaetzlich "Beenden".

    pystray bringt eine eigene Ereignisschleife mit. Die darf NICHT im
    Hauptthread laufen - dort laeuft schon Tkinter. Deshalb ein eigener
    Hintergrundthread. Beide Callbacks setzen in oberflaeche/hauptfenster.py nur ein Flag, das
    der Tk-Hauptthread alle 50 ms abfragt; Widgets aus einem fremden
    Thread anzufassen fuehrt sonst zu schwer auffindbaren Abstuerzen.
    """
    if not VERFUEGBAR:
        return None

    try:
        if not icon_pfad or not os.path.exists(icon_pfad):
            from smartsearch.kern.pfade import ressource
            icon_pfad = ressource("icons/icon.png")
        bild = Image.open(icon_pfad)

        eintraege = [pystray.MenuItem("SmartSearch öffnen", lambda *_: callback(), default=True)]
        if beenden_callback:
            eintraege.append(pystray.MenuItem("Beenden", lambda *_: beenden_callback()))

        symbol = pystray.Icon("SmartSearch", bild, "SmartSearch", pystray.Menu(*eintraege))
        threading.Thread(target=symbol.run, daemon=True).start()
        return symbol
    except Exception as e:
        print(f"[Infobereich] Symbol konnte nicht angelegt werden: {e}")
        return None


def registriere_globalen_hotkey(callback):
    """Strg+Shift+F von ueberall aus.

    Bewusst OHNE Zusatzpaket geloest: Windows bietet mit RegisterHotKey
    genau dafuer eine Systemfunktion. Sie meldet die Tastenkombination
    beim System an; ausgeloest wird sie dann als Nachricht an den
    anmeldenden Thread. Deshalb laeuft hier ein eigener kleiner Thread mit
    einer Nachrichtenschleife.

    Gaengige Fremdpakete (z.B. "keyboard") lesen stattdessen ALLE
    Tastenanschlaege mit - das ist fuer diesen Zweck zu viel des Guten und
    laesst Virenscanner aufhorchen.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as e:
        print(f"[Hotkey] Nicht verfuegbar: {e}")
        return None

    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000   # nicht dauerfeuern, solange die Taste haengt
    VK_F = 0x46
    WM_HOTKEY = 0x0312
    KENNUNG = 1

    def _schleife():
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, KENNUNG, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_F):
            print("[Hotkey] Strg+Shift+F ist bereits von einem anderen Programm belegt.")
            return
        try:
            nachricht = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(nachricht), None, 0, 0) != 0:
                if nachricht.message == WM_HOTKEY:
                    try:
                        callback()
                    except Exception as e:
                        print(f"[Hotkey] Fehler im Handler: {e}")
        finally:
            user32.UnregisterHotKey(None, KENNUNG)

    thread = threading.Thread(target=_schleife, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------- Rest
# Diese drei Dinge regelt Windows bzw. Tkinter von allein. Die Funktionen
# gibt es nur, damit die Oberflaeche fuer beide Systeme denselben Code benutzen
# kann - siehe Kopf dieser Datei.

def fenster_nach_vorne():
    """Auf dem Mac muss die Anwendung dafuer aktiviert werden; unter
    Windows genuegen die Tk-Befehle lift()/focus_force() in oberflaeche/hauptfenster.py."""
    return


def als_programm_im_dock_anmelden():
    """Mac-Eigenheit (Dock-Symbol statt reiner Hintergrundprozess)."""
    return


def dock_symbol_setzen(icon_pfad):
    """Das Symbol in Taskleiste und Fenstertitel setzt Tkinter selbst
    (siehe iconbitmap/iconphoto in oberflaeche/hauptfenster.py)."""
    return


def laufende_instanz_aktivieren():
    """Zweitstart-Erkennung laeuft unter Windows ueber die Sperrdatei in
    oberflaeche/hauptfenster.py (dieselbe Loesung wie der Mac-Ausweichweg) - hier gibt es kein
    Gegenstueck zur Bundle-Kennung von macOS."""
    return False


# ------------------------------------------------------ Gegenstuecke zum Mac
# Diese drei Funktionen ruft die Oberflaeche seit Fassung 1.0.2 auf. Sie sind dort
# jeweils mit hasattr() abgesichert - fehlen sie, laeuft das Programm also
# weiter, verliert aber stillschweigend Verhalten. Deshalb hier die
# Windows-Entsprechungen.

# Kennung, unter der Windows dieses Programm fuehrt. Aufbau ist Konvention:
# Hersteller.Produkt, ohne Leerzeichen, stabil ueber alle Fassungen hinweg -
# aendert sie sich, behandelt Windows das Programm als ein anderes und
# vergisst angeheftete Verknuepfungen.
ANWENDUNGSKENNUNG = "SmartSearch.Desktop"


def app_ist_aktiv():
    """Liegt gerade ein Fenster DIESES Programms im Vordergrund?

    Die Oberflaeche fragt das regelmaessig ab und achtet auf die Flanke
    "nicht aktiv -> aktiv": genau dann hat der Benutzer SmartSearch ueber
    die Taskleiste, Alt+Tab oder das Infobereich-Symbol zurueckgeholt, und
    das versteckte Fenster soll wieder erscheinen. Ohne diese Funktion ist
    das Fenster unter Windows nur ueber das Symbol im Infobereich oder den
    Tastenkurzbefehl erreichbar.

    Windows kennt keinen Programm-, sondern nur einen Fensterbegriff.
    Ermittelt wird deshalb das Vordergrundfenster und geprueft, ob es zu
    unserem Prozess gehoert.

    Rueckgabe:
        True/False - Zustand sicher ermittelt
        None       - nicht ermittelbar; die Oberflaeche laesst den Zustand dann
                     unveraendert, statt das Fenster faelschlich zu zeigen.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    try:
        user32 = ctypes.windll.user32
        fenster = user32.GetForegroundWindow()
        if not fenster:
            # Kein Vordergrundfenster - z.B. waehrend eines Anmeldedialogs.
            return False
        prozess = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fenster, ctypes.byref(prozess))
        return prozess.value == os.getpid()
    except Exception as e:
        print(f"[Vordergrund] Zustand nicht ermittelbar: {e}")
        return None


def programmnamen_setzen(name="SmartSearch"):
    """Meldet dem System eine eigene Anwendungskennung an.

    Auf dem Mac steht an dieser Stelle der Name im Anwendungsmenue. Unter
    Windows gibt es dieses Menue nicht; die entsprechende Stelle ist die
    Taskleiste. Ohne eigene Kennung ordnet Windows das Fenster dem
    ausfuehrenden Programm zu - also Python - und zeigt dessen Symbol
    statt unserem. Das ist dasselbe Problem wie die Python-Rakete im Dock
    auf dem Mac, nur an anderer Stelle.

    Muss VOR dem ersten Fenster aufgerufen werden; genau dort steht der
    Aufruf in oberflaeche/hauptfenster.py.

    Der uebergebene Name wird bewusst nicht in die Kennung eingebaut: sie
    muss ueber alle Fassungen hinweg gleich bleiben (siehe
    ANWENDUNGSKENNUNG).
    """
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ANWENDUNGSKENNUNG)
    except Exception as e:
        print(f"[Taskleiste] Anwendungskennung nicht gesetzt: {e}")


def aus_dem_dock_nehmen():
    """Ohne Entsprechung unter Windows - bewusst leer.

    Auf dem Mac blendet die Oberflaeche beim Beenden das Dock-Symbol aus, damit
    waehrend des Herunterfahrens nicht kurz das falsche Symbol steht.
    Unter Windows verschwindet der Taskleisten-Eintrag zusammen mit dem
    Fenster, es gibt nichts abzumelden.

    Die Funktion existiert trotzdem, damit beide Systeme dieselbe
    Schnittstelle haben und in oberflaeche/hauptfenster.py kein "wenn Windows, dann..." noetig
    ist.
    """
    return


# ===========================================================================
# SYSTEM-HANDGRIFFE (bis Herbst 2026 in plattform.py, dort je Funktion mit
# "wenn Mac ... sonst Windows ..." - jetzt je System eine eigene Datei)
# ===========================================================================

# Quick Look gibt es unter Windows nicht - der Vorschau-Knopf oeffnet die
# Datei stattdessen normal (siehe vorschau).
VORSCHAU_VERFUEGBAR = False


def _still_ausfuehren(befehl):
    """Startet ein Programm im Hintergrund und schluckt dessen Ausgabe."""
    subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def benachrichtigung(titel, text):
    """Kurze Systemmeldung ("Indexierung fertig").

    Ohne Zusatzpaket gibt es unter Windows keinen zuverlaessigen Weg zu
    einer echten Toast-Meldung. Ist eines der ueblichen Pakete installiert,
    wird es genutzt - sonst passiert einfach nichts. Eine fehlende Meldung
    ist ein Schoenheitsfehler, kein Grund fuer eine Fehlermeldung.
    """
    try:
        try:
            from win11toast import notify  # type: ignore
            notify(titel, text)
        except Exception:
            try:
                from plyer import notification as _n  # type: ignore
                _n.notify(title=titel, message=text, timeout=5)
            except Exception:
                print(f"[Hinweis] {titel}: {text}")
    except Exception as e:
        print(f"[Benachrichtigung fehlgeschlagen] {e}")


def datei_oeffnen(pfad):
    """Oeffnet eine Datei mit dem Standardprogramm."""
    try:
        os.startfile(pfad)  # type: ignore[attr-defined]  # gibt es nur unter Windows
        return True
    except Exception as e:
        print(f"[Oeffnen fehlgeschlagen] {e}")
        return False


def im_dateimanager_zeigen(dateipfad):
    """Oeffnet den Explorer und markiert die Datei darin."""
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        # Explorer erwartet genau diese Schreibweise mit Komma und OHNE
        # Leerzeichen danach - sonst oeffnet er "Dokumente".
        _still_ausfuehren(["explorer", "/select,", os.path.normpath(dateipfad)])
    except Exception as e:
        print(f"[Dateimanager Fehler] {e}")


def vorschau(dateipfad):
    """Keine Schnellvorschau unter Windows - die Datei wird normal
    geoeffnet. Besser als ein Knopf, der nichts tut."""
    if not dateipfad or not os.path.exists(dateipfad):
        return
    datei_oeffnen(dateipfad)


def app_pfad():
    """Pfad, mit dem sich SmartSearch selbst erneut starten laesst: die
    .exe, beim Start aus dem Quelltext der Pfad des Skripts."""
    return os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])


_WIN_RUN_SCHLUESSEL = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_WERT_NAME = "SmartSearch"


def autostart_aktiv():
    """Startet SmartSearch aktuell automatisch mit der Anmeldung?"""
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_SCHLUESSEL) as key:
            try:
                winreg.QueryValueEx(key, _WIN_WERT_NAME)
                return True
            except FileNotFoundError:
                return False
    except Exception:
        return False


def autostart_setzen(einschalten):
    """Autostart ueber die Registry (Schluessel ...\\CurrentVersion\\Run des Benutzers)
    ein- oder ausschalten.
    Braucht keine Administratorrechte.

    Rueckgabe: (True, "") bei Erfolg, sonst (False, Fehlertext).
    """
    try:
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
    except Exception as e:
        return False, str(e)


def systemsprache(unterstuetzt):
    """Anzeigesprache von Windows, falls SmartSearch sie kann - oder None.

    NEU: Vorher gab es unter Windows gar keine Erkennung (der Code dafuer
    war Mac-spezifisch), die Oberflaeche startete dort immer auf Deutsch.
    NOCH NICHT UNTER WINDOWS ERPROBT.
    """
    try:
        import ctypes
        import locale
        sprach_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
        name = locale.windows_locale.get(sprach_id, "")  # z. B. "de_DE"
        kurz = name[:2].lower()
        if kurz in unterstuetzt:
            return kurz
    except Exception:
        pass
    return None


def system_beschreibung():
    """Fuer die Rueckmelde-E-Mail, z. B. "Windows 11 (AMD64)"."""
    import platform
    return f"Windows {platform.release()} ({platform.machine()})"
