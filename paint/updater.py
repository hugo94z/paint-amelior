from __future__ import annotations

import json
import urllib.error
import urllib.request

REPO = "hugo94z/paint-amelior"


def latest(repo: str = REPO, timeout: float = 6.0):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"User-Agent": "PaintAmeliore", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    tag = str(data.get("tag_name", "")).lstrip("v")
    if not tag:
        return None
    return tag, data.get("html_url", f"https://github.com/{repo}/releases/latest")
