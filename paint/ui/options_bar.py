from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QWidget,
)


class OptionsBar(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.layout_box = QHBoxLayout(self)
        self.layout_box.setContentsMargins(10, 5, 10, 5)
        self.layout_box.setSpacing(8)
        self.layout_box.setAlignment(Qt.AlignLeft)
        self.build(app.tool)

    def _clear(self) -> None:
        while self.layout_box.count():
            item = self.layout_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color:#aeb4bd;")
        return label

    def _spin(self, minimum, maximum, value, suffix, setter, width=64, step=1) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(int(value))
        spin.setSuffix(suffix)
        spin.setFixedWidth(width)
        spin.valueChanged.connect(setter)
        return spin

    def _slider(self, minimum, maximum, value, setter, width=120) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(int(value))
        slider.setFixedWidth(width)
        slider.valueChanged.connect(setter)
        return slider

    def _value_slider(self, minimum, maximum, value, setter, width=90):
        slider = self._slider(minimum, maximum, value, setter, width)
        label = QLabel(f"{int(value)} %")
        label.setFixedWidth(38)
        label.setStyleSheet("color:#aeb4bd;")
        slider.valueChanged.connect(lambda v: label.setText(f"{int(v)} %"))
        return slider, label

    def _combo(self, items, current, setter, width=130) -> QComboBox:
        combo = QComboBox()
        for key, label in items:
            combo.addItem(label, key)
        index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        combo.setFixedWidth(width)
        combo.currentIndexChanged.connect(lambda _: setter(combo.currentData()))
        return combo

    def _check(self, text, checked, setter) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(checked)
        box.toggled.connect(setter)
        return box

    def build(self, tool) -> None:
        self._clear()
        canvas = self.app.canvas
        tool_id = tool.id
        if tool_id in ("brush", "eraser", "line", "rect", "ellipse", "roundrect", "polygon"):
            attr = "size" if hasattr(tool, "size") else "width"
            initial = getattr(tool, attr)
            self.layout_box.addWidget(self._label("Taille"))
            slider = self._slider(1, 300, initial, lambda value: None, 110)
            spin = self._spin(1, 800, initial, " px", lambda value: None, 70)

            def set_size(value, attr=attr, tool=tool, slider=slider, spin=spin):
                slider.blockSignals(True)
                spin.blockSignals(True)
                slider.setValue(min(300, int(value)))
                spin.setValue(int(value))
                slider.blockSignals(False)
                spin.blockSignals(False)
                setattr(tool, attr, int(value))
                canvas.update()

            slider.valueChanged.connect(set_size)
            spin.valueChanged.connect(set_size)
            self.layout_box.addWidget(slider)
            self.layout_box.addWidget(spin)
            self.layout_box.addWidget(self._label("Opacité"))
            opacity_slider, opacity_label = self._value_slider(
                1, 100, int(tool.opacity * 100), self._opacity_setter(tool), 90
            )
            self.layout_box.addWidget(opacity_slider)
            self.layout_box.addWidget(opacity_label)
            if tool_id in ("brush", "eraser"):
                self.layout_box.addWidget(self._label("Dureté"))
                hardness_slider, hardness_label = self._value_slider(
                    0, 100, int(tool.hardness * 100), self._hardness_setter(tool), 90
                )
                self.layout_box.addWidget(hardness_slider)
                self.layout_box.addWidget(hardness_label)
                self.layout_box.addWidget(
                    self._check("Pression", tool.pressure_size,
                                self._pressure_setter(tool))
                )
            if tool_id in ("rect", "ellipse", "roundrect", "polygon"):
                self.layout_box.addWidget(
                    self._check("Rempli (couleur d'arrière-plan)", tool.filled,
                                self._filled_setter(tool))
                )
            if tool_id == "roundrect":
                self.layout_box.addWidget(self._label("Arrondi"))
                self.layout_box.addWidget(self._spin(0, 400, tool.radius, " px",
                                                     self._radius_setter(tool), 64))
            self._hint_size(canvas)
        elif tool_id == "fill":
            self.layout_box.addWidget(self._label("Tolérance"))
            self.layout_box.addWidget(self._slider(0, 255, tool.tolerance,
                                                    self._tolerance_setter(tool), 140))
            self.layout_box.addWidget(
                self._spin(0, 255, tool.tolerance, "", self._tolerance_setter(tool), 56)
            )
        elif tool_id == "gradient":
            self.layout_box.addWidget(self._label("Type"))
            self.layout_box.addWidget(
                self._combo([("linear", "Linéaire"), ("radial", "Radial")], tool.kind,
                            lambda value: self._set_attr(tool, "kind", value))
            )
            self.layout_box.addWidget(self._label("Opacité"))
            gradient_slider, gradient_label = self._value_slider(
                1, 100, int(tool.opacity * 100), self._opacity_setter(tool), 100
            )
            self.layout_box.addWidget(gradient_slider)
            self.layout_box.addWidget(gradient_label)
        elif tool_id == "select":
            self.layout_box.addWidget(self._label("Forme"))
            self.layout_box.addWidget(
                self._combo([("rect", "Rectangle"), ("lasso", "Lasso")], tool.mode,
                            lambda value: self._set_attr(tool, "mode", value), 110)
            )
            self.layout_box.addWidget(self._label("Mode"))
            self.layout_box.addWidget(
                self._combo(
                    [("replace", "Remplacer"), ("add", "Ajouter"),
                     ("subtract", "Soustraire"), ("intersect", "Intersection")],
                    tool.selection_mode,
                    lambda value: self._set_attr(tool, "selection_mode", value), 120,
                )
            )
            self.layout_box.addWidget(self._label("Contour progressif"))
            self.layout_box.addWidget(
                self._spin(0, 200, tool.feather, " px", self._feather_setter(tool), 68)
            )
            hint = QLabel("Glisser dans la sélection pour la déplacer")
            hint.setStyleSheet("color:#7f858f;")
            self.layout_box.addWidget(hint)
        elif tool_id == "wand":
            self.layout_box.addWidget(self._label("Tolérance"))
            self.layout_box.addWidget(
                self._slider(0, 255, tool.tolerance, self._tolerance_setter(tool), 100)
            )
            self.layout_box.addWidget(
                self._spin(0, 255, tool.tolerance, "", self._tolerance_setter(tool), 56)
            )
            self.layout_box.addWidget(
                self._check("Contigu", tool.contiguous, self._contiguous_setter(tool))
            )
            self.layout_box.addWidget(
                self._check("Tous les calques", tool.sample_all, self._sample_setter(tool))
            )
            self.layout_box.addWidget(self._label("Contour progressif"))
            self.layout_box.addWidget(
                self._spin(0, 200, tool.feather, " px", self._feather_setter(tool), 68)
            )
            self.layout_box.addWidget(self._label("Mode"))
            self.layout_box.addWidget(
                self._combo(
                    [("replace", "Remplacer"), ("add", "Ajouter"),
                     ("subtract", "Soustraire"), ("intersect", "Intersection")],
                    tool.selection_mode,
                    lambda value: self._set_attr(tool, "selection_mode", value), 120,
                )
            )
        elif tool_id == "text":
            self.layout_box.addWidget(
                self._label("Cliquez sur le canevas pour saisir le texte")
            )
        elif tool_id == "picker":
            self.layout_box.addWidget(self._label("Échantillon"))
            self.layout_box.addWidget(
                self._combo([(1, "1 × 1"), (3, "3 × 3"), (5, "5 × 5")], tool.sample_size,
                            lambda value: self._set_attr(tool, "sample_size", int(value)), 90)
            )
            self.layout_box.addWidget(
                self._label("Cliquez pour prélever une couleur (Alt avec n'importe quel outil)")
            )
        elif tool_id == "crop":
            hint = QLabel("Glissez le cadre, puis Entrée pour recadrer • Échap pour annuler")
            hint.setStyleSheet("color:#7f858f;")
            self.layout_box.addWidget(hint)
        self.layout_box.addStretch(1)

    def _hint_size(self, canvas) -> None:
        hint = QLabel("Shift = contraindre  •  Ctrl+molette = zoom")
        hint.setStyleSheet("color:#6f757f;")
        self.layout_box.addWidget(hint)

    def _size_setter(self, tool):
        attr = "size" if hasattr(tool, "size") else "width"

        def setter(value):
            setattr(tool, attr, int(value))
            self.app.canvas.update()

        return setter

    def _opacity_setter(self, tool):
        def setter(value):
            tool.opacity = max(0.01, min(1.0, value / 100.0))
            self.app.canvas.update()

        return setter

    def _hardness_setter(self, tool):
        def setter(value):
            tool.hardness = max(0.0, min(1.0, value / 100.0))

        return setter

    def _filled_setter(self, tool):
        def setter(value):
            tool.filled = bool(value)

        return setter

    def _radius_setter(self, tool):
        def setter(value):
            tool.radius = int(value)

        return setter

    def _tolerance_setter(self, tool):
        def setter(value):
            tool.tolerance = int(value)

        return setter

    def _feather_setter(self, tool):
        def setter(value):
            tool.feather = int(value)

        return setter

    def _contiguous_setter(self, tool):
        def setter(value):
            tool.contiguous = bool(value)

        return setter

    def _sample_setter(self, tool):
        def setter(value):
            tool.sample_all = bool(value)

        return setter

    def _pressure_setter(self, tool):
        def setter(value):
            tool.pressure_size = bool(value)

        return setter

    def _set_attr(self, tool, attr, value) -> None:
        setattr(tool, attr, value)
        self.app.canvas.update()
