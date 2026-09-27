#!/usr/bin/env python3
"""
updates.py - Gibt es eine neuere Fassung? Fragt GitHub nach dem neuesten
Release und vergleicht die Versionsnummern.

Kennt keine Oberflaeche: das Hinweisfenster baut oberflaeche/dialoge/
meldungen.py, der Anstoss kommt aus dem Hauptfenster.
"""

import json
import re
import urllib.error
import urllib.request

from smartsearch import version

# Die Update-Prüfung fragt GitHub direkt nach dem neuesten Release.
#
# WARUM NICHT MEHR die eigene Website (bis 1.0.2: version.json): Sie liegt
# hinter Cloudflare, und dessen Bot-Erkennung weist Anfragen mit dem
# Standard-User-Agent von Python ("Python-urllib/...") mit HTTP 403 ab -
# nachweislich auch dann, wenn die Browserintegritätsprüfung abgeschaltet
# ist. Genau daran ist die Prüfung in Fassung 1.0.1 gescheitert, ohne dass
# es auffiel: der Fehler wird im Hintergrund still verschluckt. GitHub
# rechnet mit Programmen als Aufrufern und blockt sie nicht.
#
# Kostenlos und ohne Anmeldung. Das Limit liegt bei 60 Anfragen je Stunde
# und IP-Adresse; die App fragt einmal pro Start, das reicht mit großem
# Abstand. Ein Zugangsschlüssel würde das Limit anheben, hat aber in einer
# ausgelieferten App nichts zu suchen - er wäre auslesbar.
GITHUB_RELEASES_API = "https://api.github.com/repos/Marcel-land/SmartSearch/releases/latest"

# Wohin der "Herunterladen"-Knopf im Update-Fenster fuehrt.
#
# Bewusst die eigene Adresse und nicht die des Releases: Wer SmartSearch
# benutzt, hat mit GitHub nichts zu tun und soll dort auch nicht landen.
# smartsearch-app.com/SmartSearch.dmg leitet still zur Datei im neuesten
# Release weiter (siehe website/_redirects) - sichtbar ist nur die eigene
# Adresse, und der Download startet sofort.
#
# Die PRUEFUNG laeuft weiterhin ueber GitHub, nur der Knopf nicht. Das ist
# kein Widerspruch: die Pruefung stellt ein Programm, und solche Anfragen
# weist die Bot-Erkennung des Webhosters ab. Den Knopf klickt ein Mensch,
# es oeffnet sich ein Browser - und Browser werden nicht abgewiesen.
DOWNLOAD_ADRESSE = "https://smartsearch-app.com/SmartSearch.dmg"
UPDATE_CHECK_TIMEOUT_SEK = 5


def release_notizen(text, max_zeilen=5, max_zeichen=400):
    """Macht aus dem Release-Text von GitHub ein paar lesbare Zeilen.

    Der Text ist Markdown und enthält neben den Änderungen oft auch
    Installationshinweise. Im Hinweisfenster interessiert nur der Anfang:
    alles ab einer Trennlinie (---) entfällt, Überschriften ebenso,
    Aufzählungszeichen werden zu Punkten.

    Zur Einrückung: Eine Zeile gilt nur dann als Fortsetzung der
    vorherigen, wenn sie eingerückt ist UND darüber eine Aufzählung stand.
    Ohne diese Bedingung würden fünf gleichwertige Absätze - so sieht der
    Text von 1.0.2 aus - zu einem einzigen Klumpen zusammenlaufen.
    """
    zeilen = []
    letzte_war_aufzaehlung = False

    for rohzeile in (text or "").splitlines():
        zeile = rohzeile.strip()
        if zeile.startswith("---"):
            break
        if not zeile or zeile.startswith("#"):
            letzte_war_aufzaehlung = False
            continue

        eingerueckt = rohzeile[:1] in (" ", "\t")
        if zeile.startswith(("- ", "* ")):
            if len(zeilen) >= max_zeilen:
                break
            zeilen.append("• " + zeile[2:])
            letzte_war_aufzaehlung = True
        elif eingerueckt and letzte_war_aufzaehlung and zeilen:
            zeilen[-1] += " " + zeile
        else:
            if len(zeilen) >= max_zeilen:
                break
            zeilen.append(zeile)
            letzte_war_aufzaehlung = False

    ergebnis = "\n".join(zeilen)
    if len(ergebnis) > max_zeichen:
        ergebnis = ergebnis[:max_zeichen].rstrip() + " …"
    return ergebnis


def version_tuple(v):
    """Wandelt einen Versionsstring wie '1.2.10' in (1, 2, 10) um, damit
    Versionen NUMERISCH statt als Text verglichen werden - ein reiner
    Textvergleich würde z.B. '1.9.0' fälschlich für neuer als '1.10.0'
    halten."""
    teile = []
    for stueck in v.strip().split("."):
        ziffern = re.match(r"\d+", stueck)
        teile.append(int(ziffern.group()) if ziffern else 0)
    return tuple(teile)


def neueste_fassung_abfragen():
    """Fragt GitHub nach dem neuesten Release.

    Rueckgabe: (versionsnummer, notizen) - z. B. ("1.0.7", "• Behebt ...").
    Wirft bei jedem Fehler (kein Netz, GitHub gestoert, Anfragelimit) eine
    Ausnahme; was damit geschieht, entscheidet der Aufrufer.
    """
    # Mit eigenem User-Agent anfragen. Ohne einen solchen sendet urllib
    # "Python-urllib/3.x", und Schutzmechanismen vor automatisierten
    # Zugriffen - bei Cloudflare etwa der Bot-Schutz - weisen solche
    # Anfragen ab. Das Ergebnis war ein HTTP 403, das in der Oberflaeche wie
    # ein Netzwerkproblem aussah, obwohl die Verbindung stand.
    anfrage = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            # GitHub verlangt einen User-Agent und weist Anfragen ohne einen
            # ab. WELCHER es ist, ist ihnen egal - anders als der
            # Bot-Erkennung von Cloudflare.
            "User-Agent": f"SmartSearch/{version.APP_VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(anfrage, timeout=UPDATE_CHECK_TIMEOUT_SEK) as antwort:
        daten = json.loads(antwort.read().decode("utf-8"))

    # GitHub liefert die Markierung als "v1.0.3"; version_tuple() rechnet
    # mit reinen Ziffern.
    neueste = str(daten.get("tag_name", "")).strip().lstrip("vV")
    return neueste, release_notizen(daten.get("body", ""))


def ist_neuer(andere_version):
    """True, wenn andere_version neuer ist als die laufende Fassung.

    Liest version.APP_VERSION bei JEDEM Aufruf neu (statt sie beim Import
    festzuhalten) - so kann tests/test_update_hinweis.py die Nummer im
    Arbeitsspeicher herabsetzen.
    """
    return bool(andere_version) and version_tuple(andere_version) > version_tuple(version.APP_VERSION)
