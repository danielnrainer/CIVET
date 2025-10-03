# CIVET

**CIF Validation and Editing Tool** - A modern CIF (Crystallographic Information File) editor and validator with intelligent field checking, format conversion, and UTF-8 support.

## Key Features

- **Smart Field Validation**: Visual indicators for adding (🆕), editing (✏️), and correcting (⚠️) fields
- **CIF1 ↔ CIF2 Format Conversion**: Bidirectional conversion with intelligent field mapping
- **Multiline Field Support**: Proper handling of semicolon-delimited multiline values
- **UTF-8 Support**: Full Unicode support for international characters (Å, °, ±, ₁, ₂, etc.)
- **Dictionary Management**: Multi-dictionary support with automatic content-based suggestions
- **Custom Validation**: Flexible field rules using `.cif_rules` files (3DED, HP, or custom)
- **User-Friendly Interface**: Syntax highlighting, confirmations, and intuitive dialogs

## Quick Start

### Standalone Executable (Recommended)
1. Download `CIVET.exe` from releases
2. Run directly - no Python installation required

### From Source
```bash
git clone https://github.com/danielnrainer/CIVET.git
cd CIVET
pip install -r requirements.txt
python src/main.py
```

## Recent Enhancements (v2.1.0)

### Enhanced User Experience
- **Color-coded dialogs**: Green (add), blue (edit), orange (differs from default)
- **Multiline editing**: Proper display and editing of complex field values
- **Confirmation dialogs**: Prevents accidental formatting changes
- **Current file display**: Shows filename in window title

### Technical Improvements
- **Complete UTF-8 support**: All text operations now handle Unicode properly
- **Improved field parsing**: Better handling of multi-line and next-line field values
- **Enhanced dialog system**: Context information preserved in all dialogs

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

Built-in sets: **3DED** (electron diffraction), **HP** (high-pressure)

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

