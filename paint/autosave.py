from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .io.image_io import image_to_png_bytes
from .io.project_io import load_project, save_project


def directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    path = root / "PaintAmeliore" / "autosave"
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_slot() -> str:
    return uuid.uuid4().hex


def _paths(slot: str) -> tuple[Path, Path]:
    root = directory()
    return root / f"{slot}.paint", root / f"{slot}.json"


def write(doc, slot: str, label: str) -> bool:
    project, metadata = _paths(slot)
    try:
        if not save_project(doc, project, set_path=False):
            return False
        info = {
            "slot": slot,
            "label": label,
            "original": str(doc.path) if doc.path else None,
            "timestamp": time.time(),
        }
        temp = metadata.with_suffix(".json.tmp")
        temp.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        temp.replace(metadata)
        return True
    except OSError:
        return False


def entries() -> list[dict]:
    root = directory()
    result = []
    for meta in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        project = meta.with_suffix(".paint")
        if not project.is_file():
            continue
        info["project"] = str(project)
        info["slot"] = meta.stem
        result.append(info)
    return result


def load(entry: dict, undo_budget: int) -> object | None:
    doc = load_project(entry["project"], undo_budget)
    if doc is None:
        return None
    doc.path = None
    doc.mark_modified(True)
    return doc


def clear(slot: str) -> None:
    for path in _paths(slot):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def clear_all() -> None:
    for path in directory().glob("*"):
        try:
            path.unlink()
        except OSError:
            pass
