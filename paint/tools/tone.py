from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

import numpy as np

from ..brush import stamps_along
from ..utils import array_to_image, image_array_view
from .base import BaseTool


class ToneTool(BaseTool):
    id = "tone"
    label = "Densité"
    shortcut = "K"
    icon = "tone"

    def __init__(self, app):
        super().__init__(app)
        self.size = 50
        self.hardness = 0.6
        self.strength = 0.45
        self.mode = "dodge"
        self._layer = None
        self._tx = None
        self._last: QPointF | None = None

    def cursor_size(self) -> int:
        return self.size

    def press(self, pos, event) -> None:
        layer = self.paintable_layer()
        if layer is None:
            return
        self._layer = layer
        self._tx = self.doc.history.begin(
            "Éclaircir" if self.mode == "dodge" else "Assombrir")
        self._last = None
        self._apply(pos)

    def move(self, pos, event) -> None:
        if self._tx is not None:
            self._apply(pos)

    def _apply(self, pos: QPointF) -> None:
        if self._tx is None or self._layer is None:
            return
        size = max(1, int(self.size))
        spacing = max(1.0, size * 0.12)
        points = [pos] if self._last is None else list(stamps_along(self._last, pos, spacing))
        half = size / 2.0
        rect = QRect()
        for point in points:
            stamp_rect = QRect(int(point.x() - half), int(point.y() - half), size, size)
            rect = stamp_rect if rect.isNull() else rect.united(stamp_rect)
        self._last = pos
        rect = rect.intersected(self.doc.rect())
        if rect.isEmpty():
            return
        stamp = self.app.stamp_cache.get(size, self.hardness, QColor(255, 255, 255))
        mask = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
        mask.fill(Qt.transparent)
        painter = QPainter(mask)
        for point in points:
            painter.drawImage(int(point.x() - half) - rect.left(),
                              int(point.y() - half) - rect.top(), stamp)
        painter.end()
        crop = self._layer.image.copy(rect)
        conv, array = image_array_view(crop)
        mask_image, alpha = image_array_view(mask)
        factor = alpha[:, :, 3].astype(np.float32) / 255.0
        amount = max(0.01, min(1.0, self.strength))
        if self.mode == "dodge":
            factor = 1.0 + factor * amount * 0.6
        else:
            factor = 1.0 - factor * amount * 0.6
        rgb = array[:, :, :3].astype(np.float32) * factor[:, :, None]
        array[:, :, :3] = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
        result = array_to_image(array)
        painter = QPainter(self._layer.image)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(rect.topLeft(), result)
        painter.end()
        self._tx.touch(self._layer, rect)
        self.doc.invalidate(rect)
        self.app.canvas.update()

    def release(self, pos, event) -> None:
        if self._tx is not None:
            self._tx.commit()
        self._tx = None
        self._layer = None
        self._last = None

    def cancel(self) -> None:
        if self._tx is not None:
            self._tx.cancel()
        self._tx = None
        self._layer = None
        self._last = None
