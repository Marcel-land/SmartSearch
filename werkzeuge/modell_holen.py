#!/usr/bin/env python3
"""
modell_holen.py - laedt das Suchmodell nach ressourcen/modell/ und
verkleinert es fuer die Auslieferung.

Das Modell gehoert zur App, aber nicht ins Git-Repository. Einmal nach dem
Klonen ausfuehren (bauen/mac/build.sh ruft es selbst auf, wenn etwas fehlt):

    venv/bin/python -m werkzeuge.modell_holen

Was passiert:
  1. Laden von huggingface.co, festgenagelt auf eine bestimmte Fassung
     (REVISION) - so bekommt jeder Rechner und jeder Bau dasselbe Modell.
     Rund 415 MB, vorhandene Dateien werden nicht erneut geladen.
  2. Verkleinern: nur die Gewichte werden auf 8 Bit gebracht, gerechnet
     wird weiter in voller Genauigkeit. Ergebnis rund 100 MB, Warum und wie
     gemessen: siehe MODELL_DATEI in smartsearch/kern/modell.py.
  3. Lizenzhinweis und Pruefsummen dazulegen.

Braucht die Pakete onnx und onnxruntime (stehen in requirements.txt). In
die fertige App kommen nur die Dateien aus modell.AUSLIEFERN.
"""

import hashlib
import os
import sys
import urllib.request

from smartsearch.kern import modell

# Festgenagelte Fassung des Modells auf huggingface.co (Stand 28.09.2026).
# Nur bewusst aendern - danach neu messen (SUCHE PRUEFEN.command).
REVISION = "835ad14087e140460703cf0fae09f97d469d65c2"
BASIS = f"https://huggingface.co/{modell.MODELL_NAME}/resolve/{REVISION}/"

# README.md ist die Modellbeschreibung von IBM - sie wird mit ausgeliefert,
# weil die Apache-2.0-Lizenz verlangt, Herkunft und Lizenz weiterzugeben.
LADEN = [modell.TOKENIZER_DATEI, "config.json", "README.md", modell.QUELL_DATEI]

WORTTABELLE = "embeddings.tok_embeddings.weight"

LIZENZ_TEXT = f"""Suchmodell: {modell.MODELL_NAME}
Herkunft:   https://huggingface.co/{modell.MODELL_NAME}
Fassung:    {REVISION}
Lizenz:     Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
Hersteller: IBM

AENDERUNG DURCH SMARTSEARCH
Die Datei {modell.MODELL_DATEI} ist aus {modell.QUELL_DATEI} abgeleitet:
Die Gewichte wurden auf 8 Bit verkleinert (Worttabelle je Zeile,
Matrizen in Bloecken zu 32 Werten). Aufbau und Rechenweg des Modells sind
unveraendert. Alle uebrigen Dateien sind unveraendert uebernommen.
"""


def _laden(datei):
    ziel = modell.modell_pfad(datei)
    if os.path.isfile(ziel) and os.path.getsize(ziel) > 0:
        print(f"  vorhanden   {datei}")
        return ziel
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    teil = ziel + ".teil"
    print(f"  lade        {datei} ...", end="", flush=True)
    anfrage = urllib.request.Request(BASIS + datei, headers={"User-Agent": "SmartSearch-Bau"})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort, open(teil, "wb") as f:
        gesamt = int(antwort.headers.get("Content-Length") or 0)
        geladen, gemeldet = 0, -1
        while True:
            stueck = antwort.read(1 << 20)
            if not stueck:
                break
            f.write(stueck)
            geladen += len(stueck)
            prozent = geladen * 100 // gesamt if gesamt else 0
            # Nur in 10er-Schritten melden - sonst flutet die Ausgabe ein
            # Protokoll, das nicht in einem Terminal angezeigt wird.
            if prozent // 10 != gemeldet:
                gemeldet = prozent // 10
                print(f" {prozent}%", end="", flush=True)
    os.replace(teil, ziel)
    print(f"  ({os.path.getsize(ziel) / 1e6:.1f} MB)")
    return ziel


def _worttabelle_8bit(m):
    """Worttabelle (180.000 Woerter x 384 Werte) je Zeile auf 8 Bit.

    Ersetzt Gather(Tabelle) durch Gather(8-Bit-Tabelle) * Gather(Faktor je
    Zeile). Nur Standardbausteine von ONNX - laeuft auf jedem System.
    """
    import numpy as np
    from onnx import TensorProto, helper, numpy_helper

    g = m.graph
    init = next(i for i in g.initializer if i.name == WORTTABELLE)
    tabelle = numpy_helper.to_array(init).astype("float32")
    g.initializer.remove(init)

    faktor = np.abs(tabelle).max(axis=1, keepdims=True) / 127.0
    faktor[faktor == 0] = 1.0
    werte = np.clip(np.round(tabelle / faktor), -127, 127).astype("int8")
    g.initializer.append(numpy_helper.from_array(werte, WORTTABELLE + "_int8"))
    g.initializer.append(numpy_helper.from_array(faktor.astype("float32"), WORTTABELLE + "_faktor"))

    knoten = next(n for n in g.node if n.op_type == "Gather" and n.input[0] == WORTTABELLE)
    ausgang, ids = knoten.output[0], knoten.input[1]
    stelle = list(g.node).index(knoten)
    g.node.remove(knoten)
    neu = [
        helper.make_node("Gather", [WORTTABELLE + "_int8", ids], [ausgang + "_int8"], axis=0),
        helper.make_node("Cast", [ausgang + "_int8"], [ausgang + "_float"], to=TensorProto.FLOAT),
        helper.make_node("Gather", [WORTTABELLE + "_faktor", ids], [ausgang + "_faktor"], axis=0),
        helper.make_node("Mul", [ausgang + "_float", ausgang + "_faktor"], [ausgang]),
    ]
    for i, n in enumerate(neu):
        g.node.insert(stelle + i, n)
    return m


def verkleinern():
    ziel = modell.modell_pfad(modell.MODELL_DATEI)
    if os.path.isfile(ziel):
        print(f"  vorhanden   {modell.MODELL_DATEI}")
        return
    import logging

    import onnx
    from onnxruntime.quantization.matmul_nbits_quantizer import (
        DefaultWeightOnlyQuantConfig, MatMulNBitsQuantizer)

    logging.getLogger("onnxruntime.quantization").setLevel(logging.WARNING)
    print(f"  verkleinere {modell.QUELL_DATEI} -> {modell.MODELL_DATEI} ...", flush=True)
    m = onnx.load(modell.modell_pfad(modell.QUELL_DATEI))
    m = _worttabelle_8bit(m)
    einstellung = DefaultWeightOnlyQuantConfig(block_size=32, is_symmetric=True, bits=8)
    quant = MatMulNBitsQuantizer(m, algo_config=einstellung)
    quant.process()
    onnx.save(quant.model.model, ziel + ".teil")
    os.replace(ziel + ".teil", ziel)
    print(f"              fertig ({os.path.getsize(ziel) / 1e6:.1f} MB)")


def _pruefsumme(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for stueck in iter(lambda: f.read(1 << 20), b""):
            h.update(stueck)
    return h.hexdigest()


def main():
    print(f"Suchmodell nach {modell.modell_pfad()}\n")
    for datei in LADEN:
        _laden(datei)
    verkleinern()
    with open(modell.modell_pfad("LIZENZ.txt"), "w", encoding="utf-8") as f:
        f.write(LIZENZ_TEXT)
    # Pruefsummen: so laesst sich spaeter nachweisen, welche Modellfassung
    # in einer ausgelieferten App steckt.
    with open(modell.modell_pfad("PRUEFSUMMEN.txt"), "w", encoding="utf-8") as f:
        for datei in LADEN + [modell.MODELL_DATEI]:
            f.write(f"{_pruefsumme(modell.modell_pfad(datei))}  {datei}\n")
    ok = modell.modell_ist_vorhanden()
    print("\nFertig." if ok else "\nFEHLER: Modell unvollstaendig.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
