"""Invader card data from data/invaders_set_alpha.json (cached).

Bullets in description_points / impact_points come from the DLNR scraper in
archive/scripts/build_invaders_set_1.py, not hand-typed in the running app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALPHA_PATH = Path(__file__).resolve().parent / "data" / "invaders_set_alpha.json"
# One in-memory copy of the JSON after first load (set refresh=True to re-read the file).
_cache: dict[str, dict[str, Any]] | None = None


def get_invader_cards_by_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Return invader slug -> full card dict (facts, bullets, images) from ``invaders_set_alpha.json``."""
    global _cache
    if _cache is None or refresh:
        with _ALPHA_PATH.open(encoding="utf-8") as alpha_file:
            card_entries = json.load(alpha_file)
        _cache = {
            entry["name"]: entry
            for entry in card_entries
            if isinstance(entry, dict) and "name" in entry
        }
    return _cache
