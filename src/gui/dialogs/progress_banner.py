"""Shared "Check N/Total" progress banner used by the check-pipeline dialogs.

See gui/check_progress.py for what the numbers mean (an upper-bound estimate
that grows on the fly, not an exact prediction).
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt


def build_check_progress_banner(progress):
    """Return a QWidget with a "Check N/Total" label and a slim progress bar,
    or None if there's nothing to show.

    Args:
        progress: Optional (current, total) tuple, e.g. from
            CheckProgressTracker.snapshot(). None or a non-positive total
            means no check run is in progress - the caller should skip
            adding the banner entirely.
    """
    if not progress:
        return None
    current, total = progress
    if not total or total <= 0:
        return None

    display_current = min(current, total)

    banner = QWidget()
    layout = QHBoxLayout(banner)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    label = QLabel(f"Check {display_current}/{total}")
    label.setStyleSheet("font-weight: bold; color: #37474F;")

    bar = QProgressBar()
    bar.setMinimum(0)
    bar.setMaximum(total)
    bar.setValue(display_current)
    bar.setFixedHeight(14)
    bar.setTextVisible(False)

    layout.addWidget(label)
    layout.addWidget(bar, 1)
    return banner
