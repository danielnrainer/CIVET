"""Reusable collapsible container widgets for GUI dialogs.

Two flavours share the same toggle behaviour:

* :class:`CollapsibleBox` - a *framed* group, for visually distinct sections
  such as the panels in the editor settings dialog.
* :class:`CollapsibleSection` - a *borderless* section with a bold toggle
  row, for dense dialogs where the goal is to reclaim vertical space with
  minimal chrome.

Both expose ``content_layout`` (a ``QVBoxLayout``) plus ``add_widget`` /
``add_layout`` convenience helpers, and ``setExpanded(bool)`` /
``is_expanded()``.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QSizePolicy, QToolButton, QVBoxLayout, QWidget
)


def _arrow(expanded: bool) -> Qt.ArrowType:
    return Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow


class _CollapsibleBase(QFrame):
    """Shared toggle logic for the collapsible widgets.

    Subclasses are responsible for their own framing / styling; this base
    only wires the toggle button to the hideable content area.
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(_arrow(expanded))
        self.toggle_button.clicked.connect(self._on_toggled)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_widget.setVisible(expanded)

        self._outer = QVBoxLayout(self)
        self._outer.addWidget(self.toggle_button)
        self._outer.addWidget(self.content_widget)

    def _on_toggled(self, checked: bool) -> None:
        self.content_widget.setVisible(checked)
        self.toggle_button.setArrowType(_arrow(checked))
        # Let parent layouts reclaim the freed space immediately.
        self.updateGeometry()

    def setExpanded(self, expanded: bool) -> None:
        """Expand or collapse the section programmatically."""
        self.toggle_button.setChecked(expanded)
        self._on_toggled(expanded)

    # Snake-case alias for call sites that prefer it.
    set_expanded = setExpanded

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()

    def add_widget(self, widget) -> None:
        self.content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.content_layout.addLayout(layout)

    # CamelCase aliases mirroring the Qt layout API.
    addWidget = add_widget
    addLayout = add_layout


class CollapsibleBox(_CollapsibleBase):
    """A framed collapsible group with a titled toggle button.

    Use where the section should read as a visually distinct box (e.g. the
    grouped panels in the editor settings dialog).
    """

    def __init__(self, title: str, parent=None, *, expanded: bool = True):
        super().__init__(title, expanded, parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(4)
        self.content_layout.setContentsMargins(0, 6, 0, 0)
        self.content_layout.setSpacing(8)


class CollapsibleSection(_CollapsibleBase):
    """A borderless collapsible section with a bold toggle row.

    Collapses to a single header row and never claims spare vertical space,
    so parent layouts can hand it to the widget that needs it. Use in dense
    dialogs where a framed box would just add clutter.
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(title, expanded, parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        self.toggle_button.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 2px; }"
        )
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(1)
        self.content_layout.setContentsMargins(16, 2, 2, 6)
