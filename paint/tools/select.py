from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPolygon, QRegion

from .base import BaseTool


class SelectionTool(BaseTool):
    snaps = True
    id = "select"
    label = "Sélection"
    shortcut = "M"
    icon = "select"

    def __init__(self, app):
        super().__init__(app)
        self.mode = "rect"
        self.selection_mode = "replace"
        self.feather = 0
        self._start: QPointF | None = None
        self._cur: QPointF | None = None
        self._points: list[QPointF] = []
        self._drawing = False
        self._moving = False
        self._pending_lift: QPointF | None = None
        self._tx = None
        self._drag_origin: QPointF | None = None
        self._float_origin = QPoint()
        self._sel_region: QRegion | None = None
        self._sel_path: QPainterPath | None = None

    def cursor(self):
        return Qt.CrossCursor

    def press(self, pos, event) -> None:
        doc = self.doc
        if doc.floating is not None and self._floating_rect().contains(pos.toPoint()):
            self._begin_move(pos)
            return
        if doc.floating is not None:
            self.drop_floating()
        if doc.has_selection() and doc.selection.contains(pos.toPoint()):
            self._pending_lift = pos
            return
        self._drawing = True
        self._start = pos
        self._cur = pos
        self._points = [pos]
        self.app.canvas.update()

    def move(self, pos, event) -> None:
        if self._pending_lift is not None:
            delta = pos - self._pending_lift
            if abs(delta.x()) + abs(delta.y()) < 3:
                return
            start = self._pending_lift
            self._pending_lift = None
            self._lift(start)
        if self._moving and self.doc.floating is not None and self._drag_origin is not None:
            delta = pos - self._drag_origin
            new_pos = QPoint(
                int(round(self._float_origin.x() + delta.x())),
                int(round(self._float_origin.y() + delta.y())),
            )
            old = self._floating_rect()
            self.doc.floating_pos = new_pos
            new = self._floating_rect()
            self.app.canvas.update_doc_rect(old.united(new))
        elif self._drawing:
            self._cur = pos
            if self.mode == "lasso":
                if not self._points or (
                    abs(pos.x() - self._points[-1].x()) + abs(pos.y() - self._points[-1].y()) > 2
                ):
                    self._points.append(pos)
            self.app.canvas.update()

    def release(self, pos, event) -> None:
        if self._pending_lift is not None:
            self._pending_lift = None
            return
        if self._moving:
            self._moving = False
            self.drop_floating()
            return
        if not self._drawing:
            return
        self._drawing = False
        start, cur = self._start, pos
        self._start = None
        self._cur = None
        if start is None:
            self.app.canvas.update()
            return
        if self.mode == "rect":
            rect = QRect(start.toPoint(), cur.toPoint()).normalized()
            if rect.width() < 2 or rect.height() < 2:
                self.doc.clear_selection()
                self.app.canvas.update()
                return
            path = QPainterPath()
            path.addRect(rect)
            self._apply_selection(QRegion(rect), path)
            self.notify(f"Sélection {rect.width()} × {rect.height()}")
        else:
            points = self._points[:]
            if len(points) < 3:
                self.doc.clear_selection()
                self.app.canvas.update()
                return
            polygon = QPolygon([p.toPoint() for p in points])
            path = QPainterPath()
            path.addPolygon(polygon)
            path.closeSubpath()
            self._apply_selection(QRegion(polygon), path)
            self.notify("Sélection au lasso")
        self._points = []
        self.app.canvas.update()

    def _apply_selection(self, region: QRegion, path: QPainterPath) -> None:
        doc = self.doc
        if self.selection_mode == "replace" or not doc.has_selection():
            doc.set_selection(region, path, feather=self.feather)
            return
        from ..utils import region_mask

        array = region_mask(region, doc.size.width(), doc.size.height())
        if array is not None:
            doc.combine_selection(array, self.selection_mode, self.feather)

    def _floating_rect(self) -> QRect:
        if self.doc.floating is None:
            return QRect()
        return QRect(self.doc.floating_pos, self.doc.floating.size())

    def _begin_move(self, pos: QPointF) -> None:
        self._moving = True
        self._drag_origin = pos
        self._float_origin = QPoint(self.doc.floating_pos)
        self._sel_region = self.doc.selection
        self._sel_path = self.doc.selection_path

    def _lift(self, pos: QPointF) -> None:
        doc = self.doc
        layer = doc.active_layer()
        if layer is None or not doc.has_selection():
            return
        if layer.locked:
            self.notify("Calque verrouillé")
            return
        bounds = doc.selection.boundingRect().intersected(doc.rect())
        if bounds.isEmpty():
            return
        self._sel_region = doc.selection
        self._sel_path = doc.selection_path
        self._tx = doc.history.begin("Déplacer la sélection")
        self._tx.touch(layer, bounds)
        image = layer.image.copy(bounds)
        mask = doc.mask_for_image()
        if mask is not None:
            local_mask = mask.copy(bounds)
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, local_mask)
            painter.end()
            painter = QPainter(layer.image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            painter.drawImage(bounds.topLeft(), local_mask)
            painter.end()
        else:
            painter = QPainter(layer.image)
            painter.setClipRegion(doc.selection)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(bounds, Qt.transparent)
            painter.end()
        doc.floating = image
        doc.floating_pos = bounds.topLeft()
        doc.invalidate(bounds)
        self._begin_move(pos)
        self.notify("Glissez pour déplacer la sélection")

    def drop_floating(self) -> None:
        doc = self.doc
        if doc.floating is None:
            return
        layer = doc.active_layer()
        rect = self._floating_rect()
        if self._tx is None and layer is not None:
            self._tx = doc.history.begin("Coller")
            self._tx.touch(layer, rect)
        if layer is not None:
            painter = QPainter(layer.image)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(rect.topLeft(), doc.floating)
            painter.end()
            doc.invalidate(rect)
        if self._tx is not None:
            self._tx.commit()
            self._tx = None
        delta = rect.topLeft() - self._float_origin
        region = self._sel_region or QRegion(rect)
        path = self._sel_path
        doc.floating = None
        if path is not None:
            path = path.translated(delta.x(), delta.y())
        doc.set_selection(region.translated(delta.x(), delta.y()), path)
        self._moving = False
        self._drag_origin = None
        self.app.canvas.update()

    def preview(self, painter) -> None:
        if self._drawing and self._start is not None and self._cur is not None:
            pen = QPen(Qt.white, 0, Qt.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            if self.mode == "rect":
                painter.drawRect(QRectF(self._start, self._cur).normalized())
            elif len(self._points) > 1:
                path = QPainterPath(self._points[0])
                for point in self._points[1:]:
                    path.lineTo(point)
                painter.drawPath(path)

    def cancel(self) -> None:
        self._drawing = False
        self._pending_lift = None
        self._start = None
        self._cur = None
        self._points = []
        self.app.canvas.update()

    def deactivate(self) -> None:
        if self.doc.floating is not None:
            self.drop_floating()
        self.cancel()
