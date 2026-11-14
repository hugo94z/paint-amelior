from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class TextDialog(QDialog):
    def __init__(self, parent, family: str, pixel_size: int, bold: bool, italic: bool):
        super().__init__(parent)
        self.setWindowTitle("Ajouter du texte")
        self.setMinimumWidth(460)
        self._edit = QTextEdit()
        self._edit.setPlaceholderText("Votre texte…")
        self._edit.setMinimumHeight(120)
        self._font_box = QFontComboBox()
        self._font_box.setCurrentFont(QFont(family))
        self._size = QSpinBox()
        self._size.setRange(4, 600)
        self._size.setValue(int(pixel_size))
        self._size.setSuffix(" px")
        self._bold = QCheckBox("Gras")
        self._bold.setChecked(bold)
        self._italic = QCheckBox("Italique")
        self._italic.setChecked(italic)
        controls = QHBoxLayout()
        controls.addWidget(self._bold)
        controls.addWidget(self._italic)
        controls.addStretch(1)
        form = QFormLayout()
        form.addRow("Police", self._font_box)
        form.addRow("Taille", self._size)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._edit)
        layout.addLayout(form)
        layout.addLayout(controls)
        layout.addWidget(buttons)
        self._edit.setFocus()

    def text(self) -> str:
        return self._edit.toPlainText()

    def family(self) -> str:
        return self._font_box.currentFont().family()

    def pixel_size(self) -> int:
        return self._size.value()

    def bold(self) -> bool:
        return self._bold.isChecked()

    def italic(self) -> bool:
        return self._italic.isChecked()
