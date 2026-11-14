from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path


class PluginAPI:
    def __init__(self, app):
        self.app = app

    @property
    def document(self):
        return self.app.doc

    def add_action(self, text: str, callback, shortcut: str = "") -> None:
        from PySide6.QtGui import QAction, QKeySequence

        action = QAction(text, self.app)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _=False: callback(self.app))
        self.app.tools_menu.addAction(action)

    def notify(self, message: str) -> None:
        self.app.notify(message)


def plugin_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "plugins"


def load_plugins(app) -> list[str]:
    folder = plugin_directory()
    if not folder.is_dir():
        return []
    loaded = []
    api = PluginAPI(app)
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"paint_plugin_{path.stem}", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if callable(register):
                register(api)
                loaded.append(path.stem)
        except Exception:
            traceback.print_exc()
    return loaded
