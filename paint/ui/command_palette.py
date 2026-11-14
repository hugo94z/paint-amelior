from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class CommandPalette(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Commandes")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une commande…")
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self._actions = []
        for action in app.findChildren(type(app.action_undo)):
            text = action.text().replace("&", "").strip()
            if not text or not action.isEnabled():
                continue
            shortcut = action.shortcut().toString()
            label = f"{text}    {shortcut}" if shortcut else text
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, len(self._actions))
            self.list.addItem(item)
            self._actions.append(action)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._trigger_current)
        self.list.itemActivated.connect(lambda _: self._trigger_current())
        if self.list.count():
            self.list.setCurrentRow(0)
        self.search.setFocus()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self.search.setFocus)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        first = None
        for row in range(self.list.count()):
            item = self.list.item(row)
            action = self._actions[item.data(Qt.UserRole)]
            hidden = needle not in action.text().replace("&", "").lower()
            item.setHidden(hidden)
            if not hidden and first is None:
                first = item
        if first is not None:
            first.setSelected(True)
            self.list.setCurrentItem(first)

    def _trigger_current(self) -> None:
        item = self.list.currentItem()
        if item is None or item.isHidden():
            return
        action = self._actions[item.data(Qt.UserRole)]
        self.accept()
        action.trigger()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._trigger_current()
            return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
