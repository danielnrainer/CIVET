import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import CIFEditor

def main():
    app = QApplication(sys.argv)
    editor = CIFEditor()
    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

