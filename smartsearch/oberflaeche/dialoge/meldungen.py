#!/usr/bin/env python3
"""dialoge/meldungen.py - kleinere Hinweisfenster: neue Fassung verfuegbar,
Suchmodell konnte nicht geladen werden, Programmteil fehlt."""

import webbrowser

import customtkinter as ctk

from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t
from smartsearch import version


def update_verfuegbar(app, neue_version, download_url, notizen):
    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("update.available_title"))
    # Ohne Änderungstext reichen 260 Pixel; mit einem längeren würden
    # die Knöpfe sonst aus dem Fenster geschoben.
    top.geometry("400x340" if len(notizen or "") > 160 else "400x260")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
    top.grab_set()

    ctk.CTkLabel(
        top, text=t("update.available_heading", version=neue_version), font=("Helvetica", 14, "bold")
    ).pack(padx=20, pady=(20, 4), anchor="w")
    ctk.CTkLabel(
        top, text=t("update.available_current", version=version.APP_VERSION), font=("Helvetica", 11), text_color="#78909c"
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


def modell_download_fehlgeschlagen(app, fehler):
    """Erklaert den einen Fall, der einen neuen Nutzer sonst ratlos
    zuruecklaesst: die App wurde gerade installiert, das KI-Modell fehlt
    noch, und es ist kein Internet da."""
    app._buttons_entsperren()
    app.verstecke_fortschritt()
    app.setze_status(t("model.download_failed_status"))

    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("model.download_failed_title"))
    top.geometry("460x260")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)

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
        app.index_aktualisieren()

    ctk.CTkButton(
        zeile, text=t("model.download_failed_retry"), fg_color=farben.SEITE_KNOPF,
        hover_color=farben.SEITE_KNOPF_HOVER, command=erneut_versuchen
    ).pack(side="right")


def programm_unvollstaendig(app, fehler):
    """Der Gegenfall zum Download-Dialog: hier fehlt kein Modell,
    sondern ein Programmteil. Kein "Erneut versuchen" - das würde nur
    denselben Fehler ein zweites Mal zeigen."""
    app._buttons_entsperren()
    app.verstecke_fortschritt()
    app.setze_status(t("model.incomplete_status"))

    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("model.incomplete_title"))
    top.geometry("460x300")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)

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
        app.oeffne_rueckmeldung(vorbelegung=str(fehler))

    ctk.CTkButton(
        zeile, text=t("model.incomplete_report"), fg_color=farben.SEITE_KNOPF,
        hover_color=farben.SEITE_KNOPF_HOVER, command=melden
    ).pack(side="right")
