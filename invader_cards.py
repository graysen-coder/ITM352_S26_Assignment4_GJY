#ITM352 Assignment 4
#Kiai Aina: Guardians of the Land
#Names: Yuki, Jadon, Graysen
#This file contains a function to load invader profile card fields from data/invaders_set_alpha.json (cached)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ALPHA_PATH = Path(__file__).resolve().parent / "data" / "invaders_set_alpha.json"
_cache: dict[str, dict[str, Any]] | None = None


# This function loads the invaders_set_alpha.json file and returns its contents as a dict
# mapping each invader's name to its full card entry, caching the result so the file is
# only read once per process unless refresh=True is passed
def get_invader_cards_by_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
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