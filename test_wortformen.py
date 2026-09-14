# -*- coding: utf-8 -*-
"""Prueft die Wortform-Erkennung der Suche - ohne KI-Modell, ohne Index.

Warum eigene Pruefung: wort_trifft() entscheidet mit darueber, ob eine
Anfrage ueberhaupt Treffer bekommt, und laeuft komplett auf Zeichenketten.
Sie laesst sich deshalb in einer Sekunde pruefen, waehrend die vollstaendige
Suchdiagnose (such_diagnose.py) erst das Modell laden muss.

Aufruf:   venv/bin/python test_wortformen.py
"""

import sys

from search import wort_trifft, wortformen


# (Suchwort, Text, erwartet, wofuer der Fall steht)
FAELLE = [
    # Zusammensetzungen - der Grund, warum nicht auf ganze Woerter geprueft wird
    ("vertrag", "mietvertrag über die wohnung", True, "Wort steht hinten"),
    ("vertrag", "vertragskonto 4711", True, "Wort steht vorne"),
    ("drucker", "rechnung laserdrucker", True, "Wort steht hinten"),

    # Mehrzahl und Beugung
    ("verträge", "mietvertrag über die wohnung", True, "Mehrzahl mit Umlaut"),
    ("rechnungen", "rechnung nr. 4711", True, "Mehrzahl auf -en"),
    ("kündigungen", "kündigung des vertrags", True, "Kanzlei-Anfrage"),
    ("vollmachten", "vorsorgevollmacht", True, "Kanzlei-Anfrage"),
    ("spende", "spenden an den verein", True, "Anfrage laenger als Fundstelle"),
    ("bücher", "buch der stunde", True, "Umlaut-Mehrzahl auf -er"),
    ("häuser", "hausratversicherung", True, "Umlaut-Mehrzahl auf -er"),
    ("straße", "strassenverkehrsordnung", True, "ss statt ß"),

    # Was NICHT treffen darf
    ("auto", "waschvollautomat garantie", False, "nicht mitten im Wort"),
    ("drucker", "anlagendruck erhöht", False, "kein Stamm 'druck'"),
    ("kosten", "kostüm für fasching", False, "kein Stamm 'kost'"),
    ("planen", "der planet mars", False, "kein Stamm 'plan'"),
]

# Bekannte Grenzen: heute bewusst so, hier festgehalten, damit eine
# Aenderung an der Wortform-Regel sofort auffaellt.
GRENZEN = [
    ("mieten", "mietvertrag", False, "Verb-Mehrzahl, Stamm waere nur 4 Zeichen"),
    ("bücher", "buchhaltung", True, "Umlaut-Stamm trifft auch andere Zusammensetzung"),
]


def pruefe(faelle, ueberschrift):
    print(ueberschrift)
    fehler = 0
    for wort, text, erwartet, wofuer in faelle:
        ist = wort_trifft(wort, text)
        if ist == erwartet:
            zeichen = "ok  "
        else:
            zeichen = "FEHL"
            fehler += 1
        print("  %s %-12s in %-32s erwartet=%-5s ist=%-5s  %s"
              % (zeichen, wort, text[:30], erwartet, ist, wofuer))
        if ist != erwartet:
            print("         gebildete Formen: %s" % sorted(wortformen(wort)))
    print()
    return fehler


def main():
    fehler = pruefe(FAELLE, "Erwartetes Verhalten:")
    fehler += pruefe(GRENZEN, "Bekannte Grenzen (Aenderung hier ist eine Entscheidung):")

    gesamt = len(FAELLE) + len(GRENZEN)
    if fehler:
        print("%d von %d Faellen weichen ab." % (fehler, gesamt))
        return 1
    print("Alle %d Faelle wie erwartet." % gesamt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
