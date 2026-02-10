"""Configuration file writer for PaddiSense."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ..const import CONFIGURATION_YAML, LOVELACE_DASHBOARDS_YAML

_LOGGER = logging.getLogger(__name__)


class ConfigWriter:
    """Manage configuration.yaml modifications for PaddiSense."""

    def __init__(self) -> None:
        """Initialize the config writer."""
        self.config_file = CONFIGURATION_YAML
        self.lovelace_file = LOVELACE_DASHBOARDS_YAML

    def check_configuration(self) -> dict[str, Any]:
        """Check if configuration.yaml has required PaddiSense entries."""
        if not self.config_file.exists():
            return {
                "success": False,
                "error": "configuration.yaml not found",
                "needs_packages": True,
                "needs_dashboards": True,
            }

        try:
            content = self.config_file.read_text(encoding="utf-8")

            # Check for packages include
            has_packages = bool(re.search(
                r'packages:\s*!include_dir_named\s+PaddiSense/packages',
                content
            ))

            # Check for lovelace dashboards include
            has_dashboards = bool(re.search(
                r'dashboards:\s*!include\s+lovelace_dashboards\.yaml',
                content
            ))

            return {
                "success": True,
                "needs_packages": not has_packages,
                "needs_dashboards": not has_dashboards,
                "fully_configured": has_packages and has_dashboards,
            }

        except IOError as e:
            return {
                "success": False,
                "error": f"Failed to read configuration: {e}",
            }

    def update_configuration(self) -> dict[str, Any]:
        """Update configuration.yaml with PaddiSense entries."""
        if not self.config_file.exists():
            return {
                "success": False,
                "error": "configuration.yaml not found",
            }

        try:
            content = self.config_file.read_text(encoding="utf-8")
            original_content = content
            modified = False

            # Check and add packages
            if not re.search(r'packages:\s*!include_dir_named\s+PaddiSense/packages', content):
                content = self._add_packages_include(content)
                modified = True

            # Check and add lovelace dashboards
            if not re.search(r'dashboards:\s*!include\s+lovelace_dashboards\.yaml', content):
                content = self._add_dashboards_include(content)
                modified = True

            if modified:
                # Create backup of original
                backup_path = self.config_file.with_suffix(".yaml.paddisense_backup")
                backup_path.write_text(original_content, encoding="utf-8")

                # Write updated config
                self.config_file.write_text(content, encoding="utf-8")

                _LOGGER.info("Updated configuration.yaml for PaddiSense")

                return {
                    "success": True,
                    "modified": True,
                    "backup": str(backup_path),
                    "message": "configuration.yaml updated",
                    "restart_required": True,
                }

            return {
                "success": True,
                "modified": False,
                "message": "configuration.yaml already configured",
            }

        except IOError as e:
            _LOGGER.error("Failed to update configuration: %s", e)
            return {
                "success": False,
                "error": f"Failed to update configuration: {e}",
            }

    def _add_packages_include(self, content: str) -> str:
        """Add packages include to configuration."""
        # Look for existing homeassistant: section
        homeassistant_match = re.search(r'^homeassistant:', content, re.MULTILINE)

        if homeassistant_match:
            # Find where to insert (after homeassistant: line)
            insert_pos = homeassistant_match.end()

            # Check if there's content after homeassistant:
            remaining = content[insert_pos:]
            if remaining.startswith('\n'):
                # Has newline, insert packages entry
                packages_entry = "\n  packages: !include_dir_named PaddiSense/packages/"
                content = content[:insert_pos] + packages_entry + content[insert_pos:]
            else:
                # homeassistant: is on same line with something, add on new line
                packages_entry = "\n  packages: !include_dir_named PaddiSense/packages/"
                content = content[:insert_pos] + packages_entry + content[insert_pos:]
        else:
            # No homeassistant: section, add it
            packages_block = """
# PaddiSense packages
homeassistant:
  packages: !include_dir_named PaddiSense/packages/

"""
            content = packages_block + content

        return content

    def _add_dashboards_include(self, content: str) -> str:
        """Add lovelace dashboards include to configuration."""
        # Look for existing lovelace: section
        lovelace_match = re.search(r'^lovelace:', content, re.MULTILINE)

        if lovelace_match:
            # Find where to insert dashboards
            insert_pos = lovelace_match.end()

            # Check what comes after lovelace:
            remaining = content[insert_pos:]

            # Find the end of the lovelace section
            lines = remaining.split('\n')
            in_lovelace = True
            dashboards_line = -1

            for i, line in enumerate(lines):
                if i == 0:
                    continue  # Skip first line (rest of lovelace: line)
                if line and not line.startswith(' ') and not line.startswith('\t'):
                    # New top-level section, lovelace ends here
                    break
                if 'dashboards:' in line:
                    dashboards_line = i
                    break

            if dashboards_line == -1:
                # No dashboards: line, add it
                # Find the mode: line or end of lovelace section
                mode_match = re.search(r'mode:\s*\w+', remaining)
                if mode_match:
                    # Insert after mode line
                    mode_end = insert_pos + mode_match.end()
                    dashboards_entry = "\n  dashboards: !include lovelace_dashboards.yaml"
                    content = content[:mode_end] + dashboards_entry + content[mode_end:]
                else:
                    # Add both mode and dashboards
                    dashboards_block = "\n  mode: storage\n  dashboards: !include lovelace_dashboards.yaml"
                    content = content[:insert_pos] + dashboards_block + content[insert_pos:]
        else:
            # No lovelace: section, add it
            lovelace_block = """
# PaddiSense dashboards
lovelace:
  mode: storage
  dashboards: !include lovelace_dashboards.yaml

"""
            # Find a good place to insert (after homeassistant section or at end)
            ha_match = re.search(r'^homeassistant:.*?(?=^\w|\Z)', content, re.MULTILINE | re.DOTALL)
            if ha_match:
                insert_pos = ha_match.end()
                content = content[:insert_pos] + lovelace_block + content[insert_pos:]
            else:
                content = content + lovelace_block

        return content

    def create_lovelace_dashboards_file(self) -> dict[str, Any]:
        """Create initial lovelace_dashboards.yaml if it doesn't exist."""
        if self.lovelace_file.exists():
            return {
                "success": True,
                "created": False,
                "message": "lovelace_dashboards.yaml already exists",
            }

        try:
            initial_content = """# Auto-generated by PaddiSense
# Do not edit manually - changes may be overwritten
# Manage modules via PaddiSense Manager

# Module dashboards will be added here when installed
"""
            self.lovelace_file.write_text(initial_content, encoding="utf-8")

            _LOGGER.info("Created lovelace_dashboards.yaml")

            return {
                "success": True,
                "created": True,
                "message": "Created lovelace_dashboards.yaml",
            }

        except IOError as e:
            return {
                "success": False,
                "error": f"Failed to create file: {e}",
            }

    def validate_yaml_syntax(self) -> dict[str, Any]:
        """Validate configuration.yaml syntax."""
        if not self.config_file.exists():
            return {
                "success": False,
                "error": "configuration.yaml not found",
            }

        try:
            import yaml

            content = self.config_file.read_text(encoding="utf-8")

            # Replace !include directives with placeholders for validation
            # (yaml.safe_load doesn't understand HA's !include)
            content_for_validation = re.sub(
                r'!include\S*\s+\S+',
                '"placeholder"',
                content
            )

            yaml.safe_load(content_for_validation)

            return {
                "success": True,
                "valid": True,
                "message": "YAML syntax is valid",
            }

        except yaml.YAMLError as e:
            return {
                "success": False,
                "valid": False,
                "error": f"YAML syntax error: {e}",
            }
        except IOError as e:
            return {
                "success": False,
                "error": f"Failed to read file: {e}",
            }

    def get_configuration_instructions(self) -> str:
        """Get manual configuration instructions if auto-update fails."""
        return """
To manually configure PaddiSense, add the following to your configuration.yaml:

homeassistant:
  packages: !include_dir_named PaddiSense/packages/

lovelace:
  mode: storage
  dashboards: !include lovelace_dashboards.yaml

Then restart Home Assistant.
"""
