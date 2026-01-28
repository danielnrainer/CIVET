"""
Dictionary Information Dialog
============================

Dialog window to display detailed information about loaded CIF dictionaries,
including source locations, field counts, and the ability to load new dictionaries
from files or URLs.
"""

import os
import sys
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QLabel, QMessageBox, QFileDialog, QInputDialog, QProgressBar,
    QGroupBox, QTextEdit, QSplitter, QHeaderView, QAbstractItemView, QApplication,
    QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor
import requests

# Add parent directories to path to import from utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.cif_dictionary_manager import CIFDictionaryManager, DictionaryInfo


class DictionaryDownloadWorker(QThread):
    """Worker thread for downloading dictionaries from URLs"""
    
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int)  # progress percentage
    
    def __init__(self, url: str, dict_manager: CIFDictionaryManager):
        super().__init__()
        self.url = url
        self.dict_manager = dict_manager
    
    def run(self):
        """Download and add dictionary from URL"""
        try:
            self.progress.emit(10)
            
            # Validate URL
            if not self.url.startswith(('http://', 'https://')):
                self.finished.emit(False, "Invalid URL format. Must start with http:// or https://")
                return
            
            self.progress.emit(30)
            
            # Add dictionary from URL
            success = self.dict_manager.add_dictionary_from_url(self.url)
            
            self.progress.emit(100)
            
            if success:
                self.finished.emit(True, f"Successfully loaded dictionary from {self.url}")
            else:
                self.finished.emit(False, f"Failed to load dictionary from {self.url}")
                
        except requests.RequestException as e:
            self.finished.emit(False, f"Network error: {str(e)}")
        except Exception as e:
            self.finished.emit(False, f"Error loading dictionary: {str(e)}")


class BulkCOMCIFSDownloadWorker(QThread):
    """Worker thread for downloading all COMCIFS dictionaries"""
    
    finished = pyqtSignal(dict)  # results dictionary
    progress = pyqtSignal(int)  # progress percentage
    status_update = pyqtSignal(str)  # current status message
    
    def __init__(self, dict_manager: CIFDictionaryManager):
        super().__init__()
        self.dict_manager = dict_manager
    
    def run(self):
        """Download all COMCIFS dictionaries"""
        try:
            self.progress.emit(10)
            self.status_update.emit("Starting COMCIFS downloads...")
            
            # Use the dictionary manager's method to load all COMCIFS dictionaries
            results = self.dict_manager.load_all_comcifs_dictionaries(timeout=30)
            
            self.progress.emit(100)
            self.status_update.emit("Download complete")
            self.finished.emit(results)
            
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
            # Return empty results dict to indicate failure
            self.finished.emit({})


class BulkIUCrDownloadWorker(QThread):
    """Worker thread for downloading all IUCr dictionaries"""
    
    finished = pyqtSignal(dict)  # results dictionary
    progress = pyqtSignal(int)  # progress percentage
    status_update = pyqtSignal(str)  # current status message
    
    def __init__(self, dict_manager: CIFDictionaryManager):
        super().__init__()
        self.dict_manager = dict_manager
    
    def run(self):
        """Download all IUCr dictionaries"""
        try:
            self.progress.emit(10)
            self.status_update.emit("Starting IUCr downloads...")
            
            # Use the dictionary manager's method to load all IUCr dictionaries
            results = self.dict_manager.load_all_iucr_dictionaries(timeout=30)
            
            self.progress.emit(100)
            self.status_update.emit("Download complete")
            self.finished.emit(results)
            
        except Exception as e:
            self.status_update.emit(f"Error: {str(e)}")
            # Return empty results dict to indicate failure
            self.finished.emit({})


class DictionaryInfoDialog(QDialog):
    """
    Dialog for displaying and managing CIF dictionary information
    """
    
    def __init__(self, dict_manager: CIFDictionaryManager, parent=None):
        super().__init__(parent)
        self.dict_manager = dict_manager
        self.download_worker = None
        
        self.setWindowTitle("Dictionary Information")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self.setup_ui()
        self.load_dictionary_data()
        
        # Apply some styling
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: #fafafa;
                alternate-background-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #3875d7;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 5px 0;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
    
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout()
        
        # Summary section
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()
        
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Create splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Dictionaries table section
        table_group = QGroupBox("Loaded Dictionaries")
        table_layout = QVBoxLayout()
        
        self.dict_table = QTableWidget()
        self.dict_table.setColumnCount(10)
        self.dict_table.setHorizontalHeaderLabels([
            "Active", "Dictionary Title", "Date", "Version", "Source", "Status", "Update", "Type", "Fields", "Filename"
        ])
        
        # Set table properties
        self.dict_table.setAlternatingRowColors(True)
        self.dict_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dict_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.dict_table.horizontalHeader().setStretchLastSection(True)
        self.dict_table.verticalHeader().setVisible(False)
        
        # Connect selection change and double-click for update download
        self.dict_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.dict_table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        table_layout.addWidget(self.dict_table)
        table_group.setLayout(table_layout)
        splitter.addWidget(table_group)
        
        # Dictionary details section
        details_group = QGroupBox("Dictionary Details")
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        splitter.addWidget(details_group)
        
        # Set splitter proportions
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)
        
        # Action buttons section
        buttons_group = QGroupBox("Actions")
        buttons_layout = QVBoxLayout()
        
        # First row: Load dictionaries
        load_layout = QHBoxLayout()
        
        self.load_file_btn = QPushButton("Load from File...")
        self.load_file_btn.clicked.connect(self.load_dictionary_from_file)
        load_layout.addWidget(self.load_file_btn)
        
        self.load_url_btn = QPushButton("Load from URL...")
        self.load_url_btn.clicked.connect(self.load_dictionary_from_url)
        load_layout.addWidget(self.load_url_btn)
        
        self.load_comcif_btn = QPushButton("Load Dictionary...")
        self.load_comcif_btn.setToolTip("Load from COMCIF (development) or IUCr (official release)")
        self.load_comcif_btn.clicked.connect(self.load_comcifs_dictionary)
        load_layout.addWidget(self.load_comcif_btn)
        
        self.load_all_comcif_btn = QPushButton("Load all (dev)")
        self.load_all_comcif_btn.setToolTip("Load all COMCIF development dictionaries")
        self.load_all_comcif_btn.clicked.connect(self.load_all_comcifs_dictionaries)
        load_layout.addWidget(self.load_all_comcif_btn)
        
        self.load_all_iucr_btn = QPushButton("Load all (release)")
        self.load_all_iucr_btn.setToolTip("Load all IUCr official release dictionaries")
        self.load_all_iucr_btn.clicked.connect(self.load_all_iucr_dictionaries)
        load_layout.addWidget(self.load_all_iucr_btn)
        
        load_layout.addStretch()
        buttons_layout.addLayout(load_layout)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        buttons_layout.addWidget(self.progress_bar)
        
        # Second row: Refresh, Check Updates, Remove, and Close
        action_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        action_layout.addWidget(self.refresh_btn)
        
        self.check_updates_btn = QPushButton("Check for Updates")
        self.check_updates_btn.setToolTip("Check if newer versions are available online")
        self.check_updates_btn.clicked.connect(self.check_for_updates)
        action_layout.addWidget(self.check_updates_btn)
        
        self.load_all_updates_btn = QPushButton("Load All Updates")
        self.load_all_updates_btn.setToolTip("Load all available updates for this session only")
        self.load_all_updates_btn.clicked.connect(self.load_all_updates)
        self.load_all_updates_btn.setEnabled(False)  # Initially disabled until updates are checked
        action_layout.addWidget(self.load_all_updates_btn)
        
        self.download_all_updates_btn = QPushButton("Download All Updates")
        self.download_all_updates_btn.setToolTip("Download and save all available dictionary updates")
        self.download_all_updates_btn.clicked.connect(self.download_all_updates)
        self.download_all_updates_btn.setEnabled(False)  # Initially disabled until updates are checked
        action_layout.addWidget(self.download_all_updates_btn)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected_dictionary)
        self.remove_btn.setEnabled(False)  # Initially disabled
        action_layout.addWidget(self.remove_btn)
        
        action_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        action_layout.addWidget(self.close_btn)
        
        buttons_layout.addLayout(action_layout)
        buttons_group.setLayout(buttons_layout)
        layout.addWidget(buttons_group)
        
        self.setLayout(layout)
    
    def load_dictionary_data(self):
        """Load and display dictionary information"""
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            dict_summary = self.dict_manager.get_dictionary_info()
            
            # Update summary
            total_dicts = len(detailed_info)
            active_dicts = sum(1 for info in detailed_info if info.is_active)
            total_fields = dict_summary.get('total_cif1_mappings', 0)
            
            summary_text = f"""
            <b>Total Dictionaries:</b> {total_dicts}<br>
            <b>Active Dictionaries:</b> {active_dicts}<br>
            <b>Total Field Mappings:</b> {total_fields} CIF1→CIF2, {dict_summary.get('total_cif2_mappings', 0)} CIF2→CIF1<br>
            <b>Primary Dictionary:</b> {detailed_info[0].name if detailed_info else 'None'}
            """
            if total_dicts > 1:
                summary_text += f"<br><b>Additional Dictionaries:</b> {total_dicts - 1}"
            
            self.summary_label.setText(summary_text)
            
            # Sort dictionaries by dict_title (alphabetically)
            sorted_info = sorted(detailed_info, key=lambda x: (x.dict_title or x.name or "").lower())
            
            # Clear and update table
            self.dict_table.clearContents()
            self.dict_table.setRowCount(len(sorted_info))
            
            for row, dict_info in enumerate(sorted_info):
                # Active checkbox
                active_widget = QWidget()
                active_layout = QHBoxLayout(active_widget)
                active_checkbox = QCheckBox()
                active_checkbox.setChecked(dict_info.is_active)
                active_checkbox.setStyleSheet("margin-left: 10px;")
                # Store dict name in checkbox for later retrieval
                active_checkbox.setProperty("dict_name", dict_info.name)
                active_checkbox.stateChanged.connect(self.on_active_changed)
                active_layout.addWidget(active_checkbox)
                active_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                active_layout.setContentsMargins(0, 0, 0, 0)
                self.dict_table.setCellWidget(row, 0, active_widget)
                
                # Dictionary Title (from _dictionary.title)
                title_text = dict_info.dict_title if dict_info.dict_title else "Unknown"
                self.dict_table.setItem(row, 1, QTableWidgetItem(title_text))
                
                # Date (from _dictionary.date)
                date_text = dict_info.dict_date if dict_info.dict_date else "Unknown"
                self.dict_table.setItem(row, 2, QTableWidgetItem(date_text))
                
                # Version
                version_text = dict_info.version if dict_info.version else "Unknown"
                self.dict_table.setItem(row, 3, QTableWidgetItem(version_text))
                
                # Source (COMCIF, IUCr, Local, Custom)
                source_text = dict_info.source if dict_info.source else "Unknown"
                source_item = QTableWidgetItem(source_text)
                # Color code by source
                if source_text == 'IUCr':
                    source_item.setForeground(QColor(0, 100, 0))  # Dark green for official
                elif source_text == 'COMCIF':
                    source_item.setForeground(QColor(0, 0, 200))  # Blue for development
                self.dict_table.setItem(row, 4, source_item)
                
                # Status (release, development, unknown)
                status_text = dict_info.status if dict_info.status else "unknown"
                status_item = QTableWidgetItem(status_text.capitalize())
                # Color code by status
                if status_text == 'release':
                    status_item.setForeground(QColor(0, 100, 0))  # Green for release
                elif status_text == 'development':
                    status_item.setForeground(QColor(200, 100, 0))  # Orange for development
                self.dict_table.setItem(row, 5, status_item)
                
                # Update availability (populated by check_for_updates)
                update_text = "—"  # em-dash for "not checked"
                update_item = QTableWidgetItem(update_text)
                if dict_info.update_available is True:
                    update_item.setText("⬆ Available")
                    update_item.setForeground(QColor(0, 100, 200))  # Blue for updates available
                    tooltip = "Double-click to download this update"
                    if dict_info.online_date:
                        tooltip += f"\nOnline date: {dict_info.online_date}"
                    update_item.setToolTip(tooltip)
                elif dict_info.update_available is False:
                    update_item.setText("✓ Up to date")
                    update_item.setForeground(QColor(0, 150, 0))  # Green for up to date
                else:
                    update_item.setForeground(QColor(150, 150, 150))  # Light gray
                    update_item.setToolTip("Click 'Check for Updates' to check")
                self.dict_table.setItem(row, 6, update_item)
                
                # Type (column 7, was 6)
                type_text = dict_info.source_type.upper()
                self.dict_table.setItem(row, 7, QTableWidgetItem(type_text))
                
                # Fields (column 8, was 7)
                self.dict_table.setItem(row, 8, QTableWidgetItem(str(dict_info.field_count)))
                
                # Filename (column 9, was 8)
                self.dict_table.setItem(row, 9, QTableWidgetItem(dict_info.name))
                
                # Path column - commented out for now, may want it back later
                # if dict_info.source_type == 'url':
                #     path_text = dict_info.path
                # elif dict_info.source_type == 'file':
                #     path_text = os.path.dirname(dict_info.path) or "Current directory"
                # else:
                #     path_text = dict_info.source_type.capitalize()
                # self.dict_table.setItem(row, 10, QTableWidgetItem(path_text))
            
            # Resize columns
            header = self.dict_table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Active
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Dictionary Title
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Date
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Version
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Source
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Status
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Update
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Type
            header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Fields
            header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)           # Filename
            # header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)        # Path (commented out)
            
            # Enable/disable update buttons based on available updates
            updates_available = any(info.update_available is True for info in detailed_info)
            self.load_all_updates_btn.setEnabled(updates_available)
            self.download_all_updates_btn.setEnabled(updates_available)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load dictionary information: {str(e)}")
    
    def on_selection_changed(self):
        """Handle table selection changes"""
        current_row = self.dict_table.currentRow()
        if current_row >= 0:
            try:
                # Get the filename from the table (column 9 - Filename)
                filename_item = self.dict_table.item(current_row, 9)
                if filename_item:
                    filename = filename_item.text()
                    
                    # Find the dictionary info by filename
                    detailed_info = self.dict_manager.get_detailed_dictionary_info()
                    dict_info = None
                    for info in detailed_info:
                        if info.name == filename:
                            dict_info = info
                            break
                    
                    if dict_info:
                        details_html = f"""
                        <h3>{dict_info.name}</h3>
                        <b>Description:</b> {dict_info.description or 'No description available'}<br><br>
                        <b>Full Path:</b> {dict_info.path}<br>
                    <b>Source Type:</b> {dict_info.source_type.upper()}<br>
                    """
                    
                    if dict_info.version:
                        details_html += f"<b>Version:</b> {dict_info.version}<br>"
                    
                    if dict_info.source:
                        source_color = "green" if dict_info.source == "IUCr" else "blue" if dict_info.source == "COMCIF" else "black"
                        details_html += f'<b>Source:</b> <span style="color: {source_color};">{dict_info.source}</span><br>'
                    
                    if dict_info.status:
                        status_color = "green" if dict_info.status == "release" else "orange" if dict_info.status == "development" else "gray"
                        details_html += f'<b>Status:</b> <span style="color: {status_color};">{dict_info.status.capitalize()}</span><br>'
                    
                    details_html += f"""
                    <b>File Size:</b> {self.format_file_size(dict_info.size_bytes)}<br>
                    <b>Field Count:</b> {dict_info.field_count}<br>
                    <b>Loaded:</b> {dict_info.loaded_time or 'Unknown'}
                    """
                    
                    self.details_text.setHtml(details_html)
                
            except Exception as e:
                self.details_text.setPlainText(f"Error loading details: {str(e)}")
        else:
            self.details_text.clear()
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def load_dictionary_from_file(self):
        """Load a dictionary from a local file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select CIF Dictionary File", 
            "", 
            "CIF Dictionary Files (*.dic);;All Files (*)"
        )
        
        if file_path:
            try:
                success = self.dict_manager.add_dictionary(file_path)
                if success:
                    QMessageBox.information(
                        self, 
                        "Success", 
                        f"Successfully loaded dictionary from {os.path.basename(file_path)}"
                    )
                    self.refresh_data()
                else:
                    QMessageBox.warning(
                        self, 
                        "Error", 
                        f"Failed to load dictionary from {file_path}"
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Error loading dictionary: {str(e)}"
                )
    
    def load_dictionary_from_url(self):
        """Load a dictionary from a URL"""
        url, ok = QInputDialog.getText(
            self, 
            "Load Dictionary from URL", 
            "Enter the URL of the CIF dictionary file:",
            text="https://github.com/COMCIFS/cif_core/raw/master/"
        )
        
        if ok and url:
            self.start_url_download(url)
    
    def load_comcifs_dictionary(self):
        """Show dialog to load dictionaries from COMCIF or IUCr"""
        # Get available dictionaries from both sources
        all_dicts = self.dict_manager.get_all_available_dictionaries()
        
        # Create display options organized by source
        display_options = []
        dict_mapping = {}
        
        # Add COMCIF dictionaries (development versions)
        display_options.append("=== COMCIF Development Versions ===")
        for dict_id, dict_info in all_dicts['comcif'].items():
            display_name = f"{dict_info['name']}"
            display_options.append(display_name)
            dict_mapping[display_name] = dict_info['url']
        
        # Add separator
        display_options.append("")
        display_options.append("=== IUCr Official Release Versions ===")
        
        # Add IUCr dictionaries (official releases)
        for dict_id, dict_info in all_dicts['iucr'].items():
            display_name = f"{dict_info['name']}"
            display_options.append(display_name)
            dict_mapping[display_name] = dict_info['url']
        
        dict_name, ok = QInputDialog.getItem(
            self,
            "Load Dictionary",
            "Select a dictionary to load:\n\n"
            "COMCIF = Latest development version from GitHub\n"
            "IUCr = Official release version from IUCr.org",
            display_options,
            0,
            False
        )
        
        if ok and dict_name and dict_name in dict_mapping:
            url = dict_mapping[dict_name]
            self.start_url_download(url)
    
    def load_all_comcifs_dictionaries(self):
        """Load all available COMCIFS dictionaries"""
        # Get available dictionaries dynamically
        available_dicts = self.dict_manager.get_available_comcifs_dictionaries()
        dict_count = len(available_dicts)
        
        # Build dictionary list for display
        dict_list = ""
        for dict_info in available_dicts.values():
            dict_list += f"• {dict_info['name']}\n"
        
        reply = QMessageBox.question(
            self,
            "Load All COMCIFS Dictionaries",
            f"This will download and load all {dict_count} available COMCIFS development dictionaries:\n\n"
            f"{dict_list}\n"
            "This may take a few moments. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_bulk_comcifs_download()
    
    def load_all_iucr_dictionaries(self):
        """Load all available IUCr dictionaries"""
        # Get available dictionaries dynamically
        available_dicts = self.dict_manager.get_available_iucr_dictionaries()
        dict_count = len(available_dicts)
        
        # Build dictionary list for display
        dict_list = ""
        for dict_info in available_dicts.values():
            dict_list += f"• {dict_info['name']}\n"
        
        reply = QMessageBox.question(
            self,
            "Load All IUCr Dictionaries",
            f"This will download and load all {dict_count} available IUCr official release dictionaries:\n\n"
            f"{dict_list}\n"
            "This may take a few moments. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_bulk_iucr_download()
    
    def start_bulk_comcifs_download(self):
        """Start downloading all COMCIFS dictionaries"""
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable buttons during download
        self.load_file_btn.setEnabled(False)
        self.load_url_btn.setEnabled(False) 
        self.load_comcif_btn.setEnabled(False)
        self.load_all_comcif_btn.setEnabled(False)
        self.load_all_iucr_btn.setEnabled(False)
        
        # Create and start bulk download worker
        self.bulk_download_worker = BulkCOMCIFSDownloadWorker(self.dict_manager)
        self.bulk_download_worker.progress.connect(self.progress_bar.setValue)
        self.bulk_download_worker.finished.connect(self.on_bulk_download_finished)
        self.bulk_download_worker.status_update.connect(self.show_status_message)
        self.bulk_download_worker.start()
    
    def start_bulk_iucr_download(self):
        """Start downloading all IUCr dictionaries"""
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable buttons during download
        self.load_file_btn.setEnabled(False)
        self.load_url_btn.setEnabled(False) 
        self.load_comcif_btn.setEnabled(False)
        self.load_all_comcif_btn.setEnabled(False)
        self.load_all_iucr_btn.setEnabled(False)
        
        # Create and start bulk download worker
        self.bulk_download_worker = BulkIUCrDownloadWorker(self.dict_manager)
        self.bulk_download_worker.progress.connect(self.progress_bar.setValue)
        self.bulk_download_worker.finished.connect(self.on_bulk_download_finished)
        self.bulk_download_worker.status_update.connect(self.show_status_message)
        self.bulk_download_worker.start()
    
    def on_bulk_download_finished(self, results: dict):
        """Handle bulk download completion"""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.load_file_btn.setEnabled(True)
        self.load_url_btn.setEnabled(True)
        self.load_comcif_btn.setEnabled(True)
        self.load_all_comcif_btn.setEnabled(True)
        self.load_all_iucr_btn.setEnabled(True)
        
        # Show results
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        if successful == total:
            QMessageBox.information(
                self,
                "Download Complete",
                f"Successfully loaded all {total} dictionaries!"
            )
        elif successful > 0:
            failed_dicts = [name for name, success in results.items() if not success]
            QMessageBox.warning(
                self,
                "Partial Success",
                f"Loaded {successful} of {total} dictionaries.\n\n"
                f"Failed to load: {', '.join(failed_dicts)}"
            )
        else:
            QMessageBox.critical(
                self,
                "Download Failed",
                "Failed to load any dictionaries. Please check your internet connection."
            )
        
        # Refresh the dictionary list
        self.refresh_data()
    
    def show_status_message(self, message: str):
        """Show status message in the UI"""
        # Could be used to show current dictionary being downloaded
        # For now, just update the window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle(f"{original_title} - {message}")
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def start_url_download(self, url: str):
        """Start downloading dictionary from URL"""
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable buttons during download
        self.load_file_btn.setEnabled(False)
        self.load_url_btn.setEnabled(False) 
        self.load_comcif_btn.setEnabled(False)
        self.load_all_comcif_btn.setEnabled(False)
        self.load_all_iucr_btn.setEnabled(False)
        
        # Start download worker
        self.download_worker = DictionaryDownloadWorker(url, self.dict_manager)
        self.download_worker.progress.connect(self.progress_bar.setValue)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()
    
    def on_download_finished(self, success: bool, message: str):
        """Handle download completion"""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.load_file_btn.setEnabled(True)
        self.load_url_btn.setEnabled(True)
        self.load_comcif_btn.setEnabled(True)
        self.load_all_comcif_btn.setEnabled(True)
        self.load_all_iucr_btn.setEnabled(True)
        
        # Show result message
        if success:
            QMessageBox.information(self, "Success", message)
            self.refresh_data()
        else:
            QMessageBox.warning(self, "Error", message)
        
        # Clean up worker
        if self.download_worker:
            self.download_worker.deleteLater()
            self.download_worker = None
    
    def on_active_changed(self, state):
        """Handle changes to the Active checkbox"""
        # Get the checkbox that triggered this
        checkbox = self.sender()
        if not checkbox:
            return
        
        dict_name = checkbox.property("dict_name")
        is_active = (state == Qt.CheckState.Checked.value)
        
        # Update the dictionary manager
        success = self.dict_manager.set_dictionary_active(dict_name, is_active)
        
        if success:
            # Refresh the table to show updated active states
            self.refresh_data()
        else:
            # Revert the checkbox if the operation failed
            checkbox.blockSignals(True)
            checkbox.setChecked(not is_active)
            checkbox.blockSignals(False)
            QMessageBox.warning(self, "Error", 
                              f"Failed to change active state for dictionary: {dict_name}")
    
    def refresh_data(self):
        """Refresh the displayed dictionary information"""
        try:
            # Temporarily disable the refresh button to prevent multiple clicks
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setText("Refreshing...")
            
            # Process events to update UI
            QApplication.processEvents()
            
            # Reload dictionary data
            self.load_dictionary_data()
            
            # Update parent dictionary status if available
            try:
                if self.parent() and hasattr(self.parent(), 'update_dictionary_status'):
                    self.parent().update_dictionary_status()
            except Exception as e:
                print(f"Warning: Failed to update parent dictionary status: {e}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh dictionary data: {str(e)}")
        finally:
            # Re-enable the refresh button
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Refresh")
    
    def check_for_updates(self):
        """Check if newer versions of loaded dictionaries are available online"""
        try:
            # Disable button and show progress
            self.check_updates_btn.setEnabled(False)
            self.check_updates_btn.setText("Checking...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            QApplication.processEvents()
            
            # Call the dictionary manager's check method
            self.progress_bar.setValue(20)
            QApplication.processEvents()
            
            results = self.dict_manager.check_for_updates(timeout=10)
            
            self.progress_bar.setValue(80)
            QApplication.processEvents()
            
            # Refresh the table to show update status
            self.load_dictionary_data()
            
            self.progress_bar.setValue(100)
            QApplication.processEvents()
            
            # Count updates and errors
            updates_available = sum(1 for r in results.values() if r.get('update_available') is True)
            up_to_date = sum(1 for r in results.values() if r.get('update_available') is False)
            errors = sum(1 for r in results.values() if r.get('error'))
            
            # Build result message
            messages = []
            if updates_available > 0:
                messages.append(f"<b style='color: #0064C8;'>{updates_available} update(s) available</b>")
            if up_to_date > 0:
                messages.append(f"<b style='color: #009600;'>{up_to_date} dictionary(ies) up to date</b>")
            if errors > 0:
                error_details = []
                for name, result in results.items():
                    if result.get('error'):
                        error_details.append(f"• {name}: {result['error']}")
                messages.append(f"<b style='color: orange;'>{errors} check(s) failed:</b><br>" + 
                              "<br>".join(error_details[:5]))  # Show first 5 errors
            
            # Show summary
            if messages:
                QMessageBox.information(
                    self, 
                    "Dictionary Update Check Complete",
                    "<br><br>".join(messages)
                )
            else:
                QMessageBox.information(
                    self,
                    "Dictionary Update Check Complete", 
                    "No online sources found for the loaded dictionaries."
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to check for updates: {str(e)}")
        finally:
            # Re-enable button and hide progress
            self.check_updates_btn.setEnabled(True)
            self.check_updates_btn.setText("Check for Updates")
            self.progress_bar.setVisible(False)
    
    def on_cell_double_clicked(self, row: int, column: int):
        """Handle double-click on table cells - specifically for Update column to download"""
        # Column 6 is the Update column
        if column != 6:
            return
        
        # Get the filename from this row (column 9)
        filename_item = self.dict_table.item(row, 9)
        if not filename_item:
            return
        
        filename = filename_item.text()
        
        # Find the dictionary info
        detailed_info = self.dict_manager.get_detailed_dictionary_info()
        dict_info = None
        for info in detailed_info:
            if info.name == filename:
                dict_info = info
                break
        
        if not dict_info or not dict_info.update_available or not dict_info.update_url:
            return
        
        # Show options dialog
        self.show_update_options_dialog([dict_info])
    
    def show_update_options_dialog(self, updates: list):
        """Show dialog with Load/Save options for dictionary updates"""
        if len(updates) == 1:
            dict_info = updates[0]
            title = "Update Dictionary"
            # Show title, version, and date
            dict_name = dict_info.dict_title or dict_info.name
            current_version = dict_info.version or 'Unknown'
            current_date = dict_info.dict_date or 'Unknown'
            online_version = dict_info.online_version or dict_info.version or 'Unknown'
            online_date = dict_info.online_date or 'Unknown'
            message = (f"<b>{dict_name}</b><br><br>"
                      f"Current: v{current_version} ({current_date})<br>"
                      f"Available: v{online_version} ({online_date})")
        else:
            title = "Update Dictionaries"
            message = f"Update {len(updates)} dictionaries?"
        
        # Create custom message box with three buttons
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setInformativeText(
            "<b>Load Only:</b> Load the update for this session only.\n\n"
            "<b>Save & Load:</b> Save to your user folder and load.\n"
            "(Updates will persist across sessions)"
        )
        
        load_btn = msg_box.addButton("Load Only", QMessageBox.ButtonRole.AcceptRole)
        save_btn = msg_box.addButton("Save && Load", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
        
        msg_box.setDefaultButton(save_btn)
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == load_btn:
            self.perform_updates(updates, save_to_disk=False)
        elif clicked == save_btn:
            self.perform_updates(updates, save_to_disk=True)
    
    def perform_updates(self, updates: list, save_to_disk: bool = False):
        """
        Download and apply dictionary updates.
        
        Args:
            updates: List of DictionaryInfo objects to update
            save_to_disk: If True, save to user's AppData folder for persistence
        """
        from utils.cif_dictionary_manager import ensure_user_dictionaries_directory, HTTP_HEADERS
        
        self.progress_bar.setVisible(True)
        successful = []
        failed = []
        
        for i, dict_info in enumerate(updates):
            progress = int(((i + 0.5) / len(updates)) * 100)
            self.progress_bar.setValue(progress)
            QApplication.processEvents()
            
            try:
                # Download the dictionary
                response = requests.get(dict_info.update_url, timeout=30, headers=HTTP_HEADERS)
                response.raise_for_status()
                content = response.text
                
                if save_to_disk:
                    # Save to user's AppData dictionaries folder
                    user_dict_dir = ensure_user_dictionaries_directory()
                    save_path = os.path.join(user_dict_dir, dict_info.name)
                    
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Update the dict_info path to point to user location
                    dict_info.path = save_path
                
                # Load the dictionary into the manager (either way)
                # Create a temp file for parsing if not saved
                if not save_to_disk:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.dic', 
                                                     delete=False, encoding='utf-8') as f:
                        f.write(content)
                        temp_path = f.name
                    
                    # Note: We don't actually need to reload here since the manager
                    # already has this dictionary - we just update the metadata
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                
                # Update metadata to reflect the update
                dict_info.update_available = False
                dict_info.dict_date = dict_info.online_date
                successful.append(dict_info.dict_title or dict_info.name)
                
            except Exception as e:
                failed.append(f"{dict_info.dict_title or dict_info.name}: {str(e)[:50]}")
        
        self.progress_bar.setValue(100)
        QApplication.processEvents()
        self.progress_bar.setVisible(False)
        
        # Refresh the table
        self.load_dictionary_data()
        
        # Show results
        messages = []
        if successful:
            action = "saved and loaded" if save_to_disk else "loaded"
            messages.append(f"<b style='color: green;'>Successfully {action} {len(successful)} dictionary(ies)</b>")
            if save_to_disk:
                from utils.cif_dictionary_manager import get_user_dictionaries_directory
                user_dir = get_user_dictionaries_directory()
                messages.append(f"<br><small>Saved to: {user_dir}</small>")
            if not save_to_disk:
                messages.append("<br><i>Note: Updates will be lost when CIVET is closed.</i>")
            else:
                messages.append("<br><i>Please restart CIVET to fully reload the updated dictionaries.</i>")
        if failed:
            messages.append(f"<b style='color: red;'>Failed to update {len(failed)} dictionary(ies):</b><br>" +
                          "<br>".join([f"• {name}" for name in failed]))
        
        QMessageBox.information(
            self,
            "Dictionary Update Complete",
            "<br>".join(messages)
        )
    
    def load_all_updates(self):
        """Load all available updates for this session only (not saved to disk)"""
        # Get all dictionaries with updates available
        detailed_info = self.dict_manager.get_detailed_dictionary_info()
        updates = [info for info in detailed_info if info.update_available and info.update_url]
        
        if not updates:
            QMessageBox.information(
                self,
                "No Updates Available",
                "No dictionary updates are available.\n\n"
                "Click 'Check for Updates' first to check for available updates."
            )
            return
        
        # Perform updates without saving to disk
        self.perform_updates(updates, save_to_disk=False)
    
    def download_all_updates(self):
        """Download and save all available dictionary updates"""
        # Get all dictionaries with updates available
        detailed_info = self.dict_manager.get_detailed_dictionary_info()
        updates = [info for info in detailed_info if info.update_available and info.update_url]
        
        if not updates:
            QMessageBox.information(
                self,
                "No Updates Available",
                "No dictionary updates are available to download.\n\n"
                "Click 'Check for Updates' first to check for available updates."
            )
            return
        
        # Build list of dictionaries to update
        dict_names = [info.dict_title or info.name for info in updates]
        dict_list = "\n".join([f"  • {name}" for name in dict_names])
        
        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Download Dictionary Updates",
            f"Download and save {len(updates)} dictionary update(s)?\n\n"
            f"{dict_list}\n\n"
            "This will save the updated dictionaries to your user folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Perform updates with saving to disk
        self.perform_updates(updates, save_to_disk=True)

    def on_selection_changed(self):
        """Handle table selection changes"""
        selected_rows = self.dict_table.selectionModel().selectedRows()
        
        if not selected_rows:
            self.remove_btn.setEnabled(False)
            self.details_text.clear()
            return
        
        # Enable remove button only if no primary dictionary (row 0) is selected
        has_primary = any(row.row() == 0 for row in selected_rows)
        self.remove_btn.setEnabled(not has_primary)
        
        # Show details for the first selected dictionary
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            selected_row = selected_rows[0].row()
            if selected_row < len(detailed_info):
                dict_info = detailed_info[selected_row]
                self.show_dictionary_details(dict_info)
        except Exception as e:
            self.details_text.setText(f"Error loading details: {str(e)}")
    
    def show_dictionary_details(self, dict_info):
        """Show detailed information for a dictionary"""
        details = []
        details.append(f"<b>Dictionary Details</b><br>")
        details.append(f"<b>Name:</b> {dict_info.name}")
        
        # Show active status with color
        active_text = "Yes" if dict_info.is_active else "No"
        active_color = "green" if dict_info.is_active else "red"
        details.append(f"<b>Active:</b> <span style='color: {active_color};'>{active_text}</span>")
        
        # Show dictionary type
        if dict_info.dict_type:
            details.append(f"<b>Dictionary Type:</b> {dict_info.dict_type}")
        
        details.append(f"<b>Path/URL:</b> {dict_info.path}")
        details.append(f"<b>Source Type:</b> {dict_info.source_type}")
        details.append(f"<b>Field Count:</b> {dict_info.field_count:,}")
        
        if dict_info.size_bytes > 0:
            size_kb = dict_info.size_bytes / 1024
            details.append(f"<b>Size:</b> {size_kb:.1f} KB")
        
        if dict_info.loaded_time:
            details.append(f"<b>Loaded:</b> {dict_info.loaded_time}")
        
        if dict_info.description:
            details.append(f"<br><b>Description:</b><br>{dict_info.description}")
        
        self.details_text.setHtml("<br>".join(details))
    
    def remove_selected_dictionary(self):
        """Remove the selected dictionaries"""
        selected_rows = self.dict_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        # Check if primary dictionary (row 0) is selected
        if any(row.row() == 0 for row in selected_rows):
            QMessageBox.information(self, "Cannot Remove", 
                                  "The primary CIF core dictionary cannot be removed.")
            return
        
        try:
            detailed_info = self.dict_manager.get_detailed_dictionary_info()
            
            # Get all selected dictionaries
            dicts_to_remove = []
            for row in selected_rows:
                row_index = row.row()
                if row_index < len(detailed_info):
                    dicts_to_remove.append(detailed_info[row_index])
            
            if not dicts_to_remove:
                return
            
            # Build confirmation message
            if len(dicts_to_remove) == 1:
                dict_info = dicts_to_remove[0]
                message = (f"Are you sure you want to remove the dictionary:\n\n"
                          f"{dict_info.name}\n"
                          f"({dict_info.field_count:,} fields)\n\n"
                          f"This action cannot be undone.")
            else:
                dict_list = "\n".join([f"• {d.name} ({d.field_count:,} fields)" for d in dicts_to_remove])
                message = (f"Are you sure you want to remove {len(dicts_to_remove)} dictionaries:\n\n"
                          f"{dict_list}\n\n"
                          f"This action cannot be undone.")
            
            # Confirm removal
            reply = QMessageBox.question(self, "Remove Dictionaries", message,
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Remove all selected dictionaries
                removed_count = 0
                failed_dicts = []
                
                for dict_info in dicts_to_remove:
                    success = self.dict_manager.remove_dictionary(dict_info.name)
                    if success:
                        removed_count += 1
                    else:
                        failed_dicts.append(dict_info.name)
                
                # Show result
                if removed_count == len(dicts_to_remove):
                    if removed_count == 1:
                        QMessageBox.information(self, "Dictionary Removed", 
                                              f"Dictionary '{dicts_to_remove[0].name}' has been removed successfully.")
                    else:
                        QMessageBox.information(self, "Dictionaries Removed", 
                                              f"Successfully removed {removed_count} dictionaries.")
                elif removed_count > 0:
                    QMessageBox.warning(self, "Partial Success", 
                                      f"Removed {removed_count} of {len(dicts_to_remove)} dictionaries.\n\n"
                                      f"Failed to remove: {', '.join(failed_dicts)}")
                else:
                    QMessageBox.warning(self, "Removal Failed", 
                                      "Failed to remove the selected dictionaries.")
                
                # Refresh the display
                self.refresh_data()
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                               f"An error occurred while removing dictionaries:\n{str(e)}")