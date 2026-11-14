from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..filters import apply


class FilterDialog(QDialog):
    MAX_PREVIEW = QSize(760, 500)

    def __init__(self, app, filter_id: str, title: str, params: list[dict]):
        super().__init__(app)
        self.app = app
        self.filter_id = filter_id
        self.setWindowTitle(title)
        self.setMinimumWidth(620)
        self._boxes: dict[str, QDoubleSpinBox] = {}
        form = QFormLayout()
        for spec in params:
            box = QDoubleSpinBox()
            box.setRange(float(spec.get("min", 0.0)), float(spec.get("max", 100.0)))
            box.setDecimals(int(spec.get("decimals", 0)))
            box.setSingleStep(float(spec.get("step", 1.0)))
            box.setValue(float(spec.get("value", 0.0)))
            box.setSuffix(str(spec.get("suffix", "")))
            box.valueChanged.connect(self._schedule_preview)
            self._boxes[spec["key"]] = box
            form.addRow(spec.get("label", spec["key"]), box)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(560, 320)
        self.preview.setStyleSheet("background:#1b1d21; border:1px solid #34373c; border-radius:6px;")
        note = QLabel("Aperçu basse résolution — le filtre sera appliqué en pleine qualité.")
        note.setStyleSheet("color:#7f858f;")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview, 1)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(140)
        self._timer.timeout.connect(self._render_preview)
        self._render_preview()

    def values(self) -> dict:
        return {key: box.value() for key, box in self._boxes.items()}

    def _schedule_preview(self) -> None:
        self._timer.start()

    def _render_preview(self) -> None:
        doc = self.app.doc
        if doc is None:
            return
        composite = doc.composite()
        proxy = composite.scaled(
            self.MAX_PREVIEW, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        try:
            result = apply(proxy, self.filter_id,
                           value=self.values().get("value", 0.0), options=self.values())
        except (ValueError, OSError):
            result = proxy
        canvas = QImage(proxy.size(), QImage.Format_ARGB32)
        canvas.fill(QColor("#202225"))
        painter = QPainter(canvas)
        tile = 24
        painter.fillRect(canvas.rect(), QColor("#31343a"))
        for y in range(0, canvas.height(), tile):
            for x in range(0, canvas.width(), tile):
                if ((x // tile) + (y // tile)) % 2 == 0:
                    painter.fillRect(x, y, tile, tile, QColor("#3a3d42"))
        painter.drawImage(0, 0, result)
        painter.end()
        self.preview.setPixmap(QPixmap.fromImage(canvas))
