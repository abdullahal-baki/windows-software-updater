"""A styled search input with a painted magnifier and clear button."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget

from wsu.ui.theme import BORDER_FOCUS, BORDER_SOFT, SURFACE, TEXT_MUTED


class SearchBar(QWidget):
    """A ``QLineEdit`` wrapped in a custom widget.

    Paints a magnifier icon on the left and shows a clear (✕) button while
    text is present. Connect to text changes via the exposed
    :attr:`line_edit` attribute.
    """

    def __init__(self, placeholder: str = "Search...", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self.setFixedHeight(38)

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setObjectName("SearchInput")
        self.line_edit.setStyleSheet(
            "QLineEdit#SearchInput { background: transparent; border: none;"
            " color: #E7EAF0; padding: 0px; }"
        )

        self._clear_btn = QToolButton(self)
        self._clear_btn.setText("✕")
        self._clear_btn.setObjectName("SearchClearButton")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setFixedSize(20, 20)
        self._clear_btn.setVisible(False)
        self._clear_btn.clicked.connect(self.line_edit.clear)
        self.line_edit.textChanged.connect(
            lambda t: self._clear_btn.setVisible(bool(t))
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(38, 0, 8, 0)
        layout.setSpacing(4)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self._clear_btn)

        self._focused = False
        self.line_edit.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if obj is self.line_edit:
            if event.type() == QEvent.Type.FocusIn:
                self._focused = True
                self.update()
            elif event.type() == QEvent.Type.FocusOut:
                self._focused = False
                self.update()
        return super().eventFilter(obj, event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = 10

        border_color = QColor(BORDER_FOCUS if self._focused else BORDER_SOFT)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, radius, radius)

        icon_cx, icon_cy = 18, h // 2
        icon_r = 6
        pen = QPen(QColor(TEXT_MUTED))
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(icon_cx - icon_r, icon_cy - icon_r, icon_r * 2, icon_r * 2)
        off = int(icon_r * 0.707)
        painter.drawLine(
            icon_cx + off, icon_cy + off, icon_cx + off + 4, icon_cy + off + 4
        )
        painter.end()

    def text(self) -> str:
        """Return the current search text."""
        return self.line_edit.text()
