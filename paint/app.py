from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, QSettings, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDesktopServices,
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
    QTabBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import autosave
from . import updater
from .batch import convert as batch_convert
from .brush import StampCache
from .config import APP_NAME, APP_VERSION, Settings, load_settings
from .document import Document
from .filters import apply_to_document
from .io.image_io import EXPORT_FILTER, export_image, load_image
from .io.exporters import export_pdf, export_svg
from .io.printing import print_document
from .io.project_io import load_project, save_project
from .io.psd_io import load_psd_document
from .layer import Layer
from .plugins import load_plugins
from .tools import build_tools
from .tools.base import BaseTool
from .ui.canvas import Canvas, CanvasHost
from .ui.command_palette import CommandPalette
from .ui.docks import AnimationDock, ColorDock, HistoryDock, LayersDock, NavigatorDock
from .ui.export_dialog import ExportImageDialog
from .ui.filter_dialog import FilterDialog
from .ui.icons import tool_icon
from .ui.options_bar import OptionsBar
from .ui.preferences import PreferencesDialog
from .ui.sheet_dialog import CanvasSizeDialog, NewSheetDialog, ResizeImageDialog, load_last_sheet
from .ui.style_dialog import LayerStyleDialog
from .ui.theme import apply_theme

IMAGE_OPEN_FILTER = (
    "Projet Paint (*.paint);;Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif *.psd)"
    ";;Tous les fichiers (*)"
)
SAVE_FILTER = (
    "Projet Paint (*.paint);;PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;BMP (*.bmp);;TIFF (*.tif)"
)

SHORTCUTS_TEXT = """<b>Outils</b><br>
B pinceau • E gomme • S tampon • K densité • J goutte d'eau<br>
G pot de peinture • I pipette<br>
L ligne • R rectangle • O ellipse • U rectangle arrondi<br>
Y polygone • D dégradé • T texte • M sélection<br><br>
<b>Pinceau</b><br>
[ / ] taille du pinceau • Alt pipette temporaire<br><br>
<b>Fichier</b><br>
Ctrl+N nouveau • Ctrl+O ouvrir • Ctrl+S enregistrer • Ctrl+Maj+S enregistrer sous<br>
Ctrl+E exporter • Ctrl+P imprimer • Ctrl+, préférences<br><br>
<b>Édition</b><br>
Ctrl+Z annuler • Ctrl+Y rétablir • Ctrl+X/C/V couper/copier/coller<br>
Suppr effacer la sélection • Ctrl+A tout sélectionner • Ctrl+D désélectionner<br><br>
<b>Affichage</b><br>
Ctrl+molette zoom • molette défilement • Espace+glisser déplacement<br>
Ctrl+0 ajuster • Ctrl+1 taille réelle • F11 plein écran<br>
Ctrl+Maj+L / R rotation de la vue • Ctrl+Maj+; magnétisme<br>
Glisser depuis une règle pour créer un repère • Ctrl+glisser pour le déplacer<br><br>
<b>Calques</b><br>
Ctrl+Maj+N nouveau calque • Ctrl+J dupliquer • Ctrl+Maj+E fusionner vers le bas"""


class TransformSelectionDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Transformer la sélection")
        self.setMinimumWidth(300)
        self.angle = QSpinBox()
        self.angle.setRange(-180, 180)
        self.angle.setValue(0)
        self.angle.setSuffix(" °")
        self.scale_x = QSpinBox()
        self.scale_x.setRange(10, 400)
        self.scale_x.setValue(100)
        self.scale_x.setSuffix(" %")
        self.scale_y = QSpinBox()
        self.scale_y.setRange(10, 400)
        self.scale_y.setValue(100)
        self.scale_y.setSuffix(" %")
        form = QFormLayout()
        form.addRow("Rotation", self.angle)
        form.addRow("Échelle X", self.scale_x)
        form.addRow("Échelle Y", self.scale_y)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[float, float, float]:
        return (float(self.angle.value()), self.scale_x.value() / 100.0,
                self.scale_y.value() / 100.0)


class MainWindow(QMainWindow):
    colors_changed = Signal()
    doc_changed = Signal()
    DROP_SUFFIXES = {
        ".paint", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".psd",
    }

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.pressure = 1.0
        self.show_grid = False
        self.grid_size = 64
        self.snap_enabled = True
        self.snap_grid = False
        self.light_theme = False
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
        self.tabs: list[dict] = []
        self._active_index = -1
        self._tab_guard = False
        self.canvas = Canvas(self)
        self.canvas_host = CanvasHost(self.canvas)
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setVisible(False)
        self.tab_bar.currentChanged.connect(self._tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.tab_bar)
        central_layout.addWidget(self.canvas_host, 1)
        self.setCentralWidget(central)
        self.setAcceptDrops(True)
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_docks()
        self._build_status()
        QThreadPool.globalInstance().setMaxThreadCount(max(1, settings.threads))
        self.resize(1480, 940)
        self.setWindowIcon(tool_icon("brush", size=64))
        start_width, start_height, start_dpi = load_last_sheet(self.qsettings)
        self._create_document(start_width, start_height, QColor("#ffffff"), start_dpi)
        self._restore_session()
        tool_id = str(self.qsettings.value("tool/last", "brush"))
        self.set_tool(tool_id if tool_id in self.tools else "brush")
        self.plugin_names = load_plugins(self)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(90_000)
        self.autosave_timer.timeout.connect(self._autosave_all)
        self.autosave_timer.start()
        QTimer.singleShot(600, self._check_recovery)
        QTimer.singleShot(5000, self._auto_check_update)

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
        self.action_print = self._action("Imprimer…", self.print_current, "Ctrl+P")
        self.action_print_preview = self._action("Aperçu avant impression…", self.print_preview,
                                                "Ctrl+Shift+P")
        self.action_export_pdf = self._action("Exporter en PDF…", self.export_pdf_dialog)
        self.action_export_svg = self._action("Exporter en SVG…", self.export_svg_dialog)
        self.action_batch = self._action("Traitement par lot…", self.batch_dialog)
        self.action_palette = self._action("Palette de commandes", self.show_command_palette, "Ctrl+K")
        self.action_update = self._action("Vérifier les mises à jour", self.check_updates)
        self.action_preferences = self._action("Préférences…", self.preferences_dialog, "Ctrl+,")
        self.action_quit = self._action("Quitter", self.close, "Ctrl+Q")
        self.action_close_tab = self._action("Fermer l'onglet", self.close_current_tab, "Ctrl+W")

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
        self.action_crop = self._action("Recadrer", self.start_crop)
        self.action_canvas_size = self._action("Taille du canevas…", self.canvas_size_dialog)
        self.action_transform_selection = self._action(
            "Transformer la sélection…", self.transform_selection_dialog, "Ctrl+T"
        )
        self.action_rotate_sel_left = self._action(
            "Sélection : pivoter 90° à gauche", lambda: self.rotate_selection(-90)
        )
        self.action_rotate_sel_right = self._action(
            "Sélection : pivoter 90° à droite", lambda: self.rotate_selection(90)
        )
        self.action_rotate_sel_180 = self._action(
            "Sélection : pivoter 180°", lambda: self.rotate_selection(180)
        )
        self.action_flip_sel_h = self._action(
            "Sélection : miroir horizontal", lambda: self.flip_selection(True, False)
        )
        self.action_flip_sel_v = self._action(
            "Sélection : miroir vertical", lambda: self.flip_selection(False, True)
        )
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
        self.action_layer_style = self._action("Styles du calque…", self.layer_style_dialog)

        self.action_zoom_in = self._action("Zoom avant", lambda: self.canvas.zoom_by(1.25), "Ctrl+=")
        self.action_zoom_out = self._action("Zoom arrière", lambda: self.canvas.zoom_by(1 / 1.25), "Ctrl+-")
        self.action_zoom_100 = self._action("Taille réelle", lambda: self.canvas.set_zoom(1.0), "Ctrl+1")
        self.action_zoom_fit = self._action("Ajuster à la fenêtre", self.canvas.fit, "Ctrl+0")
        self.action_fullscreen = self._action("Plein écran", self.toggle_fullscreen, "F11")
        self.action_grid = self._action("Afficher la grille", self.toggle_grid, "Ctrl+G",
                                        checkable=True)
        self.action_grid_size = self._action("Taille de la grille…", self.grid_size_dialog)
        self.action_rulers = self._action("Afficher les règles", self.toggle_rulers,
                                         checkable=True)
        self.action_rulers.setChecked(True)
        self.action_guides = self._action("Afficher les repères", self.toggle_guides,
                                          checkable=True)
        self.action_guides.setChecked(True)
        self.action_snap = self._action("Magnétisme", self.toggle_snap, "Ctrl+Shift+;",
                                        checkable=True)
        self.action_snap.setChecked(True)
        self.action_snap_grid = self._action("Aligner sur la grille", self.toggle_snap_grid,
                                             checkable=True)
        self.action_clear_guides = self._action("Effacer les repères", self.clear_guides)
        self.action_view_left = self._action(
            "Vue : pivoter à gauche", lambda: self.rotate_view(-90), "Ctrl+Shift+L")
        self.action_view_right = self._action(
            "Vue : pivoter à droite", lambda: self.rotate_view(90), "Ctrl+Shift+R")
        self.action_view_flip_h = self._action(
            "Vue : miroir horizontal", lambda: self.canvas.flip_view(True))
        self.action_view_flip_v = self._action(
            "Vue : miroir vertical", lambda: self.canvas.flip_view(False))
        self.action_view_reset = self._action("Vue : réinitialiser", self.reset_view,
                                              "Ctrl+Shift+0")
        self.action_light_theme = self._action("Thème clair", self.toggle_light_theme,
                                                checkable=True)

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
        file_menu.addAction(self.action_print)
        file_menu.addAction(self.action_print_preview)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export_pdf)
        file_menu.addAction(self.action_export_svg)
        file_menu.addAction(self.action_batch)
        file_menu.addSeparator()
        file_menu.addAction(self.action_close_tab)
        file_menu.addAction(self.action_preferences)
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
        self.transform_menu = QMenu("Transformations de la sélection", self)
        self.transform_menu.addAction(self.action_transform_selection)
        self.transform_menu.addSeparator()
        for action in (self.action_rotate_sel_left, self.action_rotate_sel_right,
                       self.action_rotate_sel_180, self.action_flip_sel_h,
                       self.action_flip_sel_v):
            self.transform_menu.addAction(action)
        edit_menu.addMenu(self.transform_menu)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_swap_colors)

        image_menu = bar.addMenu("&Image")
        image_menu.addAction(self.action_crop)
        image_menu.addAction(self.action_canvas_size)
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
            ("Niveaux…", self.filter_levels),
            ("Teinte…", self.filter_hue),
            ("Vignettage…", self.filter_vignette),
            ("Flou directionnel…", self.filter_motion),
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
        layer_menu.addSeparator()
        layer_menu.addAction(self.action_layer_style)

        tools_menu = bar.addMenu("&Outils")
        self.tools_menu = tools_menu
        tools_menu.addSeparator()
        tools_menu.addAction(self.action_palette)

        view_menu = bar.addMenu("&Affichage")
        self.view_menu = view_menu
        for action in (self.action_zoom_in, self.action_zoom_out, self.action_zoom_100,
                       self.action_zoom_fit):
            view_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(self.action_grid)
        view_menu.addAction(self.action_grid_size)
        view_menu.addSeparator()
        view_menu.addAction(self.action_rulers)
        view_menu.addAction(self.action_guides)
        view_menu.addAction(self.action_snap)
        view_menu.addAction(self.action_snap_grid)
        view_menu.addAction(self.action_clear_guides)
        view_menu.addSeparator()
        view_menu.addAction(self.action_view_left)
        view_menu.addAction(self.action_view_right)
        view_menu.addAction(self.action_view_flip_h)
        view_menu.addAction(self.action_view_flip_v)
        view_menu.addAction(self.action_view_reset)
        view_menu.addSeparator()
        view_menu.addAction(self.action_light_theme)
        view_menu.addAction(self.action_fullscreen)

        help_menu = bar.addMenu("Aid&e")
        help_menu.addAction(self.action_shortcuts)
        help_menu.addAction(self.action_system)
        help_menu.addAction(self.action_update)
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
        self.animation_dock = AnimationDock(self)
        self.navigator_dock = NavigatorDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.color_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.layers_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.animation_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.navigator_dock)
        self.tabifyDockWidget(self.history_dock, self.animation_dock)
        self.tabifyDockWidget(self.history_dock, self.navigator_dock)
        self.animation_dock.hide()
        self.animation_dock.visibilityChanged.connect(self._raise_animation)
        self.view_menu.addAction(self.animation_dock.toggleViewAction())
        self.view_menu.addAction(self.navigator_dock.toggleViewAction())
        self.resizeDocks([self.color_dock, self.layers_dock, self.history_dock],
                         [220, 240, 220], Qt.Vertical)

    def _raise_animation(self, visible: bool) -> None:
        if visible:
            self.animation_dock.raise_()

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
        self.status_version = QLabel(f"v{APP_VERSION}")
        self.status_version.setStyleSheet("color:#8a9099; padding-left:8px;")
        self.status_version.setToolTip(f"{APP_NAME} {APP_VERSION}")
        self.statusBar().addPermanentWidget(self.status_version)

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
        self.status_size.setText(
            f"{doc.size.width()} × {doc.size.height()} px • {doc.dpi} dpi")
        self.update_zoom_label()
        self.doc_changed.emit()

    def _on_layers_changed(self) -> None:
        self.doc_changed.emit()
        self.canvas.update()

    def _on_size_changed(self) -> None:
        if self.doc is not None:
            self.status_size.setText(
                f"{self.doc.size.width()} × {self.doc.size.height()} px • {self.doc.dpi} dpi")
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
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
            return
        name = self._document_label(self.doc)
        mark = " *" if self.doc.is_modified() else ""
        self.setWindowTitle(f"{name}{mark} — {APP_NAME} {APP_VERSION}")
        self._update_active_tab()

    def _document_label(self, doc: Document) -> str:
        if doc.path is not None:
            return doc.path.name
        if 0 <= self._active_index < len(self.tabs):
            state = self.tabs[self._active_index]
            if state.get("doc") is doc and state.get("label"):
                return state["label"]
        return "Sans titre"

    def _document_tab_text(self, doc: Document) -> str:
        name = doc.path.name if doc.path else self._document_label_for_doc(doc)
        return name + (" *" if doc.is_modified() else "")

    def _document_label_for_doc(self, doc: Document) -> str:
        for state in self.tabs:
            if state.get("doc") is doc:
                return state.get("label") or "Sans titre"
        return "Sans titre"

    def _update_active_tab(self) -> None:
        if not 0 <= self._active_index < self.tab_bar.count() or self.doc is None:
            return
        self.tab_bar.setTabText(self._active_index, self._document_tab_text(self.doc))
        self.tab_bar.setTabToolTip(
            self._active_index, str(self.doc.path) if self.doc.path else "Document non enregistré"
        )

    def _tabs_visibility(self) -> None:
        self.tab_bar.setVisible(len(self.tabs) > 1)

    def _add_tab(self, doc: Document, label: str | None = None, fit: bool = True) -> None:
        if label is None and doc.path is None:
            untitled = 1 + sum(
                1 for state in self.tabs if state.get("doc") is not None and state["doc"].path is None
            )
            label = f"Sans titre {untitled}"
        state = {"doc": doc, "zoom": None, "pan": None, "label": label,
                 "rotation": 0, "flip_h": False, "flip_v": False,
                 "autosave": autosave.new_slot()}
        self.tabs.append(state)
        self._tab_guard = True
        index = self.tab_bar.addTab(self._document_tab_text(doc))
        self.tab_bar.setTabToolTip(
            index, str(doc.path) if doc.path else "Document non enregistré"
        )
        self._tab_guard = False
        self._activate_tab(len(self.tabs) - 1, fit=fit)
        self._tabs_visibility()

    def _tab_changed(self, index: int) -> None:
        if self._tab_guard:
            return
        self._activate_tab(index)

    def _activate_tab(self, index: int, fit: bool = False) -> None:
        if not 0 <= index < len(self.tabs):
            return
        if hasattr(self, "animation_dock"):
            self.animation_dock.stop()
        if self._active_index >= 0 and self.doc is not None and self._active_index < len(self.tabs):
            current = self.tabs[self._active_index]
            current["zoom"] = self.canvas.zoom
            current["pan"] = QPointF(self.canvas.pan)
            current["rotation"] = self.canvas.rotation
            current["flip_h"] = self.canvas.flip_h
            current["flip_v"] = self.canvas.flip_v
        self.commit_floating()
        state = self.tabs[index]
        self._active_index = index
        self._tab_guard = True
        self.tab_bar.setCurrentIndex(index)
        self._tab_guard = False
        self.set_document(state["doc"])
        self.canvas.rotation = int(state.get("rotation", 0))
        self.canvas.flip_h = bool(state.get("flip_h", False))
        self.canvas.flip_v = bool(state.get("flip_v", False))
        if fit or state["zoom"] is None:
            self.canvas.fit()
        else:
            self.canvas.restore_view(state["zoom"], state["pan"])
        self._update_title()
        self._tabs_visibility()

    def _activate_doc(self, doc: Document) -> None:
        for index, state in enumerate(self.tabs):
            if state["doc"] is doc:
                self._activate_tab(index)
                return

    def _close_tab(self, index: int) -> None:
        if not 0 <= index < len(self.tabs):
            return
        self._activate_tab(index)
        if not self.maybe_save():
            return
        state = self.tabs[index]
        self._tab_guard = True
        self.tab_bar.removeTab(index)
        self._tab_guard = False
        del self.tabs[index]
        autosave.clear(state.get("autosave", ""))
        for signal, slot in self._hooks:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._hooks = []
        self._active_index = -1
        self.doc = None
        if not self.tabs:
            start_width, start_height, start_dpi = load_last_sheet(self.qsettings)
            self._create_document(start_width, start_height, QColor("#ffffff"), start_dpi)
            return
        self._activate_tab(min(index, len(self.tabs) - 1))
        self._tabs_visibility()

    def _create_document(self, width: int, height: int, background: QColor | None,
                         dpi: int = 96) -> None:
        doc = Document.new(width, height, background,
                           undo_budget=self.settings.undo_budget_bytes, dpi=dpi)
        doc.invalidate_all()
        self._add_tab(doc, fit=True)
        self.notify(f"Document {width} × {height} px à {dpi} dpi créé")

    def close_current_tab(self) -> None:
        if self.tabs:
            self._close_tab(self._active_index)

    def new_document_dialog(self) -> None:
        width, height, dpi = load_last_sheet(self.qsettings)
        dialog = NewSheetDialog(self, self.qsettings, width, height, dpi)
        if dialog.exec() == QDialog.Accepted:
            width, height = dialog.document_size()
            self._create_document(width, height, dialog.background_color(),
                                  dialog.dpi_value())

    def open_document(self) -> None:
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
            self._add_tab(doc, fit=True)
            self._add_recent(path)
            self.notify(f"Projet ouvert : {path.name}")
            return
        image = load_image(path)
        if image is None:
            QMessageBox.warning(self, APP_NAME, "Format d'image non pris en charge.")
            return
        if path.suffix.lower() == ".psd":
            psd_doc = load_psd_document(path, self.settings.undo_budget_bytes)
            if psd_doc is not None:
                self._add_tab(psd_doc, fit=True)
                self._add_recent(path)
                self.notify(f"PSD importé avec {len(psd_doc.layers)} calque(s)")
                return
        dpm = image.dotsPerMeterX()
        dpi = max(36, min(1200, int(round(dpm * 0.0254)))) if dpm > 0 else 96
        doc = Document(QSize(image.width(), image.height()),
                       undo_budget=self.settings.undo_budget_bytes, dpi=dpi)
        layer = Layer(path.stem or "Image", doc.size)
        layer.image = image
        doc.add_layer_raw(layer)
        doc.active_index = 0
        doc.invalidate_all()
        doc.history.clear()
        doc.path = None
        doc.mark_modified(False)
        self._add_tab(doc, label=path.stem or "Image", fit=True)
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
            state = self.tabs[self._active_index] if 0 <= self._active_index < len(self.tabs) else None
            if state is not None:
                autosave.clear(state.get("autosave", ""))
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
        dialog = ExportImageDialog(self, self.doc.size.width(), self.doc.size.height(),
                                   self.doc.dpi)
        if dialog.exec() != QDialog.Accepted:
            return
        options = dialog.values()
        suffix = options["suffix"]
        filters = {
            "png": "PNG (*.png)", "jpg": "JPEG (*.jpg)", "webp": "WebP (*.webp)",
            "bmp": "BMP (*.bmp)", "tif": "TIFF (*.tif)",
        }
        path, _ = QFileDialog.getSaveFileName(self, "Exporter une image",
                                             self._default_name(f".{suffix}"),
                                             filters[suffix])
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix("." + suffix)
        if export_image(self.doc, target, quality=options["quality"],
                        size=options["size"], dpi=options["dpi"]):
            self.notify(f"Image exportée : {target.name}")
        else:
            QMessageBox.warning(self, APP_NAME, "Échec de l'export.")

    def print_preview(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        print_document(self.doc, self, preview=True)

    def print_current(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        if print_document(self.doc, self, preview=False):
            self.notify("Document envoyé à l'imprimante")

    def export_pdf_dialog(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en PDF",
                                             self._default_name(".pdf"), "PDF (*.pdf)")
        if path:
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".pdf")
            if export_pdf(self.doc, target):
                self.notify(f"PDF exporté : {target.name}")
            else:
                self.notify("Échec de l'export PDF")

    def export_svg_dialog(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en SVG",
                                             self._default_name(".svg"), "SVG (*.svg)")
        if path:
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".svg")
            if export_svg(self.doc, target):
                self.notify(f"SVG exporté : {target.name}")
            else:
                self.notify("Échec de l'export SVG")

    def batch_dialog(self) -> None:
        source = QFileDialog.getExistingDirectory(self, "Dossier source")
        if not source:
            return
        output = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if not output:
            return
        width, ok = QInputDialog.getInt(self, "Traitement par lot",
                                        "Largeur maximale (0 = originale) :", 0, 0, 16384, 64)
        if not ok:
            return
        fmt, ok = QInputDialog.getItem(self, "Traitement par lot", "Format :",
                                       ["png", "jpg", "webp", "tiff"], 0, False)
        if not ok:
            return
        files = [p for p in Path(source).iterdir()
                 if p.suffix.lower() in self.DROP_SUFFIXES]
        written = batch_convert(files, output, width, fmt)
        self.notify(f"{len(written)} fichier(s) converti(s)")

    def preferences_dialog(self) -> None:
        dialog = PreferencesDialog(self)
        if dialog.exec() == QDialog.Accepted:
            dialog.apply()
            self.notify("Préférences enregistrées")

    def show_command_palette(self) -> None:
        CommandPalette(self).exec()

    def check_updates(self) -> None:
        self.notify("Vérification des mises à jour…")
        QApplication.processEvents()
        result = updater.latest()
        if result is None:
            QMessageBox.information(self, "Mises à jour",
                                    "Impossible de contacter GitHub pour le moment.")
            return
        version, url = result
        if version == APP_VERSION:
            QMessageBox.information(self, "Mises à jour",
                                    f"Vous utilisez la dernière version ({APP_VERSION}).")
            return
        answer = QMessageBox.question(
            self, "Mise à jour disponible",
            f"La version {version} est disponible (installée : {APP_VERSION}).\n"
            "Ouvrir la page de téléchargement ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(url))

    def _auto_check_update(self) -> None:
        try:
            last = float(self.qsettings.value("update/last", 0) or 0)
        except (TypeError, ValueError):
            last = 0
        if time.time() - last < 86400:
            return
        self.qsettings.setValue("update/last", time.time())
        result = updater.latest(timeout=4.0)
        if result is not None and result[0] != APP_VERSION:
            self.notify(f"Mise à jour {result[0]} disponible (Aide → Vérifier les mises à jour)")

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
        for state in list(self.tabs):
            doc = state["doc"]
            if not doc.is_modified():
                continue
            self._activate_doc(doc)
            if not self.maybe_save():
                event.ignore()
                return
        for state in self.tabs:
            autosave.clear(state.get("autosave", ""))
        self._save_session()
        event.accept()

    def _autosave_all(self) -> None:
        for state in self.tabs:
            doc = state["doc"]
            if doc.is_modified():
                autosave.write(doc, state["autosave"], state["label"])

    def _check_recovery(self) -> None:
        pending = autosave.entries()
        if not pending:
            return
        answer = QMessageBox.question(
            self,
            "Récupération de documents",
            f"{len(pending)} document(s) non enregistré(s) ont été retrouvés après un arrêt brutal.\n"
            "Voulez-vous les restaurer ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            autosave.clear_all()
            return
        for entry in pending:
            doc = autosave.load(entry, self.settings.undo_budget_bytes)
            autosave.clear(entry.get("slot", ""))
            if doc is None:
                continue
            label = entry.get("label") or "Document récupéré"
            self._add_tab(doc, label=label, fit=True)
        self.notify("Documents récupérés")

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
        self.qsettings.setValue("ui/light", self.light_theme)
        self.qsettings.setValue("ui/grid", self.show_grid)
        self.qsettings.setValue("ui/grid_size", self.grid_size)
        self.qsettings.setValue("ui/snap", self.snap_enabled)
        self.qsettings.setValue("ui/snap_grid", self.snap_grid)
        self.qsettings.setValue("ui/rulers", self.action_rulers.isChecked())
        self.qsettings.setValue("ui/guides", self.action_guides.isChecked())

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
        try:
            self.grid_size = max(4, int(self.qsettings.value("ui/grid_size", 64)))
        except (TypeError, ValueError):
            self.grid_size = 64
        if str(self.qsettings.value("ui/grid", "false")).lower() in ("1", "true", "yes"):
            self.show_grid = True
            self.action_grid.setChecked(True)
        if str(self.qsettings.value("ui/snap", "true")).lower() not in ("1", "true", "yes"):
            self.snap_enabled = False
            self.action_snap.setChecked(False)
        if str(self.qsettings.value("ui/snap_grid", "false")).lower() in ("1", "true", "yes"):
            self.snap_grid = True
            self.action_snap_grid.setChecked(True)
        if str(self.qsettings.value("ui/rulers", "true")).lower() not in ("1", "true", "yes"):
            self.action_rulers.setChecked(False)
            self.canvas_host.set_rulers_visible(False)
        if str(self.qsettings.value("ui/guides", "true")).lower() not in ("1", "true", "yes"):
            self.action_guides.setChecked(False)
        if str(self.qsettings.value("ui/light", "false")).lower() in ("1", "true", "yes"):
            self.action_light_theme.setChecked(True)
            self.toggle_light_theme(True)
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

    def start_crop(self) -> None:
        self.set_tool("crop")
        self.notify("Glissez le cadre de recadrage puis appuyez sur Entrée")

    def canvas_size_dialog(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        dialog = CanvasSizeDialog(self, self.doc.size.width(), self.doc.size.height(),
                                  self.doc.dpi)
        if dialog.exec() == QDialog.Accepted:
            width, height, anchor = dialog.values()
            self.doc.resize_canvas(width, height, anchor)
            self.canvas.fit()
            self.notify(f"Taille du canevas : {width} × {height} px")

    def transform_selection_dialog(self) -> None:
        if self.doc is None or not self.doc.has_selection():
            self.notify("Aucune sélection active")
            return
        self.commit_floating()
        dialog = TransformSelectionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            angle, scale_x, scale_y = dialog.values()
            if self.doc.transform_selection(angle, scale_x, scale_y):
                self.canvas.update()
                self.notify("Sélection transformée")

    def rotate_selection(self, angle: int) -> None:
        if self.doc is None or not self.doc.has_selection():
            self.notify("Aucune sélection active")
            return
        self.commit_floating()
        if self.doc.transform_selection(angle, 1.0, 1.0):
            self.canvas.update()
            self.notify("Sélection pivotée")

    def flip_selection(self, horizontal: bool = False, vertical: bool = False) -> None:
        if self.doc is None or not self.doc.has_selection():
            self.notify("Aucune sélection active")
            return
        self.commit_floating()
        if self.doc.transform_selection(0.0, -1.0 if horizontal else 1.0,
                                        -1.0 if vertical else 1.0):
            self.canvas.update()
            self.notify("Sélection retournée")

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
        mask = doc.mask_for_image()
        if mask is not None:
            local_mask = mask.copy(bounds)
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, local_mask)
            painter.end()
        elif doc.has_selection():
            region_mask_image = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
            region_mask_image.fill(Qt.transparent)
            painter = QPainter(region_mask_image)
            painter.setClipRegion(doc.selection.translated(-bounds.left(), -bounds.top()))
            painter.fillRect(region_mask_image.rect(), Qt.white)
            painter.end()
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, region_mask_image)
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

    def layer_style_dialog(self) -> None:
        if self.doc is None:
            return
        layer = self.doc.active_layer()
        if layer is None:
            return
        dialog = LayerStyleDialog(self, layer.styles)
        if dialog.exec() == QDialog.Accepted:
            self.doc.set_layer_styles(self.doc.active_index, dialog.values())
            self.canvas.update()
            self.notify("Styles du calque mis à jour")

    def resize_dialog(self) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        dialog = ResizeImageDialog(self, self.doc.size.width(), self.doc.size.height(),
                                   self.doc.dpi)
        if dialog.exec() == QDialog.Accepted:
            width, height, smooth, dpi = dialog.values()
            self.doc.resize_image(width, height, smooth, dpi)
            self.canvas.fit()
            self._on_size_changed()
            self.notify("Image redimensionnée")

    def _apply_filter(self, name: str, label: str, value: float = 0.0) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        if apply_to_document(self.doc, name, value, label):
            self.canvas.update()
            self.notify(f"{label} appliqué")

    def _open_filter(self, filter_id: str, title: str, params: list[dict]) -> None:
        if self.doc is None:
            return
        self.commit_floating()
        if self.doc.is_active_locked():
            self.notify("Calque verrouillé")
            return
        dialog = FilterDialog(self, filter_id, title, params)
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            if apply_to_document(self.doc, filter_id, values.get("value", 0.0), title, values):
                self.canvas.update()
                self.notify(f"{title} appliqué")

    def filter_blur(self) -> None:
        self._open_filter("blur", "Flou gaussien", [
            {"key": "value", "label": "Rayon", "min": 0.1, "max": 100.0,
             "value": 4.0, "decimals": 1, "suffix": " px"},
        ])

    def filter_sharpen(self) -> None:
        self._open_filter("sharpen", "Netteté", [
            {"key": "value", "label": "Intensité", "min": 1.0, "max": 500.0,
             "value": 120.0, "decimals": 0, "suffix": " %"},
        ])

    def filter_brightness(self) -> None:
        self._open_filter("brightness", "Luminosité", [
            {"key": "value", "label": "Facteur", "min": 0.1, "max": 3.0,
             "value": 1.15, "decimals": 2, "step": 0.05},
        ])

    def filter_contrast(self) -> None:
        self._open_filter("contrast", "Contraste", [
            {"key": "value", "label": "Facteur", "min": 0.1, "max": 3.0,
             "value": 1.2, "decimals": 2, "step": 0.05},
        ])

    def filter_saturation(self) -> None:
        self._open_filter("saturation", "Saturation", [
            {"key": "value", "label": "Facteur", "min": 0.0, "max": 3.0,
             "value": 1.2, "decimals": 2, "step": 0.05},
        ])

    def filter_levels(self) -> None:
        self._open_filter("levels", "Niveaux", [
            {"key": "black", "label": "Point noir", "min": 0, "max": 254,
             "value": 0, "decimals": 0},
            {"key": "white", "label": "Point blanc", "min": 1, "max": 255,
             "value": 255, "decimals": 0},
            {"key": "gamma", "label": "Gamma", "min": 0.1, "max": 3.0,
             "value": 1.0, "decimals": 2, "step": 0.05},
        ])

    def filter_hue(self) -> None:
        self._open_filter("hue", "Teinte", [
            {"key": "shift", "label": "Décalage", "min": 0, "max": 255,
             "value": 32, "decimals": 0, "suffix": " °"},
        ])

    def filter_vignette(self) -> None:
        self._open_filter("vignette", "Vignettage", [
            {"key": "strength", "label": "Intensité", "min": 0.0, "max": 1.0,
             "value": 0.6, "decimals": 2, "step": 0.05},
        ])

    def filter_motion(self) -> None:
        self._open_filter("motionblur", "Flou directionnel", [
            {"key": "distance", "label": "Distance", "min": 2, "max": 80,
             "value": 12, "decimals": 0, "suffix": " px"},
            {"key": "angle", "label": "Angle", "min": 0, "max": 180,
             "value": 0, "decimals": 0, "suffix": " °"},
        ])

    def filter_grayscale(self) -> None:
        self._open_filter("grayscale", "Niveaux de gris", [
            {"key": "value", "label": "Intensité", "min": 0.0, "max": 1.0,
             "value": 1.0, "decimals": 2, "step": 0.05},
        ])

    def filter_pixelate(self) -> None:
        self._open_filter("pixelate", "Pixeliser", [
            {"key": "value", "label": "Taille des blocs", "min": 2, "max": 200,
             "value": 8, "decimals": 0, "suffix": " px"},
        ])

    def filter_invert(self) -> None:
        self.commit_floating()
        self._apply_filter("invert", "Inversion")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_grid(self, checked: bool) -> None:
        self.show_grid = bool(checked)
        self.canvas.update()
        self.notify("Grille affichée" if self.show_grid else "Grille masquée")

    def grid_size_dialog(self) -> None:
        value, ok = QInputDialog.getInt(self, "Taille de la grille", "Espacement (px) :",
                                        self.grid_size, 4, 400, 4)
        if ok:
            self.grid_size = value
            self.action_grid.setChecked(True)
            self.show_grid = True
            self.canvas.update()
            self.notify(f"Grille : {self.grid_size} px")

    def toggle_rulers(self, checked: bool) -> None:
        self.canvas_host.set_rulers_visible(bool(checked))
        self.canvas.fit()

    def toggle_guides(self, checked: bool) -> None:
        if self.doc is not None:
            self.doc.guides_visible = bool(checked)
        self.canvas.update()
        self.notify("Repères affichés" if checked else "Repères masqués")

    def toggle_snap(self, checked: bool) -> None:
        self.snap_enabled = bool(checked)
        self.notify("Magnétisme activé" if checked else "Magnétisme désactivé")

    def toggle_snap_grid(self, checked: bool) -> None:
        self.snap_grid = bool(checked)
        self.notify("Alignement sur la grille activé" if checked
                    else "Alignement sur la grille désactivé")

    def clear_guides(self) -> None:
        if self.doc is not None:
            self.doc.clear_guides()
            self.canvas.update()
            self.notify("Repères effacés")

    def rotate_view(self, angle: int) -> None:
        self.canvas.rotate_view(angle)
        self.notify(f"Vue pivotée de {abs(angle)}°")

    def reset_view(self) -> None:
        self.canvas.rotation = 0
        self.canvas.flip_h = False
        self.canvas.flip_v = False
        self.canvas.fit()
        self.notify("Vue réinitialisée")

    def toggle_light_theme(self, checked: bool) -> None:
        self.light_theme = bool(checked)
        from PySide6.QtWidgets import QApplication

        from .ui.theme import apply_theme

        apply_theme(QApplication.instance(), light=self.light_theme)
        self.canvas.refresh_theme()
        self._refresh_icons()
        self.notify("Thème clair" if self.light_theme else "Thème sombre")

    def _refresh_icons(self) -> None:
        color = "#1f2937" if self.light_theme else "#e8eaed"
        for tool in self.tools.values():
            action = self.tool_actions.get(tool.id)
            if action is not None:
                action.setIcon(tool_icon(tool.icon, color=color))
        self.setWindowIcon(tool_icon("brush", color=color, size=64))

    def pick_color(self, pos, sample_size: int = 1) -> None:
        doc = self.doc
        if doc is None:
            return
        x, y = int(pos.x()), int(pos.y())
        if not doc.rect().contains(QPoint(x, y)):
            return
        sample = max(1, int(sample_size))
        if sample > 1:
            half = sample // 2
            rect = QRect(x - half, y - half, sample, sample).intersected(doc.rect())
            color = doc.composite().copy(rect).scaled(
                1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            ).pixelColor(0, 0)
        else:
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
    opened = 0
    for raw in sys.argv[1:]:
        path = Path(raw)
        if path.is_file() and path.suffix.lower() in window.DROP_SUFFIXES:
            window.load_path(path)
            opened += 1
    if opened and len(window.tabs) > 1:
        first = window.tabs[0]
        if first["doc"].path is None and not first["doc"].is_modified():
            window._activate_tab(0)
            window._close_tab(0)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
