#!/usr/bin/env python3
"""
modell.py - das KI-Suchmodell: laden und im Speicher halten.

SEIT HERBST 2026: granite-embedding ueber onnxruntime statt BGE-M3 ueber
PyTorch.

Warum der Wechsel
-----------------
1. PyTorch gibt es fuer Macs mit Intel-Prozessor nicht mehr in einer
   aktuellen Fassung (letzte: 2.2.2, ohne Python 3.13). onnxruntime laeuft
   auf Mac (Apple-Chip und Intel) und Windows mit derselben Fassung.
2. Groesse: BGE-M3 wog 2,27 GB und wurde beim ersten Start aus dem Netz
   geladen. granite-embedding-97m-multilingual-r2 wiegt als int8-ONNX rund
   100 MB und wird MIT DER APP AUSGELIEFERT. Es gibt keinen Download mehr,
   keine Verbindung zu huggingface.co, auch nicht beim ersten Start. Fuer
   Kanzleien ("nichts verlaesst den Rechner") ist das ein Argument, fuer
   Rechner ohne Internet die Voraussetzung.
3. Lizenz: Apache-2.0, kommerziell ohne Auflagen nutzbar.

Wie die anderen Teile es benutzen
---------------------------------
Unveraendert: geladenes_modell().encode(texte, normalize_embeddings=True)
liefert eine Zahlenmatrix, eine Zeile je Text. Suche und Indexierung
merken vom Wechsel nichts. Der Index merkt es an MODELL_NAME (siehe
kern/index.py) und wird beim ersten Start einmal neu aufgebaut.

Woher die Modelldateien kommen
------------------------------
Sie liegen in ressourcen/modell/<Ordner>/ und gehoeren NICHT ins
Git-Repository (100 MB). Geholt werden sie einmalig mit

    venv/bin/python -m werkzeuge.modell_holen

bauen/mac/build.sh packt sie in die App.
"""

import os
import threading

from smartsearch.kern.pfade import ressource

MODELL_NAME = "ibm-granite/granite-embedding-97m-multilingual-r2"

# Ordner unter ressourcen/ und die Dateien darin.
MODELL_ORDNER = "modell/granite-embedding-97m-multilingual-r2"

# Welche ONNX-Datei benutzt wird. IBM liefert zwei:
#   onnx/model.onnx              ~390 MB, volle Genauigkeit (float32)
#   onnx/model_quint8_avx2.onnx   ~98 MB, auf 8 Bit verkleinert
# Welche ausgeliefert wird, entscheidet die Messung mit
# werkzeuge/modellvergleich.py - nicht das Bauchgefuehl. Umstellen nur hier.
MODELL_DATEI = "onnx/model_quint8_avx2.onnx"

# Nur fuer Messungen (werkzeuge/such_diagnose.py): eine andere Datei
# ausprobieren, ohne den Code zu aendern. Die ausgelieferte App setzt das nie.
MODELL_DATEI = os.environ.get("SMARTSEARCH_MODELLDATEI") or MODELL_DATEI
TOKENIZER_DATEI = "tokenizer.json"

# Laenger ist ein Textabschnitt nie (ABSCHNITT_GROESSE in dateien.py sind
# 350 Zeichen, also rund 100 Token). Die Grenze schuetzt nur davor, dass
# eine lange Suchanfrage den Speicher sprengt.
MAX_TOKEN = 512

# Wie viele Texte das Modell auf einmal rechnet.
STAPEL = 16


class ProgrammUnvollstaendig(Exception):
    """Ein Baustein fehlt in der ausgelieferten App - z. B. die
    Modelldateien. Der Nutzer kann daran nichts aendern; ein Neuversuch
    hilft nicht. Eigene Klasse, damit die Oberflaeche genau das sagt."""


def modell_pfad(datei=""):
    return ressource(os.path.join(MODELL_ORDNER, datei)) if datei else ressource(MODELL_ORDNER)


def modell_ist_vorhanden():
    """True, wenn die Modelldateien da sind. Da das Modell mitgeliefert
    wird, ist das in einer fertigen App immer der Fall - False heisst:
    beim Bauen fehlte es, oder beim Entwickeln wurde modell_holen noch
    nicht ausgefuehrt."""
    return (os.path.isfile(modell_pfad(MODELL_DATEI))
            and os.path.isfile(modell_pfad(TOKENIZER_DATEI)))


class OnnxModell:
    """Rechnet Texte in Bedeutungsvektoren um - ohne PyTorch.

    Ablauf je Stapel: Tokenizer -> Zahlenfolgen (input_ids, attention_mask)
    -> ONNX-Modell -> Vektor des ersten Tokens ([CLS]) je Text -> auf
    Laenge 1 normiert. So beschreibt IBM die Nutzung des Modells
    ("CLS pooling", L2-Normierung).
    """

    def __init__(self, modell_datei, tokenizer_datei, threads=None):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(tokenizer_datei)
        self.tokenizer.enable_truncation(max_length=MAX_TOKEN)
        self.tokenizer.enable_padding()

        optionen = ort.SessionOptions()
        if threads:
            optionen.intra_op_num_threads = threads
        self.sitzung = ort.InferenceSession(
            modell_datei, sess_options=optionen, providers=["CPUExecutionProvider"])
        self._eingaenge = {e.name for e in self.sitzung.get_inputs()}

    def _stapel_rechnen(self, texte):
        import numpy as np

        kodiert = self.tokenizer.encode_batch(list(texte))
        ids = np.asarray([k.ids for k in kodiert], dtype="int64")
        maske = np.asarray([k.attention_mask for k in kodiert], dtype="int64")

        eingabe = {"input_ids": ids, "attention_mask": maske}
        # Manche Exporte verlangen zusaetzlich token_type_ids, andere
        # lehnen sie ab - deshalb nur mitgeben, wenn das Modell sie kennt.
        if "token_type_ids" in self._eingaenge:
            eingabe["token_type_ids"] = np.zeros_like(ids)
        eingabe = {k: v for k, v in eingabe.items() if k in self._eingaenge}

        ausgabe = self.sitzung.run(None, eingabe)[0]
        if ausgabe.ndim == 3:
            # (Texte, Token, Merkmale) -> Vektor des ersten Tokens
            ausgabe = ausgabe[:, 0, :]
        return ausgabe.astype("float32")

    def encode(self, texte, show_progress_bar=False, normalize_embeddings=True, **_):
        """Wie SentenceTransformer.encode: Liste von Texten -> Matrix."""
        import numpy as np

        if isinstance(texte, str):
            texte = [texte]
        teile = [self._stapel_rechnen(texte[i:i + STAPEL])
                 for i in range(0, len(texte), STAPEL)]
        if not teile:
            return np.zeros((0, 0), dtype="float32")
        vektoren = np.vstack(teile)
        if normalize_embeddings:
            laenge = np.linalg.norm(vektoren, axis=1, keepdims=True)
            vektoren = vektoren / np.maximum(laenge, 1e-12)
        return vektoren


def lade_modell(fortschritt_fn=None):
    """Laedt das mitgelieferte Modell. Wirft ProgrammUnvollstaendig, wenn
    Dateien oder Bibliotheken fehlen.

    fortschritt_fn wird nicht mehr gebraucht (es gibt keinen Download) und
    steht nur noch in der Signatur, damit bestehende Aufrufe weiter passen.
    """
    if not modell_ist_vorhanden():
        raise ProgrammUnvollstaendig(
            f"Suchmodell fehlt unter {modell_pfad()}. Beim Entwickeln: "
            f"venv/bin/python -m werkzeuge.modell_holen")
    try:
        print(f"Lade Suchmodell ({MODELL_NAME}, {MODELL_DATEI})...")
        return OnnxModell(modell_pfad(MODELL_DATEI), modell_pfad(TOKENIZER_DATEI))
    except ImportError as e:
        raise ProgrammUnvollstaendig(str(e)) from e


_modell_cache = None
_modell_lock = threading.Lock()


def geladenes_modell(fortschritt_fn=None):
    """Lädt das Modell einmalig und cached es (Thread-sicher).

    Ohne den Lock könnten Suche und Indexierung, wenn sie gleichzeitig zum
    allerersten Mal starten, beide parallel lade_modell() aufrufen und das
    Modell doppelt laden.
    """
    global _modell_cache
    if _modell_cache is None:
        with _modell_lock:
            if _modell_cache is None:
                _modell_cache = lade_modell(fortschritt_fn=fortschritt_fn)
    return _modell_cache
