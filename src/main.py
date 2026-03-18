import sys
import os
from io import TextIOWrapper

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from gui.main_window import CIFEditor

MINIMUM_PYTHON = (3, 11)


def _configure_utf8_stream(stream):
    """Configure UTF-8 output for standard streams when supported."""
    if isinstance(stream, TextIOWrapper):
        stream.reconfigure(encoding='utf-8', errors='replace')


def main():
    if sys.version_info < MINIMUM_PYTHON:
        required_version = ".".join(str(part) for part in MINIMUM_PYTHON)
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise RuntimeError(
            f"CIVET requires Python {required_version}+; found Python {current_version}."
        )

    # Ensure UTF-8 encoding for the application
    if sys.platform.startswith('win'):
        # Windows-specific UTF-8 configuration
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        try:
            # Try to set console code page to UTF-8 (Windows 10 build 1903+)
            os.system('chcp 65001 > nul 2>&1')
        except:
            pass
    
    # Set UTF-8 as default encoding for text processing (with error handling for PyInstaller)
    try:
        _configure_utf8_stream(sys.stdout)
        _configure_utf8_stream(sys.stderr)
    except (AttributeError, TypeError):
        # Fallback for environments where reconfigure is not available
        pass
    
    app = QApplication(sys.argv)
    
    # Set application icon (for taskbar)
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "civet.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Set application-wide encoding attributes
    app.setProperty("encoding", "utf-8")
    
    editor = CIFEditor()
    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

