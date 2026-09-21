# Changelog

All notable changes to CIVET are documented in this file. Dates are release dates; entries are grouped by
theme rather than strict chronological commit order.

## since 1.4

### Fixed
- **Data names, block codes, and `.cif_rules` field matching were sometimes compared
  case-sensitively**: per the CIF spec, these identifiers are case-insensitive, but several code
  paths compared them literally instead.
  - The core parser's field lookups (`get_field`, `has_field`, `set_field_value`) now match
    case-insensitively while preserving each field's original on-disk spelling; editing a field
    under different case now updates it in place instead of creating a duplicate.
  - Duplicate/alias-conflict detection now catches a data name repeated with different case,
    previously invisible when the name wasn't in any loaded dictionary.

## [1.4] - 2026-09-18

### Added
- **Headless CLI** (`src/cli.py`): `check` (syntax/data-name/data-value validation, text or JSON
  output), `convert` (CIF1↔CIF2 syntax and legacy↔modern notation conversion), and `lint-rules`
  (structural validation of a `.cif_rules` file) subcommands, wrapping the same validation/
  conversion modules the GUI uses so CIF files can be screened or converted in CI/batch pipelines
  without launching the editor.
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
- **Local-prefix-aware data name suggestions**: Data Name Validation now recognizes a local prefix
  embedded mid-name after a real dictionary category (e.g. `_chemical_oxdiff_formula`) and offers to
  correct it to modern dotted notation (`_chemical.oxdiff_formula`) or, for a legacy-format file, the
  legacy-valid reordering with the prefix moved to the front (`_oxdiff_chemical_formula`) - a local
  prefix can only be the first segment in legacy notation, never embedded mid-name.
- **Loop Editor**: any `loop_` can now be opened as a spreadsheet-style table via **Actions → Edit
  Loop...** or **Edit Loop...** in the editor's right-click menu. Opens pre-loaded with the loop under
  the cursor, or blank if the cursor isn't inside one; a picker built into the dialog itself lists
  every loop in the file to switch to, plus a "New Loop" option to build one from scratch. Add,
  delete, or rename columns (data items); add or delete rows; edit individual cells; or set every
  row's value for one column in a single action. Only the edited loop's text is rewritten (or a new
  one inserted at the cursor) - the rest of the file is left untouched. A **Freeze First Column**
  checkbox (on by default) keeps the first column in view while scrolling through wide loops, and the
  header row of data names is bold. On multi-block files, a **Filter by Data Block** control narrows
  the picker to loops from just the selected block(s).
- **Data Name Validation flags loop columns**: a data name that's a `loop_` column (not a standalone
  field) now shows a 🔁 indicator and tooltip in the list, and clicking **Delete** on one asks for
  confirmation - explaining that the whole column (its value in every row) will be removed, and
  pointing to the Loop Editor for finer-grained changes.
- **Unsaved-changes exit confirmation**: closing CIVET with unsaved edits now prompts to Save,
  Discard, or Cancel instead of exiting silently; choosing Save keeps the window open if the save is
  cancelled or fails.
- **Rename Data Block**: **Actions → Rename Data Block...** renames a `data_` block and follows the
  rename to every place the block's code is referenced elsewhere in the file - `_vrf_<ALERT>_<code>`
  checkCIF/PLATON validation-reply-form field names inside the block, `_audit.block_code` when it
  matches the block's own code, any `_audit_link.block_code` value elsewhere in the file (including
  inside a `loop_`) that points at this block, and the echoed `data_` header of a pasted `.fcf`
  reflection listing inside `_iucr_refine_fcf_details`. Nothing else in the file is touched, and the
  new name is validated (non-empty, no whitespace/reserved characters, not already used by another
  block) before anything is changed.

### Changed
- **Selection highlight color**: the default blue selection background clashed with several of the
  category colors used in dialogs like Data Name Validation, making selected rows hard to read.
  Selections across the app now use a neutral grey background with black text instead.
- **Registered CIF prefixes now come from the live IUCr registry** instead of a bundled static list:
  CIVET fetches and caches the official
  [reserved-prefixes registry](https://cif-dictionaries.iucr.org/cifdic/dic/reserved_prefixes.cif),
  refreshing it automatically in the background when the cache is missing or stale (30+ days), or
  on demand via a new **Update from IUCr Registry** button in **Settings → View Recognised
  Prefixes...**. Falls back to a bundled offline snapshot when there is no cache yet and no network.
- User-allowed (unofficial) prefixes and fields - added via **Add User Prefix...** for local prefixes
  not yet registered with IUCr, now stored in a `user_allowed_prefixes.cif` file in the CIVET config
  directory making them visible, editable, and portable alongside the rest of CIVET's configuration.
- **Validate Field Rules dialog works on any `.cif_rules` file**: **Settings → Validate Field
  Rules...** still defaults to the file currently selected in **CIF Field Definition Selection**
  (built-in, user, or custom), but the dialog now has an **Open Another File...** button to load and
  validate any other `.cif_rules` file without closing it. Its file picker opens in CIVET's user
  field-rules directory by default, and a file bar at the top shows which file is under validation.
  The dialog's header sections ("How to use this dialog", "Validation Summary") are now collapsible -
  "How to use" starts collapsed - and the decorative group boxes were trimmed, so the Validation
  Issues list gets the bulk of the vertical space; the issue-details pane can also be dragged away
  entirely.
- **Data Name Validation dialog category order and colours**: categories now list as Malformed →
  Unknown → Deprecated → Malformed User Allowed → User Allowed → Registered Local → Valid, and
  **User Allowed Fields** no longer shares **Valid Fields**' green - a user-allowed exception isn't
  necessarily correct, just tolerated. A new **Malformed User Allowed Fields** category separates
  fields whose embedded local prefix is only user-allowed (not IUCr-registered) from the main
  Malformed bucket.
- Offering to add a real dictionary category (e.g. "refln") as a local prefix, or to exempt a field
  name that isn't a recognized attribute of its own category, now requires explicit confirmation, and
  is shown disabled with an explanation - rather than silently unavailable - when it would be wrong.

### Fixed
- **Paste always uses the editor's own formatting**: pasting into the main editor or the multi-line
  field editor no longer carries over fonts/styling from the source application (e.g. Word) - text is
  inserted as plain text and picks up whatever font/colors the editor is currently using.
- **Data Name Validation delete action left orphan values**: deleting a field from the Data Name
  Validation dialog sometimes only removed the data-name but not the data value leaving a valueless 
  data value behind and the CIF invalid. The whole data item (name *and* value) is now correctly removed.
- **Deleting or renaming a loop column corrupted the loop**: a `loop_` is a table where data names are
  the column headers, so removing or renaming one without touching every row left rows with the wrong
  number of values (or a mismatched header/data count). Deleting a loop column - or a deprecated
  field being replaced/renamed - now rewrites the whole loop, removing or renaming the column and
  dropping its value from every row (deleting every column removes the loop entirely). Only adding a
  brand-new successor column is still skipped, with a warning, since there's no sensible value to
  backfill into existing rows.
- **DDL1 dictionary parsing**: `_list_link_parent`/`_list_link_child` values are themselves data names
  (e.g. `_pd_phase_id`), but were silently discarded by an extraction heuristic meant to catch tags with
  no value, so they never reached field metadata despite being parsed. Both tags are now correctly
  extracted and exposed on `FieldMetadata` and via `CIFDictionaryManager.get_relational_links()`.
- **False "Fix" suggestion for unrelated unknown fields**: an unrecognized field under a real
  dictionary category (e.g. `_refln_frame_id`) no longer gets a fabricated dot-notation "fix" -
  `_refln.frame_id` isn't a genuine field, and "frame" isn't a local prefix, but this was previously
  suggested as if it were. The dialog now explains that the category is known but the rest of the
  name isn't a recognized attribute, instead.
- **A real dictionary category could be added as a local prefix**: doing so (via the old "+ Prefix"
  button, or **Add User Prefix...**) would silently accept *any* unrecognized field under that
  category from then on, masking real typos and errors. Both entry points now refuse and explain why;
  a category previously added this way is also now disregarded even if it's still sitting in a
  user's saved allowed-prefixes list.
- **A recognized local prefix embedded mid-name stopped being flagged entirely**: once a prefix like
  "oxdiff" in `_chemical_oxdiff_formula` was added to the allowed-prefixes list, the field was filed
  away as fully valid, even though the name itself (prefix in the middle) isn't valid in any CIF
  notation. It's now categorized Malformed / Malformed User Allowed and still requires a rename.
- **Data-name validation cache could leak a suggestion between unrelated files**: a legacy-format
  file's suggested rename for a field could incorrectly stick around and be reused when a
  differently-formatted file was validated afterward and happened to reuse the same field name.

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
