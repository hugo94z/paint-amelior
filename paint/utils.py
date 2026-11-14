from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QRegion


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
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setClipRegion(region)
    painter.fillRect(QRect(0, 0, width, height), QColor(255, 255, 255))
    painter.end()
    _, arr = image_to_array(image)
    return arr[:, :, 3] > 0


def mask_from_array(mask: np.ndarray, feather: float = 0.0) -> QImage | None:
    if mask is None or not mask.any():
        return None
    height, width = mask.shape
    arr = np.zeros((height, width, 4), np.uint8)
    arr[:, :, :3] = 255
    arr[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    image = array_to_image(arr, premultiplied=False)
    if feather > 0:
        image = blur_alpha(image, feather)
    return image


def blur_alpha(image: QImage, radius: float) -> QImage:
    from PIL import Image, ImageFilter

    _, arr = image_to_array(image)
    alpha = Image.fromarray(arr[:, :, 3], "L").filter(ImageFilter.GaussianBlur(float(radius)))
    arr[:, :, 3] = np.asarray(alpha, dtype=np.uint8)
    arr[:, :, :3] = 255
    return array_to_image(arr, premultiplied=False)


def region_from_mask(mask: QImage | None) -> QRegion:
    if mask is None or mask.isNull():
        return QRegion()
    alpha = mask.createAlphaMask()
    return QRegion(QBitmap.fromImage(alpha))


def mask_tint(mask: QImage | None, color: QColor | None = None) -> QImage | None:
    if mask is None or mask.isNull():
        return None
    color = color or QColor(59, 130, 246)
    _, arr = image_to_array(mask)
    out = np.zeros_like(arr)
    out[:, :, 0] = color.blue()
    out[:, :, 1] = color.green()
    out[:, :, 2] = color.red()
    out[:, :, 3] = (arr[:, :, 3].astype(np.uint16) * 55 // 255).astype(np.uint8)
    return array_to_image(out, premultiplied=False)


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
