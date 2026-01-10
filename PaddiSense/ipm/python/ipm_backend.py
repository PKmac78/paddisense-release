#!/usr/bin/env python3
"""
IPM Backend - Inventory Product Manager
PaddiSense Farm Management System

This script handles all write operations for the inventory system:
  - add_product: Add a new product to the inventory
  - edit_product: Update an existing product's details
  - move_stock: Adjust stock levels at a specific location

Data is stored in: /config/local_data/ipm/inventory.json
This file is NOT tracked in git - each farm maintains their own inventory.

Usage:
  python3 ipm_backend.py add_product --name "Urea" --category "Fertiliser" ...
  python3 ipm_backend.py edit_product --id "UREA" --name "Urea Granular" ...
  python3 ipm_backend.py move_stock --id "UREA" --location "Silo 1" --delta -50
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Data file location (outside of git-tracked folders)
DATA_FILE = Path("/config/local_data/ipm/inventory.json")

# Valid categories and their subcategories
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

# Valid storage locations
LOCATIONS = [
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


def generate_id(name: str) -> str:
    """Generate a clean product ID from the name."""
    # Convert to uppercase, replace non-alphanumeric with underscore
    clean = re.sub(r"[^A-Z0-9]+", "_", name.upper())
    # Remove leading/trailing underscores and collapse multiples
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:20] if clean else "UNKNOWN"


def normalize_category(raw: str) -> str:
    """Normalize category name to standard format."""
    lookup = {
        "chemical": "Chemical",
        "chemicals": "Chemical",
        "fertiliser": "Fertiliser",
        "fertilizer": "Fertiliser",
        "seed": "Seed",
        "seeds": "Seed",
        "lubricant": "Lubricant",
        "lubricants": "Lubricant",
        "oil": "Lubricant",
    }
    key = raw.strip().lower()
    return lookup.get(key, raw.strip().title())


def load_inventory() -> dict[str, Any]:
    """Load inventory from JSON file, or return empty structure."""
    if not DATA_FILE.exists():
        return {"products": {}, "transactions": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"products": {}, "transactions": []}


def save_inventory(data: dict[str, Any]) -> None:
    """Save inventory to JSON file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def log_transaction(
    data: dict,
    action: str,
    product_id: str,
    product_name: str,
    location: str = "",
    delta: float = 0,
    note: str = "",
) -> None:
    """Append a transaction record for audit trail."""
    data.setdefault("transactions", []).append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "product_id": product_id,
        "product_name": product_name,
        "location": location,
        "delta": delta,
        "note": note,
    })


def cmd_add_product(args: argparse.Namespace) -> int:
    """Add a new product to the inventory."""
    data = load_inventory()
    products = data.setdefault("products", {})

    # Generate ID from name
    product_id = generate_id(args.name)

    # Check if product already exists
    if product_id in products:
        print(f"ERROR: Product '{product_id}' already exists", file=sys.stderr)
        return 1

    # Normalize and validate category
    category = normalize_category(args.category)
    if category not in CATEGORY_SUBCATEGORIES:
        print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
        return 1

    # Validate subcategory belongs to category
    subcategory = args.subcategory.strip() if args.subcategory else ""
    if subcategory and subcategory not in CATEGORY_SUBCATEGORIES[category]:
        print(f"ERROR: Subcategory '{subcategory}' not valid for {category}", file=sys.stderr)
        return 1

    # Parse active constituents if provided (for Chemical/Fertiliser)
    # Format: [{"name": "...", "concentration": number, "unit": "g/L"}, ...]
    active_constituents = []
    if args.actives and args.actives.strip() and args.actives.strip() != "[]":
        try:
            parsed = json.loads(args.actives)
            if isinstance(parsed, list):
                # Filter out empty entries
                for a in parsed:
                    name = a.get("name", "").strip() if isinstance(a.get("name"), str) else ""
                    if name:
                        conc = a.get("concentration", 0)
                        # Handle concentration as number or string
                        if isinstance(conc, (int, float)):
                            conc_val = float(conc)
                        else:
                            try:
                                conc_val = float(str(conc).strip()) if conc else 0
                            except ValueError:
                                conc_val = 0
                        unit = a.get("unit", "g/L").strip() if isinstance(a.get("unit"), str) else "g/L"
                        active_constituents.append({
                            "name": name,
                            "concentration": conc_val,
                            "unit": unit
                        })
        except json.JSONDecodeError:
            pass  # Ignore invalid JSON

    # Create product record
    product = {
        "id": product_id,
        "name": args.name.strip(),
        "category": category,
        "subcategory": subcategory,
        "unit": args.unit.strip() if args.unit else "L",
        "container_size": args.container_size or "",
        "min_stock": float(args.min_stock) if args.min_stock else 0,
        "chemical_group": args.chemical_group.strip() if args.chemical_group else "",
        "application_unit": args.application_unit.strip() if args.application_unit else "",
        "active_constituents": active_constituents if category in ["Chemical", "Fertiliser"] else [],
        "stock_by_location": {},
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    # Add initial stock if provided
    if args.initial_stock and args.initial_stock > 0 and args.location:
        location = args.location.strip()
        product["stock_by_location"][location] = float(args.initial_stock)
        log_transaction(
            data,
            action="initial_stock",
            product_id=product_id,
            product_name=product["name"],
            location=location,
            delta=float(args.initial_stock),
            note="Initial stock on product creation",
        )

    products[product_id] = product
    save_inventory(data)

    print(f"OK:{product_id}")
    return 0


def cmd_edit_product(args: argparse.Namespace) -> int:
    """Edit an existing product's details (not stock levels)."""
    data = load_inventory()
    products = data.get("products", {})

    product_id = args.id.strip().upper()
    if product_id not in products:
        print(f"ERROR: Product '{product_id}' not found", file=sys.stderr)
        return 1

    product = products[product_id]

    # Update fields if provided
    if args.name:
        product["name"] = args.name.strip()

    if args.category:
        category = normalize_category(args.category)
        if category not in CATEGORY_SUBCATEGORIES:
            print(f"ERROR: Invalid category '{category}'", file=sys.stderr)
            return 1
        product["category"] = category

    if args.subcategory is not None:
        subcategory = args.subcategory.strip()
        category = product.get("category", "Chemical")
        if subcategory and subcategory not in CATEGORY_SUBCATEGORIES.get(category, []):
            print(f"ERROR: Subcategory '{subcategory}' not valid for {category}", file=sys.stderr)
            return 1
        product["subcategory"] = subcategory

    if args.unit:
        product["unit"] = args.unit.strip()

    if args.container_size is not None:
        product["container_size"] = args.container_size

    if args.min_stock is not None:
        product["min_stock"] = float(args.min_stock)

    if args.chemical_group is not None:
        product["chemical_group"] = args.chemical_group.strip()

    if args.application_unit is not None:
        product["application_unit"] = args.application_unit.strip()

    # Handle active constituents (for Chemical/Fertiliser)
    # Format: [{"name": "...", "concentration": number, "unit": "g/L"}, ...]
    if args.actives is not None and args.actives.strip():
        category = product.get("category", "")
        if category in ["Chemical", "Fertiliser"]:
            try:
                parsed = json.loads(args.actives)
                if isinstance(parsed, list):
                    # Filter out empty entries
                    active_constituents = []
                    for a in parsed:
                        name = a.get("name", "").strip() if isinstance(a.get("name"), str) else ""
                        if name:
                            conc = a.get("concentration", 0)
                            # Handle concentration as number or string
                            if isinstance(conc, (int, float)):
                                conc_val = float(conc)
                            else:
                                try:
                                    conc_val = float(str(conc).strip()) if conc else 0
                                except ValueError:
                                    conc_val = 0
                            unit = a.get("unit", "g/L").strip() if isinstance(a.get("unit"), str) else "g/L"
                            active_constituents.append({
                                "name": name,
                                "concentration": conc_val,
                                "unit": unit
                            })
                    product["active_constituents"] = active_constituents
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON

    product["modified"] = datetime.now().isoformat(timespec="seconds")

    log_transaction(
        data,
        action="edit_product",
        product_id=product_id,
        product_name=product["name"],
        note="Product details updated",
    )

    save_inventory(data)
    print(f"OK:{product_id}")
    return 0


def cmd_move_stock(args: argparse.Namespace) -> int:
    """Move stock in or out of a location."""
    data = load_inventory()
    products = data.get("products", {})

    product_id = args.id.strip().upper()
    if product_id not in products:
        print(f"ERROR: Product '{product_id}' not found", file=sys.stderr)
        return 1

    product = products[product_id]
    location = args.location.strip()
    delta = float(args.delta)

    if delta == 0:
        print("OK:0")
        return 0

    # Get current stock at location
    stock_by_location = product.setdefault("stock_by_location", {})
    current = float(stock_by_location.get(location, 0))

    # Calculate new stock (cannot go below 0)
    new_stock = max(0, current + delta)

    # Update or remove location
    if new_stock > 0:
        stock_by_location[location] = new_stock
    elif location in stock_by_location:
        del stock_by_location[location]

    # Log the transaction
    log_transaction(
        data,
        action="stock_in" if delta > 0 else "stock_out",
        product_id=product_id,
        product_name=product["name"],
        location=location,
        delta=delta,
        note=args.note or "",
    )

    save_inventory(data)
    print(f"OK:{new_stock}")
    return 0


def cmd_delete_product(args: argparse.Namespace) -> int:
    """Delete a product from the inventory."""
    data = load_inventory()
    products = data.get("products", {})

    product_id = args.id.strip().upper()
    if product_id not in products:
        print(f"ERROR: Product '{product_id}' not found", file=sys.stderr)
        return 1

    product_name = products[product_id].get("name", product_id)
    del products[product_id]

    log_transaction(
        data,
        action="delete_product",
        product_id=product_id,
        product_name=product_name,
        note="Product deleted",
    )

    save_inventory(data)
    print(f"OK:deleted")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ipm_backend.py",
        description="IPM Inventory Backend - PaddiSense"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add_product command
    add_p = subparsers.add_parser("add_product", help="Add a new product")
    add_p.add_argument("--name", required=True, help="Product name")
    add_p.add_argument("--category", required=True, help="Category")
    add_p.add_argument("--subcategory", default="", help="Subcategory")
    add_p.add_argument("--unit", default="L", help="Unit (L, kg, t)")
    add_p.add_argument("--container_size", default="", help="Container size")
    add_p.add_argument("--min_stock", type=float, default=0, help="Minimum stock level")
    add_p.add_argument("--chemical_group", default="", help="Chemical group")
    add_p.add_argument("--application_unit", default="", help="Application unit")
    add_p.add_argument("--location", default="", help="Initial stock location")
    add_p.add_argument("--initial_stock", type=float, default=0, help="Initial stock quantity")
    add_p.add_argument("--actives", default="", help="Active constituents as JSON array")
    add_p.set_defaults(func=cmd_add_product)

    # edit_product command
    edit_p = subparsers.add_parser("edit_product", help="Edit product details")
    edit_p.add_argument("--id", required=True, help="Product ID")
    edit_p.add_argument("--name", help="New product name")
    edit_p.add_argument("--category", help="New category")
    edit_p.add_argument("--subcategory", help="New subcategory")
    edit_p.add_argument("--unit", help="New unit")
    edit_p.add_argument("--container_size", help="New container size")
    edit_p.add_argument("--min_stock", type=float, help="New minimum stock")
    edit_p.add_argument("--chemical_group", help="New chemical group")
    edit_p.add_argument("--application_unit", help="New application unit")
    edit_p.add_argument("--actives", help="Active constituents as JSON array")
    edit_p.set_defaults(func=cmd_edit_product)

    # move_stock command
    move_p = subparsers.add_parser("move_stock", help="Adjust stock at a location")
    move_p.add_argument("--id", required=True, help="Product ID")
    move_p.add_argument("--location", required=True, help="Storage location")
    move_p.add_argument("--delta", type=float, required=True, help="Change amount (+/-)")
    move_p.add_argument("--note", default="", help="Optional note")
    move_p.set_defaults(func=cmd_move_stock)

    # delete_product command
    del_p = subparsers.add_parser("delete_product", help="Delete a product")
    del_p.add_argument("--id", required=True, help="Product ID")
    del_p.set_defaults(func=cmd_delete_product)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
