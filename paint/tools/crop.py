from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .base import BaseTool


class CropTool(BaseTool):
    snaps = True
    id = "crop"
    label = "Recadrage"
    shortcut = "C"
    icon = "crop"

    def __init__(self, app):
        super().__init__(app)
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
        if self._rect().width() < 3 or self._rect().height() < 3:
            self.cancel()
            return
        self.notify("Entrée pour recadrer, Échap pour annuler")
        self.app.canvas.update()

    def _rect(self) -> QRectF:
        if self._start is None or self._end is None:
            return QRectF()
        return QRectF(self._start, self._end).normalized().intersected(
            QRectF(self.doc.rect())
        )

    def key_press(self, event) -> bool:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            rect = self._rect()
            if rect.width() >= 3 and rect.height() >= 3:
                self.doc.crop(rect.toAlignedRect())
                self._start = None
                self._end = None
                self.app.canvas.fit()
                self.notify("Image recadrée")
            return True
        if event.key() == Qt.Key_Escape:
            self.cancel()
            return True
        return False

    def cancel(self) -> None:
        self._start = None
        self._end = None
        self.app.canvas.update()

    def deactivate(self) -> None:
        self.cancel()

    def preview(self, painter) -> None:
        rect = self._rect()
        if rect.isEmpty():
            return
        full = QRectF(self.doc.rect())
        shade = QColor(0, 0, 0, 130)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shade)
        if rect.top() > full.top():
            painter.drawRect(QRectF(full.left(), full.top(), full.width(), rect.top() - full.top()))
        if rect.bottom() < full.bottom():
            painter.drawRect(QRectF(full.left(), rect.bottom(), full.width(),
                                    full.bottom() - rect.bottom()))
        if rect.left() > full.left():
            painter.drawRect(QRectF(full.left(), rect.top(), rect.left() - full.left(), rect.height()))
        if rect.right() < full.right():
            painter.drawRect(QRectF(rect.right(), rect.top(), full.right() - rect.right(), rect.height()))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.SolidLine))
        painter.drawRect(rect)
        pen = QPen(QColor(255, 255, 255, 120), 1, Qt.DashLine)
        painter.setPen(pen)
        for factor in (1 / 3, 2 / 3):
            x = rect.left() + rect.width() * factor
            y = rect.top() + rect.height() * factor
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
