from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QRegion

from paint.brush import StampCache
from paint.document import Document
from paint.filters import apply_to_document, flood_fill
from paint.io.exporters import export_animation, export_pdf, export_svg
from paint.io.project_io import load_project, save_project
from paint.layer import Layer
from paint.tools.draw import BrushTool
from paint.tools.select import SelectionTool
from paint.tools.wand import MagicWandTool
from paint import autosave


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


def test_magic_wand_and_feather(qapp):
    doc = Document.new(120, 120, QColor("white"))
    fill_layer(doc.active_layer(), QRect(20, 20, 60, 60), QColor("#dc2626"))
    doc.invalidate_all()
    app = FakeApp(doc)
    wand = MagicWandTool(app)
    wand.press(QPointF(30, 30), None)
    assert doc.has_selection()
    assert doc.selection.boundingRect() == QRect(20, 20, 60, 60)
    assert doc.selection_mask is not None
    assert doc.selection_tint is not None
    wand.feather = 5
    wand.selection_mode = "subtract"
    wand.press(QPointF(30, 30), None)
    assert not doc.has_selection()
    doc.clear_selection()
    doc.set_selection(QRegion(QRect(10, 10, 40, 40)), None, feather=8)
    assert doc.selection_mask is not None
    assert doc.selection_feather == 8


def test_crop_canvas_and_transform_selection(qapp):
    doc = Document.new(120, 90, QColor("white"))
    fill_layer(doc.active_layer(), QRect(10, 10, 30, 30), QColor("red"))
    doc.invalidate_all()
    doc.crop(QRect(5, 5, 80, 60))
    assert doc.size == QSize(80, 60)
    doc.history.undo()
    assert doc.size == QSize(120, 90)
    doc.resize_canvas(150, 100, "center")
    assert doc.size == QSize(150, 100)
    doc.history.undo()
    assert doc.size == QSize(120, 90)
    path = QPainterPath()
    path.addRect(QRect(10, 10, 30, 30))
    doc.set_selection(QRegion(QRect(10, 10, 30, 30)), path)
    assert doc.transform_selection(45, 0.8, 0.8)
    assert doc.has_selection()
    doc.history.undo()
    assert doc.composite().pixelColor(15, 15) == QColor("red")


def test_layer_mask_adjustment_roundtrip(qapp, tmp_path):
    doc = Document.new(80, 60, QColor("white"))
    fill_layer(doc.active_layer(), QRect(0, 0, 80, 60), QColor("#2563eb"))
    doc.invalidate_all()
    doc.add_layer_mask(from_selection=False)
    assert doc.active_layer().mask is not None
    doc.add_adjustment_layer("brightness", 1.3)
    assert doc.active_layer().adjustment["type"] == "brightness"
    path = tmp_path / "masked.paint"
    assert save_project(doc, path)
    loaded = load_project(path)
    assert loaded is not None
    masks = [layer for layer in loaded.layers if layer.mask is not None]
    adjustments = [layer for layer in loaded.layers if layer.adjustment is not None]
    assert masks and adjustments


def test_exporters(qapp, tmp_path):
    doc = Document.new(60, 40, QColor("white"))
    fill_layer(doc.active_layer(), QRect(0, 0, 60, 40), QColor("#10b981"))
    doc.invalidate_all()
    doc.frames = [{"image": doc.composite().copy(), "duration": 100}]
    fill_layer(doc.active_layer(), QRect(0, 0, 30, 20), QColor("#111827"))
    doc.invalidate_all()
    doc.frames.append({"image": doc.composite().copy(), "duration": 120})
    gif = tmp_path / "anim.gif"
    apng = tmp_path / "anim.png"
    pdf = tmp_path / "doc.pdf"
    svg = tmp_path / "doc.svg"
    assert export_animation(doc, gif)
    assert export_animation(doc, apng, apng=True)
    assert export_pdf(doc, pdf)
    assert export_svg(doc, svg)
    for path in (gif, apng, pdf, svg):
        assert path.is_file() and path.stat().st_size > 0


def test_autosave_roundtrip(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    doc = Document.new(50, 40, QColor("white"))
    fill_layer(doc.active_layer(), QRect(0, 0, 20, 20), QColor("red"))
    doc.invalidate_all()
    slot = autosave.new_slot()
    assert autosave.write(doc, slot, "Sans titre 1")
    assert doc.path is None
    pending = autosave.entries()
    assert pending
    recovered = autosave.load(pending[0], 1_000_000)
    assert recovered is not None
    assert recovered.size == QSize(50, 40)
    assert recovered.path is None
    autosave.clear(slot)
    assert not autosave.entries()


def test_sheet_units_and_presets(qapp):
    from paint.sheet import PRESETS, from_px, to_px

    a4 = next(preset for preset in PRESETS if preset.name == "A4")
    assert a4.width == 2480 and a4.height == 3508
    assert abs(to_px(210, "mm", 300) - 2480.31) < 0.5
    assert abs(to_px(21, "cm", 300) - 2480.31) < 0.5
    assert abs(to_px(8.27, "in", 300) - 2481.0) < 1.0
    assert abs(from_px(2480, "mm", 300) - 210.0) < 0.5


def test_dpi_and_undoable_resize(qapp):
    doc = Document.new(100, 80, QColor("white"), dpi=300)
    layer = doc.active_layer()
    layer.mask = QImage(layer.image.size(), QImage.Format_ARGB32)
    layer.mask.fill(QColor(255, 255, 255, 255))
    doc.resize_image(50, 40, True, 150)
    assert doc.size == QSize(50, 40)
    assert doc.dpi == 150
    assert layer.mask.size() == QSize(50, 40)
    assert doc.history.can_undo
    doc.history.undo()
    assert doc.size == QSize(100, 80)
    assert doc.dpi == 300
    assert layer.mask.size() == QSize(100, 80)


def test_guides_and_snapping(qapp):
    doc = Document.new(200, 100, QColor("white"))
    doc.add_guide("h", 40)
    doc.add_guide("v", 120)
    assert doc.snap_point(QPointF(118, 43), 6) == QPointF(120, 40)
    snapped = doc.snap_point(QPointF(50, 50), 20, grid=32)
    assert snapped.x() in (32, 64) and snapped.y() == 40
    doc.resize_canvas(80, 60)
    assert all(value <= 60 for value in doc.guides_h)
    assert all(value <= 80 for value in doc.guides_v)


def test_layer_styles_and_undo(qapp):
    from paint.layer import default_styles

    doc = Document.new(80, 80, QColor("white"))
    layer = doc.active_layer()
    fill_layer(layer, QRect(20, 20, 40, 40), QColor("#2563eb"))
    doc.invalidate_all()
    styles = default_styles()
    styles["shadow"].update(enabled=True, offset_x=6, offset_y=6, blur=3)
    styles["stroke"].update(enabled=True, width=3, color="#f97316")
    doc.set_layer_styles(doc.active_index, styles)
    assert layer.styles["shadow"]["enabled"]
    assert doc.composite().pixelColor(63, 63) != QColor("white")
    doc.history.undo()
    assert not layer.styles["shadow"]["enabled"]


def test_pattern_fill(qapp, tmp_path):
    from paint.filters import pattern_fill

    pattern = tmp_path / "pattern.png"
    tile = QImage(8, 8, QImage.Format_ARGB32)
    tile.fill(QColor("#00ff00"))
    assert tile.save(str(pattern))
    doc = Document.new(40, 40, QColor("white"))
    image = doc.active_layer().image
    result, bounds = pattern_fill(image, 5, 5, str(pattern), 100, 40, None)
    assert result is not None
    assert bounds == QRect(0, 0, 40, 40)
    assert result.pixelColor(4, 4) == QColor("#00ff00")


def test_clone_and_tone_tools(qapp):
    from paint.tools.clone import CloneTool
    from paint.tools.tone import ToneTool

    doc = Document.new(160, 120, QColor("white"))
    doc.active_index = 0
    layer = doc.active_layer()
    fill_layer(layer, QRect(60, 0, 20, 120), QColor("#111827"))
    doc.invalidate_all()
    app = FakeApp(doc)
    clone = CloneTool(app)
    clone.size = 18
    clone.source = QPointF(65, 30)
    clone.press(QPointF(20, 90), None)
    for x in range(20, 140, 6):
        clone.move(QPointF(x, 90), None)
    clone.release(QPointF(140, 90), None)
    assert layer.image.pixelColor(30, 90) != QColor("white")

    doc2 = Document.new(80, 80, QColor("#808080"))
    doc2.active_index = 0
    gray = doc2.active_layer()
    app2 = FakeApp(doc2)
    tone = ToneTool(app2)
    tone.size = 30
    tone.mode = "dodge"
    tone.press(QPointF(40, 40), None)
    tone.release(QPointF(40, 40), None)
    assert gray.image.pixelColor(40, 40).lightness() > 128
    assert gray.image.pixelColor(2, 2).lightness() == 128
    doc2.history.undo()
    assert gray.image.pixelColor(40, 40).lightness() == 128
