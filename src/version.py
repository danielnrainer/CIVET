"""
CIVET Version Information
=========================

Central location for version information used throughout the application.
This file is also read by PyInstaller for embedding version info in executables.
"""

# Version components
VERSION_MAJOR = 1
VERSION_MINOR = 1

# Version string
__version__ = f"{VERSION_MAJOR}.{VERSION_MINOR}"
VERSION_STRING = __version__

# Application information
APP_NAME = "CIVET"
APP_FULL_NAME = "CIF Validation and Editing Tool"
APP_DESCRIPTION = "A modern desktop application for editing and validating Crystallographic Information Files (CIF)"
APP_AUTHOR = "Daniel N. Rainer"
APP_COPYRIGHT = "Copyright © 2025 Daniel N. Rainer"

# Repository and citation information
GITHUB_URL = "https://github.com/danielnrainer/CIVET"
ZENODO_DOI = "10.5281/zenodo.17328490"  # Update with actual DOI when available
ZENODO_URL = f"https://doi.org/{ZENODO_DOI}"

# For Windows version info (used by PyInstaller)
# Format: (major, minor)
VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR)
