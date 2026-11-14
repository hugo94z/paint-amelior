from __future__ import annotations

from PySide6.QtGui import QPainter

from ..filters import flood_fill
from .base import BaseTool


class FillTool(BaseTool):
    id = "fill"
    label = "Pot de peinture"
    shortcut = "G"
    icon = "fill"

    def __init__(self, app):
        super().__init__(app)
        self.tolerance = 24
        self.contiguous = True

    def press(self, pos, event) -> None:
        layer = self.doc.active_layer()
        if layer is None:
            return
        image, bounds = flood_fill(
            layer.image,
            int(pos.x()),
            int(pos.y()),
            self.app.fg,
            self.tolerance,
            self.doc.selection,
        )
        if image is None or bounds.isEmpty():
            self.notify("Aucune zone à remplir")
            return
        tx = self.doc.history.begin("Remplissage")
        tx.touch(layer, bounds)
        painter = QPainter(layer.image)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(bounds.topLeft(), image)
        painter.end()
        self.doc.invalidate(bounds)
        tx.commit()
        self.notify("Zone remplie")


class PickerTool(BaseTool):
    id = "picker"
    label = "Pipette"
    shortcut = "I"
    icon = "picker"

    def press(self, pos, event) -> None:
        self.app.pick_color(pos)
