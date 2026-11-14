from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPolygon,
    QRegion,
    QTransform,
)

from .history import History, LayerCommand
from .layer import Layer
from .utils import (
    array_to_image,
    blur_alpha,
    image_to_array,
    mask_from_array,
    mask_tint,
    region_from_mask,
    region_mask,
)

BLEND = {
    "normal": QPainter.CompositionMode_SourceOver,
    "multiply": QPainter.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode_Screen,
    "overlay": QPainter.CompositionMode_Overlay,
    "softlight": QPainter.CompositionMode_SoftLight,
    "hardlight": QPainter.CompositionMode_HardLight,
    "darken": QPainter.CompositionMode_Darken,
    "lighten": QPainter.CompositionMode_Lighten,
    "difference": QPainter.CompositionMode_Difference,
    "exclusion": QPainter.CompositionMode_Exclusion,
    "colordodge": QPainter.CompositionMode_ColorDodge,
    "colorburn": QPainter.CompositionMode_ColorBurn,
}


class ImageTransformCommand:
    def __init__(self, label: str, layers, before, after, before_size: QSize, after_size: QSize):
        self.label = label
        self.layers = list(layers)
        self.before = list(before)
        self.after = list(after)
        self.before_size = QSize(before_size)
        self.after_size = QSize(after_size)

    def nbytes(self) -> int:
        return sum(image.sizeInBytes() for image in self.before) + sum(
            image.sizeInBytes() for image in self.after
        )

    def restore(self, doc, use_before: bool) -> None:
        images = self.before if use_before else self.after
        for layer, image in zip(self.layers, images):
            layer.image = image
        doc.restore_image_state(self.before_size if use_before else self.after_size)


class Document(QObject):
    dirty = Signal(QRect)
    layers_changed = Signal()
    selection_changed = Signal()
    history_changed = Signal()
    modified_changed = Signal(bool)
    size_changed = Signal()

    def __init__(self, size: QSize, parent=None, undo_budget: int = 400 * 1024 * 1024):
        super().__init__(parent)
        self._size = QSize(max(1, size.width()), max(1, size.height()))
        self.layers: list[Layer] = []
        self.active_index = -1
        self.selection: QRegion | None = None
        self.selection_path: QPainterPath | None = None
        self.selection_mask: QImage | None = None
        self.selection_tint: QImage | None = None
        self.selection_feather = 0
        self.floating: QImage | None = None
        self.floating_pos = QPoint(0, 0)
        self.frames: list[dict] = []
        self.preview_image: QImage | None = None
        self.path: Path | None = None
        self._modified = False
        self._cache = QImage(self._size, QImage.Format_ARGB32_Premultiplied)
        self._cache.fill(Qt.transparent)
        self.history = History(self, undo_budget)
        self.history.changed.connect(self.history_changed)

    @classmethod
    def new(cls, width: int = 1600, height: int = 1000, background: QColor | None = None,
            undo_budget: int = 400 * 1024 * 1024) -> "Document":
        doc = cls(QSize(width, height), undo_budget=undo_budget)
        doc.add_layer_raw(Layer("Arrière-plan", doc.size,
                                background if background is not None else Qt.transparent))
        if background is not None:
            doc.add_layer_raw(Layer("Calque 1", doc.size))
        doc.active_index = len(doc.layers) - 1
        doc.history.clear()
        doc.invalidate_all()
        doc.mark_modified(False)
        return doc

    def rect(self) -> QRect:
        return QRect(0, 0, self._size.width(), self._size.height())

    @property
    def size(self) -> QSize:
        return self._size

    def active_layer(self) -> Layer | None:
        if 0 <= self.active_index < len(self.layers):
            return self.layers[self.active_index]
        return None

    def layer_by_id(self, layer_id: int) -> Layer | None:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def add_layer_raw(self, layer: Layer) -> Layer:
        self.layers.append(layer)
        if self.active_index < 0:
            self.active_index = 0
        return layer

    def _snapshot(self) -> dict:
        return {
            "layers": [(layer, layer.snapshot()) for layer in self.layers],
            "active": self.active_index,
        }

    def restore_state(self, state: dict) -> None:
        layers = []
        for layer, data in state["layers"]:
            layer.restore(data)
            layers.append(layer)
        self.layers = layers
        self.active_index = min(max(state["active"], 0), max(0, len(self.layers) - 1))
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self.invalidate_all()
        self.layers_changed.emit()
        self.selection_changed.emit()

    def add_layer(self, name: str | None = None, color: QColor | None = None,
                  label: str = "Nouveau calque") -> Layer:
        before = self._snapshot()
        layer = Layer(name or f"Calque {len(self.layers) + 1}", self.size, color)
        index = self.active_index + 1 if self.active_index >= 0 else len(self.layers)
        self.layers.insert(index, layer)
        self.active_index = index
        self.history.push(LayerCommand(label, before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        return layer

    def remove_layer(self, index: int | None = None) -> None:
        if len(self.layers) <= 1:
            return
        index = self.active_index if index is None else index
        if not 0 <= index < len(self.layers):
            return
        before = self._snapshot()
        del self.layers[index]
        self.active_index = min(index, len(self.layers) - 1)
        self.history.push(LayerCommand("Suppression du calque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def duplicate_layer(self) -> None:
        layer = self.active_layer()
        if layer is None:
            return
        before = self._snapshot()
        copy = Layer(layer.name + " copie", self.size)
        copy.image = layer.image.copy()
        copy.visible = layer.visible
        copy.opacity = layer.opacity
        copy.blend = layer.blend
        self.layers.insert(self.active_index + 1, copy)
        self.active_index += 1
        self.history.push(LayerCommand("Duplication du calque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def move_layer(self, index: int, delta: int) -> None:
        target = index + delta
        if not (0 <= index < len(self.layers) and 0 <= target < len(self.layers)):
            return
        before = self._snapshot()
        self.layers[index], self.layers[target] = self.layers[target], self.layers[index]
        self.active_index = target
        self.history.push(LayerCommand("Réorganisation des calques", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def reorder_layers(self, ids_top_to_bottom: list[int]) -> None:
        by_id = {layer.id: layer for layer in self.layers}
        try:
            new_top = [by_id[layer_id] for layer_id in ids_top_to_bottom]
        except KeyError:
            return
        if len(new_top) != len(self.layers):
            return
        if [layer.id for layer in new_top] == [layer.id for layer in reversed(self.layers)]:
            return
        active = self.active_layer()
        before = self._snapshot()
        self.layers = list(reversed(new_top))
        self.active_index = self.layers.index(active) if active in self.layers else 0
        self.history.push(LayerCommand("Réorganisation des calques", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def merge_down(self) -> None:
        index = self.active_index
        if index <= 0 or index >= len(self.layers):
            return
        before = self._snapshot()
        upper = self.layers[index]
        lower = self.layers[index - 1]
        painter = QPainter(lower.image)
        painter.setOpacity(upper.opacity)
        painter.setCompositionMode(BLEND.get(upper.blend, QPainter.CompositionMode_SourceOver))
        painter.drawImage(0, 0, upper.image)
        painter.end()
        del self.layers[index]
        self.active_index = index - 1
        self.history.push(LayerCommand("Fusion vers le bas", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self.layers) and index != self.active_index:
            self.active_index = index
            self.layers_changed.emit()

    def set_layer_props(self, index: int, opacity: float | None = None,
                        blend: str | None = None, visible: bool | None = None,
                        name: str | None = None, locked: bool | None = None,
                        lock_alpha: bool | None = None,
                        mask_enabled: bool | None = None) -> None:
        if not 0 <= index < len(self.layers):
            return
        layer = self.layers[index]
        if opacity is not None:
            layer.opacity = max(0.0, min(1.0, opacity))
        if blend is not None and blend in BLEND:
            layer.blend = blend
        if visible is not None:
            layer.visible = bool(visible)
        if name is not None and name:
            layer.name = name
        if locked is not None:
            layer.locked = bool(locked)
        if lock_alpha is not None:
            layer.lock_alpha = bool(lock_alpha)
        if mask_enabled is not None:
            layer.mask_enabled = bool(mask_enabled)
        self.invalidate_all()
        self.mark_modified(True)

    def is_active_locked(self) -> bool:
        layer = self.active_layer()
        return bool(layer is not None and layer.locked)

    def add_layer_mask(self, index: int | None = None, from_selection: bool = True) -> None:
        index = self.active_index if index is None else index
        if not 0 <= index < len(self.layers):
            return
        layer = self.layers[index]
        if layer.mask is not None:
            return
        before = self._snapshot()
        if from_selection and self.has_selection():
            if self.selection_mask is not None:
                layer.mask = self.selection_mask.copy()
            else:
                array = region_mask(self.selection, self._size.width(), self._size.height())
                layer.mask = mask_from_array(array) if array is not None else None
        if layer.mask is None:
            layer.mask = QImage(self._size, QImage.Format_ARGB32)
            layer.mask.fill(Qt.white)
        self.history.push(LayerCommand("Ajout d'un masque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def remove_layer_mask(self, index: int | None = None) -> None:
        index = self.active_index if index is None else index
        if not 0 <= index < len(self.layers):
            return
        layer = self.layers[index]
        if layer.mask is None:
            return
        before = self._snapshot()
        layer.mask = None
        self.history.push(LayerCommand("Suppression du masque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def apply_layer_mask(self, index: int | None = None) -> None:
        index = self.active_index if index is None else index
        if not 0 <= index < len(self.layers):
            return
        layer = self.layers[index]
        if layer.mask is None:
            return
        before = self._snapshot()
        painter = QPainter(layer.image)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, layer.mask)
        painter.end()
        layer.mask = None
        self.history.push(LayerCommand("Application du masque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def set_layer_adjustment(self, index: int, adjustment: dict | None) -> None:
        if not 0 <= index < len(self.layers):
            return
        before = self._snapshot()
        self.layers[index].adjustment = dict(adjustment) if adjustment else None
        self.history.push(LayerCommand("Réglage du calque", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def add_adjustment_layer(self, kind: str = "brightness", value: float = 1.15) -> None:
        labels = {
            "brightness": "Luminosité",
            "contrast": "Contraste",
            "saturation": "Saturation",
            "grayscale": "Niveaux de gris",
        }
        before = self._snapshot()
        layer = Layer("Réglage " + labels.get(kind, kind).lower(), self._size)
        layer.adjustment = {"type": kind, "value": float(value)}
        index = self.active_index + 1 if self.active_index >= 0 else len(self.layers)
        self.layers.insert(index, layer)
        self.active_index = index
        self.history.push(LayerCommand("Calque de réglage", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def _recomposite(self, rect: QRect) -> None:
        painter = QPainter(self._cache)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(rect, Qt.transparent)
        visible = [
            layer for layer in self.layers
            if layer.visible and (layer.adjustment is not None or layer.opacity > 0.0)
        ]
        if (len(visible) == 1 and visible[0].blend == "normal"
                and visible[0].opacity >= 0.999 and visible[0].mask is None
                and visible[0].adjustment is None):
            painter.drawImage(rect, visible[0].image, rect)
            painter.end()
            return
        first = True
        for layer in visible:
            if layer.adjustment is not None:
                painter.end()
                self._apply_adjustment(layer, rect)
                painter = QPainter(self._cache)
                first = False
                continue
            painter.setOpacity(layer.opacity)
            mode = QPainter.CompositionMode_SourceOver if first else BLEND.get(
                layer.blend, QPainter.CompositionMode_SourceOver
            )
            painter.setCompositionMode(mode)
            if layer.mask is not None and layer.mask_enabled and not layer.mask.isNull():
                temp = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
                temp.fill(Qt.transparent)
                layer_painter = QPainter(temp)
                layer_painter.drawImage(0, 0, layer.image, rect.x(), rect.y(),
                                        rect.width(), rect.height())
                layer_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                layer_painter.drawImage(0, 0, layer.mask, rect.x(), rect.y(),
                                        rect.width(), rect.height())
                layer_painter.end()
                painter.drawImage(rect.topLeft(), temp)
            else:
                painter.drawImage(rect, layer.image, rect)
            first = False
        painter.end()

    def _apply_adjustment(self, layer, rect: QRect) -> None:
        from .filters import apply

        crop = self._cache.copy(rect)
        adjustment = layer.adjustment or {}
        try:
            adjusted = apply(crop, adjustment.get("type", "brightness"),
                             float(adjustment.get("value", 1.0)))
        except (ValueError, OSError):
            return
        painter = QPainter(self._cache)
        painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
        if layer.mask is not None and layer.mask_enabled and not layer.mask.isNull():
            local_mask = layer.mask.copy(rect)
            temp = adjusted.copy()
            mask_painter = QPainter(temp)
            mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            mask_painter.drawImage(0, 0, local_mask)
            mask_painter.end()
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(rect.topLeft(), temp)
        else:
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(rect.topLeft(), adjusted)
        painter.end()

    def composite(self) -> QImage:
        return self._cache

    def invalidate(self, rect: QRect) -> None:
        r = rect.intersected(self.rect())
        if r.isEmpty():
            return
        self._recomposite(r)
        self.dirty.emit(r)
        self.mark_modified(True)

    def invalidate_all(self) -> None:
        self._recomposite(self.rect())
        self.dirty.emit(self.rect())

    def set_selection(self, region: QRegion | None, path: QPainterPath | None = None,
                      mask: QImage | None = None, feather: int = 0) -> None:
        if mask is None and feather > 0 and region is not None and not region.isEmpty():
            array = region_mask(region, self._size.width(), self._size.height())
            if array is not None:
                mask = mask_from_array(array, feather)
        if region is None and mask is not None:
            region = region_from_mask(mask)
        if region is not None and region.isEmpty():
            region = None
        self.selection = region
        self.selection_feather = int(feather)
        if region is None:
            self.selection_path = None
            self.selection_mask = None
            self.selection_tint = None
        else:
            if path is not None:
                self.selection_path = path
            self.selection_mask = mask
            self.selection_tint = mask_tint(mask) if mask is not None else None
        self.selection_changed.emit()

    def combine_selection(self, array, mode: str = "replace", feather: int = 0) -> None:
        width, height = self._size.width(), self._size.height()
        current = region_mask(self.selection, width, height) if self.has_selection() else None
        if current is None:
            current = ~array if mode == "subtract" else np.zeros_like(array)
        if mode == "add":
            combined = current | array
        elif mode == "subtract":
            combined = current & ~array
        elif mode == "intersect":
            combined = current & array
        else:
            combined = array
        if not combined.any():
            self.clear_selection()
            return
        mask = mask_from_array(combined, feather)
        if mask is None:
            self.clear_selection()
            return
        region = region_from_mask(mask)
        self.set_selection(region, None, mask, feather)

    def selection_array(self):
        if not self.has_selection():
            return None
        return region_mask(self.selection, self._size.width(), self._size.height())

    def mask_for_image(self) -> QImage | None:
        return self.selection_mask

    def select_all(self) -> None:
        path = QPainterPath()
        path.addRect(self.rect())
        self.set_selection(QRegion(self.rect()), path)

    def invert_selection(self) -> None:
        if not self.has_selection():
            self.select_all()
            return
        width, height = self._size.width(), self._size.height()
        current = self.selection_array()
        if current is None:
            self.select_all()
            return
        inverted = ~current
        if not inverted.any():
            self.clear_selection()
            return
        mask = mask_from_array(inverted, self.selection_feather)
        if mask is None:
            self.clear_selection()
            return
        region = region_from_mask(mask)
        path = None
        if self.selection_path is not None:
            outer = QPainterPath()
            outer.addRect(self.rect())
            path = outer.subtracted(self.selection_path)
        self.set_selection(region, path, mask if self.selection_feather else None,
                           self.selection_feather)

    def clear_selection(self) -> None:
        self.set_selection(None)

    def has_selection(self) -> bool:
        return self.selection is not None and not self.selection.isEmpty()

    def selection_bounds(self) -> QRect:
        return self.selection.boundingRect() if self.selection else self.rect()

    def mark_modified(self, value: bool = True) -> None:
        if self._modified != value:
            self._modified = value
            self.modified_changed.emit(value)

    def is_modified(self) -> bool:
        return self._modified

    def _reset_cache(self) -> None:
        self._cache = QImage(self._size, QImage.Format_ARGB32_Premultiplied)
        self._cache.fill(Qt.transparent)

    def restore_image_state(self, size: QSize) -> None:
        self._size = QSize(size)
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()

    def transform_image(self, angle: int = 0, flip_h: bool = False, flip_v: bool = False,
                        label: str = "Transformation") -> None:
        angle = int(angle) % 360
        if not angle and not flip_h and not flip_v:
            return
        layers = list(self.layers)
        if not layers:
            return
        before_images = [layer.image for layer in layers]
        before_size = QSize(self._size)
        after_images = []
        for layer in layers:
            image = layer.image
            if flip_h or flip_v:
                image = image.mirrored(flip_h, flip_v)
            if angle:
                image = image.transformed(QTransform().rotate(angle), Qt.SmoothTransformation)
            after_images.append(image.convertToFormat(QImage.Format_ARGB32_Premultiplied))
        after_size = QSize(before_size.height(), before_size.width()) if angle % 180 else QSize(before_size)
        self._size = after_size
        for layer, image in zip(layers, after_images):
            layer.image = image
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand(label, layers, before_images, after_images,
                                                before_size, after_size))
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()
        self.mark_modified(True)

    def crop(self, rect: QRect) -> None:
        rect = rect.intersected(self.rect())
        if rect.width() < 1 or rect.height() < 1:
            return
        layers = list(self.layers)
        before_images = [layer.image for layer in layers]
        before_size = QSize(self._size)
        after_images = [layer.image.copy(rect) for layer in layers]
        after_size = QSize(rect.width(), rect.height())
        self._size = after_size
        for layer, image in zip(layers, after_images):
            layer.image = image
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand("Recadrage", layers, before_images, after_images,
                                                before_size, after_size))
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()
        self.mark_modified(True)

    def resize_canvas(self, width: int, height: int, anchor: str = "center") -> None:
        if width < 1 or height < 1:
            return
        old_width, old_height = self._size.width(), self._size.height()
        if anchor in ("left", "top-left", "bottom-left"):
            offset_x = 0
        elif anchor in ("right", "top-right", "bottom-right"):
            offset_x = width - old_width
        else:
            offset_x = (width - old_width) // 2
        if anchor in ("top", "top-left", "top-right"):
            offset_y = 0
        elif anchor in ("bottom", "bottom-left", "bottom-right"):
            offset_y = height - old_height
        else:
            offset_y = (height - old_height) // 2
        layers = list(self.layers)
        before_images = [layer.image for layer in layers]
        before_size = QSize(self._size)
        after_images = []
        for layer in layers:
            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            painter.drawImage(offset_x, offset_y, layer.image)
            painter.end()
            after_images.append(image)
        after_size = QSize(width, height)
        self._size = after_size
        for layer, image in zip(layers, after_images):
            layer.image = image
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand("Taille du canevas", layers, before_images,
                                                after_images, before_size, after_size))
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()
        self.mark_modified(True)

    def transform_selection(self, angle: float = 0.0, scale_x: float = 1.0,
                            scale_y: float = 1.0) -> bool:
        layer = self.active_layer()
        if layer is None or not self.has_selection():
            return False
        bounds = self.selection.boundingRect().intersected(self.rect())
        if bounds.isEmpty():
            return False
        tx = self.history.begin("Transformation de la sélection")
        tx.touch(layer, bounds)
        image = layer.image.copy(bounds)
        local_mask = None
        if self.selection_mask is not None:
            local_mask = self.selection_mask.copy(bounds)
        else:
            array = region_mask(self.selection.translated(-bounds.left(), -bounds.top()),
                                bounds.width(), bounds.height())
            if array is None:
                tx.cancel()
                return False
            local_mask = mask_from_array(array)
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, local_mask)
        painter.end()
        painter = QPainter(layer.image)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        painter.drawImage(bounds.topLeft(), local_mask)
        painter.end()
        local = QTransform()
        local.translate(image.width() / 2.0, image.height() / 2.0)
        local.rotate(angle)
        local.scale(scale_x if abs(scale_x) >= 0.01 else 0.01,
                    scale_y if abs(scale_y) >= 0.01 else 0.01)
        local.translate(-image.width() / 2.0, -image.height() / 2.0)
        result = image.transformed(local, Qt.SmoothTransformation)
        new_pos = QPoint(
            bounds.center().x() - result.width() // 2,
            bounds.center().y() - result.height() // 2,
        )
        painter = QPainter(layer.image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(new_pos, result)
        painter.end()
        new_rect = QRect(new_pos, result.size())
        full_before = QImage(self._size, QImage.Format_ARGB32)
        full_before.fill(Qt.transparent)
        painter = QPainter(full_before)
        painter.drawImage(bounds.topLeft(), local_mask)
        painter.end()
        center = bounds.center()
        mask_transform = QTransform()
        mask_transform.translate(center.x(), center.y())
        mask_transform.rotate(angle)
        mask_transform.scale(scale_x if abs(scale_x) >= 0.01 else 0.01,
                             scale_y if abs(scale_y) >= 0.01 else 0.01)
        mask_transform.translate(-center.x(), -center.y())
        full_mask = full_before.transformed(mask_transform, Qt.SmoothTransformation)
        region = region_from_mask(full_mask)
        self.set_selection(region, None, full_mask, self.selection_feather)
        self.invalidate(bounds.united(new_rect))
        tx.commit()
        return True

    def resize_image(self, width: int, height: int, smooth: bool = True) -> None:
        if width < 1 or height < 1:
            return
        mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
        self._size = QSize(width, height)
        for layer in self.layers:
            layer.image = layer.image.scaled(width, height, Qt.IgnoreAspectRatio, mode)
            layer.image = layer.image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        self._reset_cache()
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self.history.clear()
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.mark_modified(True)

    def mask_region_for_fill(self):
        return self.selection
