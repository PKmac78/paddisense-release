#!/bin/bash
#
# PaddiSense Module Release Script
#
# Usage:
#   ./release-module.sh <module_name> [version]
#
# Examples:
#   ./release-module.sh weather              # Release with current version
#   ./release-module.sh weather 1.0.0        # Release with specific version
#   ./release-module.sh --list               # List modules and their status
#   ./release-module.sh --status             # Show release readiness
#

# Don't use set -e as arithmetic operations can return non-zero
# set -e

# Configuration
PADDISENSE_DIR="/config/PaddiSense"
RELEASE_DIR="/config/PaddiSense/github-repo/release-staging"
MODULES_JSON="$PADDISENSE_DIR/modules.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get module status from modules.json
get_module_status() {
    local module=$1
    python3 -c "
import json
with open('$MODULES_JSON') as f:
    data = json.load(f)
    mod = data.get('modules', {}).get('$module', {})
    print(mod.get('status', 'unknown'))
" 2>/dev/null || echo "unknown"
}

# Get module version from VERSION file
get_module_version() {
    local module=$1
    local version_file="$PADDISENSE_DIR/$module/VERSION"
    if [[ -f "$version_file" ]]; then
        cat "$version_file"
    else
        echo "unknown"
    fi
}

# Check if module can be released
can_release() {
    local status=$1
    case "$status" in
        rc|stable|release)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# =============================================================================
# COMMANDS
# =============================================================================

cmd_list() {
    echo ""
    echo "PaddiSense Modules"
    echo "=================="
    echo ""
    printf "%-12s %-15s %-10s %-10s\n" "MODULE" "VERSION" "STATUS" "RELEASABLE"
    printf "%-12s %-15s %-10s %-10s\n" "------" "-------" "------" "----------"

    for module_dir in "$PADDISENSE_DIR"/*/; do
        module=$(basename "$module_dir")

        # Skip non-module directories
        [[ "$module" == "scripts" ]] && continue
        [[ "$module" == "packages" ]] && continue
        [[ "$module" == "docs" ]] && continue
        [[ "$module" == "reference" ]] && continue
        [[ "$module" == "github-repo" ]] && continue
        [[ "$module" == "pumps_channels" ]] && continue

        # Check if it has a VERSION file (indicates it's a module)
        [[ ! -f "$module_dir/VERSION" ]] && continue

        version=$(get_module_version "$module")
        status=$(get_module_status "$module")

        if can_release "$status"; then
            releasable="${GREEN}yes${NC}"
        else
            releasable="${RED}no${NC}"
        fi

        printf "%-12s %-15s %-10s " "$module" "$version" "$status"
        echo -e "$releasable"
    done
    echo ""
}

cmd_status() {
    echo ""
    echo "Release Readiness Check"
    echo "======================="
    echo ""

    local ready_count=0
    local not_ready_count=0

    for module_dir in "$PADDISENSE_DIR"/*/; do
        module=$(basename "$module_dir")

        # Skip non-module directories
        [[ "$module" == "scripts" ]] && continue
        [[ "$module" == "packages" ]] && continue
        [[ "$module" == "docs" ]] && continue
        [[ "$module" == "reference" ]] && continue
        [[ "$module" == "github-repo" ]] && continue
        [[ "$module" == "pumps_channels" ]] && continue
        [[ ! -f "$module_dir/VERSION" ]] && continue

        version=$(get_module_version "$module")
        status=$(get_module_status "$module")

        echo -n "  $module ($version): "

        # Check requirements
        local issues=()

        # Check VERSION file
        [[ ! -f "$module_dir/VERSION" ]] && issues+=("missing VERSION")

        # Check package.yaml
        [[ ! -f "$module_dir/package.yaml" ]] && issues+=("missing package.yaml")

        # Check dashboards
        [[ ! -d "$module_dir/dashboards" ]] && issues+=("missing dashboards/")

        # Check status
        if ! can_release "$status"; then
            issues+=("status is '$status' (needs 'rc' or 'stable')")
        fi

        if [[ ${#issues[@]} -eq 0 ]]; then
            echo -e "${GREEN}Ready to release${NC}"
            ((ready_count++))
        else
            echo -e "${RED}Not ready${NC}"
            for issue in "${issues[@]}"; do
                echo "    - $issue"
            done
            ((not_ready_count++))
        fi
    done

    echo ""
    echo "Summary: $ready_count ready, $not_ready_count not ready"
    echo ""
}

cmd_release() {
    local module=$1
    local new_version=$2

    local module_dir="$PADDISENSE_DIR/$module"

    # Validate module exists
    if [[ ! -d "$module_dir" ]]; then
        log_error "Module '$module' not found at $module_dir"
        exit 1
    fi

    # Check VERSION file
    if [[ ! -f "$module_dir/VERSION" ]]; then
        log_error "Module '$module' has no VERSION file"
        exit 1
    fi

    # Get current version
    local current_version=$(get_module_version "$module")
    local version="${new_version:-$current_version}"

    # Check status
    local status=$(get_module_status "$module")
    if ! can_release "$status"; then
        log_error "Module '$module' has status '$status' - cannot release"
        log_error "Update modules.json status to 'rc' or 'stable' first"
        exit 1
    fi

    # Check required files
    if [[ ! -f "$module_dir/package.yaml" ]]; then
        log_error "Module '$module' has no package.yaml"
        exit 1
    fi

    log_info "Preparing release for $module v$version"
    echo ""

    # Create release staging directory
    mkdir -p "$RELEASE_DIR/$module"

    # Update VERSION if new version specified
    if [[ -n "$new_version" ]]; then
        echo "$new_version" > "$module_dir/VERSION"
        log_info "Updated VERSION to $new_version"
    fi

    # Copy module files to staging
    log_info "Copying module files..."

    # Copy package.yaml
    cp "$module_dir/package.yaml" "$RELEASE_DIR/$module/"
    log_success "  package.yaml"

    # Copy VERSION
    cp "$module_dir/VERSION" "$RELEASE_DIR/$module/"
    log_success "  VERSION"

    # Copy dashboards if exists
    if [[ -d "$module_dir/dashboards" ]]; then
        cp -r "$module_dir/dashboards" "$RELEASE_DIR/$module/"
        log_success "  dashboards/"
    fi

    # Copy python backend if exists
    if [[ -d "$module_dir/python" ]]; then
        cp -r "$module_dir/python" "$RELEASE_DIR/$module/"
        log_success "  python/"
    fi

    # Copy www (frontend assets) if exists
    if [[ -d "$module_dir/www" ]]; then
        cp -r "$module_dir/www" "$RELEASE_DIR/$module/"
        log_success "  www/"
    fi

    # Copy templates if exists
    if [[ -d "$module_dir/templates" ]]; then
        cp -r "$module_dir/templates" "$RELEASE_DIR/$module/"
        log_success "  templates/"
    fi

    echo ""
    log_success "Module staged at: $RELEASE_DIR/$module"
    echo ""

    # Create release manifest entry
    log_info "Release manifest entry:"
    echo ""
    echo "  \"$module\": {"
    echo "    \"version\": \"$version\","
    echo "    \"status\": \"$status\","
    echo "    \"released\": \"$(date -Iseconds)\""
    echo "  }"
    echo ""

    log_info "Next steps:"
    echo "  1. Review staged files at $RELEASE_DIR/$module"
    echo "  2. Copy to your release repo"
    echo "  3. Commit and push: git commit -m 'Release $module v$version'"
    echo "  4. Tag the release: git tag $module-v$version"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-}" in
    --list|-l)
        cmd_list
        ;;
    --status|-s)
        cmd_status
        ;;
    --help|-h|"")
        echo ""
        echo "PaddiSense Module Release Script"
        echo ""
        echo "Usage:"
        echo "  $0 <module_name> [version]  Release a module"
        echo "  $0 --list                   List all modules"
        echo "  $0 --status                 Check release readiness"
        echo "  $0 --help                   Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 weather                  Release weather with current version"
        echo "  $0 weather 1.0.0            Release weather as v1.0.0"
        echo "  $0 hfm 2.0.0                Release hfm as v2.0.0"
        echo ""
        ;;
    *)
        cmd_release "$1" "${2:-}"
        ;;
esac
