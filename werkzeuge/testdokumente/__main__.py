import os
import sys

from smartsearch.kern.pfade import PROJEKT_ORDNER

from . import haushalt, kanzlei
from .bausteine import schreiben

ZIEL = os.path.join(PROJEKT_ORDNER, "tests", "testdokumente")


def main():
    dokumente = haushalt.DOKUMENTE + kanzlei.DOKUMENTE
    namen = [os.path.basename(d.datei) for d in dokumente]
    doppelt = {n for n in namen if namen.count(n) > 1}
    if doppelt:
        # Die Suchdiagnose vergleicht nur Dateinamen, nicht Pfade
        sys.exit(f"Dateiname mehrfach vergeben: {', '.join(sorted(doppelt))}")
    for dok in dokumente:
        pfad = schreiben(dok, ZIEL)
        print(f"  {dok.art:5} {os.path.getsize(pfad) / 1024:7.0f} KB  {dok.datei}")
    print(f"\n{len(dokumente)} Dokumente geschrieben nach {ZIEL}")


if __name__ == "__main__":
    main()
