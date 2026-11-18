from __future__ import annotations

import json
from dataclasses import asdict, dataclass

KEY = "brushes/custom"


@dataclass
class BrushPreset:
    name: str
    size: int = 24
    hardness: float = 0.85
    opacity: float = 1.0
    spacing: float = 0.12
    pressure: bool = True
    scatter: float = 0.0
    tip: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "BrushPreset":
        return cls(
            name=str(data.get("name", "Pinceau")),
            size=max(1, min(800, int(data.get("size", 24)))),
            hardness=max(0.0, min(1.0, float(data.get("hardness", 0.85)))),
            opacity=max(0.01, min(1.0, float(data.get("opacity", 1.0)))),
            spacing=max(0.02, min(2.0, float(data.get("spacing", 0.12)))),
            pressure=bool(data.get("pressure", True)),
            scatter=max(0.0, min(2.0, float(data.get("scatter", 0.0)))),
            tip=str(data.get("tip", "")),
        )


BUILTIN = (
    BrushPreset("Rond net", 20, 0.98, 1.0, 0.08, True),
    BrushPreset("Rond doux", 28, 0.55, 0.9, 0.1, True),
    BrushPreset("Aérographe", 70, 0.05, 0.45, 0.05, False, 0.35),
    BrushPreset("Crayon", 5, 0.85, 0.85, 0.05, True),
    BrushPreset("Marqueur", 36, 1.0, 0.75, 0.06, False),
    BrushPreset("Grain", 30, 0.4, 0.6, 0.18, True, 0.8),
)


def load_custom(settings) -> list[BrushPreset]:
    if settings is None:
        return []
    raw = settings.value(KEY, "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        try:
            out.append(BrushPreset.from_dict(item))
        except (TypeError, ValueError):
            continue
    return out


def save_custom(settings, presets: list[BrushPreset]) -> None:
    if settings is None:
        return
    settings.setValue(KEY, json.dumps([asdict(preset) for preset in presets],
                                      ensure_ascii=False))
    settings.sync()


def all_presets(settings) -> list[BrushPreset]:
    return list(BUILTIN) + load_custom(settings)
