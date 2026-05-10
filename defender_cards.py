"""
Scrape DLNR Native Birds index + species pages for home-picker cards.
https://dlnr.hawaii.gov/wildlife/birds/
"""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

BIRDS_INDEX_URL = "https://dlnr.hawaii.gov/wildlife/birds/"
USER_AGENT = "Mozilla/5.0 ITM352 educational (+course project)"

# Profile path slug on dlnr.hawaii.gov (order = display order)
SLUGS_ORDERED = ["nene", "iiwi", "io", "pueo", "uau", "alala"]

KEY_BY_SLUG: dict[str, str] = {
    "nene": "nene",
    "iiwi": "'I'iwi",
    "io": "'Io",
    "pueo": "pueo",
    "uau": "'Ua'u",
    "alala": "'Alala",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _pick_best_thumbnail(src: str, srcset: str | None) -> str:
    """Prefer 768w from srcset when present; else largest listed width; else src."""
    if not srcset:
        return src
    best_url = None
    best_w = -1
    w768 = None
    for part in srcset.split(","):
        part = part.strip()
        m = re.match(r"(\S+)\s+(\d+)w$", part)
        if not m:
            continue
        url, w = m.group(1), int(m.group(2))
        if w == 768:
            w768 = url
        if w > best_w:
            best_w = w
            best_url = url
    if w768:
        return w768
    if best_url:
        return best_url
    return src


def _listing_thumbnail_and_profile(soup: BeautifulSoup, slug: str) -> tuple[str, str]:
    """Match the species anchor, then walk up until a sibling subtree contains the card image."""
    needle = f"/wildlife/birds/{slug}/"
    for a in soup.find_all("a", href=True):
        if needle not in a["href"]:
            continue
        el = a
        for _ in range(12):
            if el is None:
                break
            im = el.find("img", src=True)
            if im:
                thumb = _pick_best_thumbnail(im["src"], im.get("srcset"))
                href = a["href"]
                profile_url = href if href.endswith("/") else href + "/"
                return thumb, profile_url
            el = el.parent
    raise ValueError(f"No listing thumbnail + link for slug={slug!r}")


def _parse_names_section(soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
    """Returns (olelo, common, scientific_display) from #### Names list."""
    names_h4 = None
    for h4 in soup.find_all("h4"):
        if h4.get_text(strip=True).lower() == "names":
            names_h4 = h4
            break
    if not names_h4:
        return None, None, None
    ul = names_h4.find_next_sibling("ul")
    if not ul:
        return None, None, None
    olelo = common = None
    scientific_line: str | None = None
    for li in ul.find_all("li"):
        t = li.get_text(" ", strip=True)
        low = t.lower()
        if low.startswith("scientific:"):
            scientific_line = t
        elif "ōlelo" in low or "olelo" in low:
            if ":" in t:
                olelo = t.split(":", 1)[1].strip()
        elif low.startswith("common:"):
            common = t.split(":", 1)[1].strip()
    return olelo, common, scientific_line


def _display_name_from_detail(soup: BeautifulSoup) -> str:
    olelo, common, _ = _parse_names_section(soup)
    if olelo and common:
        return f"{olelo}, {common}"
    if olelo:
        return olelo
    h2 = soup.find("h2")
    if h2 and h2.get_text(strip=True):
        return h2.get_text(strip=True)
    return "Native bird"


def _short_name_before_comma(full: str) -> str:
    """Card title: substring before the first comma, else full string trimmed."""
    t = (full or "").strip()
    if "," in t:
        return t.split(",", 1)[0].strip()
    return t


def _card_fields_for_slug(slug: str, detail_soup: BeautifulSoup) -> dict[str, str]:
    """
    card_name: short title (before comma).
    common_line: 'Common: …' (ʻIʻiwi uses fixed Scarlet Honeycreeper).
    scientific: 'Scientific: …' (ʻIʻiwi: first binomial before comma only).
    """
    full_display = _display_name_from_detail(detail_soup)
    card_name = _short_name_before_comma(full_display)
    _, common, sci_raw = _parse_names_section(detail_soup)

    if slug == "iiwi":
        common_line = "Common: Scarlet Honeycreeper"
        sci_trimmed = ""
        if sci_raw:
            body = sci_raw.split(":", 1)[1].strip() if ":" in sci_raw else sci_raw
            sci_trimmed = body.split(",")[0].strip()
        scientific = f"Scientific: {sci_trimmed}" if sci_trimmed else (
            sci_raw or "Scientific: (not found)"
        )
    else:
        common_line = f"Common: {common}" if common else ""
        scientific = sci_raw if sci_raw else "Scientific: (not found)"

    return {
        "display_name": full_display,
        "card_name": card_name,
        "common_line": common_line,
        "scientific": scientific,
    }


def fetch_home_species_cards(timeout: int = 45) -> list[dict[str, Any]]:
    """
    Build six dicts: key, display_name (full), card_name, common_line, scientific,
    profile_url, image_url.
    """
    sess = _session()
    r = sess.get(BIRDS_INDEX_URL, timeout=timeout)
    r.raise_for_status()
    index_soup = BeautifulSoup(r.text, "lxml")

    out: list[dict[str, Any]] = []
    for slug in SLUGS_ORDERED:
        image_url, profile_url = _listing_thumbnail_and_profile(index_soup, slug)

        dr = sess.get(profile_url, timeout=timeout)
        dr.raise_for_status()
        detail_soup = BeautifulSoup(dr.text, "lxml")
        fields = _card_fields_for_slug(slug, detail_soup)

        out.append(
            {
                "key": KEY_BY_SLUG[slug],
                "display_name": fields["display_name"],
                "card_name": fields["card_name"],
                "common_line": fields["common_line"],
                "scientific": fields["scientific"],
                "profile_url": profile_url,
                "image_url": image_url,
            }
        )
    return out


_home_species_cache: list[dict[str, Any]] | None = None


def get_home_species_cards(refresh: bool = False) -> list[dict[str, Any]]:
    """Cached scrape (one fetch per process unless refresh=True)."""
    global _home_species_cache
    if _home_species_cache is None or refresh:
        _home_species_cache = fetch_home_species_cards()
    return _home_species_cache


# Native roster keys in defenders.json match DLNR URL slug (e.g. iiwi, not 'I'iwi).
DEFENDER_NATIVE_NAMES_ORDERED: list[str] = list(SLUGS_ORDERED)


def get_dlnr_meta_by_native_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Map defenders.json ``name`` -> display fields for defender cards."""
    cards = get_home_species_cards(refresh=refresh)
    return {
        slug: {
            "display_name": c["card_name"],
            "common_line": c.get("common_line", ""),
            "image_url": c["image_url"],
            "profile_url": c["profile_url"],
            "scientific": c["scientific"],
        }
        for slug, c in zip(SLUGS_ORDERED, cards)
    }
