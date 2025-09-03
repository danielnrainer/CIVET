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
*Last updated: August 18, 2025*
*Feel free to modify this file as priorities change or new requirements emerge*
