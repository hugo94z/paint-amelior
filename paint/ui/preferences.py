from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..sheet import MAX_SIDE
from .sheet_dialog import load_last_sheet, store_last_sheet


class PreferencesDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Préférences")
        self.setMinimumWidth(440)

        self.theme = QComboBox()
        self.theme.addItem("Sombre", False)
        self.theme.addItem("Clair", True)
        self.theme.setCurrentIndex(1 if app.light_theme else 0)

        self.autosave = QSpinBox()
        self.autosave.setRange(15, 900)
        self.autosave.setSuffix(" s")
        self.autosave.setValue(max(15, int(app.autosave_timer.interval() / 1000)))

        self.undo = QSpinBox()
        self.undo.setRange(64, 8192)
        self.undo.setSuffix(" Mo")
        self.undo.setValue(max(64, int(app.settings.undo_budget_bytes / (1024 * 1024))))

        width, height, dpi = load_last_sheet(app.qsettings)
        self.sheet_width = QSpinBox()
        self.sheet_width.setRange(1, MAX_SIDE)
        self.sheet_width.setSuffix(" px")
        self.sheet_width.setValue(width)
        self.sheet_height = QSpinBox()
        self.sheet_height.setRange(1, MAX_SIDE)
        self.sheet_height.setSuffix(" px")
        self.sheet_height.setValue(height)
        self.sheet_dpi = QSpinBox()
        self.sheet_dpi.setRange(36, 1200)
        self.sheet_dpi.setSuffix(" dpi")
        self.sheet_dpi.setValue(dpi)

        self.grid_size = QSpinBox()
        self.grid_size.setRange(4, 400)
        self.grid_size.setSuffix(" px")
        self.grid_size.setValue(app.grid_size)
        self.show_grid = QCheckBox("Afficher la grille")
        self.show_grid.setChecked(app.show_grid)
        self.snap = QCheckBox("Magnétisme (repères et bords)")
        self.snap.setChecked(app.snap_enabled)
        self.snap_grid = QCheckBox("Aligner sur la grille")
        self.snap_grid.setChecked(app.snap_grid)
        self.rulers = QCheckBox("Afficher les règles")
        self.rulers.setChecked(app.action_rulers.isChecked())

        form = QFormLayout()
        form.addRow("Thème", self.theme)
        form.addRow("Sauvegarde automatique", self.autosave)
        form.addRow("Budget d'annulation", self.undo)
        sheet = QLabel(f"{width} × {height} px à {dpi} dpi")
        form.addRow("Format par défaut", sheet)
        form.addRow("Largeur", self.sheet_width)
        form.addRow("Hauteur", self.sheet_height)
        form.addRow("Résolution", self.sheet_dpi)
        form.addRow("Taille de la grille", self.grid_size)
        form.addRow("", self.show_grid)
        form.addRow("", self.snap)
        form.addRow("", self.snap_grid)
        form.addRow("", self.rulers)
        note = QLabel("Le budget d'annulation s'applique aux documents ouverts.")
        note.setStyleSheet("color:#7f858f;")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def apply(self) -> None:
        app = self.app
        light = bool(self.theme.currentData())
        if light != app.light_theme:
            app.action_light_theme.setChecked(light)
            app.toggle_light_theme(light)
        app.autosave_timer.setInterval(self.autosave.value() * 1000)
        budget = self.undo.value() * 1024 * 1024
        if budget != app.settings.undo_budget_bytes:
            app.settings.allocation["undo_mb"] = self.undo.value()
            for state in app.tabs:
                doc = state.get("doc")
                if doc is not None:
                    doc.history.budget_bytes = budget
                    doc.history._trim()
        store_last_sheet(app.qsettings, self.sheet_width.value(),
                         self.sheet_height.value(), self.sheet_dpi.value())
        app.grid_size = self.grid_size.value()
        app.show_grid = self.show_grid.isChecked()
        app.action_grid.setChecked(app.show_grid)
        app.snap_enabled = self.snap.isChecked()
        app.action_snap.setChecked(app.snap_enabled)
        app.snap_grid = self.snap_grid.isChecked()
        app.action_snap_grid.setChecked(app.snap_grid)
        app.action_rulers.setChecked(self.rulers.isChecked())
        app.canvas_host.set_rulers_visible(self.rulers.isChecked())
        app.canvas.update()
        app.qsettings.sync()
