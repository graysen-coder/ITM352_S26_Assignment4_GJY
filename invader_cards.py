"""Load invader profile card fields from data/invaders_set_alpha.json (cached)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALPHA_PATH = Path(__file__).resolve().parent / "data" / "invaders_set_alpha.json"
_cache: dict[str, dict[str, Any]] | None = None


def get_invader_cards_by_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
    global _cache
    if _cache is None or refresh:
        if not _ALPHA_PATH.is_file():
            _cache = {}
        else:
            with _ALPHA_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            _cache = {e["name"]: e for e in data if isinstance(e, dict) and "name" in e}
    return _cache
