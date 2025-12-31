#!/usr/bin/env python3
"""Emit inventory JSON for HA command_line sensor."""

from __future__ import annotations

import json
from pathlib import Path

from ipm_inventory import DATA_PATH, load_data


def main():
    data = load_data()
    products = data.get("products", [])
    payload = {
        "total_products": len(products),
        "products": products,
        "source": str(DATA_PATH),
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
