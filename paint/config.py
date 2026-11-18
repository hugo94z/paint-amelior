from __future__ import annotations

import ctypes
import json
import os
import platform
from pathlib import Path

APP_NAME = "Paint Amélioré"
APP_VERSION = "1.6.5"

MB = 1024 * 1024
ALLOCATION_VERSION = 3


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


def _memory_status() -> _MemoryStatus | None:
    if os.name != "nt":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    try:
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status
    except (AttributeError, OSError):
        pass
    return None


def total_ram_mb() -> int:
    status = _memory_status()
    if status is not None:
        return int(status.ullTotalPhys // MB)
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // MB)
    except (ValueError, OSError, AttributeError):
        return 4096


def available_ram_mb() -> int:
    status = _memory_status()
    if status is not None:
        return int(status.ullAvailPhys // MB)
    return int(total_ram_mb() * 0.65)


def quick_detect() -> dict:
    logical = os.cpu_count() or 4
    return {
        "cpu_name": os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or "Inconnu",
        "physical_cores": max(1, logical // 2),
        "logical_cores": logical,
        "ram_total_mb": total_ram_mb(),
        "ram_available_mb": available_ram_mb(),
        "gpu": "Inconnu",
    }


def document_undo_budget(width: int, height: int, base: int) -> int:
    surface = max(1, int(width)) * max(1, int(height)) * 4
    return int(min(max(1, base), max(64 * MB, surface * 16)))


def allocate(detected: dict) -> dict:
    logical = max(1, min(128, int(detected.get("logical_cores") or os.cpu_count() or 4)))
    physical = max(1, min(logical, int(detected.get("physical_cores") or 0) or logical // 2))
    total = max(1024, int(detected.get("ram_total_mb") or 4096))
    available_field = detected.get("ram_available_mb")
    if available_field:
        available = max(512, min(total, int(available_field)))
        reserve = int(min(max(available * 0.15, 512), 4096))
        usable = max(384, available - reserve)
    else:
        available = int(total * 0.65)
        reserve = int(min(max(total * 0.22, 1024), 4096, max(512, total * 0.45)))
        usable = max(384, total - reserve)
    app_ram = int(min(max(usable * 0.6, 384), 24576, total * 0.62))
    undo = int(min(max(app_ram * 0.38, 192), 8192, app_ram * 0.55))
    stamp = int(min(max(app_ram * 0.05, 48), 1024, app_ram * 0.2))
    doc_ram = int(min(max(app_ram * 0.6, 256), app_ram * 0.75))
    max_pixels = int(doc_ram * MB / (4 * 3))

    if logical <= 2:
        threads = 1
    elif physical >= 2:
        threads = min(physical, max(1, logical - 1), 32)
    else:
        threads = min(max(1, logical - 1), 32)
    threads = max(1, threads)

    return {
        "allocation_version": ALLOCATION_VERSION,
        "threads": threads,
        "app_ram_mb": app_ram,
        "undo_mb": undo,
        "stamp_cache_mb": stamp,
        "doc_ram_mb": doc_ram,
        "reserve_mb": reserve,
        "max_document_pixels": max_pixels,
        "logical_cores": logical,
        "physical_cores": physical,
        "ram_total_mb": total,
        "ram_available_mb": available,
    }


DEFAULT_DETECTED = {
    "cpu_name": "Inconnu",
    "physical_cores": 0,
    "logical_cores": os.cpu_count() or 4,
    "ram_total_mb": 4096,
    "ram_available_mb": 2662,
    "gpu": "Inconnu",
}


class Settings:
    def __init__(self, data: dict | None, source: Path | None = None):
        data = data or {}
        detected = dict(DEFAULT_DETECTED)
        detected.update(data.get("detected") or {})
        if not detected.get("ram_available_mb"):
            detected["ram_available_mb"] = available_ram_mb()
        alloc = allocate(detected)
        stored = data.get("allocation") or {}
        try:
            version = int(stored.get("allocation_version", 0))
        except (TypeError, ValueError):
            version = 0
        if version >= ALLOCATION_VERSION:
            alloc.update(stored)
        self.detected = detected
        self.allocation = alloc
        self.source = source

    @property
    def threads(self) -> int:
        return max(1, int(self.allocation.get("threads", 4)))

    @property
    def app_ram_bytes(self) -> int:
        return int(self.allocation.get("app_ram_mb", 2048)) * MB

    @property
    def doc_ram_bytes(self) -> int:
        return int(self.allocation.get("doc_ram_mb", 1024)) * MB

    @property
    def max_document_pixels(self) -> int:
        return int(self.allocation.get("max_document_pixels", 100_000_000))

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

    @property
    def ram_available_mb(self) -> int:
        return int(self.detected.get("ram_available_mb") or 0)

    def summary_lines(self) -> list[str]:
        d = self.detected
        a = self.allocation
        return [
            f"Processeur : {d.get('cpu_name')}",
            f"Cœurs physiques : {d.get('physical_cores')}  •  cœurs logiques : {d.get('logical_cores')}",
            f"Mémoire vive : {int(d.get('ram_total_mb') or 0) / 1024:.1f} Go"
            f"  •  disponible : {int(d.get('ram_available_mb') or 0) / 1024:.1f} Go",
            f"Carte graphique : {d.get('gpu')}",
            "",
            f"Réserve système : {int(a.get('reserve_mb', 0))} Mo",
            f"Threads alloués à l'application : {a.get('threads')}",
            f"Mémoire allouée à l'application : {int(a.get('app_ram_mb', 0))} Mo",
            f"Budget par document : {int(a.get('doc_ram_mb', 0))} Mo",
            f"Budget historique (annuler) : {int(a.get('undo_mb', 0))} Mo",
            f"Cache des pinceaux : {int(a.get('stamp_cache_mb', 0))} Mo",
            f"Taille maximale conseillée (3 calques) : "
            f"{int(a.get('max_document_pixels', 0)) / 1_000_000:.0f} Mpx",
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
