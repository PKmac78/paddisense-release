#!/usr/bin/env python3
"""
inventory_read_products.py

Reads /config/RRAPL/JSON Files/inventory.json and prints a JSON object:

{
  "total_products": <int>,
  "products": [
    {
      "id": "...",
      "name": "...",
      "category": "...",
      "unit": "...",
      "stock_on_hand": 0.0,
      "default_pack_size": 0.0,
      "container_size": 0.0,
      "min_stock": 0.0,
      "storage_location": "...",
      "subcategory": "...",
      "chemical_group": "...",
      "application_unit": "...",
      "actives": [
        {
          "name": "...",
          "concentration": 0.0,
          "concentration_unit": "..."
        },
        ...
      ]
    },
    ...
  ]
}

This is what Home Assistant will expose as sensor.inventory_products.attributes.products
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
        # If file is corrupt, at least return empty structure
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


def product_from_dict(pid, p_dict, category_key):
    """Normalize a single product dict into the shape HA expects."""

    # Category label: try to keep the human-friendly label you stored
    category_label = p_dict.get("category") or category_key.title()

    def f(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    # Build actives list in standard form
    actives_in = p_dict.get("actives") or []
    actives_out = []

    # actives may be list of strings OR list of dicts
    for a in actives_in:
        if isinstance(a, dict):
            name = (a.get("name") or "").strip()
            if not name:
                continue
            actives_out.append(
                {
                    "name": name,
                    "concentration": f(a.get("concentration", 0.0)),
                    "concentration_unit": a.get("concentration_unit", "None / Unknown"),
                }
            )
        else:
            # assume string-like
            name = str(a).strip()
            if not name:
                continue
            actives_out.append(
                {
                    "name": name,
                    "concentration": 0.0,
                    "concentration_unit": "None / Unknown",
                }
            )

    # Use container_size if present; otherwise fall back to default_pack_size
    default_pack = p_dict.get("default_pack_size", 0.0)
    container_size = p_dict.get("container_size", default_pack)

    out = {
        "id": p_dict.get("id", pid),
        "name": p_dict.get("name", pid),
        "category": category_label,
        "unit": p_dict.get("unit", ""),
        "stock_on_hand": f(p_dict.get("stock_on_hand", 0.0)),
        "default_pack_size": f(default_pack),
        "container_size": f(container_size),
        "min_stock": f(p_dict.get("min_stock", 0.0)),
        "storage_location": p_dict.get("storage_location", ""),
        "subcategory": p_dict.get("subcategory", ""),
        "chemical_group": p_dict.get("chemical_group", "None / Unknown"),
        "application_unit": p_dict.get("application_unit", "L/ha"),
        "actives": actives_out,
    }
    return out


def main():
    data = load_inventory()

    products_flat = []

    # data keys: "chemicals", "fertiliser", "seed"
    for category_key in ("chemicals", "fertiliser", "seed"):
        cat_dict = data.get(category_key, {})
        if not isinstance(cat_dict, dict):
            continue

        for pid, p_dict in cat_dict.items():
            if not isinstance(p_dict, dict):
                continue
            products_flat.append(product_from_dict(pid, p_dict, category_key))

    result = {
        "total_products": len(products_flat),
        "products": products_flat,
    }

    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
