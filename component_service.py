"""Read-only component and item lookup from CStone Universal Item Finder."""

from dataclasses import dataclass
import html
import json
import re
import threading
import urllib.request

CATALOG_URL = "https://finder.cstone.space/GetSearch"
DETAIL_URL = "https://finder.cstone.space/Search/{item_id}"
_catalog = None
_catalog_lock = threading.Lock()


@dataclass(frozen=True)
class ComponentResult:
    name: str
    source_url: str
    locations: list[tuple[str, str, str]]
    specifications: list[tuple[str, str]]


def _request(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "KabutopzVoiceProtocol/1.2"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _catalog_items() -> list[dict]:
    global _catalog
    with _catalog_lock:
        if _catalog is None:
            _catalog = json.loads(_request(CATALOG_URL))
        return _catalog


def _ranked_matches(query: str, limit: int = 10) -> list[dict]:
    query = query.strip().lower()
    if not query:
        return []
    matches = []
    for item in _catalog_items():
        name = str(item.get("name", ""))
        lowered = name.lower()
        index = lowered.find(query)
        if index >= 0:
            matches.append((index, len(name), name.lower(), item))
    matches.sort(key=lambda value: value[:3])
    return [item for *_, item in matches[:limit]]


def suggest_components(query: str, limit: int = 10) -> list[str]:
    return [str(item["name"]) for item in _ranked_matches(query, limit)]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _locations(content: str) -> list[tuple[str, str, str]]:
    locations = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", content, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) != 3 or "/Location1/" not in cells[0]:
            continue
        locations.append((_clean(cells[0]), _clean(cells[1]), _clean(cells[2])))
    return locations


def _specifications(content: str) -> list[tuple[str, str]]:
    values = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", content, flags=re.IGNORECASE | re.DOTALL):
        cells = [_clean(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)]
        if len(cells) == 2 and all(cells) and cells[0].lower() not in {"location", "base price"}:
            values.append((cells[0], cells[1]))
    return values[:40]


def search_component(query: str) -> ComponentResult:
    matches = _ranked_matches(query, 10)
    if not matches:
        raise ValueError(f'CStone found no item matching "{query}".')
    item = next((entry for entry in matches if entry["name"].lower() == query.lower()), matches[0])
    source_url = DETAIL_URL.format(item_id=item["id"])
    content = _request(source_url)
    return ComponentResult(
        name=str(item["name"]), source_url=source_url,
        locations=_locations(content), specifications=_specifications(content),
    )
