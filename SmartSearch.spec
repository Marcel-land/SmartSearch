# -*- mode: python ; coding: utf-8 -*-
#
# Baubefehl:  pyinstaller SmartSearch.spec --noconfirm
#
# hiddenimports: PyInstaller findet diese Pakete nicht von allein, weil sie
# erst zur Laufzeit dynamisch importiert werden. Ohne sie startet die
# gebaute .app und stuerzt beim ersten Suchen/Indexieren ab.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# torchgen gehoert zu PyTorch und wird beim Laden eines Modells nachgeladen.
# Es stand hier frueher unter excludes, weil der Name nach Testcode aussieht -
# das war falsch: auf einem Rechner ohne separat installiertes PyTorch fehlte
# es dann im Bundle und der erste Start scheiterte mit
# "No module named 'torchgen'". Das Paket bringt ausserdem YAML-Dateien mit,
# die mitkopiert werden muessen; ohne sie faellt es beim Import auseinander.
# Sollte die Umgebung torchgen nicht kennen, wird hier still uebersprungen -
# der Bau darf daran nicht scheitern.
torch_module = []
torch_daten = []
try:
    torch_module = collect_submodules('torchgen')
    torch_daten = collect_data_files('torchgen')
except Exception:
    pass

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    # LICENSE.txt liegt im fertigen Bundle bei - eine App ohne
    # beiliegende Nutzungsbedingungen sollte man nicht verteilen.
    datas=[('LICENSE.txt', '.')] + torch_daten,
    hiddenimports=[
        'sentence_transformers',
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
    ] + torch_module,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Ballast, den PyInstaller sonst mit einpackt. Vorsichtig gewaehlt -
    # nur Pakete, die SmartSearch nachweislich nicht benutzt. Sparen
    # zusammen mehrere hundert Megabyte im fertigen Bundle.
    #
    # Hier gehoert nichts hin, was zu PyTorch gehoert. Was nach Testcode
    # aussieht, ist es dort oft nicht: torch.testing enthaelt Funktionen,
    # die PyTorch im normalen Betrieb selbst aufruft. Die eingesparten
    # Megabyte sind den Ausfall beim ersten Start nicht wert.
    excludes=[
        'matplotlib', 'IPython', 'jupyter', 'notebook', 'nbconvert',
        'pytest', 'sphinx', 'setuptools._distutils',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        'tkinter.test',
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
    icon=['icon.icns'],
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
    icon='icon.icns',
    # Eindeutige Bundle-ID: macOS braucht sie fuer Autostart (LaunchAgent),
    # Berechtigungen und spaeteres Signieren. Ohne sie behandelt das System
    # die App bei jedem Update wie eine voellig neue Anwendung.
    bundle_identifier='de.smartsearch.app',
    info_plist={
        'CFBundleName': 'SmartSearch',
        'CFBundleDisplayName': 'SmartSearch',
        'CFBundleShortVersionString': '1.0.1',
        'CFBundleVersion': '1.0.1',
        'NSHighResolutionCapable': True,
        # Ohne LSUIElement=False taucht die App nicht normal im Dock auf.
        'LSUIElement': False,
        # macOS soll das Bundle nie ein zweites Mal starten. Ohne diesen
        # Eintrag kann waehrend der Indexierung ein zweites Dock-Symbol
        # auftauchen (ein Arbeits-Kindprozess startet dann das komplette
        # Bundle noch einmal). Zusammen mit multiprocessing.freeze_support()
        # ganz oben in gui.py ist das doppelt abgesichert.
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
