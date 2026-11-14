from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, QSizeF
from PySide6.QtGui import QImage, QPageSize, QPainter, QPdfWriter
try:
    from PySide6.QtSvg import QSvgGenerator
except ImportError:
    QSvgGenerator = None
from PIL import Image

from ..document import Document
from .image_io import document_to_image


def export_pdf(doc: Document, path: str | Path) -> bool:
    image = document_to_image(doc, flatten=True)
    if image.isNull():
        return False
    writer = QPdfWriter(str(path))
    writer.setResolution(96)
    try:
        writer.setPageSize(QPageSize(QSizeF(image.width() * 0.75, image.height() * 0.75),
                                    QPageSize.Unit.Point))
    except (TypeError, ValueError):
        pass
    painter = QPainter(writer)
    painter.drawImage(QRectF(0, 0, writer.width(), writer.height()), image)
    painter.end()
    return True


def export_svg(doc: Document, path: str | Path) -> bool:
    if QSvgGenerator is None:
        return False
    image = document_to_image(doc)
    if image.isNull():
        return False
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(QSize(image.width(), image.height()))
    generator.setViewBox(QRect(0, 0, image.width(), image.height()))
    generator.setTitle("Paint Amélioré")
    painter = QPainter(generator)
    painter.drawImage(0, 0, image)
    painter.end()
    return True


def _pil_image(image: QImage) -> Image.Image:
    conv = image.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombuffer(
        "RGBA", (conv.width(), conv.height()), bytes(conv.constBits()), "raw", "RGBA", 0, 1
    )


def export_animation(doc: Document, path: str | Path, apng: bool = False) -> bool:
    frames = [frame for frame in doc.frames if not frame["image"].isNull()]
    if not frames:
        return False
    images = [_pil_image(frame["image"]) for frame in frames]
    durations = [max(20, int(frame.get("duration", 120))) for frame in frames]
    target = Path(path)
    try:
        if apng:
            images[0].save(
                target, format="PNG", save_all=True, append_images=images[1:],
                duration=durations, loop=0,
            )
        else:
            images[0].save(
                target, format="GIF", save_all=True, append_images=images[1:],
                duration=durations, loop=0, disposal=2, optimize=False,
            )
    except (OSError, ValueError):
        return False
    return True
