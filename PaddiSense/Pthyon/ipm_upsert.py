#!/usr/bin/env python3
"""
inventory_upsert_product.py

Add or edit a product in inventory.json, with full properties.

Args (from shell_command.inventory_upsert_product):

  1: mode              ("add" or "edit")
  2: category          ("Chemical", "Fertiliser", "Seed")
  3: id                (product id / slug, may be empty -> derived from name)
  4: name              (display name)
  5: product_unit      ("L", "kg", "t")
  6: container_size    (e.g. "20" -> 20.0)
  7: min_stock
  8: initial_stock
  9: storage_location
 10: subcategory       (Herbicide, Fungicide, etc.)
 11: chemical_group
 12: active_name
 13: active_conc
 14: active_unit       (g/L, g/kg, etc.)
 15: application_unit  (g/ha, L/ha, etc.)
"""

import json
import sys
from pathlib import Path
from datetime import datetime

INVENTORY_PATH = Path("/config/RRAPL/JSON Files/inventory.json")

CATEGORY_MAP = {
    "chemical": "chemicals",
    "chemicals": "chemicals",
    "fertiliser": "fertiliser",
    "fertilizer": "fertiliser",
    "fertilisers": "fertiliser",
    "seed": "seed",
    "seeds": "seed",
}


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
    data.setdefault("transactions", [])
    return data


def save_inventory(data):
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INVENTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)


def normalise_category(cat: str) -> str:
    key = (cat or "").strip().lower()
    return CATEGORY_MAP.get(key, "chemicals")


def slugify_id(product_id: str, name: str) -> str:
    """Turn arbitrary id/name into a clean slug e.g. 'Crucial 540' -> 'CRUCIAL_540'."""
    base = product_id.strip() if product_id else name.strip()
    cleaned = []
    for ch in base.upper():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in (" ", "-", "/"):
            cleaned.append("_")
        else:
            continue
    slug = "".join(cleaned)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "UNKNOWN_PRODUCT"


def parse_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


def add_transaction(data, *, category, product_id, product_name, action, qty, unit, note):
    tx = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "product_id": product_id,
        "product_name": product_name,
        "type": action,
        "qty": qty,
        "unit": unit,
        "note": note,
    }
    data.setdefault("transactions", []).append(tx)


def main(argv):
    if len(argv) < 16:
        print("ERROR: Expected 15 arguments", file=sys.stderr)
        return 1

    (
        _prog,
        mode,
        category,
        pid_raw,
        name,
        product_unit,
        container_size,
        min_stock,
        initial_stock,
        storage_location,
        subcategory,
        chemical_group,
        active_name,
        active_conc,
        active_unit,
        application_unit,
    ) = argv[:16]

    mode = (mode or "").strip().lower()
    cat_label = category
    cat_key = normalise_category(category)

    data = load_inventory()
    cat_dict = data.setdefault(cat_key, {})

    pid = slugify_id(pid_raw, name)
    container_size_f = parse_float(container_size, 0.0)
    min_stock_f = parse_float(min_stock, 0.0)
    initial_stock_f = parse_float(initial_stock, 0.0)
    active_conc_f = parse_float(active_conc, 0.0)

    existing = cat_dict.get(pid)

    # Build / update product
    if mode == "add":
        if existing is None:
            # New product
            product = {
                "id": pid,
                "name": name,
                "category": cat_label,
                "unit": product_unit,
                "default_pack_size": container_size_f,
                "container_size": container_size_f,
                "min_stock": min_stock_f,
                "stock_on_hand": initial_stock_f,
                "actives": [],
                "storage_location": storage_location,
                "subcategory": subcategory,
                "application_unit": application_unit,
                "chemical_group": chemical_group,
            }
            if active_name:
                product["actives"].append(
                    {
                        "name": active_name,
                        "concentration": active_conc_f,
                        "concentration_unit": active_unit,
                    }
                )
            cat_dict[pid] = product

            # Log initial stock as add_product transaction
            if initial_stock_f != 0:
                add_transaction(
                    data,
                    category=cat_label,
                    product_id=pid,
                    product_name=name,
                    action="add_product",
                    qty=initial_stock_f,
                    unit=product_unit,
                    note="Initial stock on product creation",
                )
        else:
            # "Add" on existing id -> treat as metadata update, keep stock_on_hand
            existing["name"] = name
            existing["category"] = cat_label
            existing["unit"] = product_unit
            existing["default_pack_size"] = container_size_f
            existing["container_size"] = container_size_f
            existing["min_stock"] = min_stock_f
            existing["storage_location"] = storage_location
            existing["subcategory"] = subcategory
            existing["application_unit"] = application_unit
            existing["chemical_group"] = chemical_group
            if active_name:
                existing["actives"] = [
                    {
                        "name": active_name,
                        "concentration": active_conc_f,
                        "concentration_unit": active_unit,
                    }
                ]

    elif mode == "edit":
        if existing is None:
            # Edit of unknown -> create with zero stock
            product = {
                "id": pid,
                "name": name,
                "category": cat_label,
                "unit": product_unit,
                "default_pack_size": container_size_f,
                "container_size": container_size_f,
                "min_stock": min_stock_f,
                "stock_on_hand": 0.0,
                "actives": [],
                "storage_location": storage_location,
                "subcategory": subcategory,
                "application_unit": application_unit,
                "chemical_group": chemical_group,
            }
            if active_name:
                product["actives"].append(
                    {
                        "name": active_name,
                        "concentration": active_conc_f,
                        "concentration_unit": active_unit,
                    }
                )
            cat_dict[pid] = product
        else:
            # Edit existing – do NOT change stock_on_hand here
            existing["name"] = name
            existing["category"] = cat_label
            existing["unit"] = product_unit
            existing["default_pack_size"] = container_size_f
            existing["container_size"] = container_size_f
            existing["min_stock"] = min_stock_f
            existing["storage_location"] = storage_location
            existing["subcategory"] = subcategory
            existing["application_unit"] = application_unit
            existing["chemical_group"] = chemical_group
            if active_name:
                existing["actives"] = [
                    {
                        "name": active_name,
                        "concentration": active_conc_f,
                        "concentration_unit": active_unit,
                    }
                ]
    else:
        print(f"ERROR: Unknown mode {mode!r}, expected 'add' or 'edit'", file=sys.stderr)
        return 1

    save_inventory(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
