#!/usr/bin/env python3
"""
SmartSearch - Ein kleines Tool, das lokale Dateien "versteht"
und dir erlaubt, in normaler Sprache danach zu suchen.

Backend-Modul: search.py (v3.7 - Robustheits-Fixes)

Änderungen gegenüber v3.6:
- OCR verarbeitet jetzt bis zu OCR_MAX_SEITEN Seiten (statt fest 5) - lange
  gescannte Dokumente werden nicht mehr nach Seite 5 stillschweigend
  abgeschnitten.
- geladenes_modell() ist jetzt Thread-sicher (Lock), falls Suche und
  Indexierung gleichzeitig zum allerersten Mal das Modell laden wollen.
- Dateien, die nicht gelesen werden konnten (kaputtes PDF, leerer Inhalt
  etc.) werden jetzt als "verarbeitet, aber ohne Inhalt" markiert, damit sie
  nicht bei jedem Indexierungslauf erneut (erfolglos) verarbeitet werden.
  Sie tauchen weiterhin nicht in Suchergebnissen auf.
"""

import sys
import os
import json
import pickle
import time
import datetime
import subprocess
import re
import socket
import threading
import math
from concurrent.futures import ThreadPoolExecutor

# Nutzerdaten liegen NICHT mehr neben dem Programmcode, sondern in
# ~/Library/Application Support/SmartSearch - siehe pfade.py fuer die
# ausfuehrliche Begruendung (Updates, Signierung, Schreibrechte).
from pfade import INDEX_FILE, CONFIG_FILE, FAVORITEN_FILE  # noqa: F401

# Texterkennung fuer gescannte PDFs - laeuft ueber Apples Vision-Framework
# statt ueber extern zu installierendes Tesseract/poppler, siehe ocr.py.
import ocr

UNTERSTUETZT = (".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx")

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

MODELL_NAME = "BAAI/bge-m3"

# Formatstand der Indexdatei. Wird hochgezaehlt, wenn sich der AUFBAU eines
# Eintrags aendert - nicht bei jeder Programmfassung.
#
# WARUM es das ueberhaupt gibt: Die Vektoren im Index stammen aus einem
# bestimmten Modell und sind nur mit Vektoren DESSELBEN Modells
# vergleichbar. Wird MODELL_NAME gewechselt - das ist bereits zweimal
# passiert - liefert ein alter Index keine Fehlermeldung, sondern
# stillschweigend falsche Treffer. Deshalb stehen Modellname und
# Formatstand seit Format 2 mit in der Datei und werden beim Laden
# geprueft. Passt etwas nicht, wird der Index verworfen und neu gebaut.
INDEX_FORMAT = 2

# Modellname und Formatstand stehen NEBEN der Indexdatei, nicht darin.
#
# Fassung 1.0.3 hatte sie in die index.pkl selbst geschrieben, als
# Woerterbuch statt als Liste. Das ging in eine Richtung gut und in die
# andere schief: eine aeltere Fassung liest die Datei weiterhin als Liste,
# laeuft dann ueber die Schluessel des Woerterbuchs und stuerzt beim Start
# ab. Ein Update, nach dem die vorherige Fassung nicht mehr startet, ist
# keine Option - schon gar nicht, wenn man zurueckrollen koennen muss.
#
# Deshalb bleibt index.pkl eine reine Liste, wie sie es immer war, und die
# Angaben wandern in eine kleine Datei daneben. Aeltere Fassungen sehen sie
# nicht und arbeiten wie gewohnt; neuere lesen sie und wissen Bescheid.
# Fehlt sie, gilt der Index als unbekannt und wird einmal neu gebaut.
INDEX_META_FILE = INDEX_FILE + ".meta.json"

# Score-Schwelle für suche_intern(): Treffer unterhalb dieses kombinierten
# Semantik+Keyword-Scores werden verworfen. Empirisch ermittelt (v3.x):
# alles darunter waren in Tests fast immer thematisch irrelevante Treffer.
SCORE_SCHWELLE = 0.15

# ------------------------------------------------------------------
# ALLE WERTE HIER UNTEN SIND GEMESSEN, NICHT GESCHAETZT.
#
# Am 14.09.2026 wurden zwoelf Anfragen gegen die zehn Demo-Dokumente
# durchgerechnet und fuer JEDES Dokument der rohe Aehnlichkeitswert
# festgehalten (such_diagnose.py erzeugt diese Tabelle jederzeit neu).
# Ergebnis der alten Einstellung: von den erwarteten Treffern fehlten
# elf. "Verträge", "Drucker", "Waschmaschine" und "Spende fuer die
# Steuererklaerung" ergaben ueberhaupt nichts, obwohl fuer jede dieser
# Anfragen ein eindeutig passendes Dokument im Index liegt.
#
# Die Ursache war eine falsche Annahme ueber das Modell: die frueheren
# Kommentare gingen von Werten um 0,6 fuer unverwandte und bis 0,82 fuer
# sehr aehnliche Texte aus. Gemessen liegt der gesamte Wertebereich auf
# diesen Dokumenten zwischen 0,30 und 0,64 - passende Dokumente bei
# 0,49 bis 0,57, unverwandte bei 0,30 bis 0,47. Alle Grenzen standen
# also ueber dem Bereich, in dem die richtigen Antworten liegen.
#
# Mit den Werten unten und der Wortform-Erkennung in _wort_trifft()
# wird in derselben Messung jeder erwartete Treffer gefunden.
# ------------------------------------------------------------------

# 1. Enthaelt ein Dokument KEINES der Suchwoerter woertlich, muss es
#    semantisch ueberzeugen. Ein Dokument zu finden, in dem das gesuchte
#    Wort GAR NICHT vorkommt, ist der eigentliche Zweck dieser Anwendung -
#    wer "Drucker" sucht, soll auch die Rechnung finden, auf der
#    "Multifunktionssystem" steht. Genau dieser Fall scheiterte vorher:
#    die Rechnung kam auf 0,417 und lag damit unter der alten Sperre von
#    0,60. Der neue Wert liegt unter allen gemessenen richtigen Treffern
#    und ueber dem, was das Modell fuer voellig fremde Texte liefert.
SEMANTIK_MINDEST_OHNE_TREFFER = 0.40

# Nutzbarer Wertebereich des Modells auf echten Dokumenten. Auf diesen
# Bereich wird der rohe Aehnlichkeitswert gespreizt, bevor er mit der
# Stichwortwertung verrechnet wird. Stimmt der Bereich nicht, wird die
# Semantik rechnerisch kleingehalten und die woertliche Suche gewinnt
# immer - vorher lag die Spreizung bei 0,42 bis 0,82, also fast
# vollstaendig oberhalb der tatsaechlichen Werte.
SEMANTIK_UNTERGRENZE = 0.32
SEMANTIK_OBERGRENZE = 0.62

# Verhaeltnis von inhaltlicher zu woertlicher Uebereinstimmung. Wer ein
# Wort eintippt, das woertlich im Dokument steht, erwartet es weit oben -
# deshalb wiegt die Stichwortwertung weiter mit. Sie darf aber nicht so
# schwer wiegen, dass ein woertlicher Treffer alle sinngemaessen
# Treffer aus der Liste draengt: genau das passierte bei 0,45.
GEWICHT_SEMANTIK = 0.65
GEWICHT_STICHWORT = 0.35

# 2. Alles, was klar hinter dem besten Treffer zurueckbleibt, fliegt raus.
#    Selbstjustierend: bei einer guten Anfrage bleiben mehrere Treffer
#    stehen, bei einer schlechten nur der beste - oder gar keiner. Diese
#    Regel erledigt die eigentliche Auslese; die absoluten Schwellen oben
#    halten nur noch offensichtlichen Unsinn fern.
RELATIVER_ABSTAND = 0.65

# Ordnernamen, die NIE mitindexiert werden sollen, egal wo sie im
# durchsuchten Ordnerbaum auftauchen. Das sind App-eigene/Bibliotheks-
# Ordner (venv, Build-Ausgaben, Python-Cache, Git-Interna) - deren
# enthaltene Dateien (z.B. Vorlagen-.docx/.pptx aus installierten
# Bibliotheken) haben mit den eigentlichen Nutzer-Dokumenten nichts zu
# tun, blähen aber den Index unnötig auf und kosten Rechenzeit.
IGNORIERTE_ORDNERNAMEN = {"venv", ".venv", ".git", "__pycache__", "build", "dist", "node_modules"}

# Anzahl paralleler Threads beim Einlesen der Dateien (Text-Extraktion/OCR).
# Diese Arbeit ist größtenteils I/O bzw. läuft in C-Bibliotheken
# (pdfplumber, Tesseract), die während der Arbeit die Python-GIL freigeben -
# paralleles Lesen bringt hier also einen echten Geschwindigkeitsgewinn,
# unabhängig vom CPU-Modus des KI-Modells (siehe lade_modell()).
LESE_THREADS = 4


def lade_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"ordner": []}


def speichere_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def befehl_ordner_hinzufuegen(ordner):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    if not os.path.isdir(ordner):
        print(f"Der Ordner '{ordner}' existiert nicht.")
        return
    config = lade_config()
    if ordner in config["ordner"]:
        return
    config["ordner"].append(ordner)
    speichere_config(config)


def befehl_ordner_entfernen(ordner):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    config = lade_config()
    if ordner not in config["ordner"]:
        return
    config["ordner"].remove(ordner)
    speichere_config(config)

    # WICHTIG: Ein entfernter Ordner muss auch aus dem Index verschwinden.
    # Vorher wurde nur die config.json angepasst - die bereits berechneten
    # Eintraege blieben in index.pkl liegen und tauchten weiter in den
    # Suchergebnissen auf. Genau das war der Fehler "ich finde Dateien aus
    # einem Ordner, den ich laengst entfernt habe".
    entfernt = entferne_ordner_aus_index(ordner)
    if entfernt:
        print(f"[Index] {entfernt} Eintraege aus '{ordner}' entfernt.")


# ---------- FAVORITEN ----------

def lade_favoriten():
    """Gibt die Menge der als Favorit markierten Dateipfade zurück."""
    if os.path.exists(FAVORITEN_FILE):
        try:
            with open(FAVORITEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[Warnung] Favoriten konnten nicht geladen werden: {e}")
            return set()
    return set()


def speichere_favoriten(favoriten):
    try:
        with open(FAVORITEN_FILE, "w") as f:
            json.dump(sorted(favoriten), f, indent=2)
    except Exception as e:
        print(f"[Warnung] Favoriten konnten nicht gespeichert werden: {e}")


def favorit_umschalten(pfad):
    """Fügt pfad zu den Favoriten hinzu oder entfernt ihn.

    Gibt True zurück, wenn die Datei danach ein Favorit ist, sonst False.
    """
    favoriten = lade_favoriten()
    if pfad in favoriten:
        favoriten.remove(pfad)
        ist_favorit = False
    else:
        favoriten.add(pfad)
        ist_favorit = True
    speichere_favoriten(favoriten)
    return ist_favorit


# Ungefaehre Groesse des BGE-M3-Modells auf der Festplatte. Dient NUR
# der Fortschrittsanzeige beim einmaligen Download - ein paar Prozent
# Abweichung sind egal, Hauptsache der Nutzer sieht, dass sich etwas tut.
MODELL_GROESSE_BYTES = 2_270_000_000


class ModellDownloadFehler(Exception):
    """Das Modell liegt noch nicht lokal vor und konnte nicht geladen
    werden - in aller Regel, weil beim allerersten Start keine
    Internetverbindung besteht. Eigene Klasse, damit die GUI diesen einen
    Fall verstaendlich erklaeren kann, statt einen rohen Netzwerkfehler
    anzuzeigen."""


class ProgrammUnvollstaendig(Exception):
    """Ein Baustein fehlt in der ausgelieferten App - nicht das Modell,
    sondern ein Programmteil, der beim Bauen haette mitkopiert werden
    muessen. Der Nutzer kann daran nichts aendern; ein Neuversuch oder
    eine bessere Internetverbindung helfen nicht. Eigene Klasse, damit
    die Oberflaeche das sagt, statt faelschlich auf die Verbindung zu
    zeigen."""


def _modell_cache_ordner():
    """Ordner, in dem huggingface das Modell ablegt. HF_HOME hat Vorrang,
    falls jemand den Cache verschoben hat."""
    basis = os.environ.get("HF_HOME")
    if basis:
        hub = os.path.join(basis, "hub")
    else:
        hub = os.path.expanduser("~/.cache/huggingface/hub")
    return os.path.join(hub, "models--" + MODELL_NAME.replace("/", "--"))


def _ordnergroesse(pfad):
    gesamt = 0
    for wurzel, _, dateien in os.walk(pfad):
        for name in dateien:
            try:
                # Symlinks nicht mitzaehlen: huggingface verlinkt die
                # Snapshot-Dateien auf den blobs-Ordner, sonst waere jede
                # Datei doppelt in der Summe.
                voll = os.path.join(wurzel, name)
                if not os.path.islink(voll):
                    gesamt += os.path.getsize(voll)
            except OSError:
                pass
    return gesamt


def modell_ist_vorhanden():
    """True, wenn das Modell vollstaendig genug lokal liegt, um ohne
    Internet zu starten. Die Groessenschwelle faengt einen frueher
    abgebrochenen Download ab - ein halb geladener Ordner existiert zwar,
    taugt aber nicht."""
    ordner = _modell_cache_ordner()
    if not os.path.isdir(ordner):
        return False
    return _ordnergroesse(ordner) > MODELL_GROESSE_BYTES * 0.9


def _internet_erreichbar(timeout=5):
    try:
        with socket.create_connection(("huggingface.co", 443), timeout=timeout):
            return True
    except OSError:
        return False


def lade_modell(fortschritt_fn=None):
    """Laedt das BGE-M3 KI-Modell.

    WICHTIG: Laeuft bewusst auf der CPU statt auf MPS (Apples GPU-Backend).
    PyTorchs MPS-Speicherverwalter hat einen bekannten Bug, der bei
    laengeren Indexierungslaeufen mit "buffer_block INTERNAL ASSERT FAILED"
    abstuerzt (die ganze App wird dann vom Betriebssystem beendet - "zsh:
    abort"). Auf der CPU ist die Berechnung etwas langsamer, aber stabil.

    fortschritt_fn(geladene_bytes, gesamt_bytes) wird waehrend des
    EINMALIGEN Erst-Downloads regelmaessig aufgerufen. Ohne diese Rueckmeldung
    steht ein neuer Nutzer minutenlang vor einer scheinbar eingefrorenen
    App - das war die haeufigste Stelle, an der Leute die App wieder
    geloescht haben, bevor sie sie ueberhaupt einmal benutzt hatten.

    Wirft ModellDownloadFehler, wenn das Modell fehlt und nicht geladen
    werden kann.
    """
    muss_geladen_werden = not modell_ist_vorhanden()

    if muss_geladen_werden and not _internet_erreichbar():
        raise ModellDownloadFehler(
            "Das KI-Modell wurde noch nicht heruntergeladen und es besteht "
            "keine Internetverbindung."
        )

    beobachter_stoppen = threading.Event()

    def _beobachte_download():
        """Misst waehrend des Downloads einfach die Groesse des Cache-
        Ordners. Bewusst so simpel gehalten statt ueber die internen
        Fortschritts-Hooks von huggingface_hub zu gehen - die aendern sich
        zwischen Versionen, ein Ordner auf der Festplatte nicht."""
        ordner = _modell_cache_ordner()
        while not beobachter_stoppen.wait(1.0):
            try:
                geladen = _ordnergroesse(ordner) if os.path.isdir(ordner) else 0
                fortschritt_fn(geladen, MODELL_GROESSE_BYTES)
            except Exception:
                pass

    beobachter = None
    if muss_geladen_werden and fortschritt_fn is not None:
        beobachter = threading.Thread(target=_beobachte_download, daemon=True)
        beobachter.start()

    try:
        print("Lade KI-Modell (BGE-M3, CPU-Modus)...")
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(MODELL_NAME, device="cpu")
    except ImportError as e:
        # Ein fehlendes Modul ist kein Netzwerkproblem. Frueher landete
        # dieser Fall in der Sammelbehandlung unten und wurde dem Nutzer
        # als "keine Internetverbindung" angezeigt - eine Fehlermeldung,
        # die in die falsche Richtung schickt und nicht loesbar ist.
        raise ProgrammUnvollstaendig(str(e)) from e
    except Exception as e:
        if muss_geladen_werden:
            # Beim Erst-Download ist ein Fehler fast immer ein Netzwerk-
            # oder Speicherplatzproblem - als solches weiterreichen, damit
            # die GUI es erklaeren kann.
            raise ModellDownloadFehler(str(e)) from e
        raise
    finally:
        beobachter_stoppen.set()
        if beobachter is not None:
            beobachter.join(timeout=2)


def lies_datei(pfad):
    ext = os.path.splitext(pfad)[1].lower()
    try:
        if ext in [".txt", ".md"]:
            with open(pfad, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif ext == ".pdf":
            text = ""
            try:
                import pdfplumber
                with pdfplumber.open(pfad) as pdf:
                    seiten_texte = []
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            seiten_texte.append(extracted)
                    text = "\n".join(seiten_texte)
            except Exception as e:
                print(f"[Warnung] pdfplumber fehlgeschlagen bei {pfad}: {e}")

            if not text or len(text.strip()) < 50:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(pfad)
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as e:
                    print(f"[Warnung] pypdf-Fallback fehlgeschlagen bei {pfad}: {e}")

            if not text or len(text.strip()) < 50:
                text = ocr.pdf_text_erkennen(pfad)

            return text
        elif ext == ".docx":
            from docx import Document
            doc = Document(pfad)
            text_teile = [absatz.text for absatz in doc.paragraphs if absatz.text.strip()]

            # WICHTIG: Viele moderne Vorlagen (z.B. Lebenslauf-Layouts mit
            # Spalten für Datum/Firma/Beschreibung) speichern ihren Text in
            # TABELLEN statt in normalen Absätzen. doc.paragraphs erfasst
            # das nicht - solche Dokumente wurden bisher fälschlich als
            # "ohne Inhalt" markiert, obwohl sie voller Text waren.
            for tabelle in doc.tables:
                for zeile in tabelle.rows:
                    for zelle in zeile.cells:
                        for absatz in zelle.paragraphs:
                            if absatz.text.strip():
                                text_teile.append(absatz.text)

            return "\n".join(text_teile)
        elif ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
            text_teile = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    zeilen_text = " ".join(str(cell) for cell in row if cell is not None)
                    if zeilen_text.strip():
                        text_teile.append(zeilen_text)
            return "\n".join(text_teile)
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(pfad)
            text_teile = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text_teile.append(shape.text)
            return "\n".join(text_teile)
        else:
            return None
    except PermissionError:
        # Getrennt behandelt: das ist kein defektes Dokument, sondern eine
        # fehlende Freigabe - dagegen hilft nur die Systemeinstellung.
        print(f"[Hinweis] Keine Leseberechtigung: {pfad}")
        return None
    except Exception as e:
        print(f"[Warnung] Datei konnte nicht gelesen werden: {pfad} ({e})")
        return None


# Groesse der Textabschnitte, die einzeln in einen Bedeutungsvektor
# umgerechnet werden.
#
# Warum klein: Ein Vektor ist im Kern ein Durchschnitt ueber alles, was in
# seinem Abschnitt steht. Bei 700 Zeichen einer Rechnung landen darin
# Absender, Empfaenger, Kundennummer, Zahlungsziel, Steuersatz UND die
# Positionszeile mit dem eigentlichen Artikel. Der Vektor sagt dann nur
# noch "Geschaeftsbrief mit Zahlen" - die Information, worum es
# tatsaechlich geht, verschwindet im Mittelwert.
#
# Bei rund 350 Zeichen bleibt eine Positionszeile ("1 Stk Kyocera ECOSYS
# M2540idn Multifunktionssystem s/w") in einem eigenen Abschnitt und
# behaelt ein eigenes, klares Signal. Das ist der wirksamste einzelne
# Hebel fuer die inhaltliche Suche in formularartigen Dokumenten -
# Rechnungen, Lieferscheinen, Vertraegen mit Anlagenverzeichnis.
#
# Preis: etwa doppelt so viele Abschnitte, also groesserer Index und
# laengere erste Indexierung. Das ist es wert.
ABSCHNITT_GROESSE = 350
ABSCHNITT_UEBERLAPPUNG = 80


def in_abschnitte_teilen(text, groesse=ABSCHNITT_GROESSE, ueberlappung=ABSCHNITT_UEBERLAPPUNG):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=groesse,
            chunk_overlap=ueberlappung,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        return splitter.split_text(text)
    except ImportError:
        # Notfallweg, falls langchain_text_splitters fehlt: grob nach
        # Wortzahl teilen. Rund 50 Woerter entsprechen den 350 Zeichen oben.
        woerter = text.split()
        WOERTER_PRO_ABSCHNITT = 50
        UEBERLAPPUNG_WOERTER = 12
        if len(woerter) <= WOERTER_PRO_ABSCHNITT:
            return [" ".join(woerter)]
        abschnitte = []
        schritt = max(WOERTER_PRO_ABSCHNITT - UEBERLAPPUNG_WOERTER, 1)
        for i in range(0, len(woerter), schritt):
            abschnitte.append(" ".join(woerter[i:i + WOERTER_PRO_ABSCHNITT]))
        return abschnitte


# Wird auf True gesetzt, sobald ein nicht passender Index verworfen wurde -
# damit die Oberflaeche einmal darauf hinweisen kann statt gar nicht.
_index_verworfen = False


def _meta_lesen():
    """Die Angaben neben dem Index - leer, wenn es sie nicht gibt."""
    try:
        with open(INDEX_META_FILE, encoding="utf-8") as f:
            inhalt = json.load(f)
        return inhalt if isinstance(inhalt, dict) else {}
    except Exception:
        return {}


def _meta_schreiben():
    """Schreibt Modellname und Formatstand neben den Index.

    Wird NACH der Indexdatei geschrieben. Geht dabei etwas schief, gilt der
    Index beim naechsten Start als unbekannt und wird neu gebaut - der
    Fehler kostet also Rechenzeit, aber er kann keine falschen Treffer
    erzeugen. Andersherum waere es gefaehrlich.
    """
    try:
        temp_pfad = INDEX_META_FILE + ".tmp"
        with open(temp_pfad, "w", encoding="utf-8") as f:
            json.dump({"format": INDEX_FORMAT, "modell": MODELL_NAME}, f)
        os.replace(temp_pfad, INDEX_META_FILE)
    except Exception as e:
        print(f"[Index] Begleitdatei nicht schreibbar: {e}")


def _index_datei_lesen():
    """Liest index.pkl und gibt (eintraege, passend) zurueck.

    passend ist False, wenn die Datei mit einem anderen Modell oder in
    einem aelteren Format geschrieben wurde. Die Eintraege werden trotzdem
    mitgegeben; was damit geschieht, entscheidet der Aufrufer.
    """
    with open(INDEX_FILE, "rb") as f:
        inhalt = pickle.load(f)

    # Uebergangsfall: Fassung 1.0.3 hat die Angaben in die Datei selbst
    # geschrieben. Solche Indexdateien bleiben lesbar, damit niemand ohne
    # Grund neu indexieren muss.
    if isinstance(inhalt, dict) and "eintraege" in inhalt:
        passend = (inhalt.get("format") == INDEX_FORMAT
                   and inhalt.get("modell") == MODELL_NAME)
        return inhalt.get("eintraege") or [], passend

    eintraege = inhalt if isinstance(inhalt, list) else []
    meta = _meta_lesen()
    passend = (meta.get("format") == INDEX_FORMAT
               and meta.get("modell") == MODELL_NAME)
    return eintraege, passend


def index_ist_fremd():
    """True, wenn eine Indexdatei da ist, die nicht zum aktuellen Modell passt.

    Die Oberflaeche fragt das beim Start ab, um einmal darauf hinzuweisen
    und die Neuindexierung anzustossen - sonst stuende der Benutzer vor
    einer Suche, die grundlos nichts findet.
    """
    if not os.path.exists(INDEX_FILE):
        return False
    try:
        _, passend = _index_datei_lesen()
        return not passend
    except Exception:
        # Unlesbare Datei: wird beim naechsten Indexlauf ohnehin ersetzt.
        return True


def lade_bestehenden_index():
    """Die gespeicherten Eintraege - oder eine leere Liste, wenn der Index
    nicht zum aktuellen Suchmodell passt.

    Leer heisst fuer die Indexierung: alles neu einlesen. Genau das ist
    gewollt, denn Vektoren aus einem anderen Modell sind unbrauchbar.
    """
    global _index_verworfen
    if not os.path.exists(INDEX_FILE):
        return []
    try:
        eintraege, passend = _index_datei_lesen()
    except Exception as e:
        print(f"[Index] Datei nicht lesbar, wird neu aufgebaut: {e}")
        return []
    if not passend:
        if not _index_verworfen:
            print(f"[Index] Passt nicht zum Modell {MODELL_NAME} - wird neu aufgebaut.")
        _index_verworfen = True
        return []
    return eintraege


def speichere_index(eintraege):
    """Speichert den Index atomar: erst in eine temporäre Datei schreiben,
    dann per os.replace() an die Stelle der echten Datei verschieben.

    WICHTIG für die "Suche während der Indexierung"-Funktion: Ohne das
    könnte eine parallel laufende Suche exakt in dem Moment lesen, in dem
    hier gerade geschrieben wird, und eine unvollständige/kaputte Datei
    erwischen. os.replace() ist auf demselben Dateisystem atomar - Leser
    sehen immer entweder die alte oder die neue vollständige Datei, nie
    einen Zwischenzustand.
    """
    global _index_verworfen

    temp_pfad = INDEX_FILE + ".tmp"
    with open(temp_pfad, "wb") as f:
        pickle.dump(eintraege, f)
    os.replace(temp_pfad, INDEX_FILE)

    # Erst danach die Angaben daneben - siehe INDEX_META_FILE oben.
    _meta_schreiben()
    _index_verworfen = False


# Punkt 16 der Liste: sehr grosse Dateien. Eine einzelne 500-MB-PDF kann
# die Indexierung minutenlang blockieren und viel Arbeitsspeicher belegen -
# fuer ein Dokument, das ohnehin fast nie gesucht wird. Solche Dateien
# werden uebersprungen und in der Fehlerliste benannt.
MAX_DATEIGROESSE = 120 * 1024 * 1024  # 120 MB


# Ordner, auf die macOS den Zugriff verweigert hat. Wird bei jedem Lauf
# neu gefuellt und von der GUI ausgelesen, damit der Nutzer erfaehrt,
# warum ein Ordner leer bleibt (Punkt 5 der Liste).
verweigerte_ordner = []


def dateien_im_ordner(ordner):
    gefunden = []
    verweigerte_ordner.clear()

    def bei_fehler(fehler):
        """os.walk meldet Fehler nur ueber diesen Rueckruf - ohne ihn
        werden sie stillschweigend verschluckt."""
        if isinstance(fehler, PermissionError):
            verweigerte_ordner.append(fehler.filename or ordner)
            print(f"[Hinweis] Kein Zugriff auf {fehler.filename} - "
                  f"in den Systemeinstellungen unter Datenschutz erlauben.")
        else:
            print(f"[Warnung] Ordner nicht lesbar: {fehler}")

    for wurzel, unterordner, dateien in os.walk(ordner, onerror=bei_fehler):
        # Ignorierte Unterordner direkt aus der Traversierung entfernen
        # (verändert die Liste in-place, damit os.walk gar nicht erst
        # hineinschaut - schneller als hinterher zu filtern).
        # Safari legt einen unfertigen Download als PAKET an - einen Ordner
        # namens "bericht.pdf.download", in dem die halbe Datei liegt.
        # os.walk lief bisher hinein, fand dort ein angefangenes PDF und
        # meldete es dauerhaft als "nicht lesbar". Es ist aber schlicht ein
        # abgebrochener Download, kein Dokument des Nutzers.
        unterordner[:] = [
            u for u in unterordner
            if u not in IGNORIERTE_ORDNERNAMEN and not u.endswith(".download")
        ]
        for name in dateien:
            # Temporaere Sperrdateien von Word/Excel/PowerPoint ("~$bericht
            # .docx") und macOS-Ressourcendateien ("._datei.pdf") sind keine
            # echten Dokumente. Sie liessen sich nie lesen und landeten
            # deshalb dauerhaft in der Liste der nicht lesbaren Dateien -
            # eine Warnung, gegen die der Nutzer nichts tun kann.
            if name.startswith("~$") or name.startswith("._"):
                continue
            if not name.lower().endswith(UNTERSTUETZT):
                continue
            voller_pfad = os.path.join(wurzel, name)
            try:
                groesse = os.path.getsize(voller_pfad)
                if groesse == 0:
                    # Leere Datei: kein Fehler, nur nichts zu holen. Wurde
                    # bisher als "nicht lesbar" gemeldet und beunruhigte
                    # ohne Anlass.
                    continue
                if groesse > MAX_DATEIGROESSE:
                    print(f"[Hinweis] Uebersprungen, zu gross: {name}")
                    continue
            except OSError:
                # Groesse nicht feststellbar - dann trotzdem versuchen.
                pass
            gefunden.append(voller_pfad)
    return gefunden


def nicht_zugaengliche_ordner():
    """Ordner, die beim letzten Lauf wegen fehlender Berechtigung
    uebersprungen wurden."""
    return list(dict.fromkeys(verweigerte_ordner))


def fehlgeschlagene_dateien():
    """Gibt die Liste aller Dateipfade zurück, die beim letzten
    Indexierungslauf nicht gelesen werden konnten (ohne_inhalt-Flag).

    Für die "⚠️ X Dateien nicht lesbar"-Anzeige in der GUI, damit sowas
    nicht mehr stillschweigend im Terminal verschwindet.
    """
    eintraege = lade_bestehenden_index()
    gesehen = set()
    ergebnis = []
    for e in eintraege:
        if e.get("ohne_inhalt") and e["datei"] not in gesehen:
            gesehen.add(e["datei"])
            ergebnis.append(e["datei"])
    return sorted(ergebnis)


def entferne_fehlgeschlagene_markierung():
    """Entfernt alle 'ohne_inhalt'-Einträge komplett aus dem Index.

    Danach werden diese Dateien beim nächsten aktualisiere_index()-Lauf
    ganz normal erneut versucht (z.B. sinnvoll, nachdem man OCR
    nachinstalliert hat). Gibt die Anzahl der entfernten Einträge zurück.
    """
    eintraege = lade_bestehenden_index()
    verbleibend = [e for e in eintraege if not e.get("ohne_inhalt")]
    entfernt = len(eintraege) - len(verbleibend)
    if entfernt:
        speichere_index(verbleibend)
    return entfernt


def exportiere_konfiguration(zielpfad):
    """Schreibt überwachte Ordner + Favoriten als lesbare JSON-Datei.

    Praktisch als Backup oder um die eigene Einrichtung auf einen anderen
    Mac zu übertragen, ohne den kompletten (oft sehr großen) Suchindex
    mitnehmen zu müssen - der wird beim nächsten 'Index aktualisieren'
    einfach neu aufgebaut.
    """
    daten = {
        "ordner": lade_config().get("ordner", []),
        "favoriten": sorted(lade_favoriten()),
    }
    with open(zielpfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)


def importiere_konfiguration(quellpfad):
    """Liest eine mit exportiere_konfiguration() erzeugte JSON-Datei ein
    und fügt überwachte Ordner + Favoriten zur bestehenden Einrichtung
    hinzu (überschreibt nichts, ergänzt nur). Gibt (anzahl_ordner,
    anzahl_favoriten) aus der importierten Datei zurück."""
    with open(quellpfad, "r", encoding="utf-8") as f:
        daten = json.load(f)

    importierte_ordner = daten.get("ordner", [])
    config = lade_config()
    for ordner in importierte_ordner:
        if ordner not in config["ordner"]:
            config["ordner"].append(ordner)
    speichere_config(config)

    importierte_favoriten = daten.get("favoriten", [])
    favoriten = lade_favoriten()
    favoriten.update(importierte_favoriten)
    speichere_favoriten(favoriten)

    return len(importierte_ordner), len(importierte_favoriten)


def aktualisiere_index(ordner, modell=None, still=False, fortschritt_fn=None):
    ordner = os.path.abspath(os.path.expanduser(ordner))
    alle_eintraege = lade_bestehenden_index()

    eintraege_dieser_ordner = [e for e in alle_eintraege if e["datei"].startswith(ordner + os.sep)]
    andere_eintraege = [e for e in alle_eintraege if not e["datei"].startswith(ordner + os.sep)]

    bekannt = {e["datei"]: e.get("geaendert", 0) for e in eintraege_dieser_ordner}
    aktuelle_dateien = set(dateien_im_ordner(ordner))
    zu_verarbeiten = [p for p in aktuelle_dateien if p not in bekannt or os.path.getmtime(p) > bekannt[p]]

    eintraege_dieser_ordner = [
        e for e in eintraege_dieser_ordner
        if e["datei"] in aktuelle_dateien and e["datei"] not in zu_verarbeiten
    ]

    if not zu_verarbeiten:
        ergebnis = andere_eintraege + eintraege_dieser_ordner
        speichere_index(ergebnis)
        return ergebnis

    if modell is None:
        modell = geladenes_modell()

    neue_eintraege = []

    def _datei_verarbeiten(pfad):
        geaendert = os.path.getmtime(pfad)
        text = lies_datei(pfad)
        return pfad, geaendert, text

    fertig_zaehler = 0
    with ThreadPoolExecutor(max_workers=LESE_THREADS) as pool:
        for pfad, geaendert, text in pool.map(_datei_verarbeiten, zu_verarbeiten):
            fertig_zaehler += 1
            if fortschritt_fn:
                fortschritt_fn(fertig_zaehler, os.path.basename(pfad))

            if not text or not text.strip():
                # Datei konnte nicht gelesen werden oder ist leer (z.B.
                # kaputtes PDF, gescanntes Dokument ohne erkennbaren Text).
                # Trotzdem als "verarbeitet" markieren (mit geaendert-
                # Zeitstempel, aber ohne Vektor), damit sie beim nächsten
                # Lauf nicht erneut - erfolglos - verarbeitet wird. In der
                # Suche taucht sie wegen des fehlenden Vektors nicht auf
                # (siehe suche_intern-Filter). Über fehlgeschlagene_dateien()
                # kann man diese Liste einsehen, über
                # entferne_fehlgeschlagene_markierung() einen Neuversuch
                # erzwingen (z.B. nach nachträglicher OCR-Installation).
                neue_eintraege.append({
                    "datei": pfad,
                    "text": "",
                    "text_fuer_analyse": None,
                    "geaendert": geaendert,
                    "ohne_inhalt": True,
                })
                continue

            dateiname_ohne_endung = os.path.splitext(os.path.basename(pfad))[0]

            for abschnitt in in_abschnitte_teilen(text):
                text_fuer_analyse = f"Dokument: {dateiname_ohne_endung}\nInhalt: {abschnitt}"
                neue_eintraege.append({
                    "datei": pfad,
                    "text": abschnitt,
                    "text_fuer_analyse": text_fuer_analyse,
                    "geaendert": geaendert,
                })

    # KI-Vektoren in kleinen Batches berechnen statt alles auf einmal.
    # Vorher wurde modell.encode() einmal für ALLE gesammelten Textabschnitte
    # aufgerufen - bei vielen Dateien konnte das (besonders im CPU-Modus,
    # siehe lade_modell()) mehrere Minuten dauern, OHNE dass die GUI
    # währenddessen einen Fortschritt anzeigen konnte. Es sah dann so aus,
    # als sei die App eingefroren. Jetzt wird in Batches gerechnet und nach
    # jedem Batch fortschritt_fn(None, ...) aufgerufen, damit die GUI eine
    # eigene, laufende Statusmeldung für diese Phase zeigen kann.
    # Zwischenspeicherung alle SPEICHER_INTERVALL Batches - ermöglicht
    # "Suchen während der Indexierung": statt bis zum kompletten Abschluss
    # (kann bei vielen Dateien über eine Stunde dauern) zu warten, kann man
    # schon nach den ersten fertig verarbeiteten Batches danach suchen,
    # während der Rest im Hintergrund weiterläuft.
    SPEICHER_INTERVALL = 3
    BATCH_GROESSE = 16
    zu_kodierende = [e for e in neue_eintraege if e.get("text_fuer_analyse")]
    if zu_kodierende:
        gesamt_batches = math.ceil(len(zu_kodierende) / BATCH_GROESSE)
        for batch_start in range(0, len(zu_kodierende), BATCH_GROESSE):
            batch = zu_kodierende[batch_start:batch_start + BATCH_GROESSE]
            texte = [e["text_fuer_analyse"] for e in batch]
            vektoren = modell.encode(texte, show_progress_bar=False, normalize_embeddings=True)
            for e, v in zip(batch, vektoren):
                e["vektor"] = v
                del e["text_fuer_analyse"]

            aktueller_batch = batch_start // BATCH_GROESSE + 1
            if fortschritt_fn:
                # idx=None signalisiert der GUI: das ist die Berechnungs-
                # Phase, nicht ein neu gelesenes Dokument - siehe gui.py.
                fortschritt_fn(None, f"Berechne KI-Vektoren (Batch {aktueller_batch}/{gesamt_batches})...")

            ist_letzter_batch = aktueller_batch == gesamt_batches
            if aktueller_batch % SPEICHER_INTERVALL == 0 or ist_letzter_batch:
                fertige_eintraege = [
                    e for e in neue_eintraege
                    if "vektor" in e or e.get("ohne_inhalt")
                ]
                zwischenstand = andere_eintraege + eintraege_dieser_ordner + fertige_eintraege
                speichere_index(zwischenstand)

    for e in neue_eintraege:
        e.pop("text_fuer_analyse", None)

    eintraege_dieser_ordner.extend(neue_eintraege)
    gesamt = andere_eintraege + eintraege_dieser_ordner
    speichere_index(gesamt)

    return gesamt


def datei_oeffnen(pfad):
    import platform
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", pfad], check=True)
        elif system == "Windows":
            os.startfile(pfad)
        else:
            subprocess.run(["xdg-open", pfad], check=True)
    except Exception as e:
        print(f"Fehler beim Öffnen: {e}")


_modell_cache = None
_modell_lock = threading.Lock()


def geladenes_modell(fortschritt_fn=None):
    """Lädt das Modell einmalig und cached es (Thread-sicher).

    Ohne den Lock könnten Suche und Indexierung, wenn sie gleichzeitig zum
    allerersten Mal starten, beide parallel lade_modell() aufrufen und das
    Modell doppelt laden (unnötiger Speicher-/Zeitverbrauch, im schlimmsten
    Fall doppelte Downloads beim ersten Start).
    """
    global _modell_cache
    if _modell_cache is None:
        with _modell_lock:
            if _modell_cache is None:  # Doppelt geprüft: evtl. hat ein
                # anderer Thread es inzwischen schon geladen, während wir
                # auf den Lock gewartet haben.
                _modell_cache = lade_modell(fortschritt_fn=fortschritt_fn)
    return _modell_cache


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
        for treffer in re.finditer(re.escape(form), heuhaufen):
            anfang, ende = treffer.start(), treffer.end()
            am_wortanfang = anfang == 0 or not heuhaufen[anfang - 1].isalnum()
            am_wortende = ende >= len(heuhaufen) or not heuhaufen[ende].isalnum()
            if am_wortanfang or am_wortende:
                return True
    return False


def _zeitraum_cutoff(zeitraum):
    """Wandelt eine Zeitraum-Auswahl der GUI in einen Unix-Timestamp um,
    ab dem eine Datei als 'im Zeitraum' gilt. None = kein Filter.

    Erwartet einen SPRACHUNABHÄNGIGEN Code ("alle"/"7_tage"/"monat"/"jahr"),
    keinen angezeigten Text - seit es die App auf Deutsch UND Englisch gibt,
    würde ein Vergleich gegen den sichtbaren Menütext (z.B. "7 Tage") in der
    englischen Oberfläche ("7 Days") nie mehr treffen. Die GUI übersetzt die
    Auswahl in gui.py über ZEITRAUM_CODES in einen dieser Codes, bevor sie
    hier ankommt."""
    if not zeitraum or zeitraum == "alle":
        return None

    heute = datetime.date.today()
    if zeitraum == "7_tage":
        return time.time() - 7 * 86400
    elif zeitraum == "monat":
        start = datetime.date(heute.year, heute.month, 1)
        return time.mktime(start.timetuple())
    elif zeitraum == "jahr":
        start = datetime.date(heute.year, 1, 1)
        return time.mktime(start.timetuple())
    return None


# ------------------------------------------------------------------
# GUELTIGKEIT VON INDEX-EINTRAEGEN
#
# Der Index (index.pkl) ist ein Langzeitspeicher: einmal eingelesene
# Dateien bleiben dort stehen, bis sie ausdruecklich entfernt werden.
# Was in der config.json steht, ist dagegen die AKTUELLE Auswahl des
# Nutzers. Beides kann auseinanderlaufen - ein Ordner wird entfernt, eine
# Datei geloescht oder verschoben. Wird das beim Suchen nicht abgeglichen,
# zeigt SmartSearch Treffer aus Ordnern, die der Nutzer laengst entfernt
# hat. Deshalb laeuft jede Suche durch _nur_gueltige_eintraege().
# ------------------------------------------------------------------

def ueberwachte_ordner():
    """Aktuell in der config.json eingetragene Ordner, absolut."""
    return [
        os.path.abspath(os.path.expanduser(o))
        for o in lade_config().get("ordner", [])
    ]


def _liegt_in_ordnern(pfad, ordner_liste):
    for o in ordner_liste:
        if pfad == o or pfad.startswith(o + os.sep):
            return True
    return False


def entferne_ordner_aus_index(ordner):
    """Loescht alle Index-Eintraege unterhalb von 'ordner'.

    Rueckgabe: Anzahl der entfernten Eintraege (Textabschnitte, nicht
    Dateien).
    """
    ordner = os.path.abspath(os.path.expanduser(ordner))
    eintraege = lade_bestehenden_index()
    uebrig = [
        e for e in eintraege
        if not (e["datei"] == ordner or e["datei"].startswith(ordner + os.sep))
    ]
    if len(uebrig) != len(eintraege):
        speichere_index(uebrig)
    return len(eintraege) - len(uebrig)


def bereinige_index():
    """Wirft alles aus dem Index, was nicht mehr gilt: Eintraege ausserhalb
    der ueberwachten Ordner und Dateien, die es nicht mehr gibt.

    Wird nach jedem Indexlauf aufgerufen, damit die Datei nicht endlos
    waechst und keine Karteileichen enthaelt.
    """
    ordner_liste = ueberwachte_ordner()
    eintraege = lade_bestehenden_index()
    if not eintraege:
        return 0

    existiert = {}
    uebrig = []
    for e in eintraege:
        pfad = e["datei"]
        if not _liegt_in_ordnern(pfad, ordner_liste):
            continue
        if pfad not in existiert:
            existiert[pfad] = os.path.exists(pfad)
        if existiert[pfad]:
            uebrig.append(e)

    if len(uebrig) != len(eintraege):
        speichere_index(uebrig)
    return len(eintraege) - len(uebrig)


_such_cache = None                  # (kennung, eintraege, matrix)
_such_cache_lock = threading.Lock()

# Oberhalb dieser Groesse wird der Index NICHT im Arbeitsspeicher
# behalten - ein Suchwerkzeug darf nicht mehrere Gigabyte belegen, nur um
# ein paar Zehntelsekunden zu sparen.
CACHE_OBERGRENZE_BYTES = 1_500_000_000


def _index_mit_matrix():
    """Gibt (eintraege, matrix) zurueck - den Index im Arbeitsspeicher.

    WARUM: Vorher las JEDE Suche die komplette index.pkl neu von der
    Platte und rechnete das Skalarprodukt anschliessend in einer
    Python-Schleife, einmal pro Textabschnitt. Beides waechst mit der
    Anzahl indexierter Dateien - bei einem groesseren Index vergehen
    dadurch mehrere Sekunden, bevor ueberhaupt gerechnet wird, und zwar
    bei jeder einzelnen Suche.

    Jetzt wird die Datei nur dann neu gelesen, wenn sie sich seit dem
    letzten Mal geaendert hat (Zeitstempel + Groesse), und alle Vektoren
    liegen zusaetzlich als eine einzige Zahlenmatrix bereit. Der Vergleich
    mit der Suchanfrage ist damit EINE Matrixmultiplikation statt
    zehntausender Einzelaufrufe.

    Der Zeitstempel-Vergleich ist die Verbindung zur Indexierung: sobald
    sie eine neue index.pkl geschrieben hat (siehe speichere_index, das
    atomar arbeitet), liest die naechste Suche automatisch die neue
    Fassung - ohne Neustart der App.
    """
    global _such_cache
    import numpy as np

    try:
        angaben = os.stat(INDEX_FILE)
        kennung = (angaben.st_mtime_ns, angaben.st_size)
    except OSError:
        return [], None

    with _such_cache_lock:
        if _such_cache is not None and _such_cache[0] == kennung:
            return _such_cache[1], _such_cache[2]

        eintraege, passend = _index_datei_lesen()
        if not passend:
            # Fremder Index: lieber keine Treffer als falsche. Der naechste
            # Indexlauf baut ihn neu auf.
            return [], None

        # Eintraege ohne Vektor (z.B. Dateien, die beim Indexieren nicht
        # gelesen werden konnten) lassen sich nicht durchsuchen.
        eintraege = [e for e in eintraege if "vektor" in e]

        matrix = None
        if eintraege:
            try:
                matrix = np.asarray([e["vektor"] for e in eintraege], dtype="float32")
            except Exception as e:
                # Ein alter Index mit unterschiedlich langen Vektoren laesst
                # sich nicht stapeln. Dann lieber ohne Matrix weiterarbeiten
                # als die Suche ganz scheitern lassen.
                print(f"[Suche] Vektormatrix nicht baubar: {e}")
                matrix = None

        if angaben.st_size <= CACHE_OBERGRENZE_BYTES:
            _such_cache = (kennung, eintraege, matrix)
        else:
            _such_cache = None

        return eintraege, matrix


def _gueltige_paare(paare):
    """Wie _nur_gueltige_eintraege, arbeitet aber auf (Position, Eintrag)-
    Paaren. Die Position wird fuer den Zugriff auf die Vektormatrix
    gebraucht (siehe _index_mit_matrix)."""
    ordner_liste = ueberwachte_ordner()
    if not ordner_liste:
        return []

    existiert = {}
    ergebnis = []
    for i, e in paare:
        pfad = e["datei"]
        if not _liegt_in_ordnern(pfad, ordner_liste):
            continue
        if pfad not in existiert:
            existiert[pfad] = os.path.exists(pfad)
        if existiert[pfad]:
            ergebnis.append((i, e))
    return ergebnis


def _nur_gueltige_eintraege(eintraege):
    """Filtert eine frisch geladene Index-Liste auf das, was gerade zaehlt.

    Bewusst nur gefiltert und NICHT gespeichert: eine Suche darf den Index
    nie veraendern (es kann parallel indexiert werden). Das echte
    Aufraeumen uebernimmt bereinige_index() nach dem Indexlauf.
    """
    ordner_liste = ueberwachte_ordner()
    if not ordner_liste:
        return []

    existiert = {}
    ergebnis = []
    for e in eintraege:
        pfad = e["datei"]
        if not _liegt_in_ordnern(pfad, ordner_liste):
            continue
        if pfad not in existiert:
            existiert[pfad] = os.path.exists(pfad)
        if existiert[pfad]:
            ergebnis.append(e)
    return ergebnis


def suche_intern(anfrage, top_n=10, ausgeschlossene_typen=None, zeitraum=None):
    if not os.path.exists(INDEX_FILE):
        return None

    import numpy as np

    # Index aus dem Arbeitsspeicher statt von der Platte - siehe
    # _index_mit_matrix(). Jeder Eintrag behaelt seine Position im
    # Gesamtindex, weil darueber gleich der fertig berechnete
    # Aehnlichkeitswert abgegriffen wird.
    alle_eintraege, matrix = _index_mit_matrix()
    if not alle_eintraege:
        return []

    paare = list(enumerate(alle_eintraege))

    # Nur Treffer aus Ordnern, die JETZT ueberwacht werden, und nur
    # Dateien, die es noch gibt (siehe _gueltige_paare).
    paare = _gueltige_paare(paare)

    if ausgeschlossene_typen:
        paare = [
            (i, e) for i, e in paare
            if os.path.splitext(e["datei"])[1].lower() not in ausgeschlossene_typen
        ]

    cutoff = _zeitraum_cutoff(zeitraum)
    if cutoff is not None:
        paare = [(i, e) for i, e in paare if e.get("geaendert", 0) >= cutoff]

    if not paare:
        return []

    modell = geladenes_modell()
    anfrage_vektor = np.asarray(
        modell.encode([anfrage], normalize_embeddings=True)[0], dtype="float32")
    such_woerter = anfrage_woerter(anfrage)

    # EINE Matrixmultiplikation fuer den gesamten Index statt eines
    # np.dot() je Textabschnitt. Faellt die Matrix aus (alter Index mit
    # uneinheitlichen Vektoren), wird wie frueher einzeln gerechnet.
    if matrix is not None:
        alle_werte = matrix @ anfrage_vektor
    else:
        alle_werte = None

    # ------------------------------------------------------------------
    # Bewertung auf DOKUMENTEBENE, nicht je Textabschnitt.
    #
    # Der Fehler vorher: Jeder 700-Zeichen-Abschnitt wurde einzeln bewertet,
    # auch bei der Stichwortsuche. Bei einer Rechnung steht "Rechnung" aber
    # im Briefkopf und die Artikelbezeichnung ("Drucker", ein Modellname)
    # weiter unten in der Positionsliste - also in einem ANDEREN Abschnitt.
    # Kein einzelner Abschnitt enthielt beide Suchwoerter, deshalb bekam das
    # Dokument nie die volle Stichwort-Wertung und landete hinter
    # thematisch aehnlichen Dokumenten, die gar keines der Woerter
    # enthielten.
    #
    # Jetzt gilt: der semantische Wert stammt vom BESTEN Abschnitt, die
    # Stichwort-Wertung vom GESAMTEN Dokument.
    # ------------------------------------------------------------------
    nach_datei = {}
    for i, e in paare:
        eintrag_liste = nach_datei.setdefault(e["datei"], [])
        eintrag_liste.append((i, e))

    rohe_treffer = []
    for pfad, abschnitte in nach_datei.items():
        bester_abschnitt = None
        bester_semantik = -1.0
        for i, e in abschnitte:
            if alle_werte is not None:
                wert = float(alle_werte[i])
            else:
                wert = float(np.dot(anfrage_vektor, e["vektor"]))
            if wert > bester_semantik:
                bester_semantik = wert
                bester_abschnitt = e

        dateiname = os.path.basename(pfad).lower()
        gesamttext = " ".join(e.get("text", "") for _, e in abschnitte).lower()

        gefundene_woerter = 0
        im_dateinamen = 0
        if such_woerter:
            for w in such_woerter:
                if wort_trifft(w, dateiname):
                    gefundene_woerter += 1
                    im_dateinamen += 1
                elif wort_trifft(w, gesamttext):
                    gefundene_woerter += 1

        # Semantik auf 0..1 spreizen. BGE-M3 liefert selbst fuer voellig
        # unverwandte Texte noch Werte um 0,55 - der rohe Wert nutzt also
        # nur einen schmalen Ausschnitt der Skala. Ohne diese Spreizung
        # faellt ein Unterschied von 0,05 gegenueber der Stichwortwertung
        # kaum ins Gewicht, obwohl er inhaltlich erheblich ist.
        semantik_norm = (bester_semantik - SEMANTIK_UNTERGRENZE) / (
            SEMANTIK_OBERGRENZE - SEMANTIK_UNTERGRENZE)
        semantik_norm = max(0.0, min(1.0, semantik_norm))

        if such_woerter:
            stichwort_norm = gefundene_woerter / len(such_woerter)
            # Steht ein Wort im Dateinamen, ist das ein besonders klares
            # Signal - ein Mensch benennt Dateien nach ihrem Zweck.
            stichwort_norm = min(1.0, stichwort_norm + 0.15 * im_dateinamen)
        else:
            stichwort_norm = 0.0

        if such_woerter:
            gesamt_score = (GEWICHT_SEMANTIK * semantik_norm
                            + GEWICHT_STICHWORT * stichwort_norm)
        else:
            gesamt_score = semantik_norm

        # Kein einziges Suchwort im gesamten Dokument und semantisch nur
        # mittelmaessig - dann lieber nichts anzeigen als etwas Falsches.
        if such_woerter and gefundene_woerter == 0 and bester_semantik < SEMANTIK_MINDEST_OHNE_TREFFER:
            continue

        if gesamt_score > SCORE_SCHWELLE:
            rohe_treffer.append((gesamt_score, bester_abschnitt))

    rohe_treffer.sort(key=lambda x: x[0], reverse=True)

    # Abstand zum besten Treffer auswerten - siehe RELATIVER_ABSTAND.
    if rohe_treffer:
        mindestwert = rohe_treffer[0][0] * RELATIVER_ABSTAND
        rohe_treffer = [p for p in rohe_treffer if p[0] >= mindestwert]

    return rohe_treffer[:top_n]



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
            for treffer in re.finditer(re.escape(form), text_klein):
                anfang, ende = treffer.start(), treffer.end()
                am_wortanfang = anfang == 0 or not text_klein[anfang - 1].isalnum()
                am_wortende = ende >= len(text_klein) or not text_klein[ende].isalnum()
                if am_wortanfang or am_wortende:
                    stellen.append((anfang, ende))
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


def aehnliche_dateien(pfad, top_n=10):
    """Findet Dateien, die INHALTLICH ähnlich zu 'pfad' sind - per
    Vektor-Ähnlichkeit statt nur Dateiname-Textsuche.

    Nutzt den bereits vorhandenen Embedding-Vektor der Datei aus dem Index
    (kein neuer API-Call/keine neue Berechnung nötig) und vergleicht ihn
    per Kosinus-Ähnlichkeit (Skalarprodukt, da alle Vektoren normalisiert
    sind) gegen alle anderen indexierten Dateien.

    Gibt eine Liste von (score, eintrag) zurück, im selben Format wie
    suche_intern(), damit die GUI dieselbe Ergebnisanzeige wiederverwenden
    kann. None, wenn die Datei nicht (mit Vektor) im Index ist.
    """
    if not os.path.exists(INDEX_FILE):
        return None

    import numpy as np

    pfad = os.path.abspath(os.path.expanduser(pfad))

    # Denselben Arbeitsspeicher-Index benutzen wie die Suche.
    eintraege, _ = _index_mit_matrix()
    eintraege = _nur_gueltige_eintraege(eintraege)

    eigene_vektoren = [e["vektor"] for e in eintraege if e["datei"] == pfad]
    if not eigene_vektoren:
        return None

    # Bei mehreren Textabschnitten derselben Datei: Durchschnittsvektor als
    # Repräsentation der ganzen Datei verwenden.
    referenz_vektor = np.mean(eigene_vektoren, axis=0)
    referenz_vektor = referenz_vektor / np.linalg.norm(referenz_vektor)

    rohe_treffer = []
    for e in eintraege:
        if e["datei"] == pfad:
            continue  # Datei nicht mit sich selbst vergleichen
        score = float(np.dot(referenz_vektor, e["vektor"]))
        rohe_treffer.append((score, e))

    rohe_treffer.sort(key=lambda x: x[0], reverse=True)

    gesehene_dateien = set()
    eindeutige_ergebnisse = []
    for score, eintrag in rohe_treffer:
        datei_pfad = eintrag["datei"]
        if datei_pfad not in gesehene_dateien:
            gesehene_dateien.add(datei_pfad)
            eindeutige_ergebnisse.append((score, eintrag))
        if len(eindeutige_ergebnisse) >= top_n:
            break

    return eindeutige_ergebnisse


def main():
    if len(sys.argv) < 2:
        return
    befehl = sys.argv[1]
    if befehl == "ordner" and len(sys.argv) >= 3 and sys.argv[2] == "hinzufuegen":
        befehl_ordner_hinzufuegen(sys.argv[3])


if __name__ == "__main__":
    main()