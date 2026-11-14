from __future__ import annotations

import itertools

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage

BLEND_MODES = [
    ("normal", "Normal"),
    ("multiply", "Produit"),
    ("screen", "Superposition"),
    ("overlay", "Incrustation"),
    ("softlight", "Lumière douce"),
    ("hardlight", "Lumière vive"),
    ("darken", "Obscurcir"),
    ("lighten", "Éclaircir"),
    ("difference", "Différence"),
    ("exclusion", "Exclusion"),
    ("colordodge", "Densité couleur +"),
    ("colorburn", "Densité couleur -"),
]

_ids = itertools.count(1)


class Layer:
    def __init__(self, name: str, size: QSize, color: QColor | None = None):
        self.id = next(_ids)
        self.name = name
        self.visible = True
        self.opacity = 1.0
        self.blend = "normal"
        self.mask: QImage | None = None
        self.mask_enabled = True
        self.locked = False
        self.lock_alpha = False
        self.adjustment: dict | None = None
        self.image = QImage(size, QImage.Format_ARGB32_Premultiplied)
        self.image.fill(color if color is not None else Qt.transparent)

    def snapshot(self) -> dict:
        return {
            "layer": self,
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "blend": self.blend,
            "mask": self.mask,
            "mask_enabled": self.mask_enabled,
            "locked": self.locked,
            "lock_alpha": self.lock_alpha,
            "adjustment": dict(self.adjustment) if self.adjustment else None,
        }

    def restore(self, data: dict) -> None:
        self.name = data["name"]
        self.visible = data["visible"]
        self.opacity = data["opacity"]
        self.blend = data["blend"]
        self.mask = data.get("mask")
        self.mask_enabled = data.get("mask_enabled", True)
        self.locked = data.get("locked", False)
        self.lock_alpha = data.get("lock_alpha", False)
        self.adjustment = dict(data["adjustment"]) if data.get("adjustment") else None
