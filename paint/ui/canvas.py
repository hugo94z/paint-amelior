from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSizeF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class Canvas(QWidget):
    MIN_ZOOM = 0.05
    MAX_ZOOM = 32.0

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.doc = None
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self._auto_fit = True
        self._space = False
        self._panning = False
        self._pan_origin = QPointF()
        self._pan_start = QPointF()
        self._mouse = QPointF(-1000, -1000)
        self._cursor_rect = QRect()
        self._ants_phase = 0
        self._checker = self._make_checker()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMinimumSize(240, 180)
        self._ants = QTimer(self)
        self._ants.setInterval(120)
        self._ants.timeout.connect(self._tick_ants)
        self._ants.start()

    @staticmethod
    def _make_checker() -> QPixmap:
        pixmap = QPixmap(48, 48)
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 48, 48, QColor("#8d9199"))
        painter.fillRect(0, 0, 24, 24, QColor("#b9bdc4"))
        painter.fillRect(24, 24, 24, 24, QColor("#b9bdc4"))
        painter.end()
        return pixmap

    def set_doc(self, doc) -> None:
        if self.doc is not None:
            try:
                self.doc.dirty.disconnect(self.update_doc_rect)
                self.doc.size_changed.disconnect(self.fit)
                self.doc.selection_changed.disconnect(self.update)
            except (RuntimeError, TypeError):
                pass
        self.doc = doc
        if doc is not None:
            doc.dirty.connect(self.update_doc_rect)
            doc.size_changed.connect(self.fit)
            doc.selection_changed.connect(self.update)
        self._auto_fit = True
        self.fit()

    def _target_rect(self) -> QRectF:
        if self.doc is None:
            return QRectF()
        return QRectF(self.pan, QSizeF(self.doc.size.width() * self.zoom,
                                       self.doc.size.height() * self.zoom))

    def doc_to_view(self, point: QPointF) -> QPointF:
        return QPointF(self.pan.x() + point.x() * self.zoom, self.pan.y() + point.y() * self.zoom)

    def view_to_doc(self, point: QPointF) -> QPointF:
        return QPointF((point.x() - self.pan.x()) / self.zoom,
                       (point.y() - self.pan.y()) / self.zoom)

    def visible_doc_rect(self) -> QRect:
        if self.doc is None:
            return QRect()
        top_left = self.view_to_doc(QPointF(0, 0))
        bottom_right = self.view_to_doc(QPointF(self.width(), self.height()))
        rect = QRectF(top_left, bottom_right).normalized().toAlignedRect()
        return rect.intersected(self.doc.rect())

    def update_doc_rect(self, rect: QRect) -> None:
        if self.doc is None or rect is None or rect.isEmpty():
            return
        top_left = self.doc_to_view(QPointF(rect.left(), rect.top()))
        bottom_right = self.doc_to_view(QPointF(rect.right() + 1, rect.bottom() + 1))
        widget_rect = QRectF(top_left, bottom_right).toAlignedRect().adjusted(-2, -2, 2, 2)
        self.update(widget_rect)

    def fit(self) -> None:
        if self.doc is None:
            return
        available = self.rect().adjusted(32, 32, -32, -32)
        if available.width() < 10 or available.height() < 10:
            return
        sx = available.width() / self.doc.size.width()
        sy = available.height() / self.doc.size.height()
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, min(sx, sy)))
        self.pan = QPointF(
            (self.width() - self.doc.size.width() * self.zoom) / 2,
            (self.height() - self.doc.size.height() * self.zoom) / 2,
        )
        self._auto_fit = True
        self.app.update_zoom_label()
        self.update()

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        if self.doc is None:
            return
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        if anchor is None:
            anchor = QPointF(self.rect().center())
        before = self.view_to_doc(anchor)
        self.zoom = zoom
        after = self.doc_to_view(before)
        self.pan = QPointF(self.pan.x() + anchor.x() - after.x(),
                           self.pan.y() + anchor.y() - after.y())
        self._auto_fit = False
        self.app.update_zoom_label()
        self.update()

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self.zoom * factor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_fit:
            self.fit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#15171a"))
        doc = self.doc
        if doc is None:
            return
        target = self._target_rect()
        if not target.intersects(QRectF(self.rect()).adjusted(-4, -4, 4, 4)):
            return
        painter.fillRect(target, QBrush(self._checker))
        source = self.visible_doc_rect()
        if source.isEmpty():
            self._paint_frame(painter, target)
            return
        dst = QRectF(self.doc_to_view(QPointF(source.left(), source.top())),
                     QSizeF(source.width() * self.zoom, source.height() * self.zoom))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        painter.drawImage(dst, doc.composite(), QRectF(source))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.save()
        painter.setClipRect(target)
        self._paint_overlay(painter, dst, source)
        self._paint_floating(painter)
        painter.save()
        painter.translate(self.pan)
        painter.scale(self.zoom, self.zoom)
        self.app.tool.preview(painter)
        painter.restore()
        self._paint_ants(painter, target)
        painter.restore()
        self._paint_frame(painter, target)
        self._paint_cursor(painter)

    def _paint_frame(self, painter: QPainter, target: QRectF) -> None:
        painter.setPen(QPen(QColor("#3a3f46"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(target.adjusted(-0.5, -0.5, 0.5, 0.5))

    def _paint_overlay(self, painter: QPainter, dst: QRectF, source: QRect) -> None:
        overlay = self.app.tool.overlay()
        if overlay is None:
            return
        image, opacity, erase = overlay
        if erase:
            temp = self.doc.composite().copy(source)
            inner = QPainter(temp)
            inner.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            inner.setOpacity(opacity)
            inner.drawImage(QRectF(0, 0, source.width(), source.height()), image, QRectF(source))
            inner.end()
            painter.drawImage(dst, temp)
        else:
            painter.setOpacity(opacity)
            painter.drawImage(dst, image, QRectF(source))
            painter.setOpacity(1.0)

    def _paint_floating(self, painter: QPainter) -> None:
        doc = self.doc
        if doc is None or doc.floating is None:
            return
        top_left = self.doc_to_view(QPointF(doc.floating_pos))
        size = doc.floating.size()
        dst = QRectF(top_left, QSizeF(size.width() * self.zoom, size.height() * self.zoom))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        painter.drawImage(dst, doc.floating)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

    def _paint_ants(self, painter: QPainter, target: QRectF) -> None:
        doc = self.doc
        if doc is None or not doc.has_selection() or doc.selection_path is None:
            return
        painter.save()
        painter.setClipRect(target)
        painter.translate(self.pan)
        painter.scale(self.zoom, self.zoom)
        for color, offset in ((QColor(0, 0, 0), self._ants_phase),
                              (QColor(255, 255, 255), self._ants_phase + 4)):
            pen = QPen(color, 0, Qt.DashLine)
            pen.setCosmetic(True)
            pen.setDashPattern([5, 5])
            pen.setDashOffset(offset)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(doc.selection_path)
        painter.restore()

    def _paint_cursor(self, painter: QPainter) -> None:
        size = self.app.tool.cursor_size()
        if size <= 0 or self._panning or self._space:
            return
        if not self.rect().contains(self._mouse.toPoint()):
            return
        radius = max(1.5, size * self.zoom / 2)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(0, 0, 0, 190), 1))
        painter.drawEllipse(self._mouse, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 210), 1))
        painter.drawEllipse(self._mouse, radius + 1, radius + 1)

    def _tick_ants(self) -> None:
        if self.doc is None or not self.doc.has_selection():
            return
        self._ants_phase = (self._ants_phase + 1) % 10
        self.update()

    def _cursor_for_tool(self):
        if self._space:
            return Qt.OpenHandCursor
        return self.app.tool.cursor()

    def _refresh_cursor_ring(self) -> None:
        size = self.app.tool.cursor_size()
        if size <= 0:
            if not self._cursor_rect.isNull():
                self.update(self._cursor_rect)
                self._cursor_rect = QRect()
            return
        radius = int(max(2.0, size * self.zoom / 2) + 3)
        new_rect = QRect(
            int(self._mouse.x()) - radius,
            int(self._mouse.y()) - radius,
            radius * 2 + 2,
            radius * 2 + 2,
        )
        union = self._cursor_rect.united(new_rect)
        self._cursor_rect = new_rect
        self.update(union)

    def roll_size(self) -> None:
        self._cursor_rect = QRect()

    def mousePressEvent(self, event) -> None:
        self.setFocus()
        if event.button() == Qt.MiddleButton or (self._space and event.button() == Qt.LeftButton):
            self._panning = True
            self._pan_start = event.position()
            self._pan_origin = QPointF(self.pan)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.LeftButton or self.doc is None:
            return
        pos = self.view_to_doc(event.position())
        if event.modifiers() & Qt.AltModifier:
            self.app.pick_color(pos)
            return
        self.app.tool.press(pos, event)

    def mouseMoveEvent(self, event) -> None:
        self._mouse = event.position()
        if self._panning:
            delta = event.position() - self._pan_start
            self.pan = QPointF(self._pan_origin.x() + delta.x(), self._pan_origin.y() + delta.y())
            self._auto_fit = False
            self.update()
            return
        tool = self.app.tool
        pos = self.view_to_doc(event.position())
        if event.buttons() & Qt.LeftButton:
            tool.move(pos, event)
        self.app.update_coords(pos)
        self._refresh_cursor_ring()

    def mouseReleaseEvent(self, event) -> None:
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning = False
            self.setCursor(self._cursor_for_tool())
            return
        if event.button() == Qt.LeftButton and self.doc is not None:
            self.app.tool.release(self.view_to_doc(event.position()), event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.doc is not None:
            self.app.tool.double_click(self.view_to_doc(event.position()), event)

    def wheelEvent(self, event) -> None:
        if self.doc is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.18 if delta > 0 else 1 / 1.18
            self.set_zoom(self.zoom * factor, event.position())
        else:
            step = delta / 120.0 * 56.0
            if event.modifiers() & Qt.ShiftModifier:
                self.pan = QPointF(self.pan.x() + step, self.pan.y())
            else:
                self.pan = QPointF(self.pan.x(), self.pan.y() + step)
            self._auto_fit = False
            self.update()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if self.app.tool.key_press(event):
            return
        if event.key() == Qt.Key_Escape:
            self.app.tool.cancel()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = False
            self.setCursor(self._cursor_for_tool())
            return
        super().keyReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse = QPointF(-1000, -1000)
        self.app.update_coords(QPointF(-1, -1))
        self.roll_size()
        self.update()
        super().leaveEvent(event)
