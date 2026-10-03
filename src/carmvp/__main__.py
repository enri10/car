"""Command-line interface for carmvp.

Run with ``python -m carmvp <command>``. See README.md for exact commands.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .core import (
    DEMO_HTML,
    DEMO_JSON,
    Listing,
    ScoreResult,
    evaluate_listings,
    parse_html_listings,
    parse_json_listings,
)


def _read_input(path: Optional[str]) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _print_ranked(results: List[ScoreResult]) -> None:
    for rank, result in enumerate(results, start=1):
        print(f"#{rank} {result.explain()}")
        print()


def cmd_demo(args: argparse.Namespace) -> int:
    listings: List[Listing] = []
    listings.extend(parse_json_listings(DEMO_JSON))
    listings.extend(parse_html_listings(DEMO_HTML))
    results = evaluate_listings(listings)
    _print_ranked(results)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        text = _read_input(args.file)
    except OSError as exc:
        print(f"Could not read input: {exc}", file=sys.stderr)
        return 1

    try:
        if args.format == "json":
            listings = parse_json_listings(text)
        else:
            listings = parse_html_listings(text)
    except ValueError as exc:
        print(f"Could not parse {args.format} input: {exc}", file=sys.stderr)
        return 1

    if not listings:
        print("No listings found in input.", file=sys.stderr)
        return 1
    results = evaluate_listings(listings)
    _print_ranked(results)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m carmvp",
        description="Parse, normalize, and transparently score car listings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser(
        "demo", help="Run the built-in demo data (JSON + HTML) through parsing and scoring."
    )
    demo_parser.set_defaults(func=cmd_demo)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Parse and score listings from a file (or stdin)."
    )
    evaluate_parser.add_argument(
        "--format",
        choices=("json", "html"),
        required=True,
        help="Input format of the listings file.",
    )
    evaluate_parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to the input file. Omit or use '-' to read from stdin.",
    )
    evaluate_parser.set_defaults(func=cmd_evaluate)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
