# CIF Checker

A comprehensive CIF (Crystallographic Information File) editor and validator with advanced format conversion capabilities, multi-dictionary support, and intelligent dictionary suggestions.

## Overview

CIF Checker is designed primarily for 3D electron diffraction (3DED) and high-pressure crystallography workflows, providing robust validation, format conversion, and field management for crystallographic data files. The application supports both CIF1 and CIF2 formats with intelligent field mapping, deprecation handling, and automatic dictionary recommendations based on content analysis.

## 🚀 Latest Features (September 2025)

### Smart Dictionary Suggestions System
**NEW**: Intelligent analysis of CIF content to suggest relevant specialized dictionaries:
- **Automatic Detection**: Recognizes modulated structures, twinning, powder diffraction, magnetic structures, and more
- **Smart Prompting**: Automatically prompts users when opening CIF files that could benefit from additional dictionaries
- **One-Click Downloads**: Direct download and integration of COMCIFS dictionaries from official repositories
- **Confidence Scoring**: Shows confidence levels and specific fields that triggered suggestions
- **Format Aware**: Works with both CIF1 and CIF2 field naming conventions

### Enhanced Dictionary Management
- **Multi-Repository Support**: Integrates with official COMCIFS GitHub repositories
- **Progress Tracking**: Visual progress bars for dictionary downloads
- **Status Updates**: Real-time feedback during dictionary loading
- **Smart Caching**: Efficient handling of multiple specialized dictionaries

## 🚨 Recent Critical Updates (September 2025)

### Text-Block Insertion Bug Fix
**FIXED**: Critical bug where field conversions were inserting field names into semicolon-delimited text blocks (e.g., `_publ_section.references`). This affected both:
- `convert_cif_format()` method (CIF1↔CIF2 conversion)
- `resolve_field_aliases()` method (duplicate field resolution)

**Solution**: Implemented text-block-aware field replacement using `_replace_field_text_block_aware()` method that preserves all content within `; ... ;` text blocks.

### Enhanced Field Detection
- Improved field pattern recognition to avoid false positives from comments
- Fixed underscores in comments being detected as field names
- Enhanced validation for legitimate CIF field patterns

### Dictionary Management Improvements
- Enhanced field lookup with file-based validation
- Better handling of CIF1/CIF2 field mappings
- Improved deprecation and replacement field detection
- **NEW**: Smart dictionary suggestions based on CIF content analysis

### Automatic Dictionary Suggestions  
- **Content Analysis**: Analyze CIF content and automatically suggest relevant specialized dictionaries
- **Smart Detection**: Recognizes modulated structures, twinning, powder diffraction, magnetic structures, and more
- **Format Aware**: Handles both CIF1 and CIF2 field naming conventions
- **User Friendly**: Shows confidence levels and trigger fields that caused suggestions
- **Seamless Integration**: One-click download and integration with existing workflow

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
- **Field Rules**: `.cif_rules` (standardized field validation and operation files)
- **Dictionary Files**: `.dic` (CIF dictionary files)

## Field Rules Sets

### Built-in Sets
- **3DED (3D Electron Diffraction)**: Optimized for electron diffraction studies (`3ded.cif_rules`)
- **HP (High Pressure)**: Specialized for high-pressure crystallography (`hp.cif_rules`)
- **All Fields**: Comprehensive validation using all available dictionary fields

### Consistent Naming Convention
All field rule files use the standardized `.cif_rules` extension for clear identification and consistency. This makes it easy to distinguish field validation files from other CIF-related files.

### Custom Sets
Create custom field rules files for specialized workflows using the `.cif_rules` extension:

```
# Custom field rules example
_chemical_formula_sum ? # Chemical formula of the compound
_space_group_name_H-M_alt 'P 1' # Space group in Hermann-Mauguin notation
_cell_length_a ? # Unit cell parameter a
_diffrn_source_type 'electron beam' # Type of radiation source
```

## Advanced Features

### Dictionary Download & Suggestions
The application features an intelligent dictionary suggestion system that:
- **Analyzes CIF Content**: Automatically detects specialized field patterns
- **Suggests Relevant Dictionaries**: Recommends dictionaries based on detected content types
- **Downloads Automatically**: Can download CIF dictionaries from official COMCIFS repositories:
  - CIF Core Dictionary (COMCIFS)
  - Modulated Structures Dictionary (cif_ms.dic)
  - Twinning Dictionary (cif_twin.dic)
  - Powder Diffraction Dictionary (cif_pow.dic)
  - Magnetic Structure Dictionary (cif_mag.dic)
  - Image CIF Dictionary (cif_img.dic)
  - Electron Diffraction Dictionary (cif_ed.dic)
  - And more...

#### Dictionary Suggestion Examples
```
# Modulated Structure Detection
_cell_modulation_dimension 1        → Suggests: Modulated Structures Dictionary
_space_group_ssg_name 'P1(α0γ)'    → Confidence: 100%

# Twinning Detection  
_twin_individual_id 1               → Suggests: Twinning Dictionary
_twin_individual_mass_fraction 0.6  → Confidence: 100%

# Powder Diffraction Detection
_pd_meas_2theta_range_min 5.0       → Suggests: Powder Dictionary
_pd_proc_ls_prof_R_factor 0.045     → Confidence: 100%
```

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

## Technical Architecture & Recent Fixes

### Core Components
- **`CIFDictionaryManager`**: Central dictionary management and field conversion logic with smart suggestion capabilities
- **`DictionarySuggestionManager`**: Intelligent content analysis and dictionary recommendation engine
- **`FieldDefinitionValidator`**: Validates field definition files and extracts field patterns
- **`CIFFieldChecker`**: Main validation engine for field completeness checking
- **`FieldRulesValidator`**: Advanced field rules validation system
- **`DictionarySuggestionDialog`**: User interface for dictionary recommendations with download functionality

### Critical Bug Fixes (September 2025)

#### 1. Text-Block Insertion Bug
**Problem**: During CIF1→CIF2 conversion, field names were being replaced everywhere in the file, including inside semicolon-delimited text blocks like `_publ_section.references`. For example:
```
# BEFORE (broken):
_publ_section.references
;
Crystal structure at _diffrn_ambient_temperature 
;
# After conversion: _diffrn.ambient_temperature would be inserted into the text!
```

**Root Cause**: Both `convert_cif_format()` and `resolve_field_aliases()` methods used simple `string.replace()` operations that didn't respect text block boundaries.

**Solution**: Implemented `_replace_field_text_block_aware()` method that:
- Detects semicolon-delimited text blocks (`; ... ;`)
- Only replaces field names outside protected text regions
- Preserves all content inside text blocks exactly as-is

#### 2. False Field Detection in Comments
**Problem**: Field extraction regex was matching underscores in comments and non-field contexts.

**Solution**: Enhanced regex patterns to only match legitimate CIF field names starting with underscore followed by alphanumeric characters.

#### 3. Enhanced Dictionary Field Lookup
**Problem**: Field validation was not comprehensive enough for complex field patterns.

**Solution**: Added file-based field validation and improved field pattern matching.

### Development Environment Setup
```bash
# For development work:
git clone https://github.com/danielnrainer/CIF_checker.git
cd CIF_checker

# Install in development mode
pip install -e .
pip install -r requirements.txt

# Key files for debugging:
src/utils/cif_dictionary_manager.py    # Core conversion logic
src/utils/field_definition_validator.py # Field pattern validation
src/gui/main_window.py                 # Main GUI application
```

### Testing the Text-Block Fix
```python
# Test case to verify the fix works:
from src.utils.cif_dictionary_manager import CIFDictionaryManager

test_cif = '''
_diffrn_ambient_temperature 293.15
_publ_section_references
;
Crystal structure at ambient temperature.
Reference with _diffrn_ambient_temperature in text.
;
'''

manager = CIFDictionaryManager()
result, changes = manager.convert_cif_format(test_cif, 'CIF2')
# Should convert field outside text block but preserve text block content
```

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

