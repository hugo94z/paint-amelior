from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def tool_icon(kind: str, color: str = "#e8eaed", size: int = 24) -> QIcon:
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "brush":
        path = QPainterPath()
        path.moveTo(5, 19)
        path.cubicTo(7, 13, 12, 12, 17, 6)
        painter.setPen(QPen(QColor(color), 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(color), 1.2))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(18, 5), 2.4, 2.4)
    elif kind == "eraser":
        painter.save()
        painter.translate(12, 12)
        painter.rotate(-38)
        painter.drawRoundedRect(QRectF(-8, -4.5, 16, 9), 2.5, 2.5)
        painter.drawLine(QPointF(0, -4.5), QPointF(0, 4.5))
        painter.restore()
    elif kind == "fill":
        path = QPolygonF(
            [QPointF(5, 11), QPointF(12, 4.5), QPointF(19.5, 12), QPointF(12, 19.5)]
        )
        painter.drawPolygon(path)
        painter.drawLine(QPointF(12, 4.5), QPointF(12, 2.5))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(20.5, 16), 1.6, 1.6)
    elif kind == "picker":
        painter.drawLine(QPointF(5, 19), QPointF(14, 10))
        painter.drawLine(QPointF(15.5, 8.5), QPointF(18.5, 5.5))
        painter.drawEllipse(QPointF(19.5, 4.5), 2.2, 2.2)
    elif kind == "line":
        painter.drawLine(QPointF(5, 19), QPointF(19, 5))
    elif kind == "rect":
        painter.drawRect(QRectF(4, 6, 16, 12))
    elif kind == "ellipse":
        painter.drawEllipse(QRectF(4, 6, 16, 12))
    elif kind == "roundrect":
        painter.drawRoundedRect(QRectF(4, 6, 16, 12), 4, 4)
    elif kind == "polygon":
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(12, 3.5),
                    QPointF(20.5, 10),
                    QPointF(17.5, 20),
                    QPointF(6.5, 20),
                    QPointF(3.5, 10),
                ]
            )
        )
    elif kind == "text":
        font = QFont("Segoe UI", 13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(QRectF(2, 2, 20, 20), Qt.AlignCenter, "A")
    elif kind == "gradient":
        gradient = QLinearGradient(4, 0, 20, 0)
        gradient.setColorAt(0.0, QColor(color))
        gradient.setColorAt(1.0, QColor(color).darker(300))
        painter.setBrush(gradient)
        painter.drawRect(QRectF(4, 6, 16, 12))
    elif kind == "select":
        pen = QPen(QColor(color), 1.6, Qt.DashLine)
        pen.setDashPattern([2.2, 2.2])
        painter.setPen(pen)
        painter.drawRect(QRectF(4, 5, 16, 14))
    elif kind == "wand":
        painter.drawLine(QPointF(5, 19), QPointF(15, 9))
        painter.drawLine(QPointF(15, 9), QPointF(17, 7))
        painter.setPen(QPen(QColor(color), 1.4))
        for cx, cy, r in ((18.5, 4.5, 1.6), (21, 8, 1.1), (15, 3.5, 1.0)):
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    elif kind == "crop":
        painter.drawLine(QPointF(6, 3), QPointF(6, 18))
        painter.drawLine(QPointF(3, 6), QPointF(18, 6))
        painter.drawLine(QPointF(18, 6), QPointF(18, 21))
        painter.drawLine(QPointF(6, 18), QPointF(21, 18))
    elif kind == "clone":
        painter.drawRect(QRectF(4, 7, 11, 11))
        painter.drawRect(QRectF(9, 3, 11, 11))
        painter.drawLine(QPointF(14.5, 6.5), QPointF(14.5, 10.5))
        painter.drawLine(QPointF(12.5, 8.5), QPointF(16.5, 8.5))
    elif kind == "tone":
        painter.drawEllipse(QPointF(12, 12), 5.5, 5.5)
        for angle in range(0, 360, 45):
            import math

            rad = math.radians(angle)
            painter.drawLine(
                QPointF(12 + math.cos(rad) * 7.6, 12 + math.sin(rad) * 7.6),
                QPointF(12 + math.cos(rad) * 9.6, 12 + math.sin(rad) * 9.6),
            )
    elif kind == "smudge":
        path = QPainterPath()
        path.moveTo(12, 4)
        path.cubicTo(16.5, 10, 18.5, 12.5, 18.5, 15)
        path.cubicTo(18.5, 18.6, 15.6, 21, 12, 21)
        path.cubicTo(8.4, 21, 5.5, 18.6, 5.5, 15)
        path.cubicTo(5.5, 12.5, 7.5, 10, 12, 4)
        painter.drawPath(path)
    elif kind == "zoom":
        painter.drawEllipse(QPointF(10.5, 10.5), 5.5, 5.5)
        painter.drawLine(QPointF(15, 15), QPointF(20, 20))
    else:
        painter.drawRect(QRectF(4, 4, 16, 16))

    painter.end()
    return QIcon(pixmap)
