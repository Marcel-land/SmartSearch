#!/usr/bin/env python3
"""
sprache.py - Suchwoerter aus einer Anfrage holen, deutsche Wortformen
erkennen und Fundstellen im Text markieren.

Reine Zeichenkettenarbeit, ohne Modell und ohne Index - deshalb laesst
sich alles hier in einer Sekunde pruefen (tests/test_wortformen.py).
"""

import re

# Woerter, die nichts ueber den Inhalt aussagen und deshalb nicht als
# Suchwort zaehlen. Die Liste war lange auf Artikel und die haeufigsten
# Praepositionen beschraenkt - zu wenig, sobald jemand eine Frage stellt
# statt Stichworte einzutippen. Bei "Versicherung fuers Auto" zaehlte
# "fuers" als drittes Suchwort; da es in keinem Dokument steht, kam die
# Kfz-Versicherung nur auf ein Drittel der Stichwortwertung. Gemessen am
# 14.09.2026: dadurch blieb von drei passenden Dokumenten eines uebrig.
STOPWOERTER = {
    # Artikel und Pronomen
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
    "ich", "mir", "mich", "mein", "meine", "meinen", "meiner", "meinem",
    "es", "er", "sie", "wir", "ihr", "man", "sich", "denen",
    # Fragewoerter
    "was", "wer", "wie", "wo", "wann", "warum", "wieso", "welche", "welcher",
    "welches", "welchen",
    # Praepositionen, auch die verschmolzenen Formen
    "und", "oder", "für", "fürs", "von", "vom", "mit", "auf", "im", "in",
    "zu", "zur", "zum", "um", "ums", "über", "unter", "vor", "seit", "ohne",
    "gegen", "durch", "bei", "aus", "nach", "rund",
    # Hilfs- und Modalverben
    "ist", "sind", "war", "waren", "habe", "hab", "hatte", "haben", "werde",
    "wird", "wurde", "kann", "soll", "muss", "möchte",
    # Fuellwoerter
    "als", "am", "an", "dass", "damit", "auch", "nur", "sehr", "noch", "mehr",
    "schon", "etwas", "alle", "alles", "jeden", "jede", "jedes", "jeder",
}


def anfrage_woerter(anfrage):
    rohe_woerter = re.findall(r"\w+", anfrage.lower())
    return [w for w in rohe_woerter if len(w) > 2 and w not in STOPWOERTER]


def _entumlaute(wort):
    return (wort.replace("ä", "a").replace("ö", "o")
                .replace("ü", "u").replace("ß", "ss"))


# Nur echte Mehrzahl-Endungen. "er" steht bewusst nicht dabei, ausser das
# Wort traegt einen Umlaut ("Buecher" -> "Buch", "Haeuser" -> "Haus"):
# sonst wuerde aus "Drucker" der Stamm "Druck", und die Suche faende
# jedes Dokument mit "Anlagendruck". Gemessen am 14.09.2026 war genau
# das der Fall. Geprueft wird das in test_wortformen.py.
_MEHRZAHL_ENDUNGEN = ("en", "e", "n", "s")


def wortformen(wort):
    """Das Suchwort und eine vorsichtig gebildete Grundform dazu.

    Deutsch beugt und setzt zusammen, die Suche darf daran nicht
    scheitern. Ohne diese Funktion fand "Verträge" KEIN einziges
    Dokument, waehrend "Vertrag" vier fand - der Unterschied war das
    Mehrzahl-e. Fuer eine Kanzlei, die "Kuendigungen" oder "Vollmachten"
    eintippt, waere das der Punkt, an dem sie das Programm weglegt.

    Bewusst kein richtiger Stemmer: eine Bibliothek dafuer waere eine
    weitere Abhaengigkeit im Bundle, und die vier Endungen unten decken
    ab, was in Suchanfragen tatsaechlich vorkommt.
    """
    formen = {wort, _entumlaute(wort)}
    hat_umlaut = any(z in wort for z in "äöü")
    endungen = ("er",) + _MEHRZAHL_ENDUNGEN if hat_umlaut else _MEHRZAHL_ENDUNGEN
    # Wie kurz der Stamm sein darf. Bei einem Umlaut im Suchwort ist die
    # Mehrzahl gesichert ("Buecher", "Haeuser", "Baende") und der Stamm
    # darf vier Zeichen haben. Ohne Umlaut bleibt es bei fuenf: sonst
    # wuerde aus "kosten" der Stamm "kost" und die Suche faende
    # "Kostuem", aus "planen" wuerde "plan" und sie faende "Planet".
    mindest_stamm = 4 if hat_umlaut else 5
    if len(wort) >= 6:
        for endung in endungen:
            if not wort.endswith(endung):
                continue
            # Die erste passende Endung ist die richtige, und zwar auch
            # dann, wenn der Stamm danach zu kurz ist. Frueher lief die
            # Schleife in diesem Fall weiter und probierte die naechste,
            # kuerzere Endung: aus "planen" wurde ueber die Endung "n"
            # der Stamm "plane", und die Suche fand "Planet". Richtig ist
            # die Endung "en" - der Stamm "plan" waere zu kurz, also
            # bleibt es bei der Anfrage selbst.
            if len(wort) - len(endung) >= mindest_stamm:
                stamm = wort[: -len(endung)]
                formen.add(stamm)
                formen.add(_entumlaute(stamm))
            break
    return {f for f in formen if len(f) >= 4}


def wort_trifft(wort, heuhaufen):
    """Steht das Suchwort (oder seine Grundform) im Text?

    Verlangt eine Wortgrenze an mindestens EINEM Ende. Das ist der
    Mittelweg zwischen zwei Fehlern:

    - Ein reiner Teilstring-Vergleich, wie er hier frueher stand, fand
      "Auto" in "Waschvollautomat". Bei der Anfrage "Auto" war die
      Garantie fuer die Waschmaschine deshalb der einzige woertliche
      Treffer, und die Kfz-Versicherung fiel hinten runter.
    - Ein Vergleich auf ganze Woerter wuerde "Vertrag" nicht mehr in
      "Mietvertrag" finden - und zusammengesetzte Woerter sind im
      Deutschen die Regel, nicht die Ausnahme.

    Wortanfang oder Wortende zu verlangen loest beides: "mietvertrag"
    endet auf "vertrag", "vertragskonto" faengt damit an,
    "waschvollautomat" hat "auto" nur mittendrin.
    """
    if not heuhaufen:
        return False
    for form in wortformen(wort):
        for _ in _stellen_mit_wortgrenze(form, heuhaufen):
            return True
    return False


def _stellen_mit_wortgrenze(form, text):
    """Alle (anfang, ende), an denen 'form' im Text steht und dabei an
    mindestens EINEM Ende eine Wortgrenze hat (Begruendung siehe
    wort_trifft). Wird von der Trefferpruefung UND von der Einfaerbung
    benutzt - frueher stand dieselbe Regel an beiden Stellen getrennt, und
    eine Aenderung an nur einer haette Einfaerbung und Treffer
    auseinanderlaufen lassen."""
    for treffer in re.finditer(re.escape(form), text):
        anfang, ende = treffer.start(), treffer.end()
        am_wortanfang = anfang == 0 or not text[anfang - 1].isalnum()
        am_wortende = ende >= len(text) or not text[ende].isalnum()
        if am_wortanfang or am_wortende:
            yield anfang, ende


def _fundstellen(text_klein, such_woerter):
    """Alle Stellen, an denen ein Suchwort oder seine Grundform steht.

    Nutzt dieselbe Regel wie wort_trifft(): Wortgrenze an mindestens
    einem Ende. Sonst wuerde die Einfaerbung etwas anderes zeigen als
    das, was den Treffer ausgemacht hat - bei "Verträge" bliebe der
    Ausschnitt unmarkiert, obwohl "Mietvertrag" der Grund fuer den
    Treffer war.
    """
    stellen = []
    for wort in such_woerter or []:
        for form in wortformen(wort.lower()):
            stellen.extend(_stellen_mit_wortgrenze(form, text_klein))
    return stellen


def ausschnitt_mit_fundstellen(text, such_woerter, laenge=170):
    """Schneidet einen Textausschnitt RUND UM die erste Fundstelle heraus
    und meldet, wo darin die Suchwoerter stehen.

    Vorher begann der Ausschnitt immer am Anfang des Abschnitts. Steht das
    gesuchte Wort weiter hinten, sah der Nutzer davon nichts - er bekam
    einen Treffer angezeigt, ohne zu erkennen, warum es einer ist.

    Rueckgabe: (ausschnitt, stellen) - 'stellen' ist eine Liste von
    (start, ende) im Ausschnitt, jeweils bezogen auf dessen Zeichen.
    """
    text = (text or "").strip().replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    if not text:
        return "", []

    text_klein = text.lower()

    # Alle Fundstellen sammeln und die Stelle waehlen, an der die meisten
    # Suchwoerter dicht beieinanderstehen. Die erste Fundstelle zu nehmen
    # waere zu einfach: sucht jemand "Canon Rechnung", steht "Rechnung"
    # meist schon im Briefkopf, "Canon" aber erst in der Positionszeile -
    # der Ausschnitt zeigte dann den Briefkopf statt der eigentlichen
    # Fundstelle.
    alle_stellen = [a for a, _ in _fundstellen(text_klein, such_woerter)]

    erste = None
    if alle_stellen:
        alle_stellen.sort()
        bestes = (0, alle_stellen[0])
        for kandidat in alle_stellen:
            im_fenster = sum(1 for p in alle_stellen if kandidat <= p < kandidat + laenge)
            if im_fenster > bestes[0]:
                bestes = (im_fenster, kandidat)
        erste = bestes[1]

    if erste is None or len(text) <= laenge:
        ausschnitt = text[:laenge]
        versatz = 0
        if len(text) > laenge:
            ausschnitt = ausschnitt.rsplit(" ", 1)[0] + " …"
    else:
        # Die Fundstelle etwa ins erste Drittel legen, damit auch der
        # Zusammenhang davor sichtbar bleibt.
        start = max(0, erste - laenge // 3)
        # Nicht mitten im Wort beginnen.
        if start > 0:
            leer = text.find(" ", start)
            start = leer + 1 if 0 <= leer < start + 20 else start
        ausschnitt = text[start:start + laenge]
        if start + laenge < len(text):
            ausschnitt = ausschnitt.rsplit(" ", 1)[0] + " …"
        if start > 0:
            ausschnitt = "… " + ausschnitt
            versatz = start - 2
        else:
            versatz = start

    # Alle Vorkommen im fertigen Ausschnitt einsammeln.
    stellen = _fundstellen(ausschnitt.lower(), such_woerter)

    # Ueberlappungen zusammenfassen, damit die Einfaerbung sauber bleibt.
    stellen.sort()
    zusammengefasst = []
    for start_, ende_ in stellen:
        if zusammengefasst and start_ <= zusammengefasst[-1][1]:
            zusammengefasst[-1] = (zusammengefasst[-1][0], max(zusammengefasst[-1][1], ende_))
        else:
            zusammengefasst.append((start_, ende_))

    return ausschnitt, zusammengefasst
