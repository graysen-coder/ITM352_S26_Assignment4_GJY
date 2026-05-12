"""
Defender card metadata from live DLNR Native Birds pages (runtime web scrape).

Uses ``requests`` to fetch the index at BIRDS_INDEX_URL and each species
profile, then ``BeautifulSoup`` with the ``lxml`` parser to read thumbnails,
the Names section (ōlelo / common / scientific), and profile links. Used by
Flask for game/compendium/battle display names and images, plus compendium ``facts``
lines (State Listed + Species Information sentences) from the same profile pages.

Results are cached after the first successful fetch (see get_home_species_cards).
If the network fails or the site HTML changes, the module falls back to
hardcoded display strings in _fallback_cards() (no live scrape — no images or
profile URLs).

defenders.json native ``name`` keys match DLNR URL slugs in SLUGS_ORDERED.
"""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

BIRDS_INDEX_URL = "https://dlnr.hawaii.gov/wildlife/birds/"
USER_AGENT = "Mozilla/5.0 ITM352 educational (+course project)"

# Bird order on DLNR index page — same order as ``name`` in data/defenders.json.
SLUGS_ORDERED = ["nene", "iiwi", "io", "pueo", "uau", "alala"]

# Short label stored on each card row (matches how defenders are keyed in the app).
KEY_BY_SLUG: dict[str, str] = {
    "nene": "nene",
    "iiwi": "'I'iwi",
    "io": "'Io",
    "pueo": "pueo",
    "uau": "'Ua'u",
    "alala": "'Alala",
}


def _session() -> requests.Session:
    """Create a reusable web client and tell DLNR we are a small educational project (not a blank bot)."""
    http_session = requests.Session()
    http_session.headers.update({"User-Agent": USER_AGENT})
    return http_session


def _pick_best_thumbnail(src: str, srcset: str | None) -> str:
    """Pick the sharpest image URL from an HTML ``srcset`` list (or fall back to ``src``)."""
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


def _listing_thumbnail_and_profile(soup: BeautifulSoup, slug: str) -> tuple[str, str]:
    """From the birds index page, find the small photo URL and full profile link for one slug."""
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


def _parse_names_section(soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
    """Read the bird's ``Names`` block: Hawaiian (ōlelo), English common name, and scientific line."""
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


def _display_name_from_detail(soup: BeautifulSoup) -> str:
    """Build the long title shown on cards (Hawaiian + common, or page heading as backup)."""
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
    """Short card title: text before the first comma, or the whole string if there is no comma."""
    full_text = (full or "").strip()
    if "," in full_text:
        return full_text.split(",", 1)[0].strip()
    return full_text


def _card_fields_for_slug(slug: str, detail_soup: BeautifulSoup) -> dict[str, str]:
    """
    Turn one profile page into display strings: full name, short name, common line,
    and scientific line. The ʻIʻiwi row uses a hand-tuned common name and shorter science text.
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


# --- Compendium only: read "Conservation Status" + "Species Information" from each bird's DLNR page ---

# DLNR pages often append image credits ("PC: Name, Org") in Species Information; omit from compendium bullets.
_TRAILING_PC_CREDIT = re.compile(r"\s+PC\s*:.*$", re.I)
_TRAILING_PC_CREDIT_PAREN = re.compile(r"\s*\(\s*PC\s*:.*$", re.I)


def _is_standalone_photo_credit(text: str) -> bool:
    """True when the whole line is only a picture-credit caption (starts with ``PC:``)."""
    t = (text or "").strip()
    return bool(t) and bool(re.match(r"^PC\s*:", t, re.I))


def _strip_trailing_photo_credit(text: str) -> str:
    """Remove trailing `` PC: …`` or `` (PC: …)`` from a sentence scraped with the narrative."""
    s = (text or "").strip()
    s = _TRAILING_PC_CREDIT.sub("", s).strip()
    s = _TRAILING_PC_CREDIT_PAREN.sub("", s).strip()
    return s


def _h4_by_heading_text(root: BeautifulSoup, title: str):
    """
    Bird profiles use ``<h4>Conservation Status</h4>`` style headings. This scans
    all h4 tags and returns the one whose visible text matches ``title`` (ignores
    capital letters). Returns None if that section does not exist on this page.
    """
    want = title.strip().lower()
    for h in root.find_all("h4"):
        if h.get_text(" ", strip=True).lower() == want:
            return h
    return None


def _extract_state_listed_conservation_line(root: BeautifulSoup) -> str | None:
    """
    Pull the single bullet that starts with State Listed (i.e. endangered / threatened).
    I opted to not use Federal status because this is more kama'aina focused.
    """
    h = _h4_by_heading_text(root, "Conservation Status")
    if not h:
        return None
    ul = None
    for sib in h.find_next_siblings():
        if sib.name == "h4":
            break
        if sib.name == "ul":
            ul = sib
            break
    if not ul:
        return None
    for li in ul.find_all("li", recursive=False):
        t = li.get_text(" ", strip=True)
        if "state listed" in t.lower():
            return t
    return None


def _species_information_blob_after_h4(root: BeautifulSoup) -> str:
    """
    Get the "Species Information" text.
    """
    h = _h4_by_heading_text(root, "Species Information")
    if not h:
        return ""
    parts: list[str] = []
    for sib in h.find_next_siblings():
        if sib.name == "h4":
            break
        if sib.name == "p":
            t = sib.get_text(" ", strip=True)
            if t and not _is_standalone_photo_credit(t):
                parts.append(t)
        elif sib.name in ("div", "section", "article"):
            # Sometimes paragraphs sit inside a wrapper div instead of being direct siblings of the h4.
            for p in sib.find_all("p", recursive=False):
                t = p.get_text(" ", strip=True)
                if t and not _is_standalone_photo_credit(t):
                    parts.append(t)
    return " ".join(parts)


def _first_n_sentences(blob: str, n: int) -> list[str]:
    """
    Scraping only the first few sentences from the "Species Information" text.
    """
    blob = re.sub(r"\s+", " ", (blob or "").strip())
    if not blob:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", blob)
    out: list[str] = []
    for c in chunks:
        c = _strip_trailing_photo_credit(c)
        if len(c) < 12:
            continue
        if _is_standalone_photo_credit(c):
            continue
        out.append(c)
        if len(out) >= n:
            break
    return out[:n]


def _compendium_facts_from_profile_soup(detail_soup: BeautifulSoup) -> list[str]:
    """
    Build the bullet list shown on the Species Compendium for one native bird.

    The HTML template adds a separate "Find out more here" hyperlink to the DLNR page.
    """
    # Main article body; if the site layout changes, fall back to searching the whole page.
    root = detail_soup.find("div", class_="primary-content") or detail_soup
    out: list[str] = []
    state_line = _extract_state_listed_conservation_line(root)
    if state_line:
        out.append(state_line)
    blob = _species_information_blob_after_h4(root)
    out.extend(_first_n_sentences(blob, 3))
    return out


def _fallback_cards() -> list[dict[str, Any]]:
    """When DLNR is unreachable, return safe built-in names (no photos, no off-site links)."""
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
            "compendium_facts": [],
        })
    return cards


def fetch_home_species_cards(timeout: int = 45) -> list[dict[str, Any]]:
    """
    Scrape six bird cards: key, display_name, card_name, common_line,
    scientific, profile_url, image_url.

    On any request or parse failure, returns _fallback_cards() instead of
    raising (offline-safe behavior for the app).
    """
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
            # Extra text for /compendium only (same page we already downloaded — no second request).
            compendium_facts = _compendium_facts_from_profile_soup(detail_soup)

            cards.append(
                {
                    "key": KEY_BY_SLUG[slug],
                    "display_name": fields["display_name"],
                    "card_name": fields["card_name"],
                    "common_line": fields["common_line"],
                    "scientific": fields["scientific"],
                    "profile_url": profile_url,
                    "image_url": image_url,
                    "compendium_facts": compendium_facts,
                }
            )
        return cards
    except (requests.RequestException, requests.Timeout, Exception) as e:
        print(f"⚠ Warning: Failed to fetch DLNR bird data: {e}")
        print("  Using fallback data. Bird images and external links will not be available.")
        return _fallback_cards()


_home_species_cache: list[dict[str, Any]] | None = None


def get_home_species_cards(refresh: bool = False) -> list[dict[str, Any]]:
    """
    Return cached card rows from fetch_home_species_cards(), or re-scrape when
    refresh=True. First failure in a process stores fallback rows in the cache.
    """
    global _home_species_cache
    if _home_species_cache is None or refresh:
        try:
            _home_species_cache = fetch_home_species_cards()
        except Exception as e:
            print(f"✗ Error in get_home_species_cards: {e}")
            _home_species_cache = _fallback_cards()
    return _home_species_cache


# Same bird list as SLUGS_ORDERED — imported by app.py as the defender roster order.
DEFENDER_NATIVE_NAMES_ORDERED: list[str] = list(SLUGS_ORDERED)


def get_dlnr_meta_by_native_name(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """
    Map defenders.json ``name`` (slug) -> display_name, common_line, scientific,
    image_url, profile_url for templates.

    Data comes from the same live scrape as get_home_species_cards; on error,
    returns minimal per-slug placeholders (titles only, empty URLs).
    """
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


def get_compendium_defender_facts_by_slug(refresh: bool = False) -> dict[str, list[str]]:
    """
    For each bird slug (nene, iiwi, …), return the fact lines used on the Compendium.

    Reads from the in-memory scrape cache (see ``compendium_facts`` on each card).
    If that list is empty — offline mode or the website layout changed — the Flask
    route should show the old ``facts`` list from defenders.json instead.
    """
    cards = get_home_species_cards(refresh=refresh)
    return {slug: list(c.get("compendium_facts") or []) for slug, c in zip(SLUGS_ORDERED, cards)}
