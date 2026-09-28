"""
suchfaelle.py - welche Suchanfrage welches Testdokument finden muss.

Gehoert zu tests/testdokumente (50 Dokumente, erzeugt von
werkzeuge/testdokumente) und wird von werkzeuge/such_diagnose.py
ausgewertet. Eine Anfrage gilt als RICHTIG, wenn die App genau das zeigt,
was hier steht - gemessen mit derselben Funktion, die auch die App benutzt
(kern.suche.suche_intern).

Felder eines Falls
------------------
erster   An erster Stelle muss eines dieser Dokumente stehen.
dabei    Diese Dokumente muessen alle unter den Treffern sein.
keine    True: Es darf GAR NICHTS angezeigt werden (Negativtest).
auch_ok  Duerfen angezeigt werden, ohne als Fehlgriff zu zaehlen.

Alles, was angezeigt wird und in keinem der Felder steht, zaehlt als
Fehlgriff. Die Zahl der Fehlgriffe ist die zweite Kennzahl neben
"richtig": Eine Suche, die das Richtige vorn zeigt und darunter zehn
falsche Dokumente, ist schlechter als eine mit dem Richtigen allein.

Arten
-----
alt        die zwoelf urspruenglichen Anfragen mit ihren strengen
           Soll-Antworten - nur mit --klein (zehn Dokumente), zum Vergleich
           mit den Messungen in docs/messungen
alltag     dieselben zwoelf Anfragen, Soll-Antworten fuer 50 Dokumente
stichwort  das Suchwort steht so im Dokument
bedeutung  das Suchwort steht NICHT im Dokument, nur etwas Gleichbedeutendes
frage      eine Frage in normaler Sprache
fach       Fachbegriffe, Paragraphen, Aktenzeichen
sprache    deutsche Anfrage, englisches Dokument
scan       das Dokument ist ein Scan, gefunden nur ueber die Texterkennung
thema      mehrere Dokumente gehoeren zusammen
negativ    nichts im Bestand passt - es soll nichts angezeigt werden

Wer ein Dokument aendert oder hinzufuegt, prueft hier, ob die Soll-Antworten
noch stimmen. Die Soll-Antworten sind nachgelesen, nicht geraten.
"""

from dataclasses import dataclass, field


@dataclass
class Fall:
    anfrage: str
    art: str
    erster: list = field(default_factory=list)
    dabei: list = field(default_factory=list)
    keine: bool = False
    auch_ok: list = field(default_factory=list)


# Kurznamen der Dokumente - Dateinamen sagen absichtlich nichts ueber den Inhalt
# ---- die zehn urspruenglichen (Hauptordner) -------------------------------
KAUFVERTRAG_PKW = "Neues_Dokument_7.pdf"
KFZ_POLICE = "dok_2024_02_18.pdf"
STELLPLATZ = "Scan_20231114_0003.pdf"
INTERNET = "Scan2019-03-22_112.pdf"
STROM = "20220906_0001.pdf"
HEIZUNG_WARTUNG = "IMG_4471.pdf"
WASCHMASCHINE = "Unbenannt-3.pdf"
SPENDE = "CCF_000141.pdf"
DRUCKER = "0027_2607_001.pdf"
REISEKOSTEN = "0044_1802_002.pdf"
# ---- haushalt/ -------------------------------------------------------------
GEHALT = "Scan_20240131_0001.pdf"            # Scan
ZAHNARZT = "IMG_5102.pdf"                     # Scan
NEBENKOSTEN = "Abrechnung_HV_2023.pdf"
FITNESS_KUENDIGUNG = "Dokument1.docx"
HAUSHALTSBUCH = "Mappe1.xlsx"
STEUERBESCHEID = "Scan_20240712_0002.pdf"     # Scan
RUNDFUNK = "Schreiben_0412.pdf"
HANDY = "VZF_48213.pdf"
URLAUB = "Buchungsbestaetigung.pdf"
WERKSTATT = "Scan_20240415_0001.pdf"          # Scan
HAUSRAT = "VS-2291-0087.pdf"
ARBEITSZEUGNIS = "Zeugnis_final.docx"
KAFFEE_EN = "manual_EN.pdf"                   # englisch
VEREIN = "Präsentation1.pptx"
BAD = "notizen.txt"
# ---- kanzlei/ --------------------------------------------------------------
KLAGE_UNFALL = "Klage_Albers_v2.docx"
GUTACHTEN = "Gutachten_Scan.pdf"              # Scan
VOLLMACHT = "Scan_0042.pdf"                   # Scan
URTEIL = "Scan_Urteil_AG.pdf"                 # Scan, 2 Seiten
KSK = "KSK_Wortmann.docx"
ABMAHNUNG = "Abmahnung_2023.pdf"
AUFHEBUNG = "Aufhebungsvertrag_Entwurf.docx"
LADUNG = "Scan_20240610_0001.pdf"             # Scan
TELEFONNOTIZ = "notiz_2024-03-05.md"
RAEUMUNG = "Klage_Raeumung.docx"
SCHIMMEL = "Schreiben_Vermieter.docx"
TESTAMENT = "Testament_Entwurf_Brinkmann.docx"
ERBSCHEIN = "Antrag_Nachlassgericht.pdf"
SCHEIDUNG = "Antrag_FamG.docx"
UNTERHALT = "Berechnung_KU.xlsx"
GMBH = "Satzung_Entwurf.pdf"
NDA_EN = "NDA_Northbridge.docx"               # englisch
MAHNBESCHEID = "Scan_20240506_0007.pdf"       # Scan
BERUFUNG = "Berufungsbegruendung.pdf"         # 3 Seiten
VORSCHUSS = "Brief_Mandant_0314.docx"
KOSTENRECHNUNG = "Kostenrechnung_2024-0391.pdf"
FRISTEN = "Fristen.xlsx"
HONORAR = "Verguetungsvereinbarung_Muster.docx"
AVV = "AVV_Cloudanbieter_unterschrieben.pdf"
BEA = "Schulung_ERV_2024.pptx"


# Alles, was ein Vertrag ist oder einen abschliesst
VERTRAEGE = [KAUFVERTRAG_PKW, STELLPLATZ, INTERNET, HANDY, AUFHEBUNG, GMBH, AVV,
             HONORAR, NDA_EN, FITNESS_KUENDIGUNG, HAUSRAT, KFZ_POLICE, TESTAMENT, URLAUB]


FAELLE = [
    # ---- die zwoelf urspruenglichen Anfragen, angepasst an 50 Dokumente -----
    # Mit zehn Dokumenten gab es genau einen Kaufvertrag und genau eine
    # Rechnung ueber ein Geraet. Jetzt gibt es z. B. eine Werkstattrechnung
    # fuers selbe Auto - die ist bei "Auto" genauso richtig wie der
    # Kaufvertrag. Die strengen Fassungen stehen unten in ALTE_FAELLE.
    Fall("Vertrag", "alltag", erster=VERTRAEGE, auch_ok=VERTRAEGE + [RAEUMUNG, SCHIMMEL, KSK]),
    Fall("Verträge", "alltag", erster=VERTRAEGE, auch_ok=VERTRAEGE + [RAEUMUNG, SCHIMMEL, KSK]),
    Fall("Auto", "alltag", erster=[KAUFVERTRAG_PKW, KFZ_POLICE, WERKSTATT],
         auch_ok=[BERUFUNG, GUTACHTEN, KLAGE_UNFALL, URTEIL, HAUSHALTSBUCH]),
    Fall("Fahrzeug", "alltag", erster=[KAUFVERTRAG_PKW, KFZ_POLICE, WERKSTATT],
         auch_ok=[BERUFUNG, GUTACHTEN, KLAGE_UNFALL, URTEIL]),
    Fall("Versicherung fürs Auto", "alltag", erster=[KFZ_POLICE],
         auch_ok=[HAUSRAT, KLAGE_UNFALL, URTEIL, HAUSHALTSBUCH]),
    Fall("Unterlagen rund ums Fahrzeug", "alltag", erster=[KAUFVERTRAG_PKW, KFZ_POLICE, WERKSTATT],
         auch_ok=[BERUFUNG, GUTACHTEN, KLAGE_UNFALL, URTEIL]),
    Fall("Was zahle ich jeden Monat?", "alltag",
         erster=[STELLPLATZ, HANDY, INTERNET, HAUSHALTSBUCH, RUNDFUNK],
         auch_ok=[STELLPLATZ, HANDY, INTERNET, HAUSHALTSBUCH, RUNDFUNK, NEBENKOSTEN, GEHALT, VEREIN]),
    Fall("Drucker", "alltag", erster=[DRUCKER], auch_ok=[ARBEITSZEUGNIS]),
    Fall("Heizung gewartet", "alltag", erster=[HEIZUNG_WARTUNG]),
    Fall("Spende für die Steuererklärung", "alltag", erster=[SPENDE], auch_ok=[STEUERBESCHEID]),
    Fall("Waschmaschine", "alltag", erster=[WASCHMASCHINE]),
    Fall("Strom", "alltag", erster=[STROM], auch_ok=[HAUSHALTSBUCH, NEBENKOSTEN]),

    # ---- Stichwort steht im Text ------------------------------------------
    Fall("Rundfunkbeitrag", "stichwort", erster=[RUNDFUNK]),
    Fall("Abfindung", "stichwort", erster=[AUFHEBUNG], auch_ok=[TELEFONNOTIZ]),
    Fall("Testament", "stichwort", erster=[TESTAMENT], auch_ok=[ERBSCHEIN]),
    Fall("Stammkapital", "stichwort", erster=[GMBH]),
    Fall("Fliesen", "stichwort", erster=[BAD]),
    Fall("Nebenkostenabrechnung", "stichwort", erster=[NEBENKOSTEN]),
    Fall("Arbeitszeugnis", "stichwort", erster=[ARBEITSZEUGNIS], auch_ok=[AUFHEBUNG]),
    Fall("Scheidung", "stichwort", erster=[SCHEIDUNG], auch_ok=[UNTERHALT]),
    Fall("Reisekosten", "stichwort", erster=[REISEKOSTEN]),

    # ---- nur die Bedeutung passt ------------------------------------------
    Fall("GEZ", "bedeutung", erster=[RUNDFUNK]),
    Fall("Handyvertrag", "bedeutung", erster=[HANDY], auch_ok=[INTERNET, HAUSHALTSBUCH]),
    Fall("Gehaltsabrechnung", "bedeutung", erster=[GEHALT]),
    Fall("Fitnessstudio kündigen", "bedeutung", erster=[FITNESS_KUENDIGUNG]),
    Fall("Anwaltsrechnung", "bedeutung", erster=[KOSTENRECHNUNG], auch_ok=[VORSCHUSS, HONORAR]),
    Fall("Urlaub", "bedeutung", erster=[URLAUB]),
    Fall("Mitgliedsbeitrag im Sportverein", "bedeutung", erster=[VEREIN], auch_ok=[FITNESS_KUENDIGUNG]),

    # ---- Fragen in normaler Sprache ---------------------------------------
    Fall("Wie viel habe ich für Lebensmittel ausgegeben?", "frage", erster=[HAUSHALTSBUCH]),
    Fall("Wann läuft die Berufungsfrist ab?", "frage", erster=[FRISTEN], auch_ok=[URTEIL, BERUFUNG]),
    Fall("Bin ich versichert, wenn mein Fahrrad gestohlen wird?", "frage", erster=[HAUSRAT]),
    Fall("Wann geht der Flug nach Mallorca?", "frage", erster=[URLAUB]),
    Fall("Wie viel Unterhalt bekommen die Kinder?", "frage", erster=[UNTERHALT, SCHEIDUNG],
         dabei=[UNTERHALT]),
    Fall("Wie hoch ist die Steuererstattung?", "frage", erster=[STEUERBESCHEID]),
    Fall("Wann ist der Gütetermin?", "frage", erster=[LADUNG, FRISTEN],
         auch_ok=[LADUNG, FRISTEN, TELEFONNOTIZ, AUFHEBUNG]),

    # ---- Fachbegriffe, Paragraphen, Aktenzeichen --------------------------
    Fall("§ 4 KSchG", "fach", erster=[KSK, FRISTEN], dabei=[KSK]),
    Fall("3 C 118/24", "fach", erster=[URTEIL, FRISTEN], dabei=[URTEIL]),
    Fall("Verfahrensgebühr Nr. 3100 VV RVG", "fach", erster=[KOSTENRECHNUNG]),
    Fall("Versorgungsausgleich", "fach", erster=[SCHEIDUNG], auch_ok=[FRISTEN]),
    Fall("Pflichtteilsstrafklausel", "fach", erster=[TESTAMENT]),
    Fall("Auftragsverarbeitung nach DSGVO", "fach", erster=[AVV]),
    Fall("elektronisches Empfangsbekenntnis", "fach", erster=[BEA]),
    Fall("Sozialauswahl", "fach", erster=[KSK]),
    Fall("Abmahnung wegen Zuspätkommen", "fach", erster=[ABMAHNUNG], auch_ok=[TELEFONNOTIZ]),
    Fall("Vorschuss vom Mandanten anfordern", "fach", erster=[VORSCHUSS], auch_ok=[KOSTENRECHNUNG]),
    Fall("Aktennotiz über das Telefonat mit der Mandantin", "fach", erster=[TELEFONNOTIZ]),
    Fall("Räumungsklage wegen Mietrückstand", "fach", erster=[RAEUMUNG]),
    Fall("Mietminderung wegen Schimmel", "fach", erster=[SCHIMMEL]),
    Fall("Erbschein beantragen", "fach", erster=[ERBSCHEIN], auch_ok=[TESTAMENT]),
    Fall("Stundenhonorar des Anwalts", "fach", erster=[HONORAR], auch_ok=[KOSTENRECHNUNG]),
    Fall("Rücktritt vom Autokauf wegen verschwiegenem Unfallschaden", "fach",
         erster=[BERUFUNG], auch_ok=[KAUFVERTRAG_PKW]),

    # ---- Deutsch gefragt, Englisch geschrieben ----------------------------
    Fall("Kaffeemaschine entkalken", "sprache", erster=[KAFFEE_EN]),
    Fall("Geheimhaltungsvereinbarung", "sprache", erster=[NDA_EN], auch_ok=[AVV]),

    # ---- nur ueber die Texterkennung auffindbar ---------------------------
    Fall("Reifenwechsel", "scan", erster=[WERKSTATT]),
    Fall("Rechnung vom Zahnarzt", "scan", erster=[ZAHNARZT]),
    Fall("Mahnbescheid", "scan", erster=[MAHNBESCHEID], auch_ok=[FRISTEN]),
    Fall("Prozessvollmacht", "scan", erster=[VOLLMACHT], auch_ok=[HONORAR]),
    Fall("Gutachten zum Unfallschaden", "scan", erster=[GUTACHTEN],
         auch_ok=[KLAGE_UNFALL, URTEIL, BERUFUNG]),
    Fall("Urteil zum Verkehrsunfall", "scan", erster=[URTEIL], auch_ok=[KLAGE_UNFALL, GUTACHTEN]),

    # ---- mehrere Dokumente gehoeren zusammen ------------------------------
    Fall("Unterlagen zum Unfall von Herrn Albers", "thema",
         dabei=[KLAGE_UNFALL, URTEIL, GUTACHTEN],
         auch_ok=[VOLLMACHT, VORSCHUSS, KOSTENRECHNUNG, FRISTEN]),
    Fall("Arbeitsgerichtsverfahren Wortmann", "thema",
         dabei=[KSK, LADUNG],
         auch_ok=[ABMAHNUNG, AUFHEBUNG, TELEFONNOTIZ, FRISTEN]),
    Fall("Versicherungen", "thema", dabei=[KFZ_POLICE, HAUSRAT],
         auch_ok=[URLAUB, NEBENKOSTEN, HAUSHALTSBUCH, GEHALT]),
    Fall("Rechnungen fürs Auto", "thema", dabei=[WERKSTATT],
         auch_ok=[KFZ_POLICE, KAUFVERTRAG_PKW, HAUSHALTSBUCH]),

    # ---- nichts passt - nichts anzeigen -----------------------------------
    Fall("Rezept für Apfelkuchen", "negativ", keine=True),
    Fall("Bewerbung als Pilot", "negativ", keine=True),
    Fall("Gästeliste für die Hochzeit", "negativ", keine=True),
    Fall("Gartenzaun streichen", "negativ", keine=True),
]

# Die zwoelf urspruenglichen Anfragen mit ihren urspruenglichen, strengen
# Soll-Antworten - nur fuer die zehn urspruenglichen Dokumente
# (such_diagnose --klein), damit alte Messungen vergleichbar bleiben.
ALTE_FAELLE = [
    Fall("Vertrag", "alt", dabei=[KAUFVERTRAG_PKW, STELLPLATZ, INTERNET]),
    Fall("Verträge", "alt", dabei=[KAUFVERTRAG_PKW, STELLPLATZ, INTERNET]),
    Fall("Auto", "alt", erster=[KAUFVERTRAG_PKW]),
    Fall("Fahrzeug", "alt", erster=[KAUFVERTRAG_PKW]),
    Fall("Versicherung fürs Auto", "alt", erster=[KFZ_POLICE]),
    Fall("Unterlagen rund ums Fahrzeug", "alt", erster=[KAUFVERTRAG_PKW]),
    Fall("Was zahle ich jeden Monat?", "alt", erster=[STELLPLATZ]),
    Fall("Drucker", "alt", erster=[DRUCKER]),
    Fall("Heizung gewartet", "alt", erster=[HEIZUNG_WARTUNG]),
    Fall("Spende für die Steuererklärung", "alt", erster=[SPENDE], auch_ok=[STEUERBESCHEID]),
    Fall("Waschmaschine", "alt", erster=[WASCHMASCHINE]),
    Fall("Strom", "alt", erster=[STROM], auch_ok=[HAUSHALTSBUCH, NEBENKOSTEN]),

]

ARTEN = ["alt", "alltag", "stichwort", "bedeutung", "frage", "fach", "sprache", "scan", "thema", "negativ"]

# Die zehn urspruenglichen Dokumente - fuer den Vergleich mit alten Messungen
# (such_diagnose --klein)
URSPRUENGLICHE = [KAUFVERTRAG_PKW, KFZ_POLICE, STELLPLATZ, INTERNET, STROM,
                  HEIZUNG_WARTUNG, WASCHMASCHINE, SPENDE, DRUCKER, REISEKOSTEN]
