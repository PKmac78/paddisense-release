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

DATA_DIR = Path("/config/local_data/ipm")
DATA_FILE = DATA_DIR / "inventory.json"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"

# Version file location (in module directory)
VERSION_FILE = Path("/config/PaddiSense/ipm/VERSION")


def get_version() -> str:
    """Read module version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
    except IOError:
        pass
    return "unknown"

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

# Default storage locations (used if config doesn't exist)
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

# Standard active constituents list (must match ipm_backend.py)
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


def load_config() -> dict:
    """Load config from JSON file, or return defaults."""
    if not CONFIG_FILE.exists():
        return {"locations": DEFAULT_LOCATIONS}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"locations": DEFAULT_LOCATIONS}


def get_backup_info() -> dict:
    """Get information about available backups."""
    backups = []
    last_backup = None
    backup_filenames = []

    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                data = json.loads(backup_file.read_text(encoding="utf-8"))
                product_count = len(data.get("inventory", {}).get("products", {}))
                backup_info = {
                    "filename": backup_file.name,
                    "created": data.get("created", ""),
                    "note": data.get("note", ""),
                    "product_count": product_count,
                }
                backups.append(backup_info)
                backup_filenames.append(backup_file.name)

                # First one (newest) is the last backup
                if last_backup is None:
                    last_backup = backup_info
            except (json.JSONDecodeError, IOError):
                # Include file even if we can't read it
                backups.append({
                    "filename": backup_file.name,
                    "created": "",
                    "note": "Unable to read",
                    "product_count": 0,
                })
                backup_filenames.append(backup_file.name)

    return {
        "backup_count": len(backups),
        "last_backup": last_backup,
        "backups": backups,
        "backup_filenames": backup_filenames,
    }


def main():
    # Load config for locations and custom actives
    config = load_config()
    locations = config.get("locations", DEFAULT_LOCATIONS)
    custom_actives = config.get("custom_actives", [])

    # Build merged actives list (standard + custom)
    all_actives_list = []
    for name in STANDARD_ACTIVES:
        all_actives_list.append({
            "name": name,
            "type": "standard",
            "common_groups": [],
        })
    for active in custom_actives:
        if isinstance(active, dict) and active.get("name"):
            all_actives_list.append({
                "name": active["name"],
                "type": "custom",
                "common_groups": active.get("common_groups", []),
            })
    all_actives_list.sort(key=lambda x: x["name"].lower())

    # Determine system status
    config_exists = CONFIG_FILE.exists()
    database_exists = DATA_FILE.exists()

    if config_exists or database_exists:
        system_status = "ready"
    else:
        system_status = "not_initialized"

    # Get backup info
    backup_info = get_backup_info()

    # Get version
    version = get_version()

    # Default empty output
    empty_output = {
        "total_products": 0,
        "products": {},
        "product_names": [],
        "product_locations": {},
        "categories": list(CATEGORY_SUBCATEGORIES.keys()),
        "category_subcategories": CATEGORY_SUBCATEGORIES,
        "locations": locations,
        "active_names": [],
        "system_status": system_status,
        "config_exists": config_exists,
        "database_exists": database_exists,
        "locations_with_stock": [],
        "custom_actives_count": len(custom_actives),
        "all_actives_list": all_actives_list,
        "active_products_map": {},
        "backup_count": backup_info["backup_count"],
        "last_backup": backup_info["last_backup"],
        "backup_filenames": backup_info["backup_filenames"],
        "version": version,
    }

    if not DATA_FILE.exists():
        print(json.dumps(empty_output))
        return

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        empty_output["system_status"] = "error"
        print(json.dumps(empty_output))
        return

    products = data.get("products", {})

    # Build output structures
    product_names = []
    product_locations = {}
    active_names_set = set()
    all_locations_with_stock = set()
    active_products_map = {}  # Maps active name to list of product names using it

    for product_id, product in products.items():
        name = product.get("name", product_id)
        product_names.append(name)

        # Get locations where this product has stock
        stock_by_location = product.get("stock_by_location", {})
        locations_with_stock = [
            loc for loc, qty in stock_by_location.items()
            if qty and float(qty) > 0
        ]

        # Track all locations that have any stock
        all_locations_with_stock.update(locations_with_stock)

        # Calculate total stock
        total_stock = sum(
            float(qty) for qty in stock_by_location.values()
            if qty
        )
        product["total_stock"] = round(total_stock, 2)

        # Store locations for this product
        if locations_with_stock:
            product_locations[product_id] = sorted(locations_with_stock)

        # Collect active constituent names and build active -> products map
        actives = product.get("active_constituents", [])
        if isinstance(actives, list):
            for active in actives:
                if isinstance(active, dict):
                    active_name = active.get("name", "")
                    if active_name and isinstance(active_name, str):
                        active_name = active_name.strip()
                        active_names_set.add(active_name)
                        # Add to products map
                        if active_name not in active_products_map:
                            active_products_map[active_name] = []
                        if name not in active_products_map[active_name]:
                            active_products_map[active_name].append(name)

    output = {
        "total_products": len(products),
        "products": products,
        "product_names": sorted(product_names),
        "product_locations": product_locations,
        "categories": list(CATEGORY_SUBCATEGORIES.keys()),
        "category_subcategories": CATEGORY_SUBCATEGORIES,
        "locations": locations,
        "active_names": sorted(active_names_set),
        "system_status": "ready",
        "config_exists": config_exists,
        "database_exists": database_exists,
        "locations_with_stock": sorted(all_locations_with_stock),
        "custom_actives_count": len(custom_actives),
        "all_actives_list": all_actives_list,
        "active_products_map": active_products_map,
        "backup_count": backup_info["backup_count"],
        "last_backup": backup_info["last_backup"],
        "backup_filenames": backup_info["backup_filenames"],
        "version": version,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
