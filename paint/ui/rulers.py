from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

STEPS = (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000,
         2000, 2500, 5000, 10000, 20000)


def _nice_step(zoom: float, target: float = 64.0) -> int:
    minimum = max(1e-6, target / max(1e-6, zoom))
    for step in STEPS:
        if step >= minimum:
            return step
    return STEPS[-1]


class Ruler(QWidget):
    def __init__(self, canvas, orientation: Qt.Orientation, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.orientation = orientation
        self._drag_origin = None
        self._drag_position = None
        if orientation == Qt.Horizontal:
            self.setFixedHeight(22)
        else:
            self.setFixedWidth(22)
        self.setMouseTracking(True)
        self.setCursor(Qt.SplitVCursor if orientation == Qt.Horizontal else Qt.SplitHCursor)

    def _light(self) -> bool:
        return bool(getattr(self.canvas.app, "light_theme", False))

    def _mouse_axis(self, position: QPointF) -> float:
        return position.x() if self.orientation == Qt.Horizontal else position.y()

    def _doc_position(self, position: QPointF) -> float:
        doc = self.canvas.doc
        if doc is None:
            return 0.0
        point = self.canvas.view_to_doc(position)
        return point.x() if self.orientation == Qt.Horizontal else point.y()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        light = self._light()
        painter.fillRect(self.rect(), QColor("#e9ebee") if light else QColor("#202328"))
        painter.setPen(QPen(QColor("#b9bec6") if light else QColor("#3a3f46"), 1))
        if self.orientation == Qt.Horizontal:
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        doc = self.canvas.doc
        if doc is None or self.canvas.rotation % 360:
            painter.end()
            return
        zoom = self.canvas.zoom
        step = _nice_step(zoom)
        minor = step / 5.0
        start = self.canvas.pan.x() if self.orientation == Qt.Horizontal else self.canvas.pan.y()
        length = self.width() if self.orientation == Qt.Horizontal else self.height()
        limit = doc.size.width() if self.orientation == Qt.Horizontal else doc.size.height()
        text_color = QColor("#4b5059") if light else QColor("#9aa1ab")
        first = int(math.floor(max(0.0, -start / zoom) / step)) * step
        for value in range(first, limit + step, step):
            position = start + value * zoom
            if position < -1 or position > length + 1:
                continue
            painter.setPen(QPen(QColor("#8b919a") if light else QColor("#545a63"), 1))
            if self.orientation == Qt.Horizontal:
                painter.drawLine(QPointF(position, self.height() - 7),
                                 QPointF(position, self.height() - 1))
            else:
                painter.drawLine(QPointF(self.width() - 7, position),
                                 QPointF(self.width() - 1, position))
            painter.setPen(text_color)
            label = str(int(value))
            if self.orientation == Qt.Horizontal:
                painter.drawText(QRectF(position + 3, 1, 60, 12), Qt.AlignLeft | Qt.AlignTop, label)
            else:
                painter.save()
                painter.translate(2, position + 3)
                painter.rotate(90)
                painter.drawText(QRectF(0, 0, 60, 12), Qt.AlignLeft | Qt.AlignTop, label)
                painter.restore()
        if minor * zoom >= 4:
            offset = first
            while offset <= limit:
                position = start + offset * zoom
                if -1 <= position <= length + 1:
                    if self.orientation == Qt.Horizontal:
                        painter.drawLine(QPointF(position, self.height() - 3),
                                         QPointF(position, self.height() - 1))
                    else:
                        painter.drawLine(QPointF(self.width() - 3, position),
                                         QPointF(self.width() - 1, position))
                offset += minor
        self._paint_guides(painter, zoom)
        self._paint_cursor(painter)
        painter.end()

    def _paint_guides(self, painter: QPainter, zoom: float) -> None:
        doc = self.canvas.doc
        if doc is None or not doc.guides_visible:
            return
        painter.setPen(QPen(QColor("#38bdf8"), 1))
        guides = doc.guides_h if self.orientation == Qt.Horizontal else doc.guides_v
        for value in guides:
            position = (self.canvas.pan.x() if self.orientation == Qt.Horizontal
                        else self.canvas.pan.y()) + value * zoom
            if self.orientation == Qt.Horizontal:
                painter.drawLine(QPointF(position, 2), QPointF(position, self.height() - 2))
            else:
                painter.drawLine(QPointF(2, position), QPointF(self.width() - 2, position))

    def _paint_cursor(self, painter: QPainter) -> None:
        point = self.canvas._mouse
        if point.x() < -500:
            return
        painter.setPen(QPen(QColor("#f97316"), 1))
        if self.orientation == Qt.Horizontal:
            painter.drawLine(QPointF(point.x(), 0), QPointF(point.x(), self.height()))
        else:
            painter.drawLine(QPointF(0, point.y()), QPointF(self.width(), point.y()))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.position()
            self._drag_position = event.position()
            self.canvas.set_guide_preview(
                self.orientation, self._doc_position(event.position()))

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None:
            self._drag_position = event.position()
            self.canvas.set_guide_preview(
                self.orientation, self._doc_position(event.position()))

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_origin is not None and self.canvas.doc is not None:
            value = self._doc_position(event.position())
            doc = self.canvas.doc
            limit = doc.size.width() if self.orientation == Qt.Horizontal else doc.size.height()
            if 0 <= value <= limit:
                if self.orientation == Qt.Horizontal:
                    doc.guides_h.append(float(value))
                else:
                    doc.guides_v.append(float(value))
                doc.mark_modified(True)
        self._drag_origin = None
        self._drag_position = None
        self.canvas.set_guide_preview(None, 0.0)
        self.update()
