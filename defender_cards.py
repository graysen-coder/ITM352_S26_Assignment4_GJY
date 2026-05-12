#ITM352 Assignment 4
#Kiai Aina: Guardians of the Land
#Names: Yuki, Jadon, Graysen
#This file contains code to scrape the DLNR Native Birds index and species pages 
# to build the home-picker cards for the game.

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


# This function creates and returns a requests Session with the project's user agent header set,
# so all HTTP requests made by this script identify themselves consistently
def _session() -> requests.Session:
    http_session = requests.Session()
    http_session.headers.update({"User-Agent": USER_AGENT})
    return http_session


# This function selects the best image URL from a srcset attribute by preferring the 768px-wide
# version if available, otherwise picking the largest width found
# Falls back to the plain src if no srcset is provided or none of the entries can be parsed
def _pick_best_thumbnail(src: str, srcset: str | None) -> str:
    if not srcset:
        return src
    best_url = None
    largest_width = -1
    preferred_768_url = None
    for srcset_part in srcset.split(","):
        srcset_part = srcset_part.strip()
        srcset_match = re.match(r"(\S+)\s+(\d+)w$", srcset_part)
        if not srcset_match:
            continue
        url, width = srcset_match.group(1), int(srcset_match.group(2))
        if width == 768:
            preferred_768_url = url
        if width > largest_width:
            largest_width = width
            best_url = url
    if preferred_768_url:
        return preferred_768_url
    if best_url:
        return best_url
    return src


# This function searches the index page soup for the anchor tag matching a given bird slug,
# then walks up the DOM to find the nearest image and returns the best thumbnail URL
# along with the cleaned profile URL for that species
def _listing_thumbnail_and_profile(soup: BeautifulSoup, slug: str) -> tuple[str, str]:
    needle = f"/wildlife/birds/{slug}/"
    for anchor in soup.find_all("a", href=True):
        if needle not in anchor["href"]:
            continue
        current_element = anchor
        for _ in range(12):
            if current_element is None:
                break
            image_tag = current_element.find("img", src=True)
            if image_tag:
                thumbnail_url = _pick_best_thumbnail(image_tag["src"], image_tag.get("srcset"))
                href = anchor["href"]
                profile_url = href if href.endswith("/") else href + "/"
                return thumbnail_url, profile_url
            current_element = current_element.parent
    raise ValueError(f"No listing thumbnail + link for slug={slug!r}")


# This function finds the "Names" section on a species detail page and extracts the ʻŌlelo Hawaiʻi name,
# the common English name, and the raw scientific name line from the list items under that heading
def _parse_names_section(soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
    names_header = None
    for heading in soup.find_all("h4"):
        if heading.get_text(strip=True).lower() == "names":
            names_header = heading
            break
    if not names_header:
        return None, None, None
    names_list = names_header.find_next_sibling("ul")
    if not names_list:
        return None, None, None
    olelo = common = None
    scientific_line: str | None = None
    for list_item in names_list.find_all("li"):
        text = list_item.get_text(" ", strip=True)
        text_lower = text.lower()
        if text_lower.startswith("scientific:"):
            scientific_line = text
        elif "ōlelo" in text_lower or "olelo" in text_lower:
            if ":" in text:
                olelo = text.split(":", 1)[1].strip()
        elif text_lower.startswith("common:"):
            common = text.split(":", 1)[1].strip()
    return olelo, common, scientific_line


# This function builds the full display name for a species by combining the ʻŌlelo and common names
# from the Names section, falling back to the page's h2 heading or a generic label if neither is found
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


# This function returns the portion of a display name before the first comma,
# which is used as the shorter card title shown in the game UI
def _short_name_before_comma(full: str) -> str:
    full_text = (full or "").strip()
    if "," in full_text:
        return full_text.split(",", 1)[0].strip()
    return full_text


# This function builds the card display fields for a given species slug by combining the full
# display name, short card name, common name line, and scientific name line
# It handles the ʻIʻiwi slug as a special case, using a fixed common name and trimming
# the scientific name to just the first binomial before any comma
def _card_fields_for_slug(slug: str, detail_soup: BeautifulSoup) -> dict[str, str]:
    full_display = _display_name_from_detail(detail_soup)
    card_name = _short_name_before_comma(full_display)
    _, common, sci_raw = _parse_names_section(detail_soup)

    if slug == "iiwi":
        common_line = "Common: Scarlet Honeycreeper"
        sci_trimmed = ""
        if sci_raw:
            body = sci_raw.split(":", 1)[1].strip() if ":" in sci_raw else sci_raw
            sci_trimmed = body.split(",")[0].strip()
        scientific = (
            f"Scientific: {sci_trimmed}"
            if sci_trimmed
            else (sci_raw or "Scientific: (not found)")
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


# This function returns a hardcoded list of minimal card dicts for all six defender species,
# used as a fallback when the DLNR scrape fails so the game can still run without live data
def _fallback_cards() -> list[dict[str, Any]]:
    fallback_data = {
        "nene": {"display_name": "Nēnē", "card_name": "Nēnē", "scientific": "Scientific: (unavailable)"},
        "iiwi": {"display_name": "ʻIʻiwi", "card_name": "ʻIʻiwi", "scientific": "Scientific: (unavailable)"},
        "io": {"display_name": "ʻIo", "card_name": "ʻIo", "scientific": "Scientific: (unavailable)"},
        "pueo": {"display_name": "Pueo", "card_name": "Pueo", "scientific": "Scientific: (unavailable)"},
        "uau": {"display_name": "ʻUaʻu", "card_name": "ʻUaʻu", "scientific": "Scientific: (unavailable)"},
        "alala": {"display_name": "ʻAlala", "card_name": "ʻAlala", "scientific": "Scientific: (unavailable)"},
    }
    cards = []
    for slug in SLUGS_ORDERED:
        data = fallback_data.get(slug, {})
        cards.append({
            "key": KEY_BY_SLUG[slug],
            "display_name": data.get("display_name", slug),
            "card_name": data.get("card_name", slug),
            "common_line": "",
            "scientific": data.get("scientific", ""),
            "profile_url": "",
            "image_url": "",
        })
    return cards


# This function fetches the DLNR birds index page and then each species detail page in order,
# scraping the thumbnail image, profile URL, and card fields for all six defender species
# and returning them as a list of card dicts
# If any part of the scrape fails it catches the exception, prints a warning, and returns
# the hardcoded fallback cards instead so the game can still load
def fetch_home_species_cards(timeout: int = 45) -> list[dict[str, Any]]:
    try:
        http_session = _session()
        index_response = http_session.get(BIRDS_INDEX_URL, timeout=timeout)
        index_response.raise_for_status()
        index_soup = BeautifulSoup(index_response.text, "lxml")

        cards: list[dict[str, Any]] = []
        for slug in SLUGS_ORDERED:
            image_url, profile_url = _listing_thumbnail_and_profile(index_soup, slug)

            detail_response = http_session.get(profile_url, timeout=timeout)
            detail_response.raise_for_status()
            detail_soup = BeautifulSoup(detail_response.text, "lxml")
            fields = _card_fields_for_slug(slug, detail_soup)

            cards.append(
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
        return cards
    except (requests.RequestException, requests.Timeout, Exception) as e:
        print(f"⚠ Warning: Failed to fetch DLNR bird data: {e}")
        print("  Using fallback data. Bird images and external links will not be available.")
        return _fallback_cards()


_home_species_cache: list[dict[str, Any]] | None = None


# This function returns the cached list of home species cards, fetching and caching them on the
# first call or when refresh=True is passed
# If the fetch fails it stores and returns the fallback cards instead so subsequent calls
# don't keep retrying a broken network request
def get_home_species_cards(refresh: bool = False) -> list[dict[str, Any]]:
    global _home_species_cache
    if _home_species_cache is None or refresh:
        try:
            _home_species_cache = fetch_home_species_cards()
        except Exception as e:
            print(f"✗ Error in get_home_species_cards: {e}")
            _home_species_cache = _fallback_cards()
    return _home_species_cache


# Native roster keys in defenders.json match DLNR URL slug (e.g. iiwi, not 'I'iwi).
DEFENDER_NATIVE_NAMES_ORDERED: list[str] = list(SLUGS_ORDERED)


# This function builds and returns a dict mapping each defender slug to its display metadata
# by pulling from the cached species cards, used by the game templates to show card names,
# images, profile links, and scientific names for each defender
# If the card fetch fails it catches the exception and returns a minimal fallback dict
# with just the slug title-cased so the game can still render without live data
def get_dlnr_meta_by_native_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
    try:
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
    except Exception as e:
        print(f"✗ Error in get_dlnr_meta_by_native_name: {e}")
        # Return minimal fallback data
        return {
            slug: {
                "display_name": slug.title(),
                "common_line": "",
                "image_url": "",
                "profile_url": "",
                "scientific": "",
            }
            for slug in SLUGS_ORDERED
        }