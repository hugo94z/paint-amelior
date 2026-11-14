from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRegion

from paint.brush import StampCache
from paint.document import Document
from paint.filters import apply_to_document, flood_fill
from paint.io.project_io import load_project, save_project
from paint.layer import Layer
from paint.tools.draw import BrushTool
from paint.tools.select import SelectionTool


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class FakeCanvas:
    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1

    def update_doc_rect(self, rect):
        self.updates += 1


class FakeApp:
    def __init__(self, doc):
        self.doc = doc
        self.canvas = FakeCanvas()
        self.fg = QColor("#ff0000")
        self.bg = QColor("#ffffff")
        self.stamp_cache = StampCache(32 * 1024 * 1024)
        self.messages = []

    def pick_color(self, pos):
        pass

    def notify(self, message):
        self.messages.append(message)


class DummyEvent:
    def __init__(self, shift: bool = False):
        self._shift = shift

    def modifiers(self):
        from PySide6.QtCore import Qt

        return Qt.ShiftModifier if self._shift else Qt.NoModifier

    def buttons(self):
        from PySide6.QtCore import Qt

        return Qt.LeftButton


def fill_layer(layer, rect, color):
    painter = QPainter(layer.image)
    painter.fillRect(rect, color)
    painter.end()


def test_history_undo_redo(qapp):
    doc = Document.new(200, 200, QColor("white"))
    layer = doc.active_layer()
    assert doc.composite().pixelColor(20, 20) == QColor("white")
    tx = doc.history.begin("Test")
    tx.touch(layer, QRect(0, 0, 64, 64))
    fill_layer(layer, QRect(10, 10, 30, 30), QColor("red"))
    doc.invalidate(QRect(0, 0, 64, 64))
    tx.commit()
    assert doc.composite().pixelColor(20, 20) == QColor("red")
    assert doc.history.can_undo
    doc.history.undo()
    assert doc.composite().pixelColor(20, 20) == QColor("white")
    doc.history.redo()
    assert doc.composite().pixelColor(20, 20) == QColor("red")
    assert doc.history.position == 1


def test_history_budget_trims(qapp):
    doc = Document.new(64, 64, QColor("white"))
    doc.history.budget_bytes = 40_000
    layer = doc.active_layer()
    for index in range(30):
        tx = doc.history.begin("Coup")
        tx.touch(layer, QRect(0, 0, 64, 64))
        fill_layer(layer, QRect(0, 0, 64, 1), QColor(index * 8 % 255, 0, 0))
        doc.invalidate(QRect(0, 0, 64, 64))
        tx.commit()
    assert doc.history.bytes_used() <= doc.history.budget_bytes
    assert len(doc.history.labels) >= 1


def test_flood_fill(qapp):
    image = doc_image = Document.new(80, 80, QColor("white")).active_layer().image
    painter = QPainter(image)
    painter.fillRect(QRect(0, 0, 40, 80), QColor("black"))
    painter.end()
    result, bounds = flood_fill(image, 60, 40, QColor("red"), 0)
    assert result is not None
    assert bounds == QRect(40, 0, 40, 80)
    assert result.pixelColor(10, 10) == QColor("red")


def test_layers_undo(qapp):
    doc = Document.new(64, 64, QColor("white"))
    assert len(doc.layers) == 2
    doc.add_layer("Super")
    assert len(doc.layers) == 3
    doc.history.undo()
    assert len(doc.layers) == 2
    doc.history.redo()
    assert len(doc.layers) == 3
    doc.remove_layer()
    assert len(doc.layers) == 2
    doc.history.undo()
    assert len(doc.layers) == 3


def test_project_roundtrip(qapp, tmp_path):
    doc = Document.new(90, 60, QColor("white"))
    fill_layer(doc.layers[0], QRect(0, 0, 90, 60), QColor("#3366cc"))
    doc.add_layer("Dessus")
    fill_layer(doc.active_layer(), QRect(10, 10, 20, 20), QColor("#ff8800"))
    doc.set_layer_props(doc.active_index, opacity=0.5, blend="multiply")
    path = tmp_path / "test.paint"
    assert save_project(doc, path)
    loaded = load_project(path)
    assert loaded is not None
    assert loaded.size == QSize(90, 60)
    assert len(loaded.layers) == 3
    assert loaded.layers[-1].name == "Dessus"
    assert abs(loaded.layers[-1].opacity - 0.5) < 0.01
    assert loaded.layers[-1].blend == "multiply"


def test_resize(qapp):
    doc = Document.new(120, 80, QColor("white"))
    doc.resize_image(60, 40)
    assert doc.size == QSize(60, 40)
    assert doc.composite().width() == 60
    assert doc.layers[0].image.width() == 60


def test_brush_tool_history(qapp):
    doc = Document.new(140, 140, QColor("white"))
    app = FakeApp(doc)
    tool = BrushTool(app)
    tool.size = 12
    tool.press(QPointF(20, 20), None)
    tool.move(QPointF(100, 100), None)
    tool.release(QPointF(100, 100), None)
    assert doc.history.can_undo
    assert doc.composite().pixelColor(60, 60) == app.fg
    doc.history.undo()
    assert doc.composite().pixelColor(60, 60) == QColor("white")


def test_selection_move(qapp):
    doc = Document.new(140, 140, QColor("white"))
    layer = doc.active_layer()
    fill_layer(layer, QRect(10, 10, 40, 40), QColor("red"))
    doc.invalidate_all()
    app = FakeApp(doc)
    tool = SelectionTool(app)
    path = QPainterPath()
    path.addRect(QRect(10, 10, 40, 40))
    doc.set_selection(QRegion(QRect(10, 10, 40, 40)), path)
    tool.press(QPointF(20, 20), None)
    tool.move(QPointF(30, 25), None)
    tool.release(QPointF(30, 25), None)
    assert doc.floating is None
    assert doc.composite().pixelColor(10, 10) == QColor("white")
    assert doc.composite().pixelColor(25, 20) == QColor("red")
    assert doc.history.can_undo
    doc.history.undo()
    assert doc.composite().pixelColor(20, 20) == QColor("red")


def test_filters(qapp):
    doc = Document.new(64, 64, QColor("white"))
    fill_layer(doc.active_layer(), QRect(0, 0, 64, 64), QColor("red"))
    doc.invalidate_all()
    assert apply_to_document(doc, "invert", 0.0, "Inversion")
    assert doc.composite().pixelColor(10, 10) == QColor("cyan")
    doc.history.undo()
    assert doc.composite().pixelColor(10, 10) == QColor("red")


def test_brush_shift_line(qapp):
    doc = Document.new(140, 140, QColor("white"))
    app = FakeApp(doc)
    tool = BrushTool(app)
    tool.size = 8
    tool.press(QPointF(20, 20), DummyEvent())
    tool.release(QPointF(20, 20), DummyEvent())
    tool.press(QPointF(120, 20), DummyEvent(shift=True))
    tool.release(QPointF(120, 20), DummyEvent(shift=True))
    assert doc.composite().pixelColor(70, 20) == app.fg


def test_transform_undo_redo(qapp):
    doc = Document.new(90, 60, QColor("white"))
    fill_layer(doc.active_layer(), QRect(5, 5, 10, 10), QColor("red"))
    doc.invalidate_all()
    doc.transform_image(90, label="Rotation")
    assert doc.size == QSize(60, 90)
    assert doc.history.can_undo
    doc.history.undo()
    assert doc.size == QSize(90, 60)
    assert doc.composite().pixelColor(10, 10) == QColor("red")
    doc.history.redo()
    assert doc.size == QSize(60, 90)


def test_invert_selection(qapp):
    doc = Document.new(100, 80, QColor("white"))
    path = QPainterPath()
    path.addRect(QRect(10, 10, 30, 20))
    doc.set_selection(QRegion(QRect(10, 10, 30, 20)), path)
    doc.invert_selection()
    assert doc.has_selection()
    assert not doc.selection.contains(QPoint(15, 15))
    assert doc.selection.contains(QPoint(2, 2))
    assert doc.selection_path is not None


def test_reorder_layers(qapp):
    doc = Document.new(40, 40, QColor("white"))
    doc.add_layer("Trois")
    names_before = [layer.name for layer in doc.layers]
    ids_top_to_bottom = [layer.id for layer in reversed(doc.layers)]
    doc.reorder_layers(ids_top_to_bottom[1:] + ids_top_to_bottom[:1])
    names_after = [layer.name for layer in doc.layers]
    assert names_after != names_before
    assert names_after[0] == names_before[-1]
    doc.history.undo()
    assert [layer.name for layer in doc.layers] == names_before
