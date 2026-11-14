from .draw import BrushTool, EraserTool
from .fill import FillTool, PickerTool
from .gradient import GradientTool
from .select import SelectionTool
from .shapes import PolygonTool, ShapeTool
from .text_tool import TextTool


def build_tools(app):
    return [
        BrushTool(app),
        EraserTool(app),
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
    ]
