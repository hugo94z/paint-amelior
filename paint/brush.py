from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRadialGradient


def _hardness_stops(hardness: float) -> list[tuple[float, int]]:
    h = max(0.0, min(1.0, hardness))
    if h >= 0.995:
        return [(0.0, 255), (0.9, 255), (1.0, 0)]
    inner = max(0.0, h * 0.92)
    return [(0.0, 255), (inner, 255), (inner + (1.0 - inner) * 0.35, int(255 * 0.55)), (1.0, 0)]


class StampCache:
    def __init__(self, budget_bytes: int = 128 * 1024 * 1024, max_items: int = 96):
        self.budget_bytes = budget_bytes
        self.max_items = max_items
        self._items: OrderedDict = OrderedDict()
        self._bytes = 0

    def get(self, size: int, hardness: float, color: QColor) -> QImage:
        key = (int(size), round(float(hardness), 2), color.rgba())
        img = self._items.get(key)
        if img is not None:
            self._items.move_to_end(key)
            return img
        img = self._build(int(size), float(hardness), color)
        self._items[key] = img
        self._bytes += img.sizeInBytes()
        while self._items and (self._bytes > self.budget_bytes or len(self._items) > self.max_items):
            _, old = self._items.popitem(last=False)
            self._bytes -= old.sizeInBytes()
        return img

    @staticmethod
    def _build(size: int, hardness: float, color: QColor) -> QImage:
        size = max(1, size)
        img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        radius = size / 2.0
        if hardness >= 0.995:
            c = QColor(color)
            c.setAlpha(int(color.alpha()))
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(QRect(0, 0, size, size))
        else:
            grad = QRadialGradient(radius, radius, radius)
            for stop, alpha in _hardness_stops(hardness):
                c = QColor(color)
                c.setAlpha(int(color.alpha() * alpha / 255))
                grad.setColorAt(stop, c)
            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawEllipse(QRect(0, 0, size, size))
        painter.end()
        return img


class StrokeBuffer:
    def __init__(self, size: QSize):
        self.image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.transparent)
        self.dirty = QRect()

    def reset(self) -> None:
        self.image.fill(Qt.transparent)
        self.dirty = QRect()

    def stamp(self, image: QImage, center: QPointF) -> QRect:
        half = image.width() / 2.0
        x = int(round(center.x() - half))
        y = int(round(center.y() - half))
        painter = QPainter(self.image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(x, y, image)
        painter.end()
        rect = QRect(x, y, image.width(), image.height())
        self.dirty = rect if self.dirty.isNull() else self.dirty.united(rect)
        return rect


def stamps_along(start: QPointF, end: QPointF, spacing: float):
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    distance = (dx * dx + dy * dy) ** 0.5
    if distance < 0.01:
        yield end
        return
    steps = max(1, int(distance / max(0.5, spacing)))
    for i in range(1, steps + 1):
        t = i / steps
        yield QPointF(start.x() + dx * t, start.y() + dy * t)
