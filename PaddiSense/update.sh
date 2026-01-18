#!/bin/bash
#
# PaddiSense Updater
# ==================
# Pulls latest code from git without touching local data
#
# Usage:
#   ./PaddiSense/update.sh              # Update and show changes
#   ./PaddiSense/update.sh --backup     # Backup data before updating
#   ./PaddiSense/update.sh --dry-run    # Show what would be updated
#   ./PaddiSense/update.sh --status     # Show current vs available versions
#

set -e

CONFIG_DIR="/config"
INSTALL_DIR="$CONFIG_DIR/PaddiSense"
DATA_DIR="$CONFIG_DIR/local_data"
BACKUP_DIR="$CONFIG_DIR/backups/paddisense"
SERVER_CONFIG="$CONFIG_DIR/server.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  PaddiSense Updater${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "    $1"
}

# Function to read version from file
get_version() {
    local version_file="$1"
    if [ -f "$version_file" ]; then
        cat "$version_file" | tr -d '\n'
    else
        echo "unknown"
    fi
}

# Function to check if module is enabled
is_module_enabled() {
    local module="$1"
    if [ -f "$SERVER_CONFIG" ]; then
        grep -E "^\s*${module}:\s*(true|yes)" "$SERVER_CONFIG" > /dev/null 2>&1
        return $?
    fi
    # If no server.yaml, default modules are ipm and asm
    if [ "$module" = "ipm" ] || [ "$module" = "asm" ]; then
        return 0
    fi
    return 1
}

# Function to check if module is installed
is_module_installed() {
    local module="$1"
    [ -d "$INSTALL_DIR/$module" ] && [ -f "$INSTALL_DIR/$module/package.yaml" ]
}

# Parse arguments
DO_BACKUP=false
DRY_RUN=false
STATUS_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backup)
            DO_BACKUP=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --status)
            STATUS_ONLY=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

print_header

# Check if PaddiSense is installed
if [ ! -d "$INSTALL_DIR" ]; then
    print_error "PaddiSense not found in $INSTALL_DIR"
    echo "    Please run install.sh first"
    exit 1
fi

# Check if it's a git repository
if [ ! -d "$INSTALL_DIR/.git" ] && [ ! -d "$CONFIG_DIR/.git" ]; then
    print_warn "Not a git repository"
    echo ""
    echo "For automatic updates, PaddiSense should be managed with git."
    echo "Manual update: Download the latest release and extract to $INSTALL_DIR"
    exit 1
fi

# Show current versions
echo ""
print_step "Current installed versions:"
for module in ipm asm weather weather_api; do
    if is_module_installed "$module"; then
        ver=$(get_version "$INSTALL_DIR/$module/VERSION")
        enabled=""
        if is_module_enabled "$module"; then
            enabled="${GREEN}(enabled)${NC}"
        else
            enabled="${YELLOW}(disabled)${NC}"
        fi
        echo -e "    $module: v$ver $enabled"
    fi
done

# Fetch latest from git
echo ""
print_step "Fetching latest from remote..."

# Determine if we're in PaddiSense dir or config dir
GIT_DIR="$INSTALL_DIR"
if [ -d "$CONFIG_DIR/.git" ]; then
    GIT_DIR="$CONFIG_DIR"
fi

cd "$GIT_DIR"
git fetch origin 2>/dev/null || {
    print_error "Failed to fetch from remote"
    exit 1
}

# Check for updates
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
    print_step "Already up to date!"
    echo ""
    exit 0
fi

# Show what's changed
echo ""
print_step "Changes available:"
git log --oneline HEAD..origin/main 2>/dev/null || git log --oneline HEAD..origin/master 2>/dev/null | head -10

if [ "$STATUS_ONLY" = true ]; then
    echo ""
    echo "Run without --status to apply updates"
    exit 0
fi

if [ "$DRY_RUN" = true ]; then
    echo ""
    print_warn "Dry run - no changes made"
    echo ""
    echo "Files that would be updated:"
    git diff --name-only HEAD..origin/main 2>/dev/null || git diff --name-only HEAD..origin/master 2>/dev/null
    exit 0
fi

# Optional backup
if [ "$DO_BACKUP" = true ]; then
    echo ""
    print_step "Creating backup..."
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"

    # Backup data files
    if [ -d "$DATA_DIR" ]; then
        tar -czf "$BACKUP_DIR/data_$TIMESTAMP.tar.gz" \
            -C "$CONFIG_DIR" local_data 2>/dev/null || true
        print_info "Data backup: $BACKUP_DIR/data_$TIMESTAMP.tar.gz"
    fi
fi

# Pull updates
echo ""
print_step "Pulling updates..."
git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
    print_error "Failed to pull updates"
    print_info "You may have local changes. Try: git stash && ./PaddiSense/update.sh"
    exit 1
}

# Set permissions
echo ""
print_step "Setting permissions..."
chmod +x "$INSTALL_DIR/"*.sh 2>/dev/null || true
for module in ipm asm weather weather_api; do
    if [ -d "$INSTALL_DIR/$module/python" ]; then
        chmod +x "$INSTALL_DIR/$module/python/"*.py 2>/dev/null || true
    fi
done

# Show updated versions
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Update Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

print_step "Updated versions:"
for module in ipm asm weather weather_api; do
    if is_module_installed "$module"; then
        ver=$(get_version "$INSTALL_DIR/$module/VERSION")
        enabled=""
        if is_module_enabled "$module"; then
            enabled="${GREEN}(enabled)${NC}"
        else
            enabled="${YELLOW}(disabled)${NC}"
        fi
        echo -e "    $module: v$ver $enabled"
    fi
done

echo ""
print_info "Your local data in $DATA_DIR was NOT modified."
echo ""

# Show protected data
echo "Protected data directories:"
for module in ipm asm weather_api; do
    if [ -d "$DATA_DIR/$module" ]; then
        echo "  - $DATA_DIR/$module/"
    fi
done
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Check release notes for any required configuration changes"
echo "  2. Restart Home Assistant to apply updates"
echo "  3. Verify module versions in Settings pages"
echo ""
