#!/usr/bin/env python3
"""
menueleiste_mac.py - der Mac-spezifische Teil der Bedienung.

Hier steckt alles, was ueber PyObjC direkt mit macOS spricht:
Menueleisten-Symbol (die Lupe oben rechts), globaler Tastenkurzbefehl,
Dock-Symbol, Fenster nach vorne holen und die Pruefung, ob SmartSearch
schon laeuft.

WARUM AUSGELAGERT
-----------------
Diese Dinge gibt es unter Windows entweder gar nicht oder voellig anders
(Infobereich statt Menueleiste, RegisterHotKey statt NSEvent-Monitor).
Solange sie mitten in gui.py standen, liess sich das Programm auf einem
anderen System nicht einmal starten - schon der Import von AppKit ganz
oben haette es beendet. Jetzt importiert gui.py diese Datei nur auf dem
Mac; das Gegenstueck fuer Windows kommt spaeter als eigene Datei daneben.

Alles hier ist defensiv gebaut: faellt ein Teil aus (fehlende PyObjC-
Version, fehlende Berechtigung), soll die App trotzdem laufen - nur eben
ohne diese Bequemlichkeit.
"""

import os

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
        uebergebene Funktion auf (in gui.py: Fenster auf/zu)."""

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
    gui.py fuer Mac und Windows denselben Aufruf benutzen kann - siehe
    menueleiste_windows.py."""
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
    Der Callback darf deshalb keine Widgets anfassen (in gui.py setzt er
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

    HINTERGRUND: Wird gui.py direkt mit dem Python aus dem venv
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

    gui.py fragt das alle 50 ms ab, um einen Klick auf das App-Symbol
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
