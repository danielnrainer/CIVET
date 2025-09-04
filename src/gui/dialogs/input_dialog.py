"""CIF Input Dialog for field editing."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class CIFInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes
    RESULT_USE_DEFAULT = 4  # User wants to use default value

    def __init__(self, title, text, value="", default_value=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.default_value = default_value
        
        layout = QVBoxLayout(self)
        
        # Add text label
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Add input field
        self.inputField = QLineEdit(self)
        self.inputField.setText(value)
        layout.addWidget(self.inputField)
        
        # Add buttons
        buttonBox = QHBoxLayout()
        
        okButton = QPushButton("OK")
        okButton.clicked.connect(self.accept)
        
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        # Add "Use Default" button only if default value is provided
        if default_value is not None and default_value.strip():
            useDefaultButton = QPushButton(f"Use Default ({default_value})")
            useDefaultButton.clicked.connect(self.use_default)
            buttonBox.addWidget(useDefaultButton)
        
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        
        layout.addLayout(buttonBox)
        self.setMinimumWidth(600)

    def getValue(self):
        return self.inputField.text()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)
    
    def use_default(self):
        self.done(self.RESULT_USE_DEFAULT)

    @staticmethod
    def getText(parent, title, text, value="", default_value=None):
        dialog = CIFInputDialog(title, text, value, default_value, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            return dialog.getValue(), QDialog.DialogCode.Accepted
        elif result == CIFInputDialog.RESULT_ABORT:
            return None, CIFInputDialog.RESULT_ABORT
        elif result == CIFInputDialog.RESULT_STOP_SAVE:
            return dialog.getValue(), CIFInputDialog.RESULT_STOP_SAVE
        elif result == CIFInputDialog.RESULT_USE_DEFAULT:
            return default_value, QDialog.DialogCode.Accepted
        else:
            return None, QDialog.DialogCode.Rejected
