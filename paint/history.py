from __future__ import annotations

from PySide6.QtCore import QObject, QRect, Signal
from PySide6.QtGui import QImage, QPainter

TILE = 128


class TileCommand:
    def __init__(self, label: str, before: dict, after: dict, bounds: QRect):
        self.label = label
        self.before = before
        self.after = after
        self.bounds = bounds

    def nbytes(self) -> int:
        return sum(img.sizeInBytes() for img in self.before.values()) + sum(
            img.sizeInBytes() for img in self.after.values()
        )

    def restore(self, doc, use_before: bool) -> None:
        tiles = self.before if use_before else self.after
        for (layer_id, tx, ty), img in tiles.items():
            layer = doc.layer_by_id(layer_id)
            if layer is None:
                continue
            painter = QPainter(layer.image)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.drawImage(tx * TILE, ty * TILE, img)
            painter.end()
        doc.invalidate(self.bounds)


class LayerCommand:
    def __init__(self, label: str, before: dict, after: dict):
        self.label = label
        self.before = before
        self.after = after
        self.bounds = None

    def nbytes(self) -> int:
        return 0

    def restore(self, doc, use_before: bool) -> None:
        doc.restore_state(self.before if use_before else self.after)


class Transaction:
    def __init__(self, history: "History", label: str):
        self.history = history
        self.doc = history.doc
        self.label = label
        self.before: dict = {}
        self.bounds = QRect()
        self._committed = False

    def touch(self, layer, rect: QRect) -> None:
        if rect is None:
            return
        r = rect.intersected(self.doc.rect())
        if r.isEmpty():
            return
        self.bounds = r if self.bounds.isNull() else self.bounds.united(r)
        width, height = self.doc.rect().width(), self.doc.rect().height()
        for ty in range(r.top() // TILE, r.bottom() // TILE + 1):
            for tx in range(r.left() // TILE, r.right() // TILE + 1):
                key = (layer.id, tx, ty)
                if key in self.before:
                    continue
                x = tx * TILE
                y = ty * TILE
                w = min(TILE, width - x)
                h = min(TILE, height - y)
                if w > 0 and h > 0:
                    self.before[key] = layer.image.copy(x, y, w, h)

    def commit(self) -> None:
        if self._committed or not self.before:
            self._committed = True
            return
        self._committed = True
        after: dict = {}
        for layer_id, tx, ty in self.before:
            layer = self.doc.layer_by_id(layer_id)
            if layer is None:
                continue
            x = tx * TILE
            y = ty * TILE
            w = min(TILE, layer.image.width() - x)
            h = min(TILE, layer.image.height() - y)
            if w > 0 and h > 0:
                after[(layer_id, tx, ty)] = layer.image.copy(x, y, w, h)
        self.history.push(TileCommand(self.label, self.before, after, self.bounds))

    def cancel(self) -> None:
        self._committed = True
        self.before = {}


class History(QObject):
    changed = Signal()

    def __init__(self, doc, budget_bytes: int = 400 * 1024 * 1024):
        super().__init__(doc)
        self.doc = doc
        self.budget_bytes = budget_bytes
        self._undo: list = []
        self._redo: list = []
        self._bytes = 0

    def begin(self, label: str) -> Transaction:
        return Transaction(self, label)

    @staticmethod
    def _size(command) -> int:
        value = getattr(command, "_cached_nbytes", None)
        if value is None:
            value = command.nbytes()
            command._cached_nbytes = value
        return value

    def push(self, command) -> None:
        self._undo.append(command)
        self._bytes += self._size(command)
        self._redo.clear()
        self._trim()
        self.changed.emit()
        self.doc.mark_modified(True)

    def _trim(self) -> None:
        while self._bytes > self.budget_bytes and len(self._undo) > 1:
            dropped = self._undo.pop(0)
            self._bytes -= self._size(dropped)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def position(self) -> int:
        return len(self._undo)

    @property
    def length(self) -> int:
        return len(self._undo) + len(self._redo)

    @property
    def labels(self) -> list[str]:
        return [cmd.label for cmd in self._undo]

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.restore(self.doc, True)
        self._redo.append(command)
        self._bytes -= self._size(command)
        self.changed.emit()
        self.doc.mark_modified(True)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.restore(self.doc, False)
        self._undo.append(command)
        self._bytes += self._size(command)
        self.changed.emit()
        self.doc.mark_modified(True)
        return True

    def go_to(self, index: int) -> None:
        index = max(0, min(index, self.length))
        guard = 0
        while len(self._undo) > index and guard < 5000:
            self.undo()
            guard += 1
        while len(self._undo) < index and self._redo and guard < 5000:
            self.redo()
            guard += 1

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._bytes = 0
        self.changed.emit()

    def bytes_used(self) -> int:
        return self._bytes
