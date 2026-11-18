from __future__ import annotations

from PySide6.QtGui import QPainter

from ..filters import flood_fill, pattern_fill
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
        self.pattern = ""
        self.pattern_scale = 100

    def press(self, pos, event) -> None:
        layer = self.paintable_layer()
        if layer is None:
            return
        if self.pattern:
            image, bounds = pattern_fill(
                layer.image,
                int(pos.x()),
                int(pos.y()),
                self.pattern,
                self.pattern_scale,
                self.tolerance,
                self.doc.selection,
            )
        else:
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
        mask = self.doc.mask_for_image()
        if mask is not None:
            local_mask = mask.copy(bounds)
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, local_mask)
            painter.end()
        painter = QPainter(layer.image)
        if mask is not None or layer.lock_alpha:
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        else:
            painter.setCompositionMode(QPainter.CompositionMode_Source)
        if layer.lock_alpha:
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
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

    def __init__(self, app):
        super().__init__(app)
        self.sample_size = 1

    def press(self, pos, event) -> None:
        self.app.pick_color(pos, self.sample_size)
