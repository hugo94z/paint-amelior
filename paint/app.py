from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, QSettings, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
)

from .brush import StampCache
from .config import APP_NAME, APP_VERSION, Settings, load_settings
from .document import Document
from .filters import apply_to_document
from .io.image_io import EXPORT_FILTER, export_image, load_image
from .io.project_io import load_project, save_project
from .layer import Layer
from .tools import build_tools
from .tools.base import BaseTool
from .ui.canvas import Canvas, CanvasHost
from .ui.docks import ColorDock, HistoryDock, LayersDock
from .ui.icons import tool_icon
from .ui.options_bar import OptionsBar
from .ui.theme import apply_theme

IMAGE_OPEN_FILTER = (
    "Projet Paint (*.paint);;Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"
    ";;Tous les fichiers (*)"
)
SAVE_FILTER = (
    "Projet Paint (*.paint);;PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;BMP (*.bmp);;TIFF (*.tif)"
)

SHORTCUTS_TEXT = """<b>Outils</b><br>
B pinceau • E gomme • G pot de peinture • I pipette<br>
L ligne • R rectangle • O ellipse • U rectangle arrondi<br>
Y polygone • D dégradé • T texte • M sélection<br><br>
<b>Pinceau</b><br>
[ / ] taille du pinceau • Alt pipette temporaire<br><br>
<b>Fichier</b><br>
Ctrl+N nouveau • Ctrl+O ouvrir • Ctrl+S enregistrer • Ctrl+Maj+S enregistrer sous<br><br>
<b>Édition</b><br>
Ctrl+Z annuler • Ctrl+Y rétablir • Ctrl+X/C/V couper/copier/coller<br>
Suppr effacer la sélection • Ctrl+A tout sélectionner • Ctrl+D désélectionner<br><br>
<b>Affichage</b><br>
Ctrl+molette zoom • molette défilement • Espace+glisser déplacement<br>
Ctrl+0 ajuster • Ctrl+1 taille réelle • F11 plein écran<br><br>
<b>Calques</b><br>
Ctrl+Maj+N nouveau calque • Ctrl+J dupliquer • Ctrl+Maj+E fusionner vers le bas"""


class NewDocumentDialog(QDialog):
    def __init__(self, parent, width: int = 1600, height: int = 1000):
        super().__init__(parent)
        self.setWindowTitle("Nouveau document")
        self.setMinimumWidth(360)
        self.preset = QComboBox()
        self.preset.addItem("Personnalisé", None)
        for label, size in (
            ("1600 × 1000", (1600, 1000)),
            ("1920 × 1080", (1920, 1080)),
            ("2048 × 2048", (2048, 2048)),
            ("3840 × 2160 (4K)", (3840, 2160)),
            ("A4 300 dpi", (2480, 3508)),
            ("A3 300 dpi", (3508, 4961)),
        ):
            self.preset.addItem(label, size)
        self.width_box = QSpinBox()
        self.width_box.setRange(1, 16384)
        self.width_box.setValue(width)
        self.width_box.setSuffix(" px")
        self.height_box = QSpinBox()
        self.height_box.setRange(1, 16384)
        self.height_box.setValue(height)
        self.height_box.setSuffix(" px")
        self.background = QComboBox()
        self.background.addItem("Blanc", "white")
        self.background.addItem("Transparent", "transparent")
        self.preset.currentIndexChanged.connect(self._preset_changed)
        form = QFormLayout()
        form.addRow("Format", self.preset)
        form.addRow("Largeur", self.width_box)
        form.addRow("Hauteur", self.height_box)
        form.addRow("Fond", self.background)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _preset_changed(self, index: int) -> None:
        size = self.preset.itemData(index)
        if size:
            self.width_box.setValue(size[0])
            self.height_box.setValue(size[1])

    def document_size(self) -> tuple[int, int]:
        return self.width_box.value(), self.height_box.value()

    def background_color(self) -> QColor | None:
        return QColor("#ffffff") if self.background.currentData() == "white" else None


class ResizeDialog(QDialog):
    def __init__(self, parent, width: int, height: int):
        super().__init__(parent)
        self.setWindowTitle("Redimensionner l'image")
        self.setMinimumWidth(320)
        self._ratio = width / max(1, height)
        self._guard = False
        self.width_box = QSpinBox()
        self.width_box.setRange(1, 16384)
        self.width_box.setValue(width)
        self.width_box.setSuffix(" px")
        self.height_box = QSpinBox()
        self.height_box.setRange(1, 16384)
        self.height_box.setValue(height)
        self.height_box.setSuffix(" px")
        self.keep_ratio = QCheckBox("Conserver les proportions")
        self.keep_ratio.setChecked(True)
        self.smooth = QCheckBox("Lissage (haute qualité)")
        self.smooth.setChecked(True)
        self.width_box.valueChanged.connect(self._width_changed)
        self.height_box.valueChanged.connect(self._height_changed)
        form = QFormLayout()
        form.addRow("Largeur", self.width_box)
        form.addRow("Hauteur", self.height_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.keep_ratio)
        layout.addWidget(self.smooth)
        layout.addWidget(buttons)

    def _width_changed(self, value: int) -> None:
        if self._guard or not self.keep_ratio.isChecked():
            return
        self._guard = True
        self.height_box.setValue(max(1, round(value / self._ratio)))
        self._guard = False

    def _height_changed(self, value: int) -> None:
        if self._guard or not self.keep_ratio.isChecked():
            return
        self._guard = True
        self.width_box.setValue(max(1, round(value * self._ratio)))
        self._guard = False

    def result_values(self) -> tuple[int, int, bool]:
        return self.width_box.value(), self.height_box.value(), self.smooth.isChecked()


class MainWindow(QMainWindow):
    colors_changed = Signal()
    doc_changed = Signal()
    DROP_SUFFIXES = {
        ".paint", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif",
    }

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.qsettings = QSettings("PaintAmeliore", "PaintAmeliore")
        self.recent_files = self._load_recent()
        self.stamp_cache = StampCache(settings.stamp_cache_bytes)
        self.fg = QColor("#111827")
        self.bg = QColor("#ffffff")
        self.recent = [
            QColor("#111827"), QColor("#ef4444"), QColor("#f59e0b"),
            QColor("#10b981"), QColor("#3b82f6"), QColor("#8b5cf6"),
        ]
        self.doc: Document | None = None
        self.tools = {tool.id: tool for tool in build_tools(self)}
        self.tool: BaseTool = self.tools["brush"]
        self.tool_actions: dict[str, QAction] = {}
        self._hooks = []
        self.canvas = Canvas(self)
        self.canvas_host = CanvasHost(self.canvas)
        self.setCentralWidget(self.canvas_host)
        self.setAcceptDrops(True)
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_docks()
        self._build_status()
        QThreadPool.globalInstance().setMaxThreadCount(max(1, settings.threads))
        self.resize(1480, 940)
        self.setWindowIcon(tool_icon("brush", size=64))
        self._create_document(1600, 1000, QColor("#ffffff"))
        self._restore_session()
        tool_id = str(self.qsettings.value("tool/last", "brush"))
        self.set_tool(tool_id if tool_id in self.tools else "brush")

    def _action(self, text, slot, shortcut=None, checkable=False, icon=None) -> QAction:
        action = QAction(text, self)
        if icon:
            action.setIcon(tool_icon(icon))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        self.action_new = self._action("Nouveau…", self.new_document_dialog, "Ctrl+N")
        self.action_open = self._action("Ouvrir…", self.open_document, "Ctrl+O")
        self.action_save = self._action("Enregistrer", self.save_document, "Ctrl+S")
        self.action_save_as = self._action("Enregistrer sous…", self.save_document_as, "Ctrl+Shift+S")
        self.action_export = self._action("Exporter une image…", self.export_document, "Ctrl+E")
        self.action_quit = self._action("Quitter", self.close, "Ctrl+Q")

        self.action_undo = self._action("Annuler", self.undo, "Ctrl+Z")
        self.action_redo = self._action("Rétablir", self.redo, "Ctrl+Y")
        self.action_redo_alt = self._action("Rétablir", self.redo, "Ctrl+Shift+Z")
        self.action_cut = self._action("Couper", self.cut, "Ctrl+X")
        self.action_copy = self._action("Copier", self.copy, "Ctrl+C")
        self.action_paste = self._action("Coller", self.paste, "Ctrl+V")
        self.action_delete = self._action("Effacer la sélection", self.delete_selection, "Del")
        self.action_select_all = self._action("Tout sélectionner", self.select_all, "Ctrl+A")
        self.action_deselect = self._action("Désélectionner", self.deselect, "Ctrl+D")
        self.action_invert_selection = self._action(
            "Inverser la sélection", self.invert_selection, "Ctrl+Shift+I"
        )
        self.action_swap_colors = self._action("Échanger les couleurs", self.swap_colors, "X")

        self.action_resize = self._action("Redimensionner l'image…", self.resize_dialog)
        self.action_rotate_left = self._action(
            "Pivoter 90° à gauche", lambda: self.transform_document(-90, label="Rotation à gauche")
        )
        self.action_rotate_right = self._action(
            "Pivoter 90° à droite", lambda: self.transform_document(90, label="Rotation à droite")
        )
        self.action_rotate_180 = self._action(
            "Pivoter 180°", lambda: self.transform_document(180, label="Rotation 180°")
        )
        self.action_flip_h = self._action(
            "Miroir horizontal",
            lambda: self.transform_document(0, flip_h=True, label="Miroir horizontal"),
        )
        self.action_flip_v = self._action(
            "Miroir vertical",
            lambda: self.transform_document(0, flip_v=True, label="Miroir vertical"),
        )
        self.action_new_layer = self._action("Nouveau calque", self.new_layer, "Ctrl+Shift+N")
        self.action_duplicate_layer = self._action("Dupliquer le calque", self.duplicate_layer, "Ctrl+J")
        self.action_delete_layer = self._action("Supprimer le calque", self.delete_layer)
        self.action_merge_layer = self._action("Fusionner vers le bas", self.merge_layer, "Ctrl+Shift+E")

        self.action_zoom_in = self._action("Zoom avant", lambda: self.canvas.zoom_by(1.25), "Ctrl+=")
        self.action_zoom_out = self._action("Zoom arrière", lambda: self.canvas.zoom_by(1 / 1.25), "Ctrl+-")
        self.action_zoom_100 = self._action("Taille réelle", lambda: self.canvas.set_zoom(1.0), "Ctrl+1")
        self.action_zoom_fit = self._action("Ajuster à la fenêtre", self.canvas.fit, "Ctrl+0")
        self.action_fullscreen = self._action("Plein écran", self.toggle_fullscreen, "F11")

        self.action_shortcuts = self._action("Raccourcis clavier", self.show_shortcuts)
        self.action_system = self._action("Configuration système", self.show_system_info)
        self.action_about = self._action("À propos", self.show_about)

        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)
        self.action_redo_alt.setEnabled(False)
        self.action_size_up = self._action("Augmenter la taille", lambda: self.adjust_size(2), "]")
        self.action_size_down = self._action("Diminuer la taille", lambda: self.adjust_size(-2), "[")
        self.addAction(self.action_redo_alt)
        self.addAction(self.action_size_up)
        self.addAction(self.action_size_down)
        self.addAction(self.action_swap_colors)

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Fichier")
        for action in (self.action_new, self.action_open):
            file_menu.addAction(action)
        self.recent_menu = QMenu("Documents récents", self)
        file_menu.addMenu(self.recent_menu)
        self._update_recent_menu()
        file_menu.addSeparator()
        file_menu.addSeparator()
        for action in (self.action_save, self.action_save_as, self.action_export):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.action_quit)

        edit_menu = bar.addMenu("&Édition")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        for action in (self.action_cut, self.action_copy, self.action_paste, self.action_delete):
            edit_menu.addAction(action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_select_all)
        edit_menu.addAction(self.action_deselect)
        edit_menu.addAction(self.action_invert_selection)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_swap_colors)

        image_menu = bar.addMenu("&Image")
        image_menu.addAction(self.action_resize)
        image_menu.addSeparator()
        for action in (self.action_rotate_left, self.action_rotate_right,
                       self.action_rotate_180, self.action_flip_h, self.action_flip_v):
            image_menu.addAction(action)
        image_menu.addSeparator()
        filters = [
            ("Flou gaussien…", self.filter_blur),
            ("Netteté…", self.filter_sharpen),
            ("Luminosité…", self.filter_brightness),
            ("Contraste…", self.filter_contrast),
            ("Saturation…", self.filter_saturation),
            ("Niveaux de gris…", self.filter_grayscale),
            ("Pixeliser…", self.filter_pixelate),
            ("Inverser les couleurs", self.filter_invert),
        ]
        for text, slot in filters:
            image_menu.addAction(self._action(text, slot))

        layer_menu = bar.addMenu("&Calque")
        for action in (self.action_new_layer, self.action_duplicate_layer,
                       self.action_delete_layer, self.action_merge_layer):
            layer_menu.addAction(action)

        tools_menu = bar.addMenu("&Outils")
        self.tools_menu = tools_menu

        view_menu = bar.addMenu("&Affichage")
        for action in (self.action_zoom_in, self.action_zoom_out, self.action_zoom_100,
                       self.action_zoom_fit):
            view_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(self.action_fullscreen)

        help_menu = bar.addMenu("Aid&e")
        help_menu.addAction(self.action_shortcuts)
        help_menu.addAction(self.action_system)
        help_menu.addAction(self.action_about)

    def _build_toolbars(self) -> None:
        toolbar = QToolBar("Outils")
        toolbar.setObjectName("toolbox")
        toolbar.setOrientation(Qt.Vertical)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        group = QActionGroup(self)
        group.setExclusive(True)
        for tool in self.tools.values():
            action = QAction(tool_icon(tool.icon), tool.label, self)
            action.setCheckable(True)
            if tool.shortcut:
                action.setShortcut(QKeySequence(tool.shortcut))
            action.setToolTip(f"{tool.label} ({tool.shortcut})" if tool.shortcut else tool.label)
            action.triggered.connect(lambda _=False, tid=tool.id: self.set_tool(tid))
            group.addAction(action)
            toolbar.addAction(action)
            self.addAction(action)
            self.tools_menu.addAction(action)
            self.tool_actions[tool.id] = action
            if tool.id in ("picker", "polygon", "text"):
                toolbar.addSeparator()
        self.tool_actions["brush"].setChecked(True)

        self.options = OptionsBar(self)
        options_bar = QToolBar("Options")
        options_bar.setObjectName("options")
        options_bar.setMovable(False)
        options_bar.setFloatable(False)
        options_bar.addWidget(self.options)
        self.addToolBar(Qt.TopToolBarArea, options_bar)

    def _build_docks(self) -> None:
        self.color_dock = ColorDock(self)
        self.layers_dock = LayersDock(self)
        self.history_dock = HistoryDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.color_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.layers_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)
        self.resizeDocks([self.color_dock, self.layers_dock, self.history_dock],
                         [220, 240, 220], Qt.Vertical)

    def _build_status(self) -> None:
        self.status_coords = QLabel("—")
        self.status_size = QLabel("—")
        self.status_zoom = QComboBox()
        self.status_zoom.setEditable(True)
        self.status_zoom.setFixedWidth(96)
        self.status_zoom.addItems(["25 %", "50 %", "75 %", "100 %", "150 %", "200 %", "400 %", "800 %"])
        self.status_zoom.setCurrentText("100 %")
        self.status_zoom.activated.connect(self._zoom_preset)
        self.status_zoom.lineEdit().returnPressed.connect(self._zoom_typed)
        sep_style = "color:#4a4e56;"
        self.status_coords.setMinimumWidth(90)
        self.status_size.setMinimumWidth(90)
        self.statusBar().addWidget(self.status_coords)
        sep1 = QLabel("|")
        sep1.setStyleSheet(sep_style)
        self.statusBar().addWidget(sep1)
        self.statusBar().addWidget(self.status_size)
        sep2 = QLabel("|")
        sep2.setStyleSheet(sep_style)
        self.statusBar().addWidget(sep2)
        self.statusBar().addWidget(self.status_zoom)
        hint = QLabel("Ctrl+molette = zoom   •   Espace+glisser = déplacer   •   glisser un fichier pour l'ouvrir")
        hint.setStyleSheet("color:#6f757f;")
        self.statusBar().addPermanentWidget(hint)

    def _zoom_preset(self, index: int) -> None:
        self._apply_zoom_text(self.status_zoom.itemText(index))

    def _zoom_typed(self) -> None:
        self._apply_zoom_text(self.status_zoom.currentText())

    def _apply_zoom_text(self, text: str) -> None:
        try:
            value = float(str(text).replace("%", "").replace(",", ".").strip())
        except ValueError:
            self.update_zoom_label()
            return
        if value <= 0:
            self.update_zoom_label()
            return
        self.canvas.set_zoom(value / 100.0)

    def set_document(self, doc: Document) -> None:
        if self.doc is not None:
            for signal, slot in self._hooks:
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self.doc = doc
        self.canvas.set_doc(doc)
        self._hooks = [
            (doc.layers_changed, self._on_layers_changed),
            (doc.history_changed, self._sync_history),
            (doc.modified_changed, self._update_title),
            (doc.size_changed, self._on_size_changed),
        ]
        for signal, slot in self._hooks:
            signal.connect(slot)
        self._sync_history()
        self._on_layers_changed()
        self._update_title()
        self.status_size.setText(f"{doc.size.width()} × {doc.size.height()} px")
        self.update_zoom_label()
        self.doc_changed.emit()

    def _on_layers_changed(self) -> None:
        self.doc_changed.emit()
        self.canvas.update()

    def _on_size_changed(self) -> None:
        if self.doc is not None:
            self.status_size.setText(f"{self.doc.size.width()} × {self.doc.size.height()} px")
            self.canvas.fit()

    def _sync_history(self) -> None:
        doc = self.doc
        can_undo = doc is not None and doc.history.can_undo
        can_redo = doc is not None and doc.history.can_redo
        self.action_undo.setEnabled(can_undo)
        self.action_redo.setEnabled(can_redo)
        self.action_redo_alt.setEnabled(can_redo)
        self.doc_changed.emit()

    def _update_title(self, *args) -> None:
        if self.doc is None:
            self.setWindowTitle(APP_NAME)
            return
        name = self.doc.path.name if self.doc.path else "Sans titre"
        mark = " *" if self.doc.is_modified() else ""
        self.setWindowTitle(f"{name}{mark} — {APP_NAME}")

    def _create_document(self, width: int, height: int, background: QColor | None) -> None:
        doc = Document.new(width, height, background,
                           undo_budget=self.settings.undo_budget_bytes)
        doc.invalidate_all()
        self.set_document(doc)
        self.canvas.fit()
        self.notify(f"Document {width} × {height} créé")

    def new_document_dialog(self) -> None:
        self.commit_floating()
        if not self.maybe_save():
            return
        dialog = NewDocumentDialog(self)
        if dialog.exec() == QDialog.Accepted:
            width, height = dialog.document_size()
            self._create_document(width, height, dialog.background_color())

    def open_document(self) -> None:
        self.commit_floating()
        if not self.maybe_save():
            return
        start = str(self.doc.path.parent) if self.doc and self.doc.path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir", start, IMAGE_OPEN_FILTER)
        if not path:
            return
        self.load_path(Path(path))

    def load_path(self, path: Path) -> None:
        if path.suffix.lower() == ".paint":
            doc = load_project(path, self.settings.undo_budget_bytes)
            if doc is None:
                QMessageBox.warning(self, APP_NAME, "Impossible d'ouvrir ce projet.")
                return
            doc.invalidate_all()
            self.set_document(doc)
            self.canvas.fit()
            self._add_recent(path)
            self.notify(f"Projet ouvert : {path.name}")
            return
        image = load_image(path)
        if image is None:
            QMessageBox.warning(self, APP_NAME, "Format d'image non pris en charge.")
            return
        doc = Document(QSize(image.width(), image.height()),
                       undo_budget=self.settings.undo_budget_bytes)
        layer = Layer(path.stem or "Image", doc.size)
        layer.image = image
        doc.add_layer_raw(layer)
        doc.active_index = 0
        doc.invalidate_all()
        doc.history.clear()
        doc.path = None
        doc.mark_modified(False)
        self.set_document(doc)
        self.canvas.fit()
        self._add_recent(path)
        self.notify(f"Image ouverte : {path.name}")

    def _default_name(self, suffix: str) -> str:
        if self.doc and self.doc.path:
            return str(self.doc.path.with_suffix(suffix))
        pictures = Path.home() / "Pictures"
        base = pictures if pictures.is_dir() else Path.home()
        return str(base / f"sans_titre{suffix}")

    def save_document(self) -> bool:
        doc = self.doc
        if doc is None:
            return False
        if doc.path is None:
            return self.save_document_as()
        return self._save_to(doc.path)

    def commit_floating(self) -> None:
        doc = self.doc
        if doc is not None and doc.floating is not None and hasattr(self.tool, "drop_floating"):
            self.tool.drop_floating()

    def _save_to(self, path: Path) -> bool:
        doc = self.doc
        if doc is None:
            return False
        self.commit_floating()
        if path.suffix.lower() == ".paint":
            ok = save_project(doc, path)
        else:
            ok = export_image(doc, path)
        if ok:
            doc.path = path
            doc.mark_modified(False)
            self._update_title()
            self._add_recent(path)
            self.notify(f"Enregistré : {path.name}")
        else:
            QMessageBox.warning(self, APP_NAME, "Échec de l'enregistrement.")
        return ok

    def save_document_as(self) -> bool:
        if self.doc is None:
            return False
        suggested = self._default_name(".paint")
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", suggested, SAVE_FILTER)
        if not path:
            return False
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(".paint")
        return self._save_to(target)

    def export_document(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        path, _ = QFileDialog.getSaveFileName(self, "Exporter une image",
                                             self._default_name(".png"), EXPORT_FILTER)
        if path:
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".png")
            if export_image(self.doc, target):
                self.notify(f"Image exportée : {target.name}")

    def maybe_save(self) -> bool:
        doc = self.doc
        self.commit_floating()
        if doc is None or not doc.is_modified():
            return True
        answer = QMessageBox.question(
            self,
            "Modifications non enregistrées",
            "Voulez-vous enregistrer les modifications ?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return self.save_document()
        return True

    def closeEvent(self, event) -> None:
        if self.maybe_save():
            self._save_session()
            event.accept()
        else:
            event.ignore()

    def _load_recent(self) -> list[str]:
        value = self.qsettings.value("files/recent", [])
        if isinstance(value, str):
            value = [value]
        result = []
        for item in value or []:
            try:
                path = Path(str(item))
                if path.is_file() and str(path) not in result:
                    result.append(str(path))
            except OSError:
                continue
        return result[:8]

    def _save_session(self) -> None:
        self.qsettings.setValue("window/geometry", self.saveGeometry())
        self.qsettings.setValue("window/state", self.saveState())
        self.qsettings.setValue("tool/last", self.tool.id)
        self.qsettings.setValue("colors/fg", self.fg.name(QColor.HexArgb))
        self.qsettings.setValue("colors/bg", self.bg.name(QColor.HexArgb))
        self.qsettings.setValue("files/recent", self.recent_files)

    def _restore_session(self) -> None:
        geometry = self.qsettings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.qsettings.value("window/state")
        if state is not None:
            self.restoreState(state)
        for key, attr in (("colors/fg", "fg"), ("colors/bg", "bg")):
            stored = self.qsettings.value(key)
            if stored:
                color = QColor(str(stored))
                if color.isValid():
                    setattr(self, attr, color)
        self._update_recent_menu()
        self.colors_changed.emit()

    def _update_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        if not self.recent_files:
            action = self.recent_menu.addAction("Aucun document récent")
            action.setEnabled(False)
            return
        for path in self.recent_files:
            action = self.recent_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda _=False, p=path: self.open_recent(p))
        self.recent_menu.addSeparator()
        clear = self.recent_menu.addAction("Effacer la liste")
        clear.triggered.connect(self._clear_recent)

    def _add_recent(self, path) -> None:
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            return
        self.recent_files = [resolved] + [p for p in self.recent_files if p != resolved]
        del self.recent_files[8:]
        self.qsettings.setValue("files/recent", self.recent_files)
        self._update_recent_menu()

    def _remove_recent(self, path: str) -> None:
        self.recent_files = [p for p in self.recent_files if p != path]
        self.qsettings.setValue("files/recent", self.recent_files)
        self._update_recent_menu()

    def _clear_recent(self) -> None:
        self.recent_files = []
        self.qsettings.setValue("files/recent", self.recent_files)
        self._update_recent_menu()

    def open_recent(self, path: str) -> None:
        target = Path(path)
        if not target.is_file():
            self._remove_recent(path)
            self.notify("Fichier introuvable, entrée retirée")
            return
        if not self.maybe_save():
            return
        self.load_path(target)

    def can_drop(self, mime) -> bool:
        for url in mime.urls():
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in self.DROP_SUFFIXES:
                return True
        return False

    def drop_mime(self, mime) -> None:
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in self.DROP_SUFFIXES:
                if not self.maybe_save():
                    return
                self.load_path(path)
                return

    def transform_document(self, angle: int = 0, flip_h: bool = False, flip_v: bool = False,
                           label: str = "Transformation") -> None:
        if self.doc is None:
            return
        self.commit_floating()
        self.doc.transform_image(angle, flip_h, flip_v, label)
        self._on_size_changed()
        self.notify("Transformation appliquée")

    def invert_selection(self) -> None:
        if self.doc is None:
            return
        self.doc.invert_selection()
        self.canvas.update()
        self.notify("Sélection inversée")

    def set_tool(self, tool_id: str) -> None:
        tool = self.tools.get(tool_id)
        if tool is None or tool is self.tool:
            return
        if self.doc is not None and self.doc.floating is not None and hasattr(self.tool, "drop_floating"):
            self.tool.drop_floating()
        self.tool.deactivate()
        self.tool = tool
        action = self.tool_actions.get(tool_id)
        if action is not None:
            action.setChecked(True)
        tool.activate()
        self.options.build(tool)
        self.canvas.setCursor(tool.cursor())
        self.canvas.update()
        self.notify(tool.label)

    def undo(self) -> None:
        if self.doc is not None and self.doc.history.undo():
            self.canvas.update()

    def redo(self) -> None:
        if self.doc is not None and self.doc.history.redo():
            self.canvas.update()

    def _selection_image(self) -> QImage | None:
        doc = self.doc
        if doc is None:
            return None
        self.commit_floating()
        layer = doc.active_layer()
        if layer is None:
            return None
        bounds = doc.selection.boundingRect() if doc.has_selection() else doc.rect()
        if bounds.isEmpty():
            return None
        image = layer.image.copy(bounds)
        if doc.has_selection():
            mask = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
            mask.fill(Qt.transparent)
            painter = QPainter(mask)
            painter.setClipRegion(doc.selection.translated(-bounds.left(), -bounds.top()))
            painter.fillRect(mask.rect(), Qt.white)
            painter.end()
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, mask)
            painter.end()
        return image

    def copy(self) -> None:
        image = self._selection_image()
        if image is None:
            return
        QApplication.clipboard().setImage(image)
        self.notify("Sélection copiée")

    def cut(self) -> None:
        image = self._selection_image()
        if image is None:
            return
        QApplication.clipboard().setImage(image)
        self.delete_selection()
        self.notify("Sélection coupée")

    def paste(self) -> None:
        doc = self.doc
        if doc is None:
            return
        image = QApplication.clipboard().image()
        if image.isNull():
            self.notify("Presse-papiers vide")
            return
        if doc.floating is not None and hasattr(self.tool, "drop_floating"):
            self.tool.drop_floating()
        image = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        pos = QPoint(max(0, (doc.size.width() - image.width()) // 2),
                     max(0, (doc.size.height() - image.height()) // 2))
        doc.floating = image
        doc.floating_pos = pos
        rect = QRect(pos, image.size())
        path = QPainterPath()
        path.addRect(rect)
        doc.set_selection(QRegion(rect), path)
        self.set_tool("select")
        self.canvas.update()
        self.notify("Image collée : glissez pour la positionner")

    def delete_selection(self) -> None:
        doc = self.doc
        if doc is None:
            return
        if doc.floating is not None:
            doc.floating = None
            doc.clear_selection()
            self.canvas.update()
            return
        if not doc.has_selection():
            return
        layer = doc.active_layer()
        if layer is None:
            return
        bounds = doc.selection.boundingRect()
        tx = doc.history.begin("Effacer la sélection")
        tx.touch(layer, bounds)
        painter = QPainter(layer.image)
        painter.setClipRegion(doc.selection)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(bounds, Qt.transparent)
        painter.end()
        doc.invalidate(bounds)
        tx.commit()
        self.canvas.update()

    def select_all(self) -> None:
        if self.doc is None:
            return
        if self.doc.floating is not None and hasattr(self.tool, "drop_floating"):
            self.tool.drop_floating()
        self.doc.select_all()
        self.canvas.update()

    def deselect(self) -> None:
        if self.doc is None:
            return
        if self.doc.floating is not None and hasattr(self.tool, "drop_floating"):
            self.tool.drop_floating()
        self.doc.clear_selection()
        self.canvas.update()

    def new_layer(self) -> None:
        if self.doc is not None:
            self.doc.add_layer()

    def duplicate_layer(self) -> None:
        if self.doc is not None:
            self.doc.duplicate_layer()

    def delete_layer(self) -> None:
        if self.doc is not None:
            self.doc.remove_layer()

    def merge_layer(self) -> None:
        if self.doc is not None:
            self.doc.merge_down()

    def resize_dialog(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        dialog = ResizeDialog(self, self.doc.size.width(), self.doc.size.height())
        if dialog.exec() == QDialog.Accepted:
            width, height, smooth = dialog.result_values()
            self.doc.resize_image(width, height, smooth)
            self.canvas.fit()
            self.status_size.setText(f"{width} × {height} px")
            self.notify("Image redimensionnée")

    def _apply_filter(self, name: str, label: str, value: float = 0.0) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        if apply_to_document(self.doc, name, value, label):
            self.canvas.update()
            self.notify(f"{label} appliqué")

    def filter_blur(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Flou gaussien", "Rayon (px) :", 4.0, 0.1, 100.0, 1)
        if ok:
            self._apply_filter("blur", "Flou gaussien", value)

    def filter_sharpen(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Netteté", "Intensité (%) :", 120.0, 1.0, 500.0, 1)
        if ok:
            self._apply_filter("sharpen", "Netteté", value)

    def filter_brightness(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Luminosité", "Facteur :", 1.15, 0.1, 3.0, 2)
        if ok:
            self._apply_filter("brightness", "Luminosité", value)

    def filter_contrast(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Contraste", "Facteur :", 1.2, 0.1, 3.0, 2)
        if ok:
            self._apply_filter("contrast", "Contraste", value)

    def filter_saturation(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Saturation", "Facteur :", 1.2, 0.0, 3.0, 2)
        if ok:
            self._apply_filter("saturation", "Saturation", value)

    def filter_grayscale(self) -> None:
        value, ok = QInputDialog.getDouble(self, "Niveaux de gris", "Intensité (0 à 1) :", 1.0, 0.0, 1.0, 2)
        if ok:
            self._apply_filter("grayscale", "Niveaux de gris", value)

    def filter_pixelate(self) -> None:
        value, ok = QInputDialog.getInt(self, "Pixeliser", "Taille des blocs (px) :", 8, 2, 200, 1)
        if ok:
            self._apply_filter("pixelate", "Pixelisation", value)

    def filter_invert(self) -> None:
        self._apply_filter("invert", "Inversion")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def pick_color(self, pos) -> None:
        doc = self.doc
        if doc is None:
            return
        x, y = int(pos.x()), int(pos.y())
        if not doc.rect().contains(QPoint(x, y)):
            return
        color = doc.composite().pixelColor(x, y)
        if color.alpha() == 0:
            color.setAlpha(255)
        self.set_fg_color(color)
        self.notify(f"Couleur prélevée : {color.name().upper()}")

    def set_fg_color(self, color: QColor) -> None:
        self.fg = QColor(color)
        self._push_recent(self.fg)
        self.colors_changed.emit()
        self.canvas.update()

    def adjust_size(self, delta: int) -> None:
        tool = self.tool
        attr = None
        if hasattr(tool, "size"):
            attr = "size"
        elif hasattr(tool, "width"):
            attr = "width"
        if attr is None:
            return
        value = max(1, min(800, int(getattr(tool, attr)) + delta))
        setattr(tool, attr, value)
        self.options.build(tool)
        self.canvas.update()
        self.notify(f"Taille : {value} px")

    def set_bg_color(self, color: QColor) -> None:
        self.bg = QColor(color)
        self._push_recent(self.bg)
        self.colors_changed.emit()
        self.canvas.update()

    def swap_colors(self) -> None:
        self.fg, self.bg = self.bg, self.fg
        self.colors_changed.emit()
        self.canvas.update()

    def reset_colors(self) -> None:
        self.fg = QColor("#000000")
        self.bg = QColor("#ffffff")
        self.colors_changed.emit()
        self.canvas.update()

    def _push_recent(self, color: QColor) -> None:
        name = color.name()
        for existing in list(self.recent):
            if existing.name() == name:
                self.recent.remove(existing)
        self.recent.insert(0, QColor(color))
        del self.recent[12:]

    def update_coords(self, pos) -> None:
        x, y = int(pos.x()), int(pos.y())
        if self.doc is not None and self.doc.rect().contains(QPoint(x, y)):
            self.status_coords.setText(f"{x}, {y} px")
        else:
            self.status_coords.setText("—")

    def update_zoom_label(self) -> None:
        text = f"{self.canvas.zoom * 100:.0f} %"
        self.status_zoom.blockSignals(True)
        self.status_zoom.setCurrentText(text)
        self.status_zoom.blockSignals(False)

    def notify(self, message: str) -> None:
        self.statusBar().showMessage(message, 4000)

    def show_system_info(self) -> None:
        text = "\n".join(self.settings.summary_lines())
        text += f"\n\nMémoire utilisée par l'historique : {self.doc.history.bytes_used() / (1024 * 1024):.0f} Mo"
        QMessageBox.information(self, "Configuration système", text)

    def show_shortcuts(self) -> None:
        QMessageBox.information(self, "Raccourcis clavier", SHORTCUTS_TEXT)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            f"À propos de {APP_NAME}",
            f"<h3>{APP_NAME} {APP_VERSION}</h3>"
            "<p>Clone de Paint modernisé, en Python et Qt.</p>"
            "<p>Rendu incrémental, historique par tuiles, calques, sélection et filtres.</p>",
        )


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PaintAmeliore")
    settings = load_settings()
    apply_theme(app)
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
