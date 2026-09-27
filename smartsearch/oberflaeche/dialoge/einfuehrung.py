#!/usr/bin/env python3
"""
dialoge/einfuehrung.py - die mehrstufige Einfuehrung beim ersten Start
(und erneut aufrufbar aus Einstellungen > Hilfe).
"""

import os
from tkinter import filedialog

import customtkinter as ctk

from smartsearch.oberflaeche import farben
from smartsearch.oberflaeche.i18n import t
from smartsearch.kern import ordner


def zeigen(app, mit_ordnerauswahl=True):
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
    app.attributes("-topmost", False)
    top = ctk.CTkToplevel(app)
    top.title(t("guide.title"))
    top.geometry("660x640")
    top.attributes("-topmost", True)
    app.nebenfenster_anmelden(top)
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
            app.attributes("-topmost", False)
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
            app.setze_status(t("onboarding.status_skipped"))
            return
        if not gewaehlte_ordner:
            app.setze_status(t("onboarding.status_none_selected"))
            return

        for pfad in gewaehlte_ordner:
            ordner.befehl_ordner_hinzufuegen(pfad)
        app.starte_ordner_überwachung()
        app.index_aktualisieren()

    # Das Schliessen ueber das Fenstersymbol verhaelt sich wie
    # "Ueberspringen" - ein halb durchlaufener Assistent darf keinen
    # halben Zustand hinterlassen.
    top.protocol("WM_DELETE_WINDOW", lambda: abschliessen(uebersprungen=True))

    zeichne()
