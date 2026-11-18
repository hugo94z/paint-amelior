from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from ..brush import acquire_buffer, stamps_along
from .base import BaseTool


class CloneTool(BaseTool):
    id = "clone"
    label = "Tampon de clonage"
    shortcut = "S"
    icon = "clone"
    handles_alt = True

    def __init__(self, app):
        super().__init__(app)
        self.size = 60
        self.hardness = 0.7
        self.opacity = 1.0
        self.aligned = True
        self.sample_all = True
        self.source: QPointF | None = None
        self._offset = QPointF(0, 0)
        self._layer = None
        self._buffer = None
        self._tx = None
        self._last: QPointF | None = None

    def cursor_size(self) -> int:
        return self.size

    def press(self, pos, event) -> None:
        if event is not None and event.modifiers() & Qt.AltModifier:
            self.source = QPointF(pos)
            self.notify("Source du tampon définie")
            self.app.canvas.update()
            return
        layer = self.paintable_layer()
        if layer is None:
            return
        if self.source is None:
            self.notify("Alt+clic pour définir la source du tampon")
            return
        self._layer = layer
        self._tx = self.doc.history.begin("Tampon de clonage")
        self._buffer = acquire_buffer(self.doc.size)
        if not self.aligned or self.source is not None:
            self._offset = QPointF(self.source.x() - pos.x(), self.source.y() - pos.y())
        self._last = None
        self._paint_to(pos)

    def move(self, pos, event) -> None:
        if self._buffer is not None:
            self._paint_to(pos)

    def _paint_to(self, pos: QPointF) -> None:
        if self._buffer is None or self._tx is None or self._layer is None:
            return
        pressure = max(0.05, min(1.0, getattr(self.app, "pressure", 1.0)))
        size = max(1, int(round(self.size * (0.4 + 0.6 * pressure))))
        stamp = self.app.stamp_cache.get(size, self.hardness, QColor(255, 255, 255))
        spacing = max(0.75, size * 0.15)
        points = [pos] if self._last is None else list(stamps_along(self._last, pos, spacing))
        half = size // 2
        source_image = self.doc.composite() if self.sample_all else self._layer.image
        rect = QRect()
        for point in points:
            source_x = int(round(point.x() + self._offset.x())) - half
            source_y = int(round(point.y() + self._offset.y())) - half
            patch = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
            patch.fill(Qt.transparent)
            painter = QPainter(patch)
            painter.drawImage(0, 0, source_image, source_x, source_y, size, size)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, stamp)
            painter.end()
            stamp_rect = self._buffer.stamp(patch, point)
            rect = stamp_rect if rect.isNull() else rect.united(stamp_rect)
        self._last = pos
        if not rect.isNull():
            self._tx.touch(self._layer, rect)
            self.app.canvas.update_doc_rect(rect)

    def release(self, pos, event) -> None:
        if self._buffer is None or self._tx is None:
            return
        image = self._buffer.image
        mask = self.doc.mask_for_image()
        if mask is not None:
            image = image.copy()
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, mask)
            painter.end()
        painter = QPainter(self._layer.image)
        if mask is None and self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setOpacity(self.opacity)
        painter.drawImage(0, 0, image)
        painter.end()
        self.doc.invalidate(self._buffer.dirty)
        self._tx.commit()
        self._buffer = None
        self._tx = None
        self._layer = None
        self._last = None
        self.app.canvas.update()

    def overlay(self):
        if self._buffer is not None and not self._buffer.dirty.isEmpty():
            return self._buffer.image, self.opacity, False
        return None

    def preview(self, painter) -> None:
        if self.source is None:
            return
        painter.save()
        pen = QPen(QColor("#f97316"), 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        size = max(8, self.size // 2)
        painter.drawLine(QPointF(self.source.x() - size, self.source.y()),
                         QPointF(self.source.x() + size, self.source.y()))
        painter.drawLine(QPointF(self.source.x(), self.source.y() - size),
                         QPointF(self.source.x(), self.source.y() + size))
        painter.restore()

    def cancel(self) -> None:
        if self._tx is not None:
            self._tx.cancel()
        self._buffer = None
        self._tx = None
        self._layer = None
        self._last = None
        self.app.canvas.update()
