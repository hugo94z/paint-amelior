from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..brush import StrokeBuffer, acquire_buffer, stamps_along
from .base import BaseTool


class BrushTool(BaseTool):
    id = "brush"
    label = "Pinceau"
    shortcut = "B"
    icon = "brush"
    erase = False

    def __init__(self, app):
        super().__init__(app)
        self.size = 24
        self.opacity = 1.0
        self.hardness = 0.85
        self.pressure_size = True
        self.spacing = 0.12
        self.scatter = 0.0
        self.tip = ""
        self._tip_cache: dict = {}
        self._layer = None
        self._tx = None
        self._buffer: StrokeBuffer | None = None
        self._last: QPointF | None = None
        self._anchor: QPointF | None = None

    def apply_preset(self, preset) -> None:
        self.size = preset.size
        self.hardness = preset.hardness
        self.opacity = preset.opacity
        self.spacing = preset.spacing
        self.pressure_size = preset.pressure
        self.scatter = preset.scatter
        self.tip = preset.tip
        self._tip_cache.clear()
        self.app.canvas.update()

    def _stamp(self, size: int):
        if self.tip:
            key = (self.tip, int(size), self.app.fg.rgba())
            stamp = self._tip_cache.get(key)
            if stamp is not None:
                return stamp
            source = QImage(self.tip)
            if not source.isNull():
                scaled = source.scaled(size, size, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
                stamp = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
                stamp.fill(Qt.transparent)
                painter = QPainter(stamp)
                painter.drawImage((size - scaled.width()) // 2,
                                  (size - scaled.height()) // 2, scaled)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                painter.fillRect(stamp.rect(), self._color())
                painter.end()
                if len(self._tip_cache) > 24:
                    self._tip_cache.clear()
                self._tip_cache[key] = stamp
                return stamp
        return self.app.stamp_cache.get(size, self.hardness, self._color())

    def cursor_size(self) -> int:
        return self.size

    def _color(self) -> QColor:
        return QColor(Qt.black) if self.erase else self.app.fg

    def press(self, pos, event) -> None:
        layer = self.paintable_layer()
        if layer is None:
            return
        self._layer = layer
        self._tx = self.doc.history.begin("Gomme" if self.erase else "Pinceau")
        self._buffer = acquire_buffer(self.doc.size)
        if (self._anchor is not None and event is not None
                and event.modifiers() & Qt.ShiftModifier):
            self._last = self._anchor
        else:
            self._last = None
        self._paint_to(pos)
        self.app.canvas.update()

    def move(self, pos, event) -> None:
        if self._buffer is None:
            return
        self._paint_to(pos)

    def _paint_to(self, pos: QPointF) -> None:
        if self._buffer is None or self._tx is None:
            return
        pressure = 1.0
        if self.pressure_size:
            pressure = max(0.05, min(1.0, getattr(self.app, "pressure", 1.0)))
        effective = max(1, int(round(self.size * (0.3 + 0.7 * pressure))))
        stamp = self._stamp(effective)
        spacing = max(0.75, effective * self.spacing)
        points = [pos] if self._last is None else list(stamps_along(self._last, pos, spacing))
        if self.scatter > 0 and points:
            import random

            spread = effective * self.scatter
            points = [QPointF(point.x() + random.uniform(-spread, spread),
                              point.y() + random.uniform(-spread, spread))
                      for point in points]
        rect = self._buffer.stamp_many(stamp, points)
        self._last = pos
        self._anchor = pos
        if not rect.isNull():
            self._tx.touch(self._layer, rect)
            self.app.canvas.update_doc_rect(rect)

    def release(self, pos, event) -> None:
        if self._buffer is None or self._tx is None:
            return
        layer = self._layer
        image = self._buffer.image
        mask = self.doc.mask_for_image()
        if mask is not None:
            image = image.copy()
            mask_painter = QPainter(image)
            mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            mask_painter.drawImage(0, 0, mask)
            mask_painter.end()
        painter = QPainter(layer.image)
        if mask is None and self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setOpacity(self.opacity)
        if self.erase:
            painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        elif layer.lock_alpha:
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        painter.drawImage(0, 0, image)
        painter.end()
        self.doc.invalidate(self._buffer.dirty)
        self._tx.commit()
        self._cleanup()

    def _cleanup(self) -> None:
        self._buffer = None
        self._tx = None
        self._layer = None
        self._last = None
        self.app.canvas.update()

    def cancel(self) -> None:
        if self._tx is not None:
            self._tx.cancel()
        self._cleanup()

    def overlay(self):
        if self._buffer is not None and not self._buffer.dirty.isEmpty():
            return self._buffer.image, self.opacity, self.erase
        return None


class EraserTool(BrushTool):
    id = "eraser"
    label = "Gomme"
    shortcut = "E"
    icon = "eraser"
    erase = True

    def __init__(self, app):
        super().__init__(app)
        self.size = 40
        self.hardness = 0.9
