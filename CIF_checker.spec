# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],  # Main script path
    pathex=[],
    binaries=[],
    datas=[
        ('src/gui/field_definitions.cif_ed', 'gui'),           # Include field definitions
        ('src/gui/field_definitions.cif_hp', 'gui'),          # Include HP field definitions
        ('src/gui/editor_settings.json', 'gui'),              # Include settings file
        ('LICENSE', '.'),                                      # Include license file
        ('README.md', '.'),                                    # Include readme file
    ],
    hiddenimports=[
        # PyQt6 core modules
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        # Application modules - ensure all are found
        'gui',
        'gui.main_window',
        'gui.dialogs',
        'gui.dialogs.input_dialog',
        'gui.dialogs.multiline_dialog', 
        'gui.dialogs.config_dialog',
        'gui.editor',
        'gui.editor.syntax_highlighter',
        'utils',
        'utils.CIF_field_parsing',
        'utils.CIF_parser',
        # Standard library modules that might be missed
        'json',
        'os',
        're',
        'typing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CIF_checker',
    debug=False,                          # Set to True for debugging
    bootloader_ignore_signals=False,
    strip=False,                          # Don't strip symbols for better error messages
    upx=True,                            # Compress executable (set to False if issues)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                        # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico'  # Uncomment and add icon file if available
)
