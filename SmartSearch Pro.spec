# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['sentence_transformers', 'customtkinter', 'pypdf', 'docx', 'openpyxl', 'pptx', 'pytesseract', 'pdf2image'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartSearch Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='SmartSearch Pro',
)
app = BUNDLE(
    coll,
    name='SmartSearch Pro.app',
    icon='icon.icns',
    # WICHTIG: ohne feste Bundle-Kennung erkennt SmartSearch beim Start
    # nicht, dass es schon laeuft (siehe laufende_instanz_aktivieren in
    # menueleiste_mac.py) - dann oeffnet sich die App ein zweites Mal und
    # es stehen zwei Symbole im Dock. Die Kennung muss mit BUNDLE_KENNUNG
    # in menueleiste_mac.py uebereinstimmen.
    bundle_identifier='de.smartsearch.app',
    info_plist={
        'CFBundleName': 'SmartSearch',
        'CFBundleDisplayName': 'SmartSearch',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        # macOS soll das Bundle nie ein zweites Mal starten.
        'LSMultipleInstancesProhibited': True,
    },
)
