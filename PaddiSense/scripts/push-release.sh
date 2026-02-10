#!/bin/bash
#
# Push staged releases to the release repository
#
# Usage:
#   ./push-release.sh                    # Push all staged modules
#   ./push-release.sh weather            # Push only weather
#   ./push-release.sh --init             # Initialize release repo structure
#

PADDISENSE_DIR="/config/PaddiSense"
STAGING_DIR="$PADDISENSE_DIR/github-repo/release-staging"
RELEASE_REPO="$PADDISENSE_DIR/github-repo"
MODULES_DIR="$RELEASE_REPO/PaddiSense"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cmd_init() {
    log_info "Initializing release repo structure..."

    # Create modules directory
    mkdir -p "$MODULES_DIR"

    # Create release modules.json
    if [[ ! -f "$MODULES_DIR/modules.json" ]]; then
        cat > "$MODULES_DIR/modules.json" << 'EOF'
{
  "schema_version": "1.0.0",
  "version": "1.0.0-dev",
  "released": "",
  "modules": {}
}
EOF
        log_success "Created modules.json"
    fi

    # Create VERSION
    if [[ ! -f "$MODULES_DIR/VERSION" ]]; then
        echo "1.0.0-dev" > "$MODULES_DIR/VERSION"
        log_success "Created VERSION"
    fi

    # Create empty packages directory (growers will have symlinks here)
    mkdir -p "$MODULES_DIR/packages"
    touch "$MODULES_DIR/packages/.gitkeep"

    log_success "Release repo structure initialized at $MODULES_DIR"
    echo ""
    echo "Structure:"
    ls -la "$MODULES_DIR"
}

push_module() {
    local module=$1
    local staged_path="$STAGING_DIR/$module"
    local release_path="$MODULES_DIR/$module"

    if [[ ! -d "$staged_path" ]]; then
        log_error "No staged release found for '$module'"
        log_error "Run: ./release-module.sh $module"
        return 1
    fi

    log_info "Pushing $module to release repo..."

    # Remove old version if exists
    if [[ -d "$release_path" ]]; then
        rm -rf "$release_path"
    fi

    # Copy staged to release
    cp -r "$staged_path" "$release_path"

    # Get version
    local version=$(cat "$release_path/VERSION")

    log_success "Pushed $module v$version to $release_path"

    # Update modules.json
    update_release_manifest "$module" "$version"

    # Clean up staging
    rm -rf "$staged_path"
    log_info "Cleaned up staging for $module"
}

update_release_manifest() {
    local module=$1
    local version=$2
    local manifest="$MODULES_DIR/modules.json"
    local timestamp=$(date -Iseconds)

    # Use Python to update JSON properly
    python3 << EOF
import json
from pathlib import Path

manifest_path = Path("$manifest")
data = json.loads(manifest_path.read_text())

# Get module metadata from dev modules.json
dev_manifest = Path("$PADDISENSE_DIR/modules.json")
dev_data = json.loads(dev_manifest.read_text())
module_meta = dev_data.get("modules", {}).get("$module", {})

# Update release manifest
data["modules"]["$module"] = {
    "name": module_meta.get("name", "$module"),
    "description": module_meta.get("description", ""),
    "icon": module_meta.get("icon", "mdi:package"),
    "version": "$version",
    "released": "$timestamp",
    "dashboard_slug": module_meta.get("dashboard_slug", "$module-dashboard"),
    "dashboard_title": module_meta.get("dashboard_title", "$module"),
    "dashboard_file": module_meta.get("dashboard_file", "$module/dashboards/views.yaml"),
    "dependencies": module_meta.get("dependencies", [])
}

data["released"] = "$timestamp"

manifest_path.write_text(json.dumps(data, indent=2))
print("Updated modules.json")
EOF
}

cmd_push_all() {
    if [[ ! -d "$STAGING_DIR" ]] || [[ -z "$(ls -A "$STAGING_DIR" 2>/dev/null)" ]]; then
        log_warn "No staged modules found"
        log_info "Stage modules first with: ./release-module.sh <module>"
        return 0
    fi

    log_info "Pushing all staged modules..."
    echo ""

    for module_dir in "$STAGING_DIR"/*/; do
        [[ ! -d "$module_dir" ]] && continue
        module=$(basename "$module_dir")
        push_module "$module"
        echo ""
    done

    log_success "All modules pushed"
    echo ""
    log_info "Next steps:"
    echo "  cd $RELEASE_REPO"
    echo "  git add PaddiSense/"
    echo "  git commit -m 'Release modules $(date +%Y-%m-%d)'"
    echo "  git push origin main"
}

cmd_push_one() {
    local module=$1
    push_module "$module"
    echo ""
    log_info "Next steps:"
    echo "  cd $RELEASE_REPO"
    echo "  git add PaddiSense/$module"
    echo "  git commit -m 'Release $module v$(cat "$MODULES_DIR/$module/VERSION")'"
    echo "  git push origin main"
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-}" in
    --init|-i)
        cmd_init
        ;;
    --help|-h)
        echo ""
        echo "Push Staged Releases"
        echo ""
        echo "Usage:"
        echo "  $0                  Push all staged modules"
        echo "  $0 <module>         Push specific module"
        echo "  $0 --init           Initialize release repo structure"
        echo ""
        ;;
    "")
        cmd_push_all
        ;;
    *)
        cmd_push_one "$1"
        ;;
esac
