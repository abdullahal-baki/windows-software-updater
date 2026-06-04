"""The placeholder shown when the updates table is empty."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wsu.ui.theme import ACCENT, BORDER_MID, SUCCESS, TEXT, TEXT_MUTED


class EmptyStateWidget(QWidget):
    """Shown in place of the table when there is nothing to display.

    Supported states: ``'idle'``, ``'scanning'`` (animated spinner),
    ``'up_to_date'`` (success check).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._angle = 0.0

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._advance_spinner)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)

        self._icon_canvas = QWidget()
        self._icon_canvas.setFixedSize(72, 72)
        self._icon_canvas.paintEvent = self._paint_icon  # type: ignore[method-assign]
        layout.addWidget(self._icon_canvas, 0, Qt.AlignmentFlag.AlignHCenter)

        self._title_lbl = QLabel("Scan to check for updates")
        self._title_lbl.setObjectName("EmptyStateTitle")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("Click 'Check for Updates' to begin")
        self._sub_lbl.setObjectName("EmptyStateSub")
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sub_lbl)

    def set_state(self, state: str) -> None:
        """Switch the displayed state and start/stop the spinner."""
        self._state = state
        if state == "idle":
            self._spin_timer.stop()
            self._title_lbl.setText("Scan to check for updates")
            self._sub_lbl.setText("Click 'Check for Updates' to begin")
        elif state == "scanning":
            self._angle = 0.0
            self._spin_timer.start()
            self._title_lbl.setText("Scanning for updates…")
            self._sub_lbl.setText("This may take a moment")
        elif state == "up_to_date":
            self._spin_timer.stop()
            self._title_lbl.setText("All software is up to date")
            self._sub_lbl.setText("No updates were found")
        self._icon_canvas.update()

    def _advance_spinner(self) -> None:
        self._angle = (self._angle + 4.0) % 360.0
        self._icon_canvas.update()

    def _paint_icon(self, event) -> None:
        w = self._icon_canvas.width()
        h = self._icon_canvas.height()
        painter = QPainter(self._icon_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = w / 2, h / 2

        if self._state == "scanning":
            track_pen = QPen(QColor(BORDER_MID), 4)
            painter.setPen(track_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(int(cx - 28), int(cy - 28), 56, 56, 0, 360 * 16)
            pen = QPen(QColor(ACCENT), 4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                int(cx - 28), int(cy - 28), 56, 56, int(-self._angle * 16), 270 * 16
            )
        elif self._state == "up_to_date":
            pen = QPen(QColor(SUCCESS), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(int(cx - 28), int(cy - 28), 56, 56)
            path = QPainterPath()
            path.moveTo(cx - 12, cy)
            path.lineTo(cx - 4, cy + 10)
            path.lineTo(cx + 14, cy - 10)
            painter.drawPath(path)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            bg = QColor(BORDER_MID)
            bg.setAlphaF(0.4)
            painter.setBrush(bg)
            painter.drawRoundedRect(int(cx - 28), int(cy - 28), 56, 56, 14, 14)
            pen = QPen(QColor(TEXT_MUTED), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            arrow = QPainterPath()
            arrow.moveTo(cx, cy + 14)
            arrow.lineTo(cx, cy - 14)
            arrow.moveTo(cx, cy - 14)
            arrow.lineTo(cx + 10, cy - 4)
            arrow.moveTo(cx, cy - 14)
            arrow.lineTo(cx - 10, cy - 4)
            painter.drawPath(arrow)
        painter.end()
