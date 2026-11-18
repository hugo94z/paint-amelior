from __future__ import annotations

from dataclasses import dataclass

MM_PER_INCH = 25.4

UNIT_FACTORS = {
    "px": 1.0,
    "mm": MM_PER_INCH,
    "cm": 2.54,
    "in": 1.0,
}

UNIT_LABELS = (
    ("px", "Pixels"),
    ("mm", "Millimètres"),
    ("cm", "Centimètres"),
    ("in", "Pouces"),
)

UNIT_SUFFIX = {"px": " px", "mm": " mm", "cm": " cm", "in": " po"}

UNIT_DECIMALS = {"px": 0, "mm": 1, "cm": 2, "in": 2}

RATIOS = (
    ("Libre", None),
    ("1:1", (1, 1)),
    ("4:3", (4, 3)),
    ("3:2", (3, 2)),
    ("16:9", (16, 9)),
    ("9:16", (9, 16)),
    ("3:4", (3, 4)),
    ("2:3", (2, 3)),
    ("√2 (A)", (1, 1.41421356237)),
)

MAX_SIDE = 16384
MAX_MEGAPIXELS = 300

DPI_PRESETS = (72, 96, 150, 300, 600)


def px_per_unit(unit: str, dpi: float) -> float:
    if unit == "px":
        return 1.0
    if unit == "mm":
        return max(1.0, float(dpi)) / MM_PER_INCH
    if unit == "cm":
        return max(1.0, float(dpi)) / 2.54
    if unit == "in":
        return max(1.0, float(dpi))
    return 1.0


def to_px(value: float, unit: str, dpi: float) -> float:
    return float(value) * px_per_unit(unit, dpi)


def from_px(pixels: float, unit: str, dpi: float) -> float:
    return float(pixels) / px_per_unit(unit, dpi)


@dataclass(frozen=True)
class SheetPreset:
    name: str
    width: int
    height: int
    dpi: int
    category: str

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def physical(self) -> str:
        width_mm = self.width / self.dpi * MM_PER_INCH
        height_mm = self.height / self.dpi * MM_PER_INCH
        if width_mm >= 100 or height_mm >= 100:
            return f"{width_mm / 10:.1f} × {height_mm / 10:.1f} cm"
        return f"{width_mm:.0f} × {height_mm:.0f} mm"


def _paper(name: str, width_mm: float, height_mm: float, dpi: int = 300) -> SheetPreset:
    return SheetPreset(
        name,
        int(round(width_mm / MM_PER_INCH * dpi)),
        int(round(height_mm / MM_PER_INCH * dpi)),
        dpi,
        "Papier",
    )


PRESETS: tuple[SheetPreset, ...] = (
    _paper("A6", 105, 148),
    _paper("A5", 148, 210),
    _paper("A4", 210, 297),
    _paper("A3", 297, 420),
    _paper("A2", 420, 594),
    _paper("A1", 594, 841),
    _paper("A0", 841, 1189),
    _paper("Letter", 215.9, 279.4),
    _paper("Legal", 215.9, 355.6),
    _paper("Tabloid", 279.4, 431.8),
    _paper("Photo 10 × 15", 100, 150),
    _paper("Photo 13 × 18", 130, 180),
    _paper("Photo 20 × 30", 200, 300),
    SheetPreset("HD 1280 × 720", 1280, 720, 96, "Écran"),
    SheetPreset("Full HD 1920 × 1080", 1920, 1080, 96, "Écran"),
    SheetPreset("QHD 2560 × 1440", 2560, 1440, 96, "Écran"),
    SheetPreset("4K 3840 × 2160", 3840, 2160, 96, "Écran"),
    SheetPreset("Carré 1080", 1080, 1080, 96, "Carré"),
    SheetPreset("Carré 2048", 2048, 2048, 96, "Carré"),
    SheetPreset("Carré 4096", 4096, 4096, 96, "Carré"),
    SheetPreset("Bannière 1200 × 630", 1200, 630, 96, "Web"),
    SheetPreset("Post 1080 × 1080", 1080, 1080, 96, "Web"),
    SheetPreset("Story 1080 × 1920", 1080, 1920, 96, "Web"),
)


def preset_categories() -> list[str]:
    seen: list[str] = []
    for preset in PRESETS:
        if preset.category not in seen:
            seen.append(preset.category)
    return seen


def estimate_bytes(width: int, height: int, layers: int = 2) -> int:
    return max(1, int(width)) * max(1, int(height)) * 4 * max(1, int(layers))


def human_bytes(value: float) -> str:
    value = float(value)
    if value < 1024:
        return f"{value:.0f} o"
    if value < 1024 * 1024:
        return f"{value / 1024:.0f} Ko"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.0f} Mo"
    return f"{value / (1024 * 1024 * 1024):.1f} Go"


def clamp_side(value: float) -> int:
    return max(1, min(MAX_SIDE, int(round(value))))


def sheet_label(width: int, height: int, dpi: int, unit: str = "auto") -> str:
    width_mm = width / max(1, dpi) * MM_PER_INCH
    height_mm = height / max(1, dpi) * MM_PER_INCH
    if width_mm >= 100 or height_mm >= 100:
        physical = f"{width_mm / 10:.1f} × {height_mm / 10:.1f} cm"
    else:
        physical = f"{width_mm:.0f} × {height_mm:.0f} mm"
    return f"{width} × {height} px • {physical} @ {dpi} dpi"
