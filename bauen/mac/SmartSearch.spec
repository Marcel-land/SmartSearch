# -*- mode: python ; coding: utf-8 -*-
#
# Baubefehl (im Projektordner):  pyinstaller bauen/mac/SmartSearch.spec --noconfirm
# Normalerweise nicht direkt, sondern ueber bauen/mac/build.sh.
#
# hiddenimports: PyInstaller findet diese Pakete nicht von allein, weil sie
# erst zur Laufzeit dynamisch importiert werden. Ohne sie startet die
# gebaute .app und stuerzt beim ersten Suchen/Indexieren ab.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import pathlib
import re

# Diese Datei liegt in bauen/<system>/ - der Projektordner ist zwei Ebenen
# darueber. SPECPATH setzt PyInstaller selbst auf den Ordner dieser Datei.
ROOT = pathlib.Path(SPECPATH).resolve().parents[1]  # noqa: F821

# Die Versionsnummer steht an genau EINER Stelle: smartsearch/version.py.
# Sie hier ein zweites Mal zu pflegen ging schief - bis Fassung 1.0.2 stand
# im Info.plist durchgehend "1.0.1". Der Finder und spaeter auch die
# Beglaubigung durch Apple lesen aber genau diesen Wert.
APP_VERSION = re.search(
    r'APP_VERSION\s*=\s*"([^"]+)"',
    (ROOT / "smartsearch" / "version.py").read_text(encoding="utf-8"),
).group(1)

# Das Suchmodell liegt in ressourcen/modell/ (nicht im Repository). In die
# App kommen nur die Dateien aus modell.AUSLIEFERN - das grosse Quellmodell
# (390 MB), aus dem die ausgelieferte Datei abgeleitet ist, bleibt draussen.
# Fehlt etwas, bricht der Bau hier ab: eine App ohne Modell kann nicht suchen.
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from smartsearch.kern import modell  # noqa: E402
if not modell.modell_ist_vorhanden():
    raise SystemExit("Suchmodell fehlt - zuerst: venv/bin/python -m werkzeuge.modell_holen")
modell_dateien = []
for datei in modell.AUSLIEFERN:
    quelle = pathlib.Path(modell.modell_pfad(datei))
    if not quelle.is_file():
        raise SystemExit(f"Suchmodell unvollstaendig, es fehlt: {quelle}")
    ziel = pathlib.Path('ressourcen') / modell.MODELL_ORDNER / datei
    modell_dateien.append((str(quelle), str(ziel.parent)))

# onnxruntime bringt eigene Bibliotheken mit, die PyInstaller nur ueber
# collect_dynamic_libs sicher findet.
from PyInstaller.utils.hooks import collect_dynamic_libs  # noqa: E402
ort_bibliotheken = collect_dynamic_libs('onnxruntime')

a = Analysis(
    [str(ROOT / 'smartsearch' / '__main__.py')],
    pathex=[str(ROOT)],
    binaries=ort_bibliotheken,
    # LICENSE.txt liegt im fertigen Bundle bei - eine App ohne
    # beiliegende Nutzungsbedingungen sollte man nicht verteilen.
    # ressourcen/ (Symbole) liest das Programm zur Laufzeit ueber
    # pfade.ressource() - siehe dort.
    datas=[(str(ROOT / 'LICENSE.txt'), '.'),
           (str(ROOT / 'ressourcen' / 'icons'), 'ressourcen/icons')] + modell_dateien,
    hiddenimports=[
        'onnxruntime',
        'tokenizers',
        'customtkinter',
        'pypdf',
        'pdfplumber',
        'docx',
        'openpyxl',
        'pptx',
        'watchdog',
        # Texterkennung: pypdfium2 rendert die Seiten, Vision erkennt den
        # Text. Beide werden nur zur Laufzeit importiert und von
        # PyInstaller sonst nicht gefunden.
        'pypdfium2',
        'Vision',
        'Foundation',
        'objc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Ballast, den PyInstaller sonst mit einpackt. Vorsichtig gewaehlt -
    # nur Pakete, die SmartSearch nachweislich nicht benutzt. Sparen
    # zusammen mehrere hundert Megabyte im fertigen Bundle.
    #
    # PyTorch & Co. stehen bewusst hier: seit dem Wechsel auf onnxruntime
    # braucht SmartSearch sie nicht mehr, in einem aelteren venv koennen sie
    # aber noch installiert sein - dann wuerden sie still 2 GB mitgepackt.
    excludes=[
        'matplotlib', 'IPython', 'jupyter', 'notebook', 'nbconvert',
        'pytest', 'sphinx', 'setuptools._distutils',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        'tkinter.test',
        'torch', 'torchgen', 'torchvision', 'transformers',
        'sentence_transformers', 'sklearn', 'scipy',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartSearch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX aus: komprimierte Binaries loesen auf dem Mac regelmaessig
    # Gatekeeper-Meldungen aus ("ist beschaedigt") und machen spaeteres
    # Signieren/Notarisieren unnoetig fragil.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / 'ressourcen' / 'icons' / 'icon.icns')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SmartSearch',
)
app = BUNDLE(
    coll,
    name='SmartSearch.app',
    icon=str(ROOT / 'ressourcen' / 'icons' / 'icon.icns'),
    # Eindeutige Bundle-ID: macOS braucht sie fuer Autostart (LaunchAgent),
    # Berechtigungen und spaeteres Signieren. Ohne sie behandelt das System
    # die App bei jedem Update wie eine voellig neue Anwendung.
    bundle_identifier='de.smartsearch.app',
    info_plist={
        'CFBundleName': 'SmartSearch',
        'CFBundleDisplayName': 'SmartSearch',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': True,
        # Ohne LSUIElement=False taucht die App nicht normal im Dock auf.
        'LSUIElement': False,
        # macOS soll das Bundle nie ein zweites Mal starten. Ohne diesen
        # Eintrag kann waehrend der Indexierung ein zweites Dock-Symbol
        # auftauchen (ein Arbeits-Kindprozess startet dann das komplette
        # Bundle noch einmal). Zusammen mit multiprocessing.freeze_support()
        # ganz oben in smartsearch/__main__.py ist das doppelt abgesichert.
        'LSMultipleInstancesProhibited': True,
        # Klartext-Begruendungen, die macOS im Berechtigungsdialog zeigt.
        # Fehlen sie, bricht der Zugriff auf Dokumente/Downloads/Schreibtisch
        # unter neueren macOS-Versionen kommentarlos ab.
        'NSDesktopFolderUsageDescription':
            'SmartSearch durchsucht die Dateien auf Ihrem Schreibtisch - ausschliesslich lokal auf diesem Mac.',
        'NSDocumentsFolderUsageDescription':
            'SmartSearch durchsucht Ihre Dokumente - ausschliesslich lokal auf diesem Mac, es wird nichts uebertragen.',
        'NSDownloadsFolderUsageDescription':
            'SmartSearch durchsucht Ihren Downloads-Ordner - ausschliesslich lokal auf diesem Mac.',
    },
)
