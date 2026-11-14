from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPainter

from ..brush import StrokeBuffer, stamps_along
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
        self._layer = None
        self._tx = None
        self._buffer: StrokeBuffer | None = None
        self._last: QPointF | None = None

    def cursor_size(self) -> int:
        return self.size

    def _color(self) -> QColor:
        return QColor(Qt.black) if self.erase else self.app.fg

    def press(self, pos, event) -> None:
        layer = self.doc.active_layer()
        if layer is None:
            return
        self._layer = layer
        self._tx = self.doc.history.begin("Gomme" if self.erase else "Pinceau")
        self._buffer = StrokeBuffer(self.doc.size)
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
        stamp = self.app.stamp_cache.get(self.size, self.hardness, self._color())
        spacing = max(0.75, self.size * 0.12)
        points = [pos] if self._last is None else list(stamps_along(self._last, pos, spacing))
        rect = QRect()
        for point in points:
            r = self._buffer.stamp(stamp, point)
            rect = r if rect.isNull() else rect.united(r)
        self._last = pos
        if not rect.isNull():
            self._tx.touch(self._layer, rect)
            self.app.canvas.update_doc_rect(rect)

    def release(self, pos, event) -> None:
        if self._buffer is None or self._tx is None:
            return
        layer = self._layer
        painter = QPainter(layer.image)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setOpacity(self.opacity)
        if self.erase:
            painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        painter.drawImage(0, 0, self._buffer.image)
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
