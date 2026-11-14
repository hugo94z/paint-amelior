from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..document import Document

OPEN_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif *.psd);;Tous les fichiers (*)"
EXPORT_FILTER = "PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;BMP (*.bmp);;TIFF (*.tif)"


def load_image(path: str | Path) -> QImage | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".psd":
        try:
            from PIL import Image

            with Image.open(path) as pil:
                rgba = pil.convert("RGBA")
                data = rgba.tobytes("raw", "RGBA")
                image = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
                return image.copy().convertToFormat(QImage.Format_ARGB32_Premultiplied)
        except (OSError, ValueError):
            return None
    image = QImage(str(path))
    if image.isNull():
        return None
    return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def image_to_png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data


def png_bytes_to_image(data: bytes) -> QImage | None:
    image = QImage()
    if not image.loadFromData(data, "PNG"):
        return None
    return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)


def document_to_image(doc: Document, flatten: bool = False) -> QImage:
    image = doc.composite().copy()
    if flatten:
        flat = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
        flat.fill(QColor(Qt.white))
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flat
    return image


def export_image(doc: Document, path: str | Path, quality: int = 92) -> bool:
    path = Path(path)
    suffix = path.suffix.lower()
    flatten = suffix in {".jpg", ".jpeg", ".bmp"}
    image = document_to_image(doc, flatten=flatten)
    fmt = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
        ".bmp": "BMP",
        ".tif": "TIFF",
        ".tiff": "TIFF",
    }.get(suffix, "PNG")
    return bool(image.save(str(path), fmt, quality))
