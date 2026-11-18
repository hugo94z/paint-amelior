from __future__ import annotations

import os

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..sheet import MAX_SIDE, human_bytes
from .sheet_dialog import load_last_sheet, store_last_sheet


class PreferencesDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("Préférences")
        self.setMinimumWidth(460)
        allocation = app.settings.allocation
        logical = max(1, int(allocation.get("logical_cores") or os.cpu_count() or 4))
        total = max(1024, int(allocation.get("ram_total_mb") or 4096))
        app_ram = max(256, int(allocation.get("app_ram_mb", 1024)))

        self.theme = QComboBox()
        self.theme.addItem("Sombre", False)
        self.theme.addItem("Clair", True)
        self.theme.setCurrentIndex(1 if app.light_theme else 0)

        self.autosave = QSpinBox()
        self.autosave.setRange(15, 900)
        self.autosave.setSuffix(" s")
        self.autosave.setValue(max(15, int(app.autosave_timer.interval() / 1000)))

        self.threads = QSpinBox()
        self.threads.setRange(1, logical)
        self.threads.setSuffix(" threads")
        self.threads.setValue(app.settings.threads)

        self.app_ram = QSpinBox()
        self.app_ram.setRange(256, min(32768, int(total * 0.85)))
        self.app_ram.setSuffix(" Mo")
        self.app_ram.setValue(app_ram)

        self.undo = QSpinBox()
        self.undo.setRange(64, 16384)
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

        hardware = QLabel(
            f"{allocation.get('physical_cores') or '?'} cœurs physiques / "
            f"{logical} logiques • RAM {total / 1024:.1f} Go dont "
            f"{int(allocation.get('ram_available_mb') or 0) / 1024:.1f} Go disponibles"
        )
        hardware.setWordWrap(True)
        hardware.setStyleSheet("color:#7f858f;")
        recommended = QLabel(
            f"Conseillé par le scan : {allocation.get('threads')} threads, "
            f"{int(allocation.get('app_ram_mb', 0))} Mo pour l'application, "
            f"{int(allocation.get('undo_mb', 0))} Mo d'historique, "
            f"{int(allocation.get('doc_ram_mb', 0))} Mo par document."
        )
        recommended.setWordWrap(True)
        recommended.setStyleSheet("color:#7f858f;")

        form = QFormLayout()
        form.addRow("Thème", self.theme)
        form.addRow("Sauvegarde automatique", self.autosave)
        form.addRow(hardware)
        form.addRow("Threads CPU", self.threads)
        form.addRow("Mémoire de l'application", self.app_ram)
        form.addRow("Budget d'annulation", self.undo)
        form.addRow(recommended)
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
        note = QLabel(
            "Les budgets s'appliquent immédiatement aux documents ouverts. "
            "Les threads BLAS seront pleinement appliqués au prochain démarrage."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#7f858f;")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.app_ram.valueChanged.connect(self._ram_changed)
        self._ram_changed(self.app_ram.value())

    def _ram_changed(self, value: int) -> None:
        self.undo.setMaximum(max(64, min(16384, int(value * 0.55))))

    def apply(self) -> None:
        app = self.app
        light = bool(self.theme.currentData())
        if light != app.light_theme:
            app.action_light_theme.setChecked(light)
            app.toggle_light_theme(light)
        app.autosave_timer.setInterval(self.autosave.value() * 1000)
        allocation = app.settings.allocation
        allocation["threads"] = self.threads.value()
        allocation["app_ram_mb"] = self.app_ram.value()
        allocation["doc_ram_mb"] = max(256, int(self.app_ram.value() * 0.6))
        allocation["stamp_cache_mb"] = max(48, min(1024, int(self.app_ram.value() * 0.05)))
        allocation["max_document_pixels"] = int(
            allocation["doc_ram_mb"] * 1024 * 1024 / (4 * 3))
        allocation["undo_mb"] = self.undo.value()
        QThreadPool.globalInstance().setMaxThreadCount(self.threads.value())
        app.stamp_cache.budget_bytes = app.settings.stamp_cache_bytes
        app.stamp_cache.trim()
        budget = app.settings.undo_budget_bytes
        for state in app.tabs:
            doc = state.get("doc")
            if doc is not None:
                doc.history.budget_bytes = budget
                doc.history._trim()
        app.qsettings.setValue("perf/threads", self.threads.value())
        app.qsettings.setValue("perf/app_ram_mb", self.app_ram.value())
        app.qsettings.setValue("perf/undo_mb", self.undo.value())
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
        app.notify(
            f"Performances : {self.threads.value()} threads, "
            f"{human_bytes(app.settings.doc_ram_bytes)} par document"
        )
