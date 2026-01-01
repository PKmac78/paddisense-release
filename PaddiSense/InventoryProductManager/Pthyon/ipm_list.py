#!/usr/bin/env python3
"""
Inventory Product Manager backend (ipm_).

Supports:
  - read: emit JSON for HA sensor
  - update: stock movement (add/use)
  - upsert: create/update product with location-aware ID
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "JSON" / "ipm_inventory_products.json"

CATEGORY_PREFIX = {
    "chemical": "CHEM",
    "chemicals": "CHEM",
    "seed": "SEED",
    "seeds": "SEED",
    "fertiliser": "FERT",
    "fertilizer": "FERT",
    "fertilisers": "FERT",
    "lubricant": "LUBE",
    "lubricants": "LUBE",
}


def load_data() -> Dict:
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"products": [], "transactions": []}


def save_data(data: Dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def slugify(text: str) -> str:
    out = []
    for ch in (text or ""):
        if ch.isalnum():
            out.append(ch.upper())
        elif ch in (" ", "-", "_"):
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "ITEM"


def normalize_category(cat: str) -> str:
    return (cat or "").strip().lower()


def generate_product_id(category: str, name: str, location: str, existing_ids: List[str]) -> str:
    prefix = CATEGORY_PREFIX.get(normalize_category(category), "IPM")
    base = f"{prefix}_{slugify(name)}"
    loc = slugify(location) if location else "LOC"
    date_part = datetime.now().strftime("%Y%m%d")
    candidate = f"{base}_{loc}_{date_part}"
    idx = 1
    pid = candidate
    while pid in existing_ids:
        idx += 1
        pid = f"{candidate}_{idx}"
    return pid


def find_product(data: Dict, product_id: str, name: str, location: str) -> Dict | None:
    name = (name or "").strip().lower()
    location = (location or "").strip().lower()
    for prod in data.get("products", []):
        if product_id and prod.get("id") == product_id:
            return prod
        if prod.get("name", "").strip().lower() == name and prod.get("location", "").strip().lower() == location:
            return prod
    return None


def add_transaction(data: Dict, *, product_id: str, name: str, category: str, location: str, action: str, qty: float, note: str):
    tx = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "id": product_id,
        "name": name,
        "category": category,
        "location": location,
        "action": action,
        "quantity": qty,
        "note": note or "",
    }
    data.setdefault("transactions", []).append(tx)


def handle_upsert(args: List[str]) -> int:
    if len(args) < 7:
        print("usage: ipm_inventory.py upsert <category> <subcategory> <location> <name> <active_constituent> <application_unit> <container_size> [note]", file=sys.stderr)
        return 1
    _, category, subcategory, location, name, active_constituent, application_unit, container_size, *rest = args
    note = rest[0] if rest else ""

    data = load_data()
    existing_ids = [p.get("id") for p in data.get("products", []) if p.get("id")]
    product = find_product(data, "", name, location)

    if product is None:
        product_id = generate_product_id(category, name, location, existing_ids)
        product = {"id": product_id}
        data.setdefault("products", []).append(product)
    else:
        product_id = product.get("id")

    product.update(
        {
            "id": product_id,
            "name": name,
            "category": category,
            "subcategory": subcategory,
            "location": location,
            "active_constituent": active_constituent,
            "application_unit": application_unit,
            "container_size": float(container_size) if container_size else 0.0,
            "stock_on_hand": float(product.get("stock_on_hand", 0.0)),
            "note": note,
        }
    )

    add_transaction(
        data,
        product_id=product_id,
        name=name,
        category=category,
        location=location,
        action="upsert",
        qty=0.0,
        note=note,
    )
    save_data(data)
    return 0


def handle_update(args: List[str]) -> int:
    if len(args) < 7:
        print("usage: ipm_inventory.py update <category> <subcategory> <location> <name> <action> <quantity> [note]", file=sys.stderr)
        return 1
    _, category, subcategory, location, name, action, quantity, *rest = args
    note = rest[0] if rest else ""
    qty = float(quantity)

    data = load_data()
    product = find_product(data, "", name, location)
    if product is None:
        existing_ids = [p.get("id") for p in data.get("products", []) if p.get("id")]
        product_id = generate_product_id(category, name, location, existing_ids)
        product = {
          "id": product_id,
          "name": name,
          "category": category,
          "subcategory": subcategory,
          "location": location,
          "active_constituent": "",
          "application_unit": "",
          "container_size": 0.0,
          "stock_on_hand": 0.0,
          "note": "",
        }
        data.setdefault("products", []).append(product)
    else:
        product_id = product.get("id")

    current = float(product.get("stock_on_hand", 0.0))
    action_flag = (action or "").lower()
    if action_flag == "use":
        new_stock = current - abs(qty)
        change = -abs(qty)
    else:
        new_stock = current + abs(qty)
        change = abs(qty)
    if new_stock < 0:
        new_stock = 0.0

    product["stock_on_hand"] = new_stock

    add_transaction(
        data,
        product_id=product_id,
        name=product.get("name", name),
        category=category,
        location=location,
        action=action_flag or "add",
        qty=change,
        note=note,
    )
    save_data(data)
    return 0


def handle_read() -> int:
    data = load_data()
    products = data.get("products", [])
    payload = {
        "total_products": len(products),
        "products": products,
        "source": str(DATA_PATH),
    }
    print(json.dumps(payload))
    return 0


def main(argv: List[str]) -> int:
    if len(argv) <= 1:
        return handle_read()
    cmd = argv[1]
    if cmd == "read":
        return handle_read()
    if cmd == "update":
        return handle_update(argv[1:])
    if cmd == "upsert":
        return handle_upsert(argv[1:])
    print("commands: read | update | upsert", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
