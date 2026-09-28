#!/usr/bin/env python3
"""
ocr.py - Texterkennung fuer eingescannte PDFs.

WARUM ES DIESE DATEI GIBT
-------------------------
Vorher lief OCR ueber pdf2image + pytesseract. Beide sind nur duenne
Python-Huellen um Programme, die man SEPARAT ueber Homebrew installieren
muss (poppler bzw. tesseract samt Sprachpaketen). Auf dem Entwicklungs-Mac
sind die vorhanden - auf dem Mac eines normalen Nutzers nicht. In der
gebauten .app waere OCR also bei praktisch jedem Nutzer still
fehlgeschlagen: der Fehler wurde abgefangen, es kam leerer Text zurueck,
und gescannte Dokumente wurden einfach nie gefunden. Ohne jede Meldung.

Dazu kam ein Lizenzproblem: poppler steht unter der GPL. Es mit einer
spaeter kommerziellen, nicht quelloffenen App auszuliefern, waere ein
echter Konflikt gewesen.

DER NEUE WEG
------------
1. Seiten rendern: pypdfium2 - ein normales pip-Paket mit eingebauter
   PDF-Engine (BSD/Apache). Kein Homebrew, keine GPL, laesst sich von
   PyInstaller sauber mitverpacken.
2. Text erkennen: Apples Vision-Framework, das in macOS eingebaut ist und
   ueber PyObjC angesprochen wird. Es ist schneller als Tesseract, erkennt
   deutlich zuverlaessiger und braucht keinerlei Zusatzinstallation.

Wenn auf einem Rechner doch pytesseract vorhanden ist, wird es als
Notnagel weiter genutzt - wer die alte Umgebung hat, verliert nichts.

Installation der beiden benoetigten Pakete:
    pip install pypdfium2 pyobjc-framework-Vision
"""

import io
import os
import threading

# Wie viele Seiten eines gescannten PDFs maximal durch die Texterkennung
# laufen. Schuetzt davor, dass ein einzelnes 400-Seiten-Scan-Dokument die
# gesamte Indexierung blockiert.
OCR_MAX_SEITEN = 30

# Aufloesung, mit der Seiten vor der Erkennung gerendert werden.
# Vision arbeitet bei 300 DPI bereits sehr zuverlaessig - hoehere Werte
# kosten vor allem Zeit und Arbeitsspeicher, ohne die Erkennung noch
# spuerbar zu verbessern (Tesseract brauchte dafuer frueher 400).
OCR_DPI = 300

# pdfium (die PDF-Engine in pypdfium2) ist NICHT threadsicher. Die
# Indexierung liest aber mit mehreren Threads gleichzeitig (siehe
# LESE_THREADS in indexierung.py). Zwei Scans gleichzeitig zu rendern hat
# Python am 28.09.2026 auf dem Mac hart abstuerzen lassen (SIGABRT, ohne
# jede Fehlermeldung) - aufgefallen erst mit dem Testset, das neun Scans
# enthaelt; mit einem einzelnen Scan passiert es nie.
# Deshalb laeuft JEDER Aufruf von pdfium durch diese Sperre. Die eigentliche
# Texterkennung (Vision, Tesseract) laeuft ausserhalb und bleibt parallel.
_PDFIUM_SPERRE = threading.Lock()


# ---------------------------------------------------------------------------
# Verfuegbarkeit
# ---------------------------------------------------------------------------

def _pruefe_vision():
    try:
        import Vision  # noqa: F401
        from Foundation import NSData  # noqa: F401
        return True
    except Exception:
        return False


def _pruefe_pdfium():
    try:
        import pypdfium2  # noqa: F401
        return True
    except Exception:
        return False


def _pruefe_tesseract():
    """Nur der Notnagel-Pfad. Prueft nicht nur den Python-Import, sondern
    auch, ob das tesseract-Programm ueberhaupt erreichbar ist - genau
    dieser Unterschied war der urspruengliche Fehler."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


_engine_ergebnis = []
_engine_sperre = threading.Lock()


def verfuegbare_engine():
    """Gibt zurueck, womit OCR aktuell laeuft: "vision", "tesseract" oder
    None. Die GUI zeigt das im Hilfe-Tab an, damit fehlende Texterkennung
    nie wieder unbemerkt bleibt.

    Wird nur einmal ermittelt: Die Pruefung importiert PyObjC/Vision bzw.
    startet tesseract - das soll nicht bei jedem Scan neu passieren und
    schon gar nicht in mehreren Lese-Threads gleichzeitig."""
    with _engine_sperre:
        if not _engine_ergebnis:
            if _pruefe_pdfium() and _pruefe_vision():
                _engine_ergebnis.append("vision")
            elif _pruefe_tesseract():
                _engine_ergebnis.append("tesseract")
            else:
                _engine_ergebnis.append(None)
        return _engine_ergebnis[0]


def _seiten_als_bilder(pfad):
    """Rendert die Seiten eines PDFs nacheinander als Bilder - jeder
    pdfium-Aufruf unter _PDFIUM_SPERRE. Als Generator, damit nie mehr als
    eine Seite (bei 300 dpi rund 25 MB) im Speicher liegt."""
    import pypdfium2 as pdfium

    with _PDFIUM_SPERRE:
        dokument = pdfium.PdfDocument(pfad)
        seitenzahl = min(len(dokument), OCR_MAX_SEITEN)
    try:
        for i in range(seitenzahl):
            with _PDFIUM_SPERRE:
                seite = dokument[i]
                bild = seite.render(scale=OCR_DPI / 72).to_pil().copy()
                seite.close()
            yield bild
    finally:
        with _PDFIUM_SPERRE:
            try:
                dokument.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Weg 1: pypdfium2 + Apple Vision
# ---------------------------------------------------------------------------

def _vision_text_aus_png(png_bytes, sprachen=("de-DE", "en-US")):
    """Schickt ein Seitenbild durch Apples Texterkennung.

    Vision liefert das Ergebnis als Liste erkannter Textbereiche, jeweils
    mit mehreren Kandidaten nach Konfidenz sortiert - genommen wird immer
    der beste.
    """
    import Vision
    from Foundation import NSData

    daten = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(daten, None)

    anfrage = Vision.VNRecognizeTextRequest.alloc().init()
    # 0 = "accurate". Die schnelle Stufe (1) ist bei Fliesstext aus Scans
    # spuerbar schlechter, und Geschwindigkeit ist hier nicht das Problem.
    anfrage.setRecognitionLevel_(0)
    anfrage.setUsesLanguageCorrection_(True)
    try:
        anfrage.setRecognitionLanguages_(list(sprachen))
    except Exception:
        # Aeltere macOS-Versionen kennen nicht jede Sprachkennung. Dann
        # ohne explizite Vorgabe weitermachen, statt ganz aufzugeben.
        pass

    erfolg, fehler = handler.performRequests_error_([anfrage], None)
    if not erfolg:
        raise RuntimeError(f"Vision-Anfrage fehlgeschlagen: {fehler}")

    ergebnisse = anfrage.results() or []
    zeilen = []
    for beobachtung in ergebnisse:
        kandidaten = beobachtung.topCandidates_(1)
        if kandidaten and len(kandidaten) > 0:
            text = kandidaten[0].string()
            if text:
                zeilen.append(str(text))
    return "\n".join(zeilen)


def _ocr_mit_vision(pfad):
    try:
        import objc
        pool = objc.autorelease_pool
    except Exception:
        pool = None

    teile = []
    for bild in _seiten_als_bilder(pfad):
        puffer = io.BytesIO()
        bild.save(puffer, format="PNG")

        # Autorelease-Pool pro Seite: ohne ihn sammeln sich die von
        # Vision erzeugten Objective-C-Objekte an, bis ein grosser
        # Indexierungslauf den Speicher vollaeuft.
        if pool is not None:
            with pool():
                text = _vision_text_aus_png(puffer.getvalue())
        else:
            text = _vision_text_aus_png(puffer.getvalue())

        if text.strip():
            teile.append(text)
    return "\n".join(teile)


# ---------------------------------------------------------------------------
# Weg 2: der alte Tesseract-Pfad (nur noch Notnagel)
# ---------------------------------------------------------------------------

def _bild_fuer_tesseract_aufbereiten(bild):
    """Graustufen + Kontrastanhebung. Hilft Tesseract bei blassen Scans
    deutlich - fuer Vision ist beides unnoetig, dort schadet Vorverarbeitung
    eher, weil das Modell auf normale Seitenbilder trainiert ist."""
    from PIL import ImageEnhance
    graustufen = bild.convert("L")
    return ImageEnhance.Contrast(graustufen).enhance(1.6)


def _ocr_mit_tesseract(pfad):
    import pytesseract

    # Seiten bevorzugt mit pypdfium2 rendern - dann wird poppler auch auf
    # dem Notnagel-Pfad nicht mehr gebraucht.
    if _pruefe_pdfium():
        bilder = _seiten_als_bilder(pfad)
    else:
        from pdf2image import convert_from_path
        bilder = convert_from_path(pfad, first_page=1, last_page=OCR_MAX_SEITEN, dpi=OCR_DPI)

    teile = []
    for bild in bilder:
        text = pytesseract.image_to_string(_bild_fuer_tesseract_aufbereiten(bild), lang="deu+eng")
        if text.strip():
            teile.append(text)
    return "\n".join(teile)


# ---------------------------------------------------------------------------
# Oeffentliche Schnittstelle
# ---------------------------------------------------------------------------

def pdf_text_erkennen(pfad):
    """Liest Text aus einem PDF, aus dem sich kein Text direkt extrahieren
    laesst (also einem Scan). Gibt bei Misserfolg einen leeren String
    zurueck - der Aufrufer behandelt die Datei dann wie eine ohne Inhalt.
    """
    engine = verfuegbare_engine()

    if engine == "vision":
        try:
            return _ocr_mit_vision(pfad)
        except Exception as e:
            print(f"[Warnung] Texterkennung (Vision) fehlgeschlagen bei {os.path.basename(pfad)}: {e}")
            # Nicht sofort aufgeben: wenn zusaetzlich Tesseract da ist,
            # bekommt die Datei darueber noch eine zweite Chance.
            if _pruefe_tesseract():
                engine = "tesseract"
            else:
                return ""

    if engine == "tesseract":
        try:
            return _ocr_mit_tesseract(pfad)
        except Exception as e:
            print(f"[Warnung] Texterkennung (Tesseract) fehlgeschlagen bei {os.path.basename(pfad)}: {e}")
            return ""

    print(
        "[Hinweis] Keine Texterkennung verfuegbar - gescannte PDFs werden uebersprungen. "
        "Abhilfe: pip install pypdfium2 pyobjc-framework-Vision"
    )
    return ""
