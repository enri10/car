# car

`carmvp` is a small, dependency-free Python MVP for parsing car listings
(JSON, or a simplified car.gr-like HTML structure), normalizing them into a
common `Listing` shape, and scoring/ranking them with a fully transparent,
explainable score breakdown. No network access or scraping is involved —
everything runs on local input files or the built-in demo data.

## Requirements

- Python 3.9+
- No third-party dependencies.

## Setup

From the repo root:

```
pip install -e .
```

(This is optional — the package also runs directly from `src/` without
installing, as shown below.)

## Run the demo

Using the installed console script:

```
carmvp demo
```

Or without installing, from the repo root:

```
python -m carmvp demo --help
```

```
PYTHONPATH=src python -m carmvp demo
```

On Windows PowerShell:

```
$env:PYTHONPATH="src"; python -m carmvp demo
```

This parses the built-in demo JSON and demo HTML listings, scores all of
them relative to each other, and prints a ranked list with each score's
breakdown (age, mileage, price, fuel/transmission), e.g.:

```
#1 Toyota Prius Hybrid: 83.9/100
  - age: 14.5/25 (7 year(s) old)
  - mileage: 9.5/25 (62.000 km)
  - price: 29.9/35 (16900 EUR vs reference 13066 EUR)
  - fuel_and_transmission: 13.0/15 (fuel=Hybrid, transmission=Automatic)
```

## Evaluate your own listings

```
python -m carmvp evaluate --format json path/to/listings.json
python -m carmvp evaluate --format html path/to/listings.html
```

Or read from stdin:

```
cat path/to/listings.json | python -m carmvp evaluate --format json
```

### JSON input format

A JSON array of objects. Field names are flexible (aliases are accepted):

```json
[
  {
    "title": "Toyota Corolla 1.6",
    "price": "12.500 €",
    "year": 2016,
    "mileage": "98.000 km",
    "fuel": "Petrol",
    "transmission": "Manual",
    "location": "Athens",
    "url": "https://example.test/listing/1"
  }
]
```

A single object, or `{"listings": [...]}`, is also accepted.

### HTML input format

A simplified, car.gr-like classifieds structure using `data-field`
attributes (see `src/carmvp/core.py::DEMO_HTML` for a full example):

```html
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
```

This is a small structural analogue for demos/tests, not a scraper for the
live car.gr site.

## Scoring model

Each listing is scored out of 100, split into four independently-explained
components:

- **Age** (25 pts): newer cars score higher.
- **Mileage** (25 pts): lower mileage scores higher.
- **Price** (35 pts): cheaper relative to the batch's average price (or a
  fixed reference price when scoring a single listing) scores higher.
- **Fuel/transmission** (15 pts): a small bonus for fuel efficiency
  (electric > hybrid > diesel/petrol) and automatic transmission.

Every point awarded comes with a plain-text reason, so the final ranking is
always explainable — call `ScoreResult.explain()` or just run the CLI.

## Run the tests

From the repo root:

```
python -m unittest discover -s tests -t .
```

Or with `pytest` (if installed):

```
pytest
```
