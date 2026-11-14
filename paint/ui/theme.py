from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

STYLESHEET = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 12px; }
QMainWindow, QWidget { background: #202225; color: #e6e8eb; }
QDialog { background: #232529; }
QToolBar { background: #26282c; border: none; padding: 4px; spacing: 3px; }
QToolBar::separator { background: #34373c; }
QToolBar::separator:vertical { height: 1px; width: 22px; margin: 7px 0; }
QToolBar::separator:horizontal { width: 1px; height: 22px; margin: 0 7px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px; }
QToolButton:hover { background: #34373c; }
QToolButton:pressed { background: #2b2e32; }
QToolButton:checked { background: #2f5fa8; border-color: #4f86d8; }
QMenuBar { background: #26282c; border-bottom: 1px solid #2f3237; }
QMenuBar::item { padding: 5px 9px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #34373c; }
QMenu { background: #2a2d31; border: 1px solid #3b3e44; padding: 4px; }
QMenu::item { padding: 6px 26px 6px 22px; border-radius: 4px; }
QMenu::item:selected { background: #2f5fa8; }
QMenu::separator { height: 1px; background: #3b3e44; margin: 4px 8px; }
QTabBar { background: #1b1d21; }
QTabBar::tab {
    background: #26282c; color: #aeb4bd; padding: 5px 14px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin: 2px 2px 0 0;
}
QTabBar::tab:selected { background: #202225; color: #ffffff; }
QTabBar::tab:hover { background: #31343a; }
QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
QDockWidget::title { background: #26282c; padding: 6px 8px; border-bottom: 1px solid #2f3237; }
QPushButton { background: #33363b; border: 1px solid #41444a; border-radius: 5px; padding: 4px 10px; }
QPushButton:hover { background: #3d4046; }
QPushButton:pressed { background: #2c2f33; }
QPushButton:disabled { color: #6b6f76; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox {
    background: #2a2d31; border: 1px solid #3f4248; border-radius: 5px; padding: 3px 6px;
    selection-background-color: #2f5fa8;
}
QComboBox QAbstractItemView { background: #2a2d31; selection-background-color: #2f5fa8; }
QListWidget { background: #26282c; border: 1px solid #34373c; border-radius: 5px; outline: none; }
QListWidget::item { padding: 4px 6px; border-radius: 4px; }
QListWidget::item:selected { background: #2f5fa8; }
QListWidget::item:hover { background: #31343a; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #4a4e56; background: #2a2d31; }
QCheckBox::indicator:checked { background: #3b82f6; border-color: #5b9bff; }
QSlider::groove:horizontal { height: 4px; background: #3a3d42; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -4px 0; background: #7aa7ff; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: #9cbfff; }
QScrollBar:vertical { background: #202225; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #3d4147; min-height: 24px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #4b5057; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #202225; height: 11px; margin: 0; }
QScrollBar::handle:horizontal { background: #3d4147; min-width: 24px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { background: #26282c; border-top: 1px solid #2f3237; }
QStatusBar::item { border: none; }
QGroupBox { border: 1px solid #34373c; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #aeb4bd; }
QToolTip { background: #2f3237; color: #e6e8eb; border: 1px solid #454950; padding: 4px; }
QTabWidget::pane { border: 1px solid #34373c; }
QTabBar::tab { background: #26282c; padding: 5px 10px; }
QTabBar::tab:selected { background: #2f5fa8; }
QSplitter::handle { background: #2a2d31; }
"""


LIGHT_STYLESHEET = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 12px; }
QMainWindow, QWidget { background: #eef0f3; color: #1f2937; }
QDialog { background: #f7f8fa; }
QToolBar { background: #ffffff; border: none; padding: 4px; spacing: 3px; }
QToolBar::separator { background: #d6dae1; }
QToolBar::separator:vertical { height: 1px; width: 22px; margin: 7px 0; }
QToolBar::separator:horizontal { width: 1px; height: 22px; margin: 0 7px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px; }
QToolButton:hover { background: #e6e9ee; }
QToolButton:checked { background: #cfe0fb; border-color: #6b9ee8; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #dfe3e9; }
QMenuBar::item { padding: 5px 9px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #e6e9ee; }
QMenu { background: #ffffff; border: 1px solid #d6dae1; padding: 4px; }
QMenu::item { padding: 6px 26px 6px 22px; border-radius: 4px; }
QMenu::item:selected { background: #cfe0fb; }
QMenu::separator { height: 1px; background: #e2e5ea; margin: 4px 8px; }
QTabBar { background: #e3e6eb; }
QTabBar::tab { background: #f2f4f7; color: #4b5563; padding: 5px 14px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin: 2px 2px 0 0; }
QTabBar::tab:selected { background: #ffffff; color: #111827; }
QTabBar::tab:hover { background: #e9ecf1; }
QDockWidget::title { background: #ffffff; padding: 6px 8px; border-bottom: 1px solid #dfe3e9; }
QPushButton { background: #ffffff; border: 1px solid #c9ced6; border-radius: 5px; padding: 4px 10px; }
QPushButton:hover { background: #f1f3f6; }
QPushButton:pressed { background: #e2e6ec; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QFontComboBox {
    background: #ffffff; border: 1px solid #c9ced6; border-radius: 5px; padding: 3px 6px;
    selection-background-color: #cfe0fb; selection-color: #111827;
}
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #cfe0fb; }
QListWidget { background: #ffffff; border: 1px solid #d6dae1; border-radius: 5px; outline: none; }
QListWidget::item { padding: 4px 6px; border-radius: 4px; }
QListWidget::item:selected { background: #cfe0fb; color: #111827; }
QListWidget::item:hover { background: #eff2f6; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #b7bec8; background: #ffffff; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #1d4ed8; }
QSlider::groove:horizontal { height: 4px; background: #d6dae1; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -4px 0; background: #2563eb; border-radius: 6px; }
QScrollBar:vertical { background: #eef0f3; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #c0c6cf; min-height: 24px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #eef0f3; height: 11px; margin: 0; }
QScrollBar::handle:horizontal { background: #c0c6cf; min-width: 24px; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar { background: #ffffff; border-top: 1px solid #dfe3e9; }
QStatusBar::item { border: none; }
QToolTip { background: #ffffff; color: #111827; border: 1px solid #c9ced6; padding: 4px; }
QGroupBox { border: 1px solid #d6dae1; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #4b5563; }
"""


def apply_theme(app: QApplication, light: bool = False) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    if light:
        colors = {
            QPalette.Window: "#eef0f3", QPalette.WindowText: "#1f2937",
            QPalette.Base: "#ffffff", QPalette.AlternateBase: "#f4f6f9",
            QPalette.Text: "#1f2937", QPalette.Button: "#ffffff",
            QPalette.ButtonText: "#1f2937", QPalette.Highlight: "#2563eb",
            QPalette.HighlightedText: "#ffffff", QPalette.ToolTipBase: "#ffffff",
            QPalette.ToolTipText: "#111827",
        }
        for role, color in colors.items():
            palette.setColor(role, QColor(color))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            palette.setColor(QPalette.Disabled, role, QColor("#9aa1ab"))
        app.setPalette(palette)
        app.setStyleSheet(LIGHT_STYLESHEET)
        return
    palette.setColor(QPalette.Window, QColor("#202225"))
    palette.setColor(QPalette.WindowText, QColor("#e6e8eb"))
    palette.setColor(QPalette.Base, QColor("#26282c"))
    palette.setColor(QPalette.AlternateBase, QColor("#2a2d31"))
    palette.setColor(QPalette.Text, QColor("#e6e8eb"))
    palette.setColor(QPalette.Button, QColor("#33363b"))
    palette.setColor(QPalette.ButtonText, QColor("#e6e8eb"))
    palette.setColor(QPalette.Highlight, QColor("#2f5fa8"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2f3237"))
    palette.setColor(QPalette.ToolTipText, QColor("#e6e8eb"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#6b6f76"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#6b6f76"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
