from __future__ import annotations

import time
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
from .layer import Layer, LayerGroup
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
    def __init__(self, label: str, layers, before, after, before_size: QSize, after_size: QSize,
                 before_masks=None, after_masks=None, before_dpi=None, after_dpi=None):
        self.label = label
        self.layers = list(layers)
        self.before = list(before)
        self.after = list(after)
        self.before_masks = list(before_masks) if before_masks is not None else None
        self.after_masks = list(after_masks) if after_masks is not None else None
        self.before_size = QSize(before_size)
        self.after_size = QSize(after_size)
        self.before_dpi = before_dpi
        self.after_dpi = after_dpi

    def nbytes(self) -> int:
        total = sum(image.sizeInBytes() for image in self.before) + sum(
            image.sizeInBytes() for image in self.after
        )
        for masks in (self.before_masks, self.after_masks):
            total += sum(mask.sizeInBytes() for mask in (masks or []) if mask is not None)
        return total

    def restore(self, doc, use_before: bool) -> None:
        images = self.before if use_before else self.after
        masks = self.before_masks if use_before else self.after_masks
        for index, (layer, image) in enumerate(zip(self.layers, images)):
            layer.image = image
            if masks is not None:
                layer.mask = masks[index]
        if use_before and self.before_dpi is not None:
            doc.dpi = self.before_dpi
        elif not use_before and self.after_dpi is not None:
            doc.dpi = self.after_dpi
        doc.restore_image_state(self.before_size if use_before else self.after_size)


class LayerPropsCommand:
    def __init__(self, label: str, layer, before: dict, after: dict, merge_key: str = ""):
        self.label = label
        self.layer = layer
        self.before = before
        self.after = after
        self.merge_key = merge_key
        self.bounds = None
        self._stamp = time.monotonic()

    def nbytes(self) -> int:
        return 0

    def merge(self, after: dict) -> bool:
        if time.monotonic() - self._stamp > 1.5:
            return False
        self.after = after
        self._stamp = time.monotonic()
        return True

    def restore(self, doc, use_before: bool) -> None:
        self.layer.restore(self.before if use_before else self.after)
        doc.invalidate_all()
        doc.layers_changed.emit()


class GroupPropsCommand:
    def __init__(self, label: str, group, before: dict, after: dict, merge_key: str = ""):
        self.label = label
        self.group = group
        self.before = before
        self.after = after
        self.merge_key = merge_key
        self.bounds = None
        self._stamp = time.monotonic()

    def nbytes(self) -> int:
        return 0

    def merge(self, after: dict) -> bool:
        if time.monotonic() - self._stamp > 1.5:
            return False
        self.after = after
        self._stamp = time.monotonic()
        return True

    def restore(self, doc, use_before: bool) -> None:
        self.group.restore(self.before if use_before else self.after)
        doc.invalidate_all()
        doc.layers_changed.emit()


class Document(QObject):
    dirty = Signal(QRect)
    layers_changed = Signal()
    selection_changed = Signal()
    history_changed = Signal()
    modified_changed = Signal(bool)
    size_changed = Signal()

    def __init__(self, size: QSize, parent=None, undo_budget: int = 400 * 1024 * 1024,
                 dpi: int = 96):
        super().__init__(parent)
        self._size = QSize(max(1, size.width()), max(1, size.height()))
        self.dpi = max(36, min(1200, int(dpi)))
        self.layers: list[Layer] = []
        self.groups: list[LayerGroup] = []
        self.active_index = -1
        self.selection: QRegion | None = None
        self.selection_path: QPainterPath | None = None
        self.selection_mask: QImage | None = None
        self.selection_tint: QImage | None = None
        self.selection_feather = 0
        self.floating: QImage | None = None
        self.floating_pos = QPoint(0, 0)
        self.frames: list[dict] = []
        self.guides_h: list[float] = []
        self.guides_v: list[float] = []
        self.guides_visible = True
        self.preview_image: QImage | None = None
        self.path: Path | None = None
        self._modified = False
        self._cache = QImage(self._size, QImage.Format_ARGB32_Premultiplied)
        self._cache.fill(Qt.transparent)
        self.history = History(self, undo_budget)
        self.history.changed.connect(self.history_changed)

    @classmethod
    def new(cls, width: int = 1600, height: int = 1000, background: QColor | None = None,
            undo_budget: int = 400 * 1024 * 1024, dpi: int = 96) -> "Document":
        doc = cls(QSize(width, height), undo_budget=undo_budget, dpi=dpi)
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

    def group_by_id(self, group_id: int | None) -> LayerGroup | None:
        if group_id is None:
            return None
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def layer_index(self, layer_id: int) -> int:
        for index, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return index
        return -1

    def add_layer_raw(self, layer: Layer) -> Layer:
        self.layers.append(layer)
        if self.active_index < 0:
            self.active_index = 0
        return layer

    def _snapshot(self) -> dict:
        return {
            "layers": [(layer, layer.snapshot()) for layer in self.layers],
            "groups": [(group, group.snapshot()) for group in self.groups],
            "active": self.active_index,
        }

    def restore_state(self, state: dict) -> None:
        layers = []
        for layer, data in state["layers"]:
            layer.restore(data)
            layers.append(layer)
        self.layers = layers
        groups = []
        for group, data in state.get("groups", []):
            group.restore(data)
            groups.append(group)
        self.groups = groups
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
        active = self.active_layer()
        layer.group_id = active.group_id if active is not None else None
        index = self.active_index + 1 if self.active_index >= 0 else len(self.layers)
        self.layers.insert(index, layer)
        self.active_index = index
        self._compact_groups()
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
        copy.group_id = layer.group_id
        copy.styles = {key: dict(value) for key, value in layer.styles.items()}
        self.layers.insert(self.active_index + 1, copy)
        self.active_index += 1
        self._compact_groups()
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
        self._compact_groups()
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
        self._compact_groups()
        self.history.push(LayerCommand("Réorganisation des calques", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()

    def add_group(self, name: str | None = None, indices: list[int] | None = None) -> LayerGroup:
        before = self._snapshot()
        group = LayerGroup(name or f"Groupe {len(self.groups) + 1}")
        self.groups.append(group)
        if indices is None:
            indices = [self.active_index]
        for index in sorted({int(value) for value in indices}):
            if 0 <= index < len(self.layers):
                self.layers[index].group_id = group.id
        self._compact_groups()
        self.history.push(LayerCommand("Nouveau groupe", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)
        return group

    def remove_group(self, group_id: int, delete_layers: bool = False) -> None:
        group = self.group_by_id(group_id)
        if group is None:
            return
        before = self._snapshot()
        if delete_layers:
            def belongs(layer) -> bool:
                return self._group_contains(group_id, layer.group_id)

            self.layers = [layer for layer in self.layers if not belongs(layer)]
            self.groups = [item for item in self.groups
                           if item.id != group_id and not self._group_contains(group_id, item.parent)]
        else:
            for layer in self.layers:
                if layer.group_id == group_id:
                    layer.group_id = group.parent
            for child in self.groups:
                if child.parent == group_id:
                    child.parent = group.parent
            self.groups = [item for item in self.groups if item.id != group_id]
        if not self.layers:
            self.add_layer_raw(Layer("Calque 1", self._size))
        self.active_index = min(max(0, self.active_index), len(self.layers) - 1)
        self._compact_groups()
        self.history.push(LayerCommand(
            "Suppression du groupe" if delete_layers else "Dissolution du groupe",
            before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def assign_to_group(self, indices, group_id: int | None) -> None:
        if group_id is not None and self.group_by_id(group_id) is None:
            return
        before = self._snapshot()
        changed = False
        for index in sorted({int(value) for value in indices}):
            if 0 <= index < len(self.layers):
                layer = self.layers[index]
                if layer.group_id != group_id:
                    layer.group_id = group_id
                    changed = True
        if not changed:
            return
        self._compact_groups()
        self.history.push(LayerCommand("Déplacement dans un groupe", before,
                                       self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def set_group_props(self, group_id: int, visible: bool | None = None,
                        opacity: float | None = None, blend: str | None = None,
                        name: str | None = None, expanded: bool | None = None,
                        parent: int | None = None) -> None:
        group = self.group_by_id(group_id)
        if group is None:
            return
        if expanded is not None:
            group.expanded = bool(expanded)
            self.layers_changed.emit()
            return
        before = group.snapshot()
        visual = False
        refresh = False
        changed: list[str] = []
        if visible is not None and bool(visible) != group.visible:
            group.visible = bool(visible)
            visual = True
            changed.append("visible")
        if opacity is not None:
            value = max(0.0, min(1.0, opacity))
            if value != group.opacity:
                group.opacity = value
                visual = True
                changed.append("opacity")
        if blend is not None and blend in BLEND and blend != group.blend:
            group.blend = blend
            visual = True
            changed.append("blend")
        if name is not None and name and name != group.name:
            group.name = name
            refresh = True
            changed.append("name")
        if parent is not None or (parent is None and changed and False):
            if self._valid_group_parent(group_id, parent):
                if group.parent != parent:
                    group.parent = parent
                    refresh = True
                    changed.append("parent")
        if visual:
            self.invalidate_all()
        if refresh:
            self.layers_changed.emit()
        if not changed:
            return
        labels = {
            "visible": "Visibilité du groupe", "opacity": "Opacité du groupe",
            "blend": "Mode de fusion du groupe", "name": "Renommage du groupe",
            "parent": "Parent du groupe",
        }
        after = group.snapshot()
        last = self.history._undo[-1] if self.history._undo else None
        key = ",".join(changed)
        if (isinstance(last, GroupPropsCommand) and last.group is group
                and last.merge_key == key and not self.history._redo and last.merge(after)):
            self.history.changed.emit()
        else:
            self.history.push(GroupPropsCommand(
                labels.get(changed[0], "Propriétés du groupe"), group, before, after, key))
        if changed == ["parent"]:
            self._compact_groups()
        self.mark_modified(True)

    def rebuild_tree(self, layer_ids_top: list[int], memberships: dict[int, int | None],
                     parents: dict[int, int | None]) -> None:
        by_id = {layer.id: layer for layer in self.layers}
        if len(layer_ids_top) != len(self.layers) or any(
                layer_id not in by_id for layer_id in layer_ids_top):
            return
        before = self._snapshot()
        self.layers = [by_id[layer_id] for layer_id in reversed(layer_ids_top)]
        for layer in self.layers:
            layer.group_id = memberships.get(layer.id)
        for group in self.groups:
            if group.id in parents:
                group.parent = parents[group.id]
        self._repair_groups()
        self.active_index = max(0, min(self.active_index, len(self.layers) - 1))
        self.history.push(LayerCommand("Réorganisation des calques", before,
                                       self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def _valid_group_parent(self, group_id: int, parent: int | None) -> bool:
        if parent is None:
            return True
        if parent == group_id:
            return False
        current = parent
        seen = 0
        while current is not None and seen < 64:
            if current == group_id:
                return False
            group = self.group_by_id(current)
            if group is None:
                return False
            current = group.parent
            seen += 1
        return True

    def _group_contains(self, group_id: int, child_id: int | None) -> bool:
        current = child_id
        seen = 0
        while current is not None and seen < 64:
            if current == group_id:
                return True
            group = self.group_by_id(current)
            if group is None:
                return False
            current = group.parent
            seen += 1
        return False

    def _repair_groups(self) -> None:
        ids = {group.id for group in self.groups}
        for layer in self.layers:
            if layer.group_id is not None and layer.group_id not in ids:
                layer.group_id = None
        for group in self.groups:
            if group.parent is not None and group.parent not in ids:
                group.parent = None
        for group in self.groups:
            if not self._valid_group_parent(group.id, group.parent):
                group.parent = None

    def _compact_groups(self) -> None:
        changed = False
        for group in self.groups:
            indices = [index for index, layer in enumerate(self.layers)
                       if layer.group_id == group.id]
            if not indices:
                continue
            start = indices[0]
            members = [self.layers[index] for index in indices]
            rest = [layer for layer in self.layers if layer.group_id != group.id]
            insert = sum(1 for layer in self.layers[:start] if layer.group_id != group.id)
            if insert + len(members) <= len(rest):
                candidate = rest[:insert] + members + rest[insert:]
                if candidate != self.layers:
                    active = self.active_layer()
                    self.layers = candidate
                    if active is not None and active in self.layers:
                        self.active_index = self.layers.index(active)
                    changed = True
        if changed:
            self.invalidate_all()

    def group_layer_indices(self, group_id: int) -> list[int]:
        direct = [index for index, layer in enumerate(self.layers)
                  if layer.group_id == group_id]
        for child in self.groups:
            if child.parent == group_id:
                direct.extend(self.group_layer_indices(child.id))
        return sorted(direct)

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
        before = layer.snapshot()
        visual = False
        refresh = False
        changed: list[str] = []
        if opacity is not None:
            value = max(0.0, min(1.0, opacity))
            if value != layer.opacity:
                layer.opacity = value
                visual = True
                changed.append("opacity")
        if blend is not None and blend in BLEND and blend != layer.blend:
            layer.blend = blend
            visual = True
            changed.append("blend")
        if visible is not None and bool(visible) != layer.visible:
            layer.visible = bool(visible)
            visual = True
            changed.append("visible")
        if name is not None and name and name != layer.name:
            layer.name = name
            refresh = True
            changed.append("name")
        if locked is not None and bool(locked) != layer.locked:
            layer.locked = bool(locked)
            refresh = True
            changed.append("locked")
        if lock_alpha is not None and bool(lock_alpha) != layer.lock_alpha:
            layer.lock_alpha = bool(lock_alpha)
            refresh = True
            changed.append("lock_alpha")
        if mask_enabled is not None and bool(mask_enabled) != layer.mask_enabled:
            layer.mask_enabled = bool(mask_enabled)
            visual = True
            refresh = True
            changed.append("mask_enabled")
        if visual:
            self.invalidate_all()
        if refresh:
            self.layers_changed.emit()
        if not changed:
            return
        labels = {
            "opacity": "Opacité du calque", "blend": "Mode de fusion",
            "visible": "Visibilité du calque", "name": "Renommage du calque",
            "locked": "Verrouillage du calque", "lock_alpha": "Verrouillage alpha",
            "mask_enabled": "Masque du calque",
        }
        self._push_props(layer, before, layer.snapshot(),
                         labels.get(changed[0], "Propriétés du calque"),
                         ",".join(changed))
        self.mark_modified(True)

    def _push_props(self, layer, before: dict, after: dict, label: str,
                    merge_key: str) -> None:
        last = self.history._undo[-1] if self.history._undo else None
        if (isinstance(last, LayerPropsCommand) and last.layer is layer
                and last.merge_key == merge_key and not self.history._redo
                and last.merge(after)):
            self.history.changed.emit()
            return
        self.history.push(LayerPropsCommand(label, layer, before, after, merge_key))

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
        active = self.active_layer()
        layer.group_id = active.group_id if active is not None else None
        index = self.active_index + 1 if self.active_index >= 0 else len(self.layers)
        self.layers.insert(index, layer)
        self.active_index = index
        self._compact_groups()
        self.history.push(LayerCommand("Calque de réglage", before, self._snapshot()))
        self.layers_changed.emit()
        self.invalidate_all()
        self.mark_modified(True)

    def _recomposite(self, rect: QRect) -> None:
        painter = QPainter(self._cache)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(rect, Qt.transparent)
        painter.end()
        self._render_tree(None, rect, self._cache)

    def _tree_items(self, parent_id: int | None):
        positions = {layer.id: index for index, layer in enumerate(self.layers)}
        items = []
        for layer in self.layers:
            if layer.group_id == parent_id:
                items.append((positions[layer.id], 0, "layer", layer))
        for group in self.groups:
            if group.parent != parent_id:
                continue
            indices = [positions[layer.id] for layer in self.layers
                       if self._group_contains(group.id, layer.group_id)]
            if indices:
                items.append((min(indices), 1, "group", group))
        items.sort(key=lambda item: (item[0], item[1]))
        return [(kind, obj) for _, _, kind, obj in items]

    def _render_tree(self, parent_id: int | None, rect: QRect, target: QImage) -> None:
        items = self._tree_items(parent_id)
        if not items:
            return
        painter = QPainter(target)
        first = True
        temp = None
        for kind, obj in items:
            if kind == "group":
                if not obj.visible or obj.opacity <= 0.0:
                    continue
                group_image = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
                group_image.fill(Qt.transparent)
                self._render_tree(obj.id, rect, group_image)
                painter.setOpacity(obj.opacity)
                mode = QPainter.CompositionMode_SourceOver if first else BLEND.get(
                    obj.blend, QPainter.CompositionMode_SourceOver)
                painter.setCompositionMode(mode)
                painter.drawImage(rect.topLeft(), group_image)
                painter.setOpacity(1.0)
                first = False
                continue
            layer = obj
            if not layer.visible or (layer.adjustment is None and layer.opacity <= 0.0):
                continue
            if layer.adjustment is not None:
                painter.end()
                self._apply_adjustment(layer, rect, target)
                painter = QPainter(target)
                first = False
                continue
            painter.setOpacity(layer.opacity)
            mode = QPainter.CompositionMode_SourceOver if first else BLEND.get(
                layer.blend, QPainter.CompositionMode_SourceOver
            )
            painter.setCompositionMode(mode)
            styled = self._styled_image(layer, rect) if layer.has_styles() else None
            has_mask = layer.mask is not None and layer.mask_enabled and not layer.mask.isNull()
            if has_mask or styled is not None:
                if temp is None or temp.size() != rect.size():
                    temp = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
                temp.fill(Qt.transparent)
                layer_painter = QPainter(temp)
                if styled is not None:
                    layer_painter.drawImage(0, 0, styled)
                else:
                    layer_painter.drawImage(0, 0, layer.image, rect.x(), rect.y(),
                                            rect.width(), rect.height())
                if has_mask:
                    layer_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                    layer_painter.drawImage(0, 0, layer.mask, rect.x(), rect.y(),
                                            rect.width(), rect.height())
                layer_painter.end()
                painter.drawImage(rect.topLeft(), temp)
            else:
                painter.drawImage(rect, layer.image, rect)
            first = False
        painter.end()

    def _styled_image(self, layer, rect: QRect) -> QImage:
        shadow = layer.styles.get("shadow", {})
        stroke = layer.styles.get("stroke", {})
        margin = 0
        if shadow.get("enabled"):
            margin = max(margin, int(abs(shadow.get("offset_x", 0))) + int(shadow.get("blur", 0)),
                         int(abs(shadow.get("offset_y", 0))) + int(shadow.get("blur", 0)))
        if stroke.get("enabled"):
            margin = max(margin, int(stroke.get("width", 0)))
        margin = max(0, margin)
        big = rect.adjusted(-margin, -margin, margin, margin).intersected(self.rect())
        if big.isEmpty():
            return QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
        out = QImage(big.size(), QImage.Format_ARGB32_Premultiplied)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        if shadow.get("enabled"):
            color = QColor(shadow.get("color", "#000000"))
            color.setAlphaF(max(0.0, min(1.0, float(shadow.get("opacity", 0.6)))))
            silhouette = self._silhouette(layer, big, color)
            offset_x = int(shadow.get("offset_x", 0))
            offset_y = int(shadow.get("offset_y", 0))
            blur = max(0, int(shadow.get("blur", 0)))
            positions = [(0, 0)]
            if blur > 0:
                import math

                for radius in (blur / 2.0, float(blur)):
                    for step in range(8):
                        angle = math.radians(step * 45)
                        positions.append((int(math.cos(angle) * radius),
                                          int(math.sin(angle) * radius)))
            painter.setOpacity(1.0 / len(positions))
            for dx, dy in positions:
                painter.drawImage(offset_x + dx - big.left(), offset_y + dy - big.top(),
                                  silhouette)
            painter.setOpacity(1.0)
        if stroke.get("enabled"):
            import math

            color = QColor(stroke.get("color", "#ffffff"))
            color.setAlphaF(max(0.0, min(1.0, float(stroke.get("opacity", 1.0)))))
            silhouette = self._silhouette(layer, big, color)
            width = max(1, int(stroke.get("width", 3)))
            for step in range(8):
                angle = math.radians(step * 45)
                dx = int(math.cos(angle) * width)
                dy = int(math.sin(angle) * width)
                painter.drawImage(dx, dy, silhouette)
        painter.drawImage(0, 0, layer.image, big.x(), big.y(), big.width(), big.height())
        painter.end()
        result = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.drawImage(big.left() - rect.left(), big.top() - rect.top(), out)
        painter.end()
        return result

    def _silhouette(self, layer, rect: QRect, color: QColor) -> QImage:
        image = QImage(rect.size(), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.drawImage(0, 0, layer.image, rect.x(), rect.y(), rect.width(), rect.height())
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(image.rect(), color)
        painter.end()
        return image

    def set_layer_styles(self, index: int, styles: dict) -> None:
        if not 0 <= index < len(self.layers):
            return
        layer = self.layers[index]
        before = layer.snapshot()
        layer.styles = {key: dict(value) for key, value in styles.items()}
        self.invalidate_all()
        self._push_props(layer, before, layer.snapshot(), "Styles du calque", "styles")
        self.mark_modified(True)

    def _apply_adjustment(self, layer, rect: QRect, target: QImage | None = None) -> None:
        from .filters import apply

        base = target if target is not None else self._cache
        crop = base.copy(rect)
        adjustment = layer.adjustment or {}
        try:
            adjusted = apply(crop, adjustment.get("type", "brightness"),
                             float(adjustment.get("value", 1.0)))
        except (ValueError, OSError):
            return
        painter = QPainter(base)
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

    def add_guide(self, orientation: str, value: float) -> None:
        if orientation == "h":
            self.guides_h.append(float(value))
        else:
            self.guides_v.append(float(value))
        self.mark_modified(True)

    def remove_guide(self, orientation: str, value: float, tolerance: float) -> bool:
        guides = self.guides_h if orientation == "h" else self.guides_v
        for index, existing in enumerate(guides):
            if abs(existing - value) <= tolerance:
                del guides[index]
                self.mark_modified(True)
                return True
        return False

    def clear_guides(self) -> None:
        if self.guides_h or self.guides_v:
            self.guides_h.clear()
            self.guides_v.clear()
            self.mark_modified(True)

    def snap_point(self, point: QPointF, tolerance: float = 6.0, grid: float = 0.0,
                   edges: bool = True) -> QPointF:
        x = float(point.x())
        y = float(point.y())
        best_x = x
        best_y = y
        margin_x = tolerance
        margin_y = tolerance
        candidates_x = list(self.guides_v)
        candidates_y = list(self.guides_h)
        if edges:
            candidates_x.extend((0.0, float(self._size.width())))
            candidates_y.extend((0.0, float(self._size.height())))
        for value in candidates_x:
            distance = abs(value - x)
            if distance <= margin_x:
                best_x = value
                margin_x = distance
        for value in candidates_y:
            distance = abs(value - y)
            if distance <= margin_y:
                best_y = value
                margin_y = distance
        if grid > 0:
            nearest_x = round(x / grid) * grid
            if abs(nearest_x - x) <= margin_x:
                best_x = nearest_x
                margin_x = abs(nearest_x - x)
            nearest_y = round(y / grid) * grid
            if abs(nearest_y - y) <= margin_y:
                best_y = nearest_y
        return QPointF(best_x, best_y)

    def is_modified(self) -> bool:
        return self._modified

    def _reset_cache(self) -> None:
        self._cache = QImage(self._size, QImage.Format_ARGB32_Premultiplied)
        self._cache.fill(Qt.transparent)
        self.guides_h = [value for value in self.guides_h
                         if 0.0 <= value <= float(self._size.height())]
        self.guides_v = [value for value in self.guides_v
                         if 0.0 <= value <= float(self._size.width())]

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
        before_masks = [layer.mask for layer in layers]
        before_size = QSize(self._size)
        after_images = []
        after_masks = []
        for layer in layers:
            image = layer.image
            mask = layer.mask
            if flip_h or flip_v:
                image = image.mirrored(flip_h, flip_v)
                if mask is not None:
                    mask = mask.mirrored(flip_h, flip_v)
            if angle:
                image = image.transformed(QTransform().rotate(angle), Qt.SmoothTransformation)
                if mask is not None:
                    mask = mask.transformed(QTransform().rotate(angle), Qt.SmoothTransformation)
            after_images.append(image.convertToFormat(QImage.Format_ARGB32_Premultiplied))
            after_masks.append(mask)
        after_size = QSize(before_size.height(), before_size.width()) if angle % 180 else QSize(before_size)
        self._size = after_size
        for layer, image, mask in zip(layers, after_images, after_masks):
            layer.image = image
            layer.mask = mask
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand(label, layers, before_images, after_images,
                                                before_size, after_size,
                                                before_masks, after_masks))
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
        before_masks = [layer.mask for layer in layers]
        before_size = QSize(self._size)
        after_images = [layer.image.copy(rect) for layer in layers]
        after_masks = [layer.mask.copy(rect) if layer.mask is not None else None
                       for layer in layers]
        after_size = QSize(rect.width(), rect.height())
        self._size = after_size
        for layer, image, mask in zip(layers, after_images, after_masks):
            layer.image = image
            layer.mask = mask
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand("Recadrage", layers, before_images, after_images,
                                                before_size, after_size,
                                                before_masks, after_masks))
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
        before_masks = [layer.mask for layer in layers]
        before_size = QSize(self._size)
        after_images = []
        after_masks = []
        for layer in layers:
            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            painter.drawImage(offset_x, offset_y, layer.image)
            painter.end()
            after_images.append(image)
            if layer.mask is not None:
                mask = QImage(width, height, QImage.Format_ARGB32)
                mask.fill(Qt.transparent)
                mask_painter = QPainter(mask)
                mask_painter.drawImage(offset_x, offset_y, layer.mask)
                mask_painter.end()
                after_masks.append(mask)
            else:
                after_masks.append(None)
        after_size = QSize(width, height)
        self._size = after_size
        for layer, image, mask in zip(layers, after_images, after_masks):
            layer.image = image
            layer.mask = mask
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self._reset_cache()
        self.history.push(ImageTransformCommand("Taille du canevas", layers, before_images,
                                                after_images, before_size, after_size,
                                                before_masks, after_masks))
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

    def resize_image(self, width: int, height: int, smooth: bool = True,
                     dpi: int | None = None) -> None:
        if width < 1 or height < 1:
            return
        if width > 16384 or height > 16384:
            return
        mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
        layers = list(self.layers)
        before_images = [layer.image for layer in layers]
        before_masks = [layer.mask for layer in layers]
        before_size = QSize(self._size)
        before_dpi = self.dpi
        after_images = []
        after_masks = []
        for layer in layers:
            image = layer.image.scaled(width, height, Qt.IgnoreAspectRatio, mode)
            after_images.append(image.convertToFormat(QImage.Format_ARGB32_Premultiplied))
            if layer.mask is not None:
                after_masks.append(layer.mask.scaled(
                    width, height, Qt.IgnoreAspectRatio, mode))
            else:
                after_masks.append(None)
        self._size = QSize(width, height)
        if dpi is not None:
            self.dpi = max(36, min(1200, int(dpi)))
        for layer, image, mask in zip(layers, after_images, after_masks):
            layer.image = image
            layer.mask = mask
        self._reset_cache()
        self.selection = None
        self.selection_path = None
        self.selection_mask = None
        self.selection_tint = None
        self.floating = None
        self.history.push(ImageTransformCommand(
            "Redimensionnement", layers, before_images, after_images,
            before_size, QSize(width, height), before_masks, after_masks,
            before_dpi, self.dpi))
        self.invalidate_all()
        self.size_changed.emit()
        self.selection_changed.emit()
        self.layers_changed.emit()
        self.mark_modified(True)

    def mask_region_for_fill(self):
        return self.selection
