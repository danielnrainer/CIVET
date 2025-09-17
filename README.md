# CIF Checker

A comprehensive CIF (Crystallographic Information File) editor and validator with advanced format conversion capabilities and multi-dictionary support.

## Overview

CIF Checker is designed primarily for 3D electron diffraction (3DED) and high-pressure crystallography workflows, providing robust validation, format conversion, and field management for crystallographic data files. The application supports both CIF1 and CIF2 formats with intelligent field mapping and deprecation handling.

## Key Features

### 🔍 **Advanced CIF Validation**
- **Field Completeness Checking**: Validate against predefined field sets (3DED, HP, or custom)
- **Multi-Dictionary Support**: Integrates CIF core, SHELXL restraints, and COMCIFS dictionaries
- **Deprecation Management**: Automatically detects deprecated fields and suggests modern alternatives
- **Field Conflict Resolution**: Identifies and resolves duplicate/alias fields (e.g., `_diffrn_source_type` vs `_diffrn_source.make`)

### 🔄 **Intelligent Format Conversion**
- **CIF1 ↔ CIF2 Conversion**: Bidirectional format conversion with automatic field mapping
- **Case Sensitivity Handling**: Robust handling of field name variations
- **Replaced Field Support**: Maps obsolete fields to their modern equivalents
- **Loop Structure Preservation**: Maintains data relationships during conversion

### ✏️ **Enhanced Editing Experience**
- **Syntax Highlighting**: Advanced CIF syntax highlighting with loop detection
- **Smart Formatting**: Automatic line length management while preserving structure
- **Field Suggestions**: Quick application of default values and field descriptions
- **Real-time Validation**: Instant feedback on field issues and suggestions

### 📚 **Dictionary Management**
- **Dynamic Dictionary Loading**: Add CIF dictionaries from files or URLs
- **Dictionary Information**: View detailed information about loaded dictionaries
- **Extension Support**: Support for specialized dictionaries (SHELXL, restraints, etc.)
- **Online Dictionary Access**: Download dictionaries directly from COMCIFS repositories

## Quick Start

### Option 1: Standalone Executable (Recommended)
1. Download `CIF_checker.exe` from the releases page
2. Double-click to run - no Python installation required!

### Option 2: From Source
```bash
# Clone the repository
git clone https://github.com/danielnrainer/CIF_checker.git
cd CIF_checker

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

## Building for Distribution

To create a standalone executable:

```bash
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Build the executable
pyinstaller CIF_checker.spec

# The executable will be created in the dist/ directory
```

The spec file is pre-configured to include all necessary dependencies, dictionary files, and GUI resources.

## Supported File Types

- **CIF Files**: `.cif`, `.fcf` (standard crystallographic formats)
- **Field Definitions**: `.cif_ed`, `.cif_hp`, `.cif_defs` (field validation sets)
- **Dictionary Files**: `.dic` (CIF dictionary files)

## Field Definition Sets

### Built-in Sets
- **3DED (3D Electron Diffraction)**: Optimized for electron diffraction studies
- **HP (High Pressure)**: Specialized for high-pressure crystallography
- **All Fields**: Comprehensive validation using all available dictionary fields

### Custom Sets
Create custom field definition files for specialized workflows:

```
# Custom field definitions example
_chemical_formula_sum ? # Chemical formula of the compound
_space_group_name_H-M_alt 'P 1' # Space group in Hermann-Mauguin notation
_cell_length_a ? # Unit cell parameter a
_diffrn_source_type 'electron beam' # Type of radiation source
```

## Advanced Features

### Dictionary Download
The application can automatically download CIF dictionaries from online repositories:
- CIF Core Dictionary (COMCIFS)
- Powder Diffraction Dictionary
- Magnetic Structure Dictionary
- Image CIF Dictionary
- And more...

### Format Conversion Examples
```
# Convert CIF1 to CIF2
_diffrn_radiation_wavelength 1.54184    →    _diffrn_radiation_wavelength.value 1.54184
_symmetry_cell_setting monoclinic       →    _space_group.crystal_system monoclinic
_chemical_formula_iupac 'formula'       →    _chemical_formula.iupac 'formula'

# Handle replaced fields
_cell_measurement_temperature 293       →    _diffrn.ambient_temperature 293
```

### Field Conflict Resolution
The application automatically detects when multiple aliases of the same field are present and helps resolve conflicts by suggesting the preferred modern form.

## System Requirements

- **Python 3.8+** (for source installation)
- **PyQt6** (included in requirements)
- **Windows/Linux/macOS** (cross-platform)
- **Internet connection** (optional, for dictionary downloads)

## Dependencies

- **PyQt6**: GUI framework
- **requests**: HTTP library for dictionary downloads
- **Standard library**: os, re, json, pathlib, etc.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- COMCIFS (Committee for the Maintenance of the CIF Standard) for dictionary specifications
- International Union of Crystallography (IUCr) for CIF format standards
- PyQt6 development team for the GUI framework

## Citation

If you use CIF Checker in your research, please cite:

```
CIF Checker - Crystallographic Information File Editor and Validator
GitHub: https://github.com/danielnrainer/CIF_checker
```

---

**Contact**: For questions, bug reports, or feature requests, please open an issue on GitHub.

