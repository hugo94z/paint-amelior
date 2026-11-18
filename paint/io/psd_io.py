from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter

from ..document import Document
from ..layer import Layer

BLEND_NAMES = {
    "normal": "normal",
    "multiply": "multiply",
    "screen": "screen",
    "overlay": "overlay",
    "soft_light": "softlight",
    "hard_light": "hardlight",
    "darken": "darken",
    "lighten": "lighten",
    "difference": "difference",
    "exclusion": "exclusion",
    "color_dodge": "colordodge",
    "color_burn": "colorburn",
}


def _pil_to_qimage(image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    result = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
    return result.copy().convertToFormat(QImage.Format_ARGB32_Premultiplied)


def _blend(value) -> str:
    name = getattr(value, "name", str(value)).lower()
    return BLEND_NAMES.get(name, "normal")


def load_psd_document(path: str | Path, undo_budget: int = 400 * 1024 * 1024,
                      max_side: int = 16384) -> Document | None:
    try:
        from psd_tools import PSDImage
    except ImportError:
        return None
    try:
        psd = PSDImage.open(str(path))
    except (OSError, ValueError):
        return None
    width, height = psd.size
    if width < 1 or height < 1 or width > max_side or height > max_side:
        return None
    doc = Document(QSize(width, height), undo_budget=undo_budget)
    added = 0

    def add_node(node, prefix: str = "") -> None:
        nonlocal added
        for child in node:
            kind = getattr(child, "kind", "raster")
            name = f"{prefix}{child.name or 'Calque'}"
            if kind == "group":
                add_node(child, f"{name} / ")
                continue
            try:
                composite = child.composite()
            except (OSError, ValueError):
                composite = None
            if composite is None:
                continue
            image = _pil_to_qimage(composite)
            if image.isNull():
                continue
            full = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            full.fill(Qt.transparent)
            painter = QPainter(full)
            offset_x, offset_y = getattr(child, "offset", (0, 0))
            painter.drawImage(int(offset_x), int(offset_y), image)
            painter.end()
            layer = Layer(name, QSize(width, height))
            layer.image = full
            layer.visible = bool(getattr(child, "visible", True))
            opacity = int(getattr(child, "opacity", 255))
            layer.opacity = max(0.0, min(1.0, opacity / 255.0))
            layer.blend = _blend(getattr(child, "blend_mode", "normal"))
            doc.add_layer_raw(layer)
            added += 1

    add_node(psd)
    if not added:
        return None
    doc.active_index = len(doc.layers) - 1
    doc.invalidate_all()
    doc.history.clear()
    doc.path = Path(path)
    doc.mark_modified(False)
    return doc
