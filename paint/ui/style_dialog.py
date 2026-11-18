from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ..layer import default_styles


class LayerStyleDialog(QDialog):
    def __init__(self, parent, styles: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Styles du calque")
        self.setMinimumWidth(420)
        current = default_styles()
        for key, value in (styles or {}).items():
            if key in current:
                current[key].update(value)
        self._shadow_color = QColor(current["shadow"]["color"])
        self._stroke_color = QColor(current["stroke"]["color"])

        shadow_box = QGroupBox("Ombre portée")
        self.shadow_enabled = QCheckBox("Activer l'ombre")
        self.shadow_enabled.setChecked(bool(current["shadow"]["enabled"]))
        self.shadow_button = QPushButton()
        self.shadow_button.clicked.connect(self._pick_shadow)
        self.shadow_opacity = QSlider(Qt.Horizontal)
        self.shadow_opacity.setRange(0, 100)
        self.shadow_opacity.setValue(int(float(current["shadow"]["opacity"]) * 100))
        self.shadow_x = QSpinBox()
        self.shadow_x.setRange(-100, 100)
        self.shadow_x.setValue(int(current["shadow"]["offset_x"]))
        self.shadow_x.setSuffix(" px")
        self.shadow_y = QSpinBox()
        self.shadow_y.setRange(-100, 100)
        self.shadow_y.setValue(int(current["shadow"]["offset_y"]))
        self.shadow_y.setSuffix(" px")
        self.shadow_blur = QSpinBox()
        self.shadow_blur.setRange(0, 80)
        self.shadow_blur.setValue(int(current["shadow"]["blur"]))
        self.shadow_blur.setSuffix(" px")
        shadow_form = QFormLayout(shadow_box)
        shadow_form.addRow("", self.shadow_enabled)
        shadow_form.addRow("Couleur", self.shadow_button)
        shadow_form.addRow("Opacité", self.shadow_opacity)
        shadow_form.addRow("Décalage X", self.shadow_x)
        shadow_form.addRow("Décalage Y", self.shadow_y)
        shadow_form.addRow("Flou", self.shadow_blur)

        stroke_box = QGroupBox("Contour")
        self.stroke_enabled = QCheckBox("Activer le contour")
        self.stroke_enabled.setChecked(bool(current["stroke"]["enabled"]))
        self.stroke_button = QPushButton()
        self.stroke_button.clicked.connect(self._pick_stroke)
        self.stroke_width = QSpinBox()
        self.stroke_width.setRange(1, 40)
        self.stroke_width.setValue(int(current["stroke"]["width"]))
        self.stroke_width.setSuffix(" px")
        self.stroke_opacity = QSlider(Qt.Horizontal)
        self.stroke_opacity.setRange(0, 100)
        self.stroke_opacity.setValue(int(float(current["stroke"]["opacity"]) * 100))
        stroke_form = QFormLayout(stroke_box)
        stroke_form.addRow("", self.stroke_enabled)
        stroke_form.addRow("Couleur", self.stroke_button)
        stroke_form.addRow("Épaisseur", self.stroke_width)
        stroke_form.addRow("Opacité", self.stroke_opacity)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(shadow_box)
        layout.addWidget(stroke_box)
        layout.addWidget(buttons)
        self._refresh_colors()

    def _refresh_colors(self) -> None:
        for button, color in ((self.shadow_button, self._shadow_color),
                              (self.stroke_button, self._stroke_color)):
            text = "#111418" if color.lightness() > 150 else "#f2f4f7"
            button.setText(color.name().upper())
            button.setStyleSheet(
                f"background:{color.name()}; color:{text}; "
                f"border:1px solid #4a4e56; border-radius:4px; padding:4px;"
            )

    def _pick_shadow(self) -> None:
        color = QColorDialog.getColor(self._shadow_color, self, "Couleur de l'ombre")
        if color.isValid():
            self._shadow_color = color
            self._refresh_colors()

    def _pick_stroke(self) -> None:
        color = QColorDialog.getColor(self._stroke_color, self, "Couleur du contour")
        if color.isValid():
            self._stroke_color = color
            self._refresh_colors()

    def values(self) -> dict:
        return {
            "shadow": {
                "enabled": self.shadow_enabled.isChecked(),
                "color": self._shadow_color.name(),
                "opacity": self.shadow_opacity.value() / 100.0,
                "offset_x": self.shadow_x.value(),
                "offset_y": self.shadow_y.value(),
                "blur": self.shadow_blur.value(),
            },
            "stroke": {
                "enabled": self.stroke_enabled.isChecked(),
                "color": self._stroke_color.name(),
                "opacity": self.stroke_opacity.value() / 100.0,
                "width": self.stroke_width.value(),
            },
        }
