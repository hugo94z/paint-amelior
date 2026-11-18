from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class ColorWheel(QWidget):
    color_picked = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0.0
        self._saturation = 0.0
        self._value = 255
        self._alpha = 255
        self.setMinimumSize(130, 130)
        self.setCursor(Qt.CrossCursor)

    def set_color(self, color: QColor) -> None:
        hue = max(0, color.hue())
        self._hue = float(hue)
        self._saturation = color.saturationF()
        self._value = color.value()
        self._alpha = color.alpha()
        self.update()

    def set_value(self, value: int) -> None:
        self._value = max(0, min(255, int(value)))
        self.update()

    def set_alpha(self, alpha: int) -> None:
        self._alpha = max(0, min(255, int(alpha)))
        self.update()

    def color(self) -> QColor:
        return QColor.fromHsvF(self._hue / 360.0, self._saturation,
                               self._value / 255.0, self._alpha / 255.0)

    def _disk(self) -> QRectF:
        size = min(self.width(), self.height()) - 12
        size = max(20, size)
        return QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        disk = self._disk()
        center = disk.center()
        conical = QConicalGradient(center, 0.0)
        for step in range(0, 360, 15):
            conical.setColorAt(step / 360.0, QColor.fromHsv(step % 360, 255, 255))
        conical.setColorAt(1.0, QColor.fromHsv(0, 255, 255))
        painter.setPen(Qt.NoPen)
        painter.setBrush(conical)
        painter.drawEllipse(disk)
        radial = QRadialGradient(center, disk.width() / 2)
        radial.setColorAt(0.0, QColor(255, 255, 255, 255))
        radial.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(radial)
        painter.drawEllipse(disk)
        if self._value < 255:
            painter.setBrush(QColor(0, 0, 0, 255 - self._value))
            painter.drawEllipse(disk)
        angle = math.radians(self._hue)
        radius = disk.width() / 2 * self._saturation
        point = QPointF(center.x() + math.cos(angle) * radius,
                        center.y() - math.sin(angle) * radius)
        painter.setBrush(self.color())
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(point, 5, 5)
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawEllipse(point, 6, 6)
        painter.end()

    def _pick(self, position: QPointF) -> None:
        disk = self._disk()
        center = disk.center()
        dx = position.x() - center.x()
        dy = center.y() - position.y()
        radius = disk.width() / 2
        distance = math.hypot(dx, dy)
        if distance < 1e-6:
            return
        self._hue = math.degrees(math.atan2(dy, dx)) % 360.0
        self._saturation = min(1.0, distance / max(1e-6, radius))
        self.update()
        self.color_picked.emit(self.color())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pick(event.position())

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self._pick(event.position())
