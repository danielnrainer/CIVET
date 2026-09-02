"""Reusable collapsible section widget for GUI dialogs."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class CollapsibleBox(QFrame):
    """A collapsible section container with a titled toggle button."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.clicked.connect(self._on_toggled)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 6, 0, 0)
        self.content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_widget)

    def _on_toggled(self, checked: bool) -> None:
        self.content_widget.setVisible(checked)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def setExpanded(self, expanded: bool) -> None:
        """Expand or collapse the section programmatically."""
        self.toggle_button.setChecked(expanded)
        self._on_toggled(expanded)
