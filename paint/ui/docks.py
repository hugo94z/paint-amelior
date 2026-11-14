from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..io.exporters import export_animation

from ..layer import BLEND_MODES

PALETTE = [
    "#000000", "#3f3f46", "#71717a", "#a1a1aa", "#d4d4d8", "#ffffff",
    "#7f1d1d", "#dc2626", "#f97316", "#f59e0b", "#eab308", "#84cc16",
    "#14532d", "#16a34a", "#10b981", "#06b6d4", "#0ea5e9", "#2563eb",
    "#1e1b4b", "#4338ca", "#7c3aed", "#c026d3", "#db2777", "#f472b6",
    "#78350f", "#a16207", "#065f46", "#0f766e", "#1e3a8a", "#831843",
]


class LayersDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Calques")
        self.app = app
        self._guard = False
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.list = QListWidget()
        self.list.setMinimumHeight(150)
        self.list.setIconSize(QSize(46, 34))
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setDragEnabled(True)
        self.list.setAcceptDrops(True)
        self.list.setDropIndicatorShown(True)
        self.list.itemChanged.connect(self._item_changed)
        self.list.currentRowChanged.connect(self._row_changed)
        self.list.itemDoubleClicked.connect(self._rename)
        self.list.model().rowsMoved.connect(self._rows_moved)
        layout.addWidget(self.list, 1)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacité"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity_label = QLabel("100 %")
        self.opacity_label.setMinimumWidth(40)
        self.opacity.valueChanged.connect(self._opacity_changed)
        opacity_row.addWidget(self.opacity, 1)
        opacity_row.addWidget(self.opacity_label)
        layout.addLayout(opacity_row)
        self.blend = QComboBox()
        for key, label in BLEND_MODES:
            self.blend.addItem(label, key)
        self.blend.currentIndexChanged.connect(self._blend_changed)
        layout.addWidget(self.blend)
        buttons = QHBoxLayout()
        buttons.setSpacing(3)
        for text, tip, slot in (
            ("+", "Nouveau calque", self.app.action_new_layer.trigger),
            ("⧉", "Dupliquer le calque", self.app.action_duplicate_layer.trigger),
            ("−", "Supprimer le calque", self.app.action_delete_layer.trigger),
            ("↑", "Monter le calque", lambda: self._move(1)),
            ("↓", "Descendre le calque", lambda: self._move(-1)),
            ("⤓", "Fusionner vers le bas", self.app.action_merge_layer.trigger),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setMinimumWidth(28)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        extras = QHBoxLayout()
        extras.setSpacing(3)
        self.mask_button = QToolButton()
        self.mask_button.setText("Masque")
        self.mask_button.setToolTip("Masque de fusion")
        self.mask_button.setPopupMode(QToolButton.MenuButtonPopup)
        mask_menu = QMenu(self.mask_button)
        mask_menu.addAction("Ajouter depuis la sélection",
                            lambda: self.app.doc and self.app.doc.add_layer_mask())
        mask_menu.addAction("Ajouter un masque complet",
                            lambda: self.app.doc and self.app.doc.add_layer_mask(from_selection=False))
        mask_menu.addAction("Activer / désactiver", self._toggle_mask)
        mask_menu.addAction("Appliquer le masque",
                            lambda: self.app.doc and self.app.doc.apply_layer_mask())
        mask_menu.addAction("Supprimer le masque",
                            lambda: self.app.doc and self.app.doc.remove_layer_mask())
        self.mask_button.setMenu(mask_menu)
        self.mask_button.clicked.connect(lambda: self.app.doc and self.app.doc.add_layer_mask())
        extras.addWidget(self.mask_button)
        self.adjust_button = QToolButton()
        self.adjust_button.setText("Réglage")
        self.adjust_button.setToolTip("Calque de réglage non destructif")
        self.adjust_button.setPopupMode(QToolButton.MenuButtonPopup)
        adjust_menu = QMenu(self.adjust_button)
        adjust_menu.addAction("Luminosité", lambda: self._add_adjustment("brightness", 1.15))
        adjust_menu.addAction("Contraste", lambda: self._add_adjustment("contrast", 1.2))
        adjust_menu.addAction("Saturation", lambda: self._add_adjustment("saturation", 1.2))
        adjust_menu.addAction("Niveaux de gris", lambda: self._add_adjustment("grayscale", 1.0))
        adjust_menu.addSeparator()
        adjust_menu.addAction("Modifier le réglage…", self._edit_adjustment)
        self.adjust_button.setMenu(adjust_menu)
        self.adjust_button.clicked.connect(lambda: self._add_adjustment("brightness", 1.15))
        extras.addWidget(self.adjust_button)
        self.lock_button = QToolButton()
        self.lock_button.setText("Verrou")
        self.lock_button.setCheckable(True)
        self.lock_button.setToolTip("Verrouiller le calque")
        self.lock_button.toggled.connect(self._lock_changed)
        extras.addWidget(self.lock_button)
        self.alpha_button = QToolButton()
        self.alpha_button.setText("Alpha")
        self.alpha_button.setCheckable(True)
        self.alpha_button.setToolTip("Verrouiller la transparence")
        self.alpha_button.toggled.connect(self._alpha_changed)
        extras.addWidget(self.alpha_button)
        layout.addLayout(extras)
        self.setWidget(container)
        app.doc_changed.connect(self.refresh)

    def refresh(self) -> None:
        doc = self.app.doc
        self._guard = True
        self.list.clear()
        if doc is not None:
            for index in range(len(doc.layers) - 1, -1, -1):
                layer = doc.layers[index]
                item = QListWidgetItem(layer.name)
                item.setFlags(
                    Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                    | Qt.ItemIsEditable | Qt.ItemIsDragEnabled
                )
                item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
                item.setData(Qt.UserRole, layer.id)
                item.setIcon(QIcon(self._thumbnail(layer)))
                self.list.addItem(item)
            if 0 <= doc.active_index < len(doc.layers):
                self.list.setCurrentRow(len(doc.layers) - 1 - doc.active_index)
                layer = doc.layers[doc.active_index]
                self.opacity.setValue(int(round(layer.opacity * 100)))
                self.opacity_label.setText(f"{int(round(layer.opacity * 100))} %")
                idx = self.blend.findData(layer.blend)
                self.blend.setCurrentIndex(max(0, idx))
                self.lock_button.setChecked(layer.locked)
                self.alpha_button.setChecked(layer.lock_alpha)
                self.mask_button.setEnabled(True)
        self._guard = False

    @staticmethod
    def _thumbnail(layer) -> QPixmap:
        thumb = QImage(46, 34, QImage.Format_ARGB32_Premultiplied)
        thumb.fill(QColor("#34373c"))
        painter = QPainter(thumb)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        scaled = layer.image.scaled(44, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawImage((46 - scaled.width()) // 2, (34 - scaled.height()) // 2, scaled)
        painter.end()
        return QPixmap.fromImage(thumb)

    def _rows_moved(self, parent, start, end, destination, row) -> None:
        if self._guard:
            return
        ids = []
        for index in range(self.list.count()):
            value = self.list.item(index).data(Qt.UserRole)
            if value is not None:
                ids.append(int(value))
        doc = self.app.doc
        if doc is not None and ids:
            QTimer.singleShot(0, lambda: doc.reorder_layers(ids))

    def _doc_index(self, row: int) -> int:
        doc = self.app.doc
        return len(doc.layers) - 1 - row if doc else -1

    def _toggle_mask(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        layer = doc.active_layer()
        if layer is not None and layer.mask is not None:
            doc.set_layer_props(doc.active_index, mask_enabled=not layer.mask_enabled)

    def _add_adjustment(self, kind: str, value: float) -> None:
        doc = self.app.doc
        if doc is not None:
            doc.add_adjustment_layer(kind, value)

    def _edit_adjustment(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        doc = self.app.doc
        if doc is None:
            return
        layer = doc.active_layer()
        if layer is None or layer.adjustment is None:
            return
        labels = {
            "brightness": "Luminosité (facteur)",
            "contrast": "Contraste (facteur)",
            "saturation": "Saturation (facteur)",
            "grayscale": "Niveaux de gris (0 à 1)",
        }
        maximum = 1.0 if layer.adjustment.get("type") == "grayscale" else 3.0
        value, ok = QInputDialog.getDouble(
            self, "Modifier le réglage",
            labels.get(layer.adjustment.get("type"), "Valeur"),
            float(layer.adjustment.get("value", 1.0)), 0.0, maximum, 2,
        )
        if ok:
            doc.set_layer_adjustment(doc.active_index,
                                     {"type": layer.adjustment.get("type"), "value": value})

    def _lock_changed(self, value: bool) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is not None:
            doc.set_layer_props(doc.active_index, locked=value)

    def _alpha_changed(self, value: bool) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is not None:
            doc.set_layer_props(doc.active_index, lock_alpha=value)

    def _row_changed(self, row: int) -> None:
        if self._guard or row < 0:
            return
        index = self._doc_index(row)
        if index >= 0:
            self.app.doc.set_active(index)
            layer = self.app.doc.layers[index]
            self._guard = True
            self.opacity.setValue(int(round(layer.opacity * 100)))
            self.opacity_label.setText(f"{int(round(layer.opacity * 100))} %")
            idx = self.blend.findData(layer.blend)
            self.blend.setCurrentIndex(max(0, idx))
            self._guard = False

    def _item_changed(self, item: QListWidgetItem) -> None:
        if self._guard:
            return
        row = self.list.row(item)
        index = self._doc_index(row)
        if index >= 0:
            doc = self.app.doc
            doc.set_layer_props(index, visible=item.checkState() == Qt.Checked)

    def _opacity_changed(self, value: int) -> None:
        self.opacity_label.setText(f"{value} %")
        if self._guard:
            return
        doc = self.app.doc
        self._guard = True
        doc.set_layer_props(doc.active_index, opacity=value / 100.0)
        self._guard = False

    def _blend_changed(self, index: int) -> None:
        if self._guard:
            return
        doc = self.app.doc
        self._guard = True
        doc.set_layer_props(doc.active_index, blend=self.blend.itemData(index))
        self._guard = False

    def _move(self, delta: int) -> None:
        doc = self.app.doc
        if doc is not None:
            doc.move_layer(doc.active_index, delta)

    def _rename(self, item: QListWidgetItem) -> None:
        index = self._doc_index(self.list.row(item))
        if index >= 0:
            self.app.doc.set_layer_props(index, name=item.text())


class HistoryDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Historique")
        self.app = app
        self._guard = False
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        self.list = QListWidget()
        self.list.setMinimumHeight(120)
        self.list.currentRowChanged.connect(self._row_changed)
        layout.addWidget(self.list)
        self.setWidget(container)
        app.doc_changed.connect(self.refresh)

    def refresh(self) -> None:
        doc = self.app.doc
        self._guard = True
        self.list.clear()
        self.list.addItem("Ouverture du document")
        if doc is not None:
            for label in doc.history.labels:
                self.list.addItem(label)
            self.list.setCurrentRow(doc.history.position)
        self._guard = False

    def _row_changed(self, row: int) -> None:
        if self._guard or row < 0:
            return
        doc = self.app.doc
        if doc is not None:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self._apply_row(row))

    def _apply_row(self, row: int) -> None:
        doc = self.app.doc
        if doc is not None:
            doc.history.go_to(row)
            self.app.canvas.update()


class AnimationDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Animation")
        self.app = app
        self._guard = False
        self._index = 0
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.list = QListWidget()
        self.list.setIconSize(QSize(64, 48))
        self.list.setMinimumHeight(120)
        self.list.currentRowChanged.connect(self._row_changed)
        layout.addWidget(self.list, 1)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Durée"))
        self.duration = QSpinBox()
        self.duration.setRange(20, 10000)
        self.duration.setSingleStep(10)
        self.duration.setValue(120)
        self.duration.setSuffix(" ms")
        self.duration.valueChanged.connect(self._duration_changed)
        duration_row.addWidget(self.duration, 1)
        layout.addLayout(duration_row)
        frame_buttons = QHBoxLayout()
        frame_buttons.setSpacing(3)
        for text, tip, slot in (
            ("+", "Capturer l'image actuelle", self._add_frame),
            ("⧉", "Dupliquer l'image", self._duplicate_frame),
            ("−", "Supprimer l'image", self._remove_frame),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            frame_buttons.addWidget(button)
        layout.addLayout(frame_buttons)
        playback = QHBoxLayout()
        self.play_button = QPushButton("Lire")
        self.play_button.clicked.connect(self.play)
        self.stop_button = QPushButton("Arrêter")
        self.stop_button.clicked.connect(self.stop)
        self.export_button = QToolButton()
        self.export_button.setText("Exporter")
        self.export_button.setPopupMode(QToolButton.MenuButtonPopup)
        export_menu = QMenu(self.export_button)
        export_menu.addAction("GIF animé…", lambda: self._export(False))
        export_menu.addAction("APNG animé…", lambda: self._export(True))
        self.export_button.setMenu(export_menu)
        self.export_button.clicked.connect(lambda: self._export(False))
        playback.addWidget(self.play_button)
        playback.addWidget(self.stop_button)
        playback.addWidget(self.export_button)
        layout.addLayout(playback)
        self.setWidget(container)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        app.doc_changed.connect(self.refresh)

    def refresh(self) -> None:
        doc = self.app.doc
        self._guard = True
        self.list.clear()
        if doc is not None:
            for index, frame in enumerate(doc.frames):
                item = QListWidgetItem(f"Image {index + 1}")
                item.setIcon(QIcon(self._thumbnail(frame["image"])))
                self.list.addItem(item)
            if doc.frames:
                self.list.setCurrentRow(min(self._index, len(doc.frames) - 1))
                self.duration.setValue(doc.frames[self.list.currentRow()]["duration"])
        self._guard = False

    @staticmethod
    def _thumbnail(image):
        thumb = QImage(64, 48, QImage.Format_ARGB32_Premultiplied)
        thumb.fill(QColor("#34373c"))
        painter = QPainter(thumb)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        scaled = image.scaled(62, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawImage((64 - scaled.width()) // 2, (48 - scaled.height()) // 2, scaled)
        painter.end()
        return QPixmap.fromImage(thumb)

    def _row_changed(self, row: int) -> None:
        if self._guard or row < 0:
            return
        self._index = row
        doc = self.app.doc
        if doc is not None and row < len(doc.frames):
            self._guard = True
            self.duration.setValue(doc.frames[row]["duration"])
            self._guard = False

    def _duration_changed(self, value: int) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is not None and 0 <= self._index < len(doc.frames):
            doc.frames[self._index]["duration"] = int(value)
            doc.mark_modified(True)

    def _add_frame(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        self.stop()
        doc.frames.append({"image": doc.composite().copy(), "duration": 120})
        doc.mark_modified(True)
        self._index = len(doc.frames) - 1
        self.refresh()
        self.list.setCurrentRow(self._index)

    def _duplicate_frame(self) -> None:
        doc = self.app.doc
        if doc is None or not doc.frames:
            return
        frame = doc.frames[self._index]
        doc.frames.insert(self._index + 1,
                          {"image": frame["image"].copy(), "duration": frame["duration"]})
        doc.mark_modified(True)
        self._index += 1
        self.refresh()
        self.list.setCurrentRow(self._index)

    def _remove_frame(self) -> None:
        doc = self.app.doc
        if doc is None or not doc.frames:
            return
        del doc.frames[self._index]
        doc.mark_modified(True)
        self._index = max(0, self._index - 1)
        self.refresh()
        self.list.setCurrentRow(self._index)

    def play(self) -> None:
        doc = self.app.doc
        if doc is None or not doc.frames:
            return
        self._index = 0
        self._show_frame()
        self.timer.setInterval(doc.frames[0]["duration"])
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        doc = self.app.doc
        if doc is not None and doc.preview_image is not None:
            doc.preview_image = None
            self.app.canvas.update()

    def _tick(self) -> None:
        doc = self.app.doc
        if doc is None or not doc.frames:
            self.timer.stop()
            return
        self._index = (self._index + 1) % len(doc.frames)
        self._show_frame()
        self.timer.setInterval(doc.frames[self._index]["duration"])

    def _show_frame(self) -> None:
        doc = self.app.doc
        if doc is not None and 0 <= self._index < len(doc.frames):
            doc.preview_image = doc.frames[self._index]["image"]
            self.app.canvas.update()

    def _export(self, apng: bool) -> None:
        doc = self.app.doc
        if doc is None or not doc.frames:
            self.app.notify("Aucune image d'animation")
            return
        suffix = "apng" if apng else "gif"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter l'animation", f"animation.{suffix}",
            "APNG (*.png)" if apng else "GIF (*.gif)",
        )
        if not path:
            return
        if not path.lower().endswith((".png" if apng else ".gif")):
            path += ".png" if apng else ".gif"
        if export_animation(doc, path, apng=apng):
            self.app.notify("Animation exportée")
        else:
            self.app.notify("Échec de l'export")


class ColorDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Couleurs")
        self.app = app
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        swatches = QHBoxLayout()
        self.fg_button = QPushButton()
        self.fg_button.setFixedHeight(42)
        self.fg_button.setToolTip("Couleur d'avant-plan")
        self.fg_button.clicked.connect(self._pick_fg)
        self.bg_button = QPushButton()
        self.bg_button.setFixedHeight(42)
        self.bg_button.setToolTip("Couleur d'arrière-plan")
        self.bg_button.clicked.connect(self._pick_bg)
        swatches.addWidget(self.fg_button, 1)
        swatches.addWidget(self.bg_button, 1)
        layout.addLayout(swatches)
        swap = QHBoxLayout()
        swap_button = QPushButton("Échanger (X)")
        swap_button.clicked.connect(app.swap_colors)
        reset_button = QPushButton("Noir / Blanc")
        reset_button.clicked.connect(app.reset_colors)
        swap.addWidget(swap_button)
        swap.addWidget(reset_button)
        layout.addLayout(swap)
        layout.addWidget(QLabel("Palette"))
        grid = QGridLayout()
        grid.setSpacing(3)
        for index, name in enumerate(PALETTE):
            button = QPushButton()
            button.setFixedSize(26, 26)
            button.setStyleSheet(
                f"background:{name}; border:1px solid #14161a; border-radius:4px;"
            )
            button.setToolTip(name)
            button.clicked.connect(lambda _=False, c=name: app.set_fg_color(QColor(c)))
            grid.addWidget(button, index // 6, index % 6)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Couleurs récentes"))
        self.recent_container = QWidget()
        self.recent_layout = QGridLayout(self.recent_container)
        self.recent_layout.setSpacing(3)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.recent_container)
        layout.addStretch(1)
        self.setWidget(container)
        app.colors_changed.connect(self.refresh)
        app.doc_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        fg = self.app.fg.name()
        bg = self.app.bg.name()
        self.fg_button.setStyleSheet(
            f"background:{fg}; border:1px solid #5b9bff; border-radius:5px;"
            f"color:{self._text_color(self.app.fg)};"
        )
        self.fg_button.setText(fg.upper())
        self.bg_button.setStyleSheet(
            f"background:{bg}; border:1px solid #4a4e56; border-radius:5px;"
            f"color:{self._text_color(self.app.bg)};"
        )
        self.bg_button.setText(bg.upper())
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, color in enumerate(self.app.recent[:12]):
            button = QPushButton()
            button.setFixedSize(24, 24)
            button.setStyleSheet(
                f"background:{color.name()}; border:1px solid #14161a; border-radius:4px;"
            )
            button.setToolTip(color.name())
            button.clicked.connect(lambda _=False, c=color: self.app.set_fg_color(QColor(c)))
            self.recent_layout.addWidget(button, index // 6, index % 6)

    def _pick_fg(self) -> None:
        color = QColorDialog.getColor(self.app.fg, self, "Couleur d'avant-plan",
                                      QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.app.set_fg_color(color)

    @staticmethod
    def _text_color(color) -> str:
        return "#111418" if color.lightness() > 150 else "#f2f4f7"

    def _pick_bg(self) -> None:
        color = QColorDialog.getColor(self.app.bg, self, "Couleur d'arrière-plan",
                                      QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.app.set_bg_color(color)
