#!/usr/bin/env python3
"""
angaben_eintragen.py

Traegt Domain, Download-Adresse, Kontaktadresse und Anschrift an allen
Stellen in Website und App ein. Bis dahin stehen dort Platzhalter.

Aufruf:
    python3 angaben_eintragen.py --domain smartsearch-app.de \\
        --email kontakt@smartsearch-app.de \\
        --download https://github.com/Marcel-land/SmartSearch/releases/latest \\
        --name "Marcel Landmann" \\
        --strasse "Musterweg 1" \\
        --ort "12345 Musterstadt"

Ohne --schreiben wird nur angezeigt, was sich aendern wuerde. Erst mit
--schreiben werden die Dateien tatsaechlich veraendert.
"""

import argparse
import os
import re
import sys

ALTE_DOMAIN = "smartsearch-app.de"
PROJEKT = os.path.dirname(os.path.abspath(__file__))
WEBSITE = os.path.join(PROJEKT, "website")


def dateien():
    """Alle Dateien, in denen Platzhalter vorkommen koennen."""
    treffer = []
    for wurzel, ordner, namen in os.walk(WEBSITE):
        ordner[:] = [o for o in ordner if o != "schriften"]
        for name in namen:
            if name.endswith((".html", ".css", ".xml", ".txt", ".json")):
                treffer.append(os.path.join(wurzel, name))
    treffer.append(os.path.join(PROJEKT, "gui.py"))
    return sorted(treffer)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domain", required=True, help="ohne https://, z. B. smartsearch-app.de")
    p.add_argument("--email", required=True)
    p.add_argument("--download", required=True, help="Adresse der DMG bzw. der Release-Seite")
    p.add_argument("--name", required=True)
    p.add_argument("--strasse", required=True)
    p.add_argument("--ort", required=True, help="PLZ und Ort")
    p.add_argument("--datum", default="", help="Stand der Rechtstexte; ohne Angabe heute")
    p.add_argument("--hoster", default="GitHub, Inc., 88 Colin P. Kelly Jr. Street, "
                                       "San Francisco, CA 94107, USA",
                   help="Name und Anschrift des Hosters fuer die Datenschutzerklaerung")
    p.add_argument("--speicherdauer", default="Der Hoster speichert Zugriffsdaten "
                                              "fuer maximal 30 Tage.")
    p.add_argument("--download-quelle", default="GitHub Releases",
                   dest="download_quelle")
    p.add_argument("--schreiben", action="store_true",
                   help="Ohne diesen Schalter wird nichts veraendert")
    a = p.parse_args()

    domain = a.domain.strip().rstrip("/").replace("https://", "").replace("http://", "")

    ersetzungen = [
        (ALTE_DOMAIN, domain),
        ("PLATZHALTER_DOWNLOAD_URL", a.download),
        ("kontakt@smartsearch-app.de", a.email),
        ("kontakt@ihre-domain.de", a.email),
    ]

    # Die Angaben stehen in <span class="platzhalter">...</span>. Die
    # Auszeichnung faellt mit weg, sonst blieben sie farblich markiert.
    # Impressum und Datenschutzerklaerung enthalten denselben Adressblock.
    heute = a.datum or __import__("datetime").date.today().strftime("%d.%m.%Y")
    rechtstexte = [
        ('<span class="platzhalter">Vor- und Nachname</span>', a.name),
        ('<span class="platzhalter">Straße und Hausnummer</span>', a.strasse),
        ('<span class="platzhalter">Postleitzahl und Ort</span>', a.ort),
        ('<span class="platzhalter">PLZ und Ort</span>', a.ort),
        ('<span class="platzhalter">kontakt@ihre-domain.de</span>', a.email),
        ('<span class="platzhalter">Datum eintragen</span>', heute),
        ('<span class="platzhalter">Name und Anschrift des Hosters</span>', a.hoster),
        ('<span class="platzhalter">Löschfrist des Hosters eintragen, üblich sind 7 bis 30 Tage</span>',
         a.speicherdauer),
        ('<span class="platzhalter">GitHub Releases oder eigener Server</span>', a.download_quelle),
        # Telefonnummer ist im Impressum nicht verpflichtend, solange eine
        # E-Mail-Adresse angegeben ist. Ohne Angabe faellt die Zeile weg.
    ]

    gesamt = 0
    for pfad in dateien():
        try:
            text = open(pfad, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        original = text

        # Reihenfolge ist wichtig: erst die vollstaendigen <span>-Bloecke,
        # dann die einzelnen Zeichenketten. Andersherum wuerde zuerst die
        # E-Mail-Adresse INNERHALB des span getauscht, und die graue
        # Platzhalter-Auszeichnung bliebe um die fertige Angabe stehen.
        if os.path.basename(pfad) in ("impressum.html", "datenschutz.html"):
            for muster, neu in rechtstexte:
                text = text.replace(muster, neu)
            # Telefonzeile ohne Nummer ersatzlos streichen.
            text = re.sub(r'\s*Telefon: <span class="platzhalter">optional</span>\n', "\n", text)
            # Die gelben Kaesten sind Notizen an dich ("Vor der
            # Veroeffentlichung ausfuellen") und haben auf der fertigen
            # Seite nichts zu suchen. Sie fliegen hier mit raus, damit
            # niemand vergisst, sie von Hand zu loeschen.
            text = re.sub(r'\s*<div class="hinweis"[^>]*>.*?</div>\n', "\n", text, flags=re.S)

        for alt, neu in ersetzungen:
            text = text.replace(alt, neu)

        # In der App steht die Update-Adresse noch auf example.com.
        if os.path.basename(pfad) == "gui.py":
            text = text.replace(
                "https://example.com/smartsearch/version.json",
                f"https://{domain}/version.json",
            )

        if text != original:
            anzahl = sum(1 for x, y in zip(original.split("\n"), text.split("\n")) if x != y)
            gesamt += anzahl
            kurz = os.path.relpath(pfad, PROJEKT)
            print(f"  {kurz:44s} {anzahl} Zeile(n)")
            if a.schreiben:
                open(pfad, "w", encoding="utf-8").write(text)

    print()
    if gesamt == 0:
        print("Nichts gefunden - die Angaben stehen offenbar schon drin.")
    elif a.schreiben:
        print(f"{gesamt} Zeilen geaendert.")
        print("Die App muss danach neu gebaut werden: Adresse und Update-Pfad")
        print("stecken fest im Programm.")
    else:
        print(f"{gesamt} Zeilen wuerden geaendert. Mit --schreiben ausfuehren.")

    # Kontrolle: was ist uebrig geblieben? Zwei Dinge heissen zufaellig
    # aehnlich und sind KEINE Platzhalter: PLATZHALTER_TEXT ist der graue
    # Hinweistext im Suchfeld, und .platzhalter ist die CSS-Klasse, mit der
    # offene Angaben markiert werden. Beide duerfen stehen bleiben.
    unschuldig = ("PLATZHALTER_TEXT", ".platzhalter", "span.platzhalter")
    print("\nVerbliebene Platzhalter:")
    rest = 0
    for pfad in dateien():
        try:
            for nr, zeile in enumerate(open(pfad, encoding="utf-8"), 1):
                if any(w in zeile for w in unschuldig):
                    continue
                if "PLATZHALTER" in zeile or 'class="platzhalter"' in zeile or ALTE_DOMAIN in zeile:
                    print(f"  {os.path.relpath(pfad, PROJEKT)}:{nr}  {zeile.strip()[:70]}")
                    rest += 1
        except (OSError, UnicodeDecodeError):
            continue
    if rest == 0:
        print("  keine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
