"""
DLNR species catalog (v1): display name + profile URL only.
Dedupe rule: same normalized https://dlnr.hawaii.gov/... URL -> one row.

display_name is rebuilt as "Common ( Scientific )" when a trailing (...) pair exists;
nested parens (e.g. Rat Lungworm) keep one scientific field for the outer group.
short_code: first 8 hex chars of SHA-256(profile_url); salt suffix disambiguates collisions.

No Flask required — import from your teammate's app or run this file directly.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

URL_PROFILES = "https://dlnr.hawaii.gov/hisc/info/invasive-species-profiles/"
URL_EXAMPLES = "https://dlnr.hawaii.gov/hisc/info/species/"

REQUEST_TIMEOUT = 45
USER_AGENT = (
    "ITM352-species-catalog/1.0 (+educational; contact: course project)"
)

_PROFILE_SECTIONS = frozenset({"Plants", "Vertebrates", "Invertebrates"})


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def default_species_csv_path() -> Path:
    env = os.environ.get("SPECIES_CSV_PATH")
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = _project_root() / p
        return p
    return _project_root() / "data" / "species.csv"


def normalize_profile_url(url: str) -> str | None:
    """
    Canonical URL for deduping: https + lowercase host + path without trailing slash.
    Returns None if not an on-site HISC content URL we want to keep.
    """
    raw = (url or "").strip()
    if not raw.startswith("http"):
        return None
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host != "dlnr.hawaii.gov":
        return None
    path = parsed.path or "/"
    if "/hisc/" not in path and not path.rstrip("/").endswith("/hisc"):
        return None
    parts = [p for p in path.split("/") if p]
    # Require at least /hisc/<something> (reject bare site root /hisc).
    if len(parts) < 2 or parts[0].lower() != "hisc":
        return None
    low = path.lower()
    if any(
        x in low
        for x in (
            "/wp-",
            "/wp/",
            "/files/",
            "feed",
            "xmlrpc",
            ".jpg",
            ".png",
            ".pdf",
        )
    ):
        return None
    path = path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", "", ""))


def url_to_species_id(normalized_url: str) -> str:
    """Last non-empty path segment, safe for filenames / joins."""
    p = urlparse(normalized_url).path.strip("/")
    parts = [x for x in p.split("/") if x]
    return parts[-1] if parts else "unknown"


def _clean_display_name(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t


def split_common_scientific(raw: str) -> tuple[str, str]:
    """
    Split DLNR link text into common vs scientific using the outer pair of the
    final ')' (handles nested parentheses inside the scientific segment).
    If no valid trailing pair, returns (full_cleaned_string, "").
    """
    t = _clean_display_name(raw)
    if not t:
        return "", ""
    last_close = t.rfind(")")
    if last_close == -1:
        return t, ""
    depth = 0
    i = last_close
    while i >= 0:
        c = t[i]
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                common = t[:i].strip()
                scientific = re.sub(r"\s+", " ", t[i + 1 : last_close].strip())
                if not scientific or not common:
                    return t, ""
                return common, scientific
        i -= 1
    return t, ""


def rebuild_display_name(common: str, scientific: str) -> str:
    if scientific:
        return f"{common} ({scientific})"
    return common


def _short_code_from_profile_url(profile_url: str, salt: int = 0) -> str:
    payload = profile_url if salt == 0 else f"{profile_url}\n#{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def enrich_species_rows(rows: list[dict[str, Any]]) -> None:
    """Set common_name, scientific_name, display_name (rebuilt), short_code on each row."""
    for row in rows:
        raw = row.get("display_name") or ""
        common, scientific = split_common_scientific(raw)
        row["common_name"] = common
        row["scientific_name"] = scientific
        row["display_name"] = rebuild_display_name(common, scientific)
    used: set[str] = set()
    for row in rows:
        url = row["profile_url"]
        salt = 0
        while True:
            code = _short_code_from_profile_url(url, salt)
            if code not in used:
                used.add(code)
                row["short_code"] = code
                break
            salt += 1


def _fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def scrape_profiles_categorized(html: str) -> list[dict[str, str]]:
    """
    Parse invasive-species-profiles table: Plants / Vertebrates / Invertebrates only.
    Each row: first column <p><a href=...> -> name + URL.
    """
    soup = BeautifulSoup(html, "lxml")
    pc = soup.select_one("div.primary-content")
    if not pc:
        return []
    table = pc.find("table", attrs={"border": "1"})
    if table is None:
        table = pc.find("table")
    if table is None:
        return []

    out: list[dict[str, str]] = []
    tbody = table.find("tbody") or table
    current: str | None = None

    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        td0 = tds[0]
        h4 = td0.find("h4")
        if h4 is not None:
            title = h4.get_text(" ", strip=True)
            if title in _PROFILE_SECTIONS:
                current = title
            elif title.startswith("Pathogens"):
                current = None
            continue

        if current not in _PROFILE_SECTIONS:
            continue

        for a in td0.select("p a[href]"):
            href = a.get("href") or ""
            norm = normalize_profile_url(href)
            if not norm:
                continue
            name = _clean_display_name(a.get_text(" ", strip=True))
            if not name:
                continue
            out.append(
                {
                    "display_name": name,
                    "profile_url": norm,
                    "category": current,
                    "source_page": "invasive_species_profiles",
                }
            )
    return out


def scrape_species_examples(html: str) -> list[dict[str, str]]:
    """Parse Examples list: only <li> entries whose main link is on dlnr.hawaii.gov/hisc."""
    soup = BeautifulSoup(html, "lxml")
    pc = soup.select_one("div.primary-content")
    if not pc:
        return []
    out: list[dict[str, str]] = []
    for li in pc.select("ul li"):
        a = li.find("a", href=True)
        if a is None:
            continue
        norm = normalize_profile_url(a["href"])
        if not norm:
            continue
        name = _clean_display_name(a.get_text(" ", strip=True))
        if not name:
            continue
        out.append(
            {
                "display_name": name,
                "profile_url": norm,
                "category": "species_examples",
                "source_page": "species_examples",
            }
        )
    return out


def merge_dedupe_by_url(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Dedupe key = normalized profile_url.
    If the same URL appears from profiles + examples, keep categorized row
    (Plants/Vertebrates/Invertebrates) over species_examples.
    """
    priority = {"Plants": 0, "Vertebrates": 1, "Invertebrates": 2, "species_examples": 3}
    best: dict[str, dict[str, Any]] = {}

    for row in rows:
        url = row["profile_url"]
        cat = row["category"]
        pr = priority.get(cat, 9)
        if url not in best or pr < priority.get(best[url]["category"], 9):
            best[url] = {
                "species_id": url_to_species_id(url),
                "display_name": row["display_name"],
                "profile_url": url,
                "category": cat,
                "source_page": row["source_page"],
            }
        elif url in best and pr == priority.get(best[url]["category"], 9):
            # Same priority: prefer longer / more specific display name
            if len(row["display_name"]) > len(best[url]["display_name"]):
                best[url]["display_name"] = row["display_name"]

    return list(best.values())


def fetch_and_build_rows() -> list[dict[str, Any]]:
    profiles_html = _fetch_html(URL_PROFILES)
    examples_html = _fetch_html(URL_EXAMPLES)
    combined = scrape_profiles_categorized(profiles_html) + scrape_species_examples(
        examples_html
    )
    merged = merge_dedupe_by_url(combined)
    enrich_species_rows(merged)
    merged.sort(key=lambda r: (r["category"], r["display_name"].lower()))
    return merged


def save_species_csv(rows: list[dict[str, Any]], csv_path: Path | None = None) -> Path:
    path = csv_path or default_species_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "species_id",
        "short_code",
        "display_name",
        "common_name",
        "scientific_name",
        "profile_url",
        "category",
        "source_page",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fieldnames})
    from game_species_builder import rebuild_game_species_json

    rebuild_game_species_json(path)
    return path


def build_species_catalog(
    force_refresh: bool = False, csv_path: Path | None = None
) -> Path:
    """
    Fetch DLNR pages, merge, dedupe by URL, write species.csv.
    If force_refresh is False and CSV exists and is non-empty, skip network (offline-friendly).
    """
    path = csv_path or default_species_csv_path()
    if not force_refresh and path.is_file() and path.stat().st_size > 100:
        json_path = path.parent / "species.json"
        if not json_path.is_file():
            from game_species_builder import rebuild_game_species_json

            rebuild_game_species_json(path)
        return path
    rows = fetch_and_build_rows()
    if not rows:
        raise RuntimeError("No species rows parsed; DLNR HTML structure may have changed.")
    return save_species_csv(rows, path)


def load_species(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Read species.csv into a list of dicts (no network)."""
    path = csv_path or default_species_csv_path()
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_species_dataframe(csv_path: Path | None = None):
    """Optional pandas loader for analysis joins."""
    import pandas as pd

    path = csv_path or default_species_csv_path()
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build or refresh data/species.csv from DLNR.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch from DLNR even if species.csv already exists.",
    )
    args = parser.parse_args()
    out = build_species_catalog(force_refresh=args.force)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
