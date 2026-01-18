#!/bin/bash
#
# PaddiSense Installer
# ====================
# Installs PaddiSense modules for Home Assistant
#
# Usage:
#   Fresh install from git:
#     git clone https://github.com/YOUR_USER/paddisense.git /config/PaddiSense
#     cp PaddiSense/server.yaml.example server.yaml  # Edit this!
#     ./PaddiSense/install.sh
#
#   Install specific module:
#     ./PaddiSense/install.sh ipm
#     ./PaddiSense/install.sh asm
#     ./PaddiSense/install.sh weather
#
#   Install all enabled modules from server.yaml:
#     ./PaddiSense/install.sh
#

set -e

CONFIG_DIR="/config"
INSTALL_DIR="$CONFIG_DIR/PaddiSense"
DATA_DIR="$CONFIG_DIR/local_data"
SERVER_CONFIG="$CONFIG_DIR/server.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  PaddiSense Installer${NC}"
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

# Function to check if module is enabled in server.yaml
is_module_enabled() {
    local module="$1"
    if [ -f "$SERVER_CONFIG" ]; then
        # Parse YAML - look for "module: true" pattern
        grep -E "^\s*${module}:\s*(true|yes)" "$SERVER_CONFIG" > /dev/null 2>&1
        return $?
    fi
    return 1
}

# Function to install a module
install_module() {
    local module="$1"
    local module_dir="$INSTALL_DIR/$module"
    local data_dir="$DATA_DIR/$module"

    if [ ! -d "$module_dir" ]; then
        print_error "Module not found: $module_dir"
        return 1
    fi

    local version=$(get_version "$module_dir/VERSION")
    echo ""
    print_step "Installing $module v$version"

    # Create data directory if module uses one
    if [ "$module" = "ipm" ] || [ "$module" = "asm" ] || [ "$module" = "weather" ]; then
        mkdir -p "$data_dir"
        mkdir -p "$data_dir/backups"
        print_info "Data directory: $data_dir"
    fi

    # Set permissions on Python scripts
    if [ -d "$module_dir/python" ]; then
        chmod +x "$module_dir/python/"*.py 2>/dev/null || true
    fi

    # Module-specific checks
    case "$module" in
        weather)
            print_info "Unified weather module supports:"
            print_info "  - Local Ecowitt gateway (auto-detected)"
            print_info "  - Remote API stations (requires API credentials)"
            if ! grep -q "ecowitt_app_key" "$CONFIG_DIR/secrets.yaml" 2>/dev/null; then
                print_warn "For API stations: add ecowitt_app_key to secrets.yaml"
            fi
            if ! grep -q "ecowitt_api_key" "$CONFIG_DIR/secrets.yaml" 2>/dev/null; then
                print_warn "For API stations: add ecowitt_api_key to secrets.yaml"
            fi
            ;;
    esac

    INSTALLED_MODULES+=("$module:v$version")
}

# Parse command line
MODULE="${1:-}"

print_header

# Check we're in the right place
if [ ! -f "$CONFIG_DIR/configuration.yaml" ]; then
    print_error "configuration.yaml not found in $CONFIG_DIR"
    echo "    Please run from your Home Assistant config directory"
    exit 1
fi

if [ ! -d "$INSTALL_DIR" ]; then
    print_error "PaddiSense not found in $INSTALL_DIR"
    echo "    Clone the repository first:"
    echo "    git clone https://github.com/YOUR_USER/paddisense.git $INSTALL_DIR"
    exit 1
fi

# Track what we install
INSTALLED_MODULES=()

# Determine what to install
if [ -n "$MODULE" ]; then
    # Specific module requested
    echo ""
    print_step "Installing specific module: $MODULE"
    install_module "$MODULE"
else
    # Install based on server.yaml
    if [ -f "$SERVER_CONFIG" ]; then
        echo ""
        print_step "Reading configuration from server.yaml"

        for mod in ipm asm weather; do
            if is_module_enabled "$mod"; then
                install_module "$mod"
            fi
        done
    else
        # No server.yaml - install defaults (ipm and asm)
        print_warn "No server.yaml found - installing default modules (ipm, asm)"
        echo ""
        print_info "Create server.yaml for custom module selection:"
        print_info "  cp PaddiSense/server.yaml.example server.yaml"

        install_module "ipm"
        install_module "asm"
    fi
fi

# Set script permissions
chmod +x "$INSTALL_DIR/"*.sh 2>/dev/null || true

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Installation Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

if [ ${#INSTALLED_MODULES[@]} -eq 0 ]; then
    print_warn "No modules were installed"
    echo ""
    echo "Enable modules in server.yaml or specify a module:"
    echo "  ./PaddiSense/install.sh ipm"
    exit 0
fi

echo "Installed modules:"
for m in "${INSTALLED_MODULES[@]}"; do
    echo "  - $m"
done

# Generate configuration.yaml snippet
echo ""
echo -e "${YELLOW}Add to your configuration.yaml:${NC}"
echo ""
echo "homeassistant:"
echo "  packages:"

for m in "${INSTALLED_MODULES[@]}"; do
    mod=$(echo "$m" | cut -d: -f1)
    echo "    $mod: !include PaddiSense/$mod/package.yaml"
done

echo ""
echo "lovelace:"
echo "  mode: storage"
echo "  dashboards:"

for m in "${INSTALLED_MODULES[@]}"; do
    mod=$(echo "$m" | cut -d: -f1)
    case "$mod" in
        ipm)
            echo "    ipm-inventory:"
            echo "      mode: yaml"
            echo "      title: Inventory Manager"
            echo "      icon: mdi:warehouse"
            echo "      show_in_sidebar: true"
            echo "      filename: PaddiSense/ipm/dashboards/inventory.yaml"
            ;;
        asm)
            echo "    asm-service:"
            echo "      mode: yaml"
            echo "      title: Asset Service Manager"
            echo "      icon: mdi:tractor"
            echo "      show_in_sidebar: true"
            echo "      filename: PaddiSense/asm/dashboards/views.yaml"
            ;;
        weather)
            echo "    weather-station:"
            echo "      mode: yaml"
            echo "      title: Weather"
            echo "      icon: mdi:weather-cloudy"
            echo "      show_in_sidebar: true"
            echo "      filename: PaddiSense/weather/dashboards/views.yaml"
            ;;
    esac
done

echo ""
echo -e "${YELLOW}Required HACS frontend cards:${NC}"
echo "  - button-card"
echo "  - card-mod"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update configuration.yaml with the snippet above"
echo "  2. Install required HACS cards"
echo "  3. Restart Home Assistant"
echo "  4. Open each dashboard and click 'Initialize System' in Settings"
echo ""
