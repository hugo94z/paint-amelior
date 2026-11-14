from __future__ import annotations

from PySide6.QtGui import QPainter

from ..filters import color_range_mask, flood_mask
from ..utils import region_mask
from .base import BaseTool


class MagicWandTool(BaseTool):
    id = "wand"
    label = "Baguette magique"
    shortcut = "W"
    icon = "wand"

    def __init__(self, app):
        super().__init__(app)
        self.tolerance = 32
        self.contiguous = True
        self.sample_all = True
        self.feather = 0
        self.selection_mode = "replace"

    def press(self, pos, event) -> None:
        doc = self.doc
        layer = doc.active_layer()
        if layer is None:
            return
        source = doc.composite() if self.sample_all else layer.image
        x, y = int(pos.x()), int(pos.y())
        if not doc.rect().contains(x, y):
            return
        clip = None
        if self.selection_mode in ("add", "subtract", "intersect") and doc.has_selection():
            clip = region_mask(doc.selection, doc.size.width(), doc.size.height())
        if self.contiguous:
            array = flood_mask(source, x, y, self.tolerance, clip)
        else:
            color = source.pixelColor(x, y)
            array = color_range_mask(source, color, self.tolerance)
            if clip is not None and self.selection_mode == "intersect":
                array &= clip
        if array is None or not array.any():
            self.notify("Aucune zone sélectionnée")
            return
        doc.combine_selection(array, self.selection_mode, self.feather)
        self.notify("Sélection par couleur")
