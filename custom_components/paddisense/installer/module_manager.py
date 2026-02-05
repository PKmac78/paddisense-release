"""Module management for PaddiSense installer."""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..const import (
    AVAILABLE_MODULES,
    DATA_DIR,
    LOVELACE_DASHBOARDS_YAML,
    MODULE_METADATA,
    MODULES_JSON,
    PACKAGES_DIR,
    PADDISENSE_DIR,
)

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# ERROR TYPES
# =============================================================================

class ModuleError(Exception):
    """Base exception for module operations."""
    pass


class ModuleNotFoundError(ModuleError):
    """Module does not exist in repository."""
    pass


class ModuleValidationError(ModuleError):
    """Module failed validation checks."""
    pass


class ModuleInstallError(ModuleError):
    """Module installation failed."""
    pass


class ModuleRollbackError(ModuleError):
    """Failed to rollback after error."""
    pass


# =============================================================================
# INSTALLATION STATE TRACKING
# =============================================================================

@dataclass
class InstallState:
    """Track installation state for rollback."""
    module_id: str
    symlink_created: bool = False
    symlink_path: Path | None = None
    previous_symlink_target: Path | None = None
    data_dir_created: bool = False
    data_dir_path: Path | None = None
    dashboard_added: bool = False
    dashboard_slug: str | None = None
    previous_dashboards: dict | None = None
    errors: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        _LOGGER.error("Module %s: %s", self.module_id, error)


class ModuleManager:
    """Manage PaddiSense module installation and removal."""

    def __init__(self) -> None:
        """Initialize the module manager."""
        self.paddisense_dir = PADDISENSE_DIR
        self.packages_dir = PACKAGES_DIR
        self.data_dir = DATA_DIR

    def get_modules_metadata(self) -> dict[str, Any]:
        """Load modules metadata from modules.json or fallback to const."""
        if MODULES_JSON.exists():
            try:
                data = json.loads(MODULES_JSON.read_text(encoding="utf-8"))
                return data.get("modules", MODULE_METADATA)
            except (json.JSONDecodeError, IOError):
                pass
        return MODULE_METADATA

    def get_installed_modules(self) -> list[dict[str, Any]]:
        """Get list of currently installed modules."""
        installed = []
        metadata = self.get_modules_metadata()

        for module_id in AVAILABLE_MODULES:
            symlink_path = self.packages_dir / f"{module_id}.yaml"
            module_dir = self.paddisense_dir / module_id

            if symlink_path.exists() or symlink_path.is_symlink():
                # Module is installed
                version = self._get_module_version(module_id)
                meta = metadata.get(module_id, MODULE_METADATA.get(module_id, {}))

                installed.append({
                    "id": module_id,
                    "name": meta.get("name", module_id),
                    "version": version,
                    "icon": meta.get("icon", "mdi:package"),
                    "has_data": self._module_has_data(module_id),
                })

        return installed

    def get_available_modules(self) -> list[dict[str, Any]]:
        """Get list of modules available for installation."""
        available = []
        installed_ids = [m["id"] for m in self.get_installed_modules()]
        metadata = self.get_modules_metadata()

        for module_id in AVAILABLE_MODULES:
            if module_id not in installed_ids:
                module_dir = self.paddisense_dir / module_id

                # Only show if module folder exists in repo
                if module_dir.is_dir():
                    version = self._get_module_version(module_id)
                    meta = metadata.get(module_id, MODULE_METADATA.get(module_id, {}))

                    available.append({
                        "id": module_id,
                        "name": meta.get("name", module_id),
                        "description": meta.get("description", ""),
                        "version": version,
                        "icon": meta.get("icon", "mdi:package"),
                    })

        return available

    def _get_module_version(self, module_id: str) -> str:
        """Get version from module's VERSION file."""
        version_file = self.paddisense_dir / module_id / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text(encoding="utf-8").strip()
            except IOError:
                pass
        return "unknown"

    def _module_has_data(self, module_id: str) -> bool:
        """Check if module has local data."""
        data_path = self.data_dir / module_id
        if not data_path.exists():
            return False
        # Check if there are any files in the data directory
        return any(data_path.iterdir())

    # =========================================================================
    # YAML VALIDATION
    # =========================================================================

    def validate_package_yaml(self, module_id: str) -> dict[str, Any]:
        """Validate a module's package.yaml file.

        Checks:
        - File exists and is readable
        - Valid YAML syntax
        - No duplicate top-level keys (HA requirement)
        - Required sections present

        Returns:
            dict with 'valid' bool and 'errors' list
        """
        errors = []
        warnings = []
        package_file = self.paddisense_dir / module_id / "package.yaml"

        if not package_file.exists():
            return {
                "valid": False,
                "errors": [f"package.yaml not found: {package_file}"],
                "warnings": [],
            }

        try:
            import yaml

            content = package_file.read_text(encoding="utf-8")

            # Check for empty file
            if not content.strip():
                return {
                    "valid": False,
                    "errors": ["package.yaml is empty"],
                    "warnings": [],
                }

            # Parse YAML
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                return {
                    "valid": False,
                    "errors": [f"Invalid YAML syntax: {e}"],
                    "warnings": [],
                }

            if data is None:
                return {
                    "valid": False,
                    "errors": ["package.yaml parsed as empty/null"],
                    "warnings": [],
                }

            if not isinstance(data, dict):
                return {
                    "valid": False,
                    "errors": [f"package.yaml must be a dict, got {type(data).__name__}"],
                    "warnings": [],
                }

            # Check for valid HA package keys
            valid_keys = {
                "automation", "binary_sensor", "command_line", "counter",
                "group", "homeassistant", "input_boolean", "input_datetime",
                "input_number", "input_select", "input_text", "light",
                "logger", "media_player", "mqtt", "notify", "recorder",
                "scene", "script", "sensor", "shell_command", "switch",
                "template", "timer", "utility_meter", "zone",
            }

            for key in data.keys():
                if key not in valid_keys:
                    warnings.append(f"Unusual top-level key: '{key}' (may be valid)")

            # Check for common issues
            if "template" in data:
                templates = data["template"]
                if not isinstance(templates, list):
                    errors.append("'template' should be a list of template definitions")

            _LOGGER.debug("Validated package.yaml for %s: valid=%s", module_id, len(errors) == 0)

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "keys": list(data.keys()) if isinstance(data, dict) else [],
            }

        except IOError as e:
            return {
                "valid": False,
                "errors": [f"Failed to read package.yaml: {e}"],
                "warnings": [],
            }

    def validate_dashboard_yaml(self, module_id: str) -> dict[str, Any]:
        """Validate a module's dashboard YAML file.

        Returns:
            dict with 'valid' bool and 'errors' list
        """
        errors = []
        warnings = []

        meta = self.get_modules_metadata().get(module_id, MODULE_METADATA.get(module_id, {}))
        dashboard_file_path = meta.get("dashboard_file")

        if dashboard_file_path:
            dashboard_file = self.paddisense_dir / dashboard_file_path
        else:
            dashboard_file = self.paddisense_dir / module_id / "dashboards" / "views.yaml"

        if not dashboard_file.exists():
            # Try alternate paths
            alt_paths = [
                self.paddisense_dir / module_id / "dashboards" / f"{module_id}.yaml",
                self.paddisense_dir / module_id / "dashboards" / "inventory.yaml",
            ]
            for alt in alt_paths:
                if alt.exists():
                    dashboard_file = alt
                    break
            else:
                return {
                    "valid": False,
                    "errors": [f"Dashboard file not found: {dashboard_file}"],
                    "warnings": [],
                }

        try:
            import yaml

            content = dashboard_file.read_text(encoding="utf-8")
            data = yaml.safe_load(content)

            if data is None:
                errors.append("Dashboard YAML parsed as empty/null")
            elif not isinstance(data, dict):
                errors.append(f"Dashboard must be a dict, got {type(data).__name__}")
            else:
                # Check for required dashboard keys
                if "title" not in data:
                    warnings.append("Dashboard missing 'title' key")
                if "views" not in data:
                    errors.append("Dashboard missing 'views' key")
                elif not isinstance(data["views"], list):
                    errors.append("Dashboard 'views' must be a list")

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "file": str(dashboard_file),
            }

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "errors": [f"Invalid dashboard YAML: {e}"],
                "warnings": [],
            }
        except IOError as e:
            return {
                "valid": False,
                "errors": [f"Failed to read dashboard: {e}"],
                "warnings": [],
            }

    def preflight_check(self, module_id: str) -> dict[str, Any]:
        """Run all preflight checks before installation.

        Returns:
            dict with 'ready' bool and detailed check results
        """
        checks = {
            "module_exists": False,
            "version_file": False,
            "package_yaml_valid": False,
            "dashboard_yaml_valid": False,
            "no_conflicts": True,
        }
        errors = []
        warnings = []

        # Check module exists
        module_dir = self.paddisense_dir / module_id
        if module_dir.is_dir():
            checks["module_exists"] = True
        else:
            errors.append(f"Module directory not found: {module_dir}")

        # Check VERSION file
        version_file = module_dir / "VERSION"
        if version_file.exists():
            checks["version_file"] = True
        else:
            warnings.append(f"VERSION file missing (will use 'unknown')")

        # Validate package.yaml
        pkg_result = self.validate_package_yaml(module_id)
        checks["package_yaml_valid"] = pkg_result["valid"]
        errors.extend(pkg_result.get("errors", []))
        warnings.extend(pkg_result.get("warnings", []))

        # Validate dashboard.yaml
        dash_result = self.validate_dashboard_yaml(module_id)
        checks["dashboard_yaml_valid"] = dash_result["valid"]
        errors.extend(dash_result.get("errors", []))
        warnings.extend(dash_result.get("warnings", []))

        # Check for conflicts (e.g., already installed)
        symlink_path = self.packages_dir / f"{module_id}.yaml"
        if symlink_path.exists() and symlink_path.is_symlink():
            warnings.append(f"Module already installed (will be reinstalled)")

        ready = checks["module_exists"] and checks["package_yaml_valid"]

        return {
            "ready": ready,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "module_id": module_id,
        }

    # =========================================================================
    # ROLLBACK SUPPORT
    # =========================================================================

    def _rollback(self, state: InstallState) -> None:
        """Rollback a failed installation.

        Args:
            state: InstallState tracking what was changed
        """
        _LOGGER.warning("Rolling back installation of %s", state.module_id)

        rollback_errors = []

        # Rollback symlink
        if state.symlink_created and state.symlink_path:
            try:
                if state.symlink_path.exists() or state.symlink_path.is_symlink():
                    state.symlink_path.unlink()
                    _LOGGER.debug("Rollback: removed symlink %s", state.symlink_path)

                # Restore previous symlink if there was one
                if state.previous_symlink_target:
                    state.symlink_path.symlink_to(state.previous_symlink_target)
                    _LOGGER.debug("Rollback: restored previous symlink")
            except OSError as e:
                rollback_errors.append(f"Failed to rollback symlink: {e}")

        # Rollback dashboard
        if state.dashboard_added and state.previous_dashboards is not None:
            try:
                self._write_lovelace_dashboards(state.previous_dashboards)
                _LOGGER.debug("Rollback: restored previous dashboards")
            except Exception as e:
                rollback_errors.append(f"Failed to rollback dashboard: {e}")

        # Note: We don't remove data_dir as it may contain user data

        if rollback_errors:
            _LOGGER.error("Rollback completed with errors: %s", rollback_errors)
        else:
            _LOGGER.info("Rollback completed successfully for %s", state.module_id)

    def install_module(self, module_id: str, skip_validation: bool = False) -> dict[str, Any]:
        """Install a module by creating symlink and updating dashboards.

        Args:
            module_id: The module to install
            skip_validation: Skip YAML validation (not recommended)

        Returns:
            dict with success status, errors, and metadata
        """
        state = InstallState(module_id=module_id)

        # Basic checks
        if module_id not in AVAILABLE_MODULES:
            return {
                "success": False,
                "error": f"Unknown module: {module_id}",
                "error_type": "ModuleNotFoundError",
            }

        module_dir = self.paddisense_dir / module_id
        if not module_dir.is_dir():
            return {
                "success": False,
                "error": f"Module not found in repository: {module_id}",
                "error_type": "ModuleNotFoundError",
            }

        # Run preflight validation
        if not skip_validation:
            preflight = self.preflight_check(module_id)
            if not preflight["ready"]:
                return {
                    "success": False,
                    "error": f"Preflight check failed: {'; '.join(preflight['errors'])}",
                    "error_type": "ModuleValidationError",
                    "preflight": preflight,
                }

            # Log warnings but continue
            for warning in preflight.get("warnings", []):
                _LOGGER.warning("Module %s: %s", module_id, warning)

        try:
            # Ensure packages directory exists
            self.packages_dir.mkdir(parents=True, exist_ok=True)

            # Save current dashboard state for rollback
            if LOVELACE_DASHBOARDS_YAML.exists():
                try:
                    import yaml
                    content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
                    state.previous_dashboards = yaml.safe_load(content) or {}
                except Exception:
                    state.previous_dashboards = {}
            else:
                state.previous_dashboards = {}

            # Step 1: Create symlink
            symlink_path = self.packages_dir / f"{module_id}.yaml"
            state.symlink_path = symlink_path

            # Save previous symlink target if exists
            if symlink_path.is_symlink():
                try:
                    state.previous_symlink_target = symlink_path.readlink()
                except OSError:
                    pass
                symlink_path.unlink()

            elif symlink_path.exists():
                symlink_path.unlink()

            # Create new symlink
            relative_target = Path("..") / module_id / "package.yaml"
            symlink_path.symlink_to(relative_target)
            state.symlink_created = True
            _LOGGER.debug("Created symlink: %s -> %s", symlink_path, relative_target)

            # Step 2: Create data directory
            data_path = self.data_dir / module_id
            data_existed = data_path.exists()
            data_path.mkdir(parents=True, exist_ok=True)
            (data_path / "backups").mkdir(exist_ok=True)

            if not data_existed:
                state.data_dir_created = True
                state.data_dir_path = data_path
            _LOGGER.debug("Data directory ready: %s", data_path)

            # Step 3: Update lovelace dashboards
            meta = self.get_modules_metadata().get(module_id, MODULE_METADATA.get(module_id, {}))
            state.dashboard_slug = meta.get("dashboard_slug", f"{module_id}-dashboard")
            self._add_dashboard(module_id)
            state.dashboard_added = True
            _LOGGER.debug("Dashboard registered: %s", state.dashboard_slug)

            # Success
            version = self._get_module_version(module_id)
            _LOGGER.info("Installed module %s v%s", module_id, version)

            return {
                "success": True,
                "module_id": module_id,
                "version": version,
                "message": f"Successfully installed {module_id} v{version}",
                "restart_required": True,
                "steps_completed": {
                    "symlink": True,
                    "data_dir": True,
                    "dashboard": True,
                },
            }

        except OSError as e:
            state.add_error(f"OS error during installation: {e}")
            self._rollback(state)
            return {
                "success": False,
                "error": f"Installation failed: {e}",
                "error_type": "ModuleInstallError",
                "rollback_performed": True,
            }

        except Exception as e:
            state.add_error(f"Unexpected error: {e}")
            self._rollback(state)
            return {
                "success": False,
                "error": f"Unexpected error during installation: {e}",
                "error_type": "ModuleInstallError",
                "rollback_performed": True,
            }

    def remove_module(self, module_id: str) -> dict[str, Any]:
        """Remove a module by deleting symlink and dashboard entry."""
        if module_id not in AVAILABLE_MODULES:
            return {
                "success": False,
                "error": f"Unknown module: {module_id}",
            }

        symlink_path = self.packages_dir / f"{module_id}.yaml"

        if not symlink_path.exists() and not symlink_path.is_symlink():
            return {
                "success": False,
                "error": f"Module not installed: {module_id}",
            }

        try:
            # Remove symlink
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()

            # Remove dashboard entry
            self._remove_dashboard(module_id)

            # Note: We do NOT delete local_data/{module_id} - data is preserved

            _LOGGER.info("Removed module %s (data preserved)", module_id)

            return {
                "success": True,
                "module_id": module_id,
                "message": f"Removed {module_id} (local data preserved)",
                "restart_required": True,
            }

        except OSError as e:
            _LOGGER.error("Failed to remove module %s: %s", module_id, e)
            return {
                "success": False,
                "error": f"Removal failed: {e}",
            }

    def _add_dashboard(self, module_id: str) -> None:
        """Add dashboard entry for a module."""
        # Get metadata from modules.json (preferred) or fallback to const
        all_meta = self.get_modules_metadata()
        meta = all_meta.get(module_id, MODULE_METADATA.get(module_id, {}))

        slug = meta.get("dashboard_slug", f"{module_id}-dashboard")
        title = meta.get("dashboard_title", meta.get("name", module_id))
        icon = meta.get("icon", "mdi:package")

        # Use dashboard_file from modules.json if available
        dashboard_file_path = meta.get("dashboard_file")
        if dashboard_file_path:
            dashboard_file = self.paddisense_dir / dashboard_file_path
        else:
            # Fallback to convention
            dashboard_file = self.paddisense_dir / module_id / "dashboards" / "views.yaml"
            if module_id == "ipm":
                dashboard_file = self.paddisense_dir / "ipm" / "dashboards" / "inventory.yaml"

        if not dashboard_file.exists():
            # Try alternative path
            alt_file = self.paddisense_dir / module_id / "dashboards" / f"{module_id}.yaml"
            if alt_file.exists():
                dashboard_file = alt_file

        # Read existing dashboards
        dashboards = {}
        if LOVELACE_DASHBOARDS_YAML.exists():
            try:
                import yaml
                content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
                dashboards = yaml.safe_load(content) or {}
            except (yaml.YAMLError, IOError):
                dashboards = {}

        # Add new dashboard
        relative_path = str(dashboard_file.relative_to(Path("/config")))
        dashboards[slug] = {
            "mode": "yaml",
            "title": title,
            "icon": icon,
            "show_in_sidebar": True,
            "filename": relative_path,
        }

        # Write back
        self._write_lovelace_dashboards(dashboards)

    def _remove_dashboard(self, module_id: str) -> None:
        """Remove dashboard entry for a module."""
        all_meta = self.get_modules_metadata()
        meta = all_meta.get(module_id, MODULE_METADATA.get(module_id, {}))
        slug = meta.get("dashboard_slug", f"{module_id}-dashboard")

        if not LOVELACE_DASHBOARDS_YAML.exists():
            return

        try:
            import yaml
            content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
            dashboards = yaml.safe_load(content) or {}

            if slug in dashboards:
                del dashboards[slug]
                self._write_lovelace_dashboards(dashboards)

        except (yaml.YAMLError, IOError) as e:
            _LOGGER.error("Failed to update dashboards: %s", e)

    def _write_lovelace_dashboards(self, dashboards: dict[str, Any]) -> None:
        """Write lovelace_dashboards.yaml file."""
        import yaml

        header = """# Auto-generated by PaddiSense
# Do not edit manually - changes may be overwritten
# Manage modules via PaddiSense Manager

"""
        content = header + yaml.dump(dashboards, default_flow_style=False, sort_keys=False)
        LOVELACE_DASHBOARDS_YAML.write_text(content, encoding="utf-8")

    def install_multiple(self, module_ids: list[str]) -> dict[str, Any]:
        """Install multiple modules."""
        results = []
        success_count = 0
        failed_count = 0

        for module_id in module_ids:
            result = self.install_module(module_id)
            results.append({
                "module_id": module_id,
                "success": result.get("success", False),
                "error": result.get("error"),
            })
            if result.get("success"):
                success_count += 1
            else:
                failed_count += 1

        return {
            "success": failed_count == 0,
            "installed": success_count,
            "failed": failed_count,
            "results": results,
            "restart_required": success_count > 0,
        }

    def verify_module_installation(self, module_id: str) -> dict[str, Any]:
        """Verify a module is properly installed."""
        checks = {
            "symlink_exists": False,
            "package_exists": False,
            "data_dir_exists": False,
            "dashboard_registered": False,
        }

        # Check symlink
        symlink_path = self.packages_dir / f"{module_id}.yaml"
        checks["symlink_exists"] = symlink_path.exists() or symlink_path.is_symlink()

        # Check package file
        package_file = self.paddisense_dir / module_id / "package.yaml"
        checks["package_exists"] = package_file.exists()

        # Check data directory
        data_path = self.data_dir / module_id
        checks["data_dir_exists"] = data_path.is_dir()

        # Check dashboard registration
        if LOVELACE_DASHBOARDS_YAML.exists():
            try:
                import yaml
                content = LOVELACE_DASHBOARDS_YAML.read_text(encoding="utf-8")
                dashboards = yaml.safe_load(content) or {}
                meta = MODULE_METADATA.get(module_id, {})
                slug = meta.get("dashboard_slug", f"{module_id}-dashboard")
                checks["dashboard_registered"] = slug in dashboards
            except (yaml.YAMLError, IOError):
                pass

        all_passed = all(checks.values())

        return {
            "success": all_passed,
            "module_id": module_id,
            "checks": checks,
        }
