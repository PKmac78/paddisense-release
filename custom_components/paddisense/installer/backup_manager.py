"""Backup and restore management for PaddiSense."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..const import (
    BACKUP_DIR,
    CONFIGURATION_YAML,
    LOVELACE_DASHBOARDS_YAML,
    PADDISENSE_DIR,
)

_LOGGER = logging.getLogger(__name__)

# Maximum number of backups to retain
MAX_BACKUPS = 5


class BackupManager:
    """Manage PaddiSense backups for updates and rollbacks."""

    def __init__(self) -> None:
        """Initialize the backup manager."""
        self.backup_dir = BACKUP_DIR
        self.paddisense_dir = PADDISENSE_DIR

    def create_backup(self, tag: str = "manual") -> dict[str, Any]:
        """Create a full backup of PaddiSense configuration."""
        try:
            # Ensure backup directory exists
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped backup folder
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_name = f"{timestamp}_{tag}"
            backup_path = self.backup_dir / backup_name

            if backup_path.exists():
                return {
                    "success": False,
                    "error": f"Backup already exists: {backup_name}",
                }

            backup_path.mkdir(parents=True)

            # Create manifest
            manifest = {
                "timestamp": datetime.now().isoformat(),
                "tag": tag,
                "version": self._get_current_version(),
                "contents": [],
            }

            # Backup PaddiSense directory (excluding local_data references)
            if self.paddisense_dir.exists():
                paddisense_backup = backup_path / "PaddiSense"
                self._copy_directory(
                    self.paddisense_dir,
                    paddisense_backup,
                    exclude_patterns=["__pycache__", "*.pyc", ".git"],
                )
                manifest["contents"].append("PaddiSense/")

            # Backup lovelace_dashboards.yaml
            if LOVELACE_DASHBOARDS_YAML.exists():
                shutil.copy2(
                    LOVELACE_DASHBOARDS_YAML,
                    backup_path / "lovelace_dashboards.yaml"
                )
                manifest["contents"].append("lovelace_dashboards.yaml")

            # Backup configuration.yaml patch (just the relevant lines)
            if CONFIGURATION_YAML.exists():
                config_patch = self._extract_paddisense_config()
                if config_patch:
                    (backup_path / "configuration.yaml.patch").write_text(
                        config_patch, encoding="utf-8"
                    )
                    manifest["contents"].append("configuration.yaml.patch")

            # Write manifest
            (backup_path / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            # Cleanup old backups
            self._cleanup_old_backups()

            _LOGGER.info("Created backup: %s", backup_name)

            return {
                "success": True,
                "backup_id": backup_name,
                "path": str(backup_path),
                "message": f"Backup created: {backup_name}",
            }

        except OSError as e:
            _LOGGER.error("Backup failed: %s", e)
            return {
                "success": False,
                "error": f"Backup failed: {e}",
            }

    def restore_backup(self, backup_id: str) -> dict[str, Any]:
        """Restore from a backup."""
        backup_path = self.backup_dir / backup_id

        if not backup_path.is_dir():
            return {
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }

        manifest_file = backup_path / "manifest.json"
        if not manifest_file.exists():
            return {
                "success": False,
                "error": "Invalid backup: manifest.json not found",
            }

        try:
            # Create a pre-restore backup
            pre_restore = self.create_backup("pre_restore")
            if not pre_restore.get("success"):
                _LOGGER.warning("Could not create pre-restore backup")

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

            # Restore PaddiSense directory
            paddisense_backup = backup_path / "PaddiSense"
            if paddisense_backup.is_dir():
                # Remove current (except local_data which isn't in repo anyway)
                if self.paddisense_dir.exists():
                    shutil.rmtree(self.paddisense_dir)
                shutil.copytree(paddisense_backup, self.paddisense_dir)

            # Restore lovelace_dashboards.yaml
            lovelace_backup = backup_path / "lovelace_dashboards.yaml"
            if lovelace_backup.exists():
                shutil.copy2(lovelace_backup, LOVELACE_DASHBOARDS_YAML)

            _LOGGER.info("Restored backup: %s", backup_id)

            return {
                "success": True,
                "backup_id": backup_id,
                "version": manifest.get("version", "unknown"),
                "message": f"Restored from {backup_id}",
                "restart_required": True,
            }

        except (OSError, json.JSONDecodeError) as e:
            _LOGGER.error("Restore failed: %s", e)
            return {
                "success": False,
                "error": f"Restore failed: {e}",
            }

    def rollback(self) -> dict[str, Any]:
        """Rollback to the most recent pre-update backup."""
        backups = self.list_backups()

        if not backups:
            return {
                "success": False,
                "error": "No backups available for rollback",
            }

        # Find most recent pre_update backup
        for backup in backups:
            if "pre_update" in backup.get("tag", ""):
                return self.restore_backup(backup["backup_id"])

        # If no pre_update backup, use most recent
        return self.restore_backup(backups[0]["backup_id"])

    def list_backups(self) -> list[dict[str, Any]]:
        """List available backups, sorted by date (newest first)."""
        if not self.backup_dir.exists():
            return []

        backups = []

        for backup_path in self.backup_dir.iterdir():
            if not backup_path.is_dir():
                continue

            manifest_file = backup_path / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    backups.append({
                        "backup_id": backup_path.name,
                        "timestamp": manifest.get("timestamp"),
                        "tag": manifest.get("tag"),
                        "version": manifest.get("version"),
                        "size": self._get_dir_size(backup_path),
                    })
                except (json.JSONDecodeError, IOError):
                    # Include backup even without valid manifest
                    backups.append({
                        "backup_id": backup_path.name,
                        "timestamp": None,
                        "tag": "unknown",
                        "version": "unknown",
                        "size": self._get_dir_size(backup_path),
                    })

        # Sort by timestamp (newest first)
        backups.sort(
            key=lambda x: x.get("timestamp") or "",
            reverse=True
        )

        return backups

    def delete_backup(self, backup_id: str) -> dict[str, Any]:
        """Delete a specific backup."""
        backup_path = self.backup_dir / backup_id

        if not backup_path.is_dir():
            return {
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }

        try:
            shutil.rmtree(backup_path)
            _LOGGER.info("Deleted backup: %s", backup_id)
            return {
                "success": True,
                "message": f"Deleted backup: {backup_id}",
            }
        except OSError as e:
            return {
                "success": False,
                "error": f"Failed to delete: {e}",
            }

    def _cleanup_old_backups(self) -> None:
        """Remove old backups exceeding MAX_BACKUPS."""
        backups = self.list_backups()

        if len(backups) > MAX_BACKUPS:
            # Delete oldest backups
            for backup in backups[MAX_BACKUPS:]:
                self.delete_backup(backup["backup_id"])

    def _copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_patterns: list[str] | None = None
    ) -> None:
        """Copy directory, excluding specified patterns."""
        exclude_patterns = exclude_patterns or []

        def ignore_patterns(directory: str, files: list[str]) -> list[str]:
            ignored = []
            for f in files:
                for pattern in exclude_patterns:
                    if pattern.startswith("*."):
                        if f.endswith(pattern[1:]):
                            ignored.append(f)
                            break
                    elif f == pattern:
                        ignored.append(f)
                        break
            return ignored

        shutil.copytree(src, dst, ignore=ignore_patterns)

    def _get_current_version(self) -> str:
        """Get current PaddiSense version."""
        version_file = self.paddisense_dir / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8").strip()
            except IOError:
                pass
        return "unknown"

    def _get_dir_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    def _extract_paddisense_config(self) -> str:
        """Extract PaddiSense-related lines from configuration.yaml."""
        if not CONFIGURATION_YAML.exists():
            return ""

        try:
            content = CONFIGURATION_YAML.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Find lines related to PaddiSense
            relevant_lines = []
            in_section = False

            for line in lines:
                # Check for PaddiSense-related content
                if "paddisense" in line.lower() or "PaddiSense" in line:
                    relevant_lines.append(line)
                    in_section = True
                elif in_section and line.startswith("  "):
                    relevant_lines.append(line)
                elif in_section and not line.strip():
                    relevant_lines.append(line)
                else:
                    in_section = False

            return "\n".join(relevant_lines)

        except IOError:
            return ""
