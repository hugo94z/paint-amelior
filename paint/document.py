from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal
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

BLEND = {
    "normal": QPainter.CompositionMode_SourceOver,
    "multiply": QPainter.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode_Screen,
    "overlay": QPainter.CompositionMode_Overlay,
    "darken": QPainter.CompositionMode_Darken,
    "lighten": QPainter.CompositionMode_Lighten,
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
        self.floating: QImage | None = None
        self.floating_pos = QPoint(0, 0)
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
                        name: str | None = None) -> None:
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
        self.invalidate_all()
        self.mark_modified(True)

    def _recomposite(self, rect: QRect) -> None:
        painter = QPainter(self._cache)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(rect, Qt.transparent)
        visible = [layer for layer in self.layers if layer.visible and layer.opacity > 0.0]
        if (len(visible) == 1 and visible[0].blend == "normal"
                and visible[0].opacity >= 0.999):
            painter.drawImage(rect, visible[0].image, rect)
            painter.end()
            return
        first = True
        for layer in visible:
            painter.setOpacity(layer.opacity)
            mode = QPainter.CompositionMode_SourceOver if first else BLEND.get(
                layer.blend, QPainter.CompositionMode_SourceOver
            )
            painter.setCompositionMode(mode)
            painter.drawImage(rect, layer.image, rect)
            first = False
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

    def set_selection(self, region: QRegion | None, path: QPainterPath | None = None) -> None:
        if region is not None and region.isEmpty():
            region = None
        self.selection = region
        if region is None:
            self.selection_path = None
        elif path is not None:
            self.selection_path = path
        self.selection_changed.emit()

    def select_all(self) -> None:
        path = QPainterPath()
        path.addRect(self.rect())
        self.set_selection(QRegion(self.rect()), path)

    def invert_selection(self) -> None:
        if not self.has_selection():
            self.select_all()
            return
        region = QRegion(self.rect()).subtracted(self.selection)
        outer = QPainterPath()
        outer.addRect(self.rect())
        path = outer.subtracted(self.selection_path) if self.selection_path is not None else None
        self.set_selection(region, path)

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
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand(label, layers, before_images, after_images,
                                                before_size, after_size))
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()
        self.mark_modified(True)

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
        self.floating = None
        self.history.clear()
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.mark_modified(True)

    def mask_region_for_fill(self):
        return self.selection
