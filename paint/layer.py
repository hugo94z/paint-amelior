from __future__ import annotations

import itertools

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage

BLEND_MODES = [
    ("normal", "Normal"),
    ("multiply", "Produit"),
    ("screen", "Superposition"),
    ("overlay", "Incrustation"),
    ("darken", "Obscurcir"),
    ("lighten", "Éclaircir"),
]

_ids = itertools.count(1)


class Layer:
    def __init__(self, name: str, size: QSize, color: QColor | None = None):
        self.id = next(_ids)
        self.name = name
        self.visible = True
        self.opacity = 1.0
        self.blend = "normal"
        self.image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self.image.fill(color if color is not None else Qt.transparent)

    def snapshot(self) -> dict:
        return {
            "layer": self,
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "blend": self.blend,
        }

    def restore(self, data: dict) -> None:
        self.name = data["name"]
        self.visible = data["visible"]
        self.opacity = data["opacity"]
        self.blend = data["blend"]
