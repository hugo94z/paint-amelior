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


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
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
