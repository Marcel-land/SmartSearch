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

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import json
import os
import subprocess
import sys
import time
import re

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_VERFUEGBAR = True
except ImportError:
    WATCHDOG_VERFUEGBAR = False

import objc
from AppKit import (
    NSStatusBar,
    NSVariableStatusItemLength,
    NSObject,
    NSApp,
    NSApplicationActivationPolicyRegular,
)

import search as smart_search

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

VERLAUF_DATEI = os.path.join(os.path.dirname(__file__), "verlauf.json")
MAX_VERLAUF = 20
PLATZHALTER_TEXT = "🔍 Wonach suchst du? (z.B. Rechnung, Vertrag...)"
UNTERSTUETZTE_ENDUNGEN = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"}

DATEITYP_GRUPPEN = {
    "PDF": {".pdf"},
    "Word": {".docx"},
    "Excel": {".xlsx"},
    "PowerPoint": {".pptx"},
    "Text": {".txt", ".md"},
}

BADGE_FARBEN = {
    ".pdf": ("#e53935", "#ffffff"),
    ".docx": ("#1e88e5", "#ffffff"),
    ".xlsx": ("#43a047", "#ffffff"),
    ".pptx": ("#fb8c00", "#ffffff"),
    ".txt": ("#757575", "#ffffff"),
    ".md": ("#8e24aa", "#ffffff"),
}


def send_macos_notification(title, message):
    """Zeigt eine native macOS-Notification. Escaped Anführungszeichen/Backslashes,
    damit Datei- oder Suchbegriffe das AppleScript nicht brechen können."""
    try:
        def escape(text):
            return text.replace("\\", "\\\\").replace('"', '\\"')

        script = f'display notification "{escape(message)}" with title "{escape(title)}"'
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception as e:
        print(f"[Notifikation Fehler] {e}")


def quicklook_vorschau(dateipfad):
    if dateipfad and os.path.exists(dateipfad):
        try:
            subprocess.Popen(["qlmanage", "-p", dateipfad], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[QuickLook Fehler] {e}")



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

        self.title("SmartSearch")
        self.attributes("-topmost", True)
        self.geometry("780x480")

        # -topmost wird IMMER nur reaktiviert, wenn SmartSearch selbst
        # wieder den Fokus bekommt (Klick zurück ins Fenster) - nie mehr
        # automatisch per Timer. So bleiben geöffnete Dateien/Vorschauen
        # und eigene Dialoge (Ordner verwalten, Nicht lesbare Dateien)
        # zuverlässig im Vordergrund, statt dass SmartSearch sich nach
        # kurzer Zeit von selbst wieder darüber schiebt.
        self.bind("<FocusIn>", lambda e: self.attributes("-topmost", True))

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
        self.indexierung_abbrechen = False

        self._sperrbare_buttons = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Hauptcontainer (Clean Mac Look)
        self.bg_frame = ctk.CTkFrame(self, corner_radius=14, border_width=1)
        self.bg_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.bg_frame.grid_columnconfigure(1, weight=1)
        self.bg_frame.grid_rowconfigure(0, weight=1)

        # ================= SEITENLEISTE =================
        self.sidebar_frame = ctk.CTkFrame(self.bg_frame, width=220, corner_radius=12)

        self.sidebar_title = ctk.CTkLabel(self.sidebar_frame, text="⚙️ Einstellungen", font=("Helvetica", 14, "bold"))
        self.sidebar_title.pack(padx=15, pady=(15, 8), anchor="w")

        # LIGHT / DARK MODE SWITCH
        self.theme_label = ctk.CTkLabel(self.sidebar_frame, text="Erscheinungsbild", font=("Helvetica", 10), text_color="#78909c")
        self.theme_label.pack(padx=15, pady=(4, 2), anchor="w")

        self.theme_seg = ctk.CTkSegmentedButton(
            self.sidebar_frame, values=["System", "Light", "Dark"], command=self.theme_wechseln, font=("Helvetica", 10)
        )
        self.theme_seg.set("System")
        self.theme_seg.pack(padx=12, pady=(0, 12), fill="x")

        # MENÜ BUTTONS (Clean Styling)
        self.btn_favs_anzeigen = ctk.CTkButton(
            self.sidebar_frame, text="⭐ Favoriten", fg_color="#37474f", hover_color="#263238", anchor="w", command=self.favoriten_anzeigen
        )
        self.btn_favs_anzeigen.pack(padx=12, pady=3, fill="x")

        self.add_folder_button = ctk.CTkButton(
            self.sidebar_frame, text="📁 Ordner hinzufügen", fg_color="#37474f", hover_color="#263238", anchor="w", command=self.ordner_hinzufuegen_gui
        )
        self.add_folder_button.pack(padx=12, pady=3, fill="x")

        self.manage_button = ctk.CTkButton(
            self.sidebar_frame, text="📂 Ordner verwalten", fg_color="#37474f", hover_color="#263238", anchor="w", command=self.ordner_verwalten_gui
        )
        self.manage_button.pack(padx=12, pady=3, fill="x")

        self.index_button = ctk.CTkButton(
            self.sidebar_frame, text="🔄 Index aktualisieren", fg_color="#1f77b4", hover_color="#1565c0", anchor="w", command=self.index_aktualisieren
        )
        self.index_button.pack(padx=12, pady=3, fill="x")

        # Warnbutton für Dateien, die beim Indexieren nicht gelesen werden
        # konnten (siehe search.fehlgeschlagene_dateien()). Standardmäßig
        # versteckt (kein .pack()) - wird nach jedem Indexierungslauf in
        # _index_fertig() ein- oder ausgeblendet, je nachdem ob es
        # fehlgeschlagene Dateien gibt. Vorher landeten solche Fehler nur
        # im Terminal und wurden im Alltag (z.B. bei Autostart im
        # Hintergrund) nie bemerkt.
        self.btn_fehler_anzeigen = ctk.CTkButton(
            self.sidebar_frame, text="⚠️ 0 Dateien nicht lesbar", fg_color="#e65100", hover_color="#bf360c",
            anchor="w", command=self.fehlgeschlagene_dateien_dialog
        )

        # Export/Import der Einrichtung (überwachte Ordner + Favoriten) als
        # JSON-Datei - praktisch als Backup oder zum Übertragen auf einen
        # anderen Mac, ohne den kompletten (oft großen) Suchindex
        # mitnehmen zu müssen.
        self.export_button = ctk.CTkButton(
            self.sidebar_frame, text="⬇️ Einstellungen exportieren", fg_color="#37474f", hover_color="#263238",
            anchor="w", command=self.einstellungen_exportieren
        )
        self.export_button.pack(padx=12, pady=(8, 3), fill="x")

        self.import_button = ctk.CTkButton(
            self.sidebar_frame, text="⬆️ Einstellungen importieren", fg_color="#37474f", hover_color="#263238",
            anchor="w", command=self.einstellungen_importieren
        )
        self.import_button.pack(padx=12, pady=3, fill="x")

        self.autostart_var = ctk.BooleanVar(value=self.ist_autostart_aktiv())
        self.autostart_cb = ctk.CTkCheckBox(
            self.sidebar_frame, text="Mit Mac starten", variable=self.autostart_var, font=("Helvetica", 11), command=self.autostart_umschalten
        )
        self.autostart_cb.pack(padx=12, pady=10, anchor="w")

        # Datenschutz-Erklärung direkt in der App - macht sichtbar, was
        # sonst nur auf einer externen Landingpage stehen würde: dass
        # alles lokal verarbeitet wird. Wichtig gerade weil Nutzer hier
        # sensible Dokumente (Ausweise, Rechnungen, Verträge) indexieren.
        self.datenschutz_button = ctk.CTkButton(
            self.sidebar_frame, text="🔒 Datenschutz", fg_color="transparent", hover_color=("#e0e0e0", "#3a3a3a"),
            text_color=("#37474f", "#b0bec5"), anchor="w", command=self.zeige_datenschutz_dialog
        )
        self.datenschutz_button.pack(padx=12, pady=(0, 4), anchor="w")

        self.quit_button = ctk.CTkButton(
            self.sidebar_frame, text="✕ Beenden", fg_color="#c62828", hover_color="#b71c1c", anchor="w", command=self.beenden
        )
        self.quit_button.pack(padx=12, pady=(10, 8), fill="x", side="bottom")

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

        self.such_button = ctk.CTkButton(self.top_frame, text="Suchen", width=75, height=34, font=("Helvetica", 11, "bold"), command=self.suchen)
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

        self.zeitraum_menu = ctk.CTkOptionMenu(
            self.filter_frame, values=["Alle Zeiten", "7 Tage", "Dieser Monat", "Dieses Jahr"],
            width=100, height=22, font=("Helvetica", 10), command=lambda e: self.suchen()
        )
        self.zeitraum_menu.pack(side="right", padx=2, pady=1)
        self.zeitraum_menu.set("Alle Zeiten")

        # --- ERGEBNISSE ---
        self.ergebnis_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.ergebnis_container.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.ergebnis_container.grid_columnconfigure(0, weight=1)
        self.ergebnis_container.grid_rowconfigure(0, weight=1)

        self.cards_scrollframe = ctk.CTkScrollableFrame(self.ergebnis_container, corner_radius=8)
        self.cards_scrollframe.grid(row=0, column=0, sticky="nsew")
        self.cards_scrollframe.grid_columnconfigure(0, weight=1)

        self.aktivierte_touchpad_scrolling(self.cards_scrollframe)

        self.lbl_welcome = ctk.CTkLabel(
            self.cards_scrollframe,
            text="✨ Bereit für deine Suche.\n\nTippe oben deinen Begriff ein.",
            font=("Helvetica", 12), text_color="#78909c"
        )
        self.lbl_welcome.pack(pady=40)

        # PROZENT & STATUSLEISTE
        self.status_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_container.grid(row=3, column=0, sticky="ew", padx=2)
        self.status_container.grid_columnconfigure(0, weight=1)

        self.status_bar = ctk.CTkLabel(self.status_container, text="Bereit.", anchor="w", font=("Helvetica", 10), text_color="#78909c")
        self.status_bar.grid(row=0, column=0, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.status_container, width=160, height=8, corner_radius=4)
        self.progress_bar.set(0)

        self.btn_index_abbrechen = ctk.CTkButton(
            self.status_container, text="Abbrechen", width=70, height=20, font=("Helvetica", 9),
            fg_color="#c62828", hover_color="#b71c1c", command=self.index_abbrechen
        )

        # KURZWAHLTASTEN
        self.bind("<Down>", self.fokus_nach_unten)
        self.bind("<Up>", self.fokus_nach_oben)
        self.bind("<space>", self.quicklook_fokussiert)
        self.bind("<Escape>", lambda e: self.withdraw())
        self.bind("<Command-k>", lambda e: self.suchfeld.focus_set())

        self.bind("<FocusOut>", self.auf_fokus_verlust)
        self.withdraw()

        self.starte_ordner_überwachung()
        self.aktualisiere_fehler_anzeige()
        self.check_toggle_loop()

        if self.ist_erster_start:
            # Fenster aktiv zeigen (statt versteckt zu bleiben) und kurz
            # danach den Onboarding-Dialog öffnen, damit ein neuer Nutzer
            # nicht vor einem leeren "Bereit für deine Suche."-Fenster
            # steht, ohne zu wissen, dass man erst einen Ordner hinzufügen
            # muss.
            self.zeige_unter_notch()
            self.after(300, self.zeige_onboarding_dialog)

    # ---------- THEME WECHSELN ----------

    def theme_wechseln(self, modus):
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

    def aktivierte_touchpad_scrolling(self, scroll_widget):
        def _on_mousewheel(event):
            if event.delta:
                scroll_widget._parent_canvas.yview_scroll(int(-1 * event.delta), "units")

        scroll_widget.bind_all("<MouseWheel>", _on_mousewheel)

    # ---------- FENSTER / SIGNAL-POLLING ----------

    def check_toggle_loop(self):
        if self.toggle_requested:
            self.toggle_requested = False
            self.toggle_fenster()
        self.after(50, self.check_toggle_loop)

    def zeige_unter_notch(self):
        screen_width = self.winfo_screenwidth()
        fenster_breite = 780
        x = int((screen_width - fenster_breite) / 2)
        y = 38

        self.geometry(f"{fenster_breite}x480+{x}+{y}")
        self.deiconify()

        NSApp.activateIgnoringOtherApps_(True)
        self.lift()
        self.focus_force()
        self.suchfeld.focus_set()

    def toggle_fenster(self):
        if self.winfo_viewable():
            self.withdraw()
        else:
            self.zeige_unter_notch()

    def auf_fokus_verlust(self, event=None):
        if self.focus_get() is None:
            self.withdraw()

    def toggle_sidebar(self):
        if self.sidebar_offen:
            self.sidebar_frame.grid_forget()
            self.sidebar_offen = False
        else:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            self.sidebar_offen = True

    def beenden(self):
        self.indexierung_abbrechen = True
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
        self.setze_status("Neue Datei erkannt - automatischer Index läuft...")
        self.index_aktualisieren()

    def ist_autostart_aktiv(self):
        plist_path = os.path.expanduser("~/Library/LaunchAgents/com.smartsearch.app.plist")
        return os.path.exists(plist_path)

    def autostart_umschalten(self):
        plist_path = os.path.expanduser("~/Library/LaunchAgents/com.smartsearch.app.plist")
        if self.autostart_var.get():
            app_path = os.path.abspath(sys.argv[0])
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartsearch.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>{app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
            try:
                os.makedirs(os.path.dirname(plist_path), exist_ok=True)
                with open(plist_path, "w") as f:
                    f.write(plist_content)
                self.setze_status("Auto-Start aktiviert!")
            except Exception as e:
                self.setze_status(f"Auto-Start Fehler: {e}")
        else:
            if os.path.exists(plist_path):
                os.remove(plist_path)
                self.setze_status("Auto-Start deaktiviert.")

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
                card.configure(border_width=2, border_color="#1f77b4")
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
        self.suchfeld.insert(0, f"Ähnlich zu: {os.path.basename(pfad)}")
        self._suche_button_sperren()
        self.setze_status("Suche nach ähnlichen Dokumenten...")
        threading.Thread(target=self._aehnliche_bg, args=(pfad,), daemon=True).start()

    def _aehnliche_bg(self, pfad):
        try:
            treffer = smart_search.aehnliche_dateien(pfad, top_n=15)
            self.after(0, self._zeige_aehnliche_treffer, treffer)
        except Exception as e:
            self.after(0, lambda: self._suche_fehlgeschlagen(e))

    def _zeige_aehnliche_treffer(self, treffer):
        self._suche_button_entsperren()
        if treffer is None:
            self.setze_status("Für diese Datei liegt kein KI-Vektor vor (evtl. nicht lesbar).")
            self.aktuelle_treffer = []
            self.zeige_aktuelle_ergebnisse()
            return
        self.aktuelle_treffer = treffer
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
        self._datei_im_vordergrund_oeffnen(quicklook_vorschau, pfad)



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

    def ausgeschlossene_typen(self):
        typen = set()
        for label, var in self.filter_variablen.items():
            if var.get():
                typen |= DATEITYP_GRUPPEN[label]
        return typen

    # ---------- FAVORITEN & ORDNER ----------

    def favoriten_anzeigen(self):
        if not self.favoriten:
            self.setze_status("Keine Favoriten vorhanden.")
            self.aktuelle_treffer = []
            self.zeige_aktuelle_ergebnisse()
            return

        eintraege = smart_search.lade_bestehenden_index()
        fav_treffer = [(1.0, e) for e in eintraege if e["datei"] in self.favoriten]
        self.aktuelle_treffer = fav_treffer
        self.zeige_aktuelle_ergebnisse()

    def _favorit_umschalten(self, pfad):
        ist_favorit = smart_search.favorit_umschalten(pfad)
        if ist_favorit:
            self.favoriten.add(pfad)
        else:
            self.favoriten.discard(pfad)
        self.zeige_aktuelle_ergebnisse()

    def ordner_hinzufuegen_gui(self):
        self.attributes("-topmost", False)
        ordner = filedialog.askdirectory(title="Ordner zur Überwachung auswählen", parent=self)
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        if ordner:
            smart_search.befehl_ordner_hinzufuegen(ordner)
            self.setze_status(f"Hinzugefügt: {ordner}")
            self.starte_ordner_überwachung()
            self.index_aktualisieren()

    # ---------- EXPORT / IMPORT DER EINSTELLUNGEN ----------

    # ---------- ONBOARDING (erster Start) ----------

    def zeige_datenschutz_dialog(self):
        """Zeigt eine kurze, klare Erklärung, was mit den Dateien passiert -
        direkt in der App sichtbar statt nur auf einer externen
        Landingpage. Soll Vertrauen schaffen, gerade weil Nutzer hier
        potenziell sensible Dokumente (Ausweise, Rechnungen, Verträge)
        indexieren lassen."""
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title("Datenschutz")
        top.geometry("480x420")
        top.attributes("-topmost", True)
        top.grab_set()

        ctk.CTkLabel(top, text="🔒 Deine Daten bleiben auf deinem Mac", font=("Helvetica", 15, "bold")).pack(
            padx=20, pady=(20, 10), anchor="w"
        )

        punkte = [
            ("📂", "Deine Dokumente", "werden ausschließlich lokal auf diesem Mac gelesen und analysiert. Keine Datei verlässt jemals deinen Rechner."),
            ("🧠", "Die KI-Verarbeitung", "läuft komplett offline auf deinem Mac (BGE-M3-Modell). Keine Textinhalte werden an einen Server oder eine Cloud gesendet."),
            ("💾", "Der Suchindex", "wird als lokale Datei auf deiner Festplatte gespeichert (index.pkl) - nirgendwo sonst."),
            ("⬇️", "Einmaliger Download", "beim ersten Start wird nur das KI-Modell selbst heruntergeladen (kein Dokumenteninhalt), danach funktioniert alles offline."),
        ]

        for icon, titel, text in punkte:
            zeile = ctk.CTkFrame(top, fg_color="transparent")
            zeile.pack(fill="x", padx=20, pady=6, anchor="w")
            ctk.CTkLabel(zeile, text=icon, font=("Helvetica", 16)).pack(side="left", padx=(0, 10), anchor="n")
            text_spalte = ctk.CTkFrame(zeile, fg_color="transparent")
            text_spalte.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text_spalte, text=titel, font=("Helvetica", 12, "bold"), anchor="w", justify="left").pack(fill="x", anchor="w")
            ctk.CTkLabel(
                text_spalte, text=text, font=("Helvetica", 10), text_color="#78909c",
                anchor="w", justify="left", wraplength=360
            ).pack(fill="x", anchor="w")

        ctk.CTkButton(top, text="Verstanden", command=top.destroy).pack(side="bottom", padx=20, pady=20)

    def zeige_onboarding_dialog(self):
        """Geführter Ersteinrichtungs-Dialog beim allerersten Start: lässt
        den Nutzer aus gängigen Standardordnern auswählen oder einen
        eigenen Ordner hinzufügen, statt vor einem leeren Suchfenster zu
        stehen und selbst herausfinden zu müssen, dass man erst einen
        Ordner hinzufügen und indexieren muss."""
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title("Willkommen bei SmartSearch")
        top.geometry("480x420")
        top.attributes("-topmost", True)
        top.grab_set()

        ctk.CTkLabel(
            top, text="👋 Willkommen bei SmartSearch!", font=("Helvetica", 16, "bold")
        ).pack(padx=20, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            top,
            text="Wähle, welche Ordner durchsucht werden sollen.\nDu kannst später jederzeit weitere hinzufügen.",
            font=("Helvetica", 11), text_color="#78909c", justify="left"
        ).pack(padx=20, pady=(0, 16), anchor="w")

        standard_ordner = [
            ("Dokumente", os.path.expanduser("~/Documents")),
            ("Downloads", os.path.expanduser("~/Downloads")),
            ("Schreibtisch", os.path.expanduser("~/Desktop")),
        ]

        checkbox_vars = {}
        for label, pfad in standard_ordner:
            if not os.path.isdir(pfad):
                continue
            var = ctk.BooleanVar(value=(label != "Downloads"))  # Downloads oft sehr groß - standardmäßig aus
            cb = ctk.CTkCheckBox(top, text=f"{label}  ({pfad})", variable=var, font=("Helvetica", 11))
            cb.pack(padx=20, pady=4, anchor="w")
            checkbox_vars[pfad] = var

        eigene_ordner = []
        lbl_eigene = ctk.CTkLabel(top, text="", font=("Helvetica", 10), text_color="#78909c", justify="left")

        def eigenen_ordner_hinzufuegen():
            self.attributes("-topmost", False)
            top.attributes("-topmost", False)
            gewaehlt = filedialog.askdirectory(title="Weiteren Ordner hinzufügen", parent=top)
            top.attributes("-topmost", True)
            top.lift()
            top.focus_force()
            if gewaehlt and gewaehlt not in eigene_ordner:
                eigene_ordner.append(gewaehlt)
                lbl_eigene.configure(text="Zusätzlich:\n" + "\n".join(eigene_ordner))
                lbl_eigene.pack(padx=20, pady=(4, 0), anchor="w")

        ctk.CTkButton(
            top, text="+ Weiteren Ordner wählen...", fg_color="#37474f", hover_color="#263238",
            command=eigenen_ordner_hinzufuegen
        ).pack(padx=20, pady=(12, 0), anchor="w")

        def loslegen():
            gewaehlte_ordner = [pfad for pfad, var in checkbox_vars.items() if var.get()]
            gewaehlte_ordner.extend(eigene_ordner)
            top.destroy()
            if not gewaehlte_ordner:
                self.setze_status("Kein Ordner ausgewählt - du kannst jederzeit über 'Ordner hinzufügen' starten.")
                return
            for ordner in gewaehlte_ordner:
                smart_search.befehl_ordner_hinzufuegen(ordner)
            self.starte_ordner_überwachung()
            self.index_aktualisieren()

        def ueberspringen():
            top.destroy()
            self.setze_status("Übersprungen - füge jederzeit über 'Ordner hinzufügen' einen Ordner hinzu.")

        button_zeile = ctk.CTkFrame(top, fg_color="transparent")
        button_zeile.pack(side="bottom", fill="x", padx=20, pady=20)

        ctk.CTkButton(
            button_zeile, text="Überspringen", fg_color="transparent", hover_color=("#e0e0e0", "#3a3a3a"),
            command=ueberspringen
        ).pack(side="left")

        ctk.CTkButton(
            button_zeile, text="🚀 Loslegen", fg_color="#2e7d32", hover_color="#1b5e20",
            command=loslegen
        ).pack(side="right")

    def einstellungen_exportieren(self):
        self.attributes("-topmost", False)
        pfad = filedialog.asksaveasfilename(
            title="Einstellungen exportieren", defaultextension=".json",
            initialfile="smartsearch_einstellungen.json", parent=self
        )
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        if not pfad:
            return
        try:
            smart_search.exportiere_konfiguration(pfad)
            self.setze_status(f"Einstellungen exportiert: {os.path.basename(pfad)}")
        except Exception as e:
            self.setze_status(f"Export fehlgeschlagen: {e}")

    def einstellungen_importieren(self):
        self.attributes("-topmost", False)
        pfad = filedialog.askopenfilename(
            title="Einstellungen importieren", filetypes=[("JSON-Datei", "*.json")], parent=self
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
            self.setze_status(f"Importiert: {anzahl_ordner} Ordner, {anzahl_fav} Favoriten. Jetzt 'Index aktualisieren' nicht vergessen.")
        except Exception as e:
            self.setze_status(f"Import fehlgeschlagen: {e}")

    def ordner_verwalten_gui(self):
        self.attributes("-topmost", False)
        top = ctk.CTkToplevel(self)
        top.title("Überwachte Ordner")
        top.geometry("520x360")
        top.attributes("-topmost", True)
        top.grab_set()

        lbl = ctk.CTkLabel(top, text="📂 Überwachte Ordner", font=("Helvetica", 14, "bold"))
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        scroll = ctk.CTkScrollableFrame(top, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        def lade_ordner_liste():
            for w in scroll.winfo_children():
                w.destroy()

            config = smart_search.lade_config()
            ordner_liste = config.get("ordner", [])

            if not ordner_liste:
                ctk.CTkLabel(scroll, text="Noch keine Ordner hinzugefügt.", font=("Helvetica", 12), text_color="#78909c").pack(pady=20)
                return

            for o in ordner_liste:
                row = ctk.CTkFrame(scroll, fg_color="transparent")
                row.pack(fill="x", pady=3)

                lbl_p = ctk.CTkLabel(row, text=o, font=("Helvetica", 11), anchor="w")
                lbl_p.pack(side="left", fill="x", expand=True, padx=4)

                def _entfernen_mit_bestaetigung(pfad=o):
                    bestaetigt = messagebox.askyesno(
                        "Ordner entfernen?",
                        f"Soll dieser Ordner nicht mehr durchsucht werden?\n\n{pfad}\n\n"
                        "Bereits indexierte Dateien aus diesem Ordner bleiben bis zur\n"
                        "nächsten Index-Aktualisierung weiter im Suchindex.",
                        parent=top,
                    )
                    if bestaetigt:
                        smart_search.befehl_ordner_entfernen(pfad)
                        lade_ordner_liste()
                        self.starte_ordner_überwachung()

                btn_del = ctk.CTkButton(
                    row, text="Entfernen", width=70, height=24, fg_color="#c62828", hover_color="#b71c1c", font=("Helvetica", 10),
                    command=_entfernen_mit_bestaetigung
                )
                btn_del.pack(side="right", padx=4)

        lade_ordner_liste()

        btn_add = ctk.CTkButton(top, text="+ Ordner hinzufügen", fg_color="#2e7d32", hover_color="#1b5e20", command=lambda: [self.ordner_hinzufuegen_gui(), lade_ordner_liste()])
        btn_add.pack(side="left", padx=15, pady=(0, 15))

        btn_close = ctk.CTkButton(top, text="Schließen", command=top.destroy)
        btn_close.pack(side="right", padx=15, pady=(0, 15))

    # ---------- INDEX MIT ECHTER PROZENT-ANZEIGE ----------

    def index_aktualisieren(self):
        # Verhindert, dass ein manueller Klick und ein Watchdog-Trigger
        # gleichzeitig zwei Indexierungs-Threads starten.
        if not self.indexierung_lock.acquire(blocking=False):
            self.setze_status("Indexierung läuft bereits...")
            return

        config = smart_search.lade_config()
        ordner_liste = config.get("ordner", [])
        if not ordner_liste:
            self.setze_status("Bitte zuerst einen Ordner hinzufügen.")
            self.indexierung_lock.release()
            return

        self.indexierung_laeuft = True
        self.indexierung_abbrechen = False
        self._buttons_sperren()
        self.zeige_fortschritt(0.05, "Starte Indexierung... (du kannst währenddessen schon suchen)")
        self.btn_index_abbrechen.grid(row=0, column=2, sticky="e", padx=4)
        threading.Thread(target=self._index_bg, args=(ordner_liste,), daemon=True).start()

    def index_abbrechen(self):
        self.indexierung_abbrechen = True
        self.setze_status("Breche Indexierung ab...")

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
            modell = smart_search.geladenes_modell()

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
                            text = f"{dateiname} (noch ca. {self._dauer_text(rest_sek)})"
                    self.after(0, lambda t=text: self.zeige_fortschritt(0.95, t))
                    return
                zaehler["n"] += 1
                prozent = min(zaehler["n"] / gesamt, 1.0)
                elapsed = time.time() - start_zeit
                rate = elapsed / zaehler["n"]
                rest_sek = rate * (gesamt - zaehler["n"])
                text = f"Indexiere ({zaehler['n']}/{gesamt}): {dateiname[:25]}... (noch ca. {self._dauer_text(rest_sek)})"
                self.after(0, lambda p=prozent, t=text: self.zeige_fortschritt(p, t))

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

            if abgebrochen:
                self.after(0, self._index_abgebrochen)
            else:
                self.after(0, self._index_fertig)
        except Exception as e:
            self.after(0, lambda: self._index_fehlgeschlagen(e))
        finally:
            self.indexierung_laeuft = False
            self.indexierung_lock.release()

    def _index_fertig(self):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status("Index erfolgreich aktualisiert! ✅")
        send_macos_notification("SmartSearch", "Indexierung erfolgreich abgeschlossen! ✅")
        self.aktualisiere_fehler_anzeige()

    def _index_abgebrochen(self):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status("Indexierung abgebrochen.")
        self.aktualisiere_fehler_anzeige()

    # ---------- FEHLERSICHTBARKEIT (nicht lesbare Dateien) ----------

    def aktualisiere_fehler_anzeige(self):
        """Blendet den Warnbutton ein/aus, je nachdem ob es Dateien gibt,
        die beim Indexieren nicht gelesen werden konnten. Vorher landeten
        solche Fehler nur im Terminal und wurden z.B. bei laufendem
        Autostart im Hintergrund nie bemerkt."""
        anzahl = len(smart_search.fehlgeschlagene_dateien())
        if anzahl > 0:
            self.btn_fehler_anzeigen.configure(text=f"⚠️ {anzahl} Datei(en) nicht lesbar")
            self.btn_fehler_anzeigen.pack(padx=12, pady=(0, 3), fill="x", after=self.index_button)
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
        top.title("Nicht lesbare Dateien")
        top.geometry("560x400")
        top.attributes("-topmost", True)
        top.grab_set()

        lbl = ctk.CTkLabel(
            top, text=f"⚠️ {len(dateien)} Datei(en) konnten nicht gelesen werden",
            font=("Helvetica", 14, "bold")
        )
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        hinweis = ctk.CTkLabel(
            top,
            text="Häufige Ursachen: beschädigte/leere PDFs, abgebrochene Downloads,\noder OCR war zum Zeitpunkt der Indexierung noch nicht installiert.",
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
            self.setze_status(f"{entfernt} Datei(en) werden beim nächsten 'Index aktualisieren' erneut versucht.")
            self.aktualisiere_fehler_anzeige()

        btn_retry = ctk.CTkButton(
            top, text="🔄 Alle erneut versuchen (beim nächsten Indexieren)",
            fg_color="#2e7d32", hover_color="#1b5e20", command=neuversuch
        )
        btn_retry.pack(side="left", padx=15, pady=(0, 15))

        btn_close = ctk.CTkButton(top, text="Schließen", command=top.destroy)
        btn_close.pack(side="right", padx=15, pady=(0, 15))

    def _index_fehlgeschlagen(self, fehler):
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        self.setze_status(f"Fehler bei Indexierung: {fehler}")
        self.aktualisiere_fehler_anzeige()

    # ---------- SUCHE ----------

    def suchen(self):
        anfrage = self.suchfeld.get().strip()
        if not anfrage or anfrage == PLATZHALTER_TEXT:
            return

        self.verlauf_aktualisieren(anfrage)
        self._suche_button_sperren()
        self.setze_status("Suche läuft...")
        ausschluss = self.ausgeschlossene_typen()
        zeitraum = self.zeitraum_menu.get()

        threading.Thread(target=self._suche_bg, args=(anfrage, ausschluss, zeitraum), daemon=True).start()

    def _suche_bg(self, anfrage, ausschluss, zeitraum):
        try:
            treffer = smart_search.suche_intern(anfrage, top_n=15, ausgeschlossene_typen=ausschluss, zeitraum=zeitraum)
            self.after(0, self._zeige_treffer, treffer, anfrage)
        except Exception as e:
            self.after(0, lambda: self._suche_fehlgeschlagen(e))

    def _suche_fehlgeschlagen(self, fehler):
        self._suche_button_entsperren()
        self.setze_status(f"Fehler bei Suche: {fehler}")

    def _zeige_treffer(self, treffer, anfrage):
        self._suche_button_entsperren()
        if treffer is None:
            self.setze_status("Kein Index vorhanden. Bitte zuerst Index aktualisieren.")
            self.aktuelle_treffer = []
            self.zeige_aktuelle_ergebnisse()
            return
        self.aktuelle_treffer = treffer
        self.zeige_aktuelle_ergebnisse()

    def _null_treffer_hinweis(self, anfrage):
        """Ermittelt eine hilfreiche, konkrete Erklärung dafür, warum eine
        Suche 0 Treffer ergeben hat - statt nur "Keine Treffer gefunden.",
        das dem Nutzer keinen Ansatzpunkt gibt, was er ändern könnte."""
        ordner_liste = smart_search.lade_config().get("ordner", [])
        if not ordner_liste:
            return "📁 Noch kein Ordner hinzugefügt.\n\nKlicke auf 'Ordner hinzufügen' in der Seitenleiste, um loszulegen."

        aktive_filter = self.ausgeschlossene_typen()
        if aktive_filter:
            return (
                f"🔍 Keine Treffer für „{anfrage}“ mit den aktuellen Filtern.\n\n"
                "Versuch, oben ein paar Dateityp-Filter (PDF, Word, ...) zu deaktivieren -\n"
                "vielleicht ist die passende Datei von einem ausgeschlossenen Typ."
            )

        if not os.path.exists(smart_search.INDEX_FILE):
            return "⏳ Es wurde noch nie indexiert.\n\nKlicke auf 'Index aktualisieren', bevor du suchst."

        return (
            f"🔍 Keine Treffer für „{anfrage}“.\n\n"
            "Mögliche Gründe: Die Datei liegt in keinem überwachten Ordner,\n"
            "wurde noch nicht indexiert, oder ein anderer Suchbegriff passt besser."
        )

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
            self.setze_status("Keine Treffer.")
            return

        for score, eintrag in self.aktuelle_treffer:
            pfad = eintrag["datei"]
            name = os.path.basename(pfad)
            ext = os.path.splitext(name)[1].lower()
            bg_col, fg_col = BADGE_FARBEN.get(ext, ("#37474f", "#ffffff"))

            card = ctk.CTkFrame(self.cards_scrollframe, corner_radius=8)
            card.pack(fill="x", padx=2, pady=3)

            # Obere Zeile: Badge, Dateiname, Aktions-Buttons
            zeile_oben = ctk.CTkFrame(card, fg_color="transparent")
            zeile_oben.pack(fill="x", padx=0, pady=(6, 0))

            lbl_badge = ctk.CTkLabel(zeile_oben, text=f" {ext.replace('.','').upper()} ", font=("Helvetica", 9, "bold"), fg_color=bg_col, text_color=fg_col, corner_radius=4)
            lbl_badge.pack(side="left", padx=8, pady=8)

            lbl_titel = ctk.CTkLabel(zeile_oben, text=f"[{score:.2f}] {name}", font=("Helvetica", 11, "bold"), text_color="#1f77b4")
            lbl_titel.pack(side="left", padx=4)

            btn_sim = ctk.CTkButton(zeile_oben, text="🔗 Ähnliche", width=65, height=20, font=("Helvetica", 9), fg_color="#37474f", command=lambda p=pfad: self.aehnliche_suchen(p))
            btn_sim.pack(side="right", padx=2)

            btn_ql = ctk.CTkButton(zeile_oben, text="👁 Vorschau", width=65, height=20, font=("Helvetica", 9), fg_color="#37474f", command=lambda p=pfad: self.quicklook_im_vordergrund(p))
            btn_ql.pack(side="right", padx=2)

            btn_open = ctk.CTkButton(zeile_oben, text="Öffnen", width=50, height=20, font=("Helvetica", 9), command=lambda p=pfad: self.datei_oeffnen_im_vordergrund(p))
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
            ausschnitt = (eintrag.get("text") or "").strip().replace("\n", " ")
            if ausschnitt:
                if len(ausschnitt) > 180:
                    ausschnitt = ausschnitt[:180].rsplit(" ", 1)[0] + "..."
                lbl_ausschnitt = ctk.CTkLabel(
                    card, text=f"„{ausschnitt}“", font=("Helvetica", 10), text_color="#90a4ae",
                    anchor="w", justify="left", wraplength=680
                )
                lbl_ausschnitt.pack(fill="x", padx=12, pady=(2, 8), anchor="w")
            else:
                # Kein Textausschnitt vorhanden (z.B. bei Favoriten-Ansicht,
                # wo teils nur Metadaten ohne Chunk-Text vorliegen).
                ctk.CTkFrame(card, height=6, fg_color="transparent").pack(fill="x")

            self.card_widgets.append((card, pfad))

        self.setze_status(f"{len(self.aktuelle_treffer)} Treffer geladen.")


# ================= MACOS STATUSLEISTEN-ICON =================
class MacStatusBarHandler(NSObject):
    def initWithWindow_(self, app_window):
        self = objc.super(MacStatusBarHandler, self).init()
        if self:
            self.app_window = app_window
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)

            button = self.status_item.button()
            button.setTitle_("🔍")
            button.setTarget_(self)
            button.setAction_("onClick:")
        return self

    def onClick_(self, sender):
        self.app_window.toggle_requested = True


if __name__ == "__main__":
    app_window = SmartSearchNotchWindow()
    status_handler = MacStatusBarHandler.alloc().initWithWindow_(app_window)

    NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    app_window.mainloop()