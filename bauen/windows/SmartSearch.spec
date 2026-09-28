# -*- mode: python ; coding: utf-8 -*-
#
# Baubefehl (auf einem WINDOWS-Rechner, nicht auf dem Mac):
#     venv\Scripts\python -m PyInstaller bauen\windows\SmartSearch.spec --noconfirm
# (im Projektordner ausfuehren - dort entstehen build\ und dist\)
#
# NOCH NICHT AUF WINDOWS ERPROBT. Diese Datei ist der Startpunkt fuer den
# ersten Bau, kein fertiges Ergebnis - die Liste unter hiddenimports wird
# sich beim ersten Lauf erfahrungsgemaess noch aendern.
#
# Warum eine eigene Datei und keine Verzweigung in bauen/mac/SmartSearch.spec:
# der Mac-Bau ist der, der heute funktioniert und signiert wird. Eine
# Verzweigung mittendrin wuerde ihn bei jedem Windows-Versuch mitgefaehrden.
#
# Unterschiede zur Mac-Fassung:
#   - Symbol ist icon.ico statt icon.icns (Windows kennt .icns nicht)
#   - kein BUNDLE/Info.plist - das gibt es nur auf dem Mac
#   - statt Apples Vision-Framework: pytesseract (siehe requirements-windows.txt)
#   - pystray/PIL fuer das Symbol im Infobereich neben der Uhr

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

torch_module = []
torch_daten = []
try:
    torch_module = collect_submodules('torchgen')
    torch_daten = collect_data_files('torchgen')
except Exception:
    pass

a = Analysis(
    [str(ROOT / 'smartsearch' / '__main__.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / 'LICENSE.txt'), '.'),
           (str(ROOT / 'ressourcen'), 'ressourcen')] + torch_daten,
    hiddenimports=[
        'sentence_transformers',
        'customtkinter',
        'pypdf',
        'pdfplumber',
        'docx',
        'openpyxl',
        'pptx',
        'watchdog',
        'pypdfium2',
        # Symbol im Infobereich - das Windows-Gegenstueck zur Menueleiste
        'pystray',
        'pystray._win32',
        'PIL',
        'PIL.Image',
        # Texterkennung. Das Programm tesseract.exe muss zusaetzlich
        # installiert sein, das Paket allein reicht nicht.
        'pytesseract',
    ] + torch_module,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'IPython', 'jupyter', 'notebook', 'nbconvert',
        'pytest', 'sphinx', 'setuptools._distutils',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        'tkinter.test',
        # Die Mac-Teile duerfen hier nicht mit hinein - sie existieren
        # unter Windows nicht und wuerden den Bau abbrechen.
        'Vision', 'Foundation', 'objc', 'AppKit', 'smartsearch.plattform.mac',
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
    # UPX bleibt aus. Unter Windows ist der Grund ein anderer als auf dem
    # Mac, das Ergebnis dasselbe: gepackte Programmdateien sind der
    # haeufigste Grund, warum ein Virenscanner eine an sich saubere
    # Anwendung in Quarantaene schiebt. Bei Kanzleien als Zielkunden ist
    # das der Punkt, an dem die Installation scheitert.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=[str(ROOT / 'ressourcen' / 'icons' / 'icon.ico')],
    # Zeigt Windows in den Dateieigenschaften an und wird von
    # Softwareverteilung ausgelesen.
    version_file=None,
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
