#!/usr/bin/env python3
"""
SmartSearch GUI - Refactored Clean Version (verbessert)
- Integrierter Prozent-Fortschrittsbalken bei Indexierung.
- Light / Dark / System Mode Umschalter.
- Aufgeräumtes, hochwertiges macOS-Design.

Änderungen gegenüber der Vorversion:
- Lock gegen parallele Indexierungs-Läufe (manuell + Watchdog-Trigger können
  sich nicht mehr überschneiden).
- Abbrechen-Button während der Indexierung.
- Watchdog-Observer wird thread-sicher gestartet/gestoppt.
- osascript-Notification escaped Anführungszeichen, um AppleScript nicht
  durch Sonderzeichen im Text zu brechen.
- Kleinere Aufräumarbeiten (Konstanten, Docstrings, defensive Checks).

FIX (siehe Review):
- _index_bg() rief aktualisiere_index() bisher PRO DATEI auf und übergab
  einen Dateipfad. aktualisiere_index() erwartet aber einen ORDNER und
  macht intern os.walk() darauf - bei einem Dateipfad liefert os.walk()
  nichts, wodurch nie etwas indexiert wurde (die GUI zeigte trotzdem
  "erfolgreich" an). Jetzt wird aktualisiere_index() korrekt PRO ORDNER
  aufgerufen, mit fortschritt_fn für die Prozentanzeige pro Datei.
"""

# ZWEITES DOCK-SYMBOL WAEHREND DER INDEXIERUNG
# -------------------------------------------
# In der fertig gebauten .app startet ein Arbeits-Kindprozess (den die
# KI-Bibliotheken beim Indexieren anlegen koennen) nicht einfach einen
# Python-Interpreter, sondern das GESAMTE App-Bundle ein zweites Mal -
# macOS haengt dafuer ein zweites Symbol ins Dock.
#
# multiprocessing.freeze_support() faengt genau das ab: erkennt der
# Prozess, dass er als Arbeitskind gestartet wurde, erledigt er nur seine
# Aufgabe und laeuft nie in den Programmstart weiter unten (Fenster,
# Dock-Symbol, Menueleiste). Das MUSS vor allen schweren Importen stehen,
# sonst baut das Kind vorher noch die halbe Anwendung auf.
import multiprocessing
multiprocessing.freeze_support()

import os as _os_start
# Die Tokenizer-Bibliothek legt sonst eigene Arbeitsprozesse an und warnt
# bei jedem fork. Fuer eine Desktop-App bringt das nichts ausser Unruhe -
# und potenziell genau das zweite Dock-Symbol von oben.
_os_start.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import json
import os
import sys
import time
import re
import webbrowser
import urllib.request
import urllib.error

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_VERFUEGBAR = True
except ImportError:
    WATCHDOG_VERFUEGBAR = False

# BETRIEBSSYSTEM-ABHAENGIGE TEILE
# -------------------------------
# Alles, was je nach System anders funktioniert (Benachrichtigung,
# Vorschau, "im Dateimanager zeigen", Autostart), liegt in plattform.py.
# Alles, was es nur auf dem Mac gibt (Menueleisten-Symbol, globaler
# Tastenkurzbefehl, Dock-Symbol), liegt in menueleiste_mac.py und wird
# NUR auf dem Mac importiert. Frueher stand das alles hier oben als
# harter "from AppKit import ..." - damit liess sich diese Datei auf
# Windows nicht einmal starten.
import plattform

if plattform.IST_MAC:
    import menueleiste_mac as system_ui
elif plattform.IST_WINDOWS:
    import menueleiste_windows as system_ui
else:
    system_ui = None

# Beide Module melden ueber VERFUEGBAR, ob ihre Grundlage wirklich da ist
# (PyObjC auf dem Mac, pystray unter Windows). Fehlt sie, wird system_ui
# bewusst auf None gesetzt: dann gibt es kein Symbol zum Zurueckholen des
# Fensters, und die Oberflaeche darf es nicht mehr automatisch verstecken
# (siehe auf_fokus_verlust) - sonst waere die App unbedienbar.
if system_ui is not None and not getattr(system_ui, "VERFUEGBAR", False):
    print("[Start] Kein Symbol in Menueleiste/Infobereich - Fenster bleibt sichtbar.")
    system_ui = None

import search as smart_search
import ocr
import i18n
from i18n import t
import farben

ctk.set_appearance_mode("System")
# "blue" laedt das vollstaendige Standardthema - farben.thema_anwenden
# ersetzt danach nur die Farbwerte durch die Markenfarben. Das muss vor
# dem ersten Widget passieren, weil CustomTkinter die Werte beim
# Erzeugen liest.
ctk.set_default_color_theme("blue")
farben.thema_anwenden(ctk)

# Siehe pfade.py: liegt in ~/Library/Application Support/SmartSearch,
# damit ein App-Update den Suchverlauf nicht mitloescht.
from pfade import VERLAUF_FILE as VERLAUF_DATEI, DATEN_ORDNER  # noqa: F401
MAX_VERLAUF = 20
PLATZHALTER_TEXT = t("search.placeholder")
UNTERSTUETZTE_ENDUNGEN = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"}

# Fensterbreiten: OHNE Sidebar ist FENSTER_BREITE_ZU die volle Breite für
# den Hauptbereich (Suchfeld, Filter, Ergebnisse). Die Sidebar (220px +
# 8px Abstand) kommt bei geöffneter Seitenleiste ON TOP dazu, statt sich
# den Platz mit dem Hauptbereich zu teilen - so schrumpft der Hauptbereich
# beim Öffnen der Sidebar nicht zusammen.
# Bewusst kompakt: SmartSearch ist ein Quick-Popup zum kurzen Nachschauen
# (auf/finden/zu), kein Programmfenster, in dem man sich länger aufhält -
# vorher war es mit 780x480 spürbar zu groß und "breit und lang" dafür.
FENSTER_BREITE_ZU = 640
FENSTER_BREITE_OFFEN = FENSTER_BREITE_ZU + 220 + 8
FENSTER_HOEHE = 440

# ---------- VERSION & AUTO-UPDATE ----------
# Bei jedem Release von Hand hochzählen (siehe pruefe_auf_updates()).
APP_VERSION = "1.0.4"

# Anschrift fuer Rueckmeldungen. Vor der Veroeffentlichung durch die
# eigene Adresse ersetzen - am besten eine, die zur Domain gehoert.
RUECKMELDUNG_ADRESSE = "kontakt@smartsearch-app.com"

# Die Update-Prüfung fragt GitHub direkt nach dem neuesten Release.
#
# WARUM NICHT MEHR die eigene Website (bis 1.0.2: version.json): Sie liegt
# hinter Cloudflare, und dessen Bot-Erkennung weist Anfragen mit dem
# Standard-User-Agent von Python ("Python-urllib/...") mit HTTP 403 ab -
# nachweislich auch dann, wenn die Browserintegritätsprüfung abgeschaltet
# ist. Genau daran ist die Prüfung in Fassung 1.0.1 gescheitert, ohne dass
# es auffiel: der Fehler wird im Hintergrund still verschluckt. GitHub
# rechnet mit Programmen als Aufrufern und blockt sie nicht.
#
# Kostenlos und ohne Anmeldung. Das Limit liegt bei 60 Anfragen je Stunde
# und IP-Adresse; die App fragt einmal pro Start, das reicht mit großem
# Abstand. Ein Zugangsschlüssel würde das Limit anheben, hat aber in einer
# ausgelieferten App nichts zu suchen - er wäre auslesbar.
GITHUB_RELEASES_API = "https://api.github.com/repos/Marcel-land/SmartSearch/releases/latest"
UPDATE_CHECK_TIMEOUT_SEK = 5

DATEITYP_GRUPPEN = {
    "PDF": {".pdf"},
    "Word": {".docx"},
    "Excel": {".xlsx"},
    "PowerPoint": {".pptx"},
    "Text": {".txt", ".md"},
}

# Die Toene stehen in farben.py, zusammen mit den geprueften
# Kontrastwerten gegen die weisse Schrift.
BADGE_FARBEN = farben.BADGE_FARBEN


def _download_adresse(release):
    """Sucht im Release die DMG heraus - sonst die Release-Seite.

    Die DMG-Adresse startet den Download unmittelbar. Fehlt sie (etwa weil
    ein Release ohne Anhang veröffentlicht wurde), landet der Benutzer
    wenigstens auf der Release-Seite und nicht im Nichts.
    """
    for anhang in release.get("assets") or []:
        if (anhang.get("name") or "").lower().endswith(".dmg"):
            return anhang.get("browser_download_url") or ""
    return release.get("html_url") or ""


def _release_notizen(text, max_zeilen=5, max_zeichen=400):
    """Macht aus dem Release-Text von GitHub ein paar lesbare Zeilen.

    Der Text ist Markdown und enthält neben den Änderungen oft auch
    Installationshinweise. Im Hinweisfenster interessiert nur der Anfang:
    alles ab einer Trennlinie (---) entfällt, Überschriften ebenso,
    Aufzählungszeichen werden zu Punkten.

    Zur Einrückung: Eine Zeile gilt nur dann als Fortsetzung der
    vorherigen, wenn sie eingerückt ist UND darüber eine Aufzählung stand.
    Ohne diese Bedingung würden fünf gleichwertige Absätze - so sieht der
    Text von 1.0.2 aus - zu einem einzigen Klumpen zusammenlaufen.
    """
    zeilen = []
    letzte_war_aufzaehlung = False

    for rohzeile in (text or "").splitlines():
        zeile = rohzeile.strip()
        if zeile.startswith("---"):
            break
        if not zeile or zeile.startswith("#"):
            letzte_war_aufzaehlung = False
            continue

        eingerueckt = rohzeile[:1] in (" ", "\t")
        if zeile.startswith(("- ", "* ")):
            if len(zeilen) >= max_zeilen:
                break
            zeilen.append("• " + zeile[2:])
            letzte_war_aufzaehlung = True
        elif eingerueckt and letzte_war_aufzaehlung and zeilen:
            zeilen[-1] += " " + zeile
        else:
            if len(zeilen) >= max_zeilen:
                break
            zeilen.append(zeile)
            letzte_war_aufzaehlung = False

    ergebnis = "\n".join(zeilen)
    if len(ergebnis) > max_zeichen:
        ergebnis = ergebnis[:max_zeichen].rstrip() + " …"
    return ergebnis


def _version_tuple(v):
    """Wandelt einen Versionsstring wie '1.2.10' in (1, 2, 10) um, damit
    Versionen NUMERISCH statt als Text verglichen werden - ein reiner
    Textvergleich würde z.B. '1.9.0' fälschlich für neuer als '1.10.0'
    halten."""
    teile = []
    for stueck in v.strip().split("."):
        ziffern = re.match(r"\d+", stueck)
        teile.append(int(ziffern.group()) if ziffern else 0)
    return tuple(teile)




# Ordner-/Datei-Fragmente, die NIE einen Re-Index auslösen sollen. Das sind
# typische App-eigene Pfade (venv, .git, __pycache__) und die eigenen
# Datenablagen der App (verlauf.json, Index-/Cache-Dateien). Ohne diesen
# Filter löst die App durch ihr eigenes Schreiben (Index speichern, Verlauf
# speichern) ständig neue Watchdog-Events aus und indexiert sich selbst in
# eine Endlosschleife.
IGNORIERTE_PFAD_FRAGMENTE = {
    os.sep + "venv" + os.sep,
    os.sep + ".venv" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "__pycache__" + os.sep,
    os.sep + "build" + os.sep,
    os.sep + "dist" + os.sep,
}
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
    return ext in UNTERSTUETZTE_ENDUNGEN


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


class SmartSearchNotchWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.toggle_requested = False
        # Wird vom Menue des Symbols in der Menueleiste bzw. im
        # Infobereich gesetzt. Beide laufen in einem fremden Thread und
        # duerfen deshalb nur ein Flag setzen - abgefragt wird es im
        # Tk-Hauptthread, siehe check_toggle_loop().
        self.beenden_requested = False

        self.title("SmartSearch")
        self.attributes("-topmost", True)
        self.geometry(f"{FENSTER_BREITE_ZU}x{FENSTER_HOEHE}")

        # -topmost wird IMMER nur reaktiviert, wenn SmartSearch selbst
        # wieder den Fokus bekommt (Klick zurück ins Fenster) - nie mehr
        # automatisch per Timer. So bleiben geöffnete Dateien/Vorschauen
        # und eigene Dialoge (Ordner verwalten, Nicht lesbare Dateien)
        # zuverlässig im Vordergrund, statt dass SmartSearch sich nach
        # kurzer Zeit von selbst wieder darüber schiebt.
        self.bind("<FocusIn>", self._auf_fokus_gewinn)

        self.verlauf = self.lade_verlauf()
        self.aktuelle_treffer = []
        self.favoriten = smart_search.lade_favoriten()
        self.sidebar_offen = False

        # Erster Start = noch kein einziger überwachter Ordner konfiguriert.
        # Wird am Ende von __init__ genutzt, um automatisch den
        # Onboarding-Dialog zu zeigen, statt den Nutzer vor einem leeren
        # "Bereit für deine Suche."-Fenster stehen zu lassen, ohne dass
        # klar ist, dass man erst einen Ordner hinzufügen muss.
        self.ist_erster_start = not smart_search.lade_config().get("ordner")

        self.fokussierter_index = -1
        self.card_widgets = []
        self.observer = None
        self.observer_lock = threading.Lock()

        # Schutz gegen parallele Indexierungs-Läufe (manuell + Watchdog)
        self.indexierung_lock = threading.Lock()
        self.indexierung_laeuft = False
        self.aktuelle_such_woerter = []
        self.indexierung_abbrechen = False

        self._sperrbare_buttons = []

        # Zustand, der beim Sprachwechsel (siehe wende_sprache_live_an())
        # NICHT zurückgesetzt werden darf - deshalb hier einmalig statt in
        # _baue_oberflaeche(), das bei jedem Sprachwechsel erneut läuft.
        self.einstellungen_fenster = None
        self.aktueller_theme_modus = "System"
        self.autostart_var = ctk.BooleanVar(value=self.ist_autostart_aktiv())

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Hauptcontainer (Clean Mac Look) - bleibt über die gesamte
        # Lebensdauer des Fensters bestehen. Nur sein INHALT
        # (sidebar_frame/main_frame) wird bei einem Sprachwechsel neu
        # aufgebaut, siehe _baue_oberflaeche() / wende_sprache_live_an().
        self.bg_frame = ctk.CTkFrame(self, corner_radius=14, border_width=1)
        self.bg_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.bg_frame.grid_columnconfigure(1, weight=1)
        self.bg_frame.grid_rowconfigure(0, weight=1)

        self._baue_oberflaeche()
        self._nach_oberflaechenaufbau_starten()

    def _baue_oberflaeche(self):
        """Baut Seitenleiste + Hauptbereich (Suchfeld, Filter, Ergebnisse,
        Statusleiste) innerhalb von self.bg_frame auf.

        Ausgelagert aus __init__(), damit wende_sprache_live_an() nach
        einem Sprachwechsel exakt dieselbe Oberfläche mit den neuen Texten
        neu erzeugen kann, ohne echten Zustand (Fenstergröße, Theme,
        Autostart-Einstellung, Preferences-Fenster-Referenz) zu verlieren -
        der liegt bewusst NICHT hier, sondern einmalig in __init__.
        """
        # ================= SEITENLEISTE =================
        # Bewusst schlank gehalten: nur die Aktionen, die man beim Suchen
        # wirklich oft braucht. Alles Seltene (Erscheinungsbild, Autostart,
        # Backup, Datenschutz) sitzt im separaten Preferences-Fenster (siehe
        # oeffne_einstellungen_fenster()) - dadurch muss man hier nie mehr
        # scrollen, um z.B. an den Datenschutz-Hinweis zu kommen, und es
        # gibt Platz für künftige Einstellungen.
        self.sidebar_frame = ctk.CTkFrame(self.bg_frame, width=220, corner_radius=12)

        self.sidebar_title = ctk.CTkLabel(self.sidebar_frame, text=t("sidebar.title"), font=("Helvetica", 14, "bold"))
        self.sidebar_title.pack(padx=15, pady=(12, 6), anchor="w")

        # Erscheinungsbild: bewusst wieder hier im Schnellzugriff (statt nur
        # im Preferences-Fenster) - wird oft genug gewechselt, dass ein
        # zusätzlicher Klick ins Einstellungsfenster unnötig nervt.
        self.theme_label = ctk.CTkLabel(self.sidebar_frame, text=t("sidebar.appearance"), font=("Helvetica", 10), text_color="#78909c")
        self.theme_label.pack(padx=15, pady=(3, 2), anchor="w")

        # Beschriftung <-> interner CustomTkinter-Modus.
        #
        # WARUM DIESE TABELLE: CustomTkinter kennt ausschliesslich die
        # englischen Werte "System", "Light" und "Dark". Die Knoepfe zeigen
        # aber die uebersetzte Beschriftung ("Hell"/"Dunkel"). Frueher ging
        # genau dieses deutsche Wort direkt an ctk.set_appearance_mode(),
        # das unbekannte Werte stillschweigend verwirft - der Umschalter
        # sah funktionsfaehig aus, tat auf Deutsch aber nichts.
        self.theme_label_zu_modus = {
            t("sidebar.theme_system"): "System",
            t("sidebar.theme_light"): "Light",
            t("sidebar.theme_dark"): "Dark",
        }
        self.theme_modus_zu_label = {
            modus: label for label, modus in self.theme_label_zu_modus.items()
        }

        self.theme_seg = ctk.CTkSegmentedButton(
            self.sidebar_frame,
            values=list(self.theme_label_zu_modus.keys()),
            command=self.theme_wechseln, font=("Helvetica", 10)
        )
        # Beim Neuaufbau (Sprachwechsel) den zuletzt gewaehlten Modus
        # wieder vorauswaehlen, nicht stumpf "System".
        self.theme_seg.set(self.theme_modus_zu_label.get(
            getattr(self, "aktueller_theme_modus", "System"), t("sidebar.theme_system")))
        self.theme_seg.pack(padx=12, pady=(0, 8), fill="x")

        # Beenden-Button: fest am unteren Rand verankert, damit er nie durch
        # zusätzliche Einträge (z.B. den Fehler-Button) verdeckt wird. Der
        # größere Abstand nach unten (16px) ist bewusst so belassen - sonst
        # wird der Button optisch von der abgerundeten Fensterecke
        # "verschluckt" (siehe frühere Anpassung).
        self.quit_button = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.quit"), fg_color=farben.BEENDEN, hover_color=farben.BEENDEN_HOVER, anchor="w", command=self.beenden
        )
        self.quit_button.pack(padx=12, pady=(8, 16), fill="x", side="bottom")

        self.btn_favs_anzeigen = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.favorites"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=self.favoriten_anzeigen
        )
        self.btn_favs_anzeigen.pack(padx=12, pady=3, fill="x")

        self.add_folder_button = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.add_folder"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=self.ordner_hinzufuegen_gui
        )
        self.add_folder_button.pack(padx=12, pady=3, fill="x")

        self.manage_button = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.manage_folders"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=self.ordner_verwalten_gui
        )
        self.manage_button.pack(padx=12, pady=3, fill="x")

        self.index_button = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.update_index"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=self.index_aktualisieren
        )
        self.index_button.pack(padx=12, pady=3, fill="x")

        # Warnbutton für Dateien, die beim Indexieren nicht gelesen werden
        # konnten (siehe search.fehlgeschlagene_dateien()). Standardmäßig
        # versteckt (kein .pack()) - wird nach jedem Indexierungslauf in
        # _index_fertig() ein- oder ausgeblendet, je nachdem ob es
        # fehlgeschlagene Dateien gibt. Vorher landeten solche Fehler nur
        # im Terminal und wurden im Alltag (z.B. bei Autostart im
        # Hintergrund) nie bemerkt. Bleibt bewusst im Schnellzugriff (statt
        # im Preferences-Fenster), weil es eine zeitnah wichtige Meldung
        # ist - siehe pack(after=self.index_button) in
        # aktualisiere_fehler_anzeige().
        self.btn_fehler_anzeigen = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.errors_button", anzahl=0), fg_color="#e65100", hover_color="#bf360c",
            anchor="w", command=self.fehlgeschlagene_dateien_dialog
        )

        self.einstellungen_button = ctk.CTkButton(
            self.sidebar_frame, text=t("sidebar.settings"), fg_color="transparent", hover_color=("#e0e0e0", "#3a3a3a"),
            text_color=("#37474f", "#b0bec5"), anchor="w", command=self.oeffne_einstellungen_fenster
        )
        self.einstellungen_button.pack(padx=12, pady=(6, 4), anchor="w")

        # ================= HAUPTBEREICH =================
        self.main_frame = ctk.CTkFrame(self.bg_frame, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # --- SEARCH BAR ---
        self.top_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        self.top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.sidebar_toggle_btn = ctk.CTkButton(
            self.top_frame, text="☰", width=32, height=34, fg_color="transparent", hover_color=("#e0e0e0", "#3a3a3a"), command=self.toggle_sidebar
        )
        self.sidebar_toggle_btn.grid(row=0, column=0, padx=(6, 2), pady=4)

        self.suchfeld = ctk.CTkEntry(
            self.top_frame, font=("Helvetica", 13), height=34, border_width=0, placeholder_text=PLATZHALTER_TEXT
        )
        self.suchfeld.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.suchfeld.bind("<Return>", lambda event: self.suchen())

        self.such_button = ctk.CTkButton(self.top_frame, text=t("search.button"), width=75, height=34, font=("Helvetica", 11, "bold"), command=self.suchen)
        self.such_button.grid(row=0, column=2, padx=(4, 6), pady=4)

        # ZWEI getrennte Button-Gruppen: Ordner-/Index-bezogene Buttons
        # werden nur während einer laufenden Indexierung gesperrt (damit
        # kein zweiter Lauf gestartet oder ein Ordner mittendrin entfernt
        # wird). Der Suchen-Button bleibt bewusst davon UNABHÄNGIG - dank
        # der regelmäßigen Zwischenspeicherung in aktualisiere_index()
        # (siehe search.py) kann während einer laufenden Indexierung schon
        # nach den bereits fertig verarbeiteten Dateien gesucht werden,
        # statt bis zum kompletten Abschluss warten zu müssen.
        self._index_sperrbare_buttons = [
            self.add_folder_button,
            self.manage_button,
            self.index_button,
            self.btn_favs_anzeigen
        ]
        self._suche_sperrbare_buttons = [self.such_button]

        # Rückwärtskompatibler Name (falls an anderer Stelle noch
        # referenziert) - zeigt auf die Index-Gruppe.
        self._sperrbare_buttons = self._index_sperrbare_buttons

        # --- FILTER ---
        self.filter_frame = ctk.CTkFrame(self.main_frame, height=28, corner_radius=6, fg_color="transparent")
        self.filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.filter_variablen = {}
        for label in DATEITYP_GRUPPEN:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self.filter_frame, text=label, variable=var, font=("Helvetica", 10),
                command=self.suchen
            )
            cb.pack(side="left", padx=3, pady=1)
            self.filter_variablen[label] = var

        # ZEITRAUM_CODES: Anzeige-Text (übersetzt) -> sprachunabhängiger Code,
        # den search.py._zeitraum_cutoff() versteht. Nötig, weil sich der
        # angezeigte Menütext je nach Sprache ändert (z.B. "7 Tage" vs.
        # "7 Days") - ein Vergleich gegen den angezeigten Text würde in der
        # jeweils anderen Sprache nie mehr treffen.
        self.zeitraum_anzeige_zu_code = {
            t("filter.all_time"): "alle",
            t("filter.7_days"): "7_tage",
            t("filter.this_month"): "monat",
            t("filter.this_year"): "jahr",
        }
        self.zeitraum_menu = ctk.CTkOptionMenu(
            self.filter_frame, values=list(self.zeitraum_anzeige_zu_code.keys()),
            width=100, height=22, font=("Helvetica", 10), command=lambda e: self.suchen()
        )
        self.zeitraum_menu.pack(side="right", padx=2, pady=1)
        self.zeitraum_menu.set(t("filter.all_time"))

        # --- ERGEBNISSE ---
        self.ergebnis_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.ergebnis_container.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.ergebnis_container.grid_columnconfigure(0, weight=1)
        self.ergebnis_container.grid_rowconfigure(0, weight=1)

        self.cards_scrollframe = ctk.CTkScrollableFrame(self.ergebnis_container, corner_radius=8)
        self.cards_scrollframe.grid(row=0, column=0, sticky="nsew")
        self.cards_scrollframe.grid_columnconfigure(0, weight=1)

        # Touchpad-/Mausrad-Scrolling global aktivieren - deckt jetzt BEIDE
        # scrollbaren Bereiche ab (Ergebnisliste UND die neue scrollbare
        # Seitenleiste), siehe aktiviere_touchpad_scrolling_global().
        self.aktiviere_touchpad_scrolling_global()

        self.lbl_welcome = ctk.CTkLabel(
            self.cards_scrollframe,
            text=t("welcome.text"),
            font=("Helvetica", 12), text_color="#78909c"
        )
        self.lbl_welcome.pack(pady=40)

        # PROZENT & STATUSLEISTE
        # Leise Bitte um Rueckmeldung. Sie liegt zwischen Ergebnissen und
        # Statuszeile und ist beim Start nicht eingeblendet - erst nach
        # einigen erfolgreichen Suchen, also wenn jemand das Programm
        # tatsaechlich benutzt. Grund: der Rueckmeldeknopf in den
        # Einstellungen wird faktisch nie gefunden, und ohne Konto und ohne
        # Nutzungsdaten gibt es sonst keinen Weg, von den Nutzern zu hoeren.
        self.rueckmeldung_leiste = ctk.CTkFrame(
            self.main_frame, corner_radius=8,
            fg_color=("#eceff1", "#263238"))
        self.rueckmeldung_leiste.grid_columnconfigure(0, weight=1)
        self._rueckmeldung_sichtbar = False

        ctk.CTkLabel(
            self.rueckmeldung_leiste, text=t("feedback.bar_text"),
            font=("Helvetica", 11), text_color=("#455a64", "#b0bec5"),
            anchor="w", justify="left", wraplength=380
        ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=10)

        ctk.CTkButton(
            self.rueckmeldung_leiste, text=t("feedback.bar_button"),
            width=150, height=26, font=("Helvetica", 11),
            fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            command=self._rueckmeldung_schreiben
        ).grid(row=0, column=1, padx=(0, 6), pady=10)

        ctk.CTkButton(
            self.rueckmeldung_leiste, text=t("feedback.bar_later"),
            width=86, height=26, font=("Helvetica", 11),
            fg_color="transparent", hover_color=("#cfd8dc", "#37474f"),
            text_color=("#607d8b", "#90a4ae"),
            command=self._rueckmeldung_spaeter
        ).grid(row=0, column=2, padx=(0, 10), pady=10)

        self.status_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_container.grid(row=4, column=0, sticky="ew", padx=2)
        self.status_container.grid_columnconfigure(0, weight=1)

        self.status_bar = ctk.CTkLabel(self.status_container, text=t("status.ready"), anchor="w", font=("Helvetica", 10), text_color="#78909c")
        self.status_bar.grid(row=0, column=0, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.status_container, width=160, height=8, corner_radius=4)
        self.progress_bar.set(0)

        self.btn_index_abbrechen = ctk.CTkButton(
            self.status_container, text=t("cancel"), width=70, height=20, font=("Helvetica", 9),
            fg_color=farben.WARNUNG, hover_color=farben.WARNUNG_HOVER, command=self.index_abbrechen
        )

    # ---------- SPRACHWECHSEL OHNE NEUSTART ----------

    def wende_sprache_live_an(self, code):
        """Wechselt die Sprache SOFORT, ohne die App neu starten zu
        müssen: speichert die Auswahl dauerhaft (i18n.setze_sprache) UND
        setzt die aktive Modul-Sprache direkt um (i18n.SPRACHE), dann wird
        die komplette Seitenleiste + Hauptbereich mit den neuen Texten neu
        aufgebaut (siehe _baue_oberflaeche()).

        UI-Zustand (Sidebar offen/zu, Theme, Suchtext, aktive Filter,
        Zeitraum-Auswahl, aktuelle Trefferliste, ob das Preferences-Fenster
        gerade offen war) wird vorher gesichert und danach wieder-
        hergestellt, damit sich der Wechsel nicht wie ein harter Reset
        anfühlt."""
        if code == i18n.aktuelle_sprache():
            return

        # --- Zustand sichern ---
        war_sidebar_offen = self.sidebar_offen
        such_text = self.suchfeld.get()
        aktive_filter_labels = {label for label, var in self.filter_variablen.items() if var.get()}
        zeitraum_code = self.zeitraum_anzeige_zu_code.get(self.zeitraum_menu.get(), "alle")
        einstellungen_war_offen = (
            self.einstellungen_fenster is not None and self.einstellungen_fenster.winfo_exists()
        )

        # --- Sprache umschalten ---
        i18n.setze_sprache(code)
        i18n.SPRACHE = code

        # Preferences-Fenster hängt NICHT an bg_frame und würde sonst mit
        # alten Texten (Tab-Namen etc.) stehen bleiben - vor dem Neuaufbau
        # schließen, danach ggf. frisch wieder öffnen.
        if einstellungen_war_offen:
            self.einstellungen_fenster.destroy()
            self.einstellungen_fenster = None

        # --- Oberfläche neu aufbauen ---
        self.sidebar_frame.destroy()
        self.main_frame.destroy()
        global PLATZHALTER_TEXT
        PLATZHALTER_TEXT = t("search.placeholder")
        self._baue_oberflaeche()

        # --- Zustand wiederherstellen ---
        if war_sidebar_offen:
            self.sidebar_offen = False  # toggle_sidebar() erwartet den bisherigen Zustand
            self.toggle_sidebar()

        # self.aktueller_theme_modus haelt den internen Wert
        # ("System"/"Light"/"Dark"), der Knopf zeigt die uebersetzte
        # Beschriftung - deshalb hier ueber die Tabelle umrechnen.
        self.theme_seg.set(self.theme_modus_zu_label.get(
            self.aktueller_theme_modus, t("sidebar.theme_system")))

        if such_text and such_text != PLATZHALTER_TEXT:
            self.suchfeld.insert(0, such_text)

        for label, var in self.filter_variablen.items():
            var.set(label in aktive_filter_labels)

        for anzeige, code_wert in self.zeitraum_anzeige_zu_code.items():
            if code_wert == zeitraum_code:
                self.zeitraum_menu.set(anzeige)
                break

        self.aktualisiere_fehler_anzeige()
        if self.aktuelle_treffer:
            self.zeige_aktuelle_ergebnisse()

        if einstellungen_war_offen:
            self.oeffne_einstellungen_fenster()

    # ---------- SIGNAL-POLLING / ERSTER START ----------

    def _nach_oberflaechenaufbau_starten(self):
        """Einmaliger Start-Kram, der NICHT bei jedem Sprachwechsel erneut
        laufen darf (Tastaturkürzel, Cmd+Q-Handling, Ordnerüberwachung,
        Hotkey, Update-Check, Onboarding) - wird von __init__() genau
        einmal aufgerufen, siehe dort."""
        # KURZWAHLTASTEN
        self.bind("<Down>", self.fokus_nach_unten)
        self.bind("<Up>", self.fokus_nach_oben)
        self.bind("<space>", self.quicklook_fokussiert)
        self.bind("<Escape>", lambda e: self.withdraw())
        self.bind("<Command-k>", lambda e: self.suchfeld.focus_set())

        # Cmd+Q sauber abfangen: Tk installiert auf macOS automatisch ein
        # eigenes "Quit"-Verhalten für Cmd+Q über die ::tk::mac::Quit-
        # Prozedur, die OHNE diese Zeile direkt den Interpreter beendet -
        # AN beenden() vorbei. Das würde den Watchdog-Observer und
        # laufende Indexierungs-Threads nicht sauber stoppen. Mit
        # createcommand landet Cmd+Q stattdessen bei genau derselben
        # Aufräum-Logik wie der "Beenden"-Button.
        # WICHTIG: führende "::" nicht weglassen - ohne den vollqualifizierten
        # Namen registriert Tcl einen ANDEREN Befehl, den Tks macOS-Aqua-
        # Integration beim Cmd+Q nie aufruft (genau das war der Bug: Cmd+Q
        # hat einfach nichts getan, statt beenden() auszulösen).
        self.createcommand("::tk::mac::Quit", self.beenden)

        # KLICK AUF DAS APP-SYMBOL (Dock, Finder, Launchpad, Spotlight)
        # ------------------------------------------------------------
        # SmartSearch versteckt sein Fenster, sobald es den Fokus verliert
        # (Popup-Charakter). Wer danach das App-Symbol anklickt, erwartet -
        # wie bei jeder anderen Mac-App - dass das Fenster wieder da ist.
        # Ohne die folgende Zeile passierte schlicht GAR NICHTS: das
        # Programm lief ja schon, macOS holte es nur nach vorne, und das
        # versteckte Fenster blieb versteckt. Das Menueleisten-Symbol war
        # damit der einzige Weg hinein - und genau das ist unbrauchbar,
        # wenn die Menueleiste voll ist und das Lupensymbol nicht mehr
        # sichtbar ist.
        #
        # ::tk::mac::ReopenApplication ruft macOS auf, wenn eine BEREITS
        # LAUFENDE App erneut angeklickt wird. Der ganz normale Start wird
        # weiter unten behandelt (siehe "--autostart"), damit der
        # automatische Start bei der Anmeldung unsichtbar bleiben kann.
        self.createcommand("::tk::mac::ReopenApplication", self.fenster_anzeigen_von_extern)

        self.bind("<FocusOut>", self.auf_fokus_verlust)
        self.withdraw()

        self.starte_ordner_überwachung()
        self.waerme_modell_vor()
        self.aktualisiere_fehler_anzeige()
        self.check_toggle_loop()
        self.registriere_globalen_hotkey()
        self.pruefe_auf_updates(manuell=False)
        self.pruefe_index_passt()

        if self.ist_erster_start:
            # Fenster aktiv zeigen (statt versteckt zu bleiben) und kurz
            # danach den Setup-Guide öffnen, damit ein neuer Nutzer nicht
            # vor einem leeren "Bereit für deine Suche."-Fenster steht,
            # ohne zu wissen, was die App überhaupt anders macht und dass
            # erst ein Ordner eingelesen werden muss.
            self.zeige_unter_notch()
            self.after(300, self.zeige_setup_guide)
        elif "--autostart" not in sys.argv:
            # Wer die App bewusst startet (Doppelklick im Finder, Dock,
            # Launchpad), will sie auch sehen. Frueher startete SmartSearch
            # unsichtbar und man musste erst das Lupensymbol in der
            # Menueleiste suchen. Nur beim automatischen Start mit der
            # Anmeldung (--autostart, siehe autostart_umschalten) bleibt
            # das Fenster wie gewohnt im Hintergrund.
            self.after(200, self.zeige_unter_notch)

    # ---------- THEME WECHSELN ----------

    def theme_wechseln(self, auswahl):
        """Umschalten zwischen System / Hell / Dunkel.

        WICHTIG: `auswahl` ist die ANGEZEIGTE Beschriftung des Knopfes, auf
        Deutsch also "Hell" bzw. "Dunkel". CustomTkinter versteht nur
        "System"/"Light"/"Dark" und ignoriert alles andere kommentarlos -
        genau daran scheiterte der Umschalter vorher. Deshalb wird die
        Beschriftung hier erst in den internen Modus uebersetzt.

        Eigener Merker statt ctk.get_appearance_mode(): CustomTkinter loest
        "System" sofort in "Light"/"Dark" auf, d.h. get_appearance_mode()
        gibt nie "System" zurueck - der Knopf wuerde beim Neuaufbau sonst
        faelschlich "Hell" oder "Dunkel" vorauswaehlen.
        """
        modus = getattr(self, "theme_label_zu_modus", {}).get(auswahl, auswahl)
        if modus not in ("System", "Light", "Dark"):
            modus = "System"
        self.aktueller_theme_modus = modus
        ctk.set_appearance_mode(modus)

    # ---------- PROZENT-FORTSCHRITT ----------

    def zeige_fortschritt(self, prozent, text=""):
        self.progress_bar.grid(row=0, column=1, sticky="e", padx=4)
        self.progress_bar.set(prozent)
        if text:
            self.setze_status(text)

    def verstecke_fortschritt(self):
        self.progress_bar.grid_forget()
        self.btn_index_abbrechen.grid_forget()

    # ---------- TOUCHPAD SCROLLING ----------

    def aktiviere_touchpad_scrolling_global(self):
        """Bindet EINMAL global das Touchpad-/Mausrad-Scrollen und leitet es
        an das scrollbare Widget weiter, über dem sich der Mauszeiger gerade
        befindet. Aktuell nur die Ergebnisliste - die Seitenleiste ist
        wieder ein normales, festes Frame (siehe __init__: die Sidebar
        wurde bewusst schlank gehalten, ein separates Preferences-Fenster
        übernimmt jetzt die selten gebrauchten Einstellungen). Als Liste
        statt Einzelwidget gehalten, damit spätere scrollbare Bereiche
        (z.B. in einem Preferences-Tab) sich einfach ergänzen lassen, ohne
        dass sich mehrere bind_all()-Aufrufe gegenseitig überschreiben.
        """
        scrollbare_bereiche = (self.cards_scrollframe,)

        def _on_mousewheel(event):
            if not event.delta:
                return
            widget = event.widget
            while widget is not None:
                if widget in scrollbare_bereiche:
                    widget._parent_canvas.yview_scroll(int(-1 * event.delta), "units")
                    return
                widget = getattr(widget, "master", None)

        self.bind_all("<MouseWheel>", _on_mousewheel)

    # ---------- FENSTER / SIGNAL-POLLING ----------

    def check_toggle_loop(self):
        if self.beenden_requested:
            self.beenden_requested = False
            self.beenden()
            return
        if self.toggle_requested:
            self.toggle_requested = False
            self.toggle_fenster()
        self._pruefe_zeigen_signal()
        self._pruefe_dock_klick()
        self.after(50, self.check_toggle_loop)

    def fenster_anzeigen_von_extern(self):
        """Fenster zeigen, angestossen von ausserhalb des Tk-Hauptthreads
        oder von macOS (Klick aufs App-Symbol). Immer ZEIGEN, nie
        umschalten - sonst wuerde ein Klick aufs Dock-Symbol das gerade
        sichtbare Fenster wieder zuklappen."""
        try:
            self.after(0, self.zeige_unter_notch)
        except Exception:
            pass

    def waerme_modell_vor(self):
        """Laedt das KI-Modell gleich nach dem Start im Hintergrund.

        Ohne das passiert es erst bei der ersten Suche - und dann wartet
        man einmal zehn Sekunden und laenger auf ein Ergebnis, das danach
        in Bruchteilen einer Sekunde da ist. Genau dieser erste Eindruck
        ist es, den man als "die App sucht ewig" in Erinnerung behaelt.

        Bewusst nur, wenn das Modell schon auf der Platte liegt: sonst
        wuerde der Programmstart ungefragt einen zwei Gigabyte grossen
        Download anstossen.

        Fehler werden hier absichtlich nur protokolliert. Geht etwas
        schief, faellt es bei der echten Suche ohnehin wieder auf - dort
        mit einer Erklaerung fuer den Nutzer.
        """
        def _laden():
            try:
                if smart_search.modell_ist_vorhanden():
                    smart_search.geladenes_modell()
            except Exception as e:
                print(f"[Start] Modell-Vorladen uebersprungen: {e}")

        threading.Thread(target=_laden, daemon=True).start()

    # ---------- NEBENFENSTER (Dialoge) ----------

    @staticmethod
    def _fenster_lebt(fenster):
        try:
            return bool(fenster.winfo_exists())
        except Exception:
            return False

    def nebenfenster_offen(self):
        """True, solange mindestens ein Dialog offen ist."""
        offen = [f for f in getattr(self, "_nebenfenster", []) if self._fenster_lebt(f)]
        self._nebenfenster = offen
        return bool(offen)

    def nebenfenster_anmelden(self, fenster):
        """Merkt sich einen offenen Dialog (Einstellungen, Ordnerliste,
        Setup-Hilfe ...) und holt ihn nach vorne.

        WARUM NOETIG: Das Hauptfenster haelt sich mit -topmost ganz oben
        und setzt das bei jedem Fokus erneut. Ein Dialog rutschte dabei
        dahinter und wirkte geschlossen, obwohl er noch offen war. Ueber
        diese Liste weiss das Hauptfenster, dass es sich gerade NICHT nach
        oben setzen darf (siehe _auf_fokus_gewinn).
        """
        self.nebenfenster_offen()          # raeumt geschlossene Fenster weg
        offen = getattr(self, "_nebenfenster", [])
        if fenster not in offen:
            offen.append(fenster)
        self._nebenfenster = offen

        # Solange ein Dialog offen ist, gibt das Hauptfenster den
        # Vordergrund ab - sonst konkurrieren zwei -topmost-Fenster und
        # das zuletzt gehobene gewinnt.
        try:
            self.attributes("-topmost", False)
        except Exception:
            pass
        try:
            fenster.lift()
            fenster.focus_force()
        except Exception:
            pass

    def nebenfenster_heben(self):
        """Holt alle noch offenen Dialoge wieder vor das Hauptfenster."""
        if not self.nebenfenster_offen():
            return
        for fenster in self._nebenfenster:
            try:
                fenster.attributes("-topmost", True)
                fenster.lift()
            except Exception:
                pass
        try:
            self._nebenfenster[-1].focus_force()
        except Exception:
            pass

    def _auf_fokus_gewinn(self, event=None):
        """Das Hauptfenster haelt sich normalerweise ganz oben (es ist ein
        Popup, das ueber allem liegen soll). Ist aber ein eigener Dialog
        offen, darf es sich NICHT wieder nach oben setzen - sonst
        verschwindet der Dialog dahinter."""
        try:
            if self.nebenfenster_offen():
                self.attributes("-topmost", False)
                self.after(60, self.nebenfenster_heben)
            else:
                self.attributes("-topmost", True)
        except Exception:
            pass

    def _pruefe_dock_klick(self):
        """Klick auf das App-Symbol im Dock, Launchpad oder Cmd+Tab soll
        das Fenster zurueckholen - ohne Umweg ueber die Lupe.

        Dafuer ist eigentlich ::tk::mac::ReopenApplication zustaendig
        (siehe __init__), diese Meldung kommt im gebauten Bundle aber nicht
        zuverlaessig an. Deshalb hier der zweite, unabhaengige Weg: macOS
        macht SmartSearch beim Klick aufs Symbol zur aktiven Anwendung.
        Wechselt der Zustand von "nicht aktiv" auf "aktiv" und ist das
        Fenster versteckt, wird es gezeigt.

        Bewusst nur die FLANKE (nicht-aktiv -> aktiv): sonst wuerde das
        Fenster unmittelbar nach jedem Verstecken wieder aufspringen.
        """
        if not system_ui or not hasattr(system_ui, "app_ist_aktiv"):
            return
        try:
            aktiv = system_ui.app_ist_aktiv()
            if aktiv is None:
                return
            war_aktiv = getattr(self, "_war_aktiv", True)
            self._war_aktiv = aktiv
            if aktiv and not war_aktiv and self.state() == "withdrawn":
                self.zeige_unter_notch()
        except Exception as e:
            print(f"[Dock] Klick-Erkennung fehlgeschlagen: {e}")

    def _pruefe_zeigen_signal(self):
        """Wurde SmartSearch ein zweites Mal gestartet, legt die zweite
        Kopie diese Datei an und beendet sich sofort wieder (siehe
        _bereits_offene_instanz_aktivieren). Diese - die laufende - Kopie
        holt daraufhin ihr Fenster nach vorne. Ergebnis: ein Doppelklick
        auf die App fuehrt IMMER zum sichtbaren Fenster, egal ob sie schon
        laeuft, und nie zu einer zweiten Instanz."""
        try:
            if os.path.exists(ZEIGEN_SIGNAL):
                os.remove(ZEIGEN_SIGNAL)
                self.zeige_unter_notch()
        except Exception:
            pass

    def registriere_globalen_hotkey(self):
        """Cmd+Shift+F oeffnet SmartSearch von UEBERALL aus, auch wenn eine
        andere App im Vordergrund ist - genau der "schnell aufploppen"-
        Charakter, den ein Suchwerkzeug braucht.

        Die eigentliche Registrierung ist Systemsache und steht deshalb in
        menueleiste_mac.py. Hier wird nur festgelegt, WAS passieren soll:
        dasselbe wie beim Klick auf das Menueleisten-Symbol - ein Flag
        setzen, das check_toggle_loop() alle 50 ms im Tk-Hauptthread
        abfragt. Wichtig, weil der Tastatur-Handler auf Apples Event-Loop
        laeuft und Tkinter-Widgets von dort nicht angefasst werden duerfen.
        """
        if not system_ui:
            return

        def _ausloesen():
            self.toggle_requested = True

        self._hotkey_monitor = system_ui.registriere_globalen_hotkey(_ausloesen)

    def zeige_unter_notch(self):
        screen_width = self.winfo_screenwidth()
        fenster_breite = FENSTER_BREITE_OFFEN if self.sidebar_offen else FENSTER_BREITE_ZU
        x = int((screen_width - fenster_breite) / 2)
        y = 38

        self.geometry(f"{fenster_breite}x{FENSTER_HOEHE}+{x}+{y}")
        self.deiconify()

        if system_ui:
            system_ui.fenster_nach_vorne()
        self.lift()
        self.focus_force()
        self.suchfeld.focus_set()

        # Offene Dialoge nicht unter dem Hauptfenster begraben. Kurz
        # verzoegert, damit das Heben NACH dem lift() oben greift.
        self.after(60, self.nebenfenster_heben)

    def toggle_fenster(self):
        if self.winfo_viewable():
            self.withdraw()
        else:
            self.zeige_unter_notch()

    def auf_fokus_verlust(self, event=None):
        # Das Fenster versteckt sich, sobald man woanders hinklickt
        # (Popup-Charakter). Das setzt aber voraus, dass es einen zweiten
        # Weg zurueck gibt - auf dem Mac das Menueleisten-Symbol, den
        # Kurzbefehl und das Dock-Symbol. Solange es fuer ein System noch
        # kein solches Symbol gibt, bleibt das Fenster lieber stehen,
        # statt zu verschwinden und unerreichbar zu sein.
        if not system_ui:
            return
        if self.focus_get() is None:
            self.withdraw()

    def toggle_sidebar(self):
        if self.sidebar_offen:
            self.sidebar_frame.grid_forget()
            self.sidebar_offen = False
            neue_breite = FENSTER_BREITE_ZU
        else:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            self.sidebar_offen = True
            neue_breite = FENSTER_BREITE_OFFEN

        # Fenster wächst/schrumpft mit der Sidebar mit (statt starr bei
        # 780px zu bleiben) und bleibt dabei horizontal unter der Notch
        # zentriert - so behält der Hauptbereich (Suchfeld, Filter,
        # Ergebnisse) immer seine volle, gewohnte Breite.
        screen_width = self.winfo_screenwidth()
        x = int((screen_width - neue_breite) / 2)
        y = self.winfo_y()
        self.geometry(f"{neue_breite}x{FENSTER_HOEHE}+{x}+{y}")

    def beenden(self):
        self.indexierung_abbrechen = True

        # ZUERST verschwinden, dann aufraeumen. Das Aufraeumen unten kann
        # bis zu zwei Sekunden dauern (Ordnerueberwachung anhalten) - genau
        # so lange waere sonst noch ein Dock-Symbol zu sehen, und zwar
        # nicht das eigene: das wird zur Laufzeit gesetzt und faellt beim
        # Beenden weg, worauf macOS das Symbol des ausfuehrenden Programms
        # zeigt (beim Start aus dem Quelltext die Python-Rakete).
        try:
            self.withdraw()
        except Exception:
            pass
        if system_ui and hasattr(system_ui, "aus_dem_dock_nehmen"):
            system_ui.aus_dem_dock_nehmen()
        # Sperrdatei selbst aufraeumen: weiter unten steht os._exit(0), und
        # das geht an atexit vorbei. Bliebe die Datei liegen, koennte ein
        # spaeterer Start sie faelschlich fuer eine laufende Instanz halten
        # und sich wortlos beenden.
        for datei in (SPERRDATEI, ZEIGEN_SIGNAL):
            try:
                if os.path.exists(datei):
                    os.remove(datei)
            except Exception:
                pass
        with self.observer_lock:
            if self.observer:
                try:
                    self.observer.stop()
                    self.observer.join(timeout=2)
                except Exception:
                    pass
        self.destroy()
        os._exit(0)

    # ---------- WATCHDOG & AUTOSTART ----------

    def starte_ordner_überwachung(self):
        if not WATCHDOG_VERFUEGBAR:
            return

        with self.observer_lock:
            if self.observer:
                try:
                    self.observer.stop()
                    self.observer.join(timeout=2)
                except Exception:
                    pass
                self.observer = None

            config = smart_search.lade_config()
            ordner_liste = config.get("ordner", [])

            if not ordner_liste:
                return

            handler = OrdnerAenderungsHandler(callback_funktion=self.automatische_reindexierung)
            observer = Observer()

            überwachte_ordner = 0
            for o in ordner_liste:
                if os.path.exists(o):
                    observer.schedule(handler, path=o, recursive=True)
                    überwachte_ordner += 1

            if überwachte_ordner > 0:
                observer.start()
                self.observer = observer

    def automatische_reindexierung(self):
        # WICHTIG: Dieser Callback wird vom Watchdog-Observer-Thread aufgerufen,
        # NICHT vom Main-Thread. CustomTkinter/Tkinter-Widgets dürfen nur vom
        # Main-Thread aus angefasst werden - deshalb läuft hier alles über
        # self.after(0, ...), inklusive des Indexierungs-Starts selbst.
        self.after(0, self._automatische_reindexierung_main_thread)

    def _automatische_reindexierung_main_thread(self):
        if self.indexierung_laeuft or self.indexierung_lock.locked():
            # Läuft schon (z.B. durch manuellen Klick) - nicht erneut anstoßen.
            return
        self.setze_status(t("status.autoreindex_started"))
        self.index_aktualisieren()

    def ist_autostart_aktiv(self):
        """Startet SmartSearch automatisch mit der Anmeldung? Wie das
        eingetragen ist, unterscheidet sich je nach System (LaunchAgent
        auf dem Mac, Registry-Eintrag unter Windows) - siehe
        plattform.py."""
        return plattform.autostart_aktiv()

    def autostart_umschalten(self):
        einschalten = self.autostart_var.get()
        ok, fehler = plattform.autostart_setzen(einschalten)
        if not ok:
            self.setze_status(t("status.autostart_error", fehler=fehler))
            # Schalter zuruecksetzen, damit die Anzeige nicht etwas
            # behauptet, was gar nicht eingerichtet wurde.
            self.autostart_var.set(not einschalten)
        elif einschalten:
            self.setze_status(t("status.autostart_enabled"))
        else:
            self.setze_status(t("status.autostart_disabled"))

    # ---------- TASTATUR-NAVIGATION ----------

    def fokus_nach_unten(self, event=None):
        if self.card_widgets and self.fokussierter_index < len(self.card_widgets) - 1:
            self.fokussierter_index += 1
            self._aktualisiere_karten_hervorhebung()
            return "break"

    def fokus_nach_oben(self, event=None):
        if self.card_widgets and self.fokussierter_index > 0:
            self.fokussierter_index -= 1
            self._aktualisiere_karten_hervorhebung()
            return "break"

    def _aktualisiere_karten_hervorhebung(self):
        for idx, (card, _) in enumerate(self.card_widgets):
            if idx == self.fokussierter_index:
                card.configure(border_width=2, border_color=farben.AKZENT)
            else:
                card.configure(border_width=0)
        self._scrolle_zu_fokussierter_karte()

    def _scrolle_zu_fokussierter_karte(self):
        """Scrollt die Ergebnisliste automatisch mit, wenn die per
        Pfeiltasten fokussierte Karte aus dem sichtbaren Bereich
        herauswandert - vorher bewegte sich nur der blaue Rahmen, ohne
        dass die Liste selbst mitscrollte."""
        if not (0 <= self.fokussierter_index < len(self.card_widgets)):
            return
        try:
            card, _ = self.card_widgets[self.fokussierter_index]
            canvas = self.cards_scrollframe._parent_canvas
            self.cards_scrollframe.update_idletasks()

            bbox = canvas.bbox("all")
            if not bbox:
                return
            gesamt_hoehe = bbox[3] - bbox[1]
            if gesamt_hoehe <= 0:
                return

            karte_oben = card.winfo_y() / gesamt_hoehe
            karte_unten = (card.winfo_y() + card.winfo_height()) / gesamt_hoehe
            sichtbar_oben, sichtbar_unten = canvas.yview()

            if karte_oben < sichtbar_oben:
                # Karte ragt oben aus dem sichtbaren Bereich - Liste nach oben scrollen
                canvas.yview_moveto(karte_oben)
            elif karte_unten > sichtbar_unten:
                # Karte ragt unten heraus - so weit nach unten scrollen,
                # dass die Kartenunterkante gerade noch sichtbar ist
                sichtbarer_anteil = sichtbar_unten - sichtbar_oben
                canvas.yview_moveto(max(0, karte_unten - sichtbarer_anteil))
        except Exception:
            # Scrollen ist ein reines Komfort-Feature - falls es aus
            # irgendeinem Grund fehlschlägt, soll das die Pfeiltasten-
            # Navigation selbst nicht beeinträchtigen.
            pass

    def quicklook_fokussiert(self, event=None):
        if 0 <= self.fokussierter_index < len(self.card_widgets):
            _, pfad = self.card_widgets[self.fokussierter_index]
            self.quicklook_im_vordergrund(pfad)
            return "break"

    def aehnliche_suchen(self, pfad):
        """Findet inhaltlich ähnliche Dokumente über den bereits
        vorhandenen KI-Vektor der Datei (statt vorher: neue Textsuche nur
        nach dem Dateinamen ohne Endung, was inhaltliche Ähnlichkeit gar
        nicht erkennen konnte)."""
        self.suchfeld.delete(0, "end")
        self.suchfeld.insert(0, t("similar.query_prefix", name=os.path.basename(pfad)))
        self._suche_button_sperren()
        self.setze_status(t("similar.status_searching"))
        threading.Thread(target=self._aehnliche_bg, args=(pfad,), daemon=True).start()

    def _aehnliche_bg(self, pfad):
        try:
            treffer = smart_search.aehnliche_dateien(pfad, top_n=15)
            self.after(0, self._zeige_aehnliche_treffer, treffer)
        except Exception as e:
            # e=e als Default-Argument "einfrieren": Python löscht die
            # except-Variable automatisch am Blockende, die Lambda würde
            # sie aber erst später (über self.after) auswerten und dann
            # auf ein bereits verschwundenes 'e' treffen -> NameError.
            self.after(0, lambda e=e: self._suche_fehlgeschlagen(e))

    def _zeige_aehnliche_treffer(self, treffer):
        self._suche_button_entsperren()
        if treffer is None:
            self.setze_status(t("similar.status_no_vector"))
            self.aktuelle_treffer = []
            self.aktuelle_such_woerter = []
            self.zeige_aktuelle_ergebnisse()
            return
        self.aktuelle_treffer = treffer
        # Bei "Ähnliche Dokumente" gibt es keine eingetippten Suchwörter -
        # also auch nichts, was im Textausschnitt einzufärben wäre.
        self.aktuelle_such_woerter = []
        self.zeige_aktuelle_ergebnisse()

    # ---------- DATEIEN ÖFFNEN OHNE DASS SIE HINTER SMARTSEARCH VERSCHWINDEN ----------

    def _datei_im_vordergrund_oeffnen(self, oeffnen_fn, pfad):
        """Öffnet eine Datei (per beliebiger oeffnen_fn) und stellt sicher,
        dass sie sichtbar im Vordergrund landet.

        SmartSearch läuft dauerhaft mit -topmost True, damit es unter der
        Notch sichtbar bleibt. Das hat aber den Nebeneffekt, dass jede neu
        geöffnete App/Vorschau HINTER dem SmartSearch-Fenster landet, weil
        SmartSearch sich immer über alles andere legt. Deshalb: -topmost
        deaktivieren, Datei öffnen - und NICHT nach einer festen Wartezeit
        automatisch wieder aktivieren (das sprang SmartSearch nach 800ms
        wieder vor die gerade geöffnete App/den Dialog, egal ob die
        Zeitspanne gereicht hatte oder nicht). Stattdessen wird -topmost
        erst wieder aktiviert, wenn SmartSearch selbst den Fokus zurück-
        bekommt - siehe die <FocusIn>-Bindung in __init__.
        """
        self.attributes("-topmost", False)
        oeffnen_fn(pfad)

    def datei_oeffnen_im_vordergrund(self, pfad):
        self._datei_im_vordergrund_oeffnen(smart_search.datei_oeffnen, pfad)

    def quicklook_im_vordergrund(self, pfad):
        self._datei_im_vordergrund_oeffnen(plattform.vorschau, pfad)

    def im_finder_zeigen_im_vordergrund(self, pfad):
        self._datei_im_vordergrund_oeffnen(plattform.im_dateimanager_zeigen, pfad)



    def _buttons_sperren(self):
        for btn in self._index_sperrbare_buttons:
            btn.configure(state="disabled")

    def _buttons_entsperren(self):
        for btn in self._index_sperrbare_buttons:
            btn.configure(state="normal")

    def _suche_button_sperren(self):
        for btn in self._suche_sperrbare_buttons:
            btn.configure(state="disabled")

    def _suche_button_entsperren(self):
        for btn in self._suche_sperrbare_buttons:
            btn.configure(state="normal")

    # ---------- VERLAUF & HELPER ----------

    def lade_verlauf(self):
        if os.path.exists(VERLAUF_DATEI):
            try:
                with open(VERLAUF_DATEI, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def speichere_verlauf(self):
        try:
            with open(VERLAUF_DATEI, "w") as f:
                json.dump(self.verlauf, f, indent=2)
        except Exception:
            pass

    def verlauf_aktualisieren(self, anfrage):
        if not anfrage or anfrage == PLATZHALTER_TEXT:
            return
        if anfrage in self.verlauf:
            self.verlauf.remove(anfrage)
        self.verlauf.insert(0, anfrage)
        self.verlauf = self.verlauf[:MAX_VERLAUF]
        self.speichere_verlauf()

    def setze_status(self, text):
        self.status_bar.configure(text=text)
        self.update_idletasks()

    def _dauer_text(self, sekunden):
        """Formatiert eine Sekundenzahl als kurze, lesbare Restzeit-Angabe
        für die Fortschrittsanzeige bei der Indexierung."""
        sekunden = max(0, sekunden)
        if sekunden < 60:
            return "< 1 Min"
        minuten = int(sekunden // 60)
        if minuten < 60:
            return f"{minuten} Min"
        stunden = minuten // 60
        rest_minuten = minuten % 60
        return f"{stunden} Std {rest_minuten} Min"

    def _kuerze_dateiname(self, name, max_laenge=34):
        """Kürzt lange Dateinamen in der Mitte (statt sie einfach abzu-
        schneiden), damit die Dateiendung sichtbar bleibt - wichtig, seit
        das Fenster kompakter ist und pro Treffer-Karte fünf Aktions-
        Buttons (Favorit, Öffnen, Finder, Vorschau, Ähnliche) neben dem
        Dateinamen Platz brauchen. Ohne Kürzung würden lange Dateinamen die
        Buttons aus der sichtbaren Karte herausdrücken."""
        if len(name) <= max_laenge:
            return name
        stamm, endung = os.path.splitext(name)
        # Genug vom Anfang UND vom Ende (inkl. Endung) zeigen, damit der
        # Dateiname noch wiedererkennbar bleibt.
        rest = max_laenge - len(endung) - 1  # -1 für "…"
        vorne = rest * 2 // 3
        hinten = rest - vorne
        if vorne < 4 or hinten < 4:
            return name[:max_laenge - 1] + "…"
        return f"{stamm[:vorne]}…{stamm[-hinten:]}{endung}"

    def ausgeschlossene_typen(self):
        typen = set()
        for label, var in self.filter_variablen.items():
            if var.get():
                typen |= DATEITYP_GRUPPEN[label]
        return typen

    # ---------- FAVORITEN & ORDNER ----------

    def favoriten_anzeigen(self):
        if not self.favoriten:
            self.setze_status(t("status.no_favorites"))
            self.aktuelle_treffer = []
            self.aktuelle_such_woerter = []
            self.zeige_aktuelle_ergebnisse()
            return

        # Favoriten sind keine Suchtreffer - nichts einzufärben.
        self.aktuelle_such_woerter = []
        eintraege = smart_search.lade_bestehenden_index()
        # Je Datei nur den ersten Abschnitt - sonst erscheint ein Dokument
        # so oft, wie es Abschnitte hat.
        gesehen = set()
        fav_treffer = []
        for e in eintraege:
            pfad_e = e["datei"]
            if pfad_e in self.favoriten and pfad_e not in gesehen:
                gesehen.add(pfad_e)
                fav_treffer.append((1.0, e))
        self.aktuelle_treffer = fav_treffer
        self.zeige_aktuelle_ergebnisse()

    def _rollen_weiterreichen(self, ereignis):
        """Gibt ein Mausrad-Ereignis an die Trefferliste weiter, statt es im
        Textfeld zu verarbeiten. Ohne das rollt der Ausschnitt in sich
        selbst und die Liste bleibt stehen - oder springt."""
        try:
            ziel = self.cards_scrollframe._parent_canvas
            if ereignis.num == 4:
                ziel.yview_scroll(-2, "units")
            elif ereignis.num == 5:
                ziel.yview_scroll(2, "units")
            else:
                ziel.yview_scroll(int(-1 * (ereignis.delta / 2)), "units")
        except Exception:
            pass
        return "break"

    def _favorit_umschalten(self, pfad):
        ist_favorit = smart_search.favorit_umschalten(pfad)
        if ist_favorit:
            self.favoriten.add(pfad)
        else:
            self.favoriten.discard(pfad)
        self.zeige_aktuelle_ergebnisse()

    def ordner_hinzufuegen_gui(self):
        self.attributes("-topmost", False)
        ordner = filedialog.askdirectory(title=t("folders.picker_title"), parent=self)
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        if ordner:
            smart_search.befehl_ordner_hinzufuegen(ordner)
            self.setze_status(t("folders.status_added", ordner=ordner))
            self.starte_ordner_überwachung()
            self.index_aktualisieren()

    # ---------- EXPORT / IMPORT DER EINSTELLUNGEN ----------

    # ---------- ONBOARDING (erster Start) ----------

    def _fuelle_hilfe_tab(self, parent):
        """Hilfe-Tab im Preferences-Fenster: laesst die Einfuehrung erneut
        oeffnen und beantwortet die eine Frage, die erfahrungsgemaess am
        haeufigsten kommt ("warum finde ich nichts?"). Bewusst KEIN
        vollstaendiges Handbuch - die App soll sich selbst erklaeren, das
        hier ist nur das Sicherheitsnetz."""
        ctk.CTkLabel(
            parent, text=t("help.guide_heading"), font=("Helvetica", 13, "bold")
        ).pack(padx=4, pady=(16, 2), anchor="w")

        ctk.CTkLabel(
            parent, text=t("help.guide_text"), font=("Helvetica", 11),
            text_color="#78909c", justify="left", wraplength=400
        ).pack(padx=4, pady=(0, 8), anchor="w")

        ctk.CTkButton(
            parent, text=t("help.guide_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            anchor="w", command=self._guide_aus_einstellungen_oeffnen
        ).pack(padx=4, pady=(0, 18), fill="x")

        ctk.CTkLabel(
            parent, text=t("help.trouble_heading"), font=("Helvetica", 13, "bold")
        ).pack(padx=4, pady=(0, 2), anchor="w")

        ctk.CTkLabel(
            parent, text=t("help.trouble_text"), font=("Helvetica", 11),
            text_color="#78909c", justify="left", wraplength=400
        ).pack(padx=4, pady=(0, 18), anchor="w")

        # Rueckmeldung: der einzige Draht zu den Nutzern, da bewusst keine
        # Nutzungsdaten erhoben werden. Oeffnet eine vorbereitete E-Mail -
        # mit Versions- und Systemangaben, aber ohne Dateinamen.
        ctk.CTkLabel(
            parent, text=t("help.feedback_heading"), font=("Helvetica", 13, "bold")
        ).pack(padx=4, pady=(0, 2), anchor="w")
        ctk.CTkLabel(
            parent, text=t("help.feedback_text"), font=("Helvetica", 11),
            text_color="#78909c", justify="left", wraplength=400
        ).pack(padx=4, pady=(0, 8), anchor="w")
        ctk.CTkButton(
            parent, text=t("help.feedback_button"), fg_color=farben.SEITE_KNOPF,
            hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=self.oeffne_rueckmeldung
        ).pack(padx=4, pady=(0, 18), fill="x")

        # Texterkennung sichtbar machen: frueher schlug OCR auf fremden Macs
        # still fehl (Tesseract/poppler waren nur auf dem Entwicklungsrechner
        # installiert). Jetzt steht hier schwarz auf weiss, ob sie laeuft.
        ctk.CTkLabel(
            parent, text=t("help.ocr_heading"), font=("Helvetica", 13, "bold")
        ).pack(padx=4, pady=(0, 2), anchor="w")

        engine = ocr.verfuegbare_engine()
        engine_namen = {"vision": "Apple Vision", "tesseract": "Tesseract"}
        if engine:
            ocr_text = t("help.ocr_available", engine=engine_namen.get(engine, engine))
            ocr_farbe = "#2e7d32"
        else:
            ocr_text = t("help.ocr_missing")
            ocr_farbe = "#ef6c00"

        ctk.CTkLabel(
            parent, text=ocr_text, font=("Helvetica", 11),
            text_color=ocr_farbe, justify="left", wraplength=400
        ).pack(padx=4, pady=(0, 12), anchor="w")

    def _guide_aus_einstellungen_oeffnen(self):
        """Schliesst das Preferences-Fenster, bevor der Guide aufgeht -
        sonst liegen zwei topmost-Fenster uebereinander und der Guide
        (der grab_set() nutzt) wirkt eingefroren."""
        if self.einstellungen_fenster is not None:
            try:
                self.einstellungen_fenster.destroy()
            except Exception:
                pass
            self.einstellungen_fenster = None
        self.after(120, lambda: self.zeige_setup_guide(mit_ordnerauswahl=False))

    # ---------- Bitte um Rueckmeldung ----------
    # Schwellen bewusst hoch und die Bitte hoechstens zweimal: wer einmal
    # "Nicht jetzt" sagt, meint meistens "nie" - ein zweites Nachfassen nach
    # weiteren 25 Suchen ist die Grenze des Zumutbaren.
    RM_AB_SUCHEN = 8
    RM_ABSTAND = 25
    RM_MAX = 2

    def _rueckmeldung_stand(self):
        config = smart_search.lade_config()
        stand = config.get("rueckmeldung") or {}
        stand.setdefault("suchen", 0)
        stand.setdefault("gezeigt", 0)
        stand.setdefault("erledigt", False)
        stand.setdefault("ab", self.RM_AB_SUCHEN)
        return config, stand

    def _rueckmeldung_merken(self, config, stand):
        config["rueckmeldung"] = stand
        try:
            smart_search.speichere_config(config)
        except Exception:
            pass  # Eine nicht schreibbare Konfiguration darf keine Suche stoeren.

    def _rueckmeldung_zaehlen(self):
        """Wird nach jeder erfolgreichen Suche aufgerufen."""
        config, stand = self._rueckmeldung_stand()
        stand["suchen"] += 1
        if (not stand["erledigt"] and not self._rueckmeldung_sichtbar
                and stand["gezeigt"] < self.RM_MAX
                and stand["suchen"] >= stand["ab"]):
            stand["gezeigt"] += 1
            self._rueckmeldung_sichtbar = True
            self.rueckmeldung_leiste.grid(row=3, column=0, sticky="ew",
                                          padx=2, pady=(8, 0))
        self._rueckmeldung_merken(config, stand)

    def _rueckmeldung_verbergen(self):
        self._rueckmeldung_sichtbar = False
        try:
            self.rueckmeldung_leiste.grid_forget()
        except Exception:
            pass

    def _rueckmeldung_schreiben(self):
        self._rueckmeldung_verbergen()
        self.oeffne_rueckmeldung()

    def _rueckmeldung_spaeter(self):
        config, stand = self._rueckmeldung_stand()
        stand["ab"] = stand["suchen"] + self.RM_ABSTAND
        self._rueckmeldung_merken(config, stand)
        self._rueckmeldung_verbergen()

    def oeffne_rueckmeldung(self, vorbelegung=""):
        """Oeffnet eine vorbereitete E-Mail im Standard-Mailprogramm.

        Bewusst dieser Weg statt eines eingebauten Formulars: es braucht
        keinen Server, der Nutzer sieht vor dem Absenden genau, was
        uebermittelt wird, und kann es aendern. Enthalten sind nur
        Programm- und Systemangaben - keine Dateinamen, keine Inhalte.

        vorbelegung: Fehlermeldung, die aus einem Fehlerdialog heraus
        mitgeschickt wird. Sonst muesste der Nutzer sie abtippen.
        """
        import platform
        import urllib.parse
        import webbrowser

        engine = ocr.verfuegbare_engine() or "keine"
        rumpf = (
            "\n\n\n"
            "--- Bitte diese Zeilen stehen lassen ---\n"
            + (f"Meldung: {vorbelegung}\n" if vorbelegung else "")
            + f"SmartSearch {APP_VERSION}\n"
            + f"macOS {platform.mac_ver()[0]} ({platform.machine()})\n"
            + f"Python {platform.python_version()}\n"
            + f"Texterkennung: {engine}\n"
            + f"Sprache: {i18n.aktuelle_sprache()}\n"
        )
        config, stand = self._rueckmeldung_stand()
        stand["erledigt"] = True
        self._rueckmeldung_merken(config, stand)

        adresse = RUECKMELDUNG_ADRESSE
        link = (f"mailto:{adresse}"
                f"?subject={urllib.parse.quote('SmartSearch ' + APP_VERSION + ' - Rueckmeldung')}"
                f"&body={urllib.parse.quote(rumpf)}")
        try:
            webbrowser.open(link)
        except Exception:
            self.setze_status(t("help.feedback_failed", adresse=adresse))

    def _fuelle_datenschutz_inhalt(self, parent):
        """Baut den Datenschutz-Text (persönliche, direkte Sprache statt
        trockener Stichpunktliste mit Fachbegriffen) in ein beliebiges
        Eltern-Widget - wird vom Preferences-Fenster als eigener Tab
        genutzt (siehe oeffne_einstellungen_fenster()). Soll ehrliches
        Vertrauen schaffen, gerade weil hier potenziell sensible Dokumente
        (Ausweise, Rechnungen, Verträge) indexiert werden."""
        ctk.CTkLabel(parent, text=t("privacy.heading"), font=("Helvetica", 16, "bold")).pack(
            padx=4, pady=(10, 4), anchor="w"
        )
        ctk.CTkLabel(
            parent,
            text=t("privacy.intro"),
            font=("Helvetica", 11), text_color="#78909c", justify="left", wraplength=420
        ).pack(padx=4, pady=(0, 16), anchor="w")

        abschnitte = [
            (t("privacy.section1_title"), t("privacy.section1_text")),
            (t("privacy.section2_title"), t("privacy.section2_text")),
            (t("privacy.section3_title"), t("privacy.section3_text")),
            (t("privacy.section4_title"), t("privacy.section4_text")),
        ]

        for titel, text in abschnitte:
            block = ctk.CTkFrame(parent, fg_color="transparent")
            block.pack(fill="x", padx=4, pady=7, anchor="w")
            ctk.CTkLabel(
                block, text=titel, font=("Helvetica", 12, "bold"), anchor="w", justify="left", wraplength=420
            ).pack(fill="x", anchor="w")
            ctk.CTkLabel(
                block, text=text, font=("Helvetica", 10), text_color="#78909c",
                anchor="w", justify="left", wraplength=420
            ).pack(fill="x", anchor="w", pady=(1, 0))

        ctk.CTkLabel(
            parent,
            text=t("privacy.closing"),
            font=("Helvetica", 10, "italic"), text_color="#78909c", justify="left", wraplength=420
        ).pack(padx=4, pady=(4, 10), anchor="w")

    def oeffne_einstellungen_fenster(self):
        """Separates Preferences-Fenster - sammelt die selten gebrauchten
        Einstellungen in Reitern. Erscheinungsbild, Ordner verwalten und
        die Fehleranzeige bleiben bewusst NUR im Schnellzugriff (keine
        doppelten Buttons an zwei Stellen). Wird beim erneuten Aufruf nur
        nach vorne geholt statt dupliziert, wie man es von echten
        macOS-Apps kennt (Cmd+,)."""
        if self.einstellungen_fenster is not None and self.einstellungen_fenster.winfo_exists():
            self.einstellungen_fenster.deiconify()
            self.einstellungen_fenster.lift()
            self.einstellungen_fenster.focus_force()
            return

        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("settings.window_title"))
        top.geometry("480x420")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        self.einstellungen_fenster = top

        tabview = ctk.CTkTabview(top)
        tabview.pack(fill="both", expand=True, padx=16, pady=16)

        tab_allgemein = tabview.add(t("settings.tab_general"))
        tab_hilfe = tabview.add(t("settings.tab_help"))
        tab_backup = tabview.add(t("settings.tab_backup"))
        tab_datenschutz = tabview.add(t("settings.tab_privacy"))

        # ---- Allgemein: Autostart + Sprache + Version/Update
        # (Erscheinungsbild sitzt im Schnellzugriff, siehe __init__) ----
        # autostart_var immer auf den tatsächlichen Zustand auf der
        # Festplatte zurücksetzen, falls sich das LaunchAgent-Plist seit
        # dem letzten Öffnen extern geändert hat.
        self.autostart_var.set(self.ist_autostart_aktiv())
        ctk.CTkCheckBox(
            tab_allgemein, text=t("settings.autostart_checkbox"), variable=self.autostart_var,
            command=self.autostart_umschalten
        ).pack(padx=4, pady=(16, 4), anchor="w")

        # Sprachumschalter: Sprachnamen bewusst NICHT übersetzt ("Deutsch"/
        # "English" bleiben immer in sich selbst benannt) - so findet man
        # seine Sprache auch, wenn die Oberfläche gerade in der jeweils
        # ANDEREN Sprache angezeigt wird. Wirkt SOFORT (siehe
        # wende_sprache_live_an() weiter oben) - kein Neustart mehr nötig.
        ctk.CTkLabel(
            tab_allgemein, text=t("settings.language_label"), font=("Helvetica", 10), text_color="#78909c"
        ).pack(padx=4, pady=(16, 2), anchor="w")

        sprache_werte = {"Deutsch": "de", "English": "en"}
        sprache_umkehr = {v: k for k, v in sprache_werte.items()}

        def sprache_gewaehlt(anzeige):
            code = sprache_werte.get(anzeige)
            if code:
                self.wende_sprache_live_an(code)

        sprache_seg = ctk.CTkSegmentedButton(
            tab_allgemein, values=list(sprache_werte.keys()), command=sprache_gewaehlt, font=("Helvetica", 10)
        )
        sprache_seg.set(sprache_umkehr.get(i18n.aktuelle_sprache(), "Deutsch"))
        sprache_seg.pack(padx=4, pady=(0, 12), fill="x")

        ctk.CTkLabel(
            tab_allgemein, text=t("settings.version_label", version=APP_VERSION), font=("Helvetica", 11), text_color="#78909c"
        ).pack(padx=4, pady=(20, 4), anchor="w")
        ctk.CTkButton(
            tab_allgemein, text=t("settings.check_updates_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            anchor="w", command=lambda: self.pruefe_auf_updates(manuell=True)
        ).pack(padx=4, pady=4, fill="x")

        # ---- Hilfe ----
        self._fuelle_hilfe_tab(tab_hilfe)

        # ---- Backup: Export / Import ----
        ctk.CTkLabel(
            tab_backup,
            text=t("backup.description"),
            font=("Helvetica", 11), text_color="#78909c", justify="left"
        ).pack(padx=4, pady=(12, 12), anchor="w")
        ctk.CTkButton(
            tab_backup, text=t("backup.export_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            anchor="w", command=self.einstellungen_exportieren
        ).pack(padx=4, pady=4, fill="x")
        ctk.CTkButton(
            tab_backup, text=t("backup.import_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            anchor="w", command=self.einstellungen_importieren
        ).pack(padx=4, pady=4, fill="x")

        # ---- Datenschutz ----
        datenschutz_scroll = ctk.CTkScrollableFrame(tab_datenschutz, fg_color="transparent")
        datenschutz_scroll.pack(fill="both", expand=True)
        self._fuelle_datenschutz_inhalt(datenschutz_scroll)

    def zeige_setup_guide(self, mit_ordnerauswahl=True):
        """Mehrstufige Einfuehrung.

        Beim ersten Start (mit_ordnerauswahl=True) fuehrt sie durch fuenf
        Schritte: Suchprinzip, Funktionsumfang, Datenschutz, Ordnerauswahl,
        Bedienung. Erneut geoeffnet aus Einstellungen > Hilfe entfaellt der
        Ordnerschritt, damit ein Nachschlagen nicht versehentlich Ordner
        doppelt eintraegt oder eine vollstaendige Neuindexierung ausloest.

        Zur Gestaltung: bewusst ruhig gehalten - eine Ueberschrift, eine
        Haarlinie, Flaechentext. Keine farbigen Kaesten, keine Symbole in
        Beschriftungen, ein einziger hervorgehobener Knopf pro Seite. Der
        Aufbau lehnt sich an die Systemassistenten von macOS an, damit die
        Einfuehrung wie ein Teil des Betriebssystems wirkt und nicht wie
        eine Werbeseite.

        Technisch: EIN Toplevel, dessen Inhaltsbereich pro Schritt geleert
        und neu gezeichnet wird. Die BooleanVars der Ordner-Auswahl liegen
        ausserhalb der Zeichenfunktion, damit die Auswahl beim Blaettern
        erhalten bleibt.
        """
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("guide.title"))
        top.geometry("660x640")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)
        top.grab_set()

        schritte = ["prinzip", "funktionen", "datenschutz"]
        if mit_ordnerauswahl:
            schritte.append("ordner")
        schritte.append("bedienung")

        zustand = {"index": 0}

        standard_ordner = [
            (t("onboarding.documents"), os.path.expanduser("~/Documents")),
            (t("onboarding.downloads"), os.path.expanduser("~/Downloads")),
            (t("onboarding.desktop"), os.path.expanduser("~/Desktop")),
        ]
        checkbox_vars = {}
        for label, pfad in standard_ordner:
            if not os.path.isdir(pfad):
                continue
            # Downloads ist bei vielen Nutzern sehr umfangreich und enthaelt
            # ueberwiegend Belangloses - voreingestellt daher abgewaehlt,
            # sonst dauert die erste Indexierung unnoetig lang.
            checkbox_vars[pfad] = ctk.BooleanVar(value=(label != t("onboarding.downloads")))
        eigene_ordner = []

        GRAU = "#8a949b"
        LINIE = ("#d8dcdf", "#3a3f43")

        # ---------- Geruest ----------
        kopf = ctk.CTkFrame(top, fg_color="transparent")
        kopf.pack(fill="x", padx=38, pady=(26, 0))

        titel_label = ctk.CTkLabel(kopf, text="", font=("Helvetica", 19, "bold"), anchor="w")
        titel_label.pack(side="left")

        schritt_label = ctk.CTkLabel(kopf, text="", font=("Helvetica", 11), text_color=GRAU)
        schritt_label.pack(side="right", pady=(6, 0))

        trennlinie = ctk.CTkFrame(top, height=1, fg_color=LINIE)
        trennlinie.pack(fill="x", padx=38, pady=(10, 0))

        # REIHENFOLGE IST WICHTIG: Die Fussleiste muss VOR dem
        # expandierenden Inhaltsbereich gepackt werden. Tk verteilt den
        # Platz in der Reihenfolge der pack()-Aufrufe - stand der Inhalt
        # mit expand=True zuerst, nahm er sich die gesamte Hoehe und
        # schob die Knopfleiste aus dem Fenster. Dann liess sich der
        # Assistent nicht mehr weiterblaettern.
        fuss = ctk.CTkFrame(top, fg_color="transparent")
        fuss.pack(side="bottom", fill="x", padx=38, pady=(12, 24))

        inhalt = ctk.CTkFrame(top, fg_color="transparent")
        inhalt.pack(fill="both", expand=True, padx=38, pady=(16, 0))

        btn_zurueck = ctk.CTkButton(
            fuss, text=t("guide.back"), width=92, height=30,
            fg_color="transparent", hover_color=("#e6e9eb", "#3a3f43"),
            text_color=("#3b464d", "#c8cfd4"), font=("Helvetica", 12),
            command=lambda: blaettern(-1)
        )
        btn_zurueck.pack(side="left")

        btn_skip = ctk.CTkButton(
            fuss, text=t("guide.skip"), width=110, height=30,
            fg_color="transparent", hover_color=("#e6e9eb", "#3a3f43"),
            text_color=GRAU, font=("Helvetica", 12),
            command=lambda: abschliessen(uebersprungen=True)
        )
        btn_skip.pack(side="left", padx=(4, 0))

        btn_weiter = ctk.CTkButton(
            fuss, text=t("guide.next"), width=124, height=32,
            fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, font=("Helvetica", 12, "bold"),
            command=lambda: blaettern(1)
        )
        btn_weiter.pack(side="right")

        # ---------- Bausteine ----------
        def fliesstext(text, groesse=12.5, pady=(0, 16), farbe=GRAU, eltern=None):
            ctk.CTkLabel(
                eltern or inhalt, text=text, font=("Helvetica", int(groesse)),
                text_color=farbe, justify="left", anchor="w", wraplength=560
            ).pack(pady=pady, anchor="w", fill="x")

        def zwischentitel(text, pady=(0, 6), eltern=None):
            ctk.CTkLabel(
                eltern or inhalt, text=text, font=("Helvetica", 12, "bold"),
                anchor="w", height=18
            ).pack(pady=pady, anchor="w")

        def aufzaehlung(text, eltern=None, breite=560, groesse=12):
            """Eine Zeile je Eintrag, eingerueckt statt mit Aufzaehlungs-
            zeichen - ruhiger im Schriftbild als eine Punkteliste.

            height wird ausdruecklich gesetzt: CTkLabel ist von Haus aus 28
            Pixel hoch, was bei einzeiligen Eintraegen einen unangenehm
            weiten Zeilenfall ergibt."""
            for zeile in text.split("\n"):
                if not zeile.strip():
                    continue
                ctk.CTkLabel(
                    eltern or inhalt, text=zeile, font=("Helvetica", groesse),
                    text_color=GRAU, justify="left", anchor="w", wraplength=breite,
                    height=17
                ).pack(pady=0, anchor="w", padx=(2, 0))

        # ---------- Schritt 1: Suchprinzip ----------
        def zeichne_prinzip():
            fliesstext(t("guide.s1_text"))
            zwischentitel(t("guide.s1_examples_title"), pady=(6, 10))

            tabelle = ctk.CTkFrame(inhalt, fg_color="transparent")
            tabelle.pack(fill="x", pady=(0, 4))
            tabelle.grid_columnconfigure(0, minsize=250)

            beispiele = [
                (t("guide.s1_ex1_query"), t("guide.s1_ex1_hit")),
                (t("guide.s1_ex2_query"), t("guide.s1_ex2_hit")),
                (t("guide.s1_ex3_query"), t("guide.s1_ex3_hit")),
            ]
            for i, (anfrage, treffer) in enumerate(beispiele):
                ctk.CTkLabel(
                    tabelle, text="»" + anfrage + "«", font=("Helvetica", 12),
                    anchor="w"
                ).grid(row=i, column=0, sticky="w", pady=4)
                ctk.CTkLabel(
                    tabelle, text=treffer, font=("Menlo", 11), text_color=GRAU, anchor="w"
                ).grid(row=i, column=1, sticky="w", pady=4)

            fliesstext(t("guide.s1_footer"), groesse=11.5, pady=(22, 0))

        # ---------- Schritt 2: Funktionsumfang ----------
        def zeichne_funktionen():
            fliesstext(t("guide.s2_text"), pady=(0, 14))

            spalten = ctk.CTkFrame(inhalt, fg_color="transparent")
            spalten.pack(fill="both", expand=True)
            spalten.grid_columnconfigure(0, weight=1, uniform="s")
            spalten.grid_columnconfigure(1, weight=1, uniform="s")

            links = ctk.CTkFrame(spalten, fg_color="transparent")
            links.grid(row=0, column=0, sticky="nw", padx=(0, 18))
            rechts = ctk.CTkFrame(spalten, fg_color="transparent")
            rechts.grid(row=0, column=1, sticky="nw")

            gruppen_links = [("guide.s2_g1_title", "guide.s2_g1_items"),
                             ("guide.s2_g2_title", "guide.s2_g2_items")]
            gruppen_rechts = [("guide.s2_g3_title", "guide.s2_g3_items"),
                              ("guide.s2_g4_title", "guide.s2_g4_items"),
                              ("guide.s2_g5_title", "guide.s2_g5_items")]

            for spalte, gruppen in ((links, gruppen_links), (rechts, gruppen_rechts)):
                for i, (titel_key, items_key) in enumerate(gruppen):
                    zwischentitel(t(titel_key), pady=((0 if i == 0 else 14), 5), eltern=spalte)
                    aufzaehlung(t(items_key), eltern=spalte, breite=270, groesse=11)

        # ---------- Schritt 3: Datenschutz ----------
        def zeichne_datenschutz():
            fliesstext(t("guide.s3_text"), pady=(0, 12))
            aufzaehlung(
                t("guide.s3_point1") + "\n" + t("guide.s3_point2") + "\n" + t("guide.s3_point3")
            )
            ctk.CTkFrame(inhalt, height=1, fg_color=LINIE).pack(fill="x", pady=(22, 16))
            zwischentitel(t("guide.s3_download_title"), pady=(0, 6))
            fliesstext(t("guide.s3_download_text"), groesse=11.5, pady=(0, 0))

        # ---------- Schritt 4: Ordner ----------
        def zeichne_ordner():
            fliesstext(t("guide.s4_text"), pady=(0, 18))

            for label, pfad in standard_ordner:
                if pfad not in checkbox_vars:
                    continue
                zeile = ctk.CTkFrame(inhalt, fg_color="transparent")
                zeile.pack(fill="x", pady=5, anchor="w")
                ctk.CTkCheckBox(
                    zeile, text=label, variable=checkbox_vars[pfad],
                    font=("Helvetica", 12.5), checkbox_width=18, checkbox_height=18,
                    fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, width=150
                ).pack(side="left")
                ctk.CTkLabel(
                    zeile, text=pfad, font=("Helvetica", 11), text_color=GRAU
                ).pack(side="left", padx=(10, 0))

            lbl_eigene = ctk.CTkLabel(
                inhalt, text="", font=("Helvetica", 11), text_color=GRAU, justify="left", anchor="w"
            )
            if eigene_ordner:
                lbl_eigene.configure(text=t("onboarding.extra_prefix") + "\n".join(eigene_ordner))
                lbl_eigene.pack(pady=(14, 0), anchor="w")

            def eigenen_ordner_hinzufuegen():
                # Beide Fenster kurz aus dem Vordergrund nehmen, sonst
                # erscheint der Systemdialog dahinter und die Anwendung
                # wirkt blockiert.
                self.attributes("-topmost", False)
                top.attributes("-topmost", False)
                gewaehlt = filedialog.askdirectory(title=t("onboarding.picker_title"), parent=top)
                top.attributes("-topmost", True)
                top.lift()
                top.focus_force()
                if gewaehlt and gewaehlt not in eigene_ordner:
                    eigene_ordner.append(gewaehlt)
                    lbl_eigene.configure(text=t("onboarding.extra_prefix") + "\n".join(eigene_ordner))
                    lbl_eigene.pack(pady=(14, 0), anchor="w")

            ctk.CTkButton(
                inhalt, text=t("onboarding.add_folder_button"), height=30, width=210,
                fg_color="transparent", border_width=1, border_color=LINIE,
                text_color=("#3b464d", "#c8cfd4"), hover_color=("#e6e9eb", "#3a3f43"),
                font=("Helvetica", 12), command=eigenen_ordner_hinzufuegen
            ).pack(pady=(20, 0), anchor="w")

        # ---------- Schritt 5: Bedienung ----------
        def zeichne_bedienung():
            fliesstext(t("guide.s5_text"), pady=(0, 18))
            zwischentitel(t("guide.s5_tips_title"), pady=(0, 10))
            for key in ("guide.s5_tip1", "guide.s5_tip2", "guide.s5_tip3"):
                ctk.CTkLabel(
                    inhalt, text=t(key), font=("Helvetica", 12), text_color=GRAU,
                    justify="left", anchor="w", wraplength=560
                ).pack(pady=(0, 8), anchor="w", fill="x")
            ctk.CTkFrame(inhalt, height=1, fg_color=LINIE).pack(fill="x", pady=(24, 14))
            fliesstext(t("guide.s5_footer"), groesse=11.5, pady=(0, 0))

        zeichner = {
            "prinzip": (zeichne_prinzip, "guide.s1_heading"),
            "funktionen": (zeichne_funktionen, "guide.s2_heading"),
            "datenschutz": (zeichne_datenschutz, "guide.s3_heading"),
            "ordner": (zeichne_ordner, "guide.s4_heading"),
            "bedienung": (zeichne_bedienung, "guide.s5_heading"),
        }

        # ---------- Navigation ----------
        def zeichne():
            for kind in inhalt.winfo_children():
                kind.destroy()
            i = zustand["index"]
            zeichenfunktion, titel_key = zeichner[schritte[i]]
            titel_label.configure(text=t(titel_key))
            schritt_label.configure(text=t("guide.step_label", n=i + 1, gesamt=len(schritte)))
            zeichenfunktion()

            letzter = (i == len(schritte) - 1)
            btn_weiter.configure(text=t("guide.finish") if letzter else t("guide.next"))
            # Auf der ersten Seite nur ausgrauen statt ausblenden, damit die
            # Fussleiste beim Blaettern nicht springt.
            btn_zurueck.configure(state="disabled" if i == 0 else "normal")
            if letzter:
                btn_skip.pack_forget()
            else:
                btn_skip.pack(side="left", padx=(4, 0))

        def blaettern(richtung):
            neuer = zustand["index"] + richtung
            if neuer < 0:
                return
            if neuer >= len(schritte):
                abschliessen(uebersprungen=False)
                return
            zustand["index"] = neuer
            zeichne()

        def abschliessen(uebersprungen):
            gewaehlte_ordner = []
            if mit_ordnerauswahl:
                gewaehlte_ordner = [p for p, var in checkbox_vars.items() if var.get()]
                gewaehlte_ordner.extend(eigene_ordner)

            try:
                top.grab_release()
            except Exception:
                pass
            top.destroy()

            if not mit_ordnerauswahl:
                return

            if uebersprungen:
                self.setze_status(t("onboarding.status_skipped"))
                return
            if not gewaehlte_ordner:
                self.setze_status(t("onboarding.status_none_selected"))
                return

            for ordner in gewaehlte_ordner:
                smart_search.befehl_ordner_hinzufuegen(ordner)
            self.starte_ordner_überwachung()
            self.index_aktualisieren()

        # Das Schliessen ueber das Fenstersymbol verhaelt sich wie
        # "Ueberspringen" - ein halb durchlaufener Assistent darf keinen
        # halben Zustand hinterlassen.
        top.protocol("WM_DELETE_WINDOW", lambda: abschliessen(uebersprungen=True))

        zeichne()

    def einstellungen_exportieren(self):
        self.attributes("-topmost", False)
        pfad = filedialog.asksaveasfilename(
            title=t("backup.export_title"), defaultextension=".json",
            initialfile="smartsearch_einstellungen.json", parent=self
        )
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        if not pfad:
            return
        try:
            smart_search.exportiere_konfiguration(pfad)
            self.setze_status(t("backup.export_status", name=os.path.basename(pfad)))
        except Exception as e:
            self.setze_status(t("backup.export_error", fehler=e))

    def einstellungen_importieren(self):
        self.attributes("-topmost", False)
        pfad = filedialog.askopenfilename(
            title=t("backup.import_title"), filetypes=[(t("backup.import_filetype"), "*.json")], parent=self
        )
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        if not pfad:
            return
        try:
            anzahl_ordner, anzahl_fav = smart_search.importiere_konfiguration(pfad)
            self.favoriten = smart_search.lade_favoriten()
            self.starte_ordner_überwachung()
            self.setze_status(t("backup.import_status", ordner=anzahl_ordner, favoriten=anzahl_fav))
        except Exception as e:
            self.setze_status(t("backup.import_error", fehler=e))

    # ---------- AUTO-UPDATE ----------

    def pruefe_auf_updates(self, manuell=False):
        """Fragt GitHub nach dem neuesten Release ab und zeigt
        bei Bedarf einen Hinweis mit Download-Link.

        manuell=True: Nutzer hat aktiv auf "Nach Updates suchen" geklickt
        -> auch anzeigen, wenn schon die neueste Version läuft oder die
        Prüfung fehlschlägt (Netzwerkfehler etc.).
        manuell=False: automatischer Hintergrund-Check beim Start -> bei
        jedem Fehler oder wenn kein Update verfügbar ist, still bleiben
        und den Nutzer nicht mit einer Meldung stören.

        Läuft in einem Hintergrund-Thread, damit ein langsames/fehlendes
        Netzwerk die Oberfläche nicht blockiert.
        """
        def _hintergrund():
            try:
                # Mit eigenem User-Agent anfragen. Ohne einen solchen sendet
                # urllib "Python-urllib/3.x", und Schutzmechanismen vor
                # automatisierten Zugriffen - bei Cloudflare etwa der
                # Bot-Schutz - weisen solche Anfragen ab. Das Ergebnis war
                # ein HTTP 403, das in der Oberflaeche wie ein
                # Netzwerkproblem aussah, obwohl die Verbindung stand.
                anfrage = urllib.request.Request(
                    GITHUB_RELEASES_API,
                    headers={
                        # GitHub verlangt einen User-Agent und weist Anfragen
                        # ohne einen ab. WELCHER es ist, ist ihnen egal -
                        # anders als der Bot-Erkennung von Cloudflare.
                        "User-Agent": f"SmartSearch/{APP_VERSION}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                with urllib.request.urlopen(anfrage, timeout=UPDATE_CHECK_TIMEOUT_SEK) as antwort:
                    daten = json.loads(antwort.read().decode("utf-8"))

                # GitHub liefert die Markierung als "v1.0.3";
                # _version_tuple() rechnet mit reinen Ziffern.
                neueste_version = str(daten.get("tag_name", "")).strip().lstrip("vV")
                download_url = _download_adresse(daten)
                notizen = _release_notizen(daten.get("body", ""))
            except Exception as e:
                if manuell:
                    self.after(0, lambda e=e: self._update_fehlgeschlagen(e))
                return

            if neueste_version and _version_tuple(neueste_version) > _version_tuple(APP_VERSION):
                self.after(0, lambda: self._zeige_update_verfuegbar(neueste_version, download_url, notizen))
            elif manuell:
                self.after(0, self._update_aktuell)

        threading.Thread(target=_hintergrund, daemon=True).start()

    def pruefe_index_passt(self):
        """Prüft beim Start, ob der gespeicherte Index zum aktuellen
        Suchmodell gehört - und stößt sonst den Neuaufbau an.

        Hintergrund: Die Vektoren im Index stammen aus einem bestimmten
        Modell (siehe MODELL_NAME und INDEX_FORMAT in search.py). Wechselt
        das Modell, verwirft search.py den alten Index beim Laden. Ohne
        diesen Hinweis stünde der Benutzer dann vor einer Suche, die
        grundlos nichts findet.

        Läuft im Hintergrund, weil dafür die Indexdatei gelesen wird - bei
        einem großen Index dauert das einen Moment, und der Programmstart
        soll nicht darauf warten.
        """
        def _hintergrund():
            try:
                fremd = smart_search.index_ist_fremd()
            except Exception as e:
                print(f"[Index] Prüfung fehlgeschlagen: {e}")
                return
            if fremd:
                self.after(0, self._index_neuaufbau_ankuendigen)

        threading.Thread(target=_hintergrund, daemon=True).start()

    def _index_neuaufbau_ankuendigen(self):
        messagebox.showinfo(t("index.rebuild_title"), t("index.rebuild_body"))
        self.index_aktualisieren()

    def _update_fehlgeschlagen(self, fehler):
        # Absichtlich NICHT pauschal "keine Internetverbindung" behaupten.
        # Die Prüfung kann auch fehlschlagen, wenn das Netz steht: eine
        # Störung bei GitHub, ein Sperrfilter im Firmennetz, ein
        # überschrittenes Anfragelimit. Genau diese Fälle sahen beim Testen
        # fälschlich nach einem Netzwerkproblem aus.
        messagebox.showinfo(
            t("update.check_failed_title"),
            t("update.check_failed_body", fehler=fehler),
        )

    def _update_aktuell(self):
        messagebox.showinfo(t("update.up_to_date_title"), t("update.up_to_date_body", version=APP_VERSION))

    def _zeige_update_verfuegbar(self, neue_version, download_url, notizen):
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("update.available_title"))
        # Ohne Änderungstext reichen 260 Pixel; mit einem längeren würden
        # die Knöpfe sonst aus dem Fenster geschoben.
        top.geometry("400x340" if len(notizen or "") > 160 else "400x260")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)
        top.grab_set()

        ctk.CTkLabel(
            top, text=t("update.available_heading", version=neue_version), font=("Helvetica", 14, "bold")
        ).pack(padx=20, pady=(20, 4), anchor="w")
        ctk.CTkLabel(
            top, text=t("update.available_current", version=APP_VERSION), font=("Helvetica", 11), text_color="#78909c"
        ).pack(padx=20, pady=(0, 10), anchor="w")

        if notizen:
            ctk.CTkLabel(
                top, text=notizen, font=("Helvetica", 10), text_color="#78909c",
                justify="left", wraplength=360
            ).pack(padx=20, pady=(0, 10), anchor="w")

        def herunterladen():
            if download_url:
                webbrowser.open(download_url)
            top.destroy()

        button_zeile = ctk.CTkFrame(top, fg_color="transparent")
        button_zeile.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(
            button_zeile, text=t("update.later_button"), fg_color="transparent", hover_color=("#e0e0e0", "#3a3a3a"),
            command=top.destroy
        ).pack(side="left")
        ctk.CTkButton(
            button_zeile, text=t("update.download_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
            command=herunterladen
        ).pack(side="right")

    def ordner_verwalten_gui(self):
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("folders.dialog_title"))
        top.geometry("520x360")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)
        top.grab_set()

        lbl = ctk.CTkLabel(top, text=t("folders.heading"), font=("Helvetica", 14, "bold"))
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        scroll = ctk.CTkScrollableFrame(top, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        def lade_ordner_liste():
            for w in scroll.winfo_children():
                w.destroy()

            config = smart_search.lade_config()
            ordner_liste = config.get("ordner", [])

            if not ordner_liste:
                ctk.CTkLabel(scroll, text=t("folders.empty"), font=("Helvetica", 12), text_color="#78909c").pack(pady=20)
                return

            for o in ordner_liste:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=3)

                lbl_p = ctk.CTkLabel(row, text=o, font=("Helvetica", 11), anchor="w")
                lbl_p.pack(side="left", fill="x", expand=True, padx=4)

                def _entfernen_mit_bestaetigung(pfad=o):
                    bestaetigt = messagebox.askyesno(
                        t("folders.remove_confirm_title"),
                        t("folders.remove_confirm_body", pfad=pfad),
                        parent=top,
                    )
                    if bestaetigt:
                        smart_search.befehl_ordner_entfernen(pfad)
                        lade_ordner_liste()
                        self.starte_ordner_überwachung()

                btn_del = ctk.CTkButton(
                    row, text=t("folders.remove_button"), width=70, height=24, fg_color=farben.WARNUNG, hover_color=farben.WARNUNG_HOVER, font=("Helvetica", 10),
                    command=_entfernen_mit_bestaetigung
                )
                btn_del.pack(side="right", padx=4)

        lade_ordner_liste()

        btn_add = ctk.CTkButton(top, text=t("folders.add_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda: [self.ordner_hinzufuegen_gui(), lade_ordner_liste()])
        btn_add.pack(side="left", padx=15, pady=(0, 15))

        btn_close = ctk.CTkButton(top, text=t("folders.close_button"), command=top.destroy)
        btn_close.pack(side="right", padx=15, pady=(0, 15))

    # ---------- INDEX MIT ECHTER PROZENT-ANZEIGE ----------

    def index_aktualisieren(self):
        # Verhindert, dass ein manueller Klick und ein Watchdog-Trigger
        # gleichzeitig zwei Indexierungs-Threads starten.
        if not self.indexierung_lock.acquire(blocking=False):
            self.setze_status(t("index.status_already_running"))
            return

        config = smart_search.lade_config()
        ordner_liste = config.get("ordner", [])
        if not ordner_liste:
            self.setze_status(t("index.status_need_folder"))
            self.indexierung_lock.release()
            return

        self.indexierung_laeuft = True
        self.indexierung_abbrechen = False
        self._buttons_sperren()
        self.zeige_fortschritt(0.05, t("index.status_starting"))
        self.btn_index_abbrechen.grid(row=0, column=2, sticky="e", padx=4)
        threading.Thread(target=self._index_bg, args=(ordner_liste,), daemon=True).start()

    def index_abbrechen(self):
        self.indexierung_abbrechen = True
        self.setze_status(t("index.status_cancelling"))

    def _index_bg(self, ordner_liste):
        # FIX: aktualisiere_index() erwartet einen ORDNER (macht intern
        # os.walk darauf), nicht einen einzelnen Dateipfad. Vorher wurde
        # hier pro Datei aufgerufen -> os.walk() auf eine Datei liefert
        # nichts -> nichts wurde je indexiert, obwohl die GUI "erfolgreich"
        # meldete. Jetzt: einmal pro überwachtem Ordner aufrufen und die
        # Prozentanzeige über fortschritt_fn aus search.py speisen, das
        # Backend übernimmt intern weiterhin die inkrementelle Prüfung
        # (nur neue/geänderte Dateien werden neu eingebettet).
        try:
            # Beim allerersten Start muss erst das KI-Modell geladen werden
            # (einmalig ca. 2,3 GB). Ohne sichtbaren Fortschritt sieht die
            # App dabei minutenlang aus, als haenge sie - deshalb wird der
            # Download ueber dieselbe Statuszeile gemeldet wie spaeter die
            # Indexierung.
            def modell_fortschritt(geladen, gesamt):
                anteil = min(geladen / gesamt, 0.99) if gesamt else 0
                text = t(
                    "model.download_progress",
                    geladen=self._gb_text(geladen), gesamt=self._gb_text(gesamt),
                )
                self.after(0, lambda: self.zeige_fortschritt(anteil, text))

            if not smart_search.modell_ist_vorhanden():
                self.after(0, lambda: self.zeige_fortschritt(0, t("model.download_start")))

            modell = smart_search.geladenes_modell(fortschritt_fn=modell_fortschritt)

            # Gesamtzahl vorab zählen, für einen korrekten Prozentwert
            # über alle Ordner hinweg.
            alle_dateien = []
            for o in ordner_liste:
                if os.path.exists(o):
                    alle_dateien.extend(smart_search.dateien_im_ordner(o))

            gesamt = len(alle_dateien)
            if gesamt == 0:
                self.after(0, self._index_fertig)
                return

            zaehler = {"n": 0}
            start_zeit = time.time()
            batch_phase_start = {"zeit": None}

            def fortschritt(idx, dateiname):
                if idx is None:
                    # Signal aus search.py: das ist die KI-Berechnungsphase
                    # (Batch X/Y), kein neu gelesenes Dokument. Balken bleibt
                    # bei ~95%, damit klar sichtbar ist, dass noch etwas
                    # läuft, ohne die Datei-Fortschrittszählung zu verfälschen.
                    # Zusätzlich: Restzeit anhand des Batch-Fortschritts
                    # schätzen, sobald die "Batch X/Y"-Angabe im Text steckt.
                    match = re.search(r"Batch (\d+)/(\d+)", dateiname)
                    text = dateiname
                    if match:
                        aktueller_batch, gesamt_batches = int(match.group(1)), int(match.group(2))
                        if batch_phase_start["zeit"] is None:
                            batch_phase_start["zeit"] = time.time()
                        elapsed = time.time() - batch_phase_start["zeit"]
                        if aktueller_batch > 0:
                            rate = elapsed / aktueller_batch
                            rest_sek = rate * (gesamt_batches - aktueller_batch)
                            text = t("index.progress_calculating", text=dateiname, zeit=self._dauer_text(rest_sek))
                    self.after(0, lambda txt=text: self.zeige_fortschritt(0.95, txt))
                    return
                zaehler["n"] += 1
                prozent = min(zaehler["n"] / gesamt, 1.0)
                elapsed = time.time() - start_zeit
                rate = elapsed / zaehler["n"]
                rest_sek = rate * (gesamt - zaehler["n"])
                text = t(
                    "index.progress_indexing", n=zaehler["n"], gesamt=gesamt,
                    name=dateiname[:25], zeit=self._dauer_text(rest_sek)
                )
                self.after(0, lambda p=prozent, txt=text: self.zeige_fortschritt(p, txt))

            abgebrochen = False
            for o in ordner_liste:
                if self.indexierung_abbrechen:
                    abgebrochen = True
                    break
                if not os.path.exists(o):
                    continue
                smart_search.aktualisiere_index(
                    o, modell=modell, still=True, fortschritt_fn=fortschritt
                )

            if not abgebrochen:
                # Karteileichen entfernen: Eintraege aus Ordnern, die nicht
                # mehr ueberwacht werden, und Dateien, die es nicht mehr
                # gibt. Ohne das waechst index.pkl endlos und liefert
                # Treffer aus laengst entfernten Ordnern.
                try:
                    smart_search.bereinige_index()
                except Exception as e:
                    print(f"[Index] Aufraeumen uebersprungen: {e}")

            if abgebrochen:
                self.after(0, self._index_abgebrochen)
            else:
                self.after(0, self._index_fertig)
        except smart_search.ProgrammUnvollstaendig as e:
            # Muss VOR ModellDownloadFehler stehen: ein fehlender
            # Programmteil sieht an dieser Stelle aus wie ein
            # Download-Problem, ist aber keines - der Nutzer soll nicht
            # vergeblich seine Verbindung prüfen.
            self.after(0, lambda e=e: self._programm_unvollstaendig(e))
        except smart_search.ModellDownloadFehler as e:
            # Getrennt behandelt: das ist kein Indexierungsfehler, sondern
            # fast immer "beim ersten Start kein Internet". Ein roher
            # Netzwerk-Stacktrace hilft an dieser Stelle niemandem.
            self.after(0, lambda e=e: self._modell_download_fehlgeschlagen(e))
        except Exception as e:
            self.after(0, lambda e=e: self._index_fehlgeschlagen(e))
        finally:
            self.indexierung_laeuft = False
            self.indexierung_lock.release()

    @staticmethod
    def _gb_text(bytes_zahl):
        """Bytes als "1,4 GB" - mit Komma, weil die Anzeige im deutschen
        Teil der Oberflaeche sonst fremd wirkt."""
        gb = bytes_zahl / 1_000_000_000
        return f"{gb:.1f}".replace(".", ",") + " GB"

    def _modell_download_fehlgeschlagen(self, fehler):
        """Erklaert den einen Fall, der einen neuen Nutzer sonst ratlos
        zuruecklaesst: die App wurde gerade installiert, das KI-Modell fehlt
        noch, und es ist kein Internet da."""
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(t("model.download_failed_status"))

        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("model.download_failed_title"))
        top.geometry("460x260")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)

        ctk.CTkLabel(
            top, text=t("model.download_failed_heading"), font=("Helvetica", 15, "bold")
        ).pack(padx=20, pady=(20, 8), anchor="w")

        ctk.CTkLabel(
            top, text=t("model.download_failed_body"), font=("Helvetica", 11),
            text_color="#78909c", justify="left", wraplength=410
        ).pack(padx=20, pady=(0, 10), anchor="w")

        ctk.CTkLabel(
            top, text=t("model.download_failed_details", fehler=fehler),
            font=("Helvetica", 10), text_color="#90a4ae", justify="left", wraplength=410
        ).pack(padx=20, pady=(0, 12), anchor="w")

        zeile = ctk.CTkFrame(top, fg_color="transparent")
        zeile.pack(side="bottom", fill="x", padx=20, pady=16)

        ctk.CTkButton(
            zeile, text=t("model.download_failed_close"), fg_color="transparent",
            hover_color=("#e0e0e0", "#3a3a3a"), command=top.destroy
        ).pack(side="left")

        def erneut_versuchen():
            top.destroy()
            self.index_aktualisieren()

        ctk.CTkButton(
            zeile, text=t("model.download_failed_retry"), fg_color=farben.SEITE_KNOPF,
            hover_color=farben.SEITE_KNOPF_HOVER, command=erneut_versuchen
        ).pack(side="right")

    def _programm_unvollstaendig(self, fehler):
        """Der Gegenfall zum Download-Dialog: hier fehlt kein Modell,
        sondern ein Programmteil. Kein "Erneut versuchen" - das würde nur
        denselben Fehler ein zweites Mal zeigen."""
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(t("model.incomplete_status"))

        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("model.incomplete_title"))
        top.geometry("460x300")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)

        ctk.CTkLabel(
            top, text=t("model.incomplete_heading"), font=("Helvetica", 15, "bold")
        ).pack(padx=20, pady=(20, 8), anchor="w")

        ctk.CTkLabel(
            top, text=t("model.incomplete_body"), font=("Helvetica", 11),
            text_color="#78909c", justify="left", wraplength=410
        ).pack(padx=20, pady=(0, 10), anchor="w")

        ctk.CTkLabel(
            top, text=t("model.download_failed_details", fehler=fehler),
            font=("Helvetica", 10), text_color="#90a4ae", justify="left", wraplength=410
        ).pack(padx=20, pady=(0, 12), anchor="w")

        zeile = ctk.CTkFrame(top, fg_color="transparent")
        zeile.pack(side="bottom", fill="x", padx=20, pady=16)

        ctk.CTkButton(
            zeile, text=t("model.download_failed_close"), fg_color="transparent",
            hover_color=("#e0e0e0", "#3a3a3a"), command=top.destroy
        ).pack(side="left")

        def melden():
            top.destroy()
            self.oeffne_rueckmeldung(vorbelegung=str(fehler))

        ctk.CTkButton(
            zeile, text=t("model.incomplete_report"), fg_color=farben.SEITE_KNOPF,
            hover_color=farben.SEITE_KNOPF_HOVER, command=melden
        ).pack(side="right")

    def _index_fertig(self):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(t("index.status_done"))
        plattform.benachrichtigung(t("index.notification_title"), t("index.notification_body"))
        self.aktualisiere_fehler_anzeige()

    def _index_abgebrochen(self):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(t("index.status_cancelled"))
        self.aktualisiere_fehler_anzeige()

    # ---------- FEHLERSICHTBARKEIT (nicht lesbare Dateien) ----------

    def aktualisiere_fehler_anzeige(self):
        """Blendet den Warnbutton ein/aus, je nachdem ob es Dateien gibt,
        die beim Indexieren nicht gelesen werden konnten. Vorher landeten
        solche Fehler nur im Terminal und wurden z.B. bei laufendem
        Autostart im Hintergrund nie bemerkt."""
        anzahl = len(smart_search.fehlgeschlagene_dateien())
        if anzahl > 0:
            self.btn_fehler_anzeigen.configure(text=t("sidebar.errors_button", anzahl=anzahl))
            # Direkt unter "Index aktualisieren" einsortiert (after=
            # index_button bestimmt die Stapel-Position) - noch über dem
            # "⚙ Einstellungen..."-Link.
            self.btn_fehler_anzeigen.pack(padx=12, pady=(3, 3), fill="x", after=self.index_button)
        else:
            self.btn_fehler_anzeigen.pack_forget()

    def fehlgeschlagene_dateien_dialog(self):
        """Zeigt die Liste der nicht lesbaren Dateien und bietet einen
        Neuversuch-Button an (z.B. sinnvoll nach nachträglicher
        OCR-Installation - vorher musste man dafür den kompletten Index
        löschen und alles neu durchlaufen lassen)."""
        dateien = smart_search.fehlgeschlagene_dateien()

        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title(t("errors.dialog_title"))
        top.geometry("560x400")
        top.attributes("-topmost", True)
        self.nebenfenster_anmelden(top)
        top.grab_set()

        lbl = ctk.CTkLabel(
            top, text=t("errors.dialog_heading", anzahl=len(dateien)),
            font=("Helvetica", 14, "bold")
        )
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        hinweis = ctk.CTkLabel(
            top,
            text=t("errors.dialog_reason"),
            font=("Helvetica", 10), text_color="#78909c", justify="left"
        )
        hinweis.pack(padx=15, pady=(0, 10), anchor="w")

        scroll = ctk.CTkScrollableFrame(top, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for pfad in dateien:
            ctk.CTkLabel(scroll, text=pfad, font=("Helvetica", 10), anchor="w", justify="left").pack(fill="x", pady=1)

        def neuversuch():
            entfernt = smart_search.entferne_fehlgeschlagene_markierung()
            top.destroy()
            self.setze_status(t("errors.retry_status", anzahl=entfernt))
            self.aktualisiere_fehler_anzeige()

        btn_retry = ctk.CTkButton(
            top, text=t("errors.retry_button"),
            fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=neuversuch
        )
        btn_retry.pack(side="left", padx=15, pady=(0, 15))

        btn_close = ctk.CTkButton(top, text=t("errors.close_button"), command=top.destroy)
        btn_close.pack(side="right", padx=15, pady=(0, 15))

    def _index_fehlgeschlagen(self, fehler):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(t("index.status_error", fehler=fehler))
        self.aktualisiere_fehler_anzeige()

    # ---------- SUCHE ----------

    def suchen(self):
        anfrage = self.suchfeld.get().strip()
        if not anfrage or anfrage == PLATZHALTER_TEXT:
            return

        self.verlauf_aktualisieren(anfrage)
        self._suche_button_sperren()
        self.setze_status(t("search.status_searching"))
        ausschluss = self.ausgeschlossene_typen()
        zeitraum_anzeige = self.zeitraum_menu.get()
        zeitraum = self.zeitraum_anzeige_zu_code.get(zeitraum_anzeige, "alle")

        threading.Thread(target=self._suche_bg, args=(anfrage, ausschluss, zeitraum), daemon=True).start()

    def _suche_bg(self, anfrage, ausschluss, zeitraum):
        try:
            treffer = smart_search.suche_intern(anfrage, top_n=15, ausgeschlossene_typen=ausschluss, zeitraum=zeitraum)
            self.after(0, self._zeige_treffer, treffer, anfrage)
        except Exception as e:
            self.after(0, lambda e=e: self._suche_fehlgeschlagen(e))

    def _suche_fehlgeschlagen(self, fehler):
        self._suche_button_entsperren()
        self.setze_status(t("search.status_error", fehler=fehler))

    def _zeige_treffer(self, treffer, anfrage):
        self._suche_button_entsperren()
        if treffer is None:
            self.setze_status(t("search.status_no_index"))
            self.aktuelle_treffer = []
            self.aktuelle_such_woerter = []
            self.zeige_aktuelle_ergebnisse()
            return
        self.aktuelle_treffer = treffer
        # Suchwoerter merken - die Trefferkarten faerben sie im
        # Textausschnitt ein (siehe zeige_aktuelle_ergebnisse).
        self.aktuelle_such_woerter = smart_search.anfrage_woerter(anfrage)
        self.zeige_aktuelle_ergebnisse()
        if treffer:
            self._rueckmeldung_zaehlen()

    def _null_treffer_hinweis(self, anfrage):
        """Ermittelt eine hilfreiche, konkrete Erklärung dafür, warum eine
        Suche 0 Treffer ergeben hat - statt nur "Keine Treffer gefunden.",
        das dem Nutzer keinen Ansatzpunkt gibt, was er ändern könnte."""
        ordner_liste = smart_search.lade_config().get("ordner", [])
        if not ordner_liste:
            return t("results.none_no_folder")

        aktive_filter = self.ausgeschlossene_typen()
        if aktive_filter:
            return t("results.none_filtered", anfrage=anfrage)

        if not os.path.exists(smart_search.INDEX_FILE):
            return t("results.none_never_indexed")

        return t("results.none_generic", anfrage=anfrage)

    def zeige_aktuelle_ergebnisse(self):
        for w in self.cards_scrollframe.winfo_children():
            w.destroy()

        self.card_widgets = []
        self.fokussierter_index = -1

        if not self.aktuelle_treffer:
            anfrage = self.suchfeld.get().strip()
            hinweis = self._null_treffer_hinweis(anfrage)
            ctk.CTkLabel(
                self.cards_scrollframe, text=hinweis, font=("Helvetica", 12),
                text_color="#78909c", justify="center", wraplength=600
            ).pack(pady=40, padx=20)
            self.setze_status(t("search.status_no_results"))
            return

        for score, eintrag in self.aktuelle_treffer:
            pfad = eintrag["datei"]
            name = os.path.basename(pfad)
            ext = os.path.splitext(name)[1].lower()
            bg_col, fg_col = BADGE_FARBEN.get(ext, farben.BADGE_RUECKFALL)

            card = ctk.CTkFrame(self.cards_scrollframe, corner_radius=8)
            card.pack(fill="x", padx=2, pady=3)

            # Obere Zeile: Badge, Dateiname, Aktions-Buttons
            zeile_oben = ctk.CTkFrame(card, fg_color="transparent")
            zeile_oben.pack(fill="x", padx=0, pady=(6, 0))

            lbl_badge = ctk.CTkLabel(zeile_oben, text=f" {ext.replace('.','').upper()} ", font=("Helvetica", 9, "bold"), fg_color=bg_col, text_color=fg_col, corner_radius=4)
            lbl_badge.pack(side="left", padx=8, pady=8)

            lbl_titel = ctk.CTkLabel(zeile_oben, text=f"[{score:.2f}] {self._kuerze_dateiname(name)}", font=("Helvetica", 11, "bold"), text_color=farben.DATEINAME)
            lbl_titel.pack(side="left", padx=4)

            btn_sim = ctk.CTkButton(zeile_oben, text=t("card.similar"), width=65, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: self.aehnliche_suchen(p))
            btn_sim.pack(side="right", padx=2)

            btn_ql = ctk.CTkButton(zeile_oben, text=t("card.preview"), width=65, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: self.quicklook_im_vordergrund(p))
            btn_ql.pack(side="right", padx=2)

            btn_finder = ctk.CTkButton(zeile_oben, text=t("card.finder"), width=55, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: self.im_finder_zeigen_im_vordergrund(p))
            btn_finder.pack(side="right", padx=2)

            btn_open = ctk.CTkButton(zeile_oben, text=t("card.open"), width=50, height=20, font=("Helvetica", 9), command=lambda p=pfad: self.datei_oeffnen_im_vordergrund(p))
            btn_open.pack(side="right", padx=4)

            ist_favorit = pfad in self.favoriten
            btn_fav = ctk.CTkButton(
                zeile_oben, text="★" if ist_favorit else "☆", width=24, height=20,
                font=("Helvetica", 11), fg_color="transparent",
                text_color="#f57f17" if ist_favorit else "#78909c",
                hover_color=("#e0e0e0", "#3a3a3a"),
                command=lambda p=pfad: self._favorit_umschalten(p)
            )
            btn_fav.pack(side="right", padx=2)

            # Untere Zeile: kurzer Textausschnitt aus dem getroffenen
            # Abschnitt, damit man sieht WARUM die Datei getroffen hat,
            # statt nur den nackten Score zu sehen.
            # Der Ausschnitt wird um die Fundstelle herum gewaehlt und die
            # Suchwoerter darin eingefaerbt. Ein einfaches Label kann keinen
            # Text teilweise faerben - deshalb ein Textfeld, das wie ein
            # Label aussieht: ohne Rahmen, ohne Rollbalken, nicht editierbar.
            ausschnitt, stellen = smart_search.ausschnitt_mit_fundstellen(
                eintrag.get("text"), self.aktuelle_such_woerter)
            if ausschnitt:
                txt_ausschnitt = ctk.CTkTextbox(
                    card, height=46, font=("Helvetica", 10),
                    fg_color="transparent", border_width=0, wrap="word",
                    activate_scrollbars=False, text_color="#90a4ae"
                )
                txt_ausschnitt.pack(fill="x", padx=8, pady=(0, 6))
                txt_ausschnitt.insert("1.0", "„" + ausschnitt + "“")

                try:
                    txt_ausschnitt.tag_config(
                        "fundstelle", background=farben.FUND_HINTERGRUND,
                        foreground=farben.FUND_TEXT)
                    for start_, ende_ in stellen:
                        # +1 wegen des vorangestellten Anfuehrungszeichens.
                        txt_ausschnitt.tag_add(
                            "fundstelle", f"1.{start_ + 1}", f"1.{ende_ + 1}")
                except Exception as e:
                    # Aeltere CustomTkinter-Fassungen reichen die Tag-Aufrufe
                    # nicht weiter. Dann bleibt der Text eben ungefaerbt -
                    # lesbar ist er trotzdem.
                    print(f"[Hinweis] Fundstellen nicht hervorhebbar: {e}")

                txt_ausschnitt.configure(state="disabled")
                # Immer am Anfang stehen bleiben und keine Rollereignisse
                # abfangen - sonst scrollt beim Suchen die Trefferliste weg.
                try:
                    txt_ausschnitt.yview_moveto(0)
                    inneres = txt_ausschnitt._textbox
                    inneres.configure(takefocus=False, cursor="arrow")
                    for ereignis in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                        inneres.bind(ereignis, self._rollen_weiterreichen)
                except Exception:
                    pass
            else:
                # Kein Textausschnitt vorhanden (z.B. bei Favoriten-Ansicht,
                # wo teils nur Metadaten ohne Chunk-Text vorliegen).
                ctk.CTkFrame(card, height=6, fg_color="transparent").pack(fill="x")

            self.card_widgets.append((card, pfad))

        self.setze_status(t("search.status_results_loaded", anzahl=len(self.aktuelle_treffer)))


def _selbsttest():
    """Prueft im fertigen Bundle, ob sich alle noetigen Bausteine
    tatsaechlich importieren lassen, und beendet sich dann wieder.

    Der Anlass: eine ausgelieferte Fassung startete einwandfrei, scheiterte
    aber auf einem frisch aufgesetzten Mac beim Laden des Suchmodells an
    einem fehlenden Modul ('torchgen'). Die bisherige Pruefung suchte nur
    nach Zeichenketten im Archiv - das faellt bei einem Paket, das
    zusaetzliche Datendateien braucht, nicht auf. Hier wird stattdessen
    wirklich importiert, in genau der Umgebung, die spaeter auch beim
    Nutzer laeuft.
    """
    pflicht = [
        "torch", "torchgen", "sentence_transformers", "transformers",
        "numpy", "customtkinter",
    ]
    optional = {
        "pdfplumber": "PDF (Haupterkennung)",
        "pypdf": "PDF (Ausweichweg)",
        "docx": "Word",
        "openpyxl": "Excel",
        "pptx": "PowerPoint",
        "pypdfium2": "Seiten fuer Texterkennung",
        "Vision": "Texterkennung",
        "watchdog": "Automatische Aktualisierung",
        "langchain_text_splitters": "Aufteilung in Abschnitte",
    }

    import importlib
    fehler = 0

    print("Zwingend erforderlich:")
    for name in pflicht:
        try:
            importlib.import_module(name)
            print(f"  ok      {name}")
        except Exception as e:
            print(f"  FEHLT   {name}: {e}")
            fehler += 1

    print("\nJe Dateiformat:")
    for name, zweck in optional.items():
        try:
            importlib.import_module(name)
            print(f"  ok      {name:26s} {zweck}")
        except Exception as e:
            print(f"  FEHLT   {name:26s} {zweck}  ({e})")
            fehler += 1

    # Der eigentliche Stolperstein lag nicht im Import von torch, sondern
    # im Aufbau eines Modells. Deshalb hier zusaetzlich der Weg, den auch
    # die Anwendung geht - ohne Netzzugriff, es geht nur um die Module.
    print("\nModellklasse:")
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        from transformers import AutoTokenizer  # noqa: F401
        print("  ok      Modell- und Tokenizer-Klassen ladbar")
    except Exception as e:
        print(f"  FEHLT   {e}")
        fehler += 1

    print()
    if fehler:
        print(f"Ergebnis: {fehler} Baustein(e) fehlen. Das Bundle ist unbrauchbar.")
    else:
        print("Ergebnis: vollstaendig.")
    sys.exit(1 if fehler else 0)


SPERRDATEI = os.path.join(DATEN_ORDNER, "laeuft.pid")

# Wird von einer zweiten, gerade gestarteten Kopie angelegt und von der
# bereits laufenden Kopie in check_toggle_loop() ausgewertet.
ZEIGEN_SIGNAL = os.path.join(DATEN_ORDNER, "fenster_zeigen.signal")


def _bitte_fenster_zeigen():
    """Der laufenden Instanz mitteilen, dass sie sich zeigen soll."""
    try:
        os.makedirs(DATEN_ORDNER, exist_ok=True)
        with open(ZEIGEN_SIGNAL, "w") as f:
            f.write("zeigen")
    except Exception as e:
        print(f"[Start] Signal an laufende Instanz fehlgeschlagen: {e}")


def _bereits_offene_instanz_aktivieren():
    """Sorgt dafuer, dass SmartSearch hoechstens einmal laeuft.

    Warum das noetig ist: Auf einem Mac koennen problemlos zwei Kopien
    derselben Anwendung gleichzeitig laufen - eine aus dem
    Programme-Ordner, eine aus einem Bau- oder Testordner. Beide heissen
    SmartSearch, beide legen ein Symbol in der Menueleiste an, und beide
    greifen auf denselben Index zu. Fuer den Benutzer sieht das aus, als
    haette sich das Programm von selbst ein zweites Mal geoeffnet.

    Ist bereits eine Instanz da, wird sie nach vorne geholt und diese hier
    beendet sich sofort - dasselbe Verhalten, das man von jeder anderen
    Mac-Anwendung kennt.

    Rueckgabe: True, wenn sich dieser Start beenden soll.
    """
    # 1. Der saubere Weg ueber das Betriebssystem: macOS fuehrt Buch
    #    darueber, welche Anwendungen mit welcher Bundle-Kennung laufen.
    #    Das erfasst auch eine zweite Kopie an einem anderen Ort.
    if system_ui:
        # Reihenfolge wichtig: erst das Signal legen, dann die laufende
        # Kopie nach vorne holen - so ist ihr Fenster schon auf dem Weg,
        # wenn sie aktiviert wird (siehe _bitte_fenster_zeigen).
        _bitte_fenster_zeigen()
        if system_ui.laufende_instanz_aktivieren():
            print("[Start] SmartSearch laeuft bereits - vorhandenes Fenster geholt.")
            return True
        # Es lief doch keine zweite Kopie: das eben gelegte Signal wieder
        # wegraeumen, damit sich dieses Fenster nicht gleich beim eigenen
        # Start selbst "von aussen" anstupst.
        try:
            if os.path.exists(ZEIGEN_SIGNAL):
                os.remove(ZEIGEN_SIGNAL)
        except Exception:
            pass

    # 2. Ausweichweg fuer den Fall, dass die Anwendung ohne Bundle
    #    gestartet wurde (direkt ueber die Programmdatei oder als
    #    "python3 gui.py") - dann kennt macOS keine Bundle-Kennung.
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
                    _bitte_fenster_zeigen()
                    print(f"[Start] SmartSearch laeuft bereits (Prozess {alte_pid}).")
                    return True
        os.makedirs(os.path.dirname(SPERRDATEI), exist_ok=True)
        with open(SPERRDATEI, "w") as f:
            f.write(str(os.getpid()))
        import atexit
        atexit.register(lambda: os.path.exists(SPERRDATEI) and os.remove(SPERRDATEI))
    except Exception as e:
        # Eine fehlgeschlagene Pruefung darf den Start nie verhindern.
        print(f"[Start] Sperrdatei konnte nicht angelegt werden: {e}")

    return False


def _start_protokollieren():
    """Schreibt eine Zeile pro Programmstart nach start_log.txt.

    Reine Diagnosehilfe: taucht ein zweites Dock-Symbol auf, steht hier
    schwarz auf weiss, ob wirklich ein zweiter Prozess gestartet wurde
    (zwei Zeilen mit unterschiedlicher Prozessnummer im selben Moment)
    oder ob macOS nur zweimal dasselbe Programm anzeigt. Die Datei bleibt
    klein - es werden nur die letzten 50 Zeilen aufgehoben.
    """
    try:
        from pfade import DATEN_ORDNER
        os.makedirs(DATEN_ORDNER, exist_ok=True)
        pfad = os.path.join(DATEN_ORDNER, "start_log.txt")
        zeile = "%s  PID %s  Elternprozess %s  argv=%s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), os.getppid(), sys.argv)
        zeilen = []
        if os.path.exists(pfad):
            with open(pfad, encoding="utf-8", errors="replace") as f:
                zeilen = f.readlines()[-49:]
        with open(pfad, "w", encoding="utf-8") as f:
            f.writelines(zeilen)
            f.write(zeile)
    except Exception as e:
        print(f"[Start] Startprotokoll nicht moeglich: {e}")


if __name__ == "__main__":
    _start_protokollieren()

    if "--selbsttest" in sys.argv:
        _selbsttest()

    if _bereits_offene_instanz_aktivieren():
        sys.exit(0)

    # Muss VOR dem ersten Fenster stehen: Tk liest den Programmnamen fuer
    # das Anwendungsmenue genau einmal, beim Aufbau des Fensters.
    if system_ui and hasattr(system_ui, "programmnamen_setzen"):
        system_ui.programmnamen_setzen("SmartSearch")

    app_window = SmartSearchNotchWindow()

    programm_ordner = os.path.dirname(os.path.abspath(__file__))

    if system_ui:
        # Symbol in der Menueleiste (Mac) bzw. im Infobereich (Windows).
        # Das Ergebnis MUSS in einer Variablen bleiben, sonst raeumt Python
        # das Objekt weg und das Symbol verschwindet wieder.
        status_handler = system_ui.menueleisten_symbol_anlegen(
            lambda: setattr(app_window, "toggle_requested", True),
            beenden_callback=lambda: setattr(app_window, "beenden_requested", True),
            icon_pfad=os.path.join(programm_ordner, "icon.png"),
        )
        system_ui.als_programm_im_dock_anmelden()
        system_ui.dock_symbol_setzen(os.path.join(programm_ordner, "icon.png"))

    if plattform.IST_WINDOWS:
        # Fenster- und Taskleistensymbol setzt unter Windows Tkinter selbst,
        # dafuer braucht es die .ico-Datei (.png versteht Windows an dieser
        # Stelle nicht).
        try:
            app_window.iconbitmap(os.path.join(programm_ordner, "icon.ico"))
        except Exception as e:
            print(f"[Icon] Fenstersymbol konnte nicht gesetzt werden: {e}")

    app_window.mainloop()