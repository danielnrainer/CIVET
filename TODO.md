# CIF_checker TODO List

## ✅ Completed Items
- [x] Fixed syntax error in main_window.py (line 403 malformed comment)
- [x] Removed duplicate `load_cif_field_definitions()` function from main_window.py
- [x] Verified code consistency and removed import errors
- [x] All Python files now pass syntax checks
- [x] Fixed `check_refine_special_details()` method to properly handle CIF multiline fields
- [x] **MAJOR OVERHAUL**: Implemented comprehensive CIF parser system
  - [x] Created new `CIF_parser.py` with proper field parsing logic
  - [x] Replaced fragmented field handling with centralized dictionary-based system
  - [x] Updated all field checking methods to use new parser
  - [x] Now properly handles both single-line and multiline CIF fields
  - [x] Automatic detection of multiline vs single-line format
  - [x] Proper CIF syntax generation and formatting
- [x] **BUG FIX**: Fixed multiline CIF parsing for cases where content starts on same line as opening semicolon
  - [x] Added `_parse_multiline_value_with_content_on_first_line()` method
  - [x] Updated field parsing logic to handle `;content...` format
  - [x] Fixed issue where `_refine_special_details` was only showing first line
- [x] **REFORMATTING**: Implemented 80-character line length reformatting
  - [x] Added proper line breaking within multiline semicolon blocks
  - [x] Smart detection of when to use single-line vs multiline format
  - [x] Eliminated unnecessary empty lines in CIF output
  - [x] Fixed method signature and integration issues
- [x] **CODE ORGANIZATION**: Improved file structure and naming
  - [x] Renamed `CIF_field_parsing.py` → `field_definitions.py` for clarity
  - [x] Updated `CIFField` → `CIFFieldDefinition` to avoid naming conflicts
  - [x] Clear separation: `field_definitions.py` handles validation schemas, `CIF_parser.py` handles content parsing
  - [x] Updated all imports and documentation accordingly

## ✅ Recently Completed (September 2025)
- [x] **CHECK CONFIGURATION SYSTEM**: Added configuration dialog for field checking
  - [x] Created `CheckConfigDialog` with checkbox options for checking behavior
  - [x] Option 1: Auto-fill missing fields with default values (no user prompts)
  - [x] Option 2: Skip prompts for fields that already match default values  
  - [x] Updated `start_checks_3ded()` and `start_checks_hp()` to use configuration
  - [x] Created `check_line_with_config()` method to respect configuration settings
  - [x] Dialog appears before starting any checks, can be cancelled to abort

- [x] **CRITICAL BUG FIX: CIF Loop Structure Preservation**
  - [x] Fixed major bug where CIF loop structures were corrupted during reformatting
  - [x] Added `CIFLoop` class to properly represent loop structures
  - [x] Updated `CIFParser` to detect and parse `loop_` blocks correctly
  - [x] Implemented `_parse_loop()` method for proper tabular data parsing
  - [x] Added `_format_loop()` method to preserve loop structure in output
  - [x] Fixed issue where loop data was incorrectly converted to semicolon-delimited format
  - [x] Loop structures now maintain proper tabular format with space-separated values
  - [x] Proper handling of quoted values within loop data rows

- [x] **MODULAR CODE REFACTORING (Step-by-Step Approach)**
  - [x] Extracted `CIFSyntaxHighlighter` from `main_window.py` to dedicated `src/gui/editor/` module
  - [x] Created modular dialog system with separate classes:
    - [x] `CIFInputDialog` - Field editing with abort/stop/default options
    - [x] `MultilineInputDialog` - Large text field editing
    - [x] `CheckConfigDialog` - Field checking configuration
  - [x] Organized dialogs in `src/gui/dialogs/` package with proper `__init__.py`
  - [x] Updated imports and maintained backward compatibility
  - [x] Reduced `main_window.py` by ~350 lines while improving modularity

- [x] **CIF HEADER PRESERVATION BUG FIX**
  - [x] Fixed critical bug where `data_` lines were being deleted during reformatting
  - [x] Enhanced `CIFParser` to preserve important header lines (`data_`, `save_`, `global_`, `stop_`)
  - [x] Added `header_lines` tracking and proper content block ordering
  - [x] Updated `generate_cif_content()` to output headers before fields
  - [x] Ensured CIF files maintain valid structure after reformatting

- [x] **SYNTAX HIGHLIGHTING IMPROVEMENTS**
  - [x] Fixed loop syntax highlighting bugs where loops didn't terminate properly
  - [x] Implemented proper CIF-compliant loop termination detection:
    - [x] Loops end on empty lines when in data phase
    - [x] Loops end on new fields (`_fieldname`) after data phase
    - [x] Loops end on CIF headers (`data_`, `save_`, etc.) or new `loop_` statements
  - [x] Fixed issue where loop field definitions were incorrectly highlighted as non-loop content
  - [x] Added proper state management for loop field definitions vs. loop data phases
  - [x] Synchronized loop termination logic between syntax highlighting and CIF parser

- [x] **STANDALONE EXECUTABLE CREATION**
  - [x] Created comprehensive `CIF_checker.spec` file for PyInstaller
  - [x] Added all hidden imports for PyQt6, utils, and GUI modules
  - [x] Included data files (field definitions, CIF dictionary) in executable
  - [x] Created `build_exe.bat` script for automated build process
  - [x] Added `BUILD.md` documentation with complete build instructions
  - [x] Verified successful standalone executable creation (~37MB)
  - [x] Tested executable runs independently without Python installation

- [x] **UNIFIED FIELD DEFINITION SELECTION SYSTEM**
  - [x] Replaced separate 3DED/HP buttons with unified "Start Checks" button
  - [x] Added radio button selection for field definition sets (3D ED, HP, Custom File)
  - [x] Implemented custom field definition file support with file browser
  - [x] Added file validation and visual feedback for custom files
  - [x] Enhanced user experience with smart UI state management
  - [x] Updated menu system to use unified check approach
  - [x] Maintained all existing functionality (configuration dialog, abort/stop options)

- [x] **CIF FORMATTING IMPROVEMENTS**
  - [x] Fixed loop spacing issue where fields immediately followed loops without empty lines
  - [x] Enhanced `generate_cif_content()` to add empty line after loops when followed by fields
  - [x] Maintained proper spacing: loops → empty line → fields, but fields → fields (no empty line)
  - [x] Improved CIF readability while maintaining format compliance

## 🔄 Current Priority Items

### Field Definitions Modernization
- [ ] **Update field definitions to 2025 CIF Core Dictionary standards**
  - [ ] Replace deprecated underscore notation with dot notation (e.g., `_diffrn_ambient_temperature` → `_diffrn.ambient_temperature`)
  - [ ] Update `field_definitions.cif_ed` to use modern CIF standards
  - [ ] Update `field_definitions.cif_hp` to use modern CIF standards
  - [ ] Review and update `field_definitions_all.cif_defs` (contains many deprecated fields)
  
### Missing Modern Electron Diffraction Fields
- [ ] **Add new 2025 CIF core fields for electron diffraction:**
  - [ ] `_diffrn.flux_density` (electron flux in e/Å²/s)
  - [ ] `_diffrn.total_dose` (total electron dose in MGy)
  - [ ] `_diffrn.total_dose_su` (standard uncertainty)
  - [ ] `_diffrn.total_exposure_time` (total exposure time in minutes)
  - [ ] `_diffrn.precession_semi_angle` (for precession electron diffraction)
  - [ ] `_diffrn.precession_semi_angle_su` (standard uncertainty)
  - [ ] `_diffrn_source.ed_diffracting_area_selection` (SAED vs probe selection)
  - [ ] `_diffrn_radiation.illumination_mode` (parallel vs convergent beam)
  - [ ] `_diffrn.special_details` (beam instability, crystal motion, degradation)

### Field Definition File Structure
- [ ] **Consolidate field definition formats:**
  - [ ] Decide on single format for field definition files (.cif_ed, .cif_hp, .cif_defs)
  - [ ] Standardize comment and description format
  - [ ] Create template for new field definitions

### Backward Compatibility
- [ ] **Implement support for legacy CIF files:**
  - [ ] Add mapping from old field names to new field names
  - [ ] Ensure old CIF files can still be processed
  - [ ] Add option to convert old field names to new ones

### Code Improvements
- [ ] **Enhance field validation:**
  - [ ] Add field type validation (Real, Text, Code, etc.)
  - [ ] Add unit validation for numeric fields
  - [ ] Add enumerated value validation where applicable
  - [ ] Add range validation for numeric fields

- [ ] **Improve user experience:**
  - [ ] Add field tooltips showing CIF core dictionary descriptions
  - [ ] Improve error messages with CIF standard references
  - [ ] Add progress indication for lengthy check operations

### Documentation
- [ ] **Update documentation:**
  - [ ] Update README.md with 2025 CIF standards information
  - [ ] Document new field definitions and their purposes
  - [ ] Add usage examples for electron diffraction CIFs
  - [ ] Document field definition file formats

### Testing
- [ ] **Add testing framework:**
  - [ ] Create test CIF files for validation
  - [ ] Add unit tests for field parsing
  - [ ] Add integration tests for GUI operations
  - [ ] Test with real electron diffraction CIF files

## 🔮 Future Enhancements

### Advanced CIF Processing Features
- [ ] **"Stripped CIF" Creation**
  - [ ] Implement functionality to create minimal CIF files with only essential fields
  - [ ] Allow user selection of which field categories to include/exclude
  - [ ] Useful for creating publication-ready CIF files or data sharing
  - [ ] Option to strip comments, verbose descriptions, and optional fields

- [ ] **CIF Core Dictionary Validation**
  - [ ] Implement validation against official `cif_core.dic` from IUCr
  - [ ] Parse CIF dictionary format and extract field definitions, types, and constraints
  - [ ] Add real-time validation of field names, types, and enumerated values
  - [ ] Display official CIF core descriptions and allowed values
  - [ ] Flag non-standard or deprecated fields

- [ ] **CIF-1 ↔ CIF-2 Converter**
  - [ ] Implement bidirectional conversion between CIF-1 and CIF-2 syntax
  - [ ] Handle syntax differences (quoted strings, nested structures, etc.)
  - [ ] Detect mixed CIF-1/CIF-2 notation and resolve discrepancies
  - [ ] Smart field mapping between different CIF versions
  - [ ] Preserve data integrity during conversion
  - [ ] Add validation to ensure converted files meet target CIF standard

### Advanced Features
- [ ] **CIF validation against official dictionary:**
  - [ ] Implement full CIF core dictionary parsing
  - [ ] Add validation against official CIF syntax rules
  - [ ] Support for custom dictionary extensions

- [ ] **Export/Import features:**
  - [ ] Export field definitions to different formats
  - [ ] Import field definitions from other sources
  - [ ] Batch processing for multiple CIF files

- [ ] **Integration improvements:**
  - [ ] Plugin architecture for custom validators
  - [ ] Integration with crystallographic software packages
  - [ ] Command-line interface for automation

### User Interface Enhancements
- [ ] **GUI improvements:**
  - [ ] Dark mode support
  - [ ] Customizable field checking workflows
  - [ ] Better visual feedback for field status
  - [ ] Drag-and-drop file support

## 📝 Notes for Manual Updates
- Add any subjective or personal field definition preferences here
- Note any specific requirements for your research group/institution
- Track any changes needed based on user feedback
- Record any specific electron diffraction requirements not covered by CIF core

## 🗓️ Timeline Suggestions
1. **Week 1-2:** Field definitions modernization (highest priority)
2. **Week 3:** Add missing electron diffraction fields
3. **Week 4:** Backward compatibility and validation improvements
4. **Future:** Advanced features and testing framework

---
*Last updated: September 4, 2025*
*Feel free to modify this file as priorities change or new requirements emerge*
