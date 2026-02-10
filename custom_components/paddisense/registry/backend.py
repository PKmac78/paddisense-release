"""
Farm Registry Backend for PaddiSense Integration.

Migrated from registry_backend.py CLI script to class-based methods
for integration with Home Assistant services.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..helpers import (
    create_backup,
    generate_id,
    load_registry_config,
    save_registry_config,
)
from ..const import REGISTRY_BACKUP_DIR, REGISTRY_CONFIG_FILE, REGISTRY_DATA_DIR


class RegistryBackend:
    """Backend class for Farm Registry operations."""

    def __init__(self) -> None:
        """Initialize the registry backend."""
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure data directories exist."""
        REGISTRY_DATA_DIR.mkdir(parents=True, exist_ok=True)
        REGISTRY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _log_transaction(
        self,
        config: dict[str, Any],
        action: str,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        details: str = "",
    ) -> None:
        """Append a transaction record for audit trail."""
        config.setdefault("transactions", []).append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "details": details,
            }
        )

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def init(self) -> dict[str, Any]:
        """Initialize the registry system."""
        config = load_registry_config()

        if config.get("initialized"):
            return {
                "success": True,
                "message": "Registry already initialized",
                "paddock_count": len(config.get("paddocks", {})),
                "bay_count": len(config.get("bays", {})),
                "season_count": len(config.get("seasons", {})),
            }

        now = datetime.now().isoformat(timespec="seconds")
        config["initialized"] = True
        config["version"] = "1.0.0"
        config.setdefault("paddocks", {})
        config.setdefault("bays", {})
        config.setdefault("seasons", {})
        config.setdefault("farms", {})
        config.setdefault("transactions", [])
        config["created"] = now
        config["modified"] = now

        save_registry_config(config)

        return {
            "success": True,
            "message": "Farm Registry initialized",
        }

    def status(self) -> dict[str, Any]:
        """Return system status."""
        config = load_registry_config()

        paddocks = config.get("paddocks", {})
        bays = config.get("bays", {})
        seasons = config.get("seasons", {})
        farms = config.get("farms", {})

        active_season = None
        for sid, s in seasons.items():
            if s.get("active"):
                active_season = sid
                break

        backup_count = (
            len(list(REGISTRY_BACKUP_DIR.glob("*.json")))
            if REGISTRY_BACKUP_DIR.exists()
            else 0
        )

        return {
            "initialized": config.get("initialized", False),
            "config_exists": REGISTRY_CONFIG_FILE.exists(),
            "version": config.get("version", "unknown"),
            "total_paddocks": len(paddocks),
            "total_bays": len(bays),
            "total_seasons": len(seasons),
            "total_farms": len(farms),
            "active_season": active_season,
            "transaction_count": len(config.get("transactions", [])),
            "backup_count": backup_count,
            "created": config.get("created"),
            "modified": config.get("modified"),
        }

    # =========================================================================
    # PADDOCK OPERATIONS
    # =========================================================================

    def add_paddock(
        self,
        name: str,
        bay_count: int,
        farm_id: str = "farm_1",
        bay_prefix: str = "B-",
        current_season: bool = True,
    ) -> dict[str, Any]:
        """Add a new paddock with specified number of bays."""
        config = load_registry_config()
        paddocks = config.setdefault("paddocks", {})
        bays = config.setdefault("bays", {})

        paddock_id = generate_id(name)

        if paddock_id in paddocks:
            return {"success": False, "error": f"Paddock '{paddock_id}' already exists"}

        now = datetime.now().isoformat(timespec="seconds")

        paddocks[paddock_id] = {
            "farm_id": farm_id,
            "name": name,
            "bay_prefix": bay_prefix,
            "bay_count": bay_count,
            "current_season": current_season,
            "created": now,
            "modified": now,
        }

        for i in range(1, bay_count + 1):
            bay_name = f"{bay_prefix}{i:02d}"
            bay_id = f"{paddock_id}_{generate_id(bay_name)}"
            is_last = i == bay_count

            bays[bay_id] = {
                "paddock_id": paddock_id,
                "name": bay_name,
                "order": i,
                "is_last_bay": is_last,
                "created": now,
                "modified": now,
            }

        self._log_transaction(
            config, "add", "paddock", paddock_id, name,
            f"Created with {bay_count} bays"
        )
        save_registry_config(config)

        return {
            "success": True,
            "paddock_id": paddock_id,
            "bay_count": bay_count,
            "message": f"Created paddock '{name}' with {bay_count} bays",
        }

    def edit_paddock(
        self,
        paddock_id: str,
        name: str | None = None,
        farm_id: str | None = None,
        current_season: bool | None = None,
    ) -> dict[str, Any]:
        """Edit an existing paddock."""
        config = load_registry_config()
        paddocks = config.get("paddocks", {})

        if paddock_id not in paddocks:
            return {"success": False, "error": f"Paddock '{paddock_id}' not found"}

        paddock = paddocks[paddock_id]
        changes = []

        if name is not None:
            paddock["name"] = name
            changes.append(f"name={name}")

        if farm_id is not None:
            paddock["farm_id"] = farm_id
            changes.append(f"farm={farm_id}")

        if current_season is not None:
            paddock["current_season"] = current_season
            changes.append(f"current_season={current_season}")

        paddock["modified"] = datetime.now().isoformat(timespec="seconds")

        self._log_transaction(
            config, "edit", "paddock", paddock_id, paddock["name"],
            ", ".join(changes)
        )
        save_registry_config(config)

        return {
            "success": True,
            "paddock_id": paddock_id,
            "message": f"Updated paddock '{paddock['name']}'",
        }

    def delete_paddock(self, paddock_id: str) -> dict[str, Any]:
        """Delete a paddock and all its bays."""
        config = load_registry_config()
        paddocks = config.get("paddocks", {})
        bays = config.get("bays", {})

        if paddock_id not in paddocks:
            return {"success": False, "error": f"Paddock '{paddock_id}' not found"}

        create_backup("pre_delete")

        paddock_name = paddocks[paddock_id].get("name", paddock_id)

        bays_to_delete = [
            bid for bid, b in bays.items() if b.get("paddock_id") == paddock_id
        ]
        for bid in bays_to_delete:
            del bays[bid]

        del paddocks[paddock_id]

        self._log_transaction(
            config, "delete", "paddock", paddock_id, paddock_name,
            f"Deleted with {len(bays_to_delete)} bays"
        )
        save_registry_config(config)

        return {
            "success": True,
            "paddock_id": paddock_id,
            "bays_deleted": len(bays_to_delete),
            "message": f"Deleted paddock '{paddock_name}' and {len(bays_to_delete)} bays",
        }

    def set_current_season(
        self, paddock_id: str, value: bool | None = None
    ) -> dict[str, Any]:
        """Set paddock current_season flag."""
        config = load_registry_config()
        paddocks = config.get("paddocks", {})

        if paddock_id not in paddocks:
            return {"success": False, "error": f"Paddock '{paddock_id}' not found"}

        paddock = paddocks[paddock_id]

        if value is not None:
            new_value = value
        else:
            new_value = not paddock.get("current_season", True)

        paddock["current_season"] = new_value
        paddock["modified"] = datetime.now().isoformat(timespec="seconds")

        self._log_transaction(
            config, "set_current_season", "paddock", paddock_id, paddock["name"],
            f"current_season={new_value}"
        )
        save_registry_config(config)

        return {
            "success": True,
            "paddock_id": paddock_id,
            "current_season": new_value,
            "message": f"Set {paddock['name']} current_season to {new_value}",
        }

    # =========================================================================
    # BAY OPERATIONS
    # =========================================================================

    def add_bay(
        self,
        paddock_id: str,
        name: str,
        order: int | None = None,
        is_last: bool = False,
    ) -> dict[str, Any]:
        """Add a bay to an existing paddock."""
        config = load_registry_config()
        paddocks = config.get("paddocks", {})
        bays = config.setdefault("bays", {})

        if paddock_id not in paddocks:
            return {"success": False, "error": f"Paddock '{paddock_id}' not found"}

        paddock = paddocks[paddock_id]
        bay_id = f"{paddock_id}_{generate_id(name)}"

        if bay_id in bays:
            return {"success": False, "error": f"Bay '{bay_id}' already exists"}

        existing_bays = [
            b for b in bays.values() if b.get("paddock_id") == paddock_id
        ]
        max_order = max([b.get("order", 0) for b in existing_bays], default=0)

        now = datetime.now().isoformat(timespec="seconds")
        bays[bay_id] = {
            "paddock_id": paddock_id,
            "name": name,
            "order": order if order else max_order + 1,
            "is_last_bay": is_last,
            "created": now,
            "modified": now,
        }

        paddock["bay_count"] = len(
            [b for b in bays.values() if b.get("paddock_id") == paddock_id]
        )
        paddock["modified"] = now

        self._log_transaction(
            config, "add", "bay", bay_id, name, f"Added to {paddock_id}"
        )
        save_registry_config(config)

        return {
            "success": True,
            "bay_id": bay_id,
            "message": f"Added bay '{name}' to paddock",
        }

    def edit_bay(
        self,
        bay_id: str,
        name: str | None = None,
        order: int | None = None,
        is_last: bool | None = None,
    ) -> dict[str, Any]:
        """Edit bay info."""
        config = load_registry_config()
        bays = config.get("bays", {})

        if bay_id not in bays:
            return {"success": False, "error": f"Bay '{bay_id}' not found"}

        bay = bays[bay_id]
        changes = []

        if name is not None:
            bay["name"] = name
            changes.append(f"name={name}")

        if order is not None:
            bay["order"] = order
            changes.append(f"order={order}")

        if is_last is not None:
            bay["is_last_bay"] = is_last
            changes.append(f"is_last={is_last}")

        bay["modified"] = datetime.now().isoformat(timespec="seconds")

        self._log_transaction(
            config, "edit", "bay", bay_id, bay["name"], ", ".join(changes)
        )
        save_registry_config(config)

        return {
            "success": True,
            "bay_id": bay_id,
            "message": f"Updated bay '{bay['name']}'",
        }

    def delete_bay(self, bay_id: str) -> dict[str, Any]:
        """Delete a bay."""
        config = load_registry_config()
        bays = config.get("bays", {})
        paddocks = config.get("paddocks", {})

        if bay_id not in bays:
            return {"success": False, "error": f"Bay '{bay_id}' not found"}

        bay = bays[bay_id]
        bay_name = bay.get("name", bay_id)
        paddock_id = bay.get("paddock_id")

        del bays[bay_id]

        if paddock_id and paddock_id in paddocks:
            paddocks[paddock_id]["bay_count"] = len(
                [b for b in bays.values() if b.get("paddock_id") == paddock_id]
            )
            paddocks[paddock_id]["modified"] = datetime.now().isoformat(
                timespec="seconds"
            )

        self._log_transaction(config, "delete", "bay", bay_id, bay_name, "")
        save_registry_config(config)

        return {
            "success": True,
            "bay_id": bay_id,
            "message": f"Deleted bay '{bay_name}'",
        }

    # =========================================================================
    # SEASON OPERATIONS
    # =========================================================================

    def add_season(
        self,
        name: str,
        start_date: str,
        end_date: str,
        active: bool = False,
    ) -> dict[str, Any]:
        """Add a new season."""
        config = load_registry_config()
        seasons = config.setdefault("seasons", {})

        season_id = generate_id(name)

        if season_id in seasons:
            return {"success": False, "error": f"Season '{season_id}' already exists"}

        now = datetime.now().isoformat(timespec="seconds")
        seasons[season_id] = {
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "active": active,
            "created": now,
            "modified": now,
        }

        if active:
            for sid, season in seasons.items():
                if sid != season_id:
                    season["active"] = False

        self._log_transaction(
            config, "add", "season", season_id, name, f"{start_date} to {end_date}"
        )
        save_registry_config(config)

        return {
            "success": True,
            "season_id": season_id,
            "message": f"Created season '{name}'",
        }

    def edit_season(
        self,
        season_id: str,
        name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Edit a season."""
        config = load_registry_config()
        seasons = config.get("seasons", {})

        if season_id not in seasons:
            return {"success": False, "error": f"Season '{season_id}' not found"}

        season = seasons[season_id]
        changes = []

        if name is not None:
            season["name"] = name
            changes.append(f"name={name}")

        if start_date is not None:
            season["start_date"] = start_date
            changes.append(f"start={start_date}")

        if end_date is not None:
            season["end_date"] = end_date
            changes.append(f"end={end_date}")

        season["modified"] = datetime.now().isoformat(timespec="seconds")

        self._log_transaction(
            config, "edit", "season", season_id, season["name"], ", ".join(changes)
        )
        save_registry_config(config)

        return {
            "success": True,
            "season_id": season_id,
            "message": f"Updated season '{season['name']}'",
        }

    def delete_season(self, season_id: str) -> dict[str, Any]:
        """Delete a season."""
        config = load_registry_config()
        seasons = config.get("seasons", {})

        if season_id not in seasons:
            return {"success": False, "error": f"Season '{season_id}' not found"}

        season_name = seasons[season_id].get("name", season_id)
        del seasons[season_id]

        self._log_transaction(config, "delete", "season", season_id, season_name, "")
        save_registry_config(config)

        return {
            "success": True,
            "season_id": season_id,
            "message": f"Deleted season '{season_name}'",
        }

    def set_active_season(self, season_id: str) -> dict[str, Any]:
        """Set the active season."""
        config = load_registry_config()
        seasons = config.get("seasons", {})

        if season_id not in seasons:
            return {"success": False, "error": f"Season '{season_id}' not found"}

        for sid, season in seasons.items():
            season["active"] = sid == season_id
            season["modified"] = datetime.now().isoformat(timespec="seconds")

        season_name = seasons[season_id].get("name", season_id)
        self._log_transaction(
            config, "set_active", "season", season_id, season_name, ""
        )
        save_registry_config(config)

        return {
            "success": True,
            "season_id": season_id,
            "message": f"Set active season to '{season_name}'",
        }

    # =========================================================================
    # FARM OPERATIONS
    # =========================================================================

    def add_farm(self, name: str) -> dict[str, Any]:
        """Add a new farm."""
        config = load_registry_config()
        farms = config.setdefault("farms", {})

        farm_id = generate_id(name)

        if farm_id in farms:
            return {"success": False, "error": f"Farm '{farm_id}' already exists"}

        now = datetime.now().isoformat(timespec="seconds")
        farms[farm_id] = {
            "name": name,
            "created": now,
            "modified": now,
        }

        self._log_transaction(config, "add", "farm", farm_id, name, "")
        save_registry_config(config)

        return {
            "success": True,
            "farm_id": farm_id,
            "message": f"Created farm '{name}'",
        }

    def edit_farm(self, farm_id: str, name: str | None = None) -> dict[str, Any]:
        """Edit an existing farm."""
        config = load_registry_config()
        farms = config.get("farms", {})

        if farm_id not in farms:
            return {"success": False, "error": f"Farm '{farm_id}' not found"}

        farm = farms[farm_id]
        changes = []

        if name is not None:
            farm["name"] = name
            changes.append(f"name={name}")

        farm["modified"] = datetime.now().isoformat(timespec="seconds")

        self._log_transaction(
            config, "edit", "farm", farm_id, farm["name"], ", ".join(changes)
        )
        save_registry_config(config)

        return {
            "success": True,
            "farm_id": farm_id,
            "message": f"Updated farm '{farm['name']}'",
        }

    def delete_farm(self, farm_id: str) -> dict[str, Any]:
        """Delete a farm (only if no paddocks assigned)."""
        config = load_registry_config()
        farms = config.get("farms", {})
        paddocks = config.get("paddocks", {})

        if farm_id not in farms:
            return {"success": False, "error": f"Farm '{farm_id}' not found"}

        assigned_paddocks = [
            p for p in paddocks.values() if p.get("farm_id") == farm_id
        ]
        if assigned_paddocks:
            return {
                "success": False,
                "error": f"Cannot delete farm with {len(assigned_paddocks)} assigned paddocks",
                "paddock_count": len(assigned_paddocks),
            }

        farm_name = farms[farm_id].get("name", farm_id)
        del farms[farm_id]

        self._log_transaction(config, "delete", "farm", farm_id, farm_name, "")
        save_registry_config(config)

        return {
            "success": True,
            "farm_id": farm_id,
            "message": f"Deleted farm '{farm_name}'",
        }

    # =========================================================================
    # EXPORT/IMPORT OPERATIONS
    # =========================================================================

    def export_registry(self) -> dict[str, Any]:
        """Export config to a timestamped backup."""
        if not REGISTRY_CONFIG_FILE.exists():
            return {"success": False, "error": "No config file to export"}

        backup_path = create_backup("export")

        return {
            "success": True,
            "backup_file": str(backup_path.name),
            "message": f"Exported to {backup_path.name}",
        }

    def import_registry(self, filename: str) -> dict[str, Any]:
        """Import config from a backup file."""
        import json

        backup_path = REGISTRY_BACKUP_DIR / filename

        if not backup_path.exists():
            return {"success": False, "error": f"Backup file '{filename}' not found"}

        if REGISTRY_CONFIG_FILE.exists():
            create_backup("pre_import")

        try:
            backup_data = json.loads(backup_path.read_text(encoding="utf-8"))
            if "paddocks" not in backup_data and "bays" not in backup_data:
                return {"success": False, "error": "Invalid backup file structure"}

            save_registry_config(backup_data)

            return {
                "success": True,
                "message": f"Imported from {filename}",
                "paddock_count": len(backup_data.get("paddocks", {})),
                "bay_count": len(backup_data.get("bays", {})),
            }
        except (json.JSONDecodeError, IOError) as e:
            return {"success": False, "error": f"Failed to import: {e}"}

    def backup_list(self) -> dict[str, Any]:
        """List available backup files."""
        if not REGISTRY_BACKUP_DIR.exists():
            return {"backups": []}

        backups = sorted(
            REGISTRY_BACKUP_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        backup_list = []
        for b in backups[:20]:
            backup_list.append(
                {
                    "filename": b.name,
                    "size": b.stat().st_size,
                    "modified": datetime.fromtimestamp(b.stat().st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )

        return {"backups": backup_list}

    def reset(self, token: str) -> dict[str, Any]:
        """Reset the system (requires confirmation token)."""
        if token != "CONFIRM_RESET":
            return {
                "success": False,
                "error": "Reset requires token 'CONFIRM_RESET'",
                "message": "This will delete all paddock, bay, and season data!",
            }

        if REGISTRY_CONFIG_FILE.exists():
            create_backup("pre_reset")

        now = datetime.now().isoformat(timespec="seconds")
        config = {
            "initialized": True,
            "paddocks": {},
            "bays": {},
            "seasons": {},
            "farms": {},
            "transactions": [],
            "version": "1.0.0",
            "created": now,
            "modified": now,
        }
        save_registry_config(config)

        return {
            "success": True,
            "message": "Registry reset complete. All paddocks, bays, and seasons deleted.",
        }
