from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage
from PIL import Image, ImageEnhance, ImageFilter

from .utils import array_to_image, color_bgra, image_to_array, mask_bbox, region_mask


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
    if name == "invert":
        result = _invert(layer.image)
    else:
        result = apply(layer.image, name, value, options=options)
    from PySide6.QtGui import QPainter

    mask = doc.mask_for_image()
    if mask is not None:
        masked = result.copy()
        mask_painter = QPainter(masked)
        mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        mask_painter.drawImage(0, 0, mask)
        mask_painter.end()
        result = masked
    painter = QPainter(layer.image)
    if mask is not None:
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, result)
    else:
        if doc.has_selection():
            painter.setClipRegion(doc.selection)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(0, 0, result)
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


def flood_mask(image: QImage, x: int, y: int, tolerance: int, clip=None):
    import numpy as np

    _, arr = image_to_array(image)
    height, width = arr.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        return None
    target = arr[y, x].astype(np.int16)
    diff = np.zeros((height, width), np.uint8)
    for channel in range(4):
        channel_diff = np.abs(arr[:, :, channel].astype(np.int16) - int(target[channel]))
        channel_diff = channel_diff.astype(np.uint8)
        np.maximum(diff, channel_diff, out=diff)
    match = diff <= tolerance
    if clip is not None:
        match &= clip
    if not match[y, x]:
        return None

    if match.all():
        return np.ones((height, width), bool)

    cache: dict = {}

    def runs(row: int):
        r = cache.get(row)
        if r is None:
            line = match[row]
            d = np.diff(np.concatenate(([0], line.view(np.int8), [0])))
            r = (np.flatnonzero(d == 1), np.flatnonzero(d == -1))
            cache[row] = r
        return r

    start_end = runs(y)
    index = int(np.searchsorted(start_end[0], x, side="right")) - 1
    if index < 0 or x >= start_end[1][index]:
        return None

    filled = np.zeros((height, width), bool)
    visited: set = set()
    stack = [(y, index)]
    while stack:
        row, idx = stack.pop()
        if (row, idx) in visited:
            continue
        visited.add((row, idx))
        starts, ends = runs(row)
        left = int(starts[idx])
        right = int(ends[idx])
        filled[row, left:right] = True
        for neighbor in (row - 1, row + 1):
            if not (0 <= neighbor < height):
                continue
            nstarts, nends = runs(neighbor)
            i0 = int(np.searchsorted(nends, left, side="right"))
            i1 = int(np.searchsorted(nstarts, right, side="left"))
            for j in range(i0, max(i0, i1)):
                if (neighbor, j) not in visited:
                    stack.append((neighbor, j))
    return filled


def color_range_mask(image: QImage, color: QColor, tolerance: int):
    import numpy as np

    _, arr = image_to_array(image)
    target = np.array(color_bgra(color), dtype=np.int16)
    diff = np.zeros(arr.shape[:2], np.uint8)
    for channel in range(4):
        channel_diff = np.abs(arr[:, :, channel].astype(np.int16) - int(target[channel]))
        channel_diff = channel_diff.astype(np.uint8)
        np.maximum(diff, channel_diff, out=diff)
    return diff <= tolerance


def flood_fill(image: QImage, x: int, y: int, color: QColor, tolerance: int = 0,
               clip_region=None) -> tuple[QImage | None, QRect]:
    height, width = image.height(), image.width()
    clip = region_mask(clip_region, width, height)
    mask = flood_mask(image, x, y, int(tolerance), clip)
    if mask is None or not mask.any():
        return None, QRect()
    bounds = mask_bbox(mask)
    _, arr = image_to_array(image)
    arr[mask] = color_bgra(color)
    crop = arr[bounds.top(): bounds.bottom() + 1, bounds.left(): bounds.right() + 1]
    return array_to_image(crop), bounds
