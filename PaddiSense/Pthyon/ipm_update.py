#!/usr/bin/env python3
"""
inventory_update.py

Modes:

1) Update stock (default, called by shell_command.inventory_update):

   python3 inventory_update.py \
     --category "Chemical" \
     --product "MAGISTER" \
     --action "Use" \
     --quantity "5.0" \
     --note "Sprayed SW4_E"

   or sign-based:

   python3 inventory_update.py \
     --category "Chemical" \
     --product "MAGISTER" \
     --quantity "-5.0" \
     --note "Sprayed SW4_E"

2) Add new product (legacy, not used by HA anymore):

   python3 inventory_update.py add_product \
     "<category>" "<name>" "<unit>" "<pack_size>" "<min_stock>" "<initial_stock>" \
     "<active_1_name>" "<active_1_conc>" "<active_1_unit>" "<product_id>" \
     "[<storage_location>] [<subcategory>]"

3) Upsert product (NEW – used by shell_command.inventory_upsert_product):

   python3 inventory_update.py upsert_product \
     "<mode>" "<category>" "<id>" "<name>" "<product_unit>" "<container_size>" \
     "<min_stock>" "<initial_stock>" "<storage_location>" "<subcategory>" \
     "<chemical_group>" "<application_unit>" \
     "<a1_name>" "<a1_conc>" "<a1_unit>" \
     "<a2_name>" "<a2_conc>" "<a2_unit>" \
     "<a3_name>" "<a3_conc>" "<a3_unit>" \
     "<a4_name>" "<a4_conc>" "<a4_unit>" \
     "<a5_name>" "<a5_conc>" "<a5_unit>" \
     "<a6_name>" "<a6_conc>" "<a6_unit>"

JSON file: /config/RRAPL/JSON Files/inventory.json
"""

import argparse
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
        # If file is corrupt, start fresh but don't blow up
        return {
            "chemicals": {},
            "fertiliser": {},
            "seed": {},
            "transactions": [],
        }

    # Ensure all keys exist
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
    if product_id:
        base = product_id.strip()
    else:
        base = name.strip()

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


def parse_float(value, default=0.0):
    try:
        return float(value)
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
        "note": note or "",
    }
    data.setdefault("transactions", []).append(tx)


# -------------------------------------------------------------------
# Legacy add_product (still here for backward compatibility)
# -------------------------------------------------------------------
def mode_add_product(argv):
    """
    Positional args:
      0: add_product (already consumed)
      1: category
      2: name
      3: unit
      4: pack_size
      5: min_stock
      6: initial_stock
      7: active_1_name
      8: active_1_conc
      9: active_1_unit
      10: product_id
      11: storage_location (optional)
      12: subcategory (optional)
    """
    if len(argv) < 11:
        print("ERROR: Not enough arguments for add_product", file=sys.stderr)
        return 1

    _, category, name, unit, pack_size, min_stock, initial_stock, \
        active_name, active_conc, active_unit, product_id = argv[:11]

    storage_location = ""
    subcategory = ""
    if len(argv) >= 12:
        storage_location = argv[11]
    if len(argv) >= 13:
        subcategory = argv[12]

    cat_key = normalise_category(category)
    data = load_inventory()

    pid = slugify_id(product_id, name)
    pack_size_f = parse_float(pack_size, 0.0)
    min_stock_f = parse_float(min_stock, 0.0)
    initial_stock_f = parse_float(initial_stock, 0.0)
    active_conc_f = parse_float(active_conc, 0.0)

    cat_dict = data.setdefault(cat_key, {})
    product = {
        "id": pid,
        "name": name,
        "category": category,
        "unit": unit,
        "default_pack_size": pack_size_f,
        "container_size": pack_size_f,
        "min_stock": min_stock_f,
        "stock_on_hand": initial_stock_f,
        "actives": [],
        "storage_location": storage_location,
        "subcategory": subcategory,
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

    add_transaction(
        data,
        category=category,
        product_id=pid,
        product_name=name,
        action="add_product",
        qty=initial_stock_f,
        unit=unit,
        note=(
            f"Initial stock on product creation"
            f" (location={storage_location}, subcategory={subcategory})"
        ),
    )

    save_inventory(data)
    return 0


# -------------------------------------------------------------------
# NEW: upsert_product – used by HA UI for Add + Edit
# -------------------------------------------------------------------
def mode_upsert_product(argv):
    """
    argv layout (starting from index 0 = 'upsert_product'):

      1: mode               ('add' or 'edit')
      2: category
      3: id
      4: name
      5: product_unit
      6: container_size
      7: min_stock
      8: initial_stock
      9: storage_location
      10: subcategory
      11: chemical_group
      12: application_unit
      13–15: active1: name, conc, unit
      16–18: active2: name, conc, unit
      19–21: active3: name, conc, unit
      22–24: active4: name, conc, unit
      25–27: active5: name, conc, unit
      28–30: active6: name, conc, unit
    """
    if len(argv) < 31:
        print("ERROR: Not enough arguments for upsert_product", file=sys.stderr)
        return 1

    # Unpack
    (
        _cmd,
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
        application_unit,
        a1_name, a1_conc, a1_unit,
        a2_name, a2_conc, a2_unit,
        a3_name, a3_conc, a3_unit,
        a4_name, a4_conc, a4_unit,
        a5_name, a5_conc, a5_unit,
        a6_name, a6_conc, a6_unit,
    ) = argv[:31]

    mode = (mode or "").strip().lower()
    cat_key = normalise_category(category)
    data = load_inventory()
    cat_dict = data.setdefault(cat_key, {})

    pid = slugify_id(pid_raw, name)
    container_size_f = parse_float(container_size, 0.0)
    min_stock_f = parse_float(min_stock, 0.0)
    initial_stock_f = parse_float(initial_stock, 0.0)

    # Build actives list
    def make_active(name, conc, unit):
        name = (name or "").strip()
        if not name:
            return None
        return {
            "name": name,
            "concentration": parse_float(conc, 0.0),
            "concentration_unit": unit,
        }

    actives = []
    for triple in [
        (a1_name, a1_conc, a1_unit),
        (a2_name, a2_conc, a2_unit),
        (a3_name, a3_conc, a3_unit),
        (a4_name, a4_conc, a4_unit),
        (a5_name, a5_conc, a5_unit),
        (a6_name, a6_conc, a6_unit),
    ]:
        a = make_active(*triple)
        if a:
            actives.append(a)

    # Get existing or create new
    existing = cat_dict.get(pid, {})
    product = dict(existing)  # copy

    product["id"] = pid
    product["name"] = name
    product["category"] = category
    product["unit"] = product_unit
    product["default_pack_size"] = container_size_f
    product["container_size"] = container_size_f
    product["min_stock"] = min_stock_f
    product["storage_location"] = storage_location
    product["subcategory"] = subcategory
    product["chemical_group"] = chemical_group
    product["application_unit"] = application_unit

    # Stock handling:
    #  - if product is NEW, use initial_stock as starting stock
    #  - if product already existed, leave stock_on_hand alone
    if "stock_on_hand" not in product:
        product["stock_on_hand"] = initial_stock_f

    product["actives"] = actives

    cat_dict[pid] = product

    # Log a zero-qty "upsert" transaction just for audit (optional)
    add_transaction(
        data,
        category=category,
        product_id=pid,
        product_name=name,
        action=f"upsert_{mode or 'unknown'}",
        qty=0.0,
        unit=product_unit,
        note=f"Upsert via HA UI (location={storage_location}, subcategory={subcategory})",
    )

    save_inventory(data)
    return 0


# -------------------------------------------------------------------
# Stock movements (unchanged)
# -------------------------------------------------------------------
def mode_update_stock():
    parser = argparse.ArgumentParser(description="Update inventory stock")
    parser.add_argument("--category", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--quantity", required=True)
    parser.add_argument("--note", default="")
    # optional for backwards compatibility
    parser.add_argument("--action", default="")

    args = parser.parse_args()

    category_label = args.category
    cat_key = normalise_category(category_label)
    product_id = args.product.strip()
    qty = parse_float(args.quantity, 0.0)
    note = args.note
    action_flag = (args.action or "").strip().lower()

    if qty == 0:
        return 0

    data = load_inventory()
    cat_dict = data.setdefault(cat_key, {})

    if product_id not in cat_dict:
        # if unknown, create stub so you still see movements
        cat_dict[product_id] = {
            "id": product_id,
            "name": product_id,
            "category": category_label,
            "unit": "",
            "default_pack_size": 0,
            "container_size": 0,
            "min_stock": 0,
            "stock_on_hand": 0,
            "actives": [],
        }

    p = cat_dict[product_id]
    current = parse_float(p.get("stock_on_hand", 0.0), 0.0)

    # --- Movement logic ---
    if action_flag:
        # explicit action from HA
        if "use" in action_flag:
            action_type = "use"
            adj = abs(qty)
            new_stock = current - adj
        else:
            action_type = "topup"
            adj = abs(qty)
            new_stock = current + adj
        qty_logged = adj
    else:
        # sign-based
        if qty < 0:
            action_type = "use"
            adj = abs(qty)
            new_stock = current - adj
        else:
            action_type = "topup"
            adj = qty
            new_stock = current + adj
        qty_logged = adj

    if new_stock < 0:
        new_stock = 0.0

    p["stock_on_hand"] = new_stock

    unit = p.get("unit", "")
    add_transaction(
        data,
        category=category_label,
        product_id=p.get("id", product_id),
        product_name=p.get("name", product_id),
        action=action_type,
        qty=qty_logged,
        unit=unit,
        note=note,
    )

    save_inventory(data)
    return 0


# -------------------------------------------------------------------
# Main dispatcher
# -------------------------------------------------------------------
def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "add_product":
            return mode_add_product(sys.argv[1:])
        if sys.argv[1] == "upsert_product":
            return mode_upsert_product(sys.argv[1:])
    return mode_update_stock()


if __name__ == "__main__":
    raise SystemExit(main())
