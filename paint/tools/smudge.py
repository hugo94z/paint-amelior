from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..brush import stamps_along
from .base import BaseTool


class SmudgeTool(BaseTool):
    id = "smudge"
    label = "Goutte d'eau"
    shortcut = "J"
    icon = "smudge"

    def __init__(self, app):
        super().__init__(app)
        self.size = 46
        self.hardness = 0.5
        self.strength = 0.45
        self._layer = None
        self._tx = None
        self._pickup: QImage | None = None
        self._last: QPointF | None = None

    def cursor_size(self) -> int:
        return self.size

    def _capture(self, point: QPointF) -> QImage:
        size = max(1, int(self.size))
        half = size // 2
        patch = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        patch.fill(Qt.transparent)
        painter = QPainter(patch)
        painter.drawImage(0, 0, self._layer.image,
                          int(point.x()) - half, int(point.y()) - half, size, size)
        painter.end()
        return patch

    def press(self, pos, event) -> None:
        layer = self.paintable_layer()
        if layer is None:
            return
        self._layer = layer
        self._tx = self.doc.history.begin("Goutte d'eau")
        self._pickup = self._capture(pos)
        self._last = pos

    def move(self, pos, event) -> None:
        if self._pickup is None or self._tx is None or self._layer is None:
            return
        size = max(1, int(self.size))
        spacing = max(1.0, size * 0.18)
        points = list(stamps_along(self._last, pos, spacing)) if self._last is not None else [pos]
        half = size / 2.0
        strength = max(0.05, min(1.0, self.strength))
        stamp = self.app.stamp_cache.get(size, self.hardness, QColor(255, 255, 255))
        rect = QRect()
        for point in points:
            current = self._capture(point)
            blended = current.copy()
            painter = QPainter(blended)
            painter.setOpacity(strength)
            painter.drawImage(0, 0, self._pickup)
            painter.end()
            mask_image = stamp
            masked = blended.copy()
            painter = QPainter(masked)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, mask_image)
            painter.end()
            painter = QPainter(self._layer.image)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(int(point.x() - half), int(point.y() - half), masked)
            painter.end()
            self._pickup = blended
            stamp_rect = QRect(int(point.x() - half), int(point.y() - half), size, size)
            rect = stamp_rect if rect.isNull() else rect.united(stamp_rect)
        self._last = pos
        rect = rect.intersected(self.doc.rect())
        if not rect.isEmpty():
            self._tx.touch(self._layer, rect)
            self.doc.invalidate(rect)
            self.app.canvas.update()

    def release(self, pos, event) -> None:
        if self._tx is not None:
            self._tx.commit()
        self._tx = None
        self._layer = None
        self._pickup = None
        self._last = None

    def cancel(self) -> None:
        if self._tx is not None:
            self._tx.cancel()
        self._tx = None
        self._layer = None
        self._pickup = None
        self._last = None
