from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSizeF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QScrollBar, QWidget

from .rulers import Ruler


class Canvas(QWidget):
    MIN_ZOOM = 0.05
    MAX_ZOOM = 32.0
    MARGIN = 32

    view_changed = Signal()
    cursor_changed = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.host = None
        self.doc = None
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False
        self._auto_fit = True
        self._space = False
        self._panning = False
        self._pan_origin = QPointF()
        self._pan_start = QPointF()
        self._mouse = QPointF(-1000, -1000)
        self._cursor_rect = QRect()
        self._ants_phase = 0
        self._guide_preview = None
        self._guide_drag = None
        self._checker = self._make_checker()
        self.setMouseTracking(True)
        self.setTabletTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAcceptDrops(True)
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

    def _background(self) -> QColor:
        return QColor("#e4e6ea") if getattr(self.app, "light_theme", False) else QColor("#15171a")

    def refresh_theme(self) -> None:
        self._checker = self._make_checker()
        self.update()

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

    def content_size(self) -> QSizeF:
        if self.doc is None:
            return QSizeF()
        width = self.doc.size.width()
        height = self.doc.size.height()
        if self.rotation % 180:
            width, height = height, width
        return QSizeF(width, height)

    def transform(self):
        from PySide6.QtGui import QTransform

        transform = QTransform()
        if self.doc is None:
            return transform
        content = self.content_size()
        transform.translate(
            self.pan.x() + content.width() * self.zoom / 2.0,
            self.pan.y() + content.height() * self.zoom / 2.0,
        )
        transform.rotate(self.rotation % 360)
        transform.scale(
            self.zoom * (-1.0 if self.flip_h else 1.0),
            self.zoom * (-1.0 if self.flip_v else 1.0),
        )
        transform.translate(-self.doc.size.width() / 2.0, -self.doc.size.height() / 2.0)
        return transform

    def _target_rect(self) -> QRectF:
        if self.doc is None:
            return QRectF()
        content = self.content_size()
        return QRectF(self.pan, QSizeF(content.width() * self.zoom,
                                       content.height() * self.zoom))

    def doc_to_view(self, point: QPointF) -> QPointF:
        return self.transform().map(QPointF(point))

    def view_to_doc(self, point: QPointF) -> QPointF:
        inverted, ok = self.transform().inverted()
        if not ok:
            return QPointF(point)
        return inverted.map(QPointF(point))

    def visible_doc_rect(self) -> QRect:
        if self.doc is None:
            return QRect()
        corners = [
            self.view_to_doc(QPointF(0, 0)),
            self.view_to_doc(QPointF(self.width(), 0)),
            self.view_to_doc(QPointF(0, self.height())),
            self.view_to_doc(QPointF(self.width(), self.height())),
        ]
        xs = [point.x() for point in corners]
        ys = [point.y() for point in corners]
        rect = QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys))).toAlignedRect()
        return rect.intersected(self.doc.rect())

    def update_doc_rect(self, rect: QRect) -> None:
        if self.doc is None or rect is None or rect.isEmpty():
            return
        corners = [
            self.doc_to_view(QPointF(rect.left(), rect.top())),
            self.doc_to_view(QPointF(rect.right() + 1, rect.top())),
            self.doc_to_view(QPointF(rect.left(), rect.bottom() + 1)),
            self.doc_to_view(QPointF(rect.right() + 1, rect.bottom() + 1)),
        ]
        xs = [point.x() for point in corners]
        ys = [point.y() for point in corners]
        widget_rect = QRectF(QPointF(min(xs), min(ys)),
                             QPointF(max(xs), max(ys))).toAlignedRect()
        self.update(widget_rect.adjusted(-2, -2, 2, 2))

    def fit(self) -> None:
        if self.doc is None:
            return
        available = self.rect().adjusted(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)
        if available.width() < 10 or available.height() < 10:
            return
        content = self.content_size()
        sx = available.width() / max(1, content.width())
        sy = available.height() / max(1, content.height())
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, min(sx, sy)))
        self.pan = QPointF(
            (self.width() - content.width() * self.zoom) / 2,
            (self.height() - content.height() * self.zoom) / 2,
        )
        self._auto_fit = True
        self.app.update_zoom_label()
        self._notify_view()
        self.update()

    def center_on(self, point: QPointF) -> None:
        viewport = QPointF(self.rect().center())
        current = self.doc_to_view(point)
        self.pan = QPointF(self.pan.x() + viewport.x() - current.x(),
                           self.pan.y() + viewport.y() - current.y())
        self._auto_fit = False
        self._notify_view()
        self.update()

    def rotate_view(self, angle: int) -> None:
        if self.doc is None:
            return
        center = self.view_to_doc(QPointF(self.rect().center()))
        self.rotation = (self.rotation + int(angle)) % 360
        self.center_on(center)
        self.update()

    def flip_view(self, horizontal: bool = True) -> None:
        if self.doc is None:
            return
        center = self.view_to_doc(QPointF(self.rect().center()))
        if horizontal:
            self.flip_h = not self.flip_h
        else:
            self.flip_v = not self.flip_v
        self.center_on(center)
        self.update()

    def _notify_view(self) -> None:
        if self.host is not None:
            self.host.sync_bars()
        self.view_changed.emit()

    def set_guide_preview(self, orientation, value: float) -> None:
        self._guide_preview = None if orientation is None else (orientation, float(value))
        self.update()

    def _guide_at(self, position: QPointF):
        doc = self.doc
        if doc is None or not doc.guides_visible or self.rotation % 360:
            return None
        tolerance = 5.0
        for index, value in enumerate(doc.guides_h):
            y = self.doc_to_view(QPointF(0, value)).y()
            if abs(position.y() - y) <= tolerance:
                return ("h", index)
        for index, value in enumerate(doc.guides_v):
            x = self.doc_to_view(QPointF(value, 0)).x()
            if abs(position.x() - x) <= tolerance:
                return ("v", index)
        return None

    def set_scroll_offset(self, x: int, y: int) -> None:
        self.pan = QPointF(self.MARGIN - x, self.MARGIN - y)
        self._auto_fit = False
        self.update()

    def restore_view(self, zoom: float, pan: QPointF | None) -> None:
        if zoom is None or pan is None:
            self.fit()
            return
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(zoom)))
        self.pan = QPointF(pan)
        self._auto_fit = False
        self.app.update_zoom_label()
        self._notify_view()
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
        self._notify_view()
        self.update()

    def zoom_by(self, factor: float) -> None:
        self.set_zoom(self.zoom * factor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._auto_fit:
            self.fit()
        else:
            self._notify_view()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background())
        doc = self.doc
        if doc is None:
            return
        target = self._target_rect()
        if not target.intersects(QRectF(self.rect()).adjusted(-4, -4, 4, 4)):
            return
        painter.fillRect(target, QBrush(self._checker))
        source = self.visible_doc_rect()
        if source.isEmpty():
            self._paint_frame(painter)
            return
        painter.save()
        painter.setClipRect(target)
        painter.setTransform(self.transform())
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        painter.drawImage(QRectF(source),
                          doc.preview_image if doc.preview_image is not None
                          else doc.composite(), QRectF(source))
        if doc.selection_tint is not None:
            painter.drawImage(QRectF(source), doc.selection_tint, QRectF(source))
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._paint_overlay(painter, source)
        self._paint_floating(painter)
        self.app.tool.preview(painter)
        self._paint_ants(painter)
        self._paint_guides(painter)
        self._paint_grid(painter)
        painter.restore()
        self._paint_frame(painter)
        self._paint_cursor(painter)

    def _paint_guides(self, painter: QPainter) -> None:
        doc = self.doc
        if doc is None or not doc.guides_visible:
            return
        pen = QPen(QColor("#38bdf8"), 1, Qt.DashLine)
        pen.setCosmetic(True)
        pen.setDashPattern([4, 4])
        painter.save()
        painter.setPen(pen)
        for value in doc.guides_h:
            painter.drawLine(QPointF(0, value), QPointF(doc.size.width(), value))
        for value in doc.guides_v:
            painter.drawLine(QPointF(value, 0), QPointF(value, doc.size.height()))
        preview = self._guide_preview
        if preview is not None:
            orientation, value = preview
            if orientation == Qt.Horizontal:
                painter.drawLine(QPointF(0, value), QPointF(doc.size.width(), value))
            else:
                painter.drawLine(QPointF(value, 0), QPointF(value, doc.size.height()))
        painter.restore()

    def _paint_grid(self, painter: QPainter) -> None:
        if not getattr(self.app, "show_grid", False) or self.doc is None:
            return
        spacing = float(self.app.grid_size)
        if spacing * self.zoom < 5:
            return
        doc = self.doc
        color = QColor(0, 0, 0, 40) if getattr(self.app, "light_theme", False) else QColor(255, 255, 255, 42)
        pen = QPen(color, 1)
        pen.setCosmetic(True)
        painter.save()
        painter.setPen(pen)
        painter.setClipRect(QRectF(doc.rect()).adjusted(-1, -1, 1, 1))
        limit = 400
        x = spacing
        count = 0
        while x < doc.size.width() and count < limit:
            painter.drawLine(QPointF(x, 0), QPointF(x, doc.size.height()))
            x += spacing
            count += 1
        y = spacing
        count = 0
        while y < doc.size.height() and count < limit:
            painter.drawLine(QPointF(0, y), QPointF(doc.size.width(), y))
            y += spacing
            count += 1
        painter.restore()

    def _paint_frame(self, painter: QPainter) -> None:
        from PySide6.QtGui import QPolygonF

        doc = self.doc
        if doc is None:
            return
        corners = [
            self.doc_to_view(QPointF(0, 0)),
            self.doc_to_view(QPointF(doc.size.width(), 0)),
            self.doc_to_view(QPointF(doc.size.width(), doc.size.height())),
            self.doc_to_view(QPointF(0, doc.size.height())),
        ]
        painter.save()
        painter.setPen(QPen(QColor("#3a3f46"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(QPolygonF(corners))
        painter.restore()

    def _paint_overlay(self, painter: QPainter, source: QRect) -> None:
        overlay = self.app.tool.overlay()
        if overlay is None:
            return
        image, opacity, erase = overlay
        if erase:
            temp = self.doc.composite().copy(source)
            inner = QPainter(temp)
            inner.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            inner.setOpacity(opacity)
            inner.drawImage(QRectF(0, 0, source.width(), source.height()), image,
                            QRectF(source))
            inner.end()
            painter.drawImage(QPointF(source.topLeft()), temp)
        else:
            painter.setOpacity(opacity)
            painter.drawImage(QRectF(source), image, QRectF(source))
            painter.setOpacity(1.0)

    def _paint_floating(self, painter: QPainter) -> None:
        doc = self.doc
        if doc is None or doc.floating is None:
            return
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        painter.drawImage(QPointF(doc.floating_pos), doc.floating)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

    def _paint_ants(self, painter: QPainter) -> None:
        doc = self.doc
        if doc is None or not doc.has_selection():
            return
        painter.save()
        painter.setBrush(Qt.NoBrush)
        for color, offset in ((QColor(0, 0, 0), self._ants_phase),
                              (QColor(255, 255, 255), self._ants_phase + 4)):
            pen = QPen(color, 0, Qt.DashLine)
            pen.setCosmetic(True)
            pen.setDashPattern([4, 4])
            pen.setDashOffset(offset)
            painter.setPen(pen)
            if doc.selection_path is not None:
                painter.drawPath(doc.selection_path)
            else:
                bounds = doc.selection.boundingRect()
                painter.drawRect(QRectF(bounds.adjusted(0, 0, 1, 1)))
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
        doc = self.doc
        if doc is None or not doc.has_selection():
            return
        self._ants_phase = (self._ants_phase + 1) % 10
        bounds = doc.selection.boundingRect()
        if bounds.isEmpty():
            self.update()
            return
        self.update_doc_rect(bounds)

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
        if (self.doc is not None and event.button() == Qt.LeftButton
                and event.modifiers() & Qt.ControlModifier):
            hit = self._guide_at(event.position())
            if hit is not None:
                self._guide_drag = hit
                orientation = hit[0]
                self.setCursor(Qt.SizeVerCursor if orientation == "h" else Qt.SizeHorCursor)
                event.accept()
                return
        if event.button() == Qt.MiddleButton or (self._space and event.button() == Qt.LeftButton):
            self._panning = True
            self._pan_start = event.position()
            self._pan_origin = QPointF(self.pan)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.LeftButton or self.doc is None:
            return
        self.app.pressure = 1.0
        pos = self.view_to_doc(event.position())
        if event.modifiers() & Qt.AltModifier and not getattr(self.app.tool, "handles_alt", False):
            self.app.pick_color(pos)
            return
        self.app.tool.press(self._snap(pos), event)

    def mouseMoveEvent(self, event) -> None:
        self._mouse = event.position()
        if self._guide_drag is not None and self.doc is not None:
            orientation, index = self._guide_drag
            guides = (self.doc.guides_h if orientation == "h" else self.doc.guides_v)
            if 0 <= index < len(guides):
                point = self.view_to_doc(event.position())
                guides[index] = float(point.y() if orientation == "h" else point.x())
                self.update()
                self.view_changed.emit()
            self.cursor_changed.emit()
            return
        if self._panning:
            delta = event.position() - self._pan_start
            self.pan = QPointF(self._pan_origin.x() + delta.x(), self._pan_origin.y() + delta.y())
            self._auto_fit = False
            self._notify_view()
            self.update()
            return
        tool = self.app.tool
        pos = self.view_to_doc(event.position())
        if event.buttons() & Qt.LeftButton:
            if (event.modifiers() & Qt.AltModifier
                    and not getattr(tool, "handles_alt", False)):
                self.app.pick_color(pos)
                self.app.update_coords(pos)
                return
            tool.move(self._snap(pos), event)
        self.app.update_coords(pos)
        self._refresh_cursor_ring()
        self.cursor_changed.emit()

    def mouseReleaseEvent(self, event) -> None:
        if self._guide_drag is not None and self.doc is not None:
            orientation, index = self._guide_drag
            guides = (self.doc.guides_h if orientation == "h" else self.doc.guides_v)
            if 0 <= index < len(guides):
                point = self.view_to_doc(event.position())
                value = float(point.y() if orientation == "h" else point.x())
                limit = (self.doc.size.height() if orientation == "h"
                         else self.doc.size.width())
                if value < 0 or value > limit:
                    del guides[index]
                else:
                    guides[index] = value
                self.doc.mark_modified(True)
            self._guide_drag = None
            self.setCursor(self._cursor_for_tool())
            self.update()
            self.view_changed.emit()
            return
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning = False
            self.setCursor(self._cursor_for_tool())
            return
        if event.button() == Qt.LeftButton and self.doc is not None:
            self.app.tool.release(self._snap(self.view_to_doc(event.position())), event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.doc is not None:
            if event.modifiers() & Qt.ControlModifier:
                hit = self._guide_at(event.position())
                if hit is not None:
                    orientation, index = hit
                    guides = (self.doc.guides_h if orientation == "h"
                              else self.doc.guides_v)
                    if 0 <= index < len(guides):
                        del guides[index]
                        self.doc.mark_modified(True)
                        self.update()
                        self.view_changed.emit()
                    return
            self.app.tool.double_click(self.view_to_doc(event.position()), event)

    def _snap(self, pos: QPointF) -> QPointF:
        if self.doc is None or not getattr(self.app, "snap_enabled", True):
            return pos
        if not getattr(self.app.tool, "snaps", False):
            return pos
        grid = self.app.grid_size if getattr(self.app, "snap_grid", False) else 0.0
        return self.doc.snap_point(pos, tolerance=8.0 / max(1e-6, self.zoom), grid=grid)

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
            self._notify_view()
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

    def tabletEvent(self, event) -> None:
        from PySide6.QtCore import QEvent

        if self.doc is None:
            return
        self.setFocus()
        self._mouse = event.position()
        self.app.pressure = max(0.05, min(1.0, float(event.pressure() or 1.0)))
        pos = self.view_to_doc(event.position())
        kind = event.type()
        if kind == QEvent.TabletPress:
            self.app.tool.press(pos, event)
        elif kind == QEvent.TabletMove:
            self.app.tool.move(pos, event)
        elif kind == QEvent.TabletRelease:
            self.app.tool.release(pos, event)
            self.app.pressure = 1.0
        self.app.update_coords(pos)
        event.accept()

    def dragEnterEvent(self, event) -> None:
        if self.app.can_drop(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if self.app.can_drop(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self.app.can_drop(event.mimeData()):
            self.app.drop_mime(event.mimeData())
            event.acceptProposedAction()


class CanvasHost(QWidget):
    def __init__(self, canvas: Canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        canvas.host = self
        self.setAcceptDrops(True)
        self._syncing = False
        self.hruler = Ruler(canvas, Qt.Horizontal)
        self.vruler = Ruler(canvas, Qt.Vertical)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.hruler, 0, 1)
        layout.addWidget(self.vruler, 1, 0)
        layout.addWidget(canvas, 1, 1)
        self.vbar = QScrollBar(Qt.Vertical)
        self.hbar = QScrollBar(Qt.Horizontal)
        layout.addWidget(self.vbar, 1, 2)
        layout.addWidget(self.hbar, 2, 1)
        corner = QWidget()
        corner.setFixedSize(self.vbar.sizeHint().width(), self.hbar.sizeHint().height())
        layout.addWidget(corner, 2, 2)
        self.hbar.valueChanged.connect(self._hbar_changed)
        self.vbar.valueChanged.connect(self._vbar_changed)
        canvas.view_changed.connect(self._refresh_rulers)
        canvas.cursor_changed.connect(self._refresh_rulers)

    def set_rulers_visible(self, visible: bool) -> None:
        self.hruler.setVisible(visible)
        self.vruler.setVisible(visible)

    def _refresh_rulers(self) -> None:
        self.hruler.update()
        self.vruler.update()

    def _hbar_changed(self, value: int) -> None:
        if not self._syncing:
            self.canvas.set_scroll_offset(value, self.vbar.value())

    def _vbar_changed(self, value: int) -> None:
        if not self._syncing:
            self.canvas.set_scroll_offset(self.hbar.value(), value)

    def sync_bars(self) -> None:
        canvas = self.canvas
        margin = canvas.MARGIN
        self._syncing = True
        if canvas.doc is None:
            self.hbar.setRange(0, 0)
            self.vbar.setRange(0, 0)
            self._syncing = False
            return
        viewport_w = max(1, canvas.width())
        viewport_h = max(1, canvas.height())
        content = canvas.content_size()
        content_w = content.width() * canvas.zoom
        content_h = content.height() * canvas.zoom
        range_x = max(0, int(round(content_w + 2 * margin - viewport_w)))
        range_y = max(0, int(round(content_h + 2 * margin - viewport_h)))
        for bar, range_value, viewport, content, pan in (
            (self.hbar, range_x, viewport_w, content_w, canvas.pan.x()),
            (self.vbar, range_y, viewport_h, content_h, canvas.pan.y()),
        ):
            bar.setRange(0, range_value)
            bar.setPageStep(max(1, viewport))
            bar.setSingleStep(48)
            bar.setEnabled(range_value > 0)
            if range_value > 0:
                bar.setValue(min(max(int(round(margin - pan)), 0), range_value))
            else:
                bar.setValue(0)
        self._syncing = False

    def dragEnterEvent(self, event) -> None:
        if self.canvas.app.can_drop(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if self.canvas.app.can_drop(event.mimeData()):
            self.canvas.app.drop_mime(event.mimeData())
            event.acceptProposedAction()
