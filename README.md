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
- **Syntax Highlighting**: Enhanced CIF syntax highlighting with loop support
- **File Reformatting**: Automatic line length handling while preserving structure
- **Multiple Field Sets**: Support for 3DED and High-Pressure crystallography
- **Use Default Values**: Quick application of suggested field values

