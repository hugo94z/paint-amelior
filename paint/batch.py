from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .io.image_io import document_to_image, export_image, load_image
from .io.project_io import load_project

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".psd", ".paint"}


def convert(paths, output_dir, max_width: int = 0, fmt: str = "png", quality: int = 92) -> list[str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for raw in paths:
        source = Path(raw)
        if source.suffix.lower() in (".paint",):
            doc = load_project(source)
            if doc is None:
                continue
            image = document_to_image(doc)
            stem = source.stem
        else:
            image = load_image(source)
            if image is None:
                continue
            stem = source.stem
        if max_width and image.width() > max_width:
            image = image.scaledToWidth(max_width)
        target = out_dir / f"{stem}.{fmt}"
        if export_image_from_qimage(image, target, quality):
            written.append(str(target))
    return written


def export_image_from_qimage(image, target: Path, quality: int = 92) -> bool:
    suffix = target.suffix.lower()
    if suffix in (".jpg", ".jpeg", ".bmp"):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QImage, QPainter

        flat = QImage(image.size(), QImage.Format_ARGB32)
        flat.fill(QColor(Qt.white))
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flat
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
           ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF"}.get(suffix, "PNG")
    return bool(image.save(str(target), fmt, quality))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conversion par lot pour Paint Amélioré")
    parser.add_argument("input", help="Dossier ou fichiers à convertir")
    parser.add_argument("output", help="Dossier de sortie")
    parser.add_argument("--width", type=int, default=0, help="Largeur maximale (0 = inchangée)")
    parser.add_argument("--format", default="png", choices=["png", "jpg", "webp", "bmp", "tiff"])
    parser.add_argument("--quality", type=int, default=92)
    args = parser.parse_args(argv)
    source = Path(args.input)
    if source.is_dir():
        files = [p for p in source.iterdir() if p.suffix.lower() in SUPPORTED]
    else:
        files = [source]
    written = convert(files, args.output, args.width, args.format, args.quality)
    print(f"{len(written)} fichier(s) converti(s) dans {args.output}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
