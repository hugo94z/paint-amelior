from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from .config import Settings, allocate, available_ram_mb, total_ram_mb


def _powershell_json(script: str):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _cpu_data() -> dict:
    data = _powershell_json(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"
    )
    if isinstance(data, list):
        data = data[0] if data else None
    logical = os.cpu_count() or 1
    if isinstance(data, dict) and data.get("Name"):
        return {
            "cpu_name": str(data.get("Name")).strip(),
            "physical_cores": int(data.get("NumberOfCores") or 0),
            "logical_cores": int(data.get("NumberOfLogicalProcessors") or logical),
        }
    return {
        "cpu_name": platform.processor() or "Inconnu",
        "physical_cores": max(1, logical // 2),
        "logical_cores": logical,
    }


def _gpu_name() -> str:
    data = _powershell_json(
        "Get-CimInstance Win32_VideoController | Select-Object -First 1 Name | ConvertTo-Json -Compress"
    )
    if isinstance(data, dict) and data.get("Name"):
        return str(data.get("Name")).strip()
    return "Inconnu"


def detect() -> dict:
    cents = _cpu_data()
    detected = {
        "cpu_name": cents["cpu_name"],
        "physical_cores": cents["physical_cores"],
        "logical_cores": cents["logical_cores"],
        "ram_total_mb": total_ram_mb(),
        "ram_available_mb": available_ram_mb(),
        "gpu": _gpu_name(),
    }
    return {"detected": detected, "allocation": allocate(detected)}


def summary(data: dict, source=None) -> str:
    settings = Settings(data, source)
    return "\n".join(settings.summary_lines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse matérielle de Paint Amélioré")
    parser.add_argument("--write", type=Path, help="Écrit hardware.json")
    parser.add_argument("--json", action="store_true", help="Sortie JSON brute")
    parser.add_argument("--quiet", action="store_true", help="Aucun affichage")
    args = parser.parse_args(argv)

    data = detect()
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(summary(data, args.write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
