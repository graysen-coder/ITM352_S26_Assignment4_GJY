"""
Fetch https://dlnr.hawaii.gov/hisc/info/invasive-species-profiles/ and build
data/invaders_list.json — Vertebrates + Invertebrates only (no Plants / Pathogens / Aquatic).

Also writes data/invaders_set_alpha.json (active invaders + DLNR-style card fields, no thumbnails).

Run from root:  python build_invaders_set_1.py
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

LIST_URL = "https://dlnr.hawaii.gov/hisc/info/invasive-species-profiles/"
USER_AGENT = "Mozilla/5.0 ITM352 educational (+course project)"
FULL_SET_PATH = Path("data") / "invaders_list.json"
ALPHA_SET_PATH = Path("data") / "invaders_set_alpha.json"

# Keep gameplay to 6 invaders for now (miconia replaced by brown-tree-snake).
ACTIVE_INVADER_NAMES = [
    "coqui-frog",
    "coconut-rhinoceros-beetle",
    "brown-tree-snake",
    "little-fire-ant-lfa",
    "naio-thrips",
    "mongoose-urva-auropunctata",
]

SKIP_SUBSECTION_TITLES = frozenset(
    {
        "rodents",
        "snakes",
        "ungulates",
        "fruit flies",
    }
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _game_stats(seed: str) -> tuple[int, int]:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    health = 48 + (h[0] % 52)
    attack = 22 + (h[1] % 38)
    return health, attack


def _slugify(label: str) -> str:
    t = label.lower().replace("ʻ", "").replace("'", "").replace("`", "")
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-") or "unknown"


def _slug_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    slug = parts[-1]
    # e.g. https://dlnr.hawaii.gov/hisc/?p=... yields path "/hisc" → unusable slug "hisc"
    if slug in ("hisc", "info", "wildlife", "dofaw"):
        return None
    return slug


def _normalize_url(href: str | None, base: str) -> str | None:
    if not href or href.strip() in ("#",):
        return None
    u = urljoin(base, href.strip())
    return u.split("#")[0]


def _split_common_scientific(raw: str) -> tuple[str, str | None]:
    t = re.sub(r"\s+", " ", (raw or "").strip())
    if "(" not in t or ")" not in t:
        return t, None
    lo = t.find("(")
    hi = t.rfind(")")
    if hi <= lo:
        return t, None
    common = t[:lo].strip()
    scientific = t[lo + 1 : hi].strip()
    return common, scientific or None


def _row_texts(tr) -> tuple[str, str, str]:
    cells = tr.find_all("td")
    if len(cells) < 3:
        return "", "", ""
    return (
        cells[0].get_text(" ", strip=True),
        cells[1].get_text(" ", strip=True),
        cells[2].get_text(" ", strip=True),
    )


def _first_hisc_link(td) -> str | None:
    for a in td.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#"):
            continue
        return href
    return None


def _section_indices(rows: list) -> tuple[int, int, int]:
    idx_v = idx_i = idx_p = -1
    for i, tr in enumerate(rows):
        cells = tr.find_all("td")
        if not cells:
            continue
        t0 = cells[0].get_text(" ", strip=True)
        tl = t0.lower()
        if tl == "vertebrates":
            idx_v = i
        elif tl == "invertebrates":
            idx_i = i
        elif tl.startswith("pathogens and diseases"):
            idx_p = i
            break
    if idx_v < 0 or idx_i < 0 or idx_p < 0:
        raise RuntimeError("Could not find Vertebrates / Invertebrates / Pathogens table sections.")
    return idx_v, idx_i, idx_p


def _parse_table(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        raise RuntimeError("No table on invasive species profiles page.")
    rows = table.find_all("tr")
    idx_v, idx_i, idx_p = _section_indices(rows)

    out: list[dict[str, Any]] = []
    for tr in rows[idx_v + 1 : idx_i] + rows[idx_i + 1 : idx_p]:
        name_cell = tr.find_all("td")
        if len(name_cell) < 3:
            continue
        name_raw, reg_raw, prev_raw = _row_texts(tr)
        if not name_raw:
            continue
        if name_raw.lower() in SKIP_SUBSECTION_TITLES:
            continue

        href = _first_hisc_link(name_cell[0])
        profile_url = _normalize_url(href, LIST_URL)

        common, scientific = _split_common_scientific(name_raw)
        if not common:
            continue

        slug = _slug_from_url(profile_url) or _slugify(common)

        reg = reg_raw.strip() if reg_raw.strip() else None
        prev = prev_raw.strip() if prev_raw.strip() else None

        health, attack = _game_stats(slug)

        facts: list[str] = []
        if scientific:
            facts.append(f"{common} — {scientific}")
        else:
            facts.append(common)
        if profile_url:
            facts.append(f"Profile: {profile_url}")
        if reg:
            facts.append(f"Regulatory status: {reg}")
        if prev:
            facts.append(f"Prevention / Control: {prev}")

        out.append(
            {
                "name": slug,
                "common_name": common,
                "scientific_name": scientific,
                "profile_url": profile_url,
                "regulatory_status": reg,
                "prevention_control_category": prev,
                "health": health,
                "attack": attack,
                "resistance": {"default": 1.0},
                "is_invasive": True,
                "weak_to": ["Placeholder weakness"],
                "strong_against": ["Placeholder strength"],
                "facts": facts,
            }
        )

    return out


def _to_game_subset_entry(entry: dict[str, Any]) -> dict[str, Any]:
    common = entry.get("common_name") or entry.get("name")
    scientific = entry.get("scientific_name")
    url = entry.get("profile_url")

    if scientific:
        fact = f"{common} ({scientific})"
    else:
        fact = str(common)
    if url:
        fact = f"{fact} — {url}"

    return {
        "name": entry["name"],
        "health": entry["health"],
        "attack": entry["attack"],
        "resistance": {"default": 1.0},
        "is_invasive": True,
        "weak_to": ["Placeholder weakness"],
        "strong_against": ["Placeholder strength"],
        "facts": [fact],
    }


def _to_alpha_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Gameplay keys from _to_game_subset_entry plus DLNR-style card lines (no thumbnail)."""
    base = _to_game_subset_entry(entry)
    common = entry.get("common_name") or entry["name"]
    scientific = entry.get("scientific_name")
    return {
        **base,
        "display_name": common,
        "common_line": f"Common: {common}",
        "scientific": (f"Scientific: {scientific}" if scientific else None),
        "profile_url": entry.get("profile_url"),
        "image_url": None,
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    out_path = root / FULL_SET_PATH
    alpha_out_path = root / ALPHA_SET_PATH

    sess = _session()
    r = sess.get(LIST_URL, timeout=60)
    r.raise_for_status()
    entries = _parse_table(r.text)

    axis = next((e for e in entries if e.get("common_name") == "Axis Deer"), None)
    if axis:
        axis["regulatory_status"] = None
        axis["prevention_control_category"] = "BIISC Target Species"
        axis["facts"] = [
            f"{axis['common_name']} — {axis['scientific_name']}",
            "Prevention / Control: BIISC Target Species",
        ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")

    by_name = {e["name"]: e for e in entries}
    missing = [n for n in ACTIVE_INVADER_NAMES if n not in by_name]
    if missing:
        raise RuntimeError(f"Missing active invaders in scraped set: {missing}")

    alpha_entries = [_to_alpha_entry(by_name[n]) for n in ACTIVE_INVADER_NAMES]
    with alpha_out_path.open("w", encoding="utf-8") as f:
        json.dump(alpha_entries, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(entries)} invaders to {out_path}")
    print(f"Wrote {len(alpha_entries)} active invaders to {alpha_out_path}")


if __name__ == "__main__":
    main()
