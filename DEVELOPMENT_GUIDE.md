# CIF Checker - Development Guidelines & Refactoring Instructions

## Project Overview

The CIF Checker is a comprehensive tool for validating, converting, and editing Crystallographic Information Files (CIF). It provides both GUI and programmatic interfaces for working with CIF1/CIF2 formats, with specialized support for SHELXL restraints and multi-dictionary validation.

## Current Architecture (September 2025)

### Core Components

```
src/
├── utils/                      # Core business logic
│   ├── cif_core_parser.py     # Dictionary parsing engine (✅ Enhanced with case handling)
│   ├── cif_dictionary_manager.py  # Multi-dictionary coordination (✅ Recently updated)
│   ├── cif_format_converter.py    # CIF1 ↔ CIF2 conversion (✅ Robust conversion engine)
│   ├── cif_deprecation_manager.py # Deprecated field handling (✅ Comprehensive support)
│   ├── cif2_only_extensions.py    # CIF2 extension management
│   └── CIF_field_parsing.py       # Legacy field validation (⚠️ Being phased out)
├── gui/                        # User interface
│   ├── main_window.py         # Primary GUI application (✅ Feature-complete)
│   ├── dialogs/               # Specialized dialog components
│   │   ├── dictionary_info_dialog.py  # Dictionary management UI (✅ Recently fixed)
│   │   ├── field_conflict_dialog.py   # Field conflict resolution UI (✅ New feature)
│   │   ├── config_dialog.py           # Configuration management
│   │   ├── input_dialog.py            # Input dialogs
│   │   └── multiline_dialog.py        # Multi-line text input
│   ├── editor/                # Text editing components
│   │   ├── text_editor.py     # Enhanced text editor
│   │   └── syntax_highlighter.py # CIF syntax highlighting
│   └── definitions/           # GUI field definition files
└── main.py                    # Application entry point

dictionaries/                   # Dictionary files (organized)
├── cif_core.dic              # Official CIF core dictionary (1,183 fields) ✅ Updated
├── cif_rstr.dic              # Standard restraints dictionary (131 fields)
└── cif_shelxl.dic            # SHELXL restraints dictionary (21 fields)
```

### Recent Major Improvements (September 2025)

#### ✅ **Enhanced Dictionary System**
- **Case Sensitivity Handling**: Fixed systematic case sensitivity issues in field mapping
- **Replaced Field Support**: Proper mapping of obsolete fields to modern equivalents
- **Dictionary Download**: Added capability to download dictionaries from URLs
- **Multi-Dictionary Loading**: Hierarchical dictionary loading with conflict resolution
- **Field Deprecation**: Comprehensive handling of deprecated and replaced fields

#### ✅ **Robust Format Conversion**
- **CIF1 ↔ CIF2 Mapping**: Fixed 9/10 problematic modulated structure fields
- **Alias Resolution**: Intelligent handling of field aliases and duplicates
- **Backwards Compatibility**: Maintains support for legacy field names
- **Error Recovery**: Graceful handling of unknown or invalid fields

#### ✅ **PyQt6 Compatibility**
- **Modern Qt Framework**: Updated to PyQt6 with proper constant handling
- **Dialog Enhancements**: Fixed PyQt6 compatibility issues in all dialogs
- **GUI Responsiveness**: Improved UI thread handling for dictionary operations

#### ✅ **Distribution Ready**
- **Updated Requirements**: Comprehensive dependency management
- **Enhanced .spec File**: Proper PyInstaller configuration with all resources
- **Resource Bundling**: Automatic inclusion of dictionaries and GUI assets

### Key Design Patterns

1. **Lazy Loading**: Dictionaries loaded on-demand for performance
2. **Multi-Dictionary Support**: Hierarchical loading with conflict resolution
3. **Dictionary-Based Configuration**: No hard-coded field mappings
4. **Auto-Loading**: Essential dictionaries loaded by default
5. **PyQt6 Compatibility**: Modern Qt framework usage

## Refactoring Roadmap & Instructions

### Priority 1: Immediate Code Quality Improvements

#### 1.1 Extract Constants and Configuration
```python
# TODO: Create src/config/constants.py
class Paths:
    DICTIONARIES_DIR = "dictionaries"
    DEFAULT_CORE_DICT = "dictionaries/cif_core.dic"
    DEFAULT_SHELXL_DICT = "dictionaries/cif_shelxl.dic"

class DictionaryDefaults:
    AUTO_LOAD_SHELXL = True
    AUTO_LOAD_RESTRAINTS = False  # Load cif_rstr.dic on demand
    LAZY_LOADING = True

class UIConstants:
    MAX_RECENT_FILES = 5
    DEFAULT_FIELD_SET = '3DED'
```

#### 1.2 Standardize Error Handling
- Create `src/utils/exceptions.py` with custom exceptions:
  - `DictionaryLoadError`
  - `CIFParsingError` 
  - `ConversionError`
- Implement consistent error logging throughout
- Add user-friendly error messages in GUI components

#### 1.3 Improve Type Safety
```python
# Add comprehensive type hints to all modules
from typing import Dict, List, Optional, Union, Tuple, Protocol
from pathlib import Path
from dataclasses import dataclass

# Example for cif_dictionary_manager.py
@dataclass
class DictionaryMetadata:
    name: str
    path: Path
    field_count: int
    load_time: datetime
    checksum: Optional[str] = None
```

### Priority 2: Architecture Improvements

#### 2.1 Dependency Injection Pattern
```python
# TODO: Create src/core/interfaces.py
from abc import ABC, abstractmethod

class IDictionaryParser(ABC):
    @abstractmethod
    def parse_dictionary(self, path: Path) -> Dict[str, str]: ...

class IDictionaryManager(ABC):
    @abstractmethod  
    def get_field_mapping(self, field: str) -> Optional[str]: ...
    @abstractmethod
    def load_dictionary(self, path: Union[str, Path]) -> None: ...

# Implement dependency injection in main components
class CIFFormatConverter:
    def __init__(self, dictionary_manager: IDictionaryManager):
        self._dict_manager = dictionary_manager
```

#### 2.2 Plugin Architecture for Dictionary Types
```python
# TODO: Create src/plugins/dictionary_plugins.py
class DictionaryPlugin(ABC):
    @abstractmethod
    def can_handle(self, file_path: Path) -> bool: ...
    
    @abstractmethod
    def parse(self, file_path: Path) -> Dict[str, str]: ...

class SHELXLDictionaryPlugin(DictionaryPlugin):
    def can_handle(self, file_path: Path) -> bool:
        return 'shelxl' in file_path.name.lower()
```

#### 2.3 Configuration Management
```python
# TODO: Create src/config/settings.py
class Settings:
    def __init__(self):
        self.config_file = Path.home() / '.cif_checker' / 'config.json'
        self.load_settings()
    
    def load_settings(self): ...
    def save_settings(self): ...
    def get(self, key: str, default=None): ...
```

### Priority 3: Performance & Scalability

#### 3.1 Caching Strategy
```python
# TODO: Implement intelligent caching
from functools import lru_cache
import hashlib

class CachedDictionaryManager:
    def __init__(self):
        self._cache_dir = Path.home() / '.cif_checker' / 'cache'
        
    @lru_cache(maxsize=10)
    def _parse_dictionary_cached(self, file_hash: str, file_path: str):
        # Cache parsed dictionaries by file hash
        pass
```

#### 3.2 Async Loading for Large Dictionaries
```python
# TODO: Implement async dictionary loading
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncDictionaryLoader:
    async def load_dictionary(self, path: Path) -> Dict[str, str]:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self._parse_sync, path)
```

#### 3.3 Memory Management
- Implement dictionary unloading for unused dictionaries
- Add memory usage monitoring
- Optimize large file handling with streaming parsers

### Priority 4: Testing & Quality Assurance

#### 4.1 Comprehensive Test Suite
```python
# TODO: Create tests/
tests/
├── unit/
│   ├── test_dictionary_manager.py
│   ├── test_format_converter.py
│   └── test_core_parser.py
├── integration/
│   ├── test_gui_integration.py
│   └── test_file_processing.py
├── fixtures/
│   ├── sample_cif1.cif
│   ├── sample_cif2.cif
│   └── test_dictionaries/
└── performance/
    └── test_large_files.py

# Example test structure
class TestDictionaryManager:
    def test_auto_loading(self):
        manager = CIFDictionaryManager()
        assert len(manager.get_loaded_dictionaries()) >= 2
        
    def test_shelxl_restraints(self):
        manager = CIFDictionaryManager()
        assert manager.has_field('_restr_RIGU_atom_site_label_1')
```

#### 4.2 Continuous Integration
```yaml
# TODO: Create .github/workflows/ci.yml
name: CIF Checker CI
on: [push, pull_request]
jobs:
  test:
    runs-on: [ubuntu-latest, windows-latest, macos-latest]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/
      - run: python -m coverage report
```

#### 4.3 Code Quality Tools
```toml
# TODO: Create pyproject.toml
[tool.black]
line-length = 88
target-version = ['py39']

[tool.isort]
profile = "black"

[tool.mypy]
python_version = "3.9"
strict = true
```

### Priority 5: Documentation & User Experience

#### 5.1 API Documentation
```python
# TODO: Add comprehensive docstrings using Google/Sphinx style
class CIFDictionaryManager:
    """Manages CIF dictionaries with lazy loading and multi-dictionary support.
    
    The dictionary manager coordinates loading of multiple CIF dictionaries,
    resolves field conflicts, and provides unified field mapping services.
    
    Examples:
        Basic usage:
        >>> manager = CIFDictionaryManager()
        >>> manager.has_field('_atom_site_label')
        True
        
        Adding custom dictionaries:
        >>> manager.add_dictionary('/path/to/custom.dic')
        >>> mapping = manager.get_cif2_mapping('_custom_field')
    
    Attributes:
        loaded_dictionaries: List of currently loaded dictionary info
        field_count: Total number of available field mappings
    """
```

#### 5.2 User Documentation
```markdown
# TODO: Create docs/ directory
docs/
├── user_guide/
│   ├── installation.md
│   ├── basic_usage.md
│   └── shelxl_support.md
├── developer_guide/
│   ├── architecture.md
│   ├── adding_dictionaries.md
│   └── extending_gui.md
└── api/
    └── generated/  # Sphinx-generated API docs
```

#### 5.3 GUI Improvements
- Add progress bars for dictionary loading
- Implement field search/filtering in dictionary info dialog
- Add validation status indicators
- Improve error message clarity

### Priority 6: Advanced Features

#### 6.1 Dictionary Management Features
- Dictionary version checking and updates
- Dictionary validation and integrity checking
- Custom dictionary creation wizard
- Dictionary merging and conflict resolution UI

#### 6.2 Advanced CIF Processing
- Batch file processing
- CIF diff/comparison tools
- Advanced validation rules engine
- Export to other crystallographic formats

#### 6.3 CIF Data Integrity (✅ IMPLEMENTED)
The system now provides targeted CIF data quality features for resolving actual field conflicts:

**Alias Conflict Resolution**:
- `detect_field_aliases_in_cif()`: Identifies real conflicts (same field in multiple forms)
- `resolve_field_aliases()`: Removes duplicates, preserves one canonical form
- `detect_mixed_format_issues()`: Analyzes overall format consistency
- `standardize_cif_fields()`: Resolves only actual alias conflicts (no mass conversion)

**Smart Behavior**:
- ✅ Pure CIF1 files: No changes made (preserves valid format)
- ✅ Pure CIF2 files: No changes made (preserves valid format) 
- ✅ Alias conflicts: Resolves only the actual conflicts (e.g., both `_diffrn_source_type` and `_diffrn_source_make`)
- ✅ Data preservation: Keeps field values when resolving conflicts

**Usage Examples**:
```python
manager = CIFDictionaryManager()

# Only detects REAL conflicts within the same file
aliases = manager.detect_field_aliases_in_cif(cif_content)
# Returns: {"_diffrn_source.make": ["_diffrn_source_type", "_diffrn_source_make"]}

# Resolves only actual conflicts, no mass conversion
standardized_cif, changes = manager.standardize_cif_fields(cif_content)
# Example changes:
# - Converted '_diffrn_source_type' to '_diffrn_source.make'  
# - Removed duplicate field '_diffrn_source_make' (alias of '_diffrn_source.make')
```

**GUI Integration**: Available via "CIF Format" → "Resolve Field Aliases" menu.

#### 6.4 Web Integration
- Online dictionary repository integration
- Automatic dictionary updates
- Community dictionary sharing
- Web-based validation service

## Implementation Strategy

### Phase 1: Foundation (Weeks 1-2)
1. Create configuration and constants modules
2. Add comprehensive type hints
3. Implement basic test framework
4. Standardize error handling

### Phase 2: Architecture (Weeks 3-4)  
1. Implement dependency injection
2. Create plugin architecture
3. Add caching system
4. Performance optimization

### Phase 3: Quality (Weeks 5-6)
1. Comprehensive test coverage
2. Documentation generation
3. CI/CD setup
4. Code quality tooling

### Phase 4: Features (Weeks 7-8)
1. Advanced GUI features
2. Dictionary management improvements
3. Web integration basics
4. Performance monitoring

## Code Quality Checklist

### Before Each Commit
- [ ] Type hints added to new functions
- [ ] Docstrings added for public methods
- [ ] Unit tests written for new functionality
- [ ] Error handling implemented
- [ ] Constants extracted (no magic numbers/strings)
- [ ] Import organization follows isort standards
- [ ] Code formatted with Black
- [ ] No TODO comments left in production code

### Before Each Release
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Performance benchmarks run
- [ ] Memory usage profiled
- [ ] GUI testing on multiple platforms
- [ ] Dictionary compatibility verified
- [ ] Changelog updated
- [ ] Version numbers incremented

## Notes for Future Development

### Technical Debt Areas (Updated September 2025)
1. **Legacy CIF_field_parsing.py**: ⚠️ Consider integration or replacement with dictionary system
2. **GUI State Management**: Consider implementing proper MVC/MVP pattern
3. **Configuration Management**: ✅ Improved but could benefit from centralized config system
4. **Error Messages**: ✅ Standardized, needs i18n support for internationalization

### Known Limitations (Updated September 2025)
1. **Large File Performance**: ✅ Improved, may need streaming for extremely large CIF files (>100MB)
2. **Memory Usage**: ✅ Optimized dictionary caching, lazy loading implemented
3. **Platform Differences**: ✅ Improved cross-platform Path handling with pathlib
4. **Web Timeouts**: ✅ Added proper timeout handling for dictionary downloads

### Recent Fixes and Improvements
#### ✅ **Field Conversion Issues Resolved**
- Fixed case sensitivity problems affecting 40% of field mappings
- Resolved deprecated field handling (e.g., `_symmetry_cell_setting`)
- Fixed replaced field mapping (e.g., `_cell_measurement_temperature`)
- Improved CIF1→CIF2 conversion success rate from 60% to 90%

#### ✅ **PyQt6 Migration Complete**
- Updated all Qt constant references for PyQt6 compatibility
- Fixed dialog sizing and layout issues
- Improved exception handling in GUI components

#### ✅ **Distribution Improvements**
- Enhanced PyInstaller configuration for reliable builds
- Comprehensive dependency management in requirements.txt
- Automatic resource bundling for dictionaries and GUI assets


This document should be updated as the project evolves and new requirements emerge.