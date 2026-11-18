from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .base import BaseTool


class ShapeTool(BaseTool):
    snaps = True
    icon = "rect"

    def __init__(self, app, kind: str):
        super().__init__(app)
        self.kind = kind
        self.id = kind
        self.label = {
            "line": "Ligne",
            "rect": "Rectangle",
            "ellipse": "Ellipse",
            "roundrect": "Rectangle arrondi",
        }.get(kind, "Forme")
        self.shortcut = {"line": "L", "rect": "R", "ellipse": "O", "roundrect": "U"}.get(kind, "")
        self.icon = kind
        self.width = 4
        self.filled = False
        self.radius = 18
        self.opacity = 1.0
        self._start: QPointF | None = None
        self._end: QPointF | None = None
        self._tx = None
        self._layer = None

    def cursor_size(self) -> int:
        return max(8, self.width * 2)

    def _path(self) -> QPainterPath:
        path = QPainterPath()
        if self._start is None or self._end is None:
            return path
        rect = QRectF(self._start, self._end).normalized()
        if self.kind == "line":
            path.moveTo(self._start)
            path.lineTo(self._end)
        elif self.kind == "rect":
            path.addRect(rect)
        elif self.kind == "ellipse":
            path.addEllipse(rect)
        else:
            radius = min(self.radius, rect.width() / 2, rect.height() / 2)
            path.addRoundedRect(rect, radius, radius)
        return path

    def press(self, pos, event) -> None:
        self._start = pos
        self._end = pos
        self._layer = self.paintable_layer()
        if self._layer is None:
            self._start = None
            return
        self._tx = self.doc.history.begin(self.label)
        self.app.canvas.update()

    def move(self, pos, event) -> None:
        if self._start is None:
            return
        if event.modifiers() & Qt.ShiftModifier:
            if self.kind == "line":
                import math

                dx = pos.x() - self._start.x()
                dy = pos.y() - self._start.y()
                angle = math.atan2(dy, dx)
                step = math.pi / 4
                angle = round(angle / step) * step
                length = (dx * dx + dy * dy) ** 0.5
                self._end = QPointF(
                    self._start.x() + math.cos(angle) * length,
                    self._start.y() + math.sin(angle) * length,
                )
            else:
                dx = pos.x() - self._start.x()
                dy = pos.y() - self._start.y()
                size = max(abs(dx), abs(dy))
                dx = size if dx >= 0 else -size
                dy = size if dy >= 0 else -size
                self._end = QPointF(self._start.x() + dx, self._start.y() + dy)
        else:
            self._end = pos
        self.app.canvas.update()

    def release(self, pos, event) -> None:
        if self._start is None or self._tx is None:
            return
        self._end = pos
        path = self._path()
        if path.isEmpty():
            self.cancel()
            return
        bounds = path.boundingRect().adjusted(-self.width - 2, -self.width - 2,
                                              self.width + 2, self.width + 2)
        self._tx.touch(self._layer, bounds.toAlignedRect())
        painter = QPainter(self._layer.image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self.opacity)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        pen = QPen(self.app.fg, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(self.app.bg if self.filled else Qt.NoBrush)
        painter.drawPath(path)
        painter.end()
        self.doc.invalidate(bounds.toAlignedRect())
        self._tx.commit()
        self._reset()

    def preview(self, painter) -> None:
        if self._start is None:
            return
        path = self._path()
        if path.isEmpty():
            return
        painter.setOpacity(self.opacity)
        pen = QPen(self.app.fg, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(self.app.bg if self.filled else Qt.NoBrush)
        painter.drawPath(path)

    def cancel(self) -> None:
        if self._tx is not None:
            self._tx.cancel()
        self._reset()
        self.app.canvas.update()

    def _reset(self) -> None:
        self._start = None
        self._end = None
        self._tx = None
        self._layer = None
        self.app.canvas.update()


class PolygonTool(BaseTool):
    snaps = True
    id = "polygon"
    label = "Polygone"
    shortcut = "Y"
    icon = "polygon"

    def __init__(self, app):
        super().__init__(app)
        self.width = 3
        self.filled = True
        self.opacity = 1.0
        self._points: list[QPointF] = []
        self._cursor: QPointF | None = None

    def cursor_size(self) -> int:
        return max(8, self.width * 2)

    def press(self, pos, event) -> None:
        if not self._points:
            self.app.canvas.update()
        self._points.append(pos)
        self._cursor = pos
        self.app.canvas.update()

    def move(self, pos, event) -> None:
        if self._points:
            self._cursor = pos
            self.app.canvas.update()

    def double_click(self, pos, event) -> None:
        self.release(pos, event)

    def key_press(self, event) -> bool:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.release(self._points[-1] if self._points else QPointF(), event)
            return True
        if event.key() == Qt.Key_Escape:
            self.cancel()
            return True
        return False

    def release(self, pos, event) -> None:
        if len(self._points) < 3:
            self.cancel()
            return
        layer = self.paintable_layer()
        if layer is None:
            self._points = []
            self._cursor = None
            self.app.canvas.update()
            return
        path = QPainterPath()
        path.moveTo(self._points[0])
        for point in self._points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        bounds = path.boundingRect().adjusted(-self.width - 2, -self.width - 2,
                                              self.width + 2, self.width + 2)
        tx = self.doc.history.begin("Polygone")
        tx.touch(layer, bounds.toAlignedRect())
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self.opacity)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setPen(QPen(self.app.fg, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(self.app.bg if self.filled else Qt.NoBrush)
        painter.drawPath(path)
        painter.end()
        self.doc.invalidate(bounds.toAlignedRect())
        tx.commit()
        self._points = []
        self._cursor = None
        self.app.canvas.update()

    def preview(self, painter) -> None:
        if len(self._points) < 2:
            return
        path = QPainterPath()
        path.moveTo(self._points[0])
        for point in self._points[1:]:
            path.lineTo(point)
        if self._cursor is not None:
            path.lineTo(self._cursor)
        painter.setPen(QPen(self.app.fg, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def cancel(self) -> None:
        self._points = []
        self._cursor = None
        self.app.canvas.update()

    def deactivate(self) -> None:
        self.cancel()
