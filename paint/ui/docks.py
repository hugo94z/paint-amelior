from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QLineEdit,
    QInputDialog,
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
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..io.exporters import export_animation
from .color_wheel import ColorWheel

from ..layer import BLEND_MODES

PALETTE = [
    "#000000", "#3f3f46", "#71717a", "#a1a1aa", "#d4d4d8", "#ffffff",
    "#7f1d1d", "#dc2626", "#f97316", "#f59e0b", "#eab308", "#84cc16",
    "#14532d", "#16a34a", "#10b981", "#06b6d4", "#0ea5e9", "#2563eb",
    "#1e1b4b", "#4338ca", "#7c3aed", "#c026d3", "#db2777", "#f472b6",
    "#78350f", "#a16207", "#065f46", "#0f766e", "#1e3a8a", "#831843",
]


class LayerTree(QTreeWidget):
    dropped = Signal()

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self.dropped.emit()


class LayersDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Calques")
        self.app = app
        self._guard = False
        self._selected = None
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.tree = LayerTree()
        self.tree.setMinimumHeight(170)
        self.tree.setIconSize(QSize(46, 34))
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.currentItemChanged.connect(self._current_changed)
        self.tree.itemDoubleClicked.connect(self._rename)
        self.tree.dropped.connect(self._tree_dropped)
        self.tree.itemExpanded.connect(lambda item: self._expansion(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._expansion(item, False))
        layout.addWidget(self.tree, 1)
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
            ("▣", "Nouveau groupe depuis le calque actif", self._group_active),
            ("⧉", "Dupliquer le calque", self.app.action_duplicate_layer.trigger),
            ("−", "Supprimer", self.app.action_delete_layer.trigger),
            ("↑", "Monter", lambda: self._move(1)),
            ("↓", "Descendre", lambda: self._move(-1)),
            ("⤓", "Fusionner vers le bas", self.app.action_merge_layer.trigger),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.setMinimumWidth(26)
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
        group_button = QToolButton()
        group_button.setText("Groupe")
        group_button.setToolTip("Grouper le calque actif / dissoudre le groupe sélectionné")
        group_button.setPopupMode(QToolButton.MenuButtonPopup)
        group_menu = QMenu(group_button)
        group_menu.addAction("Grouper le calque actif", self._group_active)
        group_menu.addAction("Nouveau groupe vide", self._new_group)
        group_menu.addAction("Dissoudre le groupe", self._ungroup_selected)
        group_menu.addAction("Supprimer le groupe et ses calques",
                             lambda: self._remove_selected_group(delete_layers=True))
        group_button.setMenu(group_menu)
        group_button.clicked.connect(self._group_active)
        extras.addWidget(group_button)
        layout.addLayout(extras)
        self.setWidget(container)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        app.doc_changed.connect(self.refresh)

    def _entry(self, item):
        if item is None:
            return None, None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return None, None
        return data[0], data[1]

    def refresh(self) -> None:
        if self._guard:
            return
        doc = self.app.doc
        self._guard = True
        expanded = self._expanded_ids()
        selected = self._selected
        self.tree.clear()
        if doc is not None:
            top = []
            for group in doc.groups:
                if group.parent is None:
                    indices = doc.group_layer_indices(group.id)
                    position = (max(indices) if indices
                                else len(doc.layers) + 50 + doc.groups.index(group))
                    top.append((position, 1, group))
            for layer in doc.layers:
                if layer.group_id is None:
                    top.append((doc.layer_index(layer.id), 0, layer))
            top.sort(key=lambda entry: (-entry[0], entry[1]))
            for _, kind, obj in top:
                if kind == 1:
                    self._add_group_item(doc, obj, self.tree.invisibleRootItem(), expanded)
                else:
                    self._add_layer_item(doc, obj, self.tree.invisibleRootItem())
        self.tree.expandAll()
        if doc is not None and doc.groups:
            for group in doc.groups:
                item = self._find_item(("group", group.id))
                if item is not None:
                    item.setExpanded(group.expanded)
        item = self._find_item(selected) if selected else None
        if item is None and doc is not None and 0 <= doc.active_index < len(doc.layers):
            item = self._find_item(("layer", doc.layers[doc.active_index].id))
        if item is not None:
            self.tree.setCurrentItem(item)
        self._guard = False
        self._apply_selection_controls(item)

    def _expanded_ids(self) -> set:
        result = set()
        doc = self.app.doc
        if doc is not None:
            for group in doc.groups:
                if not group.expanded:
                    result.add(group.id)
        return result

    def _find_item(self, key):
        if not key:
            return None
        kind, value = key
        stack = [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            item_kind, item_value = self._entry(item)
            if item_kind == kind and item_value == value:
                return item
            stack.extend(item.child(index) for index in range(item.childCount()))
        return None

    def _add_layer_item(self, doc, layer, parent) -> None:
        index = doc.layer_index(layer.id)
        item = QTreeWidgetItem([layer.name])
        flags = (Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                 | Qt.ItemIsEditable | Qt.ItemIsDragEnabled)
        item.setFlags(flags)
        item.setCheckState(0, Qt.Checked if layer.visible else Qt.Unchecked)
        item.setData(0, Qt.UserRole, ("layer", layer.id))
        item.setData(0, Qt.UserRole + 1, index)
        item.setIcon(0, QIcon(self._thumbnail(layer)))
        parent.addChild(item)

    def _add_group_item(self, doc, group, parent, expanded: set) -> None:
        item = QTreeWidgetItem([group.name])
        flags = (Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                 | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        item.setFlags(flags)
        item.setCheckState(0, Qt.Checked if group.visible else Qt.Unchecked)
        item.setData(0, Qt.UserRole, ("group", group.id))
        item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
        parent.addChild(item)
        children = []
        for layer in doc.layers:
            if layer.group_id == group.id:
                children.append((doc.layer_index(layer.id), 0, layer))
        for child in doc.groups:
            if child.parent == group.id:
                indices = doc.group_layer_indices(child.id)
                position = (max(indices) if indices
                            else len(doc.layers) + 50 + doc.groups.index(child))
                children.append((position, 1, child))
        children.sort(key=lambda entry: (-entry[0], entry[1]))
        for _, kind, obj in children:
            if kind == 1:
                self._add_group_item(doc, obj, item, expanded)
            else:
                self._add_layer_item(doc, obj, item)
        item.setExpanded(group.expanded)

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

    def _tree_dropped(self) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is None:
            return
        order: list[int] = []
        memberships: dict = {}
        parents: dict = {}

        def walk(item, parent_group) -> None:
            kind, value = self._entry(item)
            if kind == "group":
                parents[value] = parent_group
                for index in range(item.childCount()):
                    walk(item.child(index), value)
            elif kind == "layer":
                order.append(value)
                memberships[value] = parent_group

        for index in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(index), None)
        if not order:
            return
        self._guard = True
        try:
            doc.rebuild_tree(order, memberships, parents)
        finally:
            self._guard = False
        self.refresh()

    def _selected_target(self):
        kind, value = self._entry(self.tree.currentItem())
        doc = self.app.doc
        if doc is None:
            return None, None
        if kind == "group":
            return "group", doc.group_by_id(value)
        if kind == "layer" and 0 <= doc.active_index < len(doc.layers):
            return "layer", doc.layers[doc.active_index]
        return None, None

    def _apply_selection_controls(self, item) -> None:
        kind, _ = self._entry(item)
        self._guard = True
        if kind == "group":
            group = self._selected_target()[1]
            if group is not None:
                self.opacity.setValue(int(round(group.opacity * 100)))
                self.opacity_label.setText(f"{int(round(group.opacity * 100))} %")
                self.blend.setCurrentIndex(max(0, self.blend.findData(group.blend)))
        elif kind == "layer":
            layer = self.app.doc.active_layer() if self.app.doc else None
            if layer is not None:
                self.opacity.setValue(int(round(layer.opacity * 100)))
                self.opacity_label.setText(f"{int(round(layer.opacity * 100))} %")
                self.blend.setCurrentIndex(max(0, self.blend.findData(layer.blend)))
                self.lock_button.setChecked(layer.locked)
                self.alpha_button.setChecked(layer.lock_alpha)
        group_selected = kind == "group"
        for widget in (self.mask_button, self.adjust_button, self.lock_button,
                       self.alpha_button):
            widget.setEnabled(not group_selected)
        self._guard = False

    def _expansion(self, item, expanded: bool) -> None:
        if self._guard:
            return
        kind, value = self._entry(item)
        doc = self.app.doc
        if kind != "group" or doc is None:
            return
        self._guard = True
        try:
            doc.set_group_props(value, expanded=expanded)
        finally:
            self._guard = False

    def _current_changed(self, current, previous) -> None:
        if self._guard or current is None:
            return
        self._selected = self._entry(current)
        kind, value = self._selected
        doc = self.app.doc
        if doc is None:
            return
        if kind == "layer":
            index = doc.layer_index(value)
            if index >= 0:
                doc.set_active(index)
        self._apply_selection_controls(current)

    def _item_changed(self, item, column: int) -> None:
        if self._guard:
            return
        kind, value = self._entry(item)
        doc = self.app.doc
        if doc is None or kind is None:
            return
        checked = item.checkState(0) == Qt.Checked
        self._guard = True
        try:
            if kind == "layer":
                index = doc.layer_index(value)
                if index >= 0:
                    layer = doc.layers[index]
                    if layer.name != item.text(0):
                        doc.set_layer_props(index, name=item.text(0))
                    if layer.visible != checked:
                        doc.set_layer_props(index, visible=checked)
            else:
                group = doc.group_by_id(value)
                if group is not None:
                    if group.name != item.text(0):
                        doc.set_group_props(value, name=item.text(0))
                    if group.visible != checked:
                        doc.set_group_props(value, visible=checked)
        finally:
            self._guard = False

    def _toggle_mask(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        layer = doc.active_layer()
        if layer is not None and layer.mask is not None:
            self._guard = True
            try:
                doc.set_layer_props(doc.active_index, mask_enabled=not layer.mask_enabled)
            finally:
                self._guard = False

    def _add_adjustment(self, kind: str, value: float) -> None:
        doc = self.app.doc
        if doc is not None:
            self._guard = True
            try:
                doc.add_adjustment_layer(kind, value)
            finally:
                self._guard = False
            self.refresh()

    def _edit_adjustment(self) -> None:
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
            self._guard = True
            try:
                doc.set_layer_props(doc.active_index, locked=value)
            finally:
                self._guard = False

    def _alpha_changed(self, value: bool) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is not None:
            self._guard = True
            try:
                doc.set_layer_props(doc.active_index, lock_alpha=value)
            finally:
                self._guard = False

    def _opacity_changed(self, value: int) -> None:
        self.opacity_label.setText(f"{value} %")
        if self._guard:
            return
        doc = self.app.doc
        if doc is None:
            return
        kind, target = self._selected_target()
        self._guard = True
        try:
            if kind == "group" and target is not None:
                doc.set_group_props(target.id, opacity=value / 100.0)
            elif kind == "layer":
                doc.set_layer_props(doc.active_index, opacity=value / 100.0)
        finally:
            self._guard = False

    def _blend_changed(self, index: int) -> None:
        if self._guard:
            return
        doc = self.app.doc
        if doc is None:
            return
        kind, target = self._selected_target()
        self._guard = True
        try:
            if kind == "group" and target is not None:
                doc.set_group_props(target.id, blend=self.blend.itemData(index))
            elif kind == "layer":
                doc.set_layer_props(doc.active_index, blend=self.blend.itemData(index))
        finally:
            self._guard = False

    def _move(self, delta: int) -> None:
        doc = self.app.doc
        if doc is not None:
            self._guard = True
            try:
                doc.move_layer(doc.active_index, delta)
            finally:
                self._guard = False
            self.refresh()

    def _rename(self, item, column: int) -> None:
        kind, value = self._entry(item)
        doc = self.app.doc
        if doc is None or kind is None:
            return
        name = item.text(0)
        self._guard = True
        try:
            if kind == "layer":
                index = doc.layer_index(value)
                if index >= 0:
                    doc.set_layer_props(index, name=name)
            else:
                doc.set_group_props(value, name=name)
        finally:
            self._guard = False

    def _group_active(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        index = doc.active_index
        layer = doc.active_layer()
        if layer is None:
            return
        if layer.group_id is not None:
            group = doc.group_by_id(layer.group_id)
            if group is not None:
                self.app.notify(f"Calque déjà dans « {group.name} »")
                return
        self._guard = True
        try:
            doc.add_group(indices=[index])
        finally:
            self._guard = False
        self.refresh()

    def _new_group(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        self._guard = True
        try:
            doc.add_group(indices=[])
        finally:
            self._guard = False
        self.refresh()

    def _ungroup_selected(self) -> None:
        kind, value = self._entry(self.tree.currentItem())
        doc = self.app.doc
        if doc is None:
            return
        if kind == "group" and doc.group_by_id(value) is not None:
            self._guard = True
            try:
                doc.remove_group(value, delete_layers=False)
            finally:
                self._guard = False
            self.refresh()
        else:
            self.app.notify("Sélectionnez un groupe")

    def _remove_selected_group(self, delete_layers: bool = False) -> None:
        kind, value = self._entry(self.tree.currentItem())
        doc = self.app.doc
        if doc is None:
            return
        if kind == "group" and doc.group_by_id(value) is not None:
            self._guard = True
            try:
                doc.remove_group(value, delete_layers=delete_layers)
            finally:
                self._guard = False
            self.refresh()
        else:
            self.app.notify("Sélectionnez un groupe")

    def _context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        kind, value = self._entry(item)
        doc = self.app.doc
        if doc is None or kind is None:
            return
        menu = QMenu(self)
        if kind == "group":
            menu.addAction("Renommer", lambda: self.tree.editItem(item, 0))
            menu.addAction("Dissoudre le groupe", self._ungroup_selected)
            menu.addAction("Supprimer le groupe et ses calques",
                           lambda: self._remove_selected_group(delete_layers=True))
        else:
            menu.addAction("Renommer", lambda: self.tree.editItem(item, 0))
            menu.addAction("Grouper ce calque", self._group_active)
            if doc.group_by_id(doc.layers[doc.active_index].group_id
                               if 0 <= doc.active_index < len(doc.layers) else None):
                menu.addAction("Retirer du groupe",
                               lambda: doc.assign_to_group([doc.active_index], None) or self.refresh())
            menu.addSeparator()
            menu.addAction("Supprimer le calque", self.app.action_delete_layer.trigger)
        menu.exec(self.tree.viewport().mapToGlobal(position))


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
    NAMED_KEY = "palettes/named"
    CUSTOM_KEY = "palettes/custom"

    def __init__(self, app):
        super().__init__("Couleurs")
        self.app = app
        self._guard = False
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self._named = self._load_json(self.NAMED_KEY, {})
        self._custom = self._load_json(self.CUSTOM_KEY, [])
        if not isinstance(self._named, dict):
            self._named = {}
        if not isinstance(self._custom, list):
            self._custom = []
        self._palette_colors = list(PALETTE)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.wheel = ColorWheel()
        self.wheel.color_picked.connect(self._wheel_picked)
        layout.addWidget(self.wheel, 1)
        value_row = QHBoxLayout()
        value_row.addWidget(QLabel("Valeur"))
        self.value_slider = QSlider(Qt.Horizontal)
        self.value_slider.setRange(0, 255)
        self.value_slider.setValue(255)
        value_row.addWidget(self.value_slider, 1)
        layout.addLayout(value_row)
        alpha_row = QHBoxLayout()
        alpha_row.addWidget(QLabel("Alpha"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 255)
        self.alpha_slider.setValue(255)
        alpha_row.addWidget(self.alpha_slider, 1)
        layout.addLayout(alpha_row)
        hex_row = QHBoxLayout()
        self.hex_edit = QLineEdit()
        self.hex_edit.setMaxLength(9)
        self.hex_edit.setPlaceholderText("#RRGGBB")
        hex_row.addWidget(self.hex_edit, 1)
        layout.addLayout(hex_row)

        swatches = QHBoxLayout()
        self.fg_button = QPushButton()
        self.fg_button.setFixedHeight(38)
        self.fg_button.setToolTip("Couleur d'avant-plan")
        self.fg_button.clicked.connect(self._pick_fg)
        self.bg_button = QPushButton()
        self.bg_button.setFixedHeight(38)
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

        palette_header = QHBoxLayout()
        palette_header.addWidget(QLabel("Palette"))
        self.palette_box = QComboBox()
        self.palette_box.setToolTip("Charger une palette enregistrée")
        palette_header.addWidget(self.palette_box, 1)
        self.palette_save = QToolButton()
        self.palette_save.setText("+")
        self.palette_save.setToolTip("Enregistrer la palette actuelle")
        self.palette_delete = QToolButton()
        self.palette_delete.setText("−")
        self.palette_delete.setToolTip("Supprimer la palette sélectionnée")
        palette_header.addWidget(self.palette_save)
        palette_header.addWidget(self.palette_delete)
        layout.addLayout(palette_header)

        self.palette_container = QWidget()
        self.palette_layout = QGridLayout(self.palette_container)
        self.palette_layout.setSpacing(3)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.palette_container)

        custom_header = QHBoxLayout()
        custom_header.addWidget(QLabel("Mes couleurs"))
        add_button = QToolButton()
        add_button.setText("+")
        add_button.setToolTip("Ajouter la couleur courante")
        custom_header.addWidget(add_button)
        custom_header.addStretch(1)
        layout.addLayout(custom_header)
        self.custom_container = QWidget()
        self.custom_layout = QGridLayout(self.custom_container)
        self.custom_layout.setSpacing(3)
        self.custom_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.custom_container)

        layout.addWidget(QLabel("Couleurs récentes"))
        self.recent_container = QWidget()
        self.recent_layout = QGridLayout(self.recent_container)
        self.recent_layout.setSpacing(3)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.recent_container)
        layout.addStretch(1)
        self.setWidget(container)

        self.value_slider.valueChanged.connect(self._value_changed)
        self.alpha_slider.valueChanged.connect(self._alpha_changed)
        self.hex_edit.editingFinished.connect(self._hex_changed)
        self.palette_save.clicked.connect(self._save_palette)
        self.palette_delete.clicked.connect(self._delete_palette)
        self.palette_box.currentIndexChanged.connect(self._palette_selected)
        add_button.clicked.connect(self._add_custom)
        app.colors_changed.connect(self.refresh)
        app.doc_changed.connect(self.refresh)
        self._fill_palette_combo()
        self._fill_palette()
        self.refresh()

    @staticmethod
    def _load_json(key: str, fallback):
        from PySide6.QtCore import QSettings

        settings = QSettings("PaintAmeliore", "PaintAmeliore")
        raw = settings.value(key, "")
        if not raw:
            return fallback
        try:
            import json

            return json.loads(raw)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _store_json(key: str, value) -> None:
        from PySide6.QtCore import QSettings

        import json

        settings = QSettings("PaintAmeliore", "PaintAmeliore")
        settings.setValue(key, json.dumps(value, ensure_ascii=False))

    def _fill_palette_combo(self) -> None:
        self._guard = True
        self.palette_box.clear()
        self.palette_box.addItem("Palette par défaut", None)
        for name in sorted(self._named):
            self.palette_box.addItem(name, name)
        self._guard = False

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _fill_palette(self) -> None:
        self._clear_layout(self.palette_layout)
        for index, color in enumerate(self._palette_colors[:36]):
            button = QPushButton()
            button.setFixedSize(24, 24)
            button.setStyleSheet(
                f"background:{color}; border:1px solid #14161a; border-radius:4px;"
            )
            button.setToolTip(color)
            button.clicked.connect(lambda _=False, c=color: self.app.set_fg_color(QColor(c)))
            self.palette_layout.addWidget(button, index // 6, index % 6)

    def _fill_custom(self) -> None:
        self._clear_layout(self.custom_layout)
        for index, color in enumerate(self._custom[:24]):
            button = QPushButton()
            button.setFixedSize(24, 24)
            button.setStyleSheet(
                f"background:{color}; border:1px solid #14161a; border-radius:4px;"
            )
            button.setToolTip(color)
            button.clicked.connect(lambda _=False, c=color: self.app.set_fg_color(QColor(c)))
            button.setContextMenuPolicy(Qt.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda _pos, i=index: self._remove_custom(i))
            self.custom_layout.addWidget(button, index // 6, index % 6)

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
        self._guard = True
        self.wheel.set_color(self.app.fg)
        self.value_slider.setValue(self.app.fg.value())
        self.alpha_slider.setValue(self.app.fg.alpha())
        self.hex_edit.setText(self.app.fg.name(QColor.HexRgb).upper())
        self._guard = False
        self._clear_layout(self.recent_layout)
        for index, color in enumerate(self.app.recent[:12]):
            button = QPushButton()
            button.setFixedSize(24, 24)
            button.setStyleSheet(
                f"background:{color.name()}; border:1px solid #14161a; border-radius:4px;"
            )
            button.setToolTip(color.name())
            button.clicked.connect(lambda _=False, c=color: self.app.set_fg_color(QColor(c)))
            self.recent_layout.addWidget(button, index // 6, index % 6)

    def _wheel_picked(self, color: QColor) -> None:
        if self._guard:
            return
        color.setAlpha(self.app.fg.alpha())
        self.app.set_fg_color(color)

    def _value_changed(self, value: int) -> None:
        if self._guard:
            return
        self.wheel.set_value(value)
        self.app.set_fg_color(self.wheel.color())

    def _alpha_changed(self, value: int) -> None:
        if self._guard:
            return
        self.wheel.set_alpha(value)
        self.app.set_fg_color(self.wheel.color())

    def _hex_changed(self) -> None:
        text = self.hex_edit.text().strip()
        if not text.startswith("#"):
            text = "#" + text
        color = QColor(text)
        if color.isValid():
            self.app.set_fg_color(color)
        else:
            self.refresh()

    def _add_custom(self) -> None:
        name = self.app.fg.name(QColor.HexArgb)
        if name not in self._custom:
            self._custom.insert(0, name)
            del self._custom[24:]
            self._store_json(self.CUSTOM_KEY, self._custom)
            self._fill_custom()
            self.app.notify("Couleur ajoutée à mes couleurs")

    def _remove_custom(self, index: int) -> None:
        if 0 <= index < len(self._custom):
            del self._custom[index]
            self._store_json(self.CUSTOM_KEY, self._custom)
            self._fill_custom()

    def _palette_selected(self, index: int) -> None:
        if self._guard:
            return
        name = self.palette_box.itemData(index)
        if name and name in self._named:
            self._palette_colors = list(self._named[name])
        else:
            self._palette_colors = list(PALETTE)
        self._fill_palette()

    def _save_palette(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Enregistrer la palette", "Nom :")
        name = name.strip()
        if not ok or not name:
            return
        self._named[name] = list(self._palette_colors)
        self._store_json(self.NAMED_KEY, self._named)
        self._fill_palette_combo()
        self.palette_box.setCurrentIndex(self.palette_box.findData(name))
        self.app.notify(f"Palette « {name} » enregistrée")

    def _delete_palette(self) -> None:
        name = self.palette_box.currentData()
        if not name or name not in self._named:
            return
        del self._named[name]
        self._store_json(self.NAMED_KEY, self._named)
        self._fill_palette_combo()
        self._palette_colors = list(PALETTE)
        self._fill_palette()
        self.app.notify(f"Palette « {name} » supprimée")

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


class NavigatorView(QWidget):
    def __init__(self, dock):
        super().__init__()
        self.dock = dock
        self.setMinimumSize(180, 130)
        self.setCursor(Qt.CrossCursor)
        self._dragging = False

    def _geometry(self):
        from PySide6.QtCore import QRectF

        doc = self.dock.app.doc
        if doc is None:
            return None, None
        area = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        ratio = doc.size.width() / max(1, doc.size.height())
        if area.width() / max(1.0, area.height()) > ratio:
            height = area.height()
            width = height * ratio
        else:
            width = area.width()
            height = width / ratio
        box = QRectF(
            area.center().x() - width / 2,
            area.center().y() - height / 2,
            width,
            height,
        )
        return doc, box

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1b1d21"))
        doc, box = self._geometry()
        if doc is None or box is None:
            painter.end()
            return
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        preview = doc.preview_image if doc.preview_image is not None else doc.composite()
        painter.setOpacity(0.85)
        painter.drawImage(box, preview)
        painter.setOpacity(1.0)
        painter.setPen(QColor("#5b616b"))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(box)
        canvas = self.dock.app.canvas
        visible = canvas.visible_doc_rect()
        if not visible.isEmpty():
            scale_x = box.width() / max(1, doc.size.width())
            scale_y = box.height() / max(1, doc.size.height())
            rect = box.adjusted(visible.left() * scale_x, visible.top() * scale_y,
                                -(doc.size.width() - visible.right() - 1) * scale_x,
                                -(doc.size.height() - visible.bottom() - 1) * scale_y)
            painter.setPen(QColor("#f97316"))
            painter.drawRect(rect)
        painter.end()

    def _center(self, position) -> None:
        doc, box = self._geometry()
        if doc is None or box is None:
            return
        from PySide6.QtCore import QPointF

        x = (position.x() - box.left()) / max(1e-6, box.width()) * doc.size.width()
        y = (position.y() - box.top()) / max(1e-6, box.height()) * doc.size.height()
        self.dock.app.canvas.center_on(QPointF(x, y))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._center(event.position())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._center(event.position())

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False


class NavigatorDock(QDockWidget):
    def __init__(self, app):
        super().__init__("Navigateur")
        self.app = app
        self.setObjectName("navigator")
        self.view = NavigatorView(self)
        self.setWidget(self.view)
        self._timer = QTimer(self)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self.view.update)
        app.doc_changed.connect(self.view.update)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)
