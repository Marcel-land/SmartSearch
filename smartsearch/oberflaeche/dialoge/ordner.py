#!/usr/bin/env python3
"""dialoge/ordner.py - "Ordner verwalten": Liste der ueberwachten Ordner,
entfernen mit Rueckfrage, neuen hinzufuegen."""

from tkinter import messagebox

import customtkinter as ctk

from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t
from smartsearch.kern import einstellungen, ordner


def verwalten(app):
    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("folders.dialog_title"))
    top.geometry("520x360")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
    top.grab_set()

    lbl = ctk.CTkLabel(top, text=t("folders.heading"), font=("Helvetica", 14, "bold"))
    lbl.pack(padx=15, pady=(15, 5), anchor="w")

    scroll = ctk.CTkScrollableFrame(top, corner_radius=8)
    scroll.pack(fill="both", expand=True, padx=15, pady=10)

    def lade_ordner_liste():
        for w in scroll.winfo_children():
            w.destroy()

        config = einstellungen.lade_config()
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
                    ordner.befehl_ordner_entfernen(pfad)
                    lade_ordner_liste()
                    app.starte_ordner_überwachung()

            btn_del = ctk.CTkButton(
                row, text=t("folders.remove_button"), width=70, height=24, fg_color=farben.WARNUNG, hover_color=farben.WARNUNG_HOVER, font=("Helvetica", 10),
                command=_entfernen_mit_bestaetigung
            )
            btn_del.pack(side="right", padx=4)

    lade_ordner_liste()

    btn_add = ctk.CTkButton(top, text=t("folders.add_button"), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda: [app.ordner_hinzufuegen_gui(), lade_ordner_liste()])
    btn_add.pack(side="left", padx=15, pady=(0, 15))

    btn_close = ctk.CTkButton(top, text=t("folders.close_button"), command=top.destroy)
    btn_close.pack(side="right", padx=15, pady=(0, 15))
