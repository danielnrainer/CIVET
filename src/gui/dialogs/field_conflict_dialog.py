"""
Field Conflict Resolution Dialog

Allows users to resolve CIF field alias conflicts by choosing which field
to keep and what value to use for each conflict.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QTextEdit, QComboBox, QLineEdit, QGroupBox,
                           QScrollArea, QWidget, QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt
from typing import Dict, List, Tuple, Optional


class ConflictResolutionWidget(QWidget):
    """Widget for resolving a single field conflict"""
    
    def __init__(self, canonical_field: str, aliases_and_values: List[Tuple[str, str]], dict_manager=None, cif_format='modern', parent=None):
        super().__init__(parent)
        self.canonical_field = canonical_field
        self.aliases_and_values = aliases_and_values
        self.dict_manager = dict_manager
        self.cif_format = cif_format  # 'legacy' or 'modern'
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(f"<b>Conflict: {self.canonical_field}</b>")
        layout.addWidget(title_label)
        
        # Description of the conflict
        desc_text = "The following field aliases were found in your CIF file:\n\n"
        for alias, value in self.aliases_and_values:
            desc_text += f"• {alias}: {value}\n"
        desc_text += f"\nThese are all aliases of the same field. Please choose which field name to use and what value to keep."
        
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd;")
        layout.addWidget(desc_label)
        
        # Form for resolution
        form_layout = QFormLayout()
        
        # Field name combo
        self.field_combo = QComboBox()
        
        # Add aliases, but mark deprecated ones
        for alias, _ in self.aliases_and_values:
            if self.dict_manager and self.dict_manager.is_field_deprecated(alias):
                # Still add deprecated fields but mark them clearly
                self.field_combo.addItem(f"{alias} (DEPRECATED - not recommended)")
            else:
                self.field_combo.addItem(alias)
        
        # Determine the appropriate format option based on CIF format
        if self.cif_format.lower() == 'legacy':
            # For legacy CIFs, prefer the legacy equivalent
            legacy_equiv = None
            if self.dict_manager:
                legacy_equiv = self.dict_manager.get_modern_equivalent(self.canonical_field, prefer_format='legacy')
            
            if legacy_equiv and legacy_equiv != self.canonical_field:
                # Add legacy form as preferred option
                self.field_combo.addItem(f"{legacy_equiv} (legacy format - recommended)")
                self.field_combo.setCurrentText(f"{legacy_equiv} (legacy format - recommended)")
            else:
                # No specific legacy form, use canonical
                self.field_combo.addItem(f"{self.canonical_field} (recommended)")
                self.field_combo.setCurrentText(f"{self.canonical_field} (recommended)")
        else:
            # For modern CIFs, use the canonical (modern) field
            self.field_combo.addItem(f"{self.canonical_field} (modern format - recommended)")
            self.field_combo.setCurrentText(f"{self.canonical_field} (modern format - recommended)")
        
        form_layout.addRow("Field name to use:", self.field_combo)
        
        # Add deprecation warning if any deprecated fields are present
        if self.dict_manager:
            deprecated_aliases = [alias for alias, _ in self.aliases_and_values 
                                if self.dict_manager.is_field_deprecated(alias)]
            if deprecated_aliases:
                warning_text = f"⚠️ Warning: {', '.join(deprecated_aliases)} {'is' if len(deprecated_aliases) == 1 else 'are'} deprecated field{'s' if len(deprecated_aliases) > 1 else ''}. " \
                              f"Consider using the modern format ({self.canonical_field}) instead."
                warning_label = QLabel(warning_text)
                warning_label.setWordWrap(True)
                warning_label.setStyleSheet("color: #ff6b35; background-color: #fff3cd; padding: 8px; border: 1px solid #ffeaa7; border-radius: 4px;")
                layout.addWidget(warning_label)
        
        # Value input
        self.value_edit = QLineEdit()
        # Set initial value to the first non-empty value found
        for alias, value in self.aliases_and_values:
            if value.strip():
                self.value_edit.setText(value.strip())
                break
        
        form_layout.addRow("Value:", self.value_edit)
        
        layout.addLayout(form_layout)
        layout.addSpacing(20)
        
        self.setLayout(layout)
    
    def get_resolution(self) -> Tuple[str, str]:
        """Get the user's resolution for this conflict"""
        field_text = self.field_combo.currentText()

        # Handle the format options
        if "(modern format - recommended)" in field_text or "(modern format)" in field_text:
            field_name = self.canonical_field
        elif "(legacy format - recommended)" in field_text:
            # Extract the field name from legacy marker
            field_name = field_text.split(" (legacy format - recommended)")[0]
        elif "(recommended)" in field_text:
            # Extract the field name from recommended marker
            field_name = field_text.split(" (recommended)")[0]
        elif "(DEPRECATED - not recommended)" in field_text:
            # Extract the field name from deprecated marker
            field_name = field_text.split(" (DEPRECATED - not recommended)")[0]
        else:
            field_name = field_text
            
        value = self.value_edit.text().strip()
        
        return field_name, value


class FieldConflictDialog(QDialog):
    """Dialog for resolving field alias conflicts"""
    
    def __init__(self, conflicts: Dict[str, List[str]], cif_content: str, parent=None, dict_manager=None, cif_format='modern'):
        super().__init__(parent)
        self.conflicts = conflicts
        self.cif_content = cif_content
        self.dict_manager = dict_manager
        self.cif_format = cif_format  # 'legacy' or 'modern'
        self.resolution_widgets = []
        
        self.setWindowTitle("Resolve Field Alias Conflicts")
        self.setMinimumSize(600, 500)
        
        # Limit dialog height to prevent it from extending beyond screen
        # Allow for up to 10 conflicts to be shown comfortably, then use scrolling
        max_conflicts_visible = 10
        if len(conflicts) > max_conflicts_visible:
            # Estimated height: 200px header + 180px per conflict + 100px buttons + 50px margin
            self.setMaximumHeight(800)  # Reasonable maximum height
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"<h2>Field Alias Conflicts Found</h2>")
        layout.addWidget(header)
        
        # Info with special message for many conflicts
        if len(self.conflicts) > 10:
            info_text = f"Found {len(self.conflicts)} field conflicts that need to be resolved. " + \
                       "Due to the large number of conflicts, consider using the 'Auto-Resolve' button " + \
                       "to quickly set all conflicts to use modern format with the first available values."
        else:
            info_text = f"Found {len(self.conflicts)} field conflicts that need to be resolved. " + \
                       "Each conflict occurs when the same field appears in multiple forms in your CIF file."
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        if len(self.conflicts) > 10:
            info_label.setStyleSheet("color: #d68910; background-color: #fef9e7; padding: 10px; border: 1px solid #f7dc6f; border-radius: 4px;")
        layout.addWidget(info_label)
        
        # Scroll area for conflicts
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Create resolution widgets for each conflict
        for canonical_field, alias_list in self.conflicts.items():
            # Extract values for each alias from the CIF content
            aliases_and_values = self._extract_values_for_aliases(alias_list)
            
            # Create group box for this conflict
            group_box = QGroupBox()
            group_layout = QVBoxLayout()
            
            resolution_widget = ConflictResolutionWidget(canonical_field, aliases_and_values, self.dict_manager, self.cif_format, self)
            self.resolution_widgets.append(resolution_widget)
            
            group_layout.addWidget(resolution_widget)
            group_box.setLayout(group_layout)
            scroll_layout.addWidget(group_box)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        # Set a reasonable height policy for the scroll area
        scroll_area.setMinimumHeight(200)
        
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Format-aware auto-resolve button text
        if self.cif_format.lower() == 'legacy':
            auto_resolve_text = "Auto-Resolve (Use Legacy format + First Value)"
        else:
            auto_resolve_text = "Auto-Resolve (Use Modern format + First Value)"
        
        auto_resolve_btn = QPushButton(auto_resolve_text)
        auto_resolve_btn.clicked.connect(self.auto_resolve)
        if len(self.conflicts) > 5:
            auto_resolve_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        button_layout.addWidget(auto_resolve_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setDefault(True)  # Set Cancel as default instead of Apply
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply Resolutions")
        apply_btn.clicked.connect(self.accept)
        # Removed setDefault(True) from apply button
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _extract_values_for_aliases(self, alias_list: List[str]) -> List[Tuple[str, str]]:
        """Extract the values for each alias from the CIF content"""
        aliases_and_values = []
        
        lines = self.cif_content.split('\n')
        
        for alias in alias_list:
            value = ""
            found_in_loop = False
            
            # Check if field is in a loop
            in_loop = False
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith('loop_'):
                    in_loop = True
                elif in_loop and line_stripped == alias:
                    found_in_loop = True
                    value = "(in loop - data preserved)"
                    break
                elif in_loop and line_stripped.startswith('_'):
                    continue  # Still in loop header
                elif in_loop and line_stripped and not line_stripped.startswith('_') and not line_stripped.startswith('#'):
                    in_loop = False  # End of loop
                elif not line_stripped or line_stripped.startswith('#'):
                    in_loop = False  # End of loop
            
            # If not found in loop, look for simple field definition
            if not found_in_loop:
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith(alias + ' '):
                        # Simple field definition
                        parts = line_stripped.split(None, 1)
                        if len(parts) > 1:
                            value = parts[1]
                        break
                    elif line_stripped == alias:
                        # Field might be on next line (multiline value)
                        value = "(multiline value)"
                        break
            
            # If still no value found, mark as present but no value
            if not value:
                value = "(present, no value found)"
            
            aliases_and_values.append((alias, value))
        
        return aliases_and_values
    
    def auto_resolve(self):
        """Auto-resolve all conflicts using the appropriate format and first available values"""
        format_label = "modern format - recommended" if self.cif_format.lower() == 'modern' else "legacy format - recommended"
        
        for widget in self.resolution_widgets:
            # Try to find the appropriate format option
            for i in range(widget.field_combo.count()):
                item_text = widget.field_combo.itemText(i)
                if format_label in item_text:
                    widget.field_combo.setCurrentIndex(i)
                    break
            else:
                # Fallback: try to find any recommended option
                for i in range(widget.field_combo.count()):
                    item_text = widget.field_combo.itemText(i)
                    if "recommended" in item_text:
                        widget.field_combo.setCurrentIndex(i)
                        break
            
            # Keep current value (should already be set to first non-empty value)
        
        format_name = "legacy" if self.cif_format.lower() == 'legacy' else "modern"
        QMessageBox.information(self, "Auto-Resolved", 
                              f"All conflicts have been auto-resolved using {format_name} format and the first available values. " +
                              "You can still modify the selections before applying.")
    
    def get_resolutions(self) -> Dict[str, Tuple[str, str]]:
        """Get all user resolutions"""
        resolutions = {}
        
        for i, (canonical_field, _) in enumerate(self.conflicts.items()):
            field_name, value = self.resolution_widgets[i].get_resolution()
            resolutions[canonical_field] = (field_name, value)
        
        return resolutions