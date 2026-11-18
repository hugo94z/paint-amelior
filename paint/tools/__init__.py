from .clone import CloneTool
from .draw import BrushTool, EraserTool
from .crop import CropTool
from .fill import FillTool, PickerTool
from .gradient import GradientTool
from .select import SelectionTool
from .shapes import PolygonTool, ShapeTool
from .smudge import SmudgeTool
from .text_tool import TextTool
from .tone import ToneTool
from .wand import MagicWandTool


def build_tools(app):
    return [
        BrushTool(app),
        EraserTool(app),
        CloneTool(app),
        SmudgeTool(app),
        ToneTool(app),
        FillTool(app),
        PickerTool(app),
        ShapeTool(app, "line"),
        ShapeTool(app, "rect"),
        ShapeTool(app, "ellipse"),
        ShapeTool(app, "roundrect"),
        PolygonTool(app),
        GradientTool(app),
        TextTool(app),
        SelectionTool(app),
        MagicWandTool(app),
        CropTool(app),
    ]
