#!/usr/bin/env python3
"""
inventory_list.py

Reads /config/RRAPL/JSON Files/inventory.json (used by inventory_update.py)
and outputs a flat JSON of products for Home Assistant:

{
  "count": <int>,
  "products": [
    {
      "id": "MAGISTER",
      "name": "Magister",
      "category": "Chemical",
      "unit": "L",
      "stock_on_hand": 0,
      "actives": [
        {
          "name": "fenazaquin",
          "concentration": 200.0,
          "concentration_unit": "g/L"
        }
      ],
      "active_names": ["fenazaquin"],
      "storage_location": "Chem Shed 1",
      "subcategory": "Herbicide",
      "chemical_group": "3A",
      "application_unit": "L/ha",
      "default_pack_size": 20.0,
      "container_size": 20.0
    },
    ...
  ]
}
"""

import json
import sys
from pathlib import Path

INVENTORY_PATH = Path("/config/RRAPL/JSON Files/inventory.json")

CATEGORY_LABELS = {
    "chemicals": "Chemical",
    "fertiliser": "Fertiliser",
    "seed": "Seed",
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


def normalise_actives(actives_src):
    """
    Ensure we always return a list of dicts:
    { "name": ..., "concentration": <float>, "concentration_unit": <str> }
    PLUS a parallel list of just the names for easy display.
    """
    out = []
    names = []

    for a in actives_src or []:
        if isinstance(a, dict):
            name = (a.get("name") or "").strip()
            if not name:
                continue
            conc = a.get("concentration", 0)
            unit = a.get("concentration_unit", "None / Unknown")
        else:
            # If it's a plain string, keep name but default conc/unit
            name = str(a).strip()
            if not name:
                continue
            conc = 0
            unit = "None / Unknown"

        try:
            conc_val = float(conc)
        except Exception:
            conc_val = 0.0

        out.append(
            {
                "name": name,
                "concentration": conc_val,
                "concentration_unit": unit,
            }
        )
        names.append(name)

    return out, names


def main():
    data = load_inventory()
    products_out = []

    for key, cat_dict in (
        ("chemicals", data.get("chemicals", {})),
        ("fertiliser", data.get("fertiliser", {})),
        ("seed", data.get("seed", {})),
    ):
        label = CATEGORY_LABELS.get(key, key.title())
        for pid, p in (cat_dict or {}).items():
            actives_list, active_names = normalise_actives(p.get("actives") or [])

            products_out.append(
                {
                    "id": p.get("id", pid),
                    "name": p.get("name", pid),
                    "category": label,
                    "unit": p.get("unit", ""),
                    "stock_on_hand": p.get("stock_on_hand", 0),
                    "actives": actives_list,              # full dicts
                    "active_names": active_names,         # just names (back-compat)
                    "storage_location": p.get("storage_location", ""),
                    "subcategory": p.get("subcategory", ""),
                    "chemical_group": p.get("chemical_group", "None / Unknown"),
                    "application_unit": p.get("application_unit", "L/ha"),
                    "default_pack_size": p.get("default_pack_size"),
                    "container_size": p.get("container_size"),
                }
            )

    out = {
        "count": len(products_out),
        "products": products_out,
    }
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
