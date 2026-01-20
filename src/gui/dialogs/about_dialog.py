"""
About Dialog
============

Dialog showing application version, credits, and links to documentation.
"""

import sys
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices

# Import version information
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from version import (
    __version__, APP_NAME, APP_FULL_NAME, APP_DESCRIPTION, 
    APP_AUTHOR, APP_COPYRIGHT, GITHUB_URL, ZENODO_DOI, ZENODO_URL
)


class AboutDialog(QDialog):
    """
    About dialog displaying application information, version, and links.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(450, 380)
        self.setModal(True)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Application icon and name
        header_layout = QHBoxLayout()
        
        # Try to load the application icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "civet.ico")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(icon_label)
        header_layout.addSpacing(15)
        
        # Title and version
        title_layout = QVBoxLayout()
        
        name_label = QLabel(APP_NAME)
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        name_label.setFont(name_font)
        title_layout.addWidget(name_label)
        
        full_name_label = QLabel(APP_FULL_NAME)
        full_name_font = QFont()
        full_name_font.setPointSize(10)
        full_name_font.setItalic(True)
        full_name_label.setFont(full_name_font)
        full_name_label.setStyleSheet("color: #666;")
        title_layout.addWidget(full_name_label)
        
        version_label = QLabel(f"Version {__version__}")
        version_font = QFont()
        version_font.setPointSize(10)
        version_label.setFont(version_font)
        title_layout.addWidget(version_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Description
        desc_label = QLabel(APP_DESCRIPTION)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #444;")
        layout.addWidget(desc_label)
        
        # Author and copyright
        author_label = QLabel(f"<b>Author:</b> {APP_AUTHOR}")
        layout.addWidget(author_label)
        
        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(copyright_label)
        
        layout.addSpacing(10)
        
        # Links section
        links_layout = QVBoxLayout()
        links_layout.setSpacing(8)
        
        # GitHub link
        github_btn = QPushButton("🔗 View on GitHub")
        github_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(lambda: self.open_url(GITHUB_URL))
        links_layout.addWidget(github_btn)
        
        # Zenodo/DOI link
        zenodo_btn = QPushButton(f"📄 Cite this software (DOI: {ZENODO_DOI})")
        zenodo_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        zenodo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zenodo_btn.clicked.connect(lambda: self.open_url(ZENODO_URL))
        links_layout.addWidget(zenodo_btn)
        
        layout.addLayout(links_layout)
        
        layout.addStretch()
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(80)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def open_url(self, url: str):
        """Open a URL in the default browser."""
        QDesktopServices.openUrl(QUrl(url))
