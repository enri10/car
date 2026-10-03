import json
import unittest

from carmvp.core import (
    DEMO_HTML,
    DEMO_JSON,
    Listing,
    evaluate_listings,
    parse_html_listings,
    parse_json_listings,
    score_listing,
)


class ParseJsonTests(unittest.TestCase):
    def test_parses_demo_json(self):
        listings = parse_json_listings(DEMO_JSON)
        self.assertEqual(len(listings), 3)
        first = listings[0]
        self.assertEqual(first.title, "Toyota Corolla 1.6")
        self.assertEqual(first.price_eur, 12500.0)
        self.assertEqual(first.year, 2016)
        self.assertEqual(first.mileage_km, 98000)
        self.assertEqual(first.fuel_type, "Petrol")
        self.assertEqual(first.transmission, "Manual")
        self.assertEqual(first.location, "Athens")
        self.assertEqual(first.url, "https://example.test/listing/1")
        self.assertEqual(first.source, "json")

    def test_accepts_single_object(self):
        single = json.dumps({"title": "Solo car", "price": 5000})
        listings = parse_json_listings(single)
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].title, "Solo car")
        self.assertEqual(listings[0].price_eur, 5000.0)

    def test_accepts_wrapped_listings_key(self):
        wrapped = json.dumps({"listings": [{"title": "A"}, {"title": "B"}]})
        listings = parse_json_listings(wrapped)
        self.assertEqual([l.title for l in listings], ["A", "B"])

    def test_handles_key_aliases(self):
        text = json.dumps(
            [
                {
                    "name": "Aliased car",
                    "amount": "7.250,50",
                    "manufacture_year": 2018,
                    "odometer_km": 50000,
                    "gearbox": "Automatic",
                    "city": "Larissa",
                    "link": "https://example.test/x",
                }
            ]
        )
        listing = parse_json_listings(text)[0]
        self.assertEqual(listing.title, "Aliased car")
        self.assertAlmostEqual(listing.price_eur, 7250.50)
        self.assertEqual(listing.year, 2018)
        self.assertEqual(listing.mileage_km, 50000)
        self.assertEqual(listing.transmission, "Automatic")
        self.assertEqual(listing.location, "Larissa")

    def test_missing_fields_are_none(self):
        listing = parse_json_listings(json.dumps([{"title": "Bare"}]))[0]
        self.assertIsNone(listing.price_eur)
        self.assertIsNone(listing.year)
        self.assertIsNone(listing.mileage_km)
        self.assertIsNone(listing.fuel_type)

    def test_rejects_non_list_non_object(self):
        with self.assertRaises(ValueError):
            parse_json_listings(json.dumps("not a list"))


class ParseHtmlTests(unittest.TestCase):
    def test_parses_demo_html(self):
        listings = parse_html_listings(DEMO_HTML)
        self.assertEqual(len(listings), 3)
        first = listings[0]
        self.assertEqual(first.title, "Toyota Corolla 1.6")
        self.assertEqual(first.price_eur, 12500.0)
        self.assertEqual(first.year, 2016)
        self.assertEqual(first.mileage_km, 98000)
        self.assertEqual(first.fuel_type, "Petrol")
        self.assertEqual(first.transmission, "Manual")
        self.assertEqual(first.location, "Athens")
        self.assertEqual(first.url, "https://example.test/listing/1")
        self.assertEqual(first.source, "html")

    def test_empty_html_yields_no_listings(self):
        self.assertEqual(parse_html_listings("<html><body>nothing here</body></html>"), [])

    def test_single_article_block(self):
        html = """
        <article class="listing">
          <span data-field="title">Solo</span>
          <span data-field="price">1000</span>
        </article>
        """
        listings = parse_html_listings(html)
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].title, "Solo")
        self.assertEqual(listings[0].price_eur, 1000.0)


class ScoringTests(unittest.TestCase):
    def test_score_is_within_bounds(self):
        listing = Listing(title="X", price_eur=12000, year=2020, mileage_km=50000,
                           fuel_type="Petrol", transmission="Manual")
        result = score_listing(listing, current_year=2026)
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, result.max_total)
        self.assertEqual(result.max_total, 100.0)

    def test_newer_lower_mileage_cheaper_scores_higher(self):
        good = Listing(title="Good", price_eur=8000, year=2023, mileage_km=20000,
                        fuel_type="Hybrid", transmission="Automatic")
        bad = Listing(title="Bad", price_eur=20000, year=2008, mileage_km=250000,
                       fuel_type="Petrol", transmission="Manual")
        good_result = score_listing(good, current_year=2026)
        bad_result = score_listing(bad, current_year=2026)
        self.assertGreater(good_result.total, bad_result.total)

    def test_every_component_has_a_reason(self):
        listing = Listing(title="X")
        result = score_listing(listing, current_year=2026)
        for component in result.components:
            self.assertTrue(component.reason)

    def test_missing_fields_score_zero_for_their_component(self):
        listing = Listing(title="Unknown everything")
        result = score_listing(listing, current_year=2026)
        by_name = {c.name: c for c in result.components}
        self.assertEqual(by_name["age"].points, 0.0)
        self.assertEqual(by_name["mileage"].points, 0.0)
        self.assertEqual(by_name["price"].points, 0.0)

    def test_explain_contains_title_and_components(self):
        listing = Listing(title="Explain me", price_eur=10000, year=2020, mileage_km=10000)
        result = score_listing(listing, current_year=2026)
        text = result.explain()
        self.assertIn("Explain me", text)
        self.assertIn("age", text)
        self.assertIn("mileage", text)
        self.assertIn("price", text)


class EvaluateListingsTests(unittest.TestCase):
    def test_sorted_best_first(self):
        listings = parse_json_listings(DEMO_JSON)
        results = evaluate_listings(listings)
        totals = [r.total for r in results]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_handles_empty_list(self):
        self.assertEqual(evaluate_listings([]), [])

    def test_market_price_is_batch_average(self):
        listings = [
            Listing(title="A", price_eur=10000),
            Listing(title="B", price_eur=20000),
        ]
        results = evaluate_listings(listings)
        # market price = 15000, so A (below average) should score higher on price
        a_price = next(c for r in results for c in r.components
                        if r.listing.title == "A" and c.name == "price")
        b_price = next(c for r in results for c in r.components
                        if r.listing.title == "B" and c.name == "price")
        self.assertGreater(a_price.points, b_price.points)


if __name__ == "__main__":
    unittest.main()
