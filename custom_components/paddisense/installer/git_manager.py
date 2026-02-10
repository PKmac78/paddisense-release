"""Git operations for PaddiSense installer."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..const import (
    PADDISENSE_DIR,
    PADDISENSE_REPO_URL,
    PADDISENSE_REPO_BRANCH,
    PADDISENSE_VERSION_FILE,
)

_LOGGER = logging.getLogger(__name__)

# Subfolder in repo containing the modules (repo structure: repo/PaddiSense/ipm, etc.)
REPO_MODULES_SUBFOLDER = "PaddiSense"


class GitManager:
    """Manage git operations for PaddiSense repository."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize the git manager."""
        self.repo_dir = PADDISENSE_DIR
        self._base_url = PADDISENSE_REPO_URL
        self.branch = PADDISENSE_REPO_BRANCH
        self._token = token

    @property
    def repo_url(self) -> str:
        """Get repo URL with token if available."""
        if self._token:
            # https://TOKEN@github.com/user/repo.git
            return self._base_url.replace("https://", f"https://{self._token}@")
        return self._base_url

    def set_token(self, token: str | None) -> None:
        """Update token for authenticated operations."""
        self._token = token

    def is_git_available(self) -> bool:
        """Check if git is available on the system."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def is_repo_cloned(self) -> bool:
        """Check if the PaddiSense modules are present."""
        # Check for modules.json or VERSION as indicator
        version_file = self.repo_dir / "VERSION"
        modules_json = self.repo_dir / "modules.json"
        return version_file.exists() or modules_json.exists()

    def clone(self) -> dict[str, Any]:
        """Clone the PaddiSense repository and extract modules subfolder."""
        if self.is_repo_cloned():
            return {
                "success": False,
                "error": "Repository already exists",
            }

        try:
            # Clone to temp directory first
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "repo"

                _LOGGER.info("Cloning PaddiSense repository...")
                result = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--branch",
                        self.branch,
                        "--single-branch",
                        "--depth",
                        "1",
                        self.repo_url,
                        str(temp_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes
                )

                if result.returncode != 0:
                    _LOGGER.error("Git clone failed: %s", result.stderr)
                    return {
                        "success": False,
                        "error": f"Clone failed: {result.stderr}",
                    }

                # Check if modules are in a subfolder
                modules_source = temp_path / REPO_MODULES_SUBFOLDER
                if modules_source.is_dir():
                    source_dir = modules_source
                    _LOGGER.info("Found modules in %s subfolder", REPO_MODULES_SUBFOLDER)
                else:
                    # Modules at repo root
                    source_dir = temp_path
                    _LOGGER.info("Modules at repository root")

                # Ensure target directory exists
                self.repo_dir.parent.mkdir(parents=True, exist_ok=True)

                # Remove existing target if it exists
                if self.repo_dir.exists():
                    shutil.rmtree(self.repo_dir)

                # Copy modules to target, excluding packages folder (growers start fresh)
                def ignore_packages(dir, files):
                    if Path(dir).name == "PaddiSense" or dir == str(source_dir):
                        return ["packages"] if "packages" in files else []
                    return []

                shutil.copytree(source_dir, self.repo_dir, ignore=ignore_packages)

                # Create empty packages directory
                (self.repo_dir / "packages").mkdir(exist_ok=True)
                _LOGGER.info("Copied modules to %s (packages excluded)", self.repo_dir)

            _LOGGER.info("Successfully cloned PaddiSense repository")
            return {
                "success": True,
                "message": "Repository cloned successfully",
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Clone timed out. Check your network connection.",
            }
        except subprocess.SubprocessError as e:
            return {
                "success": False,
                "error": f"Clone failed: {e}",
            }
        except (OSError, shutil.Error) as e:
            return {
                "success": False,
                "error": f"Failed to copy modules: {e}",
            }

    def pull(self) -> dict[str, Any]:
        """Pull latest changes from the repository (or clone if missing)."""
        if not self.is_repo_cloned():
            _LOGGER.info("Repository not found, performing fresh clone")
            return self.clone()

        try:
            # Clone to temp and copy (same as clone, but overwrites)
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "repo"

                _LOGGER.info("Fetching latest PaddiSense updates...")
                result = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--branch",
                        self.branch,
                        "--single-branch",
                        "--depth",
                        "1",
                        self.repo_url,
                        str(temp_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode != 0:
                    _LOGGER.error("Git fetch failed: %s", result.stderr)
                    return {
                        "success": False,
                        "error": f"Fetch failed: {result.stderr}",
                    }

                # Check if modules are in a subfolder
                modules_source = temp_path / REPO_MODULES_SUBFOLDER
                if modules_source.is_dir():
                    source_dir = modules_source
                else:
                    source_dir = temp_path

                # Backup existing packages folder (preserve installed modules)
                existing_packages = None
                packages_dir = self.repo_dir / "packages"
                if packages_dir.exists():
                    existing_packages = Path(temp_dir) / "packages_backup"
                    shutil.copytree(packages_dir, existing_packages)
                    _LOGGER.info("Backed up existing packages folder")

                # Remove old modules and copy new
                if self.repo_dir.exists():
                    shutil.rmtree(self.repo_dir)

                # Copy new modules, excluding packages folder from repo
                def ignore_packages(dir, files):
                    if Path(dir).name == "PaddiSense" or dir == str(source_dir):
                        return ["packages"] if "packages" in files else []
                    return []

                shutil.copytree(source_dir, self.repo_dir, ignore=ignore_packages)

                # Restore packages folder
                if existing_packages and existing_packages.exists():
                    shutil.copytree(existing_packages, packages_dir)
                    _LOGGER.info("Restored packages folder")
                else:
                    packages_dir.mkdir(exist_ok=True)

                _LOGGER.info("Updated modules at %s", self.repo_dir)

            _LOGGER.info("Successfully pulled latest changes")
            return {
                "success": True,
                "message": "Repository updated successfully",
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Pull timed out. Check your network connection.",
            }
        except subprocess.SubprocessError as e:
            return {
                "success": False,
                "error": f"Pull failed: {e}",
            }
        except (OSError, shutil.Error) as e:
            return {
                "success": False,
                "error": f"Failed to update modules: {e}",
            }

    def get_local_version(self) -> str | None:
        """Get the local version from VERSION file."""
        if not PADDISENSE_VERSION_FILE.exists():
            return None
        try:
            return PADDISENSE_VERSION_FILE.read_text(encoding="utf-8").strip()
        except IOError:
            return None

    def get_remote_version(self) -> str | None:
        """Get the latest version from remote repository."""
        try:
            # Clone minimal to temp and read VERSION
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "repo"

                result = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--branch",
                        self.branch,
                        "--single-branch",
                        "--depth",
                        "1",
                        self.repo_url,
                        str(temp_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode != 0:
                    return None

                # Check subfolder first
                version_file = temp_path / REPO_MODULES_SUBFOLDER / "VERSION"
                if not version_file.exists():
                    version_file = temp_path / "VERSION"

                if version_file.exists():
                    return version_file.read_text(encoding="utf-8").strip()
                return None

        except (subprocess.SubprocessError, IOError):
            return None

    def check_for_updates(self) -> dict[str, Any]:
        """Check if updates are available."""
        local_version = self.get_local_version()
        remote_version = self.get_remote_version()

        if local_version is None:
            return {
                "success": False,
                "error": "Local version not found",
                "update_available": False,
            }

        if remote_version is None:
            return {
                "success": False,
                "error": "Could not fetch remote version",
                "update_available": False,
                "local_version": local_version,
            }

        update_available = remote_version != local_version

        return {
            "success": True,
            "local_version": local_version,
            "remote_version": remote_version,
            "update_available": update_available,
        }

    def get_commit_info(self) -> dict[str, Any]:
        """Get current commit information."""
        # Since we don't keep .git, return version info instead
        version = self.get_local_version()
        return {
            "version": version or "unknown",
            "commit": "N/A (shallow copy)",
            "date": "N/A",
        }

    def verify_repo_integrity(self) -> dict[str, Any]:
        """Verify the repository is in good state."""
        if not self.is_repo_cloned():
            return {
                "success": False,
                "error": "Repository not found",
            }

        checks = {
            "version_file_exists": PADDISENSE_VERSION_FILE.exists(),
            "modules_json_exists": (self.repo_dir / "modules.json").exists(),
            "ipm_exists": (self.repo_dir / "ipm").is_dir(),
        }

        all_passed = all(checks.values())

        return {
            "success": all_passed,
            "checks": checks,
            "error": None if all_passed else "Repository integrity check failed",
        }
