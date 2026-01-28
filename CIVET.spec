# -*- mode: python ; coding: utf-8 -*-
# CIVET PyInstaller Spec File
# ============================
# Cross-platform build configuration for Windows, macOS, and Linux.
#
# Build Instructions:
#   Windows:  pyinstaller CIVET.spec
#   macOS:    pyinstaller CIVET.spec
#   Linux:    pyinstaller CIVET.spec
#
# User data is stored in platform-specific locations:
#   Windows: %APPDATA%/CIVET/
#   macOS:   ~/Library/Application Support/CIVET/
#   Linux:   ~/.config/CIVET/

import sys
import os

block_cipher = None

# Platform-specific settings
if sys.platform == 'darwin':
    icon_file = 'civet.icns'  # macOS icon format
elif sys.platform == 'win32':
    icon_file = 'civet.ico'   # Windows icon format
else:
    icon_file = None          # Linux typically doesn't use icons in executable

a = Analysis(
    ['src/main.py'],  # Main script path
    pathex=[],
    binaries=[],
    datas=[
        # Field definition files for validation
        ('field_rules/3ded.cif_rules', 'field_rules'),        # 3D ED field rules
        ('field_rules/3ded_legacy.cif_rules', 'field_rules'), # 3D ED field rules in legacy format
        ('field_rules/hp.cif_rules', 'field_rules'),          # High-pressure field rules
        ('field_rules/cleanups.cif_rules', 'field_rules'),    # Cleanup operations
        ('field_rules/checkcif_compatibility.cif_rules', 'field_rules'),  # checkCIF compatibility fields
        
        # CIF Dictionary files - All .dic files in dictionaries folder are bundled
        # The application will automatically load all dictionaries at startup
        # Dictionary filenames include version numbers (e.g., cif_core_3.3.0.dic)
        ('dictionaries/*.dic', 'dictionaries'),               # All CIF dictionaries
        ('dictionaries/registered_prefixes.json', 'dictionaries'),  # Registered CIF prefixes
        
        # Documentation and licensing
        ('LICENSE', '.'),                                      # Include license file
        ('README.md', '.'),                                    # Include readme file
        
        # Version information
        ('src/version.py', '.'),                               # Version module for About dialog
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
        'gui.dialogs.dictionary_suggestion_dialog',
        'gui.dialogs.field_rules_validation_dialog',
        'gui.dialogs.format_conversion_dialog',
        'gui.dialogs.editor_settings_dialog',
        'gui.dialogs.about_dialog',
        'version',
        
        # Utility modules - Core functionality
        'utils',
        'utils.CIF_field_parsing',
        'utils.CIF_parser',
        'utils.cif_dictionary_manager',
        'utils.cif_format_converter',
        'utils.cif_dictionary_parser',
        'utils.cif_deprecation_manager',
        'utils.dictionary_suggestion_manager',
        'utils.field_rules_validator',
        'utils.user_config',              # Unified configuration management
        'utils.user_field_rules',         # User field rules management
        'utils.registered_prefixes',      # CIF prefix registry
        
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
    icon=icon_file if icon_file and os.path.exists(icon_file) else None  # Platform-specific icon
)

# macOS-specific: Create an app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='CIVET.app',
        icon='civet.icns' if os.path.exists('civet.icns') else None,
        bundle_identifier='org.civet.civet',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleDisplayName': 'CIVET',
            'NSHighResolutionCapable': True,
        },
    )
