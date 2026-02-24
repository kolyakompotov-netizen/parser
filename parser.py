#!/usr/bin/env python3
"""Product scraper with Excel export for WordPress imports.

Usage example:
python parser.py \
  --start-url "https://example.com/catalog" \
  --product-link-selector ".product-card a::attr(href)" \
  --title-selector "h1.product-title" \
  --price-selector ".price" \
  --description-selector ".description" \
  --image-selector ".gallery img::attr(src)" \
  --category-selector ".breadcrumbs a" \
  --sku-selector ".sku" \
  --output products.xlsx
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


@dataclass
class Product:
    name: str
    sku: str
    price: str
    description: str
    images: str
    categories: str
    source_url: str


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_selector(selector: str) -> tuple[str, str | None]:
    """Parse selector format 'css' or 'css::attr(name)'."""
    attr_match = re.search(r"::attr\(([^)]+)\)$", selector)
    if not attr_match:
        return selector.strip(), None
    css = selector[: attr_match.start()].strip()
    attr = attr_match.group(1).strip()
    return css, attr


def _extract_many(soup: BeautifulSoup, selector: str) -> list[str]:
    css, attr = _parse_selector(selector)
    nodes = soup.select(css)
    values: list[str] = []

    for node in nodes:
        if attr:
            if node.has_attr(attr):
                values.append(_normalize_text(str(node[attr])))
        else:
            values.append(_normalize_text(node.get_text(" ", strip=True)))

    return [v for v in values if v]


def _extract_one(soup: BeautifulSoup, selector: str) -> str:
    values = _extract_many(soup, selector)
    return values[0] if values else ""


def fetch(url: str, timeout: int = 20) -> str:
    response = requests.get(url, timeout=timeout, headers=HEADERS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def collect_product_links(start_url: str, product_link_selector: str) -> list[str]:
    html = fetch(start_url)
    soup = BeautifulSoup(html, "lxml")
    links = _extract_many(soup, product_link_selector)

    unique: dict[str, None] = {}
    for link in links:
        abs_link = urljoin(start_url, link)
        unique[abs_link] = None
    return list(unique.keys())


def parse_product(url: str, args: argparse.Namespace) -> Product:
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    image_values = [urljoin(url, val) for val in _extract_many(soup, args.image_selector)]
    category_values = _extract_many(soup, args.category_selector) if args.category_selector else []

    return Product(
        name=_extract_one(soup, args.title_selector),
        sku=_extract_one(soup, args.sku_selector) if args.sku_selector else "",
        price=_extract_one(soup, args.price_selector),
        description=_extract_one(soup, args.description_selector),
        images=", ".join(dict.fromkeys(image_values)),
        categories=" > ".join(category_values),
        source_url=url,
    )


def parse_all(products_urls: Iterable[str], args: argparse.Namespace) -> list[Product]:
    items: list[Product] = []
    for idx, url in enumerate(products_urls, start=1):
        try:
            item = parse_product(url, args)
            items.append(item)
            print(f"[{idx}] OK: {url}")
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}] FAIL: {url} -> {exc}", file=sys.stderr)
        time.sleep(args.delay)
    return items


def export_to_excel(items: list[Product], output_file: str) -> None:
    df = pd.DataFrame([asdict(item) for item in items])
    # Column names compatible with typical WP import mappings.
    rename_map = {
        "name": "post_title",
        "sku": "sku",
        "price": "regular_price",
        "description": "post_content",
        "images": "images",
        "categories": "tax:product_cat",
        "source_url": "meta:source_url",
    }
    df = df.rename(columns=rename_map)
    df.to_excel(output_file, index=False)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scrape product cards and export to XLSX for WordPress")
    p.add_argument("--start-url", required=True, help="Catalog/list URL containing product links")
    p.add_argument("--product-link-selector", required=True, help="CSS selector for product links (use ::attr(href))")
    p.add_argument("--title-selector", required=True, help="CSS selector for product title")
    p.add_argument("--price-selector", required=True, help="CSS selector for price")
    p.add_argument("--description-selector", required=True, help="CSS selector for description")
    p.add_argument("--image-selector", required=True, help="CSS selector for product images (use ::attr(src))")
    p.add_argument("--category-selector", default="", help="Optional CSS selector for categories")
    p.add_argument("--sku-selector", default="", help="Optional CSS selector for SKU")
    p.add_argument("--output", default="products.xlsx", help="Path to output xlsx")
    p.add_argument("--delay", type=float, default=0.25, help="Delay between product requests (seconds)")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print("Collecting product links...")
    product_urls = collect_product_links(args.start_url, args.product_link_selector)
    print(f"Found {len(product_urls)} product links")

    items = parse_all(product_urls, args)
    print(f"Parsed {len(items)} items")

    export_to_excel(items, args.output)
    print(f"Excel exported: {args.output}")


if __name__ == "__main__":
    main()
