"""
Merge DLNR species.csv (invasives) with data/natives.json for GraysenGame/game_logic.py.

GraysenGame loads data/species.json relative to the process working directory — run from
A4 root via run_game.py so paths resolve next to species.csv.

Duplicate species_id across profiles vs examples: prefer invasive_species_profiles row.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _game_stats(seed: str) -> tuple[int, int]:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    health = 48 + (h[0] % 52)
    attack = 22 + (h[1] % 38)
    return health, attack


def _dedupe_csv_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Same species_id can appear under profiles and examples URLs; keep profiles row."""
    best: dict[str, tuple[int, dict[str, str]]] = {}
    for row in rows:
        sid = row.get("species_id") or ""
        if not sid:
            continue
        sp = row.get("source_page", "")
        rank = 0 if sp == "invasive_species_profiles" else 1
        if sid not in best or rank < best[sid][0]:
            best[sid] = (rank, row)
    return [v[1] for v in best.values()]


def _load_natives(natives_path: Path) -> list[dict[str, Any]]:
    if not natives_path.is_file():
        raise FileNotFoundError(
            f"Missing {natives_path}: native defenders for the game live here (not in DLNR CSV)."
        )
    with natives_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("natives.json must be a JSON array of species objects.")
    return data


def rebuild_game_species_json(csv_path: Path | None = None) -> Path:
    """
    Write data/species.json next to the given species.csv for game_logic.load_species().
    """
    root = _project_root()
    path = (csv_path or (root / "data" / "species.csv")).resolve()
    data_dir = path.parent
    natives_path = data_dir / "natives.json"
    out_path = data_dir / "species.json"

    if not path.is_file():
        raise FileNotFoundError(f"Missing species CSV: {path}")

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    invasives: list[dict[str, Any]] = []
    for row in _dedupe_csv_rows(rows):
        sid = row["species_id"]
        hp, atk = _game_stats(sid)
        display = (row.get("display_name") or sid).strip()
        url = (row.get("profile_url") or "").strip()
        fact_line = f"{display} — {url}" if url else display
        invasives.append(
            {
                "name": sid,
                "health": hp,
                "attack": atk,
                "resistance": {"default": 1.0},
                "is_invasive": True,
                "facts": [fact_line],
            }
        )

    natives = _load_natives(natives_path)
    combined = natives + invasives

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
        f.write("\n")
    return out_path


def ensure_species_json(csv_path: Path | None = None) -> Path:
    """Rebuild species.json if missing or older than species.csv."""
    root = _project_root()
    csv_p = (csv_path or (root / "data" / "species.csv")).resolve()
    json_p = csv_p.parent / "species.json"
    if not json_p.is_file():
        return rebuild_game_species_json(csv_p)
    if json_p.stat().st_mtime < csv_p.stat().st_mtime:
        return rebuild_game_species_json(csv_p)
    return json_p


if __name__ == "__main__":
    out = rebuild_game_species_json()
    print(f"Wrote {out}")
