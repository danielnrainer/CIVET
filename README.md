# CIF Checker

A CIF (Crystallographic Information File) editor and validator with format conversion and intelligent field validation.

## Overview

CIF Checker is designed for crystallographic workflows, particularly 3D electron diffraction (3DED) and high-pressure crystallography. It provides CIF1/CIF2 format conversion, field validation, and multi-dictionary support.

## Key Features

- **CIF1 ↔ CIF2 Format Conversion**: Bidirectional format conversion with intelligent field mapping
- **Field Validation**: Validate against predefined field sets (3DED, HP, or custom .cif_rules files)  
- **Selective Conversion**: Choose specific types of field conversions (Official/CIF2-Extensions/All)
- **Dictionary Management**: Multi-dictionary support with automatic suggestions based on content
- **Smart Editing**: Syntax highlighting, line length management, and real-time validation

## Quick Start

### Standalone Executable (Recommended)
1. Download `CIF_checker.exe` from releases
2. Run directly - no Python installation required

### From Source
```bash
git clone https://github.com/danielnrainer/CIF_checker.git
cd CIF_checker
pip install -r requirements.txt
python src/main.py
```

## Building Executable
```bash
pip install pyinstaller
pyinstaller CIF_checker.spec
```

## Field Rules
Create custom validation rules using `.cif_rules` files:
```
# Example custom field rules
_chemical_formula_sum ? # Chemical formula
_space_group_name_H-M_alt 'P 1' # Space group
_diffrn_ambient_temperature 293 # Temperature
```

Built-in sets: **3DED** (electron diffraction), **HP** (high-pressure)

## Recent Enhancements

### Enhanced Field Validation
- **Selective Conversions**: Convert only official mappings, CIF2-extensions, or all auto-fixable fields
- **Real-time Feedback**: Dynamic button counts and format-aware validation
- **CIF2-Only Extensions**: Access to 30+ specialized field mappings beyond core CIF specification

### Smart Dictionary Suggestions
- **Automatic Detection**: Analyzes CIF content to suggest relevant dictionaries (twinning, powder, modulated structures, etc.)
- **One-Click Integration**: Download and integrate COMCIFS dictionaries directly

## System Requirements
- Python 3.8+ (source) or Windows (executable)
- PyQt6, requests
- Optional: Internet for dictionary downloads

## License
MIT License - see [LICENSE](LICENSE) file

## Citation
```
CIF Checker - Crystallographic Information File Editor and Validator  
GitHub: https://github.com/danielnrainer/CIF_checker
```

