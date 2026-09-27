#!/usr/bin/env python3
"""
farben.py - alle Farben von SmartSearch an einer Stelle.

WARUM ES DIESE DATEI GIBT
-------------------------
Die Farbwerte lagen als 79 einzelne Zeichenketten in gui.py verstreut.
Eine Aenderung am Erscheinungsbild bedeutete damit: alle 79 Stellen
finden, keine vergessen, und hoffen, dass sich kein Wert doppelt
irgendwo anders versteckt. Ab jetzt steht jeder Ton genau einmal hier.

Der zweite Grund: Website und Programm sahen aus wie zwei verschiedene
Produkte. Die Website hat ein gedecktes Aktenrot als einzigen Akzent,
das Programm kraeftiges Systemblau. Dieses Blau war allerdings nie eine
Entscheidung - es ist das eingebaute Standardthema von CustomTkinter
("blue"), das nie ueberschrieben wurde. thema_anwenden() weiter unten
ueberschreibt es.

AUFBAU
------
Jeder Wert ist ein Paar (hell, dunkel). CustomTkinter nimmt solche Paare
direkt an und waehlt selbst, je nach Systemeinstellung. Ein einzelner
Wert waere in einem der beiden Modi immer falsch - genau dieser Fehler
steckte vorher in den Seitenleisten-Knoepfen, die auch im hellen Modus
dunkelgrau blieben.

Die Toene sind dieselben wie in website/style.css. Wer dort etwas
aendert, sollte es hier mitaendern - und umgekehrt.
"""

# ---------------------------------------------------------------------------
# Marke
# ---------------------------------------------------------------------------

# Das Aktenrot der Website. Im dunklen Modus eine Spur heller, damit es
# sich vom dunklen Grund abhebt, ohne grell zu werden.
AKZENT = ("#c1361f", "#cf3d22")

# Beim Ueberfahren wird abgedunkelt, nicht aufgehellt. Auf der Website
# wird aufgehellt - dort sind es Verweise, hier gefuellte Schaltflaechen
# mit weisser Schrift. Aufhellen wuerde den Kontrast zur Schrift unter
# 4.5:1 druecken und die Beschriftung schlechter lesbar machen.
AKZENT_HOVER = ("#a52d19", "#b3311c")

# Schrift auf dem Akzent. Geprueft: 5.5:1 im hellen, 4.8:1 im dunklen
# Modus - beides ueber der Schwelle fuer kleine Schrift.
AUF_AKZENT = ("#ffffff", "#ffffff")

# ---------------------------------------------------------------------------
# Flaechen und Schrift
# ---------------------------------------------------------------------------

PAPIER       = ("#f7f7f6", "#14161a")   # Fensterhintergrund
FLAECHE      = ("#eeeeec", "#1c1f25")   # Rahmen, Karten
FLAECHE_HOCH = ("#e5e5e2", "#23272e")   # abgesetzte Bereiche, Reiter
FELD         = ("#ffffff", "#23272e")   # Eingabefelder
LINIE        = ("#dddcd7", "#2d323a")   # Trennlinien, Rahmen
TEXT         = ("#2c3340", "#d2d6dd")   # Fliesstext
GEDAEMPFT    = ("#61697a", "#98a0ac")   # Nebenangaben, Statuszeile

# Seitenleiste. Die Knoepfe dort sind Nebenaktionen - sie bleiben in
# beiden Modi dunkel, damit die weisse Beschriftung aus dem Thema traegt.
SEITE_KNOPF = ("#3f4750", "#37474f")
SEITE_KNOPF_HOVER = ("#333a42", "#263238")

# "Beenden" war rot (#c62828) - fast derselbe Ton wie der Akzent. Damit
# sahen "Suchen" und "Beenden" gleich wichtig aus, und der groesste rote
# Block im Fenster war der, den man am seltensten braucht. Rot bedeutet
# hier ausserdem Gefahr, wo keine ist: das Programm zu schliessen loescht
# nichts. Jetzt ruhig; erkennbar bleibt es durch seine Lage ganz unten.
BEENDEN = ("#565e69", "#3a4048")
BEENDEN_HOVER = ("#4a5158", "#474e58")

# Warnton fuer Aktionen, die etwas abbrechen oder entfernen.
#
# Vorher trugen sie #c62828 - fast genau den Akzent. Damit sah eine
# Warnung aus wie eine Empfehlung: "Entfernen" und "Suchen" waren
# derselbe Knopf in anderer Beschriftung.
#
# Dieser Ton bleibt rot, ist aber eindeutig ein anderes Rot: 19 Grad
# blaustichiger als der Akzent, neun Helligkeitsstufen dunkler und
# weniger gesaettigt. Nebeneinander verwechselt man die beiden nicht,
# und allein gesehen liest es sich trotzdem sofort als Warnung.
# Kontrast zur weissen Schrift: 8.5:1 hell, 7.1:1 dunkel.
WARNUNG = ("#8f2438", "#a32b41")
WARNUNG_HOVER = ("#7a1e2f", "#8f2438")

# Der Dateiname in der Trefferliste war vorher blau (#1f77b4) und sah
# damit aus wie ein Verweis. Er ist aber der Inhalt, auf den es ankommt -
# also die kraeftigste Textfarbe. Die Handlung steckt im Knopf daneben.
DATEINAME = ("#2c3340", "#e6e9eb")

# Hervorhebung der Fundstelle im Vorschautext. Das ist ein tkinter-Tag,
# kein CustomTkinter-Widget - dort ist nur ein einzelner Wert moeglich.
# Der Akzent traegt in beiden Modi.
FUND_HINTERGRUND = "#c1361f"
FUND_TEXT = "#ffffff"

# ---------------------------------------------------------------------------
# Dateityp-Plaketten
# ---------------------------------------------------------------------------
# Vorher sechs volle Material-Design-Toene (#e53935, #1e88e5, #43a047,
# #fb8c00, #757575, #8e24aa). Sechs gesaettigte Farben nebeneinander sind
# das Lauteste im Fenster - und sie stehen an der unwichtigsten Stelle:
# das Dateiformat ist eine Randnotiz, der Dateiname und die Fundstelle
# sind der Inhalt.
#
# Die Unterscheidbarkeit bleibt, die Saettigung geht. Alle sechs liegen
# auf aehnlicher Helligkeit, damit keine Plakette aus der Reihe springt,
# und alle tragen weisse Schrift mit mindestens 5.7:1 Kontrast.
BADGE_FARBEN = {
    ".pdf":  ("#a8412c", "#ffffff"),   # 6.07:1
    ".docx": ("#3d5a80", "#ffffff"),   # 7.06:1
    ".xlsx": ("#4a6b52", "#ffffff"),   # 5.97:1
    ".pptx": ("#8f5a30", "#ffffff"),   # 5.72:1
    ".txt":  ("#5c6470", "#ffffff"),   # 5.98:1
    ".md":   ("#6b5a7d", "#ffffff"),   # 6.21:1
}

# Fuer Endungen, die in der Zuordnung oben nicht vorkommen.
BADGE_RUECKFALL = ("#5c6470", "#ffffff")


# ---------------------------------------------------------------------------
# Das Standardthema ueberschreiben
# ---------------------------------------------------------------------------

def thema_anwenden(ctk):
    """Ersetzt die Farben des CustomTkinter-Themas durch die Markenfarben.

    Muss laufen, bevor das erste Widget entsteht - CustomTkinter liest die
    Werte beim Erzeugen, nicht beim Zeichnen.

    Bewusst kein eigenes Thema als JSON-Datei: die muesste in der
    gebauten .app mitgeliefert und zur Laufzeit gefunden werden. Findet
    CustomTkinter sie nicht, bricht der Start ab. Hier wird stattdessen
    das bereits geladene Thema im Speicher angepasst - schlaegt etwas
    fehl, laeuft das Programm mit dem Standardthema weiter und sieht
    lediglich aus wie vorher.
    """
    aenderungen = {
        "CTk":         {"fg_color": PAPIER},
        "CTkToplevel": {"fg_color": PAPIER},
        "CTkFrame": {
            "fg_color": FLAECHE,
            "top_fg_color": FLAECHE_HOCH,
            "border_color": LINIE,
        },
        "CTkButton": {
            "fg_color": AKZENT,
            "hover_color": AKZENT_HOVER,
            "border_color": LINIE,
            "text_color": AUF_AKZENT,
        },
        "CTkLabel":  {"text_color": TEXT},
        "CTkEntry": {
            "fg_color": FELD,
            "border_color": LINIE,
            "text_color": TEXT,
            "placeholder_text_color": GEDAEMPFT,
        },
        "CTkCheckBox": {
            "fg_color": AKZENT,
            "hover_color": AKZENT_HOVER,
            "border_color": GEDAEMPFT,
            "checkmark_color": AUF_AKZENT,
            "text_color": TEXT,
        },
        "CTkSwitch": {
            "progress_color": AKZENT,
            "text_color": TEXT,
        },
        "CTkRadioButton": {
            "fg_color": AKZENT,
            "hover_color": AKZENT_HOVER,
            "border_color": GEDAEMPFT,
            "text_color": TEXT,
        },
        "CTkProgressBar": {
            "fg_color": LINIE,
            "progress_color": AKZENT,
        },
        "CTkSlider": {
            "button_color": AKZENT,
            "button_hover_color": AKZENT_HOVER,
            "fg_color": LINIE,
        },
        # Bewusst nicht der Akzent. Das Auswahlmenue ist der
        # Zeitraum-Filter - eine Nebeneinstellung. Vorher war es
        # themenblau und damit genauso auffaellig wie "Suchen". Wenn
        # jedes Bedienelement schreit, schreit keines. Der Akzent bleibt
        # der Suche und dem Oeffnen eines Treffers.
        "CTkOptionMenu": {
            "fg_color": FLAECHE_HOCH,
            "button_color": LINIE,
            "button_hover_color": GEDAEMPFT,
            "text_color": TEXT,
        },
        "CTkComboBox": {
            "fg_color": FELD,
            "border_color": LINIE,
            "button_color": LINIE,
            "text_color": TEXT,
        },
        # Achtung, Falle: CustomTkinter hat nur EINE Textfarbe fuer alle
        # Segmente - ausgewaehlte und nicht ausgewaehlte. Ein heller
        # Grund fuer die nicht ausgewaehlten haette dunkle Schrift
        # verlangt, und dieselbe dunkle Schrift stand dann auf dem roten
        # ausgewaehlten Segment: 2.4:1, unlesbar. Deshalb tragen hier
        # alle Segmente weisse Schrift und die nicht ausgewaehlten einen
        # dunklen Grund (5.8:1 hell, 10.5:1 dunkel).
        "CTkSegmentedButton": {
            "fg_color": ("#5f6673", "#3a4048"),
            "selected_color": AKZENT,
            "selected_hover_color": AKZENT_HOVER,
            "unselected_color": ("#5f6673", "#3a4048"),
            "unselected_hover_color": ("#575e6b", "#474e58"),
            "text_color": AUF_AKZENT,
        },
        "CTkTextbox": {
            "fg_color": FELD,
            "border_color": LINIE,
            "text_color": TEXT,
        },
        "CTkScrollableFrame": {"label_fg_color": FLAECHE_HOCH},
        "DropdownMenu": {
            "fg_color": FLAECHE,
            "hover_color": FLAECHE_HOCH,
            "text_color": TEXT,
        },
    }

    try:
        thema = ctk.ThemeManager.theme
    except AttributeError:
        # Andere CustomTkinter-Fassung als erwartet: nichts anfassen.
        return False

    gesetzt = 0
    for widget, werte in aenderungen.items():
        ziel = thema.get(widget)
        if not isinstance(ziel, dict):
            # Dieses Widget kennt die installierte Fassung nicht.
            continue
        for schluessel, wert in werte.items():
            if schluessel in ziel:
                # Als Liste, nicht als Tupel - so speichert CustomTkinter
                # seine Werte selbst, und Vergleiche im Rahmenwerk gehen
                # von Listen aus.
                ziel[schluessel] = list(wert)
                gesetzt += 1

    return gesetzt > 0


# Kleine Selbstpruefung: python3 farben.py zeigt die Kontrastwerte.
if __name__ == "__main__":
    def _helligkeit(hexwert):
        hexwert = hexwert.lstrip("#")
        teile = [int(hexwert[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        teile = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                 for c in teile]
        return 0.2126 * teile[0] + 0.7152 * teile[1] + 0.0722 * teile[2]

    def _kontrast(a, b):
        hoch, tief = sorted((_helligkeit(a), _helligkeit(b)), reverse=True)
        return (hoch + 0.05) / (tief + 0.05)

    print("Plaketten gegen weisse Schrift (Schwelle 4.5:1)")
    for endung, (grund, schrift) in BADGE_FARBEN.items():
        wert = _kontrast(grund, schrift)
        print(f"  {endung:6s} {grund}  {wert:4.2f}:1  "
              f"{'ok' if wert >= 4.5 else 'ZU GERING'}")

    print("\nAkzent gegen weisse Schrift")
    for beschriftung, wert in (("hell", AKZENT[0]), ("dunkel", AKZENT[1])):
        k = _kontrast(wert, "#ffffff")
        print(f"  {beschriftung:7s} {wert}  {k:4.2f}:1  "
              f"{'ok' if k >= 4.5 else 'ZU GERING'}")
