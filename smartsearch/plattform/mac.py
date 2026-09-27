#!/usr/bin/env python3
"""
plattform/mac.py - alles, was SmartSearch auf dem Mac ANDERS macht als
unter Windows.

Zwei Teile:
  1. Bedienung ueber PyObjC: Menueleisten-Symbol (die Lupe oben rechts),
     globaler Tastenkurzbefehl, Dock-Symbol, Fenster nach vorne holen und
     die Pruefung, ob SmartSearch schon laeuft.
  2. System-Handgriffe: Datei oeffnen, im Finder zeigen, Quick Look,
     Benachrichtigung, Autostart (LaunchAgent), Systemsprache.

Gegenstueck: plattform/windows.py - gleiche Funktionsnamen, gleiche
Bedeutung. Welche der beiden Dateien geladen wird, entscheidet
plattform/__init__.py.

WARUM AUSGELAGERT
-----------------
Diese Dinge gibt es unter Windows entweder gar nicht oder voellig anders
(Infobereich statt Menueleiste, RegisterHotKey statt NSEvent-Monitor).
Solange sie mitten in oberflaeche/hauptfenster.py standen, liess sich das Programm auf einem
anderen System nicht einmal starten - schon der Import von AppKit ganz
oben haette es beendet. Jetzt wird diese Datei nur auf dem Mac geladen.

Alles hier ist defensiv gebaut: faellt ein Teil aus (fehlende PyObjC-
Version, fehlende Berechtigung), soll die App trotzdem laufen - nur eben
ohne diese Bequemlichkeit.
"""

import os
import subprocess
import sys

VERFUEGBAR = False
HOTKEY_VERFUEGBAR = False

try:
    import objc
    from AppKit import (
        NSStatusBar,
        NSVariableStatusItemLength,
        NSObject,
        NSApp,
        NSApplicationActivationPolicyRegular,
        NSImage,
        NSEvent,
        NSRunningApplication,
        NSWorkspace,
    )
    VERFUEGBAR = True
except ImportError as e:  # pragma: no cover - nur auf Nicht-Mac-Systemen
    print(f"[Menueleiste] PyObjC nicht verfuegbar: {e}")
    NSObject = object

try:
    from AppKit import (
        NSEventMaskKeyDown,
        NSEventModifierFlagCommand,
        NSEventModifierFlagShift,
        NSEventModifierFlagControl,
        NSEventModifierFlagOption,
        NSEventModifierFlagDeviceIndependentFlagsMask,
    )
    HOTKEY_VERFUEGBAR = VERFUEGBAR
except ImportError:
    HOTKEY_VERFUEGBAR = False

# Wird zum Beenden gebraucht (siehe aus_dem_dock_nehmen). Separat
# importiert, damit eine aeltere PyObjC-Fassung ohne diese Konstante den
# Hauptimport oben nicht zu Fall bringt.
try:
    from AppKit import NSApplicationActivationPolicyProhibited
    DOCK_AUSBLENDEN_MOEGLICH = VERFUEGBAR
except ImportError:
    DOCK_AUSBLENDEN_MOEGLICH = False

BUNDLE_KENNUNG = "de.smartsearch.app"


if VERFUEGBAR:

    class MenueleistenSymbol(NSObject):
        """Die Lupe in der Menueleiste. Ein Klick darauf ruft die
        uebergebene Funktion auf (in oberflaeche/hauptfenster.py: Fenster auf/zu)."""

        def initWithCallback_(self, callback):
            self = objc.super(MenueleistenSymbol, self).init()
            if self:
                self.callback = callback
                self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                    NSVariableStatusItemLength
                )

                button = self.status_item.button()
                # Natives SF-Symbol statt Text-/Emoji-Zeichen: skaliert sauber
                # mit der Menueleiste, ist als Template-Image immer gut
                # sichtbar (passt sich an helle/dunkle Menueleiste an) und
                # wirkt nicht wie ein zu klein geratenes Unicode-Zeichen.
                symbol = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "magnifyingglass", "SmartSearch"
                )
                if symbol:
                    symbol.setTemplate_(True)
                    button.setImage_(symbol)
                else:
                    button.setTitle_("🔍")
                button.setTarget_(self)
                button.setAction_("onClick:")
            return self

        def onClick_(self, sender):
            try:
                self.callback()
            except Exception as e:
                print(f"[Menueleiste] Klick konnte nicht verarbeitet werden: {e}")


def menueleisten_symbol_anlegen(callback, beenden_callback=None, icon_pfad=None):
    """Legt das Lupensymbol an. Gibt das Objekt zurueck - es MUSS in einer
    Variablen aufbewahrt werden, sonst raeumt Python es weg und das Symbol
    verschwindet wieder aus der Menueleiste.

    beenden_callback und icon_pfad werden hier nicht gebraucht (Beenden
    laeuft auf dem Mac ueber Cmd+Q und den Knopf in der App, das Symbol
    ist ein System-Zeichen). Sie stehen nur in der Signatur, damit
    die Oberflaeche fuer Mac und Windows denselben Aufruf benutzen kann -
    siehe plattform/windows.py."""
    if not VERFUEGBAR:
        return None
    try:
        return MenueleistenSymbol.alloc().initWithCallback_(callback)
    except Exception as e:
        print(f"[Menueleiste] Symbol konnte nicht angelegt werden: {e}")
        return None


def registriere_globalen_hotkey(callback):
    """Cmd+Shift+F von ueberall aus - auch wenn eine andere App vorne ist.

    BEWUSST NICHT Cmd+Shift+Leertaste: eine aeltere SmartSearch-Version
    hoert bei Marcel noch auf diese Kombination.

    WICHTIG: Globale Tastaturmonitore brauchen unter macOS die Freigabe
    "Eingabeueberwachung" (Systemeinstellungen > Datenschutz & Sicherheit).
    Ohne Freigabe bleibt der Kurzbefehl wirkungslos - das Menueleisten-
    Symbol funktioniert davon unabhaengig immer.

    Der Handler laeuft auf Apples Event-Loop, NICHT im Tk-Hauptthread.
    Der Callback darf deshalb keine Widgets anfassen (in oberflaeche/hauptfenster.py setzt er
    nur ein Flag, das alle 50 ms abgefragt wird).
    """
    if not HOTKEY_VERFUEGBAR:
        print("[Hotkey] Uebersprungen - AppKit-Konstanten nicht verfuegbar.")
        return None

    HOTKEY_KEYCODE = 3  # "F" (physische Taste, layoutunabhaengig)
    erforderlich = NSEventModifierFlagCommand | NSEventModifierFlagShift
    stoerend = NSEventModifierFlagControl | NSEventModifierFlagOption

    def _handler(event):
        flags = event.modifierFlags() & NSEventModifierFlagDeviceIndependentFlagsMask
        passt = (flags & erforderlich) == erforderlich and not (flags & stoerend)
        if passt and event.keyCode() == HOTKEY_KEYCODE:
            callback()

    try:
        return NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, _handler
        )
    except Exception as e:
        print(f"[Hotkey Fehler] Globaler Hotkey konnte nicht registriert werden: {e}")
        return None


def fenster_nach_vorne():
    """Holt SmartSearch vor alle anderen Programme."""
    if not VERFUEGBAR:
        return
    try:
        NSApp.activateIgnoringOtherApps_(True)
    except Exception as e:
        print(f"[Fenster] Aktivieren fehlgeschlagen: {e}")


def als_programm_im_dock_anmelden():
    """Sorgt fuer ein normales Dock-Symbol (statt eines reinen
    Hintergrundprozesses ohne Symbol)."""
    if not VERFUEGBAR:
        return
    try:
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    except Exception as e:
        print(f"[Dock] Aktivierungsrichtlinie fehlgeschlagen: {e}")


def aus_dem_dock_nehmen():
    """Nimmt SmartSearch noch VOR dem eigentlichen Beenden aus dem Dock.

    WARUM: Das eigene Dock-Symbol wird zur Laufzeit gesetzt (siehe
    dock_symbol_setzen). Beim Beenden faellt dieses Bild weg, der Prozess
    lebt aber noch kurz weiter - er raeumt Sperrdatei und Ordner-
    ueberwachung auf. In genau diesem Moment zeigt macOS wieder das Symbol
    des Programms, das SmartSearch ausfuehrt: beim Start aus dem Quelltext
    die Python-Rakete.

    Wird die Anwendung vorher aus dem Dock genommen, gibt es nichts mehr
    anzuzeigen - das Symbol verschwindet einfach, wie bei jeder anderen
    App auch.
    """
    if not DOCK_AUSBLENDEN_MOEGLICH:
        return False
    try:
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
        return True
    except Exception as e:
        print(f"[Dock] Symbol konnte nicht ausgeblendet werden: {e}")
        return False


def dock_symbol_setzen(icon_pfad):
    """Eigenes Symbol im Dock, auch beim Start aus dem Quelltext.

    Das .icns aus den PyInstaller-Angaben greift NUR in der fertig
    gebauten .app - ohne diese Zeilen sieht man beim Entwickeln immer die
    Python-Rakete.
    """
    if not VERFUEGBAR or not icon_pfad or not os.path.exists(icon_pfad):
        return
    try:
        bild = NSImage.alloc().initWithContentsOfFile_(icon_pfad)
        if bild:
            NSApp.setApplicationIconImage_(bild)
    except Exception as e:
        print(f"[Icon Fehler] Dock-Symbol konnte nicht gesetzt werden: {e}")


def programmnamen_setzen(name="SmartSearch"):
    """Sorgt dafuer, dass die App beim Start aus dem Quelltext nicht
    "Python" heisst.

    HINTERGRUND: Wird SmartSearch direkt mit dem Python aus dem venv
    gestartet, gibt es kein eigenes App-Paket - macOS nimmt Namen und
    Menuetitel deshalb aus dem Paket des Python-Frameworks. Das Dock-
    Symbol laesst sich zur Laufzeit ersetzen (siehe dock_symbol_setzen),
    der Name nur ueber die Angaben des Hauptpakets, die hier im Speicher
    ueberschrieben werden.

    MUSS vor dem Erzeugen des ersten Fensters aufgerufen werden - Tk baut
    das Anwendungsmenue beim Start auf und liest den Namen genau einmal.

    In der fertig gebauten .app ist das nicht noetig: dort steht der Name
    korrekt in den Paketangaben (CFBundleName, siehe SmartSearch.spec).
    Der Name im Dock kann beim Quelltext-Start trotzdem "Python" bleiben -
    den vergibt macOS beim Programmstart, bevor eine Zeile Python laeuft.
    """
    if not VERFUEGBAR:
        return False
    try:
        from Foundation import NSBundle
        paket = NSBundle.mainBundle()
        angaben = paket.localizedInfoDictionary() or paket.infoDictionary()
        if angaben is None:
            return False
        angaben["CFBundleName"] = name
        angaben["CFBundleDisplayName"] = name
        return True
    except Exception as e:
        print(f"[Name] Programmname konnte nicht gesetzt werden: {e}")
        return False


def app_ist_aktiv():
    """True, wenn SmartSearch gerade die vorderste Anwendung ist.

    Die Oberflaeche fragt das alle 50 ms ab, um einen Klick auf das App-Symbol
    (Dock, Launchpad, Cmd+Tab) zu erkennen: macOS aktiviert die App dabei
    immer, schickt Tk die dafuer eigentlich vorgesehene Meldung
    ReopenApplication im gebauten Bundle aber nicht zuverlaessig.

    Rueckgabe None, wenn sich die Information nicht holen laesst - dann
    laesst die Oberflaeche das Fenster einfach in Ruhe.
    """
    if not VERFUEGBAR:
        return None
    try:
        return bool(NSRunningApplication.currentApplication().isActive())
    except Exception:
        return None


def laufende_instanz_aktivieren():
    """Laeuft SmartSearch schon? Dann diese Kopie nach vorne holen.

    macOS fuehrt Buch darueber, welche Programme mit welcher Bundle-
    Kennung laufen - das erfasst auch eine zweite Kopie an einem anderen
    Ort (z.B. eine aus dem Bau-Ordner neben der aus dem Programme-Ordner).

    Rueckgabe: True, wenn bereits eine andere Kopie laeuft.
    """
    if not VERFUEGBAR:
        return False
    try:
        eigene = NSRunningApplication.currentApplication()
        andere = [
            app for app in NSWorkspace.sharedWorkspace().runningApplications()
            if app.bundleIdentifier() == BUNDLE_KENNUNG
            and app.processIdentifier() != eigene.processIdentifier()
        ]
        if andere:
            andere[0].activateWithOptions_(1 << 1)  # ActivateIgnoringOtherApps
            return True
    except Exception as e:
        print(f"[Start] Instanzpruefung ueber macOS nicht moeglich: {e}")
    return False


# ===========================================================================
# SYSTEM-HANDGRIFFE (bis Herbst 2026 in plattform.py, dort je Funktion mit
# "wenn Mac ... sonst Windows ..." - jetzt je System eine eigene Datei)
# ===========================================================================

# Quick Look gibt es so nur auf dem Mac.
VORSCHAU_VERFUEGBAR = True


def _still_ausfuehren(befehl):
    """Startet ein Programm im Hintergrund und schluckt dessen Ausgabe."""
    subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def benachrichtigung(titel, text):
    """Kurze Systemmeldung ("Indexierung fertig")."""
    try:
        def escape(s):
            return s.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{escape(text)}" with title "{escape(titel)}"'
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception as e:
        print(f"[Benachrichtigung fehlgeschlagen] {e}")


def datei_oeffnen(pfad):
    """Oeffnet eine Datei mit dem Standardprogramm."""
    try:
        subprocess.run(["open", pfad], check=True)
        return True
    except Exception as e:
        print(f"[Oeffnen fehlgeschlagen] {e}")
        return False


def im_dateimanager_zeigen(dateipfad):
    """Oeffnet den Finder und markiert die Datei darin."""
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        _still_ausfuehren(["open", "-R", dateipfad])
    except Exception as e:
        print(f"[Dateimanager Fehler] {e}")


def vorschau(dateipfad):
    """Schnellvorschau ohne die Datei wirklich zu oeffnen (Quick Look)."""
    if not dateipfad or not os.path.exists(dateipfad):
        return
    try:
        _still_ausfuehren(["qlmanage", "-p", dateipfad])
    except Exception as e:
        print(f"[Vorschau Fehler] {e}")


def app_pfad():
    """Pfad, mit dem sich SmartSearch selbst erneut starten laesst.

    Das .app-Bundle (NICHT die Programmdatei tief darin - "open" braucht
    das Bundle). Beim Start aus dem Quelltext der Pfad des Skripts.
    """
    pfad = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
    marke = ".app" + os.sep + "Contents" + os.sep
    if marke in pfad:
        return pfad.split(marke)[0] + ".app"
    return pfad


_MAC_PLIST = os.path.expanduser("~/Library/LaunchAgents/com.smartsearch.app.plist")


def autostart_aktiv():
    """Startet SmartSearch aktuell automatisch mit der Anmeldung?"""
    try:
        return os.path.exists(_MAC_PLIST)
    except Exception:
        return False


def autostart_setzen(einschalten):
    """Autostart ueber einen LaunchAgent ein- oder ausschalten.

    Rueckgabe: (True, "") bei Erfolg, sonst (False, Fehlertext).
    """
    try:
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
    except Exception as e:
        return False, str(e)


def systemsprache(unterstuetzt):
    """Erste bevorzugte Sprache des Mac, die SmartSearch kann - oder None.

    Ueber NSLocale statt Pythons locale-Modul: das liefert in einer
    gebauten .app oft nur "C" zurueck. (Stand frueher in i18n.py - dort
    lief es als Mac-Code auch unter Windows mit und fiel dort still aus.)
    """
    try:
        from AppKit import NSLocale
        for code in NSLocale.preferredLanguages():
            kurz = str(code)[:2].lower()
            if kurz in unterstuetzt:
                return kurz
    except Exception:
        pass
    return None


def system_beschreibung():
    """Fuer die Rueckmelde-E-Mail, z. B. "macOS 15.1 (arm64)"."""
    import platform
    return f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
