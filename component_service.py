"""Live component and ship-weapon lookup from the Star Citizen Wiki."""

from dataclasses import dataclass
import html
import json
import re
import urllib.parse
import urllib.request

WIKI_BASE_URL = "https://starcitizen.tools"
WIKI_API_URL = f"{WIKI_BASE_URL}/api.php"


@dataclass(frozen=True)
class ComponentResult:
    name: str
    source_url: str
    locations: list[tuple[str, str, str]]
    specifications: list[tuple[str, str]]


def _request(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "KabutopzVoiceProtocol/1.4"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


_SPOKEN_ROMAN_NUMERALS = {
    "one": "I", "two": "II", "three": "III", "four": "IV", "five": "V", "six": "VI",
    "seven": "VII", "eight": "VIII", "nine": "IX", "ten": "X", "eleven": "XI", "twelve": "XII",
    "thirteen": "XIII", "fourteen": "XIV", "fifteen": "XV", "sixteen": "XVI", "seventeen": "XVII",
    "eighteen": "XVIII", "nineteen": "XIX", "twenty": "XX",
}


def _normalize_spoken_roman_numerals(query: str) -> str:
    """Make spoken names such as ``Deadbolt five`` find ``Deadbolt V``."""
    return re.sub(r"\b(" + "|".join(_SPOKEN_ROMAN_NUMERALS) + r")\b",
                  lambda match: _SPOKEN_ROMAN_NUMERALS[match.group(1).lower()], query, flags=re.IGNORECASE)


def _wiki_search(query: str, limit: int = 10) -> list[tuple[str, str]]:
    query = _normalize_spoken_roman_numerals(query.strip())
    if not query:
        return []
    params = urllib.parse.urlencode({"action": "opensearch", "search": query, "limit": limit, "namespace": 0, "format": "json"})
    data = json.loads(_request(f"{WIKI_API_URL}?{params}"))
    matches = [(str(title), str(url)) for title, url in zip(data[1] if len(data) > 1 else [], data[3] if len(data) > 3 else [])]
    if matches:
        return matches

    # OpenSearch occasionally omits partial series names (for example, Greatsword).
    # Fall back to the Wiki's full-text endpoint while preserving a Wiki page URL.
    params = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json"})
    search_data = json.loads(_request(f"{WIKI_API_URL}?{params}"))
    return [
        (str(item["title"]), f"{WIKI_BASE_URL}/{urllib.parse.quote(str(item['title']).replace(' ', '_'))}")
        for item in search_data.get("query", {}).get("search", [])
    ]


def _ranked_wiki_matches(query: str, limit: int = 10, ship_weapon: bool = False) -> list[tuple[str, str]]:
    normalized = _normalize_spoken_roman_numerals(query).lower()
    matches = _wiki_search(query, limit * 2)
    matches.sort(key=lambda item: (
        ship_weapon and not any(word in item[0].lower() for word in ("cannon", "gatling", "repeater", "scattergun", "gun", "missile", "torpedo", "weapon")),
        item[0].lower() != normalized,
        normalized not in item[0].lower(),
        item[0].lower().find(normalized) if normalized in item[0].lower() else len(item[0]),
        len(item[0]),
    ))
    return matches[:limit]


def suggest_components(query: str, limit: int = 10) -> list[str]:
    return [name for name, _ in _ranked_wiki_matches(query, limit)]


def suggest_ship_weapons(query: str, limit: int = 10) -> list[str]:
    return [name for name, _ in _ranked_wiki_matches(query, limit, ship_weapon=True)]


def _locations(content: str) -> list[tuple[str, str, str]]:
    """Read the Wiki acquisition table: System, shop Location, and Buy price."""
    for raw_table in re.findall(r"<table[^>]*>(.*?)</table>", content, flags=re.IGNORECASE | re.DOTALL):
        rows = []
        for raw_row in re.findall(r"<tr[^>]*>(.*?)</tr>", raw_table, flags=re.IGNORECASE | re.DOTALL):
            cells = [_clean(cell) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", raw_row, flags=re.IGNORECASE | re.DOTALL)]
            if cells:
                rows.append(cells)
        if not rows:
            continue
        header = [cell.lower() for cell in rows[0]]
        if not {"system", "location", "buy"} <= set(header):
            continue
        system, location, price = header.index("system"), header.index("location"), header.index("buy")
        return [(row[system], row[location], row[price]) for row in rows[1:] if len(row) > max(system, location, price)]
    return []


def _specifications(content: str) -> list[tuple[str, str]]:
    values = []
    pattern = (r'<dt[^>]*class="[^"]*t-infobox-item-label[^"]*"[^>]*>(.*?)</dt>\s*'
               r'<dd[^>]*class="[^"]*t-infobox-item-(?:value|content)[^"]*"[^>]*>(.*?)</dd>')
    for label, value in re.findall(pattern, content, flags=re.IGNORECASE | re.DOTALL):
        label, value = _clean(label), _clean(value)
        if label and value:
            values.append((label, value))
    return values[:40]


def _search_wiki_item(query: str, kind: str, ship_weapon: bool = False) -> ComponentResult:
    matches = _ranked_wiki_matches(query, ship_weapon=ship_weapon)
    if not matches:
        raise ValueError(f'Star Citizen Wiki found no {kind} matching "{query}".')
    name, source_url = matches[0]
    content = _request(source_url)
    return ComponentResult(name, source_url, _locations(content), _specifications(content))


def search_component(query: str) -> ComponentResult:
    return _search_wiki_item(query, "component")


def search_ship_weapon(query: str) -> ComponentResult:
    return _search_wiki_item(query, "ship weapon", ship_weapon=True)
