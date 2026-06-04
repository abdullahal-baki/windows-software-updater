"""The footer status indicator (a coloured dot plus a text label)."""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from wsu.ui.theme import ACCENT, ERROR, SUCCESS, TEXT_MUTED, WARNING


class StatusChip(QWidget):
    """Footer status indicator: a colored dot plus a text label.

    States map to dot colors; ``'scanning'`` pulses via an opacity animation.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._dot_opacity = 1.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self._dot_canvas = QWidget()
        self._dot_canvas.setFixedSize(10, 10)
        self._dot_canvas.paintEvent = self._paint_dot  # type: ignore[method-assign]
        layout.addWidget(self._dot_canvas, 0, Qt.AlignmentFlag.AlignVCenter)

        self._label = QLabel("Idle")
        self._label.setObjectName("FooterText")
        layout.addWidget(self._label)

        self._anim = QPropertyAnimation(self, b"dot_opacity")
        self._anim.setDuration(1000)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.2)
        self._anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        self._anim.setLoopCount(-1)

    @pyqtProperty(float)
    def dot_opacity(self) -> float:  # noqa: D401 - Qt property
        return self._dot_opacity

    @dot_opacity.setter
    def dot_opacity(self, value: float) -> None:
        self._dot_opacity = value
        self._dot_canvas.update()

    def set_state(self, state: str, text: str) -> None:
        """Set the chip's state and label text."""
        self._state = state
        self._label.setText(text)
        if state == "scanning":
            self._anim.start()
        else:
            self._anim.stop()
            self._dot_opacity = 1.0
        self._dot_canvas.update()

    def _paint_dot(self, event) -> None:
        color_map = {
            "idle": TEXT_MUTED,
            "scanning": ACCENT,
            "updating": WARNING,
            "done": SUCCESS,
            "error": ERROR,
        }
        c = QColor(color_map.get(self._state, TEXT_MUTED))
        c.setAlphaF(self._dot_opacity)
        painter = QPainter(self._dot_canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(0, 0, 9, 9)
        painter.end()


class FooterProxy:
    """Adapter so ``setText(...)`` calls route to a :class:`StatusChip`.

    Lets call sites set a status string without knowing about chip states;
    the message text is mapped to the appropriate dot colour/state.
    """

    def __init__(self, chip: StatusChip) -> None:
        self._chip = chip

    def setText(self, text: str) -> None:  # noqa: N802 - mirrors QLabel API
        lowered = text.lower()
        if text == "Idle":
            state = "idle"
        elif "scan" in lowered:
            state = "scanning"
        elif "updating" in lowered:
            state = "updating"
        elif "updated" in lowered:
            state = "done"
        else:
            state = "idle"
        self._chip.set_state(state, text)
