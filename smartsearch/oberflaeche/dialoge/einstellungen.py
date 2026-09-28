#!/usr/bin/env python3
"""
dialoge/einstellungen.py - das Einstellungsfenster mit seinen Reitern
(Allgemein, Hilfe, Sicherung, Datenschutz).
"""

import os
from tkinter import filedialog

import customtkinter as ctk

from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t
from smartsearch import version
from smartsearch.kern import einstellungen, ocr
from smartsearch.oberflaeche import i18n


def oeffnen(app):
    """Separates Preferences-Fenster - sammelt die selten gebrauchten
    Einstellungen in Reitern. Erscheinungsbild, Ordner verwalten und
    die Fehleranzeige bleiben bewusst NUR im Schnellzugriff (keine
    doppelten Buttons an zwei Stellen). Wird beim erneuten Aufruf nur
    nach vorne geholt statt dupliziert, wie man es von echten
    macOS-Apps kennt (Cmd+,)."""
    if app.einstellungen_fenster is not None and app.einstellungen_fenster.winfo_exists():
        app.einstellungen_fenster.deiconify()
        app.einstellungen_fenster.lift()
        app.einstellungen_fenster.focus_force()
        return

    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("settings.window_title"))
    top.geometry("480x420")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
    top.protocol("WM_DELETE_WINDOW", top.destroy)
    app.einstellungen_fenster = top

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
    app.autostart_var.set(app.ist_autostart_aktiv())
    ctk.CTkCheckBox(
        tab_allgemein, text=t("settings.autostart_checkbox"), variable=app.autostart_var,
        command=app.autostart_umschalten
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
            app.wende_sprache_live_an(code)

    sprache_seg = ctk.CTkSegmentedButton(
        tab_allgemein, values=list(sprache_werte.keys()), command=sprache_gewaehlt, font=("Helvetica", 10)
    )
    sprache_seg.set(sprache_umkehr.get(i18n.aktuelle_sprache(), "Deutsch"))
    sprache_seg.pack(padx=4, pady=(0, 12), fill="x")

    ctk.CTkLabel(
        tab_allgemein, text=t("settings.version_label", version=version.APP_VERSION), font=("Helvetica", 11), text_color="#78909c"
    ).pack(padx=4, pady=(20, 4), anchor="w")
    ctk.CTkButton(
        tab_allgemein, text=t("settings.check_updates_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
        anchor="w", command=lambda: app.pruefe_auf_updates(manuell=True)
    ).pack(padx=4, pady=4, fill="x")

    # ---- Hilfe ----
    _hilfe_tab(app, tab_hilfe)

    # ---- Backup: Export / Import ----
    ctk.CTkLabel(
        tab_backup,
        text=t("backup.description"),
        font=("Helvetica", 11), text_color="#78909c", justify="left"
    ).pack(padx=4, pady=(12, 12), anchor="w")
    ctk.CTkButton(
        tab_backup, text=t("backup.export_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
        anchor="w", command=lambda: exportieren(app)
    ).pack(padx=4, pady=4, fill="x")
    ctk.CTkButton(
        tab_backup, text=t("backup.import_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER,
        anchor="w", command=lambda: importieren(app)
    ).pack(padx=4, pady=4, fill="x")

    # ---- Datenschutz ----
    datenschutz_scroll = ctk.CTkScrollableFrame(tab_datenschutz, fg_color="transparent")
    datenschutz_scroll.pack(fill="both", expand=True)
    _datenschutz_inhalt(datenschutz_scroll)


def _hilfe_tab(app, parent):
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
        anchor="w", command=lambda: _einfuehrung_oeffnen(app)
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
        hover_color=farben.SEITE_KNOPF_HOVER, anchor="w", command=app.oeffne_rueckmeldung
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


def _einfuehrung_oeffnen(app):
    """Schliesst das Preferences-Fenster, bevor der Guide aufgeht -
    sonst liegen zwei topmost-Fenster uebereinander und der Guide
    (der grab_set() nutzt) wirkt eingefroren."""
    if app.einstellungen_fenster is not None:
        try:
            app.einstellungen_fenster.destroy()
        except Exception:
            pass
        app.einstellungen_fenster = None
    app.after(120, lambda: app.zeige_setup_guide(mit_ordnerauswahl=False))


def _datenschutz_inhalt(parent):
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


def exportieren(app):
    app.attributes("-topmost", False)
    pfad = filedialog.asksaveasfilename(
        title=t("backup.export_title"), defaultextension=".json",
        initialfile="smartsearch_einstellungen.json", parent=app
    )
    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()

    if not pfad:
        return
    try:
        einstellungen.exportiere_konfiguration(pfad)
        app.setze_status(t("backup.export_status", name=os.path.basename(pfad)))
    except Exception as e:
        app.setze_status(t("backup.export_error", fehler=e))


def importieren(app):
    app.attributes("-topmost", False)
    pfad = filedialog.askopenfilename(
        title=t("backup.import_title"), filetypes=[(t("backup.import_filetype"), "*.json")], parent=app
    )
    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()

    if not pfad:
        return
    try:
        anzahl_ordner, anzahl_fav = einstellungen.importiere_konfiguration(pfad)
        app.favoriten = einstellungen.lade_favoriten()
        app.starte_ordner_überwachung()
        app.setze_status(t("backup.import_status", ordner=anzahl_ordner, favoriten=anzahl_fav))
    except Exception as e:
        app.setze_status(t("backup.import_error", fehler=e))
