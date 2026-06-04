"""The custom frameless-window title bar (logo, title, window controls)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wsu.core.config import APP_SUBTITLE, APP_TITLE
from wsu.ui.icons import build_logo_pixmap
from wsu.ui.theme import ACCENT
from wsu.ui.widgets.window_controls import WindowControlButton


class TitleBar(QFrame):
    """Draggable title bar for the frameless main window.

    Wires its minimise / maximise / close buttons to the parent window's
    ``showMinimized`` / ``toggle_maximize`` / ``close`` methods, and lets the
    user drag or double-click to move / maximise the window.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(50)
        self._drag_pos: Optional[QPoint] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 5, 12, 5)
        layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setPixmap(build_logo_pixmap(26))
        logo_label.setFixedSize(28, 28)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(2)
        title = QLabel(APP_TITLE)
        title.setObjectName("TitleText")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("SubtitleText")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)

        title_wrap = QHBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(10)
        title_wrap.addWidget(logo_label)
        title_wrap.addLayout(title_block)

        left = QWidget()
        left.setLayout(title_wrap)

        layout.addWidget(left)
        layout.addStretch(1)

        self.min_button = WindowControlButton(
            symbol="min", color_normal="#2A3040", color_hover="#5A6070"
        )
        self.max_button = WindowControlButton(
            symbol="max", color_normal="#2A3040", color_hover="#5A6070"
        )
        self.close_button = WindowControlButton(
            symbol="close", color_normal="#2A3040", color_hover="#E0443A"
        )

        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

        self.min_button.clicked.connect(parent.showMinimized)
        self.max_button.clicked.connect(parent.toggle_maximize)
        self.close_button.clicked.connect(parent.close)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        gradient = QLinearGradient(0, 0, w, 0)
        gradient.setColorAt(0.0, QColor(ACCENT))
        gradient.setColorAt(0.6, QColor(ACCENT))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        pen = QPen()
        pen.setBrush(gradient)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(0, h - 1, w, h - 1)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().toggle_maximize()
