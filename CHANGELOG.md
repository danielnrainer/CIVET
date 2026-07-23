# Changelog

All notable changes to CIVET are documented in this file. Dates are release dates; entries are grouped by
theme rather than strict chronological commit order.

## since 1.3

### Added
- **IF / IF NOT checks**: keywords for .cif_rules files extended to include if / if not logic
- **Multi-Data-Block Support**: CIF files containing several `data_` blocks (e.g. multiple crystals
  or a variable-temperature series) are now checked block-by-block.
  - **Start Checks** detects multiple data blocks and lets you choose which ones to check, plus a
    **Shared** (default) or **Independent** check mode. Shared mode prompts once for a field when
    all selected blocks agree on its value, and only opens a per-block resolution table when values
    genuinely differ - so a variable-temperature file needs no extra configuration to get one
    shared prompt for common metadata and a per-block prompt for temperature.
  - Check dialogs show which data block(s) they apply to in a bold banner.
  - **Data Name Validation** lists every block a field occurs in and lets you apply a fix to all
  - blocks or scope it to just one.
  - Duplicate/alias-conflict detection, the legacy-compatibility-fields action, and the refinement
    special-details editor now all run per data block.
  - The **File Status** panel's first row reports the data-block count, with a new scope selector
    to show syntax/notation/data-name/data-value status for the whole file or a single block; a
    tooltip explains the combined "all blocks" issue count against the per-block breakdown.
- **Check Progress Indicator**: **Start Checks** now shows a "Check N/Total" counter and progress
  bar in the status bar for the duration of a run, echoed in a banner inside each field-check
  dialog. The total is an estimate derived from the loaded `.cif_rules` set and the number of
  selected data blocks, and grows on the fly if a run needs more steps than predicted.
- **DDL1 parent/child key checking**: `CIFDataValidator.check_parent_child_links()` verifies that
  values in a field declared as a DDL1 child key (`_list_link_parent`) or referenced as a parent key
  (`_list_link_child`) actually match a value in the linked field.

### Fixed
- **DDL1 dictionary parsing**: `_list_link_parent`/`_list_link_child` values are themselves data names
  (e.g. `_pd_phase_id`), but were silently discarded by an extraction heuristic meant to catch tags with
  no value, so they never reached field metadata despite being parsed. Both tags are now correctly
  extracted and exposed on `FieldMetadata` and via `CIFDictionaryManager.get_relational_links()`.

## [1.3] - 2026-07-06

### Added
- **CIF Syntax Compliance dialog**: dedicated tabbed dialog (CIF 2.0 / CIF 1.1 / all) covering syntax-version
  compliance issues, with line navigation, scoped **Fix All** actions, refresh, and a non-ASCII character
  conversion entry point. A live, debounced **File Status panel** now sits alongside field-rule selection,
  tracking syntax compliance, notation state, and the latest data-name/data-value validation outcomes.
- **Data-Name Integrity resolution**: detects duplicate data names and alias groups with conflicting values;
  **Save** now blocks until conflicts are resolved, and conversion/fix workflows prompt for guided manual or
  automatic resolution (with an option to keep aliases and synchronize their values).
- **Data Value Validation** (`Actions → Validate Data Values...`): validates field values against
  dictionary-defined types, numeric ranges, and enumeration sets, and detects loop count mismatches, in a
  sortable, colour-coded, live-refreshable results dialog.
- **Dictionary Search** (`Dictionaries → Search Loaded Dictionaries...`): search loaded dictionaries by data
  name, alias, category, and optionally description text, with multi-dictionary filtering, cross-checking
  against the current CIF, and a right-click "Search in Dictionaries" shortcut from the editor.
- **`.cif_rules` Legacy/Modern notation converter**: convert a field-rules file's notation from the main
  menu; **Start Checks** now detects a notation mismatch between the loaded CIF and the active rule set and
  offers to convert the rules, convert the CIF, run as-is, or cancel.
- **Deprecated-field remediation upgrades** in the Data Name Validation dialog: **+ Successor** (prefers a
  legacy successor name for legacy/mixed files), **Replace** (swap the deprecated name for its successor in
  place), and **Delete** (remove the deprecated field once its successor already exists).
- **Command-line file opening**: `python src/main.py path/to/file.cif` opens a file on startup; unknown
  arguments are ignored so future Qt flags can pass through safely.
- **Editor/UX additions**: `Edit → Reload File` (`Ctrl+Shift+R`); customisable syntax-highlighting colours
  (including a distinct "modern-only" category) via Editor Settings, with a `Help → Syntax Highlighting
  Guide...` reference; configurable per-dialog interaction modes with editor (allow editing / browse read-only /
  modal-lock).
- **Absolute structure check** generalised from 3D-ED-only to any Sohncke space group, plus a check for the
  presence of a z-score for electron diffraction data.

### Changed
- Dictionary Information dialog: improved dictionary name recognition, clearer notes on active dictionary
  types, corrected detail-line display, updated development/release dictionary URLs, and sortable/resizable
  columns in the Loaded Dictionaries table.
- Malformed-field detection now works correctly in modern (dot) notation, prefers legacy replacement names
  for legacy/mixed CIF files when a legacy alias exists, and folds into the Data Name Validation dialog
  rather than a separate pre-check step.
- Main menu items reordered; clearer in-dialog explanations (e.g. "Replace" in Data Name Validation).
- Performance: debounced/background compliance checks, content-hash-based reparse avoidance, and caching
  across dictionary lookups and data-value validation for better responsiveness on larger files.

### Fixed
- Modern-only data-name classification no longer misclassifies malformed/unknown dotted names as
  modern-only in editor highlighting and the File Status panel.
- Sequential `.cif_rules` processing now applies each rule immediately (e.g. a `RENAME` followed by a
  `CHECK` for the old name correctly prompts to re-add it), and repeated `APPEND` runs no longer duplicate
  content already present in a semicolon-block value.
- Various fixes to deprecated-field checks, dictionary search line-mapping/highlighting, and multiline-value deletion edge cases.

### Testing
- Continued expansion of the workflow-oriented automated test suite (parsing, format conversion, data-name
  and data-value validation, dictionary search, dialog navigation, field-checking decisions, syntax
  compliance) plus new performance baseline tooling.

## [1.2] - 2026-02-21

### Added
- **CIF Data Name Validation** (new): Data Name Validation dialog to review, allow, delete, or correct
  field names against loaded dictionaries and IUCr registered prefixes, with validation-aware syntax
  highlighting; Recognised Prefixes dialog and an interactive prefix/field manager with live validation
  refresh.
- **Dictionary format auto-detection and DDL1 support**: full DDL1 dictionary parser alongside the
  existing DDLm parser, score-based format detection (DDLm/DDL1/DDL2), and enhanced field metadata
  (units, `ddl_format`, `source_dictionary`).
- **Dictionary update system**: check bundled/user dictionaries for updates, load-only vs. save & load,
  bulk "Load/Download All Updates", user dictionary overrides stored in the platform AppData directory.
- **Persistent, cross-platform user configuration** (Windows/macOS/Linux AppData): settings, user field
  rules, and recognised prefixes now survive updates and reinstalls; new Editor Settings dialog (font,
  size, line numbers, syntax highlighting, ruler) and Built-in/User/Custom field-rules selection UI.
- **`CALCULATE` and `RENAME` actions** in `.cif_rules`, with safe expression evaluation for `CALCULATE`
  and computed-value suggestions surfaced to the user.
- **`APPEND` action** for multiline CIF fields (e.g. `_publ_section_references`).
- **CIF2 value formatting**: smart bracket quoting for values containing `[ ] { }`, triple-quoted string
  support (`'''`/`"""`), and automatic quoting of CIF2 special characters on save.
- **Audit trail automation**: `_audit_creation_date` refreshed and a CIVET signature appended to
  `_audit_creation_method` automatically on save.
- **About dialog** and `version.py` module: displays version, author, and GitHub/Zenodo links.
- File status bar now shows explicit saved/unsaved state for the current file.

### Changed
- Deprecated-field handling now retains the deprecated field and adds its successor alongside it, rather
  than replacing it outright; the redundant "Keep" action was consolidated into "Skip".
- Built-in field rules auto-switch to the paired legacy variant when legacy CIF content is detected.

### Fixed
- Field-rules selection hardened against stale/empty dropdown selections.
- Corrected mis-notated data names in `3ded_legacy.cif_rules`.

## [1.1] - 2026-01-08

### Added
- **Robust deprecated-field handling**: auto-replace deprecated fields with modern equivalents, unified
  duplicate/alias/deprecated detection in a single workflow, and automatic dedicated deprecated-field
  section formatting.
- **Legacy/modern terminology rename**: CIF1/CIF2 renamed to legacy/modern throughout the UI and codebase.
- **checkCIF compatibility**: dedicated `checkcif_compatibility.cif_rules` field list plus an automatic
  format-conversion suggestion dialog shown on file load.
- **IUCr official release dictionary support**, with source/status indicators and an active/inactive
  toggle in the dictionary info dialog.
- **Dropdown suggestions** for field values, aggregated from repeated `.cif_rules` entries, with
  default-value and current-CIF-value markers.
- **Modern-notation checkCIF warning** (dismissible) and automatic `#\#CIF_2.0` header insertion on save.
- **Critical Issues dialog**: scrollable and robust for large issue lists.
- **Linux installation instructions** (virtual-environment based; notes on `libxcb-cursor0`/`libxcb-util1`).

### Changed
- Window title always shows "CIVET - filename".
- Loop data reformatting now respects the 80-character line limit.
- Field conflict dialog and auto-resolve logic are legacy/modern-format aware.

### Fixed
- Case preservation for field names during conversion (e.g. `_space_group.IT_number`).
- Deprecated-field warnings no longer fire for legacy CIF files.
- Text-block field name conversion, with a pattern-based fallback for unmapped fields.

## [1.0] - 2025-10-10

First release under the CIVET name.

### Added
- **Rebrand to CIVET** (CIF Validation and Editing Tool), including new icon/logo, UTF-8-safe PyInstaller
  executables, and the current CIF filename shown in the window title.
- **CIF1/CIF2 format detection** for 3D ED field rules with automatic switching, plus a dedicated
  CIF1-compatible rule set (`3ded_cif1.cif_rules`).
- Deprecated-field checking in the main GUI with auto-replacement, and case-insensitive matching for
  deprecated field names.

### Changed
- Improved CIF field alignment/reformatting, including correct handling of loops containing multiline
  entries.
