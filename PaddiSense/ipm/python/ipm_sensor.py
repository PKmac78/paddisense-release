#!/usr/bin/env python3
"""
IPM Sensor - Read-only data output for Home Assistant
PaddiSense Farm Management System

This script reads the inventory and outputs JSON for the HA command_line sensor.
It provides:
  - Product list with stock totals
  - Unique product names for selection dropdowns
  - Location lists per product (for multi-location products)
  - Category/subcategory relationships

Output format:
{
  "total_products": 25,
  "products": { "PRODUCT_ID": { ... } },
  "product_names": ["Glyphosate 450", "Urea", ...],
  "product_locations": { "PRODUCT_ID": ["Silo 1", "Silo 3"], ... },
  "categories": ["Chemical", "Fertiliser", "Seed", "Lubricant"],
  "category_subcategories": { "Chemical": [...], ... },
  "locations": ["Chem Shed", "Seed Shed", ...]
}

Data source: /config/local_data/ipm/inventory.json
"""

import json
from pathlib import Path

DATA_FILE = Path("/config/local_data/ipm/inventory.json")

# Category to subcategory mapping (must match ipm_backend.py)
CATEGORY_SUBCATEGORIES = {
    "Chemical": [
        "Adjuvant",
        "Fungicide",
        "Herbicide",
        "Insecticide",
        "Pesticide",
        "Rodenticide",
        "Seed Treatment",
    ],
    "Fertiliser": [
        "Nitrogen",
        "Phosphorus",
        "Potassium",
        "NPK Blend",
        "Trace Elements",
        "Organic",
    ],
    "Seed": [
        "Wheat",
        "Barley",
        "Canola",
        "Rice",
        "Oats",
        "Pasture",
        "Other",
    ],
    "Lubricant": [
        "Engine Oil",
        "Hydraulic Oil",
        "Grease",
        "Gear Oil",
        "Transmission Fluid",
        "Coolant",
    ],
}

# All storage locations
ALL_LOCATIONS = [
    "Chem Shed",
    "Seed Shed",
    "Oil Shed",
    "Silo 1",
    "Silo 2",
    "Silo 3",
    "Silo 4",
    "Silo 5",
    "Silo 6",
    "Silo 7",
    "Silo 8",
    "Silo 9",
    "Silo 10",
    "Silo 11",
    "Silo 12",
    "Silo 13",
]


def main():
    # Default empty output
    empty_output = {
        "total_products": 0,
        "products": {},
        "product_names": [],
        "product_locations": {},
        "categories": list(CATEGORY_SUBCATEGORIES.keys()),
        "category_subcategories": CATEGORY_SUBCATEGORIES,
        "locations": ALL_LOCATIONS,
    }

    if not DATA_FILE.exists():
        print(json.dumps(empty_output))
        return

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        print(json.dumps(empty_output))
        return

    products = data.get("products", {})

    # Build output structures
    product_names = []
    product_locations = {}

    for product_id, product in products.items():
        name = product.get("name", product_id)
        product_names.append(name)

        # Get locations where this product has stock
        stock_by_location = product.get("stock_by_location", {})
        locations_with_stock = [
            loc for loc, qty in stock_by_location.items()
            if qty and float(qty) > 0
        ]

        # Calculate total stock
        total_stock = sum(
            float(qty) for qty in stock_by_location.values()
            if qty
        )
        product["total_stock"] = round(total_stock, 2)

        # Store locations for this product
        if locations_with_stock:
            product_locations[product_id] = sorted(locations_with_stock)

    output = {
        "total_products": len(products),
        "products": products,
        "product_names": sorted(product_names),
        "product_locations": product_locations,
        "categories": list(CATEGORY_SUBCATEGORIES.keys()),
        "category_subcategories": CATEGORY_SUBCATEGORIES,
        "locations": ALL_LOCATIONS,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
