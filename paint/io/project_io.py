from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PySide6.QtCore import QSize

from ..document import Document
from ..layer import Layer
from .image_io import image_to_png_bytes, png_bytes_to_image

PROJECT_SUFFIX = ".paint"
PROJECT_FILTER = "Projet Paint (*.paint);;Toutes les images (*.png *.jpg *.jpeg *.webp *.bmp)"


def save_project(doc: Document, path: str | Path) -> bool:
    path = Path(path)
    data = {
        "format": 1,
        "app": "paint-amelior",
        "width": doc.size.width(),
        "height": doc.size.height(),
        "active": doc.active_index,
        "layers": [
            {
                "name": layer.name,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "blend": layer.blend,
                "file": f"layers/{index:03d}.png",
            }
            for index, layer in enumerate(doc.layers)
        ],
    }
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("project.json", json.dumps(data, ensure_ascii=False, indent=1))
            for index, layer in enumerate(doc.layers):
                archive.writestr(f"layers/{index:03d}.png", image_to_png_bytes(layer.image))
    except (OSError, ValueError):
        return False
    doc.path = path
    doc.mark_modified(False)
    return True


def load_project(path: str | Path, undo_budget: int = 400 * 1024 * 1024) -> Document | None:
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            data = json.loads(archive.read("project.json").decode("utf-8"))
            width = int(data.get("width", 1))
            height = int(data.get("height", 1))
            doc = Document(QSize(width, height), undo_budget=undo_budget)
            for entry in data.get("layers", []):
                image = png_bytes_to_image(archive.read(entry["file"]))
                if image is None:
                    continue
                layer = Layer(entry.get("name", "Calque"), QSize(width, height))
                layer.image = image
                layer.visible = bool(entry.get("visible", True))
                layer.opacity = float(entry.get("opacity", 1.0))
                layer.blend = entry.get("blend", "normal")
                if not any(layer.blend == key for key in
                           ("normal", "multiply", "screen", "overlay", "darken", "lighten")):
                    layer.blend = "normal"
                doc.add_layer_raw(layer)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    if not doc.layers:
        return None
    doc.active_index = min(max(int(data.get("active", 0)), 0), len(doc.layers) - 1)
    doc.history.clear()
    doc.invalidate_all()
    doc.path = path
    doc.mark_modified(False)
    return doc
