"""Core logic for carmvp: parsing, normalizing, and transparently scoring car listings.

This module is dependency-free (stdlib only) and does no network access. It can
parse two input formats:

  * JSON: a list of objects with flexible/aliased keys (see ``_FIELD_ALIASES``).
  * HTML: a small, car.gr-like classifieds markup used for demos/tests. It is a
    simplified structural analogue of a listing card (title/price/year/mileage/
    fuel/transmission/location/url as tagged fields) -- not a scraper for the
    live car.gr site.

Both formats normalize into the same :class:`Listing` dataclass, which can then
be scored with :func:`score_listing` / :func:`evaluate_listings`. Scoring is
"transparent": every point awarded comes with a human-readable reason, so the
final number is always explainable.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import date
from statistics import mean
from typing import Any, Iterable, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Normalized data model
# ---------------------------------------------------------------------------


@dataclass
class Listing:
    """A normalized car listing, regardless of its original source format."""

    title: str
    price_eur: Optional[float] = None
    year: Optional[int] = None
    mileage_km: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    source: str = "unknown"


# ---------------------------------------------------------------------------
# Value normalization helpers
# ---------------------------------------------------------------------------


def _parse_float(value: Any) -> Optional[float]:
    """Parse numbers that may come as int/float or as formatted strings.

    Handles things like "12.500 €", "12,500", "€ 12500", 12500.0, "12500".
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Keep digits, dot, comma, minus; drop currency symbols/units/words.
    cleaned = re.sub(r"[^0-9.,-]", "", text)
    if not cleaned:
        return None
    # Heuristic: if both '.' and ',' are present, treat '.' as thousands sep
    # (European style, e.g. "12.500,50") and ',' as decimal separator.
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # Single comma: ambiguous between thousands and decimal. Treat as
        # thousands separator if it looks like "12,500" (3 digits after).
        if re.search(r",\d{3}(\D|$)", cleaned):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
        # "12.500" style thousands separator (no decimal part).
        cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(value: Any) -> Optional[int]:
    parsed = _parse_float(value)
    return int(parsed) if parsed is not None else None


def _first_present(data: dict, keys: Sequence[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


_FIELD_ALIASES = {
    "title": ("title", "name", "heading"),
    "price_eur": ("price_eur", "price", "amount"),
    "year": ("year", "manufacture_year", "model_year"),
    "mileage_km": ("mileage_km", "mileage", "odometer_km", "odometer"),
    "fuel_type": ("fuel_type", "fuel"),
    "transmission": ("transmission", "gearbox"),
    "location": ("location", "city", "area"),
    "url": ("url", "link", "href"),
}


def _listing_from_dict(data: dict, source: str) -> Listing:
    title = _first_present(data, _FIELD_ALIASES["title"]) or "Untitled listing"
    return Listing(
        title=str(title).strip(),
        price_eur=_parse_float(_first_present(data, _FIELD_ALIASES["price_eur"])),
        year=_parse_int(_first_present(data, _FIELD_ALIASES["year"])),
        mileage_km=_parse_int(_first_present(data, _FIELD_ALIASES["mileage_km"])),
        fuel_type=_normalize_text(_first_present(data, _FIELD_ALIASES["fuel_type"])),
        transmission=_normalize_text(
            _first_present(data, _FIELD_ALIASES["transmission"])
        ),
        location=_normalize_text(_first_present(data, _FIELD_ALIASES["location"])),
        url=_normalize_text(_first_present(data, _FIELD_ALIASES["url"])),
        source=source,
    )


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def parse_json_listings(text: str) -> List[Listing]:
    """Parse a JSON string containing a list of listing objects.

    Also accepts a single JSON object (treated as a one-item list), or a
    top-level object with a "listings" key holding the list.
    """
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("listings", [data])
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of listing objects")
    return [_listing_from_dict(item, source="json") for item in data if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# HTML parsing (simplified car.gr-like structure)
# ---------------------------------------------------------------------------

_LISTING_BLOCK_RE = re.compile(
    r'<article[^>]*class="[^"]*\blisting\b[^"]*"[^>]*>(.*?)</article>',
    re.IGNORECASE | re.DOTALL,
)
_FIELD_RE = re.compile(
    r'<[^>]+data-field="(?P<field>[a-z_]+)"[^>]*(?:href="(?P<href>[^"]*)")?[^>]*>'
    r"(?P<text>.*?)</[^>]+>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


def parse_html_listings(html: str) -> List[Listing]:
    """Parse a simplified, car.gr-like HTML listing page.

    Expected structure (see ``DEMO_HTML`` for a full example)::

        <article class="listing">
          <span data-field="title">Toyota Corolla 1.6</span>
          <span data-field="price">12.500 &#8364;</span>
          <span data-field="year">2016</span>
          <span data-field="mileage">98.000 km</span>
          <span data-field="fuel">Petrol</span>
          <span data-field="transmission">Manual</span>
          <span data-field="location">Athens</span>
          <a data-field="url" href="https://example.test/listing/1">details</a>
        </article>

    This is a small structural analogue used for demos and tests; it is not a
    scraper for the live car.gr website and performs no network access.
    """
    listings = []
    for block_match in _LISTING_BLOCK_RE.finditer(html):
        block = block_match.group(1)
        raw: dict = {}
        for field_match in _FIELD_RE.finditer(block):
            field_name = field_match.group("field").lower()
            href = field_match.group("href")
            if field_name == "url":
                href_match = re.search(r'href=["\']([^"\']+)["\']', field_match.group(0), re.I)
                href = href_match.group(1) if href_match else href
            value = href if (field_name == "url" and href) else _strip_tags(
                field_match.group("text")
            )
            raw[field_name] = value
        if raw:
            listings.append(_listing_from_dict(raw, source="html"))
    return listings


# ---------------------------------------------------------------------------
# Transparent scoring
# ---------------------------------------------------------------------------


@dataclass
class ScoreComponent:
    """One line item of a score breakdown: always explains its own points."""

    name: str
    points: float
    max_points: float
    reason: str


@dataclass
class ScoreResult:
    listing: Listing
    components: List[ScoreComponent] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(c.points for c in self.components), 1)

    @property
    def max_total(self) -> float:
        return sum(c.max_points for c in self.components)

    def explain(self) -> str:
        lines = [f"{self.listing.title}: {self.total}/{self.max_total}"]
        for c in self.components:
            lines.append(f"  - {c.name}: {c.points:.1f}/{c.max_points} ({c.reason})")
        return "\n".join(lines)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


DEFAULT_PRICE_REFERENCE_EUR = 15_000.0


def score_listing(
    listing: Listing,
    *,
    market_price: Optional[float] = None,
    current_year: Optional[int] = None,
) -> ScoreResult:
    """Score a listing out of 100, with a fully transparent breakdown.

    The score has four independently-explained components:

      * Age (25 pts): newer cars score higher.
      * Mileage (25 pts): lower mileage scores higher.
      * Price (35 pts): cheaper relative to ``market_price`` (or the default
        reference price, if not given) scores higher.
      * Fuel/transmission (15 pts): small bonus for fuel economy/efficiency
        (electric > hybrid > diesel/petrol) and automatic transmission.

    ``market_price`` lets callers score a listing relative to a batch average
    (see :func:`evaluate_listings`); without it, a fixed reference price is
    used so a single listing can still be scored on its own.
    """
    year = current_year or date.today().year
    components: List[ScoreComponent] = []

    # Age
    if listing.year is None:
        components.append(ScoreComponent("age", 0.0, 25.0, "year unknown"))
    else:
        age = max(0, year - listing.year)
        points = _clamp(25.0 - age * 1.5, 0.0, 25.0)
        components.append(
            ScoreComponent("age", points, 25.0, f"{age} year(s) old")
        )

    # Mileage
    if listing.mileage_km is None:
        components.append(ScoreComponent("mileage", 0.0, 25.0, "mileage unknown"))
    else:
        points = _clamp(25.0 - listing.mileage_km / 4000.0, 0.0, 25.0)
        components.append(
            ScoreComponent(
                "mileage", points, 25.0, f"{listing.mileage_km:,} km".replace(",", ".")
            )
        )

    # Price
    reference = market_price if market_price and market_price > 0 else DEFAULT_PRICE_REFERENCE_EUR
    if not listing.price_eur or listing.price_eur <= 0:
        components.append(ScoreComponent("price", 0.0, 35.0, "price unknown"))
    else:
        ratio = reference / listing.price_eur
        points = _clamp(35.0 * ratio, 0.0, 35.0)
        components.append(
            ScoreComponent(
                "price",
                points,
                35.0,
                f"{listing.price_eur:,.0f} EUR vs reference {reference:,.0f} EUR".replace(
                    ",", "."
                ),
            )
        )

    # Fuel / transmission bonus
    fuel_points, fuel_reason = _fuel_bonus(listing.fuel_type)
    trans_points, trans_reason = _transmission_bonus(listing.transmission)
    components.append(
        ScoreComponent(
            "fuel_and_transmission",
            fuel_points + trans_points,
            15.0,
            f"fuel={fuel_reason}, transmission={trans_reason}",
        )
    )

    return ScoreResult(listing=listing, components=components)


_FUEL_BONUS = {
    "electric": 10.0,
    "hybrid": 8.0,
    "diesel": 5.0,
    "petrol": 5.0,
    "gasoline": 5.0,
}

_TRANSMISSION_BONUS = {
    "automatic": 5.0,
    "manual": 3.0,
}


def _fuel_bonus(fuel_type: Optional[str]) -> tuple:
    key = (fuel_type or "").strip().lower()
    points = _FUEL_BONUS.get(key, 0.0)
    return points, (fuel_type or "unknown")


def _transmission_bonus(transmission: Optional[str]) -> tuple:
    key = (transmission or "").strip().lower()
    points = _TRANSMISSION_BONUS.get(key, 0.0)
    return points, (transmission or "unknown")


def evaluate_listings(listings: Iterable[Listing]) -> List[ScoreResult]:
    """Score a batch of listings relative to each other and rank them.

    The market price used for the "price" component of each score is the
    mean of all known prices in the batch, so each listing is judged against
    its peers. Returns results sorted best-first (highest total score).
    """
    listings = list(listings)
    known_prices = [l.price_eur for l in listings if l.price_eur and l.price_eur > 0]
    market_price = mean(known_prices) if known_prices else None
    results = [score_listing(l, market_price=market_price) for l in listings]
    return sorted(results, key=lambda r: r.total, reverse=True)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

DEMO_JSON = json.dumps(
    [
        {
            "title": "Toyota Corolla 1.6",
            "price": "12.500 €",
            "year": 2016,
            "mileage": "98.000 km",
            "fuel": "Petrol",
            "transmission": "Manual",
            "location": "Athens",
            "url": "https://example.test/listing/1",
        },
        {
            "title": "VW Golf 1.6 TDI",
            "price": "9.800 €",
            "year": 2014,
            "mileage": "165.000 km",
            "fuel": "Diesel",
            "transmission": "Manual",
            "location": "Thessaloniki",
            "url": "https://example.test/listing/2",
        },
        {
            "title": "Toyota Prius Hybrid",
            "price": "16.900 €",
            "year": 2019,
            "mileage": "62.000 km",
            "fuel": "Hybrid",
            "transmission": "Automatic",
            "location": "Patra",
            "url": "https://example.test/listing/3",
        },
    ],
    ensure_ascii=False,
    indent=2,
)


DEMO_HTML = """
<html>
<body>
<article class="listing">
  <span data-field="title">Toyota Corolla 1.6</span>
  <span data-field="price">12.500 &#8364;</span>
  <span data-field="year">2016</span>
  <span data-field="mileage">98.000 km</span>
  <span data-field="fuel">Petrol</span>
  <span data-field="transmission">Manual</span>
  <span data-field="location">Athens</span>
  <a data-field="url" href="https://example.test/listing/1">details</a>
</article>
<article class="listing">
  <span data-field="title">VW Golf 1.6 TDI</span>
  <span data-field="price">9.800 &#8364;</span>
  <span data-field="year">2014</span>
  <span data-field="mileage">165.000 km</span>
  <span data-field="fuel">Diesel</span>
  <span data-field="transmission">Manual</span>
  <span data-field="location">Thessaloniki</span>
  <a data-field="url" href="https://example.test/listing/2">details</a>
</article>
<article class="listing">
  <span data-field="title">Toyota Prius Hybrid</span>
  <span data-field="price">16.900 &#8364;</span>
  <span data-field="year">2019</span>
  <span data-field="mileage">62.000 km</span>
  <span data-field="fuel">Hybrid</span>
  <span data-field="transmission">Automatic</span>
  <span data-field="location">Patra</span>
  <a data-field="url" href="https://example.test/listing/3">details</a>
</article>
</body>
</html>
"""
