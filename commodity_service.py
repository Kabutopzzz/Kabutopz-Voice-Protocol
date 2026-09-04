"""Live, read-only commodity lookups from UEX."""

from dataclasses import dataclass
import html
import json
import re
import urllib.parse
import urllib.request


UEX_COMMODITY_NAMES_URL = "https://uexcorp.space/resources/json_get_names/type/commodities/"
UEX_COMMODITY_BASE_URL = "https://uexcorp.space/commodities/info/name/{slug}/"


@dataclass(frozen=True)
class CommoditySearchResult:
    name: str
    source_url: str
    selling: list[tuple[str, str, str]]
    buying: list[tuple[str, str, str]]
    matches: list[str]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _request(url: str, data: dict[str, str] | None = None) -> str:
    encoded = urllib.parse.urlencode(data).encode("utf-8") if data else None
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"User-Agent": "KabutopzVoiceProtocol/1.2", "Accept": "text/html, application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _locations(content: str) -> list[tuple[str, str, str]]:
    rows = re.findall(
        r'<tr[^>]*class="[^"]*row-location[^"]*"[^>]*>(.*?)</tr>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    locations = []
    for row in rows:
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 11:
            continue
        values = []
        for attributes, body in cells:
            match = re.search(r'data-value="([^"]*)"', attributes, flags=re.IGNORECASE)
            values.append(html.unescape(match.group(1)).strip() if match else _text(body))
        location, price = values[0], values[10]
        if location and price:
            locations.append((location, price, " / ".join(part for part in (values[2], values[1]) if part)))
    return locations


def suggest_commodities(query: str, limit: int = 10) -> list[str]:
    """Return UEX commodity-name suggestions for a partial search string."""
    response = json.loads(_request(UEX_COMMODITY_NAMES_URL, {"search": query}))
    return list(response.get("data", []))[:limit]


def search_commodity(query: str) -> CommoditySearchResult:
    """Fetch all UEX offer and demand terminals for a commodity name."""
    matches = suggest_commodities(query)
    if not matches:
        raise ValueError(f'UEX found no commodity matching "{query}".')
    name = next((item for item in matches if item.lower() == query.lower()), matches[0])
    source_url = UEX_COMMODITY_BASE_URL.format(slug=_slug(name))
    return CommoditySearchResult(
        name=name,
        source_url=source_url,
        selling=_locations(_request(source_url + "tab/locations_selling/")),
        buying=_locations(_request(source_url + "tab/locations_buying/")),
        matches=matches,
    )
