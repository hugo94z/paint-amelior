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


def apply(image: QImage, name: str, value: float = 0.0, extra: float = 0.0) -> QImage:
    if name == "invert":
        return _invert(image)
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


def apply_to_document(doc, name: str, value: float = 0.0, label: str | None = None) -> bool:
    layer = doc.active_layer()
    if layer is None:
        return False
    tx = doc.history.begin(label or ("Filtre " + name))
    bounds = doc.selection_bounds()
    if not doc.has_selection():
        bounds = doc.rect()
    tx.touch(layer, bounds)
    if name == "invert":
        result = _invert(layer.image)
    else:
        result = apply(layer.image, name, value)
    from PySide6.QtGui import QPainter

    painter = QPainter(layer.image)
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


def _flood_fill_mask(image: QImage, x: int, y: int, tolerance: int, clip) -> "object":
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


def flood_fill(image: QImage, x: int, y: int, color: QColor, tolerance: int = 0,
               clip_region=None) -> tuple[QImage | None, QRect]:
    import numpy as np

    height, width = image.height(), image.width()
    clip = region_mask(clip_region, width, height)
    mask = _flood_fill_mask(image, x, y, int(tolerance), clip)
    if mask is None or not mask.any():
        return None, QRect()
    bounds = mask_bbox(mask)
    _, arr = image_to_array(image)
    arr[mask] = color_bgra(color)
    crop = arr[bounds.top(): bounds.bottom() + 1, bounds.left(): bounds.right() + 1]
    return array_to_image(crop), bounds
