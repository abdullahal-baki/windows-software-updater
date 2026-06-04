"""Procedurally drawn application artwork (no image assets required)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap


def build_logo_pixmap(size: int) -> QPixmap:
    """Render the app logo: a rounded gradient tile with an upward arrow.

    The arrow inside a dark circle reads as "update". Painted at the requested
    pixel ``size`` so it stays crisp for both the title bar and the tray icon.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#21D4FD"))
    gradient.setColorAt(1, QColor("#2BD98A"))

    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, size * 0.35, size * 0.35)

    painter.setBrush(QColor("#0B0C0F"))
    inset = int(size * 0.28)
    painter.drawEllipse(inset, inset, size - inset * 2, size - inset * 2)

    cx, cy = size / 2, size / 2
    arrow_h = size * 0.30
    arrow_w = size * 0.20
    path = QPainterPath()
    path.moveTo(cx, cy - arrow_h / 2)
    path.lineTo(cx + arrow_w / 2, cy)
    path.lineTo(cx + arrow_w * 0.25, cy)
    path.lineTo(cx + arrow_w * 0.25, cy + arrow_h / 2)
    path.lineTo(cx - arrow_w * 0.25, cy + arrow_h / 2)
    path.lineTo(cx - arrow_w * 0.25, cy)
    path.lineTo(cx - arrow_w / 2, cy)
    path.closeSubpath()

    arrow_gradient = QLinearGradient(0, 0, size, size)
    arrow_gradient.setColorAt(0, QColor("#21D4FD"))
    arrow_gradient.setColorAt(1, QColor("#2BD98A"))
    painter.setBrush(arrow_gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)

    painter.end()
    return pixmap
