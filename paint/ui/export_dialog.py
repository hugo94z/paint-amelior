from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ..sheet import MAX_SIDE


class ExportImageDialog(QDialog):
    def __init__(self, parent, width: int, height: int, dpi: int = 96):
        super().__init__(parent)
        self.setWindowTitle("Exporter une image")
        self.setMinimumWidth(400)
        self._width = width
        self._height = height
        self.format_box = QComboBox()
        for label, suffix in (("PNG", "png"), ("JPEG", "jpg"), ("WebP", "webp"),
                              ("BMP", "bmp"), ("TIFF", "tif")):
            self.format_box.addItem(label, suffix)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(1.0, 400.0)
        self.scale.setValue(100.0)
        self.scale.setSuffix(" %")
        self.scale.setDecimals(1)
        self.resize = QCheckBox("Redimensionner à l'export")
        self.target_width = QSpinBox()
        self.target_width.setRange(1, MAX_SIDE)
        self.target_width.setValue(width)
        self.target_width.setSuffix(" px")
        self.target_height = QSpinBox()
        self.target_height.setRange(1, MAX_SIDE)
        self.target_height.setValue(height)
        self.target_height.setSuffix(" px")
        self.keep_ratio = QCheckBox("Conserver les proportions")
        self.keep_ratio.setChecked(True)
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(10, 100)
        self.quality.setValue(92)
        self.quality_label = QLabel("92")
        quality_row = QVBoxLayout()
        quality_row.addWidget(self.quality)
        quality_row.setContentsMargins(0, 0, 0, 0)
        self.dpi = QSpinBox()
        self.dpi.setRange(36, 1200)
        self.dpi.setValue(dpi)
        self.dpi.setSuffix(" dpi")
        self.info = QLabel()
        self.info.setStyleSheet("color:#7f858f;")

        form = QFormLayout()
        form.addRow("Format", self.format_box)
        form.addRow("Qualité", self.quality)
        form.addRow("", self.quality_label)
        form.addRow("Résolution", self.dpi)
        form.addRow("", self.resize)
        form.addRow("Largeur", self.target_width)
        form.addRow("Hauteur", self.target_height)
        form.addRow("", self.keep_ratio)
        form.addRow("", self.info)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.target_width.setEnabled(False)
        self.target_height.setEnabled(False)
        self.keep_ratio.setEnabled(False)
        self.resize.toggled.connect(self._toggle_resize)
        self.target_width.valueChanged.connect(self._width_changed)
        self.target_height.valueChanged.connect(self._height_changed)
        self.quality.valueChanged.connect(self._quality_changed)
        self.format_box.currentIndexChanged.connect(self._refresh)
        self.scale.valueChanged.connect(self._refresh)
        self._refresh()

    def _toggle_resize(self, checked: bool) -> None:
        self.target_width.setEnabled(checked)
        self.target_height.setEnabled(checked)
        self.keep_ratio.setEnabled(checked)
        if checked:
            self.target_width.setValue(int(round(self._width * self.scale.value() / 100)))
            self.target_height.setValue(int(round(self._height * self.scale.value() / 100)))

    def _width_changed(self, value: int) -> None:
        if self.keep_ratio.isChecked() and self._width:
            ratio = self._height / self._width
            self.target_height.blockSignals(True)
            self.target_height.setValue(max(1, int(round(value * ratio))))
            self.target_height.blockSignals(False)
        self._refresh()

    def _height_changed(self, value: int) -> None:
        if self.keep_ratio.isChecked() and self._height:
            ratio = self._width / self._height
            self.target_width.blockSignals(True)
            self.target_width.setValue(max(1, int(round(value * ratio))))
            self.target_width.blockSignals(False)
        self._refresh()

    def _quality_changed(self, value: int) -> None:
        self.quality_label.setText(str(value))

    def _refresh(self) -> None:
        width, height = self.size()
        self.info.setText(f"{width} × {height} px • {width * height / 1_000_000:.1f} Mpx")
        enabled = self.format_box.currentData() in ("jpg", "webp")
        self.quality.setEnabled(enabled)
        self.quality_label.setEnabled(enabled)

    def size(self) -> tuple[int, int]:
        if self.resize.isChecked():
            return self.target_width.value(), self.target_height.value()
        return self._width, self._height

    def values(self) -> dict:
        width, height = self.size()
        return {
            "suffix": self.format_box.currentData(),
            "quality": self.quality.value(),
            "size": None if (width, height) == (self._width, self._height) else (width, height),
            "dpi": self.dpi.value(),
        }
