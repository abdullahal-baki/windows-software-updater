"""Custom-painted window control buttons (minimise / maximise / close)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QToolButton

from wsu.ui.theme import TEXT


class WindowControlButton(QToolButton):
    """A circular window-control button painted entirely with QPainter.

    Args:
        symbol: One of ``'min'``, ``'max'`` / ``'restore'``, or ``'close'``.
        color_normal: Idle circle fill (``None`` = transparent until hover).
        color_hover: Circle fill on hover.
    """

    def __init__(
        self,
        symbol: str,
        color_normal: Optional[str],
        color_hover: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self._color_normal = QColor(color_normal) if color_normal else None
        self._color_hover = QColor(color_hover)
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("WindowControlButton")
        self.setIcon(QIcon())

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 4

        # Circle fill: subtle at idle, brighter on hover.
        if self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color_hover)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        elif self._color_normal:
            idle_fill = QColor(self._color_normal)
            idle_fill.setAlphaF(0.35)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(idle_fill)
            painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # Symbol is always drawn so each control is recognisable at idle.
        if self._hovered:
            symbol_color = QColor("#0B0C0F")
        elif self._symbol == "close":
            symbol_color = QColor("#FF9C96")
        else:
            symbol_color = QColor(TEXT)
        pen = QPen(symbol_color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = int(r * 0.42)
        x0, y0 = int(cx) - m, int(cy) - m
        x1, y1 = int(cx) + m, int(cy) + m
        if self._symbol == "close":
            painter.drawLine(x0, y0, x1, y1)
            painter.drawLine(x1, y0, x0, y1)
        elif self._symbol == "min":
            painter.drawLine(x0, int(cy), x1, int(cy))
        elif self._symbol in ("max", "restore"):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x0, y0, m * 2, m * 2)
        painter.end()
