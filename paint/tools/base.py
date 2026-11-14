from __future__ import annotations

from PySide6.QtCore import Qt


class BaseTool:
    id = "base"
    label = "Outil"
    shortcut = ""
    icon = ""

    def __init__(self, app):
        self.app = app

    @property
    def doc(self):
        return self.app.doc

    def cursor(self):
        return Qt.CrossCursor

    def cursor_size(self) -> int:
        return 0

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def press(self, pos, event) -> None:
        pass

    def move(self, pos, event) -> None:
        pass

    def release(self, pos, event) -> None:
        pass

    def double_click(self, pos, event) -> None:
        self.press(pos, event)

    def key_press(self, event) -> bool:
        return False

    def cancel(self) -> None:
        pass

    def overlay(self):
        return None

    def preview(self, painter) -> None:
        pass

    def notify(self, message: str) -> None:
        self.app.notify(message)

    def paintable_layer(self):
        layer = self.doc.active_layer()
        if layer is None:
            return None
        if layer.locked:
            self.notify("Calque verrouillé")
            return None
        return layer
