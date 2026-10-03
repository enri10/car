"""Normalization helpers for messy, bilingual (Greek/English) listing text.

car.gr-style listings mix Greek and English labels and use European-style
number formatting ("15.000" = fifteen thousand, not fifteen point zero).
These helpers turn free text into clean, typed values.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Optional

_CURRENT_YEAR = date.today().year

_FUEL_MAP = {
    "petrol": "petrol",
    "gasoline": "petrol",
    "gas": "petrol",
    "βενζινη": "petrol",
    "diesel": "diesel",
    "πετρελαιο": "diesel",
    "ντιζελ": "diesel",
    "hybrid": "hybrid",
    "υβριδικο": "hybrid",
    "υβριδο": "hybrid",
    "electric": "electric",
    "ηλεκτρικο": "electric",
    "lpg": "lpg",
    "υγραεριο": "lpg",
    "cng": "cng",
    "φυσικο αεριο": "cng",
}

_TRANSMISSION_MAP = {
    "automatic": "automatic",
    "auto": "automatic",
    "αυτοματο": "automatic",
    "αυτοματη": "automatic",
    "manual": "manual",
    "χειροκινητο": "manual",
    "χειροκινητη": "manual",
}


def _strip_accents_lower(text: str) -> str:
    """Lowercase and strip Greek accents so 'Βενζίνη' matches 'βενζινη'."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return no_accents.lower().strip()


def clean_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed or None


def parse_number(text: Optional[str]) -> Optional[float]:
    """Parse a number from mixed European/US formatted text.

    Handles "15.000" (-> 15000), "15,000" (-> 15000), "15.000,50"
    (-> 15000.50), "15,000.50" (-> 15000.50), and plain "15000.5".
    Returns None if no digits are present.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    match = re.search(r"-?\d[\d.,]*", text)
    if not match:
        return None
    raw = match.group(0)

    has_dot = "." in raw
    has_comma = "," in raw
    if has_dot and has_comma:
        decimal_sep = max(raw.rfind("."), raw.rfind(","))
        decimal_char = raw[decimal_sep]
        int_part = raw[:decimal_sep]
        frac_part = raw[decimal_sep + 1 :]
        int_part = int_part.replace("." if decimal_char == "," else ",", "")
        int_part = int_part.replace(decimal_char, "")
        cleaned = f"{int_part}.{frac_part}" if frac_part else int_part
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        groups = raw.split(sep)
        # A single separator followed by exactly 3 digits (and more than
        # one group) reads as a thousands separator, e.g. "15.000" or
        # "15,000". Anything else (e.g. "15.5", "1234,99") is a decimal.
        if len(groups) > 1 and all(len(g) == 3 for g in groups[1:]) and len(groups[0]) <= 3:
            cleaned = "".join(groups)
        else:
            cleaned = raw.replace(sep, ".", 1) if sep == "," else raw
    else:
        # In Greek listings a lone dot/comma followed by exactly three digits
        # is a thousands separator, not a decimal point.
        if (has_dot or has_comma) and len(raw.rsplit("." if has_dot else ",", 1)[-1]) == 3:
            cleaned = raw.replace(".", "").replace(",", "")
        else:
            cleaned = raw

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_price(text: Optional[str]) -> tuple[Optional[float], str]:
    """Extract (amount, currency) from text like '15.000 €' or 'EUR 15,000'."""
    if not text:
        return None, "EUR"
    currency = "EUR"
    if "$" in text or re.search(r"\busd\b", text, re.I):
        currency = "USD"
    elif "£" in text or re.search(r"\bgbp\b", text, re.I):
        currency = "GBP"
    amount = parse_number(text)
    return amount, currency


def parse_year(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"(19[5-9]\d|20[0-4]\d)", text)
    if not match:
        return None
    year = int(match.group(0))
    if 1950 <= year <= _CURRENT_YEAR + 1:
        return year
    return None


def parse_mileage(text: Optional[str]) -> Optional[int]:
    value = parse_number(text)
    if value is None:
        return None
    return int(round(value))


def parse_int(text: Optional[str]) -> Optional[int]:
    value = parse_number(text)
    if value is None:
        return None
    return int(round(value))


def normalize_fuel(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    key = _strip_accents_lower(text)
    for needle, canon in _FUEL_MAP.items():
        if needle in key:
            return canon
    return "other"


def normalize_transmission(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    key = _strip_accents_lower(text)
    for needle, canon in _TRANSMISSION_MAP.items():
        if needle in key:
            return canon
    return "other"
