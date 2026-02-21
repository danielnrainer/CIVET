# CIVET

**CIF Validation and Editing Tool** - A modern CIF (Crystallographic Information File) editor and validator with intelligent field checking, format conversion, and UTF-8 support.


_Disclaimer_\
The code in this project has been written in large parts by Anthropic LLM models (mainly Sonnet 4.5 and Opus 4.5).


*Be advised that this software is in constant development and might therefore contain bugs or other unintended behaviour.
Always check your CIF files carefully and if you encounter an issue and would like to report it, please do so via the [Issues](https://github.com/danielnrainer/CIVET/issues) section.*

## Key Features (v1.2)

- **CIF Editing and Validation**: Syntax highlighting, guided dialogs, smart field checks, and duplicate/alias-aware workflows.
- **Flexible Field Rules Engine**: Supports `CHECK`, `DELETE`, `EDIT`, `RENAME`, `CALCULATE`, and `APPEND` actions in `.cif_rules` files.
- **Legacy/Modern CIF Handling**: Detects legacy, modern, and mixed notation; includes conversion and malformed-field correction workflows.
- **CIF2 Compliance Support**: Maintains `#\#CIF_2.0` headers and handles CIF2 quoting/formatting edge cases (including triple-quoted values).
- **Dictionary-Backed Intelligence**: Multi-dictionary loading, metadata display, update checks, and parser support for DDLm + DDL1 dictionaries.
- **Data Name Validation**: Validates names against loaded dictionaries and IUCr registered prefixes, with validation-aware highlighting.
- **Persistent User Configuration**: Cross-platform storage for settings, user rules, recognised prefixes, and downloaded dictionaries.
- **Productivity UX**: Built-in/user/custom rules selection, dropdown suggestions for field values, and focused editor settings.

## Quick Start

### From Source (Windows)
```bash
git clone https://github.com/danielnrainer/CIVET.git
cd CIVET
pip install -r requirements.txt
python src/main.py
```

### Standalone Executable (Windows)
1. Download `CIVET.exe` from releases
2. Run directly - no Python installation required

### From source (Linux)

Linux distributions do not like use of `pip` outside a virtual environment:

```bash
git clone https://github.com/danielnrainer/CIVET.git
cd CIVET
mkdir civet_virtual
python -m venv ./civet_virtual
source ./civet_virtual/bin/activate
pip install -r requirements.txt
python src/main.py
```

If the error message `From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin` appears
when you run `python src/main.py`, 
you need to install packages `libxcb-cursor0` and `libxcb-util1` or equivalent package names for your distribution.

To execute after the initial installation:
```bash
source CIVET/civet_virtual/bin/activate
python CIVET/src/main.py
```

## Building Executable
```bash
pip install pyinstaller
pyinstaller CIVET.spec
```

## Custom Field Rules
Create validation rules using `.cif_rules` files:
```
# Example custom field rules
_chemical_formula_sum         ?        # Chemical formula
_space_group_name_H-M_alt     'P 1'    # Space group
_diffrn_ambient_temperature   293      # Temperature in K

# Special actions:
DELETE: _field_to_remove           # Removes field from CIF
EDIT: _field_name new_value        # Replaces field value
RENAME: _old_name _new_name        # Renames field (for correcting erroneous field names)
CALCULATE: _field = expression     # Calculates value from other fields
APPEND: _publ_section_references Allen, F.H. (2010), Acta Cryst B66, 380-386.  # Appends to multiline field
    Multiple APPEND entries (in the same .cif_rules file) for the same CIF field (data name) will be concatenated

# CALCULATE example - convert fluence to flux density:
# CrysAlisPRO reports fluence (e/Å²) as _diffrn.flux_density, but flux density is e/Å²/s
CALCULATE: _diffrn.flux_density = _diffrn.flux_density / (_diffrn.total_exposure_time * 60) 
```

Built-in sets: **3DED** (electron diffraction)

### User Custom Field Rules (AppData)
CIVET supports persistent user-created field rules stored in your system's application data directory:

**Location:**
- **Windows**: `%APPDATA%\CIVET\field_rules\` (typically `C:\Users\[username]\AppData\Roaming\CIVET\field_rules\`)
- **macOS**: `~/Library/Application Support/CIVET/field_rules/`
- **Linux**: `~/.config/CIVET/field_rules/`

**Field Rules Selection UI:**
The application provides three ways to select field rules:
1. **Built-in**: Select from field rules that ship with CIVET (3D ED Modern, 3D ED Legacy, High Pressure)
2. **User**: Select from your custom rules stored in the AppData directory (dropdown shows available files)
3. **Custom File**: Browse to select any `.cif_rules` file from your filesystem

**Quick Access:**
- Click the 📁 button next to the User dropdown to open the user rules directory
- Click the ↻ button to refresh the list after adding new files
- Use **Settings → Open User Config Directory...** from the menu

## User Data Directory

CIVET stores all user configuration and customizations in a platform-specific application data directory:

| Platform | Location |
|----------|----------|
| Windows  | `%APPDATA%\CIVET\` |
| macOS    | `~/Library/Application Support/CIVET/` |
| Linux    | `~/.config/CIVET/` |

**Contents:**
```
CIVET/
├── settings.json           # Editor preferences (font, ruler, etc.)
├── registered_prefixes.json  # Custom CIF prefix registry
├── dictionaries/           # User-downloaded CIF dictionaries
└── field_rules/            # Custom validation rules
```

This allows settings and customizations to persist across sessions and software updates, even when using the standalone executable.

### Editor Settings

CIVET provides customizable editor preferences accessible via **Settings → Editor Settings...**:

- **Font Family**: Choose from system-installed fonts (default: Courier New)
- **Font Size**: Adjustable size in points (default: 10)
- **Line Numbers**: Toggle line number display
- **Syntax Highlighting**: Enable/disable CIF-specific syntax coloring
- **80-Character Ruler**: Visual guide for line length

All settings are stored in `settings.json` and persist across sessions. User settings always take precedence over built-in defaults. Use **Reset to Defaults** to restore original settings.

## Building

### Executable 
```bash
pip install pyinstaller
pyinstaller CIVET.spec
```

Output: `dist/CIVET` (or `CIVET.exe` on Windows, `CIVET.app` on macOS)


## System Requirements
- **Executable**: Windows 10/11, macOS 10.14+ (not tested), Linux (not tested)
- **Source**: Python 3.8+, PyQt6, requests

## License
BSD Clause License - see [LICENSE](LICENSE)

## Citation
```
CIVET - CIF Validation and Editing Tool
GitHub: https://github.com/danielnrainer/CIVET
Zenodo: https://doi.org/10.5281/zenodo.17328490
```

