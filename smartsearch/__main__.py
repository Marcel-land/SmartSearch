"""Startpunkt:  venv/bin/python -m smartsearch
(in der gebauten App ruft PyInstaller genau diese Datei auf)."""

# ZWEITES DOCK-SYMBOL WAEHREND DER INDEXIERUNG
# -------------------------------------------
# In der fertig gebauten .app startet ein Arbeits-Kindprozess (den die
# KI-Bibliotheken beim Indexieren anlegen koennen) nicht einfach einen
# Python-Interpreter, sondern das GESAMTE App-Bundle ein zweites Mal -
# macOS haengt dafuer ein zweites Symbol ins Dock.
#
# multiprocessing.freeze_support() faengt genau das ab: erkennt der
# Prozess, dass er als Arbeitskind gestartet wurde, erledigt er nur seine
# Aufgabe und laeuft nie in den Programmstart weiter unten (Fenster,
# Dock-Symbol, Menueleiste). Das MUSS vor allen schweren Importen stehen,
# sonst baut das Kind vorher noch die halbe Anwendung auf.
import multiprocessing
multiprocessing.freeze_support()

import os  # noqa: E402

# Die Tokenizer-Bibliothek legt sonst eigene Arbeitsprozesse an und warnt
# bei jedem fork. Fuer eine Desktop-App bringt das nichts ausser Unruhe -
# und potenziell genau das zweite Dock-Symbol von oben.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from smartsearch.start import starten  # noqa: E402

starten()
