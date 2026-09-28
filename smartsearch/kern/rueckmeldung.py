#!/usr/bin/env python3
"""
rueckmeldung.py - die Bitte um Rueckmeldung: wann sie erscheint und was
in der vorbereiteten E-Mail steht.

Ohne Konto und ohne Nutzungsdaten ist die E-Mail der einzige Draht zu den
Nutzern. Die Oberflaeche zeigt Leiste und Knoepfe; hier steht nur, WANN
gefragt wird und WAS in der Mail steht.
"""

import platform
import urllib.parse

from smartsearch import version
from smartsearch.kern.einstellungen import lade_config, speichere_config

# Anschrift fuer Rueckmeldungen - gehoert zur eigenen Domain.
RUECKMELDUNG_ADRESSE = "kontakt@smartsearch-app.com"

# Schwellen bewusst hoch und die Bitte hoechstens zweimal: wer einmal
# "Nicht jetzt" sagt, meint meistens "nie" - ein zweites Nachfassen nach
# weiteren 25 Suchen ist die Grenze des Zumutbaren.
RM_AB_SUCHEN = 8
RM_ABSTAND = 25
RM_MAX = 2


def _stand():
    config = lade_config()
    stand = config.get("rueckmeldung") or {}
    stand.setdefault("suchen", 0)
    stand.setdefault("gezeigt", 0)
    stand.setdefault("erledigt", False)
    stand.setdefault("ab", RM_AB_SUCHEN)
    return config, stand


def _merken(config, stand):
    config["rueckmeldung"] = stand
    try:
        speichere_config(config)
    except Exception:
        pass  # Eine nicht schreibbare Konfiguration darf keine Suche stoeren.


def suche_zaehlen(leiste_schon_sichtbar):
    """Nach jeder erfolgreichen Suche aufrufen.

    Rueckgabe: True, wenn die Oberflaeche die Bitte JETZT einblenden soll.
    """
    config, stand = _stand()
    stand["suchen"] += 1
    zeigen = (not stand["erledigt"] and not leiste_schon_sichtbar
              and stand["gezeigt"] < RM_MAX
              and stand["suchen"] >= stand["ab"])
    if zeigen:
        stand["gezeigt"] += 1
    _merken(config, stand)
    return zeigen


def spaeter():
    """"Nicht jetzt" - erst nach RM_ABSTAND weiteren Suchen wieder fragen."""
    config, stand = _stand()
    stand["ab"] = stand["suchen"] + RM_ABSTAND
    _merken(config, stand)


def mail_link(vorbelegung="", texterkennung="keine", sprache="de", system=None):
    """Der mailto:-Link fuer die vorbereitete E-Mail - und merkt sich, dass
    der Nutzer die Rueckmeldung geoeffnet hat (dann wird nicht mehr gefragt).

    Bewusst E-Mail statt eines eingebauten Formulars: es braucht keinen
    Server, der Nutzer sieht vor dem Absenden genau, was uebermittelt wird,
    und kann es aendern. Enthalten sind nur Programm- und Systemangaben -
    keine Dateinamen, keine Inhalte.

    vorbelegung: Fehlermeldung, die aus einem Fehlerdialog heraus
    mitgeschickt wird. Sonst muesste der Nutzer sie abtippen.
    system: z. B. "macOS 15.1 (arm64)". Frueher stand hier fest "macOS" -
    unter Windows waere die Angabe falsch gewesen.
    """
    if system is None:
        system = f"{platform.system()} {platform.release()} ({platform.machine()})"
    rumpf = (
        "\n\n\n"
        "--- Bitte diese Zeilen stehen lassen ---\n"
        + (f"Meldung: {vorbelegung}\n" if vorbelegung else "")
        + f"SmartSearch {version.APP_VERSION}\n"
        + f"{system}\n"
        + f"Python {platform.python_version()}\n"
        + f"Texterkennung: {texterkennung}\n"
        + f"Sprache: {sprache}\n"
    )
    config, stand = _stand()
    stand["erledigt"] = True
    _merken(config, stand)

    betreff = f"SmartSearch {version.APP_VERSION} - Rueckmeldung"
    return (f"mailto:{RUECKMELDUNG_ADRESSE}"
            f"?subject={urllib.parse.quote(betreff)}"
            f"&body={urllib.parse.quote(rumpf)}")
