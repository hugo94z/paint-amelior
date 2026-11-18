from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage
from PIL import Image, ImageEnhance, ImageFilter
from .utils import (
    array_to_image,
    color_bgra,
    image_array_view,
    image_to_array,
    mask_bbox,
    mask_from_array,
    region_mask,
)


def _to_pil(image: QImage) -> Image.Image:
    conv = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = conv.width(), conv.height()
    return Image.frombuffer("RGBA", (width, height), bytes(conv.constBits()), "raw", "RGBA", 0, 1)


def _from_pil(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    img = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888)
    return img.copy().convertToFormat(QImage.Format_ARGB32_Premultiplied)


def apply(image: QImage, name: str, value: float = 0.0, extra: float = 0.0,
          options: dict | None = None) -> QImage:
    options = options or {}
    if name == "invert":
        return _invert(image)
    if name == "levels":
        return _levels(image, options.get("black", 0.0), options.get("white", 255.0),
                       options.get("gamma", 1.0))
    if name == "hue":
        return _hue(image, options.get("shift", 0.0))
    if name == "vignette":
        return _vignette(image, options.get("strength", 0.6))
    if name == "motionblur":
        return _motion_blur(image, options.get("angle", 0.0), options.get("distance", 12.0))
    pil = _to_pil(image)
    if name == "blur":
        result = pil.filter(ImageFilter.GaussianBlur(max(0.1, value)))
    elif name == "sharpen":
        result = pil.filter(ImageFilter.UnsharpMask(radius=2, percent=int(max(1, value)), threshold=3))
    elif name == "brightness":
        result = ImageEnhance.Brightness(pil).enhance(max(0.0, value))
    elif name == "contrast":
        result = ImageEnhance.Contrast(pil).enhance(max(0.0, value))
    elif name == "saturation":
        result = ImageEnhance.Color(pil).enhance(max(0.0, value))
    elif name == "grayscale":
        gray = pil.convert("L").convert("RGBA")
        result = Image.blend(pil, gray, max(0.0, min(1.0, value)))
    elif name == "pixelate":
        block = max(1, int(value))
        small = pil.resize(
            (max(1, pil.width // block), max(1, pil.height // block)), Image.Resampling.NEAREST
        )
        result = small.resize(pil.size, Image.Resampling.NEAREST)
    else:
        result = pil
    return _from_pil(result)


def _invert(image: QImage) -> QImage:
    conv = image.convertToFormat(QImage.Format_ARGB32)
    width, height = conv.width(), conv.height()
    raw = conv.bits()
    import numpy as np

    arr = np.frombuffer(raw, np.uint8).reshape(height, conv.bytesPerLine())[:, : width * 4]
    arr = arr.reshape(height, width, 4).copy()
    arr[:, :, :3] = 255 - arr[:, :, :3]
    return array_to_image(arr)


def _levels(image: QImage, black: float, white: float, gamma: float) -> QImage:
    import numpy as np

    _, arr = image_to_array(image)
    black = max(0.0, min(254.0, float(black)))
    white = max(black + 1.0, min(255.0, float(white)))
    gamma = max(0.05, float(gamma))
    rgb = arr[:, :, :3].astype(np.float32)
    normalized = np.clip((rgb - black) / (white - black), 0.0, 1.0)
    arr[:, :, :3] = (np.power(normalized, 1.0 / gamma) * 255.0).astype(np.uint8)
    return array_to_image(arr)


def _hue(image: QImage, shift: float) -> QImage:
    pil = _to_pil(image)
    hsv = pil.convert("HSV")
    h, s, v = hsv.split()
    offset = int(round(shift)) % 256
    h = h.point(lambda value: (value + offset) % 256)
    merged = Image.merge("HSV", (h, s, v)).convert("RGBA")
    return _from_pil(merged)


def _vignette(image: QImage, strength: float) -> QImage:
    import numpy as np

    _, arr = image_to_array(image)
    height, width = arr.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    cx, cy = width / 2.0, height / 2.0
    dist = np.sqrt(((xx - cx) / max(1.0, cx)) ** 2 + ((yy - cy) / max(1.0, cy)) ** 2)
    dist = np.clip(dist / np.sqrt(2.0), 0.0, 1.0)
    factor = 1.0 - max(0.0, min(1.0, float(strength))) * (dist ** 2)
    arr[:, :, :3] = (arr[:, :, :3].astype(np.float32) * factor[:, :, None]).astype(np.uint8)
    return array_to_image(arr)


def _motion_blur(image: QImage, angle: float, distance: float) -> QImage:
    import math

    import numpy as np

    _, arr = image_to_array(image)
    steps = max(2, int(abs(distance) // 2))
    dx = math.cos(math.radians(angle)) * (distance / steps)
    dy = math.sin(math.radians(angle)) * (distance / steps)
    acc = np.zeros_like(arr, dtype=np.float32)
    for step in range(steps):
        offset_x = int(round(dx * step))
        offset_y = int(round(dy * step))
        acc += np.roll(np.roll(arr, offset_y, axis=0), offset_x, axis=1)
    arr[:, :, :] = (acc / steps).astype(np.uint8)
    return array_to_image(arr)


def apply_to_document(doc, name: str, value: float = 0.0, label: str | None = None,
                      options: dict | None = None) -> bool:
    layer = doc.active_layer()
    if layer is None:
        return False
    if layer.locked:
        return False
    tx = doc.history.begin(label or ("Filtre " + name))
    bounds = doc.selection_bounds()
    if not doc.has_selection():
        bounds = doc.rect()
    tx.touch(layer, bounds)
    full = bounds == doc.rect()
    source = layer.image if full else layer.image.copy(bounds)
    if name == "invert":
        result = _invert(source)
    else:
        result = apply(source, name, value, options=options)
    from PySide6.QtGui import QPainter

    mask = doc.mask_for_image()
    if mask is not None:
        local_mask = mask if full else mask.copy(bounds)
        masked = result.copy()
        mask_painter = QPainter(masked)
        mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        mask_painter.drawImage(0, 0, local_mask)
        mask_painter.end()
        result = masked
    painter = QPainter(layer.image)
    if mask is not None:
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(bounds.topLeft(), result)
    else:
        if doc.has_selection():
            painter.setClipRegion(doc.selection)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(bounds.topLeft(), result)
    painter.end()
    doc.invalidate(bounds)
    tx.commit()
    return True


def fill_color(image: QImage, rect: QRect, color: QColor) -> QImage:
    out = image.copy()
    from PySide6.QtGui import QPainter

    painter = QPainter(out)
    painter.setCompositionMode(QPainter.CompositionMode_Source)
    painter.fillRect(rect, color)
    painter.end()
    return out


def _diff_mask(arr, target, tolerance: int):
    import numpy as np

    if tolerance <= 0:
        packed = arr.view(np.uint32)[..., 0]
        value = int.from_bytes(np.asarray(target, dtype=np.uint8).tobytes(), "little")
        return packed == value
    diff = np.zeros(arr.shape[:2], np.uint8)
    for channel in range(4):
        values = arr[:, :, channel]
        np.maximum(diff, np.maximum(values, target[channel]) - np.minimum(
            values, target[channel]), out=diff)
    return diff <= tolerance


def _mask_from_array(arr, x: int, y: int, tolerance: int, clip=None):
    import numpy as np

    height, width = arr.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        return None
    match = _diff_mask(arr, arr[y, x], tolerance)
    if clip is not None:
        match &= clip
    if not match[y, x]:
        return None
    if match.all():
        return np.ones((height, width), bool)
    return _scanline(match, x, y)


def _scanline(match, x: int, y: int):
    from bisect import bisect_left, bisect_right

    import numpy as np

    height, width = match.shape
    padded = np.zeros((height, width + 2), np.int8)
    padded[:, 1:-1] = match
    diff = np.diff(padded, axis=1)
    stride = width + 1
    starts = (np.flatnonzero(diff.ravel() == 1) % stride).tolist()
    ends = (np.flatnonzero(diff.ravel() == -1) % stride).tolist()
    counts = (diff == 1).sum(axis=1)
    offsets = np.zeros(height + 1, np.int64)
    np.cumsum(counts, out=offsets[1:])
    offsets = offsets.tolist()

    begin = offsets[y]
    end = offsets[y + 1]
    index = bisect_right(starts[begin:end], x) - 1
    if index < 0 or x >= ends[begin + index]:
        return None

    filled = np.zeros((height, width), bool)
    visited: set = {(y, index)}
    stack = [(y, index)]
    while stack:
        row, idx = stack.pop()
        begin = offsets[row]
        left = starts[begin + idx]
        right = ends[begin + idx]
        filled[row, left:right] = True
        for neighbor in (row - 1, row + 1):
            if not (0 <= neighbor < height):
                continue
            nb = offsets[neighbor]
            ne = offsets[neighbor + 1]
            if nb == ne:
                continue
            nstarts = starts[nb:ne]
            nends = ends[nb:ne]
            i0 = bisect_right(nends, left)
            i1 = bisect_left(nstarts, right)
            for j in range(i0, max(i0, i1)):
                key = (neighbor, j)
                if key not in visited:
                    visited.add(key)
                    stack.append(key)
    return filled


def flood_mask(image: QImage, x: int, y: int, tolerance: int, clip=None):
    conv, arr = image_array_view(image)
    return _mask_from_array(arr, x, y, int(tolerance), clip)


def color_range_mask(image: QImage, color: QColor, tolerance: int):
    conv, arr = image_array_view(image)
    return _diff_mask(arr, np.array(color_bgra(color), dtype=np.uint8), int(tolerance))


def pattern_fill(image: QImage, x: int, y: int, pattern_path: str, scale: float = 100.0,
                 tolerance: int = 0, clip_region=None) -> tuple[QImage | None, QRect]:
    from PySide6.QtGui import QBrush, QPainter

    tile = QImage(str(pattern_path))
    if tile.isNull():
        return None, QRect()
    height, width = image.height(), image.width()
    clip = region_mask(clip_region, width, height)
    conv, arr = image_array_view(image)
    mask = _mask_from_array(arr, x, y, int(tolerance), clip)
    if mask is None or not mask.any():
        return None, QRect()
    bounds = mask_bbox(mask)
    factor = max(1.0, float(scale)) / 100.0
    if abs(factor - 1.0) > 0.01:
        tile = tile.scaled(max(1, int(tile.width() * factor)),
                           max(1, int(tile.height() * factor)),
                           Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    canvas = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.fillRect(canvas.rect(), QBrush(tile))
    painter.end()
    local = mask[bounds.top(): bounds.bottom() + 1, bounds.left(): bounds.right() + 1]
    alpha = mask_from_array(local)
    if alpha is not None:
        painter = QPainter(canvas)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, alpha)
        painter.end()
    return canvas, bounds


def flood_fill(image: QImage, x: int, y: int, color: QColor, tolerance: int = 0,
               clip_region=None) -> tuple[QImage | None, QRect]:
    import numpy as np

    height, width = image.height(), image.width()
    clip = region_mask(clip_region, width, height)
    conv, arr = image_array_view(image)
    mask = _mask_from_array(arr, x, y, int(tolerance), clip)
    if mask is None or not mask.any():
        return None, QRect()
    bounds = mask_bbox(mask)
    crop = np.ascontiguousarray(
        arr[bounds.top(): bounds.bottom() + 1, bounds.left(): bounds.right() + 1])
    local = mask[bounds.top(): bounds.bottom() + 1, bounds.left(): bounds.right() + 1]
    packed = crop.view(np.uint32)[..., 0]
    packed[local] = int.from_bytes(bytes(color_bgra(color)), "little")
    return array_to_image(crop), bounds
