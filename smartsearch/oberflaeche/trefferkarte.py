#!/usr/bin/env python3
"""
trefferkarte.py - eine Karte in der Ergebnisliste: Dateityp, Name, Knoepfe
(Favorit, Oeffnen, Finder, Vorschau, Aehnliche) und ein Textausschnitt mit
eingefaerbten Fundstellen.

Die Knoepfe rufen Methoden des Hauptfensters auf (app.*) - die Karte selbst
weiss nicht, wie man eine Datei oeffnet oder sucht.
"""

import os

import customtkinter as ctk

from smartsearch.kern.sprache import ausschnitt_mit_fundstellen
from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t


def karte_zeichnen(app, eltern, score, eintrag, such_woerter):
    """Zeichnet die Karte fuer einen Treffer in 'eltern' und gibt den
    Rahmen der Karte zurueck (fuer die Pfeiltasten-Hervorhebung)."""
    pfad = eintrag["datei"]
    name = os.path.basename(pfad)
    ext = os.path.splitext(name)[1].lower()
    bg_col, fg_col = farben.BADGE_FARBEN.get(ext, farben.BADGE_RUECKFALL)

    card = ctk.CTkFrame(eltern, corner_radius=8)
    card.pack(fill="x", padx=2, pady=3)

    # Obere Zeile: Badge, Dateiname, Aktions-Buttons
    zeile_oben = ctk.CTkFrame(card, fg_color="transparent")
    zeile_oben.pack(fill="x", padx=0, pady=(6, 0))

    lbl_badge = ctk.CTkLabel(zeile_oben, text=f" {ext.replace('.','').upper()} ", font=("Helvetica", 9, "bold"), fg_color=bg_col, text_color=fg_col, corner_radius=4)
    lbl_badge.pack(side="left", padx=8, pady=8)

    lbl_titel = ctk.CTkLabel(zeile_oben, text=f"[{score:.2f}] {kuerze_dateiname(name)}", font=("Helvetica", 11, "bold"), text_color=farben.DATEINAME)
    lbl_titel.pack(side="left", padx=4)

    btn_sim = ctk.CTkButton(zeile_oben, text=t("card.similar"), width=65, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: app.aehnliche_suchen(p))
    btn_sim.pack(side="right", padx=2)

    btn_ql = ctk.CTkButton(zeile_oben, text=t("card.preview"), width=65, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: app.quicklook_im_vordergrund(p))
    btn_ql.pack(side="right", padx=2)

    btn_finder = ctk.CTkButton(zeile_oben, text=t("card.finder"), width=55, height=20, font=("Helvetica", 9), fg_color=farben.SEITE_KNOPF, hover_color=farben.SEITE_KNOPF_HOVER, command=lambda p=pfad: app.im_finder_zeigen_im_vordergrund(p))
    btn_finder.pack(side="right", padx=2)

    btn_open = ctk.CTkButton(zeile_oben, text=t("card.open"), width=50, height=20, font=("Helvetica", 9), command=lambda p=pfad: app.datei_oeffnen_im_vordergrund(p))
    btn_open.pack(side="right", padx=4)

    ist_favorit = pfad in app.favoriten
    btn_fav = ctk.CTkButton(
        zeile_oben, text="★" if ist_favorit else "☆", width=24, height=20,
        font=("Helvetica", 11), fg_color="transparent",
        text_color="#f57f17" if ist_favorit else "#78909c",
        hover_color=("#e0e0e0", "#3a3a3a"),
        command=lambda p=pfad: app._favorit_umschalten(p)
    )
    btn_fav.pack(side="right", padx=2)

    # Untere Zeile: kurzer Textausschnitt aus dem getroffenen
    # Abschnitt, damit man sieht WARUM die Datei getroffen hat,
    # statt nur den nackten Score zu sehen.
    # Der Ausschnitt wird um die Fundstelle herum gewaehlt und die
    # Suchwoerter darin eingefaerbt. Ein einfaches Label kann keinen
    # Text teilweise faerben - deshalb ein Textfeld, das wie ein
    # Label aussieht: ohne Rahmen, ohne Rollbalken, nicht editierbar.
    ausschnitt, stellen = ausschnitt_mit_fundstellen(
        eintrag.get("text"), such_woerter)
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
                inneres.bind(ereignis, app._rollen_weiterreichen)
        except Exception:
            pass
    else:
        # Kein Textausschnitt vorhanden (z.B. bei Favoriten-Ansicht,
        # wo teils nur Metadaten ohne Chunk-Text vorliegen).
        ctk.CTkFrame(card, height=6, fg_color="transparent").pack(fill="x")
    return card


def kuerze_dateiname(name, max_laenge=34):
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
