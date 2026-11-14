from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygon, QRegion

from .base import BaseTool
from ..ui.text_dialog import TextDialog


class TextTool(BaseTool):
    id = "text"
    label = "Texte"
    shortcut = "T"
    icon = "text"

    def __init__(self, app):
        super().__init__(app)
        self.family = "Segoe UI"
        self.pixel_size = 48
        self.bold = False
        self.italic = False
        self.opacity = 1.0

    def press(self, pos, event) -> None:
        layer = self.paintable_layer()
        if layer is None:
            return
        dialog = TextDialog(self.app, self.family, self.pixel_size, self.bold, self.italic)
        if dialog.exec() != TextDialog.Accepted:
            return
        text = dialog.text()
        if not text.strip():
            return
        self.family = dialog.family()
        self.pixel_size = dialog.pixel_size()
        self.bold = dialog.bold()
        self.italic = dialog.italic()
        font = QFont(self.family)
        font.setPixelSize(self.pixel_size)
        font.setBold(self.bold)
        font.setItalic(self.italic)
        rect = QRectF(pos.x(), pos.y(), max(1.0, self.doc.size.width() - pos.x()),
                      max(1.0, self.doc.size.height() - pos.y()))
        flags = int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
        metrics = self.app.fontMetrics(font)
        bounds = metrics.boundingRect(rect.toRect(), flags, text).adjusted(-6, -6, 12, 12)
        bounds = bounds.intersected(self.doc.rect())
        if bounds.isEmpty():
            return
        tx = self.doc.history.begin("Texte")
        tx.touch(layer, bounds)
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setOpacity(self.opacity)
        if self.doc.has_selection():
            painter.setClipRegion(self.doc.selection)
        painter.setFont(font)
        painter.setPen(self.app.fg)
        painter.drawText(rect, flags, text)
        painter.end()
        self.doc.invalidate(bounds)
        tx.commit()
        self.notify("Texte ajouté")
