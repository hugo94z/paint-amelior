from __future__ import annotations

import ctypes
import json
import os
import platform
from pathlib import Path

APP_NAME = "Paint Amélioré"
APP_VERSION = "1.6.0"

MB = 1024 * 1024


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def total_ram_mb() -> int:
    if os.name == "nt":
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys // MB)
        except (AttributeError, OSError):
            pass
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // MB)
    except (ValueError, OSError, AttributeError):
        return 4096


def quick_detect() -> dict:
    logical = os.cpu_count() or 4
    return {
        "cpu_name": os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or "Inconnu",
        "physical_cores": max(1, logical // 2),
        "logical_cores": logical,
        "ram_total_mb": total_ram_mb(),
        "gpu": "Inconnu",
    }


def allocate(detected: dict) -> dict:
    logical = max(1, int(detected.get("logical_cores") or os.cpu_count() or 4))
    physical = max(1, int(detected.get("physical_cores") or logical))
    ram_mb = max(1024, int(detected.get("ram_total_mb") or 4096))
    threads = max(1, min(logical - 1 if logical > 1 else 1, physical * 2, 32))
    app_ram_mb = int(min(max((ram_mb - 2048) * 0.5, 1024), 16384))
    undo_mb = int(min(max(app_ram_mb * 0.35, 256), 4096))
    stamp_mb = int(min(max(app_ram_mb * 0.03, 48), 512))
    return {
        "threads": threads,
        "app_ram_mb": app_ram_mb,
        "undo_mb": undo_mb,
        "stamp_cache_mb": stamp_mb,
    }


DEFAULT_DETECTED = {
    "cpu_name": "Inconnu",
    "physical_cores": 0,
    "logical_cores": os.cpu_count() or 4,
    "ram_total_mb": 4096,
    "gpu": "Inconnu",
}

class Settings:
    def __init__(self, data: dict | None, source: Path | None = None):
        data = data or {}
        detected = dict(DEFAULT_DETECTED)
        detected.update(data.get("detected") or {})
        alloc = allocate(detected)
        alloc.update(data.get("allocation") or {})
        self.detected = detected
        self.allocation = alloc
        self.source = source

    @property
    def threads(self) -> int:
        return int(self.allocation.get("threads", 4))

    @property
    def app_ram_bytes(self) -> int:
        return int(self.allocation.get("app_ram_mb", 2048)) * MB

    @property
    def undo_budget_bytes(self) -> int:
        return int(self.allocation.get("undo_mb", 400)) * MB

    @property
    def stamp_cache_bytes(self) -> int:
        return int(self.allocation.get("stamp_cache_mb", 128)) * MB

    @property
    def cpu_name(self) -> str:
        return str(self.detected.get("cpu_name") or "Inconnu")

    @property
    def ram_total_mb(self) -> int:
        return int(self.detected.get("ram_total_mb") or 0)

    def summary_lines(self) -> list[str]:
        d = self.detected
        a = self.allocation
        return [
            f"Processeur : {d.get('cpu_name')}",
            f"Cœurs physiques : {d.get('physical_cores')}  •  cœurs logiques : {d.get('logical_cores')}",
            f"Mémoire vive : {int(d.get('ram_total_mb') or 0) / 1024:.1f} Go",
            f"Carte graphique : {d.get('gpu')}",
            "",
            f"Threads alloués à l'application : {a.get('threads')}",
            f"Mémoire allouée à l'application : {int(a.get('app_ram_mb', 0))} Mo",
            f"Budget historique (annuler) : {int(a.get('undo_mb', 0))} Mo",
            f"Cache des pinceaux : {int(a.get('stamp_cache_mb', 0))} Mo",
            f"Fichier de configuration : {self.source or 'valeurs par défaut'}",
        ]


def _candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("PAINT_HARDWARE")
    if env:
        out.append(Path(env))
    out.append(Path(__file__).resolve().parent.parent / "hardware.json")
    base = os.environ.get("LOCALAPPDATA")
    if base:
        out.append(Path(base) / "PaintAmeliore" / "hardware.json")
    return out


def load_settings() -> Settings:
    for path in _candidates():
        try:
            if path.is_file():
                return Settings(json.loads(path.read_text(encoding="utf-8")), path)
        except (OSError, ValueError):
            continue
    return Settings({"detected": quick_detect()})
