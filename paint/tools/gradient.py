from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient

from .base import BaseTool


class GradientTool(BaseTool):
    snaps = True
    id = "gradient"
    label = "Dégradé"
    shortcut = "D"
    icon = "gradient"

    def __init__(self, app):
        super().__init__(app)
        self.kind = "linear"
        self.opacity = 1.0
        self._start: QPointF | None = None
        self._end: QPointF | None = None

    def press(self, pos, event) -> None:
        self._start = pos
        self._end = pos
        self.app.canvas.update()

    def move(self, pos, event) -> None:
        if self._start is None:
            return
        self._end = pos
        self.app.canvas.update()

    def release(self, pos, event) -> None:
        if self._start is None:
            return
        self._end = pos
        layer = self.paintable_layer()
        if layer is None:
            self._reset()
            return
        bounds = QRectF(self._start, self._end).normalized().toAlignedRect()
        bounds = bounds.adjusted(-2, -2, 2, 2).intersected(self.doc.rect())
        if bounds.isEmpty():
            self._reset()
            return
        tx = self.doc.history.begin("Dégradé")
        tx.touch(layer, bounds)
        painter = QPainter(layer.image)
        painter.setOpacity(self.opacity)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._gradient())
        painter.drawRect(bounds)
        painter.end()
        self.doc.invalidate(bounds)
        tx.commit()
        self._reset()

    def _gradient(self):
        if self.kind == "radial":
            center = self._start
            radius = ((self._end.x() - center.x()) ** 2 + (self._end.y() - center.y()) ** 2) ** 0.5
            gradient = QRadialGradient(center, max(1.0, radius))
        else:
            gradient = QLinearGradient(self._start, self._end)
        gradient.setColorAt(0.0, self.app.fg)
        gradient.setColorAt(1.0, self.app.bg)
        return gradient

    def preview(self, painter) -> None:
        if self._start is None or self._end is None:
            return
        bounds = QRectF(self._start, self._end).normalized().toAlignedRect()
        painter.setOpacity(self.opacity)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._gradient())
        painter.drawRect(bounds)

    def cancel(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._start = None
        self._end = None
        self.app.canvas.update()
