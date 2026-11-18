from __future__ import annotations

import json

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..sheet import (
    DPI_PRESETS,
    MAX_SIDE,
    RATIOS,
    UNIT_DECIMALS,
    UNIT_LABELS,
    UNIT_SUFFIX,
    PRESETS,
    SheetPreset,
    clamp_side,
    estimate_bytes,
    from_px,
    human_bytes,
    px_per_unit,
    sheet_label,
    to_px,
)

CUSTOM_KEY = "sheets/custom"
LAST_KEY = "sheets/last"

ANCHORS = (
    "top-left", "top", "top-right",
    "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
)

ANCHOR_TEXT = {
    "top-left": "↖", "top": "↑", "top-right": "↗",
    "left": "←", "center": "•", "right": "→",
    "bottom-left": "↙", "bottom": "↓", "bottom-right": "↘",
}


def load_custom_sheets(settings) -> list[dict]:
    if settings is None:
        return []
    raw = settings.value(CUSTOM_KEY, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        try:
            out.append({
                "name": str(item["name"]),
                "width": clamp_side(item["width"]),
                "height": clamp_side(item["height"]),
                "dpi": max(36, min(1200, int(item.get("dpi", 300)))),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save_custom_sheets(settings, items: list[dict]) -> None:
    if settings is None:
        return
    settings.setValue(CUSTOM_KEY, json.dumps(items, ensure_ascii=False))
    settings.sync()


def load_last_sheet(settings, width: int = 1600, height: int = 1000,
                    dpi: int = 96) -> tuple[int, int, int]:
    if settings is not None:
        raw = settings.value(LAST_KEY, "")
        if raw:
            try:
                data = json.loads(raw)
                return (clamp_side(data["width"]), clamp_side(data["height"]),
                        max(36, min(1200, int(data.get("dpi", dpi)))))
            except (KeyError, TypeError, ValueError):
                pass
    return width, height, dpi


def store_last_sheet(settings, width: int, height: int, dpi: int) -> None:
    if settings is None:
        return
    settings.setValue(LAST_KEY, json.dumps(
        {"width": int(width), "height": int(height), "dpi": int(dpi)}))


class SheetSizeWidget(QWidget):
    changed = Signal()

    def __init__(self, width: int = 1600, height: int = 1000, dpi: int = 96,
                 unit: str = "px", allow_dpi: bool = True, parent=None):
        super().__init__(parent)
        self._w = float(clamp_side(width))
        self._h = float(clamp_side(height))
        self._dpi = float(max(36, min(1200, int(dpi))))
        self._unit = unit if unit in UNIT_SUFFIX else "px"
        self._guard = False
        self._ratio = None
        self._allow_dpi = allow_dpi

        self.unit_box = QComboBox()
        for key, label in UNIT_LABELS:
            self.unit_box.addItem(label, key)
        self.unit_box.setCurrentIndex(max(0, [k for k, _ in UNIT_LABELS].index(self._unit)))

        self.dpi_box = QSpinBox()
        self.dpi_box.setRange(36, 1200)
        self.dpi_box.setValue(int(self._dpi))
        self.dpi_box.setSuffix(" dpi")
        self.dpi_box.setToolTip("Résolution d'impression. Modifie la taille en pixels "
                                "quand l'unité n'est pas le pixel.")

        self.width_box = QDoubleSpinBox()
        self.width_box.setRange(0.1, 1_000_000.0)
        self.width_box.setKeyboardTracking(False)
        self.height_box = QDoubleSpinBox()
        self.height_box.setRange(0.1, 1_000_000.0)
        self.height_box.setKeyboardTracking(False)

        self.ratio_box = QComboBox()
        for label, ratio in RATIOS:
            self.ratio_box.addItem(label, ratio)
        self.lock_button = QToolButton()
        self.lock_button.setText("Ratio")
        self.lock_button.setCheckable(True)
        self.lock_button.setToolTip("Conserver les proportions lors du changement de taille")

        self.portrait_button = QToolButton()
        self.portrait_button.setText("Portrait")
        self.portrait_button.setCheckable(True)
        self.landscape_button = QToolButton()
        self.landscape_button.setText("Paysage")
        self.landscape_button.setCheckable(True)
        self.orientation_group = QButtonGroup(self)
        self.orientation_group.setExclusive(True)
        self.orientation_group.addButton(self.portrait_button)
        self.orientation_group.addButton(self.landscape_button)

        self.info = QLabel()
        self.info.setStyleSheet("color:#7f858f;")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        units_row = QHBoxLayout()
        units_row.addWidget(self.unit_box, 1)
        if allow_dpi:
            units_row.addWidget(self.dpi_box)
        form.addRow("Unité", self._row(units_row))
        form.addRow("Largeur", self.width_box)
        form.addRow("Hauteur", self.height_box)
        ratio_row = QHBoxLayout()
        ratio_row.addWidget(self.ratio_box, 1)
        ratio_row.addWidget(self.lock_button)
        form.addRow("Proportions", self._row(ratio_row))
        orient_row = QHBoxLayout()
        orient_row.addWidget(self.portrait_button)
        orient_row.addWidget(self.landscape_button)
        orient_row.addStretch(1)
        form.addRow("Orientation", self._row(orient_row))
        form.addRow("", self.info)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)

        self.unit_box.currentIndexChanged.connect(self._unit_changed)
        self.dpi_box.valueChanged.connect(self._dpi_changed)
        self.width_box.valueChanged.connect(self._width_changed)
        self.height_box.valueChanged.connect(self._height_changed)
        self.ratio_box.currentIndexChanged.connect(self._ratio_changed)
        self.lock_button.toggled.connect(self._lock_toggled)
        self.portrait_button.clicked.connect(lambda: self._set_orientation(False))
        self.landscape_button.clicked.connect(lambda: self._set_orientation(True))
        self._refresh()

    @staticmethod
    def _row(layout) -> QWidget:
        widget = QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        return widget

    def _refresh(self) -> None:
        self._guard = True
        unit = self._unit
        self.width_box.setDecimals(UNIT_DECIMALS[unit])
        self.height_box.setDecimals(UNIT_DECIMALS[unit])
        self.width_box.setSuffix(UNIT_SUFFIX[unit])
        self.height_box.setSuffix(UNIT_SUFFIX[unit])
        self.width_box.setSingleStep(1.0 if unit == "px" else 10 ** -UNIT_DECIMALS[unit] * 10)
        self.height_box.setSingleStep(1.0 if unit == "px" else 10 ** -UNIT_DECIMALS[unit] * 10)
        self.width_box.setValue(from_px(self._w, unit, self._dpi))
        self.height_box.setValue(from_px(self._h, unit, self._dpi))
        self.landscape_button.setChecked(self._w >= self._h)
        self.portrait_button.setChecked(self._w < self._h)
        self.info.setText(sheet_label(clamp_side(self._w), clamp_side(self._h),
                                      int(self._dpi)))
        self._guard = False

    def _unit_changed(self, _index: int) -> None:
        if self._guard:
            return
        self._unit = str(self.unit_box.currentData())
        self._refresh()
        self.changed.emit()

    def _dpi_changed(self, value: int) -> None:
        if self._guard:
            return
        if self._unit == "px":
            self._dpi = float(value)
        else:
            self._dpi = float(value)
            self._w = to_px(self.width_box.value(), self._unit, self._dpi)
            self._h = to_px(self.height_box.value(), self._unit, self._dpi)
        self._refresh()
        self.changed.emit()

    def _width_changed(self, value: float) -> None:
        if self._guard:
            return
        self._w = to_px(value, self._unit, self._dpi)
        if self.lock_button.isChecked() and self._ratio:
            self._h = self._w / self._ratio
            self._guard = True
            self.height_box.setValue(from_px(self._h, self._unit, self._dpi))
            self._guard = False
        self._refresh_info()
        self.changed.emit()

    def _height_changed(self, value: float) -> None:
        if self._guard:
            return
        self._h = to_px(value, self._unit, self._dpi)
        if self.lock_button.isChecked() and self._ratio:
            self._w = self._h * self._ratio
            self._guard = True
            self.width_box.setValue(from_px(self._w, self._unit, self._dpi))
            self._guard = False
        self._refresh_info()
        self.changed.emit()

    def _ratio_changed(self, _index: int) -> None:
        if self._guard:
            return
        ratio = self.ratio_box.currentData()
        self._ratio = ratio
        if ratio is None:
            self.lock_button.setChecked(False)
            return
        self.lock_button.setChecked(True)
        self._h = self._w / ratio
        self._refresh()
        self.changed.emit()

    def _lock_toggled(self, checked: bool) -> None:
        if self._guard:
            return
        if checked:
            ratio = self.ratio_box.currentData()
            if ratio is None:
                self._ratio = self._w / max(1.0, self._h)
            else:
                self._ratio = ratio
            self._h = self._w / self._ratio
            self._refresh()
            self.changed.emit()

    def _refresh_info(self) -> None:
        self.info.setText(sheet_label(clamp_side(self._w), clamp_side(self._h),
                                      int(self._dpi)))

    def _set_orientation(self, landscape: bool) -> None:
        if self._guard:
            return
        if landscape and self._w < self._h:
            self._w, self._h = self._h, self._w
        elif not landscape and self._w > self._h:
            self._w, self._h = self._h, self._w
        self._refresh()
        self.changed.emit()

    def set_size_px(self, width: int, height: int) -> None:
        self._w = float(clamp_side(width))
        self._h = float(clamp_side(height))
        self._refresh()

    def set_dpi(self, dpi: int) -> None:
        self._dpi = float(max(36, min(1200, int(dpi))))
        self._guard = True
        self.dpi_box.setValue(int(self._dpi))
        self._guard = False
        self._refresh()

    def set_preset(self, preset: SheetPreset) -> None:
        self._dpi = float(preset.dpi)
        self._guard = True
        self.dpi_box.setValue(int(preset.dpi))
        self._guard = False
        self.set_size_px(preset.width, preset.height)

    def size_px(self) -> tuple[int, int]:
        return clamp_side(self._w), clamp_side(self._h)

    def dpi(self) -> int:
        return int(round(self._dpi))

    def set_unit(self, unit: str) -> None:
        if unit in UNIT_SUFFIX:
            self._unit = unit
            self._guard = True
            self.unit_box.setCurrentIndex(max(0, [k for k, _ in UNIT_LABELS].index(unit)))
            self._guard = False
            self._refresh()

    def megapixels(self) -> float:
        width, height = self.size_px()
        return width * height / 1_000_000


class SheetPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._w = 4.0
        self._h = 3.0
        self.setMinimumSize(160, 160)

    def set_size(self, width: float, height: float) -> None:
        self._w = max(1.0, float(width))
        self._h = max(1.0, float(height))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#1b1d21"))
        area = self.rect().adjusted(18, 18, -18, -18)
        ratio = self._w / self._h
        if area.width() / max(1, area.height()) > ratio:
            height = area.height()
            width = height * ratio
        else:
            width = area.width()
            height = width / ratio
        sheet = QRectF(
            area.center().x() - width / 2 + 3,
            area.center().y() - height / 2 + 3,
            width,
            height,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 90))
        painter.drawRect(sheet)
        sheet.translate(-3, -3)
        painter.setBrush(QColor("#f5f6f8"))
        painter.setPen(QPen(QColor("#5b616b"), 1))
        painter.drawRect(sheet)
        painter.end()


class NewSheetDialog(QDialog):
    def __init__(self, parent, settings=None, width: int = 1600, height: int = 1000,
                 dpi: int = 96, budget_bytes: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau document")
        self.setMinimumWidth(520)
        self._settings = settings
        self._budget = budget_bytes or 0
        self._custom = load_custom_sheets(settings)
        self._current_custom = -1

        self.preset_box = QComboBox()
        self.size_widget = SheetSizeWidget(width, height, dpi)
        self.background = QComboBox()
        self.background.addItem("Blanc", "white")
        self.background.addItem("Transparent", "transparent")
        self.background.addItem("Couleur personnalisée…", "custom")
        self.color_button = QPushButton("Couleur")
        self.color_button.setStyleSheet("background:#ffffff; color:#111827;")
        self._custom_color = QColor("#ffffff")

        self.memory = QLabel()
        self.memory.setWordWrap(True)

        self.preview = SheetPreview()
        self.preview.setFixedWidth(190)

        self.save_button = QPushButton("Mémoriser ce format")
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)

        form = QFormLayout()
        form.addRow("Format", self.preset_box)
        form.addRow(self.size_widget)
        form.addRow("Fond", self.background)
        form.addRow("", self.color_button)
        form.addRow("Mémoire", self.memory)
        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.save_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch(1)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addLayout(buttons_row)
        left.addStretch(1)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(buttons)

        self.preset_box.currentIndexChanged.connect(self._preset_changed)
        self.size_widget.changed.connect(self._refresh)
        self.background.currentIndexChanged.connect(self._refresh)
        self.color_button.clicked.connect(self._pick_color)
        self.save_button.clicked.connect(self._save_format)
        self.delete_button.clicked.connect(self._delete_format)

        self._fill_presets()
        self._refresh()

    def _fill_presets(self, select: str | None = None) -> None:
        self._guard = True
        self.preset_box.clear()
        self.preset_box.addItem("Personnalisé", None)
        if self._custom:
            self._add_header("Mes formats")
            for index, item in enumerate(self._custom):
                self.preset_box.addItem(
                    f"{item['name']} ({item['width']} × {item['height']} px)",
                    ("custom", index),
                )
        category = None
        for preset in PRESETS:
            if preset.category != category:
                category = preset.category
                self._add_header(category)
            self.preset_box.addItem(
                f"{preset.name} — {preset.physical} ({preset.width} × {preset.height} px)",
                ("preset", preset),
            )
        self._guard = False
        if select:
            for index in range(self.preset_box.count()):
                data = self.preset_box.itemData(index)
                if isinstance(data, tuple) and data[0] == "custom":
                    if self._custom[data[1]]["name"] == select:
                        self.preset_box.setCurrentIndex(index)
                        return
        self.preset_box.setCurrentIndex(0)

    def _add_header(self, text: str) -> None:
        self.preset_box.addItem(f"— {text} —", None)
        model = self.preset_box.model()
        item = model.item(self.preset_box.count() - 1)
        if item is not None:
            item.setEnabled(False)

    def _preset_changed(self, index: int) -> None:
        if self._guard:
            return
        data = self.preset_box.itemData(index)
        self._current_custom = -1
        if isinstance(data, tuple):
            kind, value = data
            if kind == "custom":
                item = self._custom[value]
                self.size_widget.set_size_px(item["width"], item["height"])
                self.size_widget.set_dpi(item["dpi"])
                self._current_custom = value
                self.delete_button.setEnabled(True)
            else:
                self.size_widget.set_preset(value)
                self.delete_button.setEnabled(False)
        else:
            self.delete_button.setEnabled(False)
        self._refresh()

    def _refresh(self) -> None:
        width, height = self.size_widget.size_px()
        self.preview.set_size(width, height)
        layers = 2 if self.background.currentData() == "white" else 1
        need = estimate_bytes(width, height, layers)
        text = (f"{width} × {height} px • {self.size_widget.megapixels():.1f} Mpx • "
                f"≈ {human_bytes(need)} pour {layers} calque(s)")
        if self._budget:
            text += f" / budget {human_bytes(self._budget)}"
        if width > MAX_SIDE or height > MAX_SIDE:
            text += f"\nLimite : {MAX_SIDE} px par côté."
        self.memory.setText(text)
        if self._budget and need > self._budget:
            self.memory.setStyleSheet("color:#ef4444;")
        elif need > 768 * 1024 * 1024:
            self.memory.setStyleSheet("color:#eab308;")
        else:
            self.memory.setStyleSheet("color:#7f858f;")
        is_custom = self.background.currentData() == "custom"
        self.color_button.setVisible(is_custom)
        self.delete_button.setEnabled(self._current_custom >= 0)

    def _pick_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(self._custom_color, self, "Couleur du fond")
        if color.isValid():
            self._custom_color = color
            self.color_button.setStyleSheet(
                f"background:{color.name()}; color:{'#111827' if color.lightness() > 128 else '#ffffff'};"
            )

    def _save_format(self) -> None:
        name, ok = QInputDialog.getText(self, "Mémoriser le format", "Nom du format :")
        name = name.strip()
        if not ok or not name:
            return
        width, height = self.size_widget.size_px()
        entry = {"name": name, "width": width, "height": height,
                 "dpi": self.size_widget.dpi()}
        replaced = False
        for index, item in enumerate(self._custom):
            if item["name"].casefold() == name.casefold():
                self._custom[index] = entry
                replaced = True
                break
        if not replaced:
            self._custom.append(entry)
        save_custom_sheets(self._settings, self._custom)
        self._fill_presets(select=name)

    def _delete_format(self) -> None:
        if self._current_custom < 0:
            return
        name = self._custom[self._current_custom]["name"]
        del self._custom[self._current_custom]
        save_custom_sheets(self._settings, self._custom)
        self._current_custom = -1
        self._fill_presets(select=name)

    def document_size(self) -> tuple[int, int]:
        return self.size_widget.size_px()

    def dpi_value(self) -> int:
        return self.size_widget.dpi()

    def background_color(self) -> QColor | None:
        kind = self.background.currentData()
        if kind == "white":
            return QColor("#ffffff")
        if kind == "custom":
            return QColor(self._custom_color)
        return None

    def accept(self) -> None:
        width, height = self.document_size()
        store_last_sheet(self._settings, width, height, self.dpi_value())
        super().accept()


class CanvasSizeDialog(QDialog):
    def __init__(self, parent, width: int, height: int, dpi: int = 96):
        super().__init__(parent)
        self.setWindowTitle("Taille du canevas")
        self.setMinimumWidth(420)
        self._width = width
        self._height = height
        self.size_widget = SheetSizeWidget(width, height, dpi, allow_dpi=False)
        self.relative = QCheckBox("Taille relative (ajouter ou retirer des pixels)")
        self.delta_w = QSpinBox()
        self.delta_w.setRange(-MAX_SIDE, MAX_SIDE)
        self.delta_w.setSuffix(" px")
        self.delta_h = QSpinBox()
        self.delta_h.setRange(-MAX_SIDE, MAX_SIDE)
        self.delta_h.setSuffix(" px")
        self.anchor_group = QButtonGroup(self)
        self.anchor_group.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(2)
        for index, anchor in enumerate(ANCHORS):
            button = QToolButton()
            button.setText(ANCHOR_TEXT[anchor])
            button.setCheckable(True)
            button.setFixedSize(34, 30)
            button.setToolTip(anchor)
            if anchor == "center":
                button.setChecked(True)
            self.anchor_group.addButton(button, index)
            grid.addWidget(button, index // 3, index % 3)
        anchor_box = QWidget()
        anchor_box.setLayout(grid)
        anchor_row = QHBoxLayout()
        anchor_row.addWidget(anchor_box)
        anchor_row.addStretch(1)

        form = QFormLayout()
        self.absolute_row = QWidget()
        absolute_layout = QVBoxLayout(self.absolute_row)
        absolute_layout.setContentsMargins(0, 0, 0, 0)
        absolute_layout.addWidget(self.size_widget)
        form.addRow(self.absolute_row)
        self.relative_row = QWidget()
        relative_form = QFormLayout(self.relative_row)
        relative_form.setContentsMargins(0, 0, 0, 0)
        relative_form.addRow("Ajouter en largeur", self.delta_w)
        relative_form.addRow("Ajouter en hauteur", self.delta_h)
        form.addRow(self.relative_row)
        form.addRow("Ancrage", anchor_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.relative)
        layout.addWidget(buttons)
        self.relative_row.setVisible(False)
        self.relative.toggled.connect(self._relative_toggled)

    def _relative_toggled(self, checked: bool) -> None:
        self.absolute_row.setVisible(not checked)
        self.relative_row.setVisible(checked)

    def values(self) -> tuple[int, int, str]:
        index = self.anchor_group.checkedId()
        anchor = ANCHORS[index] if 0 <= index < len(ANCHORS) else "center"
        if self.relative.isChecked():
            return (max(1, min(MAX_SIDE, self._width + self.delta_w.value())),
                    max(1, min(MAX_SIDE, self._height + self.delta_h.value())), anchor)
        width, height = self.size_widget.size_px()
        return width, height, anchor


class ResizeImageDialog(QDialog):
    def __init__(self, parent, width: int, height: int, dpi: int = 96):
        super().__init__(parent)
        self.setWindowTitle("Redimensionner l'image")
        self.setMinimumWidth(420)
        self._width = width
        self._height = height
        self.size_widget = SheetSizeWidget(width, height, dpi)
        self.mode = QComboBox()
        self.mode.addItem("Pixels", "px")
        self.mode.addItem("Pourcentage", "percent")
        self.mode.addItem("Unités physiques", "units")
        self.percent = QDoubleSpinBox()
        self.percent.setRange(1.0, 4000.0)
        self.percent.setValue(100.0)
        self.percent.setSuffix(" %")
        self.percent.setDecimals(1)
        self.percent_row = QWidget()
        percent_layout = QHBoxLayout(self.percent_row)
        percent_layout.setContentsMargins(0, 0, 0, 0)
        percent_layout.addWidget(self.percent)
        percent_layout.addStretch(1)
        self.smooth = QCheckBox("Lissage (haute qualité)")
        self.smooth.setChecked(True)
        self.info = QLabel()
        self.info.setStyleSheet("color:#7f858f;")
        form = QFormLayout()
        form.addRow("Mode", self.mode)
        form.addRow(self.size_widget)
        form.addRow(self.percent_row)
        form.addRow("", self.info)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.smooth)
        layout.addWidget(buttons)
        self.percent_row.setVisible(False)
        self.size_widget.set_unit("px")
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.percent.valueChanged.connect(self._update_info)
        self.size_widget.changed.connect(self._update_info)
        self._update_info()

    def _mode_changed(self, _index: int) -> None:
        mode = self.mode.currentData()
        self.percent_row.setVisible(mode == "percent")
        self.size_widget.setVisible(mode != "percent")
        if mode == "units":
            self.size_widget.set_unit("cm")
        elif mode == "px":
            self.size_widget.set_unit("px")
        self._update_info()

    def _update_info(self) -> None:
        width, height = self.result_size()
        self.info.setText(f"Résultat : {width} × {height} px "
                          f"({width * height / 1_000_000:.1f} Mpx)")

    def result_size(self) -> tuple[int, int]:
        mode = self.mode.currentData()
        if mode == "percent":
            factor = self.percent.value() / 100.0
            return (max(1, min(MAX_SIDE, int(round(self._width * factor)))),
                    max(1, min(MAX_SIDE, int(round(self._height * factor)))))
        return self.size_widget.size_px()

    def values(self) -> tuple[int, int, bool, int]:
        width, height = self.result_size()
        return width, height, self.smooth.isChecked(), self.size_widget.dpi()
