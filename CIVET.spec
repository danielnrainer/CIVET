# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],  # Main script path
    pathex=[],
    binaries=[],
    datas=[
        # GUI configuration files
        ('src/gui/editor_settings.json', 'gui'),              # Include editor settings file

        # Field definition files for validation
        ('field_rules/3ded.cif_rules', 'field_rules'),        # 3D ED field rules
        ('field_rules/3ded_cif1.cif_rules', 'field_rules'),   # 3D ED field rules in CIF1 format
        ('field_rules/hp.cif_rules', 'field_rules'),          # High-pressure field rules
        ('field_rules/cleanups.cif_rules', 'field_rules'),    # Cleanup operations
        
        # CIF Dictionary files - Essential for field validation and conversion
        ('dictionaries/cif_core.dic', 'dictionaries'),        # Core CIF dictionary
        ('dictionaries/cif_rstr.dic', 'dictionaries'),        # SHELXL restraints dictionary
        ('dictionaries/cif_shelxl.dic', 'dictionaries'),      # SHELXL dictionary
        ('dictionaries/cif_twin.dic', 'dictionaries'),        # Twinning dictionary
        
        # Documentation and licensing
        ('LICENSE', '.'),                                      # Include license file
        ('README.md', '.'),                                    # Include readme file
    ],
    hiddenimports=[
        # PyQt6 core modules - Essential for GUI functionality
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        
        # Application modules - Main application structure
        'gui',
        'gui.main_window',
        'gui.editor',
        'gui.editor.text_editor',
        'gui.editor.syntax_highlighter',
        'gui.widgets',
        'gui.dialogs',
        'gui.dialogs.input_dialog',
        'gui.dialogs.multiline_dialog', 
        'gui.dialogs.config_dialog',
        'gui.dialogs.field_conflict_dialog',
        'gui.dialogs.dictionary_info_dialog',
        'gui.dialogs.dictionary_suggestion_dialog',  # New dictionary suggestion dialog
        'gui.dialogs.field_rules_validation_dialog', # New field validation dialog
        
        # Utility modules - Core functionality
        'utils',
        'utils.CIF_field_parsing',
        'utils.CIF_parser',
        'utils.cif_dictionary_manager',
        'utils.cif_format_converter',
        'utils.cif_core_parser',
        'utils.cif_deprecation_manager',
        'utils.cif2_only_extensions',
        'utils.dictionary_suggestion_manager',  # New dictionary suggestion system
        'utils.field_rules_validator',  # New field rules validation system
        
        # Third-party libraries
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.exceptions',
        'urllib3',
        
        # Standard library modules that might be missed by PyInstaller
        'json',
        'os',
        'sys',
        're',
        'typing',
        'tempfile',
        'pathlib',
        'dataclasses',
        'enum',
        'datetime',
        'urllib.parse',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused modules to reduce size
        'tkinter',         # We use PyQt6, not tkinter
        'matplotlib',      # Not used in this application
        'numpy',           # Not used in this application  
        'pandas',          # Not used in this application
        'PIL',             # Not used in this application
        'pytest',          # Testing framework not needed in distribution
    ],
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
    name='CIVET',
    debug=False,                          # Set to True for debugging builds
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
    icon='civet.ico'  # CIVET application icon
)
