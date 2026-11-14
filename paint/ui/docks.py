from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
