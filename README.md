# CIF Checker

Simple CIF (crystallographic information file) viewer/editor, intended to be used mainly for 3D ED CIF files to check for missing/erroneous fields before publishing/depositing the CIF in a paper/database.

The CIF fields to check are declared in a config file 'field_definitions.cif_ed'. This is easily expandable to other use-cases such as high-pressure crystallography, using another config file 'field_definitions.cif_hp'.

## Quick Start

### Option 1: Standalone Executable (Recommended)
Download and run `CIF_checker.exe` - no Python installation required!

### Option 2: From Source
```bash
conda activate your_environment
pip install -r requirements.txt
python src/main.py
```

## Building Executable

To create a standalone executable:
```bash
build_exe.bat
```

See [BUILD.md](BUILD.md) for detailed build instructions.

## Features

- **CIF Field Validation**: Check for missing or incorrect fields
- **Flexible Field Definitions**: Choose from built-in sets (3DED, HP) or use custom field definition files
- **Syntax Highlighting**: Enhanced CIF syntax highlighting with loop support
- **File Reformatting**: Automatic line length handling while preserving structure
- **Custom Field Sets**: Load your own field definition files for specialized workflows
- **Use Default Values**: Quick application of suggested field values

## Using Custom Field Definition Files

You can create and use your own field definition files for specialized workflows:

1. **Select Custom File**: Choose the "Custom File" radio button in the field definition selection
2. **Browse for File**: Click "Select Custom File..." to choose your field definition file
3. **Start Checks**: Once loaded, use "Start Checks" to validate against your custom fields

### Field Definition File Format

Custom field definition files should follow this format:
```
# Field definitions for custom workflow
_field_name default_value # Optional description
_another_field 'default with spaces' # Description here

# You can also use the comment-only description format:
# _field_name: Detailed description of the field
_field_name default_value
```

Supported file extensions: `.cif_ed`, `.cif_hp`, `.cif_defs`

