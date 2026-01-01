#!/usr/bin/env python3
"""
inventory_products_sensor.py

Reads inventory.json and outputs:

{
  "count": <int>,
  "products": [ ...flat list of products... ],
  "catalog": {
    "chemicals": { ... },
    "fertiliser": { ... },
    "seed": { ... }
  }
}

Used by HA command_line sensor `sensor.inventory_products`.
"""

import json
import sys
from pathlib import Path

INVENTORY_PATH = Path("/config/RRAPL/JSON Files/inventory.json")


def load_inventory():
    if not INVENTORY_PATH.exists():
        return {
            "chemicals": {},
            "fertiliser": {},
            "seed": {},
            "transactions": [],
        }
    try:
        with INVENTORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {
            "chemicals": {},
            "fertiliser": {},
            "seed": {},
            "transactions": [],
        }

    data.setdefault("chemicals", {})
    data.setdefault("fertiliser", {})
    data.setdefault("seed", {})
    return data


def main():
    data = load_inventory()

    catalog = {
        "chemicals": data.get("chemicals", {}),
        "fertiliser": data.get("fertiliser", {}),
        "seed": data.get("seed", {}),
    }

    products = []
    for cat_key, cat_data in catalog.items():
        for pid, p in cat_data.items():
            item = dict(p)  # shallow copy
            item.setdefault("id", pid)

            if cat_key == "fertiliser":
                nice_cat = "Fertiliser"
            elif cat_key == "seed":
                nice_cat = "Seed"
            else:
                nice_cat = "Chemical"

            # ensure nice category label exists
            item["category"] = item.get("category") or nice_cat

            products.append(item)

    out = {
        "count": len(products),
        "products": products,
        "catalog": catalog,
    }
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
