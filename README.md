# CIVET

**CIF Validation and Editing Tool** - A modern CIF (Crystallographic Information File) editor and validator with intelligent field checking, format conversion, and UTF-8 support.


_Disclaimer_\
The code in this project has been written in large parts by Anthropic LLM models (mainly Sonnet 4.5 and Opus 4.5).


*Be advised that this software is in constant development and might therefore contain bugs or other unintended behaviour.
Always check your CIF files carefully and if you encounter an issue and would like to report it, please do so via the [Issues](https://github.com/danielnrainer/CIVET/issues) section.*

## Known checkCIF Compatibility Notes

A few CIVET behaviours exist specifically to keep files compatible for example with IUCr's checkCIF service:

- **Multiline text blocks are never rewritten.** Content inside a semicolon-delimited (`;...;`) or CIF 2.0 triple-quoted (`"""..."""` / `'''...'''`) value — such as the reflection/refinement narrative in `_iucr_refine_fcf_details` — is treated as opaque text. CIVET does not convert notation, flag deprecated data names, or otherwise modify anything inside these blocks, even if the text happens to contain data-name-like strings (e.g. software echoing part of the CIF back into a details block). This is intentional: checkCIF and other downstream tools may expect that content to survive untouched. I will review this periodically and change the behaviour if it becomes safe to do so.
- **Some legacy data names are deliberately retained alongside their modern successors.** For example, `_cell_measurement_temperature` is kept even when the modern `_diffrn_ambient_temperature` is present, because checkCIF's [PLAT197](https://journals.iucr.org/services/cif/checking/PLAT197.html) check does not yet recognise the modern name. The full list of these data names (as far as I am aware) lives in [field_rules/checkcif_compatibility.cif_rules](field_rules/checkcif_compatibility.cif_rules) and is reviewed periodically as checkCIF is updated.

## Key Features (v1.3)

- **CIF Editing and Validation**: Syntax highlighting, guided dialogs, smart field checks, and duplicate/alias-aware workflows.
- **Command-Line File Opening**: Launch CIVET with an optional CIF file path argument to open it on startup (unknown arguments are ignored, so Qt flags can be passed through safely).
- **Flexible Field Rules Engine**: Supports `CHECK`, `DELETE`, `EDIT`, `RENAME`, `CALCULATE`, and `APPEND` actions, plus `IF`/`IF NOT` ... `ENDIF` conditional blocks, in `.cif_rules` files.
- **Legacy/Modern CIF Handling**: Detects legacy, modern, and mixed notation; includes conversion plus integrated malformed-field detection and correction.
- **`.cif_rules` Notation Converter**: Converts a field-rules file between legacy and modern notation from the main menu; when a loaded CIF's notation doesn't match the active rule set, **Start Checks** offers to convert the rules, convert the CIF, run as-is, or cancel.
- **CIF Syntax Compliance Dialog**: Dedicated tabbed dialog (CIF 2.0 / CIF 1.1 / all) for syntax-version compliance issues, with line navigation, scoped **Fix All** actions, refresh, and a non-ASCII character conversion entry point.
- **CIF2 Compliance Support**: Maintains `#\#CIF_2.0` headers and handles CIF2 quoting/formatting edge cases (including triple-quoted values and CIF2 lists/tables).
- **Dictionary-Backed Intelligence**: Multi-dictionary loading, metadata display, update checks, and parser support for DDLm + DDL1 dictionaries.
- **Dictionary Search**: Search loaded dictionaries by data name, alias, category, and optionally description text; filter to selected dictionaries and cross-check hits against the currently loaded CIF.
- **Data Name Validation**: Validates names against loaded dictionaries and IUCr registered prefixes, groups malformed/unknown/deprecated names, offers one-click fixes (including **Replace** and **Delete** for deprecated fields with an existing successor), and uses validation-aware highlighting. On multi-block files, a field's occurrences across all blocks are shown together, and any fix can be applied to all blocks or scoped to just one.
- **Data-Name Integrity Resolution**: Detects duplicate data names and alias groups with conflicting values, then offers guided manual or auto-resolution in save/conversion workflows. On multi-block files this runs per block, so the same data name legitimately repeated across blocks is never flagged as a duplicate.
- **Data Value Validation**: Validates field values against dictionary-defined types, numeric ranges, and enumeration sets; detects loop count mismatches. Results shown in a sortable, live-refreshable dialog. Accessible via **Actions → Validate Data Values...**
- **Multi-Data-Block Support**: Files with several `data_` blocks are checked block-by-block instead of silently mixing them up (see below for details).
- **Check Progress Indicator**: A live "Check N/Total" counter and progress bar in the status bar, echoed in each field-check dialog, shows how far a **Start Checks** run has gotten.
- **Live File Status Panel**: Side-by-side with field-rule selection, a compact status panel tracks the data-block count, syntax compliance (CIF 2.0 / CIF 1.1 / not compliant), notation state (modern/legacy/mixed), and latest data-name/data-value validation outcomes — for the whole file or a single selected data block.
- **Persistent User Configuration**: Cross-platform storage for settings, user rules, recognised prefixes, and downloaded dictionaries.
- **Productivity UX**: Built-in/user/custom rules selection, dropdown suggestions for field values, configurable dialog interaction modes, and focused editor settings.
- **Performance**: Debounced/background compliance checks, content-hash-based reparse avoidance, and caching across dictionary lookups and validation keep the editor responsive on larger files.

## Quick Start

### From Source (Windows)
```bash
git clone https://github.com/danielnrainer/CIVET.git
cd CIVET
pip install -r requirements.txt
python src/main.py
```

Optionally pass a CIF file to open on startup: `python src/main.py path/to/file.cif`.

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
pip install -r requirements-dev.txt
pyinstaller CIVET.spec
```

Compiled releases bundle only the runtime application and required runtime dependencies; development and test tools are not included.

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

# IF/THEN conditional blocks: run nested rules only when a condition holds
IF: _diffrn_radiation.probe electron   # field exists and equals "electron"
    CHECK: _diffrn_radiation_wavelength 0.02508
    CHECK: _diffrn.ambient_temperature 293
ENDIF

IF: _exptl_crystal.colour_lustre        # field exists (any value)
    DELETE: _exptl_crystal.colour_lustre_note
ENDIF

IF NOT: _cell_measurement.temperature   # field is absent
    CHECK: _cell_measurement.temperature 293
ENDIF
```

Conditions support `IF: _field` (field present, any value), `IF: _field value` (present and
equal to value), `IF: _field != value` (present and not equal), and `IF NOT: _field` (field absent).
There is no `exists` keyword - `IF: _field exists` is parsed as an equals-check against the
literal value `"exists"`, not as an existence test. Use the bare `IF: _field` form for that.
Nested rules use the same `CHECK:`/`DELETE:`/`EDIT:`/`APPEND:`/`RENAME:`/`CALCULATE:` syntax as
top-level rules (an explicit `CHECK:` prefix is optional at any nesting level); `DELETE:`/`EDIT:`/
`APPEND:`/`RENAME:` inside a block still only run for Custom/User rule sets. IF blocks may be
nested inside one another to any depth - each `ENDIF` closes the innermost still-open block.

Built-in sets include packaged `.cif_rules` files from `field_rules/` (for example 3DED modern and 3DED legacy).

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
- **Syntax Highlighting Colors**: Adjust the highlight colours used for valid, unknown, malformed, deprecated, loop, and value text directly in the dialog
- **80-Character Ruler**: Visual guide for line length
- **Dialog Behavior**: Three interaction modes for result dialogs: *Allow editing while open* (non-blocking, default for Validate Data Values), *Browse editor (read-only) while open*, and *Classic modal (lock editor)*. Each dialog can inherit the global default or set its own mode.

All settings are stored in `settings.json` and persist across sessions. User settings always take precedence over built-in defaults. Use **Reset to Defaults** to restore original settings.

Advanced users can also customise syntax-highlighting colours manually in `settings.json` under `editor.syntax_highlighting_colors`.

### Data Value Validation

The **Actions → Validate Data Values...** dialog checks all field values in the current file against dictionary definitions:

- **Type mismatches**: flags non-numeric values for `Real`/`Integer` fields
- **Enum violations**: flags values not listed in `_enumeration_set.state`
- **Loop count errors**: flags loops where the number of data values is not a multiple of the field count
- Results are shown in a sortable table with severity colour-coding (error/warning/info)
- **Refresh**: re-runs validation against the current editor content without closing the dialog, useful when editing to fix issues
- **Go to Line**: navigates the editor to the flagged line (double-click also works)

The dialog opens in non-blocking mode by default so you can edit while it is open. This can be changed under **Settings → Editor Settings → Dialog Behavior**.

### Dictionary Search

The **Dictionaries → Search Loaded Dictionaries...** dialog provides a searchable view over all currently loaded dictionaries:

- Searches canonical data names, known aliases, categories, and optionally description text
- Supports multi-dictionary selection, with the active CORE dictionary selected by default when available
- Marks whether hits are present in the current CIF, including separate states for canonical names, alias-only matches, and cases where both forms are present
- Shows dictionary metadata, known aliases, units, examples or allowed values, and the first matching CIF line
- Lets you jump directly to the matching line in the editor

You can also select a data name in the editor, right-click, and use **Search in Dictionaries** to open the dialog prefilled with that text.

### Data Name Validation Results

The validation results dialog now combines several related checks in one place:

- **Malformed Fields**: Detects names that are structurally wrong (including misplaced dots in modern notation) but can be mapped to a known field, and offers one-click, notation-aware correction.
- **Unknown Fields**: Flags names not recognised by loaded dictionaries or registered prefixes.
- **Deprecated Fields**: Offers a **+ Successor** action that adds the appropriate successor name while keeping the deprecated field, a **Replace** action that swaps the deprecated name for its successor in place, and a **Delete** action to remove the deprecated field once its successor already exists. In legacy or mixed CIF files, CIVET prefers a legacy successor name when one exists; otherwise it falls back to the modern name.
- **Conflict Resolution Controls**: The conflict dialog now supports keeping aliases while synchronizing all alias values when that strategy is preferred.
- **Details Tooltips**: Hover over the Details column to read the full text when the column is truncated.

Malformed-field fixes are now handled through the validation dialog itself rather than through a separate pre-check option.

### Syntax Highlighting Categories

When dictionary-aware validation highlighting is enabled, CIVET distinguishes field categories directly in the editor:

- **Valid fields**: green
- **Modern-only fields**: strong blue with underline (known modern names that have no legacy notation alias)
- **Registered local-prefix fields**: cyan/teal
- **User-allowed fields**: cyan/teal italics
- **Unknown fields**: red
- **Malformed fields**: red italics
- **Deprecated fields**: dark yellow with strikethrough

Without validation-aware categorisation, data names use a default purple fallback. Quoted values and multiline values are blue, `loop_` is bold orange, loop field names inherit their category styling and are italicised, and loop data values use a darker orange.

If you are new to the colour scheme, use **Help → Syntax Highlighting Guide...** in the application for a quick explanation of what each colour and text style means. The guide reflects the currently active colours, including any custom values you set in `settings.json`.

Advanced users can also customise syntax-highlighting colours manually in `settings.json` under `editor.syntax_highlighting_colors`, including `modern_only`.

### Data-Name Integrity Checks

To prevent conflicting aliases and duplicate data names from being written accidentally, CIVET now enforces data-name integrity in key workflows:

- **Save** blocks when unresolved duplicate/alias-value conflicts remain.
- Conversion and automated fix operations prompt to resolve conflicts when detected.
- Auto-resolution keeps a single recommended field by default; manual resolution can preserve aliases and synchronize values.

### Multi-Data-Block Support

CIF files containing more than one `data_` block (e.g. several crystals, or a variable-temperature
series) are checked block-by-block rather than treating the file as one document:

- **Block selection**: When **Start Checks** detects more than one data block, the check
  configuration dialog lists them with checkboxes (default: all selected).
- **Check mode — Shared (default) or Independent**: In *Shared* mode, a field whose value agrees
  across all selected blocks is confirmed once and the resolution applied everywhere; a field whose
  value differs between blocks (e.g. `_diffrn.ambient_temperature` in a variable-temperature study)
  opens a per-block table instead of silently applying one value to all of them. *Independent* mode
  runs the full check pass separately for each selected block.
- **Block-labelled dialogs**: Check prompts show which data block(s) they apply to in a bold banner.
- **Per-block validation actions**: The Data Name Validation dialog lists every block a field occurs
  in, and any action (delete, correct, add/replace a deprecated successor) can be applied to all
  blocks or scoped to just one.
- **Block-aware duplicate detection and compatibility fields**: duplicate/alias checks and the
  `add_legacy_compatibility_fields` action run per block, so the same data name repeated across
  blocks is not a false duplicate, and each block's compatibility fields use that block's own values.
- **File Status panel**: reports the data-block count first, with a **Show status for** selector to
  view syntax/notation/data-name/data-value status for the whole file or a single block; when
  viewing the whole file, a tooltip on the issue counts explains any gap between the combined total
  and the per-block figures (shared issues are counted once combined).

### Check Progress Indicator

**Start Checks** shows a "Check N/Total" counter and progress bar in the status bar for the
duration of the run, and repeats the same counter in a banner inside each field-check dialog.
`Total` is an estimate computed at the start of the run from the loaded `.cif_rules` set (and the
number of selected data blocks); it grows on the fly if a run turns out to need more steps than
predicted (e.g. an `IF` block whose condition is met, or a per-block fallback in Shared mode), so
the counter never shows something like "61/60" - it just adjusts upward. The counter still
advances through checks that resolve silently (auto-fill or skip-matching-defaults), so it never
stalls, and the indicator disappears once the run finishes, is stopped, or is aborted.

### Editing Convenience

- **Reload File**: Available from **Edit → Reload File** with `Ctrl+Shift+R`, this reloads the current file from disk and discards unsaved editor changes after confirmation.

## Building

### Executable 
```bash
pip install pyinstaller
pyinstaller CIVET.spec
```

Output: `dist/CIVET` (or `CIVET.exe` on Windows, `CIVET.app` on macOS)


## System Requirements
- **Executable**: Windows 10/11, macOS 10.14+ (not tested), Linux (not tested)
- **Source**: Python 3.11+, PyQt6, requests

## License
BSD Clause License - see [LICENSE](LICENSE)

## Citation
```
CIVET - CIF Validation and Editing Tool
GitHub: https://github.com/danielnrainer/CIVET
Zenodo: https://doi.org/10.5281/zenodo.17328490
```

