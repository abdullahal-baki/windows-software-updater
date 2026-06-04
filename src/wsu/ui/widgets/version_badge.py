"""A rounded pill badge that displays a version string."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from wsu.ui.theme import (
    ACCENT,
    ACCENT_SOFT,
    BORDER_MID,
    BORDER_SOFT,
    TEXT_MUTED,
)


class VersionBadge(QWidget):
    """A rounded pill badge showing a version string.

    Args:
        text: The version string to display.
        variant: ``'installed'`` (muted grey pill) or ``'available'``
            (cyan accent pill).
    """

    def __init__(self, text: str, variant: str = "installed", parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self.setFont(QFont("Bahnschrift", 8))
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setFixedHeight(22)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        fm = QFontMetrics(self.font())
        width = fm.horizontalAdvance(self._text) + 22
        return QSize(max(width, 52), 22)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.height() / 2
        rect = self.rect().adjusted(0, 1, -1, -2)

        if self._variant == "available":
            bg = QColor(ACCENT)
            bg.setAlphaF(0.15)
            border = QColor(ACCENT)
            text_color = QColor(ACCENT_SOFT)
        else:
            bg = QColor(BORDER_MID)
            bg.setAlphaF(0.5)
            border = QColor(BORDER_SOFT)
            text_color = QColor(TEXT_MUTED)

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()
