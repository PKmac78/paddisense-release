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

# Data file locations (outside of git-tracked folders)
DATA_DIR = Path("/config/local_data/ipm")
DATA_FILE = DATA_DIR / "inventory.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# Default locations (used when creating initial config)
DEFAULT_LOCATIONS = [
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

# Standard active constituents list (built-in, cannot be removed)
STANDARD_ACTIVES = [
    # Herbicides
    "2,4-D", "Atrazine", "Bromoxynil", "Carfentrazone-ethyl", "Clethodim",
    "Clodinafop-propargyl", "Clopyralid", "Dicamba", "Diflufenican", "Diquat",
    "Fenoxaprop-P-ethyl", "Florasulam", "Fluazifop-P-butyl", "Flumetsulam",
    "Fluroxypyr", "Glufosinate-ammonium", "Glyphosate", "Haloxyfop", "Imazamox",
    "Imazapic", "Imazapyr", "Imazethapyr", "MCPA", "Mesotrione", "Metolachlor",
    "Metsulfuron-methyl", "Paraquat", "Pendimethalin", "Picloram", "Pinoxaden",
    "Propaquizafop", "Prosulfocarb", "Pyroxasulfone", "Pyroxsulam",
    "Quizalofop-P-ethyl", "Sethoxydim", "Simazine", "Sulfometuron-methyl",
    "Sulfosulfuron", "Terbuthylazine", "Triallate", "Tribenuron-methyl",
    "Triclopyr", "Trifluralin", "Trifloxysulfuron",
    # Fungicides
    "Azoxystrobin", "Bixafen", "Boscalid", "Carbendazim", "Chlorothalonil",
    "Cyproconazole", "Difenoconazole", "Epoxiconazole", "Fludioxonil",
    "Fluopyram", "Flutriafol", "Fluxapyroxad", "Iprodione", "Isopyrazam",
    "Mancozeb", "Metalaxyl", "Propiconazole", "Prothioconazole",
    "Pyraclostrobin", "Tebuconazole", "Thiram", "Triadimefon", "Triadimenol",
    "Trifloxystrobin",
    # Insecticides
    "Abamectin", "Acetamiprid", "Alpha-cypermethrin", "Bifenthrin",
    "Chlorantraniliprole", "Chlorpyrifos", "Clothianidin", "Cyantraniliprole",
    "Cypermethrin", "Deltamethrin", "Dimethoate", "Emamectin benzoate",
    "Esfenvalerate", "Fipronil", "Imidacloprid", "Indoxacarb",
    "Lambda-cyhalothrin", "Malathion", "Methomyl", "Omethoate", "Pirimicarb",
    "Spinetoram", "Spinosad", "Sulfoxaflor", "Thiacloprid", "Thiamethoxam",
    # Seed Treatments
    "Ipconazole", "Metalaxyl-M", "Sedaxane", "Triticonazole",
    # Fertiliser Elements
    "Boron", "Calcium", "Copper", "Iron", "Magnesium", "Manganese",
    "Molybdenum", "Nitrogen", "Phosphorus", "Potassium", "Sulfur", "Zinc",
    # Adjuvants
    "Alcohol ethoxylate", "Ammonium sulfate", "Methylated seed oil",
    "Organosilicone", "Paraffin oil", "Petroleum oil",
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def load_config() -> dict[str, Any]:
    """Load config from JSON file, or return default structure."""
    if not CONFIG_FILE.exists():
        return {
            "locations": DEFAULT_LOCATIONS.copy(),
            "custom_actives": [],
        }
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {
            "locations": DEFAULT_LOCATIONS.copy(),
            "custom_actives": [],
        }


def save_config(config: dict[str, Any]) -> None:
    """Save config to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config["modified"] = datetime.now().isoformat(timespec="seconds")
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def get_locations() -> list[str]:
    """Get current locations list from config."""
    config = load_config()
    return config.get("locations", DEFAULT_LOCATIONS.copy())


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
    # Format: [{"name": "...", "concentration": number, "unit": "g/L", "group": "2"}, ...]
    # Note: chemical_group is stored per active constituent, not at product level
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
                        group = a.get("group", "").strip() if isinstance(a.get("group"), str) else ""
                        active_constituents.append({
                            "name": name,
                            "concentration": conc_val,
                            "unit": unit,
                            "group": group
                        })
        except json.JSONDecodeError:
            pass  # Ignore invalid JSON

    # Create product record
    # Note: chemical_group is stored per active constituent, not at product level
    product = {
        "id": product_id,
        "name": args.name.strip(),
        "category": category,
        "subcategory": subcategory,
        "unit": args.unit.strip() if args.unit else "L",
        "container_size": args.container_size or "",
        "min_stock": float(args.min_stock) if args.min_stock else 0,
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

    if args.application_unit is not None:
        product["application_unit"] = args.application_unit.strip()

    # Handle active constituents (for Chemical/Fertiliser)
    # Format: [{"name": "...", "concentration": number, "unit": "g/L", "group": "2"}, ...]
    # Note: chemical_group is stored per active constituent, not at product level
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
                            group = a.get("group", "").strip() if isinstance(a.get("group"), str) else ""
                            active_constituents.append({
                                "name": name,
                                "concentration": conc_val,
                                "unit": unit,
                                "group": group
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


def cmd_status(args: argparse.Namespace) -> int:
    """Return system status as JSON."""
    status = {
        "database_exists": DATA_FILE.exists(),
        "config_exists": CONFIG_FILE.exists(),
        "status": "not_initialized",
        "product_count": 0,
        "transaction_count": 0,
        "location_count": 0,
        "locations_with_stock": [],
    }

    # Check config
    if CONFIG_FILE.exists():
        try:
            config = load_config()
            status["location_count"] = len(config.get("locations", []))
        except Exception:
            status["status"] = "error"
            status["error"] = "Config file corrupted"
            print(json.dumps(status))
            return 0

    # Check database
    if DATA_FILE.exists():
        try:
            data = load_inventory()
            products = data.get("products", {})
            status["product_count"] = len(products)
            status["transaction_count"] = len(data.get("transactions", []))

            # Find locations with stock
            locations_with_stock = set()
            for product in products.values():
                for loc, qty in product.get("stock_by_location", {}).items():
                    if qty and float(qty) > 0:
                        locations_with_stock.add(loc)
            status["locations_with_stock"] = sorted(locations_with_stock)

            status["status"] = "ready"
        except Exception as e:
            status["status"] = "error"
            status["error"] = f"Database file corrupted: {e}"
    elif CONFIG_FILE.exists():
        # Config exists but no database - still considered initialized
        status["status"] = "ready"

    print(json.dumps(status))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the IPM system - create config and database files."""
    created = []

    # Create directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create config if missing
    if not CONFIG_FILE.exists():
        config = {
            "locations": DEFAULT_LOCATIONS.copy(),
            "custom_actives": [],
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        save_config(config)
        created.append("config")

    # Create empty inventory if missing
    if not DATA_FILE.exists():
        data = {"products": {}, "transactions": []}
        save_inventory(data)
        created.append("database")

    if created:
        print(f"OK:created:{','.join(created)}")
    else:
        print("OK:already_initialized")
    return 0


def cmd_add_location(args: argparse.Namespace) -> int:
    """Add a new storage location."""
    location = args.name.strip()
    if not location:
        print("ERROR: Location name cannot be empty", file=sys.stderr)
        return 1

    config = load_config()
    locations = config.get("locations", DEFAULT_LOCATIONS.copy())

    # Check if already exists (case-insensitive)
    if any(loc.lower() == location.lower() for loc in locations):
        print(f"ERROR: Location '{location}' already exists", file=sys.stderr)
        return 1

    locations.append(location)
    config["locations"] = locations
    save_config(config)

    print(f"OK:{location}")
    return 0


def cmd_remove_location(args: argparse.Namespace) -> int:
    """Remove a storage location (only if no stock there)."""
    location = args.name.strip()
    if not location:
        print("ERROR: Location name cannot be empty", file=sys.stderr)
        return 1

    config = load_config()
    locations = config.get("locations", [])

    # Find exact match
    matching = [loc for loc in locations if loc.lower() == location.lower()]
    if not matching:
        print(f"ERROR: Location '{location}' not found", file=sys.stderr)
        return 1

    actual_location = matching[0]

    # Check if any products have stock at this location
    data = load_inventory()
    products = data.get("products", {})
    for product_id, product in products.items():
        stock = product.get("stock_by_location", {}).get(actual_location, 0)
        if stock and float(stock) > 0:
            print(f"ERROR: Cannot remove '{actual_location}' - has stock for {product.get('name', product_id)}", file=sys.stderr)
            return 1

    # Remove location
    config["locations"] = [loc for loc in locations if loc != actual_location]
    save_config(config)

    print(f"OK:removed:{actual_location}")
    return 0


def cmd_list_actives(args: argparse.Namespace) -> int:
    """List all active constituents (standard + custom)."""
    config = load_config()
    custom_actives = config.get("custom_actives", [])

    # Build merged list
    all_actives = []

    # Add standard actives
    for name in STANDARD_ACTIVES:
        all_actives.append({
            "name": name,
            "type": "standard",
            "common_groups": [],
        })

    # Add custom actives
    for active in custom_actives:
        if isinstance(active, dict) and active.get("name"):
            all_actives.append({
                "name": active["name"],
                "type": "custom",
                "common_groups": active.get("common_groups", []),
            })

    # Sort alphabetically by name
    all_actives.sort(key=lambda x: x["name"].lower())

    result = {
        "total": len(all_actives),
        "standard_count": len(STANDARD_ACTIVES),
        "custom_count": len(custom_actives),
        "actives": all_actives,
    }

    print(json.dumps(result))
    return 0


def cmd_add_active(args: argparse.Namespace) -> int:
    """Add a custom active constituent."""
    name = args.name.strip()
    if not name:
        print("ERROR: Active name cannot be empty", file=sys.stderr)
        return 1

    # Parse common groups if provided
    common_groups = []
    if args.groups and args.groups.strip():
        common_groups = [g.strip() for g in args.groups.split(",") if g.strip()]

    config = load_config()
    custom_actives = config.get("custom_actives", [])

    # Check if already exists in standard list (case-insensitive)
    if any(std.lower() == name.lower() for std in STANDARD_ACTIVES):
        print(f"ERROR: '{name}' is already a standard active", file=sys.stderr)
        return 1

    # Check if already exists in custom list (case-insensitive)
    if any(a.get("name", "").lower() == name.lower() for a in custom_actives):
        print(f"ERROR: Active '{name}' already exists in custom list", file=sys.stderr)
        return 1

    # Add new custom active
    custom_actives.append({
        "name": name,
        "common_groups": common_groups,
        "created": datetime.now().isoformat(timespec="seconds"),
    })

    config["custom_actives"] = custom_actives
    save_config(config)

    print(f"OK:{name}")
    return 0


def cmd_remove_active(args: argparse.Namespace) -> int:
    """Remove a custom active constituent (only if unused)."""
    name = args.name.strip()
    if not name:
        print("ERROR: Active name cannot be empty", file=sys.stderr)
        return 1

    # Check if it's a standard active (cannot remove)
    if any(std.lower() == name.lower() for std in STANDARD_ACTIVES):
        print(f"ERROR: Cannot remove standard active '{name}'", file=sys.stderr)
        return 1

    config = load_config()
    custom_actives = config.get("custom_actives", [])

    # Find the custom active
    matching = [a for a in custom_actives if a.get("name", "").lower() == name.lower()]
    if not matching:
        print(f"ERROR: Custom active '{name}' not found", file=sys.stderr)
        return 1

    actual_name = matching[0].get("name", name)

    # Check if any products use this active
    data = load_inventory()
    products = data.get("products", {})
    products_using = []

    for product_id, product in products.items():
        actives = product.get("active_constituents", [])
        if isinstance(actives, list):
            for active in actives:
                if isinstance(active, dict):
                    if active.get("name", "").lower() == actual_name.lower():
                        products_using.append(product.get("name", product_id))
                        break

    if products_using:
        print(f"ERROR: Cannot remove '{actual_name}' - used by: {', '.join(products_using[:3])}", file=sys.stderr)
        return 1

    # Remove the custom active
    config["custom_actives"] = [
        a for a in custom_actives if a.get("name", "").lower() != actual_name.lower()
    ]
    save_config(config)

    print(f"OK:removed:{actual_name}")
    return 0


# =========================================================================
# PHASE 3: DATA MANAGEMENT COMMANDS
# =========================================================================

def cmd_export(args: argparse.Namespace) -> int:
    """Export inventory and config to a timestamped backup file."""
    # Create backup directory if needed
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = BACKUP_DIR / f"inventory_{timestamp}.json"

    # Load current data
    inventory = load_inventory()
    config = load_config()

    # Create backup structure
    backup_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "ipm_backup",
        "inventory": inventory,
        "config": config,
    }

    # Write backup file
    backup_file.write_text(
        json.dumps(backup_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"OK:{backup_file.name}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import inventory and config from a backup file."""
    filename = args.filename.strip()
    if not filename:
        print("ERROR: Filename cannot be empty", file=sys.stderr)
        return 1

    # Construct full path
    backup_file = BACKUP_DIR / filename
    if not backup_file.exists():
        print(f"ERROR: Backup file '{filename}' not found", file=sys.stderr)
        return 1

    # Load and validate backup
    try:
        backup_data = json.loads(backup_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in backup file: {e}", file=sys.stderr)
        return 1

    # Validate backup structure
    if backup_data.get("type") != "ipm_backup":
        print("ERROR: File is not a valid IPM backup", file=sys.stderr)
        return 1

    inventory = backup_data.get("inventory")
    config = backup_data.get("config")

    if not isinstance(inventory, dict) or "products" not in inventory:
        print("ERROR: Backup contains invalid inventory data", file=sys.stderr)
        return 1

    # Create a backup of current data before importing
    current_inventory = load_inventory()
    current_config = load_config()

    pre_import_backup = {
        "version": "1.0",
        "created": datetime.now().isoformat(timespec="seconds"),
        "type": "ipm_backup",
        "note": "Pre-import automatic backup",
        "inventory": current_inventory,
        "config": current_config,
    }

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    pre_import_file = BACKUP_DIR / f"pre_import_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    pre_import_file.write_text(
        json.dumps(pre_import_backup, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Import the data
    save_inventory(inventory)
    if config and isinstance(config, dict):
        save_config(config)

    product_count = len(inventory.get("products", {}))
    print(f"OK:imported:{product_count}:{pre_import_file.name}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Reset all IPM data (requires confirmation token)."""
    token = args.token.strip() if args.token else ""

    # Token must be "CONFIRM_RESET" to proceed
    if token != "CONFIRM_RESET":
        print("ERROR: Invalid confirmation token. Use --token CONFIRM_RESET", file=sys.stderr)
        return 1

    # Create backup before reset
    current_inventory = load_inventory()
    current_config = load_config()

    if current_inventory.get("products") or current_config.get("custom_actives"):
        pre_reset_backup = {
            "version": "1.0",
            "created": datetime.now().isoformat(timespec="seconds"),
            "type": "ipm_backup",
            "note": "Pre-reset automatic backup",
            "inventory": current_inventory,
            "config": current_config,
        }

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        pre_reset_file = BACKUP_DIR / f"pre_reset_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        pre_reset_file.write_text(
            json.dumps(pre_reset_backup, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Reset to empty state
    empty_inventory = {"products": {}, "transactions": []}
    save_inventory(empty_inventory)

    # Reset config to defaults (keep locations, clear custom actives)
    reset_config = {
        "locations": DEFAULT_LOCATIONS.copy(),
        "custom_actives": [],
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    save_config(reset_config)

    print("OK:reset")
    return 0


def cmd_backup_list(args: argparse.Namespace) -> int:
    """List available backup files with metadata."""
    backups = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(backup_file.read_text(encoding="utf-8"))
                product_count = len(data.get("inventory", {}).get("products", {}))
                backups.append({
                    "filename": backup_file.name,
                    "created": data.get("created", ""),
                    "note": data.get("note", ""),
                    "product_count": product_count,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })
            except (json.JSONDecodeError, IOError):
                # Include file even if we can't read it
                backups.append({
                    "filename": backup_file.name,
                    "created": "",
                    "note": "Unable to read",
                    "product_count": 0,
                    "size_kb": round(backup_file.stat().st_size / 1024, 1),
                })

    result = {
        "total": len(backups),
        "backups": backups,
    }

    print(json.dumps(result))
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
    add_p.add_argument("--application_unit", default="", help="Application unit")
    add_p.add_argument("--location", default="", help="Initial stock location")
    add_p.add_argument("--initial_stock", type=float, default=0, help="Initial stock quantity")
    add_p.add_argument("--actives", default="", help="Active constituents as JSON array (includes group per active)")
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
    edit_p.add_argument("--application_unit", help="New application unit")
    edit_p.add_argument("--actives", help="Active constituents as JSON array (includes group per active)")
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

    # status command
    status_p = subparsers.add_parser("status", help="Get system status")
    status_p.set_defaults(func=cmd_status)

    # init command
    init_p = subparsers.add_parser("init", help="Initialize IPM system")
    init_p.set_defaults(func=cmd_init)

    # add_location command
    add_loc_p = subparsers.add_parser("add_location", help="Add a storage location")
    add_loc_p.add_argument("--name", required=True, help="Location name")
    add_loc_p.set_defaults(func=cmd_add_location)

    # remove_location command
    rem_loc_p = subparsers.add_parser("remove_location", help="Remove a storage location")
    rem_loc_p.add_argument("--name", required=True, help="Location name")
    rem_loc_p.set_defaults(func=cmd_remove_location)

    # ----- Active Constituents Commands -----
    # list_actives command
    list_act_p = subparsers.add_parser("list_actives", help="List all active constituents")
    list_act_p.set_defaults(func=cmd_list_actives)

    # add_active command
    add_act_p = subparsers.add_parser("add_active", help="Add a custom active constituent")
    add_act_p.add_argument("--name", required=True, help="Active name")
    add_act_p.add_argument("--groups", default="", help="Common chemical groups (comma-separated)")
    add_act_p.set_defaults(func=cmd_add_active)

    # remove_active command
    rem_act_p = subparsers.add_parser("remove_active", help="Remove a custom active constituent")
    rem_act_p.add_argument("--name", required=True, help="Active name")
    rem_act_p.set_defaults(func=cmd_remove_active)

    # ----- Data Management Commands (Phase 3) -----
    # export command
    export_p = subparsers.add_parser("export", help="Export data to backup file")
    export_p.set_defaults(func=cmd_export)

    # import command
    import_p = subparsers.add_parser("import_backup", help="Import data from backup file")
    import_p.add_argument("--filename", required=True, help="Backup filename to import")
    import_p.set_defaults(func=cmd_import)

    # reset command
    reset_p = subparsers.add_parser("reset", help="Reset all data (requires confirmation)")
    reset_p.add_argument("--token", required=True, help="Confirmation token (CONFIRM_RESET)")
    reset_p.set_defaults(func=cmd_reset)

    # backup_list command
    backup_list_p = subparsers.add_parser("backup_list", help="List available backups")
    backup_list_p.set_defaults(func=cmd_backup_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
