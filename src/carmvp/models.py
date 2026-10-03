"""Normalized data model for a car listing."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# Fields that scoring/data-quality checks consider "important" to have.
CORE_FIELDS = (
    "price_eur",
    "year",
    "mileage_km",
    "fuel_type",
    "transmission",
)


@dataclass
class Listing:
    """A normalized car listing.

    All fields are optional because real-world inputs are frequently
    incomplete. ``extra`` keeps anything we parsed but don't have a
    dedicated field for, so no information is silently discarded.
    """

    title: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    price_eur: Optional[float] = None
    currency: str = "EUR"
    mileage_km: Optional[int] = None
    fuel_type: Optional[str] = None  # petrol/diesel/hybrid/electric/lpg/other
    transmission: Optional[str] = None  # manual/automatic/other
    engine_cc: Optional[int] = None
    power_hp: Optional[int] = None
    body_type: Optional[str] = None
    location: Optional[str] = None
    seller_type: Optional[str] = None  # private/dealer/unknown
    owners_count: Optional[int] = None
    first_registration: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    listing_id: Optional[str] = None
    vin: Optional[str] = None
    images_count: Optional[int] = None
    source_format: str = "unknown"  # html / json / jsonld / demo
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def missing_core_fields(self) -> list[str]:
        """Which of the fields most important for scoring are absent."""
        return [f for f in CORE_FIELDS if getattr(self, f) is None]
