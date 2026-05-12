"""
Fetch https://dlnr.hawaii.gov/hisc/info/invasive-species-profiles/ and build
archive/data/invaders_list.json — Vertebrates + Invertebrates only (no Plants / Pathogens / Aquatic).

Also writes data/invaders_set_alpha.json at the repo root (active invaders + DLNR-style card fields, no thumbnails).

Run from repo root:  python archive/scripts/build_invaders_set_1.py
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
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FULL_SET_PATH = _REPO_ROOT / "archive" / "data" / "invaders_list.json"
ALPHA_SET_PATH = _REPO_ROOT / "data" / "invaders_set_alpha.json"

# Keep gameplay to 6 invaders for now (miconia replaced by brown-tree-snake).
ACTIVE_INVADER_NAMES = [
    "coqui-frog",
    "coconut-rhinoceros-beetle",
    "brown-tree-snake",
    "little-fire-ant-lfa",
    "naio-thrips",
    "mongoose-urva-auropunctata",
]

CRB_DESC_OVERRIDE = [
    "Adult: 2” length, black, with a horn / Larva: Up to 3” white, “C-shaped” body",
    "Adult CRB are nocturnal and can fly up to two miles if looking for a food source. Female Beetles lay 50-140 eggs in their lifetime (4-9 months)",
    "The Coconut Rhinoceros Beetle is native to Africa, China, Myanmar/India, and Southeast Asia",
    "First found in Hawaii in 2013 at the Joint Base Pearl Harbor-Hickam",
    "In 2023 multiple populations were discovered on Kauai",
    "Siting’s also occurred on Maui and Hawaii islands, but established populations have not been confirmed",
    "They do not bite, but CRBResponse advises they should be handled with care as they may carry disease because they live in dirt and mulch",
]

CRB_IMPACT_OVERRIDE = [
    "CRB jeopardizes the economy, the entire ecosystem, agriculture, and food security (Citation – Maui County)",
    "To feed, CRB bite and bore into emerging palm fronds creating holes in the top of the tree",
    "CRB can kill palms and other trees if they burrow and eat below the bark",
    "CRB prefer to feed on coconut, royal, date, and fan palms (including Pitchardia), but if these trees are unavailable CRB will feed on Hala, Taro, Banana, Pineapple, and Sugarcane",
    "Adult CRB feed on tree sap but do not typically stay in trees very long. Larva will feed on nearly any moist, rotting or composting organic matter from fallen logs, tree stumps, green waste, grass clippings, manure, and sawdust piles",
    "On Hawaiʻi Island, these invasive beetles pose a serious threat to five endemic species of loulu palms (Pritchardia beccariana, P. gordonii, P. lanigera, P. schattaueri, and P. maideniana), with three of these species already designated as endangered or critically imperiled",
    "CRB damage cultural staples like Hala and Taro which impacts Native Hawaiian cultural practices. Protecting these plants is critical for preserving local heritage and maintaining a healthy, balanced ecosystem and local economy (Maui County)",
]

INVADER_IMAGE_URLS = {
    "mongoose-urva-auropunctata": "https://www.olaproperties.com/wp-content/uploads/2021/10/MONGOOSE-IN-HAWAII-scaled.jpg",
    "naio-thrips": "https://dlnr.hawaii.gov/hisc/files/2016/05/myoporum_04.jpg",
    "coconut-rhinoceros-beetle": "https://dlnr.hawaii.gov/hisc/files/2024/03/crb-response-pic-1.jpg",
    "coqui-frog": "https://www.kauaiisc.org/wp-content/uploads/Closeup-of-male-coqui.jpg",
    "little-fire-ant-lfa": "https://dlnr.hawaii.gov/hisc/files/2024/06/IMG_2728-1.jpg",
    "brown-tree-snake": "https://www.biisc.org/wp-content/uploads/brown-tree-snake_ccPavel-Kirillov.jpeg",
}

SKIP_SUBSECTION_TITLES = frozenset(
    {
        "rodents",
        "snakes",
        "ungulates",
        "fruit flies",
    }
)


def _session() -> requests.Session:
    http_session = requests.Session()
    http_session.headers.update({"User-Agent": USER_AGENT})
    return http_session


def _game_stats(seed: str) -> tuple[int, int]:
    digest_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
    health = 48 + (digest_bytes[0] % 52)
    attack = 22 + (digest_bytes[1] % 38)
    return health, attack


def _slugify(label: str) -> str:
    slug_text = label.lower().replace("ʻ", "").replace("'", "").replace("`", "")
    slug_text = re.sub(r"[^a-z0-9]+", "-", slug_text)
    return slug_text.strip("-") or "unknown"


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
    normalized_url = urljoin(base, href.strip())
    return normalized_url.split("#")[0]


def _split_common_scientific(raw: str) -> tuple[str, str | None]:
    cleaned_text = re.sub(r"\s+", " ", (raw or "").strip())
    if "(" not in cleaned_text or ")" not in cleaned_text:
        return cleaned_text, None
    left_paren_index = cleaned_text.find("(")
    right_paren_index = cleaned_text.rfind(")")
    if right_paren_index <= left_paren_index:
        return cleaned_text, None
    common = cleaned_text[:left_paren_index].strip()
    scientific = cleaned_text[left_paren_index + 1 : right_paren_index].strip()
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

    entries: list[dict[str, Any]] = []
    for tr in rows[idx_v + 1 : idx_i] + rows[idx_i + 1 : idx_p]:
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        name_raw, reg_raw, prev_raw = _row_texts(tr)
        if not name_raw:
            continue
        if name_raw.lower() in SKIP_SUBSECTION_TITLES:
            continue

        href = _first_hisc_link(cells[0])
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

        entries.append(
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

    return entries


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
    """
    Build an active invader entry:
    - gameplay keys from _to_game_subset_entry
    - card metadata used in templates/result pages
    """
    base = _to_game_subset_entry(entry)
    common = entry.get("common_name") or entry["name"]
    scientific = entry.get("scientific_name")
    if scientific:
        title_line = f"{common} ({scientific})"
    else:
        title_line = str(common)
    return {
        **base,
        "display_name": common,
        "title_line": title_line,
        "common_line": f"Common: {common}",
        "scientific": (f"Scientific: {scientific}" if scientific else None),
        "profile_url": entry.get("profile_url"),
        "description_points": [],
        "impact_points": [],
        "image_url": INVADER_IMAGE_URLS.get(entry.get("name")),
    }


def _clean_bullet_text(text: str) -> str:
    """Normalize whitespace/punctuation artifacts in scraped bullet text."""
    t = re.sub(r"\s+", " ", text or "").strip()
    # Trim spacing artifacts from scraped HTML.
    t = re.sub(r"\s+\)", ")", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = t.replace("“", "\"").replace("”", "\"")
    return t.rstrip(":").strip()


def _is_heading_fragment(text: str) -> bool:
    """Heuristic to skip heading-like fragments from bullet outputs."""
    t = _clean_bullet_text(text)
    if not t:
        return True
    if t.lower() in {"management actions", "tab"}:
        return True
    # Short title-like fragments without sentence punctuation are usually headings.
    if len(t.split()) <= 3 and not re.search(r"[.!?]$", t):
        return True
    return False


def _split_into_sentences(points: list[str]) -> list[str]:
    """Split paragraph-like bullets into sentence bullets (used only when needed)."""
    out: list[str] = []
    for p in points:
        if not p:
            continue
        protected = p.replace("U.S.", "U__S__")
        # Split only when next segment starts like a new sentence.
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z“\"'])", protected)
        for part in parts:
            s = _clean_bullet_text(part.replace("U__S__", "U.S."))
            if s and not _is_heading_fragment(s):
                out.append(s)
    return out


def _filter_impact_distribution_leak(points: list[str]) -> list[str]:
    """Drop likely distribution/history lines from impact bullet lists."""
    leak_markers = (
        "native to",
        "first noticed",
        "has now spread",
        "were also found",
        "transported to new areas",
        "preventing the spread",
        "please report all sightings",
    )
    out: list[str] = []
    for p in points:
        low = p.lower()
        marker_hits = sum(1 for m in leak_markers if m in low)
        if marker_hits >= 1 and "impact" not in low and "damage" not in low:
            continue
        out.append(p)
    return out


def _is_marker(text: str, marker: str) -> bool:
    return _clean_bullet_text(text).upper().startswith(marker.upper())


def _extract_section_points(primary, start_marker: str, stop_markers: tuple[str, ...]) -> list[str]:
    """Extract bullet/paragraph points between section markers in primary-content."""
    elems = [el for el in primary.find_all(recursive=False) if getattr(el, "name", None)]
    start_idx = -1
    for i, el in enumerate(elems):
        if _is_marker(el.get_text(" ", strip=True), start_marker):
            start_idx = i
            break
    if start_idx < 0:
        return []

    out: list[str] = []
    for el in elems[start_idx + 1 :]:
        txt = _clean_bullet_text(el.get_text(" ", strip=True))
        if not txt:
            continue
        if any(_is_marker(txt, m) for m in stop_markers):
            break
        if el.name in ("ul", "ol"):
            for li in el.find_all("li"):
                li_text = _clean_bullet_text(li.get_text(" ", strip=True))
                if li_text:
                    out.append(li_text)
        elif el.name == "p" and txt and not txt.isupper():
            out.append(txt)

    deduped: list[str] = []
    seen = set()
    for p in out:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    deduped = [p for p in deduped if not _is_heading_fragment(p)]
    return deduped


def _extract_tab_points(primary, tab_title: str) -> list[str]:
    """
    Extract points from shortcode tab panes such as:
    <div class="su-tabs-pane" data-title="DESCRIPTION">...</div>
    """
    pane = primary.find(
        "div",
        attrs={"data-title": re.compile(rf"^{re.escape(tab_title)}$", re.IGNORECASE)},
    )
    if not pane:
        return []

    text = pane.get_text("\n", strip=True).replace("\xa0", " ")
    # CRB tab panes often embed many "o ..." bullets in one long line.
    text = re.sub(r"\s+o\s+", "\n o ", text)
    lines = [_clean_bullet_text(x) for x in re.split(r"[\n\r]+", text) if _clean_bullet_text(x)]
    out: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^[o•\-\u2022]+\s*", "", line).strip()
        if cleaned:
            out.append(cleaned)

    merged: list[str] = []
    for item in out:
        t = item.strip()
        # Merge obvious fragments produced by inline links/split tags.
        if merged:
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", t):
                merged[-1] = f"{merged[-1]} {t}".strip()
                continue
            if t in {")", "(", "TAB"}:
                merged[-1] = f"{merged[-1]} {t}".strip()
                continue
            if merged[-1].endswith("("):
                merged[-1] = f"{merged[-1]}{t}".strip()
                continue
        merged.append(t)

    deduped: list[str] = []
    seen = set()
    for p in merged:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    deduped = [p for p in deduped if not _is_heading_fragment(p)]
    return deduped


def _fetch_profile_points(
    sess: requests.Session, url: str | None, slug: str | None = None
) -> tuple[list[str], list[str]]:
    """Scrape description/impact bullets from an invader profile page."""
    if not url:
        return [], []
    r = sess.get(url, timeout=45)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    primary = soup.find("div", class_="primary-content")
    if not primary:
        return [], []

    description_points = _extract_section_points(
        primary,
        start_marker="DESCRIPTION",
        stop_markers=("IMPACTS", "DISTRIBUTION/HISTORY", "WHAT YOU CAN DO"),
    )
    impact_points = _extract_section_points(
        primary,
        start_marker="IMPACTS",
        stop_markers=("DISTRIBUTION/HISTORY", "WHAT YOU CAN DO", "REPORTS ON", "FOR MORE INFORMATION"),
    )
    # Fallback for tabbed pages (CRB profile)
    if not description_points:
        description_points = _extract_tab_points(primary, "DESCRIPTION")
    if not impact_points:
        impact_points = _extract_tab_points(primary, "IMPACTS")
    # Keep source bullet formatting for most species.
    # Naio-thrips source is jumbled paragraph text, so sentence-splitting improves readability.
    if slug == "naio-thrips":
        description_points = _split_into_sentences(description_points)
        impact_points = _split_into_sentences(impact_points)
    impact_points = _filter_impact_distribution_leak(impact_points)
    return description_points, impact_points


def main() -> None:
    out_path = FULL_SET_PATH
    alpha_out_path = ALPHA_SET_PATH

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

    alpha_entries = []
    for n in ACTIVE_INVADER_NAMES:
        alpha = _to_alpha_entry(by_name[n])
        desc_pts, impact_pts = _fetch_profile_points(sess, alpha.get("profile_url"), slug=n)
        if n == "coconut-rhinoceros-beetle":
            desc_pts = list(CRB_DESC_OVERRIDE)
            impact_pts = list(CRB_IMPACT_OVERRIDE)
        alpha["description_points"] = desc_pts
        alpha["impact_points"] = impact_pts
        alpha_entries.append(alpha)
    with alpha_out_path.open("w", encoding="utf-8") as f:
        json.dump(alpha_entries, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(entries)} invaders to {out_path}")
    print(f"Wrote {len(alpha_entries)} active invaders to {alpha_out_path}")


if __name__ == "__main__":
    main()
