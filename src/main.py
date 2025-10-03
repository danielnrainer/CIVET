import sys
import os
from PyQt6.QtWidgets import QApplication
from gui.main_window import CIFEditor

def main():
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
        if hasattr(sys.stdout, 'reconfigure') and sys.stdout is not None:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure') and sys.stderr is not None:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, TypeError):
        # Fallback for environments where reconfigure is not available
        pass
    
    app = QApplication(sys.argv)
    
    # Set application-wide encoding attributes
    app.setProperty("encoding", "utf-8")
    
    editor = CIFEditor()
    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

