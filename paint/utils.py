from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage, QPainter, QRegion


@contextmanager
def painting(target):
    painter = QPainter(target)
    try:
        yield painter
    finally:
        painter.end()


def image_to_array(image: QImage) -> tuple[QImage, np.ndarray]:
    conv = image.convertToFormat(QImage.Format_ARGB32)
    width, height = conv.width(), conv.height()
    raw = np.frombuffer(conv.constBits(), np.uint8)
    stride = conv.bytesPerLine()
    arr = raw.reshape(height, stride)[:, : width * 4].reshape(height, width, 4).copy()
    return conv, arr


def array_to_image(arr: np.ndarray, premultiplied: bool = True) -> QImage:
    height, width, _ = arr.shape
    data = np.ascontiguousarray(arr, dtype=np.uint8).tobytes()
    img = QImage(data, width, height, width * 4, QImage.Format_ARGB32)
    img = img.copy()
    if premultiplied:
        img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    return img


def color_bgra(color: QColor) -> tuple[int, int, int, int]:
    return color.blue(), color.green(), color.red(), color.alpha()


def region_mask(region: QRegion | None, width: int, height: int) -> np.ndarray | None:
    if region is None or region.isEmpty():
        return None
    mask = np.zeros((height, width), bool)
    for rect in region.rects():
        r = rect.intersected(QRect(0, 0, width, height))
        if not r.isEmpty():
            mask[r.top(): r.bottom() + 1, r.left(): r.right() + 1] = True
    return mask


def mask_bbox(mask: np.ndarray) -> QRect:
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return QRect()
    cols = np.flatnonzero(mask.any(axis=0))
    return QRect(
        int(cols[0]),
        int(rows[0]),
        int(cols[-1] - cols[0] + 1),
        int(rows[-1] - rows[0] + 1),
    )


def point_rect(point: QPoint, radius: int) -> QRect:
    size = radius * 2
    return QRect(point.x() - radius, point.y() - radius, size, size)
