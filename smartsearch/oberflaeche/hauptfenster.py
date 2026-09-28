#!/usr/bin/env python3
"""
hauptfenster.py - das Suchfenster: Suchfeld, Filter, Trefferliste,
Seitenleiste und Statuszeile.

Was hier NICHT mehr steht (bis Herbst 2026 lag alles in gui.py):
  - Suche, Index, Modell, Einstellungen, Updates, Ordnerueberwachung
    -> smartsearch/kern/   (laeuft ohne Oberflaeche und wird beim Umstieg
                            auf eine neue Oberflaeche nicht angefasst)
  - Einstellungen, Einfuehrung, Ordnerliste, Fehlerliste, Hinweisfenster
    -> oberflaeche/dialoge/
  - eine Karte in der Trefferliste -> oberflaeche/trefferkarte.py
  - alles, was Mac und Windows verschieden machen -> smartsearch/plattform/
  - Programmstart, "nur eine Kopie" -> smartsearch/start.py

Faustregel fuer diese Datei: sie ZEIGT an und reagiert auf Klicks. Sobald
eine Methode etwas ausrechnet, liest oder speichert, gehoert das in den
Kern.
"""

import os
import sys
import threading
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from smartsearch import plattform, version
from smartsearch.kern import (einstellungen, einzelinstanz, index, indexierung,
                              modell, ocr, sprache, suche, updates)
from smartsearch.kern import ordner as ordner_verwaltung
from smartsearch.kern import rueckmeldung
from smartsearch.kern.pfade import INDEX_FILE
from smartsearch.kern.ueberwachung import Ordnerwaechter
from smartsearch.oberflaeche import farben, i18n, trefferkarte
from smartsearch.oberflaeche.dialoge import einfuehrung, fehlerliste, meldungen
from smartsearch.oberflaeche.dialoge import einstellungen as einstellungen_dialog
from smartsearch.oberflaeche.dialoge import ordner as ordner_dialog
from smartsearch.oberflaeche.i18n import t

ctk.set_appearance_mode("System")
# "blue" laedt das vollstaendige Standardthema - farben.thema_anwenden
# ersetzt danach nur die Farbwerte durch die Markenfarben. Das muss vor
# dem ersten Widget passieren, weil CustomTkinter die Werte beim
# Erzeugen liest.
ctk.set_default_color_theme("blue")
farben.thema_anwenden(ctk)

PLATZHALTER_TEXT = t("search.placeholder")

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

DATEITYP_GRUPPEN = {
    "PDF": {".pdf"},
    "Word": {".docx"},
    "Excel": {".xlsx"},
    "PowerPoint": {".pptx"},
    "Text": {".txt", ".md"},
}


def dauer_text(sekunden):
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


class Hauptfenster(ctk.CTk):
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

        self.verlauf = einstellungen.lade_verlauf()
        self.aktuelle_treffer = []
        self.favoriten = einstellungen.lade_favoriten()
        self.sidebar_offen = False

        # Erster Start = noch kein einziger überwachter Ordner konfiguriert.
        # Wird am Ende von __init__ genutzt, um automatisch den
        # Onboarding-Dialog zu zeigen, statt den Nutzer vor einem leeren
        # "Bereit für deine Suche."-Fenster stehen zu lassen, ohne dass
        # klar ist, dass man erst einen Ordner hinzufügen muss.
        self.ist_erster_start = not einstellungen.lade_config().get("ordner")

        self.fokussierter_index = -1
        self.card_widgets = []
        # Ordnerueberwachung (watchdog) - siehe kern/ueberwachung.py
        self.waechter = Ordnerwaechter(bei_aenderung=self.automatische_reindexierung)

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
        # (siehe kern/indexierung.py) kann während einer laufenden Indexierung schon
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
        # den suche._zeitraum_cutoff() (kern/suche.py) versteht. Nötig, weil sich der
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
        müssen: i18n.setze_sprache() stellt sofort um und speichert die
        Auswahl dauerhaft, dann wird
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

        Fehler werden hier absichtlich nur protokolliert. Geht etwas
        schief, faellt es bei der echten Suche ohnehin wieder auf - dort
        mit einer Erklaerung fuer den Nutzer.
        """
        def _laden():
            try:
                if modell.modell_ist_vorhanden():
                    modell.geladenes_modell()
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
        if not plattform.SYMBOL_VERFUEGBAR:
            return
        try:
            aktiv = plattform.app_ist_aktiv()
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
        Kopie ein Signal ab und beendet sich sofort wieder (siehe
        kern/einzelinstanz.py). Diese - die laufende - Kopie holt daraufhin
        ihr Fenster nach vorne. Ergebnis: ein Doppelklick auf die App fuehrt
        IMMER zum sichtbaren Fenster, egal ob sie schon laeuft, und nie zu
        einer zweiten Instanz."""
        if einzelinstanz.zeigen_signal_abholen():
            self.zeige_unter_notch()

    def registriere_globalen_hotkey(self):
        """Cmd+Shift+F oeffnet SmartSearch von UEBERALL aus, auch wenn eine
        andere App im Vordergrund ist - genau der "schnell aufploppen"-
        Charakter, den ein Suchwerkzeug braucht.

        Die eigentliche Registrierung ist Systemsache und steht deshalb in
        plattform/mac.py bzw. windows.py. Hier wird nur festgelegt, WAS passieren soll:
        dasselbe wie beim Klick auf das Menueleisten-Symbol - ein Flag
        setzen, das check_toggle_loop() alle 50 ms im Tk-Hauptthread
        abfragt. Wichtig, weil der Tastatur-Handler auf Apples Event-Loop
        laeuft und Tkinter-Widgets von dort nicht angefasst werden duerfen.
        """
        if not plattform.SYMBOL_VERFUEGBAR:
            return

        def _ausloesen():
            self.toggle_requested = True

        self._hotkey_monitor = plattform.registriere_globalen_hotkey(_ausloesen)

    def zeige_unter_notch(self):
        screen_width = self.winfo_screenwidth()
        fenster_breite = FENSTER_BREITE_OFFEN if self.sidebar_offen else FENSTER_BREITE_ZU
        x = int((screen_width - fenster_breite) / 2)
        y = 38

        self.geometry(f"{fenster_breite}x{FENSTER_HOEHE}+{x}+{y}")
        self.deiconify()

        if plattform.SYMBOL_VERFUEGBAR:
            plattform.fenster_nach_vorne()
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
        if not plattform.SYMBOL_VERFUEGBAR:
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
        if plattform.SYMBOL_VERFUEGBAR:
            plattform.aus_dem_dock_nehmen()
        # Sperrdatei selbst aufraeumen: weiter unten steht os._exit(0), und
        # das geht an atexit vorbei (siehe kern/einzelinstanz.py).
        einzelinstanz.aufraeumen()
        self.waechter.stoppen()
        self.destroy()
        os._exit(0)

    # ---------- WATCHDOG & AUTOSTART ----------

    def starte_ordner_überwachung(self):
        """Ueberwachung (neu) starten - nach jeder Aenderung an der
        Ordnerliste aufrufen. Die Arbeit macht kern/ueberwachung.py."""
        self.waechter.neu_starten()

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
        plattform/mac.py bzw. windows.py."""
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
            treffer = suche.aehnliche_dateien(pfad, top_n=15)
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
        self._datei_im_vordergrund_oeffnen(plattform.datei_oeffnen, pfad)

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

    def verlauf_aktualisieren(self, anfrage):
        if not anfrage or anfrage == PLATZHALTER_TEXT:
            return
        self.verlauf = einstellungen.verlauf_ergaenzen(self.verlauf, anfrage)

    def setze_status(self, text):
        self.status_bar.configure(text=text)
        self.update_idletasks()

    def _dauer_text(self, sekunden):
        """Formatiert eine Sekundenzahl als kurze, lesbare Restzeit-Angabe
        für die Fortschrittsanzeige bei der Indexierung."""
        return dauer_text(sekunden)

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
        eintraege = index.lade_bestehenden_index()
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
        ist_favorit = einstellungen.favorit_umschalten(pfad)
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
            ordner_verwaltung.befehl_ordner_hinzufuegen(ordner)
            self.setze_status(t("folders.status_added", ordner=ordner))
            self.starte_ordner_überwachung()
            self.index_aktualisieren()

    # ---------- EXPORT / IMPORT DER EINSTELLUNGEN ----------

    # ---------- ONBOARDING (erster Start) ----------

    # ---------- Bitte um Rueckmeldung ----------
    # Wann gefragt wird und was in der E-Mail steht: kern/rueckmeldung.py.

    def _rueckmeldung_zaehlen(self):
        """Wird nach jeder erfolgreichen Suche aufgerufen."""
        if rueckmeldung.suche_zaehlen(self._rueckmeldung_sichtbar):
            self._rueckmeldung_sichtbar = True
            self.rueckmeldung_leiste.grid(row=3, column=0, sticky="ew",
                                          padx=2, pady=(8, 0))

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
        rueckmeldung.spaeter()
        self._rueckmeldung_verbergen()

    def oeffne_rueckmeldung(self, vorbelegung=""):
        """Oeffnet eine vorbereitete E-Mail im Standard-Mailprogramm.

        vorbelegung: Fehlermeldung, die aus einem Fehlerdialog heraus
        mitgeschickt wird. Sonst muesste der Nutzer sie abtippen.
        """
        link = rueckmeldung.mail_link(
            vorbelegung,
            texterkennung=ocr.verfuegbare_engine() or "keine",
            sprache=i18n.aktuelle_sprache(),
            system=plattform.system_beschreibung(),
        )
        try:
            webbrowser.open(link)
        except Exception:
            self.setze_status(t("help.feedback_failed", adresse=rueckmeldung.RUECKMELDUNG_ADRESSE))

    # ---------- DIALOGE (je einer in oberflaeche/dialoge/) ----------

    def oeffne_einstellungen_fenster(self):
        einstellungen_dialog.oeffnen(self)

    def zeige_setup_guide(self, mit_ordnerauswahl=True):
        einfuehrung.zeigen(self, mit_ordnerauswahl)

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
        Netzwerk die Oberfläche nicht blockiert. Die Abfrage selbst steht
        in kern/updates.py.
        """
        def _hintergrund():
            try:
                neueste_version, notizen = updates.neueste_fassung_abfragen()
            except Exception as e:
                if manuell:
                    self.after(0, lambda e=e: self._update_fehlgeschlagen(e))
                return

            if updates.ist_neuer(neueste_version):
                self.after(0, lambda: meldungen.update_verfuegbar(
                    self, neueste_version, updates.DOWNLOAD_ADRESSE, notizen))
            elif manuell:
                self.after(0, self._update_aktuell)

        threading.Thread(target=_hintergrund, daemon=True).start()

    def pruefe_index_passt(self):
        """Prüft beim Start, ob der gespeicherte Index zum aktuellen
        Suchmodell gehört - und stößt sonst den Neuaufbau an.

        Hintergrund: Die Vektoren im Index stammen aus einem bestimmten
        Modell (siehe kern/modell.py und INDEX_FORMAT in kern/index.py).
        Wechselt das Modell, wird der alte Index beim Laden verworfen. Ohne
        diesen Hinweis stünde der Benutzer dann vor einer Suche, die
        grundlos nichts findet.

        Läuft im Hintergrund, weil dafür die Indexdatei gelesen wird - bei
        einem großen Index dauert das einen Moment, und der Programmstart
        soll nicht darauf warten.
        """
        def _hintergrund():
            try:
                fremd = index.index_ist_fremd()
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
        messagebox.showinfo(t("update.up_to_date_title"), t("update.up_to_date_body", version=version.APP_VERSION))

    def ordner_verwalten_gui(self):
        ordner_dialog.verwalten(self)

    # ---------- INDEX MIT ECHTER PROZENT-ANZEIGE ----------

    def index_aktualisieren(self):
        # Verhindert, dass ein manueller Klick und ein Watchdog-Trigger
        # gleichzeitig zwei Indexierungs-Threads starten.
        if not self.indexierung_lock.acquire(blocking=False):
            self.setze_status(t("index.status_already_running"))
            return

        config = einstellungen.lade_config()
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
        """Laeuft im Hintergrund-Thread. Die eigentliche Arbeit macht
        kern/indexierung.alles_indexieren(); hier wird nur angezeigt, was
        es meldet. Jede Aenderung an Fenstern geht ueber self.after(0, ...)
        in den Hauptthread - Tk darf nur von dort angefasst werden."""
        def melden(ereignis):
            art = ereignis["art"]
            if art == "datei":
                anteil = ereignis["anteil"]
                text = t("index.progress_indexing", n=ereignis["n"], gesamt=ereignis["gesamt"],
                         name=ereignis["name"][:25], zeit=dauer_text(ereignis["restzeit_sek"]))
            elif art == "vektoren":
                # Balken bleibt bei ~95 %, damit sichtbar ist, dass noch
                # etwas laeuft, ohne die Dateizaehlung zu verfaelschen.
                anteil = 0.95
                text = t("index.progress_vectors", batch=ereignis["batch"], batches=ereignis["batches"])
                if ereignis["restzeit_sek"] is not None:
                    text = t("index.progress_calculating", text=text, zeit=dauer_text(ereignis["restzeit_sek"]))
            else:
                return
            self.after(0, lambda a=anteil, txt=text: self.zeige_fortschritt(a, txt))

        try:
            vollstaendig = indexierung.alles_indexieren(
                ordner_liste,
                soll_abbrechen=lambda: self.indexierung_abbrechen,
                melden=melden,
            )
            self.after(0, self._index_fertig if vollstaendig else self._index_abgebrochen)
        except modell.ProgrammUnvollstaendig as e:
            # Modelldateien oder eine Bibliothek fehlen in der App - dafuer
            # gibt es einen eigenen Dialog statt einer rohen Fehlermeldung.
            self.after(0, lambda e=e: self._index_dialog_fehler(meldungen.programm_unvollstaendig, e))
        except Exception as e:
            self.after(0, lambda e=e: self._index_fehlgeschlagen(e))
        finally:
            self.indexierung_laeuft = False
            self.indexierung_lock.release()

    def _index_dialog_fehler(self, dialog, fehler):
        """Modell-Fehler zeigen einen eigenen Dialog (dialoge/meldungen.py).
        Vorher Knoepfe freigeben und Fortschritt ausblenden."""
        self._buttons_entsperren()
        self.verstecke_fortschritt()
        dialog(self, fehler)

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
        anzahl = len(index.fehlgeschlagene_dateien())
        if anzahl > 0:
            self.btn_fehler_anzeigen.configure(text=t("sidebar.errors_button", anzahl=anzahl))
            # Direkt unter "Index aktualisieren" einsortiert (after=
            # index_button bestimmt die Stapel-Position) - noch über dem
            # "⚙ Einstellungen..."-Link.
            self.btn_fehler_anzeigen.pack(padx=12, pady=(3, 3), fill="x", after=self.index_button)
        else:
            self.btn_fehler_anzeigen.pack_forget()

    def fehlgeschlagene_dateien_dialog(self):
        fehlerliste.zeigen(self)

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
            treffer = suche.suche_intern(anfrage, top_n=15, ausgeschlossene_typen=ausschluss, zeitraum=zeitraum)
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
        self.aktuelle_such_woerter = sprache.anfrage_woerter(anfrage)
        self.zeige_aktuelle_ergebnisse()
        if treffer:
            self._rueckmeldung_zaehlen()

    def _null_treffer_hinweis(self, anfrage):
        """Ermittelt eine hilfreiche, konkrete Erklärung dafür, warum eine
        Suche 0 Treffer ergeben hat - statt nur "Keine Treffer gefunden.",
        das dem Nutzer keinen Ansatzpunkt gibt, was er ändern könnte."""
        ordner_liste = einstellungen.lade_config().get("ordner", [])
        if not ordner_liste:
            return t("results.none_no_folder")

        aktive_filter = self.ausgeschlossene_typen()
        if aktive_filter:
            return t("results.none_filtered", anfrage=anfrage)

        if not os.path.exists(INDEX_FILE):
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
            # Aufbau einer Karte: oberflaeche/trefferkarte.py
            card = trefferkarte.karte_zeichnen(
                self, self.cards_scrollframe, score, eintrag, self.aktuelle_such_woerter)
            self.card_widgets.append((card, eintrag["datei"]))

        self.setze_status(t("search.status_results_loaded", anzahl=len(self.aktuelle_treffer)))
