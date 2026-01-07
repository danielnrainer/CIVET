# CIVET

**CIF Validation and Editing Tool** - A modern CIF (Crystallographic Information File) editor and validator with intelligent field checking, format conversion, and UTF-8 support.


_Disclaimer_\
The code in this project has been written in large parts by Anthropic LLM models (mainly Sonnet 4.5 and Opus 4.5).


*Be advised that this software is in constant development and might therefore contain bugs or other unintended behaviour.
Always check your CIF files carefully and if you encounter an issue and would like to report it, please do so via the [Issues](https://github.com/danielnrainer/CIVET/issues) section.*

## Key Features

- **Smart Field Validation**: Visual indicators for adding (🆕), editing (✏️), and correcting (⚠️) fields
- **CIF1 ↔ CIF2 Format Conversion**: Bidirectional conversion with intelligent field mapping
- **Multiline Field Support**: Proper handling of semicolon-delimited multiline values
- **UTF-8 Support**: Full Unicode support for international characters (Å, °, ±, ₁, ₂, etc.)
- **Dictionary Management**: Multi-dictionary support with automatic content-based suggestions
- **Custom Validation**: Flexible field rules using `.cif_rules` files (3DED, HP, or custom)
- **User-Friendly Interface**: Syntax highlighting, confirmations, and intuitive dialogs
- **Guided Suggestions**: Dropdown menu to select from several suggested values (if specified in the cif_rules)

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

## Recent Enhancements (v2.2.0)

### Data Quality Improvements
- **Malformed field detection**: Automatically identifies and fixes incorrectly formatted field names (e.g., `_diffrn_total_exposure_time` → `_diffrn.total_exposure_time`)
- **Pre-check cleanup**: Optional automated correction before field validation to prevent duplicates
- **Dropdown suggestions**: Multiple recommended values in `.cif_rules` now surface as selectable options before editing

### User Experience
- **Color-coded dialogs**: Green (matches default), blue (new field), orange (differs from default)
- **Enhanced button labels**: Clearer action descriptions in dialogs
- **Improved workflow**: Integrated malformed field fixing in validation checks

## Building Executable
```bash
pip install pyinstaller
pyinstaller CIVET.spec
```

## Custom Field Rules
Create validation rules using `.cif_rules` files:
```
# Example custom field rules
_chemical_formula_sum ? # Chemical formula
_space_group_name_H-M_alt 'P 1' # Space group
_diffrn_ambient_temperature 293 # Temperature in K
```

Built-in sets: **3DED** (electron diffraction)

## System Requirements
- **Executable**: Windows 10/11 (64-bit)
- **Source**: Python 3.8+, PyQt6, requests

## License
BSD Clause License - see [LICENSE](LICENSE)

## Citation
```
CIVET - CIF Validation and Editing Tool
GitHub: https://github.com/danielnrainer/CIVET
```

