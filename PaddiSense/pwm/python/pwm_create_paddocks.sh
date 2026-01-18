#!/bin/bash
###################################################################################################
# FILE: pwm_create_new_paddock_complete.sh
# VERSION: 2025.12-04
# DATE: 2025-12-31
#
# PURPOSE
#   One-stop script to:
#     1. Register a paddock and its bays in paddock_list.json
#     2. Generate the paddock-level YAML (automation state, drain control, supply depth, etc.)
#     3. Generate one bay-helper YAML file per bay
#     4. Generate a default Lovelace dashboard block for the paddock and its bays
#
# TYPICAL USAGE
#   /bin/bash pwm_create_new_paddock_complete.sh "Field Name" "B-" 5 [--overwrite] [--prune-bays] [--start 1] \
#       [--pad 2] [--json "/config/RRAPL/JSON Files/paddock_list.json"] \
#       [--outdir "/config/RRAPL/YAMLS"]
#
# ARGUMENTS
#   "Field Name"   Human readable paddock name (e.g., "SW5", "Sheepwash 5")
#   "B-"           Bay prefix (e.g., "B-" gives B-01, B-02, ... B-NN)
#   TOTAL_BAYS     Number of numbered bays (not including drain; drain is auto-added)
#
# OPTIONAL FLAGS
#   --overwrite / --force   Overwrite existing JSON entry for paddock (do not preserve bay list)
#   --prune / --prune-bays  Truncate paddock to exactly TOTAL_BAYS:
#                           - JSON entry rebuilt for the new range
#                           - Extra bay-helper YAMLs for higher bays are removed
#   --start N               First bay number (default: 1 → B-01)
#   --pad W                 Zero-pad width (default: max(2, digits(TOTAL_BAYS)))
#   --json PATH             Location of paddock_list.json
#   --outdir DIR            Where YAML helper files are written
#
# BEHAVIOUR OVERVIEW
#   1) JSON update:
#      - Ensures paddock_list.json exists and is valid JSON.
#      - Creates or updates paddock entry:
#          "enabled": true
#          "automation_state_individual": false
#          B-01..B-NN, plus final "B-NN Drain"
#      - Preserves existing device assignments for bays when possible.
#      - Uses jq if available; otherwise falls back to Python.
#
#   2) Paddock-level YAML:
#      - Creates pwm_paddock_<field_slug>.yaml
#      - Defines:
#          * <field>_automation_state
#          * <field>_drain_door_control
#          * <field>_supply_waterleveloffset
#          * Template sensor for supply water depth (B-01)
#          * Automations for door control & propagating paddock automation state.
#
#   3) Dashboard YAML:
#      - Creates a basic Lovelace config for:
#          * A picture-elements card with supply + bay depth badges
#          * A vertical stack with:
#              - field automation state control
#              - inlet controls for each bay
#              - drain control
#              - link to an "Extra Data" subview.
#
#   4) Bay helper YAMLs:
#      - For each bay, creates pwm_paddock_helpers_<field_slug>_<bay_slug>.yaml
#      - Defines:
#          * door control & automation state input_selects
#          * level min/max/offset input_numbers
#          * flush-active boolean
#          * Depth template sensor (calculating next bay or drain device)
#          * Full irrigation automation: Flush / Pond / Drain logic, plus timers.
#
# REQUIREMENTS
#   - bash
#   - jq (preferred) OR python3 for JSON handling
#
# VERSION HISTORY
#   2025.11-00  (2025-11-16)
#       - Initial documented version.
#       - Stable JSON paddock list updates with metadata + bay ranges.
#       - Generates paddock-level YAML, dashboard YAML, and per-bay helper YAMLs.
#       - Supports variable bay numbering and padding (e.g., B-01, B-001, etc.).
#   2025.11-01  (2025-11-16)
#       - Added --prune / --prune-bays option.
#       - When pruning, JSON paddock entry is rebuilt for the new bay range.
#       - Bay helper YAMLs above the new max bay index are removed.
#   2025.11-02  (2025-11-16)
#       - Added per-bay "Flush Deactivate On Off" automation.
#       - Whenever a bay's automation_state goes to Off, its flushactive boolean is forced Off.
#       - This keeps bay state consistent even when automation_state is changed manually.
#   2025.11-03  (2025-11-19)
#       - Added automation to turn off paddock level automation state when all bays automation
#         states turn 'Off', only when it wasn't off already and the paddocks
#         automation_state_individual is 'false'
#   2025.11-04  (2025-11-19)
#       - Adjusted prune section to remove helper files that are deleted bays
#   2025.11-05  (2025-11-20)
#       - Added version variable to be inserted at the top of all generated YAML files
#       - Re-worked door control automation to include better support for "Spur" door controls
#         and "Channel Supply" door controls
#   2025.11-06  (2025-11-21)
#       - Added for timer setting on water level min max changes in bay irrigation automation
#           -> delays automation triggering for 5 minutes after number change
#       - Changed Flush Deactivate automation to trigger on automation state change "Flush" -> Any
#         (was Any -> "Off")
#   2025.11-07  (2025-11-24)
#       - Changes in Irrigation Automation
#           > In maintenance mode, all bays control only their supply door during adding water and holding position,
#             except bottom bay which can also control drain door
#           > In maintenance mode, first bay no longer closes stop when supply water level is lower than bay water level,
#             now continues to open door but also sends a notification that the supply channel needs water.
#       - Repurposed Flush Activate automation -> Automation Setup automation. Does everything Flush Activate did
#         but also sets up bay for maintenance mode
#           > Opens bays supply door
#           > Closes bays drain door IF BAY IS FINAL BAY
#           > Notifies users
#       - Changes to Flush Close Supply automation
#           > Triggers on set flush time on water timer finish (default bay 2)
#           > Starts new timer called timer.<paddock>_flushclosesupply and waits for it to finish
#           > Then sends notification to suggest closing B-01's supply
#           > Keeps disabled closing of first bays supply door action
#   2025.12-01  (2025-12-12)
#       - Disabled all notifications around irrigation automation - Too many especially in blocks with lots of bays
#       - Added paddock level version sensor for version tracking
#   2025.12-02  (2025-12-13)
#       - Irrigation automation: replaced 3 threshold-based numeric_state triggers (Above/Below/Optimal)
#         with a single time_pattern trigger (every 3 minutes).
#       - Keeps existing Home Assistant start trigger(s) and all other triggers intact.
#       - Rationale: numeric_state triggers do not repeatedly fire while the sensor remains above/below;
#         a periodic trigger ensures consistent re-evaluation of water control logic.
#   2025.12-03  (2025-12-23)
#       - Changed "Maintain" automation state to "Pond" as more accurately reflects the intention of the user
#       - Added a "HoldOne" action before a door control is set to "Open" or "Close"
#           > Ensures that the door controls state and the physical door are in sync
#   2025.12-04  (2025-12-31)
#       - Changed trigger time to 10 mins to reduce trigger volumes and build some buffer in water heights
#       - Bug Fix HoldOne typo in flush release water section
###################################################################################################

# Safety flags:
#   -e : exit on error
#   -u : error on unset variable
#   -o pipefail : fail if any command in a pipeline fails
set -euo pipefail

########################################
#           DEFAULT SETTINGS           #
########################################
JSON_DEFAULT="/config/RRAPL/JSON Files/paddock_list.json"
OUTDIR_DEFAULT="/config/RRAPL/YAMLS"
DASHBOARD_DEFAULT="/config/RRAPL/Dashboards"

START_DEFAULT=1          # First bay number (1 → B-01)
PAD_DEFAULT=""           # If empty, compute as max(2, digits(TOTAL_BAYS))
OVERWRITE=0              # Whether to overwrite JSON paddock mapping
PRUNE_BAYS=0             # Whether to prune bays above TOTAL_BAYS and remove extra helpers
VERSION="v2025.12-04"    # Version variable embedded into generated YAML headers

########################################
#       BASIC ARGUMENT PARSING         #
########################################
if [ "$#" -lt 3 ]; then
  echo "[ERROR] Usage: $0 \"Field Name\" \"B-\" <TOTAL_BAYS> [--overwrite] [--prune-bays] [--start N] [--pad W] [--json PATH] [--outdir DIR]" >&2
  exit 2
fi

FIELD_NAME="$1"; shift
BAY_PREFIX="$1"; shift
TOTAL_BAYS="$1"; shift

START="$START_DEFAULT"
PAD="$PAD_DEFAULT"
JSON_PATH="$JSON_DEFAULT"
OUTDIR="$OUTDIR_DEFAULT"
DASHBOARD_PATH="$DASHBOARD_DEFAULT"

# Parse remaining flags (order-insensitive)
while [ "${1-}" != "" ]; do
  case "$1" in
    --overwrite|--force)
      OVERWRITE=1
      ;;
    --prune|--prune-bays)
      PRUNE_BAYS=1
      ;;
    --start)
      shift
      START="${1:?--start requires a value}"
      ;;
    --pad)
      shift
      PAD="${1:?--pad requires a value}"
      ;;
    --json)
      shift
      JSON_PATH="${1:?--json requires a path}"
      ;;
    --outdir)
      shift
      OUTDIR="${1:?--outdir requires a path}"
      ;;
    *)
      echo "[WARN] Ignoring unknown option: $1" >&2
      ;;
  esac
  shift || true
done

# If pruning bays, rebuild JSON entry to exactly match the new bay range.
if [ "$PRUNE_BAYS" -eq 1 ]; then
  OVERWRITE=1
fi

########################################
#  CONDITIONAL APPEND HELPERS (Bays)   #
########################################
# These helpers allow us to include YAML fragments only when a previous/next bay exists.
# They avoid duplicated conditional branching inside heredocs.
incl_if_prev() {
  if [ "$HAS_PREV" -eq 1 ]; then
    cat >> "$FILEPATH"
  else
    cat >/dev/null
  fi
}

incl_if_next() {
  if [ "$HAS_NEXT" -eq 1 ]; then
    cat >> "$FILEPATH"
  else
    cat >/dev/null
  fi
}

########################################
#             VALIDATION               #
########################################
case "$TOTAL_BAYS" in
  ''|*[!0-9]* )
    echo "[ERROR] TOTAL_BAYS must be a positive integer" >&2
    exit 2
    ;;
esac

case "$START" in
  ''|*[!0-9]* )
    echo "[ERROR] --start must be a non-negative integer" >&2
    exit 2
    ;;
esac

if [ -n "$PAD" ]; then
  case "$PAD" in
    ''|*[!0-9]* )
      echo "[ERROR] --pad must be an integer" >&2
      exit 2
      ;;
  esac
fi

# Compute zero-pad width:
#   - If user did not specify PAD, use digits(TOTAL_BAYS), but at least 2.
if [ -z "$PAD" ]; then
  PAD="${#TOTAL_BAYS}"
  [ "$PAD" -lt 2 ] && PAD=2
fi

########################################
#        SMALL UTILITY FUNCTIONS       #
########################################
slugify() {
  local s
  s=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+|_+$//g')
  [ -n "$s" ] || s="unnamed_field"
  printf '%s' "$s"
}

to_upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }

########################################
#        SLUG / PATH PREPARATION       #
########################################
FIELD_SLUG="$(slugify "$FIELD_NAME")"
FIELD_PRETTY_UPPER="$(to_upper "$FIELD_NAME")"

mkdir -p "$(dirname "$JSON_PATH")" "$OUTDIR"

################################################################################
#                       JSON: paddock_list.json MANAGEMENT                     #
################################################################################
init_empty_json_if_missing() {
  if [ ! -f "$JSON_PATH" ]; then
    printf '{\n  "paddocks": {}\n}\n' > "$JSON_PATH"
  fi
}
init_empty_json_if_missing

JSON_DONE=0

if command -v jq >/dev/null 2>&1; then
  if ! jq empty "$JSON_PATH" >/dev/null 2>&1; then
    echo "[WARN] Existing JSON invalid. Reinitializing." >&2
    ts=$(date +%s); cp -p "$JSON_PATH" "$JSON_PATH.bak.$ts" 2>/dev/null || true
    printf '{\n  "paddocks": {}\n}\n' > "$JSON_PATH"
  fi

  if jq -e --arg k "$FIELD_SLUG" '(.paddocks // {}) | has($k)' "$JSON_PATH" >/dev/null; then
    if [ "$OVERWRITE" -ne 1 ]; then
      echo "[INFO] Paddock '$FIELD_SLUG' already exists in JSON. Use --overwrite or --prune-bays to replace." >&2
    fi
  fi

  existing_arr="$(jq -c --arg key "$FIELD_SLUG" '
    (.paddocks // {})[$key] // []
  ' "$JSON_PATH")"

  bays_json="$(jq -n \
    --arg prefix "$BAY_PREFIX" \
    --argjson total "$TOTAL_BAYS" \
    --argjson start "$START" \
    --argjson width "$PAD" \
    --argjson existing "$existing_arr" '
      def zpad(n; w): ((("000000000000000000000000000000000000" + (n|tostring)))[-w:]);
      def to_obj(x):
        if (x|type) == "array" then reduce x[] as $i ({}; . + $i)
        elif (x|type) == "object" then x
        else {} end;

      def normalize_device:
        if . == null then "unset"
        elif type == "string" then
          ( . | gsub("^\\s+|\\s+$"; "") | ascii_downcase ) as $s
          | if ($s == "" or $s == "none" or $s == "null")
            then "unset"
            else . end
        else . end;

      (to_obj($existing)) as $ex
      | ($ex.enabled | if . == null then true else . end) as $enabled
      | ($ex.automation_state_individual | if . == null then false else . end) as $auto_indiv
      | [ { "enabled": $enabled }
        , { "automation_state_individual": $auto_indiv }
        ] as $meta

      | [ range($start; ($start + $total))
          | ($prefix + zpad(.; $width)) as $k
          | ($ex[$k] // {}
              | .device |= normalize_device
            ) as $entry
          | { ($k): $entry }
        ] as $bays

      | ($start + $total - 1) as $last_num
      | ($prefix + zpad($last_num; $width)) as $last
      | ($ex[$last + " Drain"] // {}
          | .device |= normalize_device
        ) as $drain_entry
      | { ($last + " Drain"): $drain_entry } as $drain

      | $meta + $bays + [ $drain ]
    ')"

  tmp="$(mktemp "$(dirname "$JSON_PATH")/.paddock_tmp_XXXXXX")"
  if [ "$OVERWRITE" -eq 1 ]; then
    jq --arg key "$FIELD_SLUG" --argjson bays "$bays_json" '
      .paddocks = (.paddocks // {}) |
      .paddocks[$key] = $bays
    ' "$JSON_PATH" > "$tmp"
  else
    jq --arg key "$FIELD_SLUG" --argjson bays "$bays_json" '
      .paddocks = (.paddocks // {}) |
      if (.paddocks[$key]) then
        (.paddocks[$key]) as $arr
        | ($arr | map( (type=="object") and has("enabled") ) | any) as $has_en
        | ($arr | map( (type=="object") and has("automation_state_individual") ) | any) as $has_ai
        | .paddocks[$key] =
            ( ( (if $has_en then [] else [ { "enabled": true } ] end)
              + (if $has_ai then [] else [ { "automation_state_individual": false } ] end)
              )
              + $arr
            )
      else
        .paddocks[$key] = $bays
      end
    ' "$JSON_PATH" > "$tmp"
  fi
  mv "$tmp" "$JSON_PATH"
  JSON_DONE=1
fi

if [ "$JSON_DONE" -eq 0 ] && command -v python3 >/dev/null 2>&1; then
  ts=$(date +%s); cp -p "$JSON_PATH" "$JSON_PATH.bak.$ts" 2>/dev/null || true
  python3 - "$JSON_PATH" "$FIELD_SLUG" "$BAY_PREFIX" "$TOTAL_BAYS" "$PAD" "$OVERWRITE" <<'PY'
import json, sys, os, tempfile
json_path, field_key, bay_prefix, total_bays, pad, overwrite = sys.argv[1:]
total_bays, pad, overwrite = int(total_bays), int(pad), int(overwrite)

try:
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
        data = json.loads(raw) if raw else {"paddocks": {}}
except Exception:
    data = {"paddocks": {}}
if not isinstance(data, dict):
    data = {"paddocks": {}}
data.setdefault("paddocks", {})

def build_array_with_meta():
    arr = []
    arr.append({"enabled": True})
    arr.append({"automation_state_individual": False})
    for i in range(1, total_bays + 1):
        num = str(i).zfill(pad)
        arr.append({f"{bay_prefix}{num}": {"device": "unset"}})
    last = f"{bay_prefix}{str(total_bays).zfill(pad)}"
    arr.append({f"{last} Drain": {"device": "unset"}})
    return arr

if overwrite or field_key not in data["paddocks"]:
    data["paddocks"][field_key] = build_array_with_meta()
else:
    arr = data["paddocks"][field_key]
    has_enabled = any(isinstance(x, dict) and "enabled" in x for x in arr)
    has_indiv  = any(isinstance(x, dict) and "automation_state_individual" in x for x in arr)
    prefix = []
    if not has_enabled:
        prefix.append({"enabled": True})
    if not has_indiv:
        prefix.append({"automation_state_individual": False})
    if prefix:
        data["paddocks"][field_key] = prefix + arr

dirn = os.path.dirname(json_path) or "."
fd, tmp_path = tempfile.mkstemp(prefix=".paddock_tmp_", dir=dirn)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
        json.dump(data, tmp, indent=2); tmp.write("\n")
    os.replace(tmp_path, json_path)
except Exception as e:
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass
    print(f"[ERROR] Failed to write JSON: {e}", file=sys.stderr)
    sys.exit(4)
PY
  JSON_DONE=1
fi

if [ "$JSON_DONE" -eq 0 ]; then
  echo "[ERROR] Neither 'jq' nor 'python3' are available. Please install jq or python3." >&2
  exit 4
fi

################################################################################
#                    PADDOCK-LEVEL YAML (ONE FILE PER PADDOCK)                 #
################################################################################
PADDOCK_FILE="$OUTDIR/pwm_paddock_${FIELD_SLUG}.yaml"
cat > "$PADDOCK_FILE" <<EOF
# PWM System ${VERSION}
# Paddock-level controls for ${FIELD_PRETTY_UPPER}
input_select:
  ${FIELD_SLUG}_automation_state:
    name: "PWM ${FIELD_PRETTY_UPPER} Automation State"
    options: ["Flush","Pond","Drain","Off"]
    icon: mdi:water
  ${FIELD_SLUG}_drain_door_control:
    name: "PWM ${FIELD_PRETTY_UPPER} Drain Door Control"
    options: ["Open","HoldOne","Close","HoldTwo"]
    icon: mdi:door

input_number:
  ${FIELD_SLUG}_supply_waterleveloffset:
    name: PWM ${FIELD_PRETTY_UPPER} Supply Water Level Offset
    unit_of_measurement: "cm"
    min: -150
    max: 150
    step: 0.1
    mode: box
    icon: mdi:arrow-up-down

template:
  - sensor:
      - name: "PWM ${FIELD_PRETTY_UPPER} Version"
        unique_id: "pwm_${FIELD_SLUG}_version"
        icon: mdi:update
        state: "${VERSION}"
      - name: PWM ${FIELD_PRETTY_UPPER} Supply Water Depth
        unique_id: pwm_${FIELD_SLUG}_supply_water_depth
        state_class: measurement
        device_class: distance
        unit_of_measurement: cm
        state: >-
          {% set paddocks = state_attr('sensor.pwm_paddock_list', 'paddocks') or {} %}
          {% set pdk = '${FIELD_SLUG}' %}
          {% set bay = 'B_01' %}
          {% set key = bay | replace('_','-') %}
          {% set out = namespace(device='') %}

          {% for item in paddocks.get(pdk, []) %}
            {% if key in item %}
              {% set out.device = item[key]['device'] | slugify %}
            {% endif %}
          {% endfor %}

          {% if out.device in [None, '', 'unset', 'none'] %}
            {{ 'unavailable' }}
          {% else %}
            {% set depth_id = 'sensor.' ~ out.device ~ '_' ~ out.device ~ '_1m_water_depth' %}
            {% set depth_state = states(depth_id) | float | round(2) | default(0) %}

            {% set offset_id = 'input_number.' ~ pdk ~ '_supply_waterleveloffset' %}
            {% set offset_state = states(offset_id) | float | round(2) | default(0) %}

            {% set final_depth = depth_state - offset_state | float | round(2) | default(0) if states(depth_id) not in ['unknown', 'unavailable', 'none'] else 'unavailable' %}
            {% if final_depth == 'unavailable' %}
              {{ final_depth }}
            {% elif final_depth <= -10 %}
              -10
            {% elif final_depth > -10 %}
              {{ final_depth }}
            {% endif %}
          {% endif %}

automation:
    - id: "pwm_${FIELD_SLUG}_door_control_automation"
      alias: "PWM ${FIELD_PRETTY_UPPER} Door Control Automation"
      description: "Controls doors for all stops in ${FIELD_PRETTY_UPPER}, connecting each stop to a device set by the user in Paddock Config."
      mode: parallel
      max: 10
      trigger:
        - platform: state
          entity_id:
            - input_select.${FIELD_SLUG}_drain_door_control
EOF

i="$START"; end=$(( START + TOTAL_BAYS - 1 ))
while [ "$i" -le "$end" ]; do
  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  echo "            - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control" >> "$PADDOCK_FILE"
  i=$(( i + 1 ))
done

cat >> "$PADDOCK_FILE" <<EOF
      variables:
        control_entity: "{{ trigger.entity_id }}"
        control_option: "{{ trigger.to_state.state }}"

        sfx_supply: "_door_control"
        sfx_drain: "_drain_door_control"
        sfx_spur: "_spur_door_control"
        sfx_channel_supply: "_channel_supply_door_control"
        sfx_actuator: "_actuator_state"

        control_object_id: "{{ control_entity.split('.')[1] }}"

        is_drain_control: "{{ control_object_id.endswith(sfx_drain) }}"
        is_spur_control: "{{ control_object_id.endswith(sfx_spur) }}"
        is_channel_supply_control: "{{ control_object_id.endswith(sfx_channel_supply) }}"
        is_supply_control: "{{ control_object_id.endswith(sfx_supply) and not is_drain_control and not is_channel_supply_control }}"

        bay_stem: >-
          {% if is_supply_control %}
            {% set sfx = sfx_supply | length %}
            {{ control_object_id[:-sfx] }}
          {% elif is_channel_supply_control and '_b_' in control_object_id %}
            {% set sfx = sfx_channel_supply | length %}
            {{ control_object_id[:-sfx] }}
          {% else %}
            {{ '' }}
          {% endif %}

        paddock_slug: >-
          {% if is_drain_control %}
            {{ control_object_id[:- (sfx_drain | length)] }}
          {% elif is_supply_control and '_b_' in bay_stem %}
            {{ bay_stem.split('_b_')[0] }}
          {% elif is_spur_control %}
            {{ control_object_id[:- (sfx_spur | length)] }}
          {% elif is_channel_supply_control %}
            {% if '_b_' in bay_stem %}
              {{ bay_stem.split('_b_')[0] }}
            {% else %}
              {{ control_object_id[:- (sfx_channel_supply | length)] }}
            {% endif %}
          {% else %}
            {{ '' }}
          {% endif %}

        bay_num: >-
          {% if is_supply_control and '_b_' in bay_stem %}
            {{ bay_stem.split('_b_')[1] }}
          {% else %}
            {{ '' }}
          {% endif %}

        bay_name: >-
          {% if bay_num %}
            {{ 'B-' ~ bay_num }}
          {% else %}
            {{ '' }}
          {% endif %}

        bays: >-
          {% set pdk_list = state_attr('sensor.pwm_paddock_list', 'paddocks') | default({}, true) %}
          {{ pdk_list[paddock_slug] | default([], true) }}

        device_name: >-
          {% if is_supply_control and bay_name|length > 0 %}
            {% set dev = namespace(val='unset') %}
            {% for b in bays %}
              {% set name = (b | list | first) %}
              {% if name | slugify == bay_name | slugify %}
                {% set dev.val = b[name].device | default('unset') %}
                {% break %}
              {% endif %}
            {% endfor %}
            {{ dev.val }}
          {% elif is_drain_control %}
            {% set dev = namespace(val='unset') %}
            {% for b in bays %}
              {% set name = (b | list | first) %}
              {% if 'Drain' in name %}
                {% set dev.val = b[name].device | default('unset') %}
                {% break %}
              {% endif %}
            {% endfor %}
            {{ dev.val }}
          {% elif is_spur_control %}
            {% set dev = namespace(val='unset') %}
            {% for b in bays %}
              {% set name = ( b | list | first) %}
              {% if 'Spur' in name %}
                {% set dev.val = b[name].device | default('unset') %}
                {% break %}
              {% endif %}
            {% endfor %}
            {{ dev.val }}
          {% elif is_channel_supply_control %}
            {% set dev = namespace(val='unset') %}
            {% for b in bays %}
              {% set name = ( b | list | first) %}
              {% if 'Channel Supply' in name %}
                {% set dev.val = b[name].device | default('unset') %}
                {% break %}
              {% endif %}
            {% endfor %}
            {{ dev.val }}
          {% else %}
            unset
          {% endif %}

        device_id_slug: >-
          {{ device_name | trim | lower
                          | replace('-', '_')
                          | replace(' ', '_')
                          | regex_replace('[^0-9a-z_]', '') }}

        target_device: "{{ 'input_select.' ~ device_id_slug ~ sfx_actuator }}"

      condition:
        - condition: template
          value_template: "{{ control_option | length > 0 }}"
        - condition: template
          value_template: "{{ trigger.to_state is not none }}"
        - condition: template
          value_template: "{{ trigger.from_state is not none }}"
        - condition: template
          value_template: "{{ trigger.to_state.state not in ['unknown', 'unavailable'] }}"
        - condition: template
          value_template: "{{ trigger.to_state.state != trigger.from_state.state }}"
        - condition: template
          value_template: "{{ paddock_slug | length > 0 }}"
        - condition: template
          value_template: "{{ device_id_slug | length > 0 }}"
        - condition: template
          value_template: "{{ device_id_slug != 'unset' }}"

      action:
        - service: input_select.select_option
          target:
            entity_id: "{{ target_device | lower }}"
          data:
            option: "{{ control_option }}"

    - id: "pwm_${FIELD_SLUG}_individual_automation_state_automation"
      alias: "PWM ${FIELD_PRETTY_UPPER} Individual Automation State Automation"
      description: "Propagate paddock-level automation state to bay-level states unless individual automation is enabled in paddock config."
      mode: parallel
      max: 10
      trigger:
        - platform: state
          entity_id:
            - input_select.${FIELD_SLUG}_automation_state
      conditions:
        - condition: not
          conditions:
            - condition: template
              value_template: >-
                {% set paddock = '${FIELD_SLUG}' %}
                {% set pdk_list = state_attr('sensor.pwm_paddock_list', 'paddocks') | default({}, true) %}
                {{ (pdk_list[paddock] | map(attribute='automation_state_individual') | select('defined') | list | first | default(false)) }}
      variables:
        entity_list: >-
          {% set paddock = '${FIELD_SLUG}' %}
          {% set entity = namespace(list=[]) %}

          {% for e in states.input_select
            | selectattr('entity_id', 'search', paddock)
            | selectattr('entity_id', 'search', 'automation_state')
            | selectattr('entity_id', 'search', '_b_') %}
          {% set entity.list = entity.list + [e.entity_id] %}
          {% endfor %}

          {{ entity.list }}
        new_option: >-
          {{ trigger.to_state.state if trigger is defined else 'Off' }}
      action:
        - repeat:
            for_each: "{{ entity_list }}"
            sequence:
              - service: input_select.select_option
                target:
                  entity_id: "{{ repeat.item }}"
                data:
                  option: "{{ new_option }}"

    - id: "pwm_${FIELD_SLUG}_flush_close_supply"
      alias: "PWM ${FIELD_PRETTY_UPPER} Flush Close Supply"
      description: "Set when to close the paddock supply door (B-01 SUPPLY) during a flush. Migrate and modify as required."
      triggers:
        - trigger: state
          entity_id:
            - timer.${FIELD_SLUG}_b_02_flushtimeonwater
          from: active
          to: idle
      conditions: []
      actions:
        - alias: Start Flush Close Supply timer
          action: timer.start
          target:
            entity_id: timer.${FIELD_SLUG}_flushclosesupply
        - alias: Wait for timer to finish
          wait_for_trigger:
            - trigger: state
              entity_id:
                - timer.${FIELD_SLUG}_flushclosesupply
              from: active
              to: idle
        - action: notify.notify
          metadata: {}
          data:
            message: ${FIELD_PRETTY_UPPER} Has enough water to flush, close B-01's supply door when ready
            title: ${FIELD_PRETTY_UPPER} Flush Close Supply
        - action: input_select.select_option
          enabled: false
          metadata: {}
          data:
            option: Close
          target:
            entity_id: input_select.${FIELD_SLUG}_b_01_door_control
      mode: restart

    - id: "pwm_${FIELD_SLUG}_automationstate_turn_off"
      alias: "PWM ${FIELD_PRETTY_UPPER} Automation State Turn Off"
      description: "Sets ${FIELD_PRETTY_UPPER}'s Automation State to 'Off' when all bays Automation States's are also 'Off' and automation_state_individual is 'true'"
      mode: queued
      max: 10
      triggers:
        - alias: Any Bays Automation State Turns 'Off'
          trigger: state
          from: null
          to: 'Off'
          entity_id:
EOF

i="$START"; end=$(( START + TOTAL_BAYS - 1 ))
while [ "$i" -le "$end" ]; do
  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  echo "            - input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state" >> "$PADDOCK_FILE"
  i=$(( i + 1 ))
done

cat >> "$PADDOCK_FILE" <<EOF
      conditions:
        - alias: ${FIELD_PRETTY_UPPER}'s Automation State isn't already 'Off' and automation_state_individual key is false
          condition: not
          conditions:
            - alias: ${FIELD_PRETTY_UPPER}'s Automation State isn't already 'Off' (inverted by not condition)
              condition: state
              entity_id: input_select.${FIELD_SLUG}_automation_state
              state: 'Off'
            - alias: ${FIELD_PRETTY_UPPER}'s automation_state_individual key is false (inverted by not condition)
              condition: template
              value_template: >-
                {% set paddock = '${FIELD_SLUG}' %}
                {% set pdk_list = state_attr('sensor.pwm_paddock_list', 'paddocks') | default({}, true) %}
                {{ (pdk_list[paddock] | map(attribute='automation_state_individual') | select('defined') | list | first | default(false)) }}
        - alias: All Bays Automaion States are 'Off'
          condition: state
          state: 'Off'
          entity_id:
EOF

i="$START"; end=$(( START + TOTAL_BAYS - 1 ))
while [ "$i" -le "$end" ]; do
  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  echo "            - input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state" >> "$PADDOCK_FILE"
  i=$(( i + 1 ))
done

cat >> "$PADDOCK_FILE" <<EOF
      actions:
        - action: input_select.select_option
          target:
            entity_id: input_select.${FIELD_SLUG}_automation_state
          data:
            option: 'Off'

EOF

################################################################################
#                DEFAULT DASHBOARD YAML SNIPPET FOR THIS PADDOCK               #
################################################################################
FIELD_DASH="${FIELD_SLUG//_/-}"
DASHBOARD_FILE="$DASHBOARD_PATH/pwm_${FIELD_SLUG}_default_dashboard.yaml"
cat > "$DASHBOARD_FILE" <<EOF
# PWM System ${VERSION}
  - title: ${FIELD_PRETTY_UPPER}
    path: ${FIELD_DASH}
    type: masonry
    cards:
      - type: picture-elements
        image: <Paddock Image URL> # INSERT PADDOCK IMAGE HERE
        elements:
          - type: state-badge
            tap_action:
              action: more-info
            entity: sensor.pwm_${FIELD_SLUG}_supply_water_depth
            style:
              top: 10%
              left: 10%
              '--ha-label-badge-title-font-size': 0em
              '--paper-font-subhead_-_font-size': 10px
              transform: scale(1.0)
EOF

i="$START"; end=$(( START + TOTAL_BAYS - 1 ))
n=0
while [ "$i" -le "$end" ]; do
  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  NUM=$(( n + 10 ))
  cat >> "$DASHBOARD_FILE" <<YAML
          - type: state-badge
            tap_action:
              action: more-info
            entity: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
            style:
              top: ${NUM}%
              left: ${NUM}%
              '--ha-label-badge-title-font-size': 0em
              '--paper-font-subhead_-_font-size': 10px
              transform: scale(1)
YAML
  i=$(( i + 1 ))
  n=$(( n + 10 ))
done

cat >> "$DASHBOARD_FILE" <<EOF
      - type: vertical-stack
        cards:
          - type: custom:button-card
            template: template_titleblock
            name: ${FIELD_PRETTY_UPPER}
          - type: custom:button-card
            template: template_inputselect_automationstate
            entity: input_select.${FIELD_SLUG}_automation_state
            name: ${FIELD_PRETTY_UPPER} Automation State
            variables:
              paddock_var: ${FIELD_SLUG}
          - type: custom:button-card
            template: template_titleblock
            name: ${FIELD_PRETTY_UPPER} Inlet Controls
EOF

i="$START"; end=$(( START + TOTAL_BAYS - 1 ))
while [ "$i" -le "$end" ]; do
  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  cat >> "$DASHBOARD_FILE" <<YAML
          - type: custom:layout-card
            layout_type: custom:horizontal-layout
            layout:
              margin: 0px 0px 0px 0px
              padding: 0px 0px 0px 0px
              card_margin: 0px 0px 0px 0px
            cards:
              - type: custom:button-card
                template: template_buttoncard_openclose
                entity: input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                name: ${BAY_NAME} SUPPLY
              - type: custom:button-card
                template: template_inputselect_automationstate
                entity: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                name: ${BAY_NAME} Automation State
                variables:
                  paddock_var: ${FIELD_SLUG}
                styles:
                  card:
                    - display: |
                        [[[
                          const paddock = variables.paddock_var;
                          const s = hass.states['sensor.pwm_paddock_list'];
                          const item = s?.attributes?.paddocks?.[paddock]?.find(o => o.automation_state_individual !== undefined);
                          return item && item.automation_state_individual === false ? 'none' : null;
                        ]]]
YAML
  i=$(( i + 1 ))
done

LAST=$(( START + TOTAL_BAYS - 1 ))
LAST_NUM=$(printf "%0${PAD}d" "$LAST")
LAST_NAME="${BAY_PREFIX}${LAST_NUM}"

cat >> "$DASHBOARD_FILE" <<YAML
          - type: custom:button-card
            template: template_buttoncard_openclose
            entity: input_select.${FIELD_SLUG}_drain_door_control
            name: ${LAST_NAME} DRAIN
YAML

cat >> "$DASHBOARD_FILE" <<EOF
      - type: custom:button-card
        template: template_paddockconfigbutton
        variables:
          paddock_config_var: ${FIELD_SLUG}
      - type: button
        name: Extra Data
        icon: mdi:database
        show_name: true
        show_icon: true
        tap_action:
          action: navigate
          navigation_path: /farms-fields/${FIELD_DASH}-extra
        hold_action:
          action: none
        icon_height: 80px
        show_state: true
  - title: ${FIELD_PRETTY_UPPER} Extra Data
    type: masonry
    path: ${FIELD_DASH}-extra
    subview: true
    cards: []
EOF

################################################################################
#          BAY-LEVEL HELPERS (ONE YAML FILE PER BAY IN THIS PADDOCK)           #
################################################################################
end=$(( START + TOTAL_BAYS - 1 ))
i="$START"
while [ "$i" -le "$end" ]; do

  curr_num=$((10#$i))
  end_num=$((10#$end))
  start_num=$((10#$START))

  BAY_NUM=$(printf "%0${PAD}d" "$i")
  BAY_NAME="${BAY_PREFIX}${BAY_NUM}"
  BAY_SLUG="$(slugify "$BAY_NAME")"
  DISPLAY_BASE="PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")"

  HAS_PREV=0
  if (( curr_num > start_num )); then
    HAS_PREV=1
    prev_num=$(( curr_num - 1 ))
    PREV_NUM=$(printf "%0${PAD}d" "$prev_num")
    PREV_NAME="${BAY_PREFIX}${PREV_NUM}"
    PREV_SLUG="$(slugify "$PREV_NAME")"
  else
    PREV_NAME="Supply"
    PREV_SLUG="supply"
  fi

  HAS_NEXT=0
  if (( curr_num < end_num )); then
    HAS_NEXT=1
    next_num=$(( curr_num + 1 ))
    NEXT_NUM=$(printf "%0${PAD}d" "$next_num")
    NEXT_NAME="${BAY_PREFIX}${NEXT_NUM}"
    NEXT_SLUG="$(slugify "$NEXT_NAME")"
  else
    NEXT_NAME="Drain"
    NEXT_SLUG="drain"
  fi

  FILEPATH="$OUTDIR/pwm_paddock_helpers_${FIELD_SLUG}_${BAY_SLUG}.yaml"
  cat > "$FILEPATH" <<EOF
# PWM System ${VERSION}
# Helper entities and automations for bay ${BAY_NAME} in paddock ${FIELD_PRETTY_UPPER}
input_select:
  ${FIELD_SLUG}_${BAY_SLUG}_door_control:
    name: ${DISPLAY_BASE} Door Control
    options: ["Open", "HoldOne", "Close", "HoldTwo"]
    icon: mdi:door
  ${FIELD_SLUG}_${BAY_SLUG}_automation_state:
    name: "${DISPLAY_BASE} Automation State"
    options: ["Flush","Pond","Drain","Off"]
    icon: mdi:water

input_number:
  ${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax:
    name: ${DISPLAY_BASE} Water Level Max
    unit_of_measurement: "cm"
    min: 0
    max: 40
    step: 1
    mode: box
    icon: mdi:water
  ${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin:
    name: ${DISPLAY_BASE} Water Level Min
    unit_of_measurement: "cm"
    min: -10
    max: 40
    step: 1
    mode: box
    icon: mdi:water-minus
  ${FIELD_SLUG}_${BAY_SLUG}_waterleveloffset:
    name: ${DISPLAY_BASE} Water Level Offset
    unit_of_measurement: "cm"
    min: -150
    max: 150
    step: 0.1
    mode: box
    icon: mdi:arrow-up-down

input_boolean:
  ${FIELD_SLUG}_${BAY_SLUG}_flushactive:
    name: ${DISPLAY_BASE} Flush Active
    icon: mdi:water-pump

template:
  - sensor:
      - name: ${DISPLAY_BASE} Water Depth
        unique_id: pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
        state_class: measurement
        device_class: distance
        unit_of_measurement: cm
        state: >-
          {% set paddock_id = '${FIELD_SLUG}' %}
          {% set current_bay = '${BAY_SLUG}' %}
          {% set data = state_attr('sensor.pwm_paddock_list', 'paddocks') or {} %}
          {% set pdk = data.get(paddock_id, []) %}
          {% set ns = namespace(bays=[], drain_device='') %}

          {% for b in pdk %}
            {% set k = b | list | first %}
            {% set kl = (k|string) | lower %}
            {% set kn = kl | replace('-', '_') %}
            {% set v = b[k] %}

            {% if v is mapping %}
              {% set dev = v.get('device',
                            v.get('supply_device',
                            v.get('supply_door', {}).get('device',
                            v.get('drain_door', {}).get('device', '')))) %}
            {% else %}
              {% set dev = '' %}
            {% endif %}

            {% if kn is match('^b_\\d+$') %}
              {% set num = (kn.split('_')[1] | int) %}
              {% set ns.bays = ns.bays + [ {'key': kn, 'num': num, 'device': dev} ] %}
            {% elif 'drain' in kn %}
              {% set ns.drain_device = dev %}
            {% endif %}
          {% endfor %}

          {% set bays_sorted = ns.bays | sort(attribute='num') %}
          {% set next = namespace(device='') %}
          {% set cb_norm = current_bay | lower | replace('-', '_') %}

          {% for i in range(bays_sorted | count) %}
            {% if bays_sorted[i]['key'] == cb_norm %}
              {% if i + 1 < (bays_sorted | count) %}
                {% set next.device = bays_sorted[i + 1]['device'] %}
              {% else %}
                {% set next.device = ns.drain_device %}
              {% endif %}
            {% endif %}
          {% endfor %}

          {% if not next.device and bays_sorted | count > 0 %}
            {% for b in bays_sorted %}
              {% if b['key'] == cb_norm %}
                {% set next.device = b['device'] %}
              {% endif %}
            {% endfor %}
          {% endif %}

          {% if next.device %}
            {% set depth_entity = 'sensor.' ~ next.device | slugify ~ '_' ~ next.device | slugify ~ '_1m_water_depth' %}
            {% set dev_state = states(depth_entity) | float(0) %}
          {% else %}
            {% set depth_entity = '' %}
            {% set dev_state = 0 %}
          {% endif %}

          {% set offset_entity = 'input_number.' ~ paddock_id ~ '_' ~ cb_norm ~ '_waterleveloffset' %}
          {% set bay_offset = states(offset_entity) | float(0) %}

          {% set final_depth = (dev_state - bay_offset) | round(1) if states(depth_entity) not in ['unknown', 'unavailable', 'none'] else 'unavailable' %}
          {% if final_depth == 'unavailable' %}
            {{ final_depth }}
          {% elif final_depth <= -10 %}
            -10
          {% elif final_depth > -10 %}
            {{ final_depth }}
          {% endif %}
#########################################################################################################
## PADDOCK AUTOMATION
############################################################################################################
automation:
  - id: "pwm_${FIELD_SLUG}_${BAY_SLUG}_irrigation_automation"
    alias: "PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Irrigation Automation"
    mode: restart
    description: "Control Water for ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")"
    triggers:
      - trigger: homeassistant
        event: start
        alias: On Home Assistant Start

      - trigger: state
        entity_id:
          - input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
        from: null
        to: null
        for:
          hours: 0
          minutes: 2
          seconds: 0
        alias: ${FIELD_PRETTY_UPPER} Automation State Changes

      - trigger: state
        entity_id:
          - input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
        from: null
        to: null
        alias: $(to_upper "$BAY_NAME") Flush Active State Change
EOF

incl_if_prev <<EOF
      - trigger: state
        entity_id:
          - input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
        from: null
        to: null
        alias: $(to_upper "$PREV_SLUG") Flush Active State Change
EOF

cat >> "$FILEPATH" <<EOF
      - trigger: state
        alias: Min or Max Number Changes
        entity_id:
          - input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
          - input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax
        from: null
        to: null
        for:
          hours: 0
          minutes: 5
          seconds: 0

      - trigger: time_pattern
        minutes: "/10"
        alias: Re-evaluate Water Level (Every 10 Minutes)

    conditions:
      - condition: and
        conditions:
          - condition: not
            conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: "Off"
    actions:
      - choose:
          - alias: Flushing
            conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: Flush
                alias: Automation State is Flush
            sequence:
              - alias: Adding Water
                if:
                  - alias: Check if water required
                    condition: and
                    conditions:
EOF

incl_if_prev <<EOF
                      - condition: state
                        entity_id: input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
                        state: "off"
EOF

cat >> "$FILEPATH" <<EOF
                      - alias: Check if Water Required
                        condition: or
                        conditions:
                          - condition: numeric_state
                            entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                            below: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
                            alias: Below Low Level
                      - condition: state
                        entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                        state: "on"
                then:
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Close
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Close
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Open
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Open
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                  - wait_for_trigger: []
                else:
                  - alias: Hold Position
                    if:
                      - alias: Check If Any condition needs water
                        condition: or
                        conditions:
                          - condition: numeric_state
                            entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                            below: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax
                            above: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
                            alias: Optimal Level
                      - condition: state
                        entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                        state: "on"
EOF

incl_if_prev <<EOF
                      - condition: state
                        entity_id: input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
                        state: "off"
EOF

cat >> "$FILEPATH" <<EOF
                    then:
                      - wait_for_trigger: []
                    else:
                      - alias: Release Water
                        if:
                          - condition: numeric_state
                            entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                            above: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax
                            alias: High Water
                          - condition: state
                            entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                            state: "on"
EOF

incl_if_prev <<EOF
                          - condition: state
                            entity_id: input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
                            state: "off"
EOF

cat >> "$FILEPATH" <<EOF
                        then:
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: HoldOne
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: Open
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                          - wait_for_trigger: []
                        else:
                          - alias: Drain The Bay
                            if:
                              - condition: state
                                entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                                state: "off"
EOF

incl_if_prev <<EOF
                              - condition: state
                                entity_id: input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
                                state: "off"
EOF

cat >> "$FILEPATH" <<EOF
                            then:
                              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                                action: input_select.select_option
                                metadata: {}
                                data:
                                  option: HoldOne
                                target:
                                  entity_id: input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                                action: input_select.select_option
                                metadata: {}
                                data:
                                  option: Open
                                target:
                                  entity_id: input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Turn Off Automation State
                                action: input_select.select_option
                                metadata: {}
                                data:
                                  option: "Off"
                                target:
                                  entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                              - wait_for_trigger: []
EOF

incl_if_prev <<EOF
                            else:
                              - alias: Bay Above is Flushing - Waiting for Water
                                if:
                                  - condition: state
                                    entity_id: input_boolean.${FIELD_SLUG}_${PREV_SLUG}_flushactive
                                    state: "on"
                                    alias: Bay Above Flushing
                                  - condition: state
                                    entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                                    state: "on"
                                then:
                                  - action: notify.notify
                                    enabled: false
                                    metadata: {}
                                    data:
                                      title: Automation Update
                                      message: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") - Waiting for Water
EOF

cat >> "$FILEPATH" <<EOF
          - alias: Ponding
            conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: Pond
            sequence:
              - alias: Add Water
                if:
                  - alias: Check If Any condition needs water
                    condition: or
                    conditions:
                      - condition: numeric_state
                        entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                        below: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
                then:
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Open
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Open
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
EOF

if [ "$HAS_NEXT" -eq 0 ]; then
  cat >> "$FILEPATH" <<EOF
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Close
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Close
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
EOF
fi

if [ "$HAS_PREV" -eq 0 ]; then
  cat >> "$FILEPATH" <<EOF
                  - alias: Supply Water Level Low
                    if:
                      - alias: Supply Water Level Below Bay Water Level
                        condition: numeric_state
                        entity_id: sensor.pwm_${FIELD_SLUG}_supply_water_depth
                        below: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                    then:
                      - alias: Notify Supply Low
                        action: notify.notify
                        metadata: {}
                        data:
                          message: ${FIELD_PRETTY_UPPER} supply channel water depth lower than bay water depth.
                          title: ${FIELD_PRETTY_UPPER} Supply Chanel Low Level
EOF
fi

cat >> "$FILEPATH" <<EOF
                  - action: notify.notify
                    metadata: {}
                    data:
                      message: Adding Water to ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")
                      title: Automation Update
                    enabled: false
                  - wait_for_trigger: []
                else:
                  - alias: Hold Position
                    if:
                      - alias: Check If Water Level Optimal
                        condition: or
                        conditions:
                          - condition: numeric_state
                            entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                            below: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax
                            above: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
                    then:
                      - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Hold
                        action: input_select.select_option
                        metadata: {}
                        data:
                          option: HoldOne
                        target:
                          entity_id:
                            - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                      - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Close
                        action: input_select.select_option
                        metadata: {}
                        data:
                          option: Close
                        target:
                          entity_id:
                            - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
EOF

if [ "$HAS_NEXT" -eq 0 ]; then
  cat >> "$FILEPATH" <<EOF
                      - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                        action: input_select.select_option
                        metadata: {}
                        data:
                          option: HoldOne
                        target:
                          entity_id:
                            - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                      - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Close
                        action: input_select.select_option
                        metadata: {}
                        data:
                          option: Close
                        target:
                          entity_id:
                            - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
EOF
fi

cat >> "$FILEPATH" <<EOF
                      - wait_for_trigger: []
                    else:
                      - alias: Release Water
                        if:
                          - condition: numeric_state
                            entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                            above: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmax
                        then:
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Hold
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: HoldOne
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Close
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: Close
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: HoldOne
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                          - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                            action: input_select.select_option
                            metadata: {}
                            data:
                              option: Open
                            target:
                              entity_id:
                                - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                          - action: notify.notify
                            metadata: {}
                            data:
                              message: Releasing Water from ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")
                              title: Automation Update
                            enabled: false
                          - wait_for_trigger: []
                        else:
                          - wait_for_trigger: []
          - alias: Draining Bay
            conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: Drain
            sequence:
              - alias: Check if Bay is Already Empty
                if:
                  - condition: numeric_state
                    entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                    below: -8
                then:
                  - action: input_boolean.turn_off
                    metadata: {}
                    data: {}
                    target:
                      entity_id:
                        - input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Open
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - wait_for_trigger: []
                else:
                  - action: input_boolean.turn_off
                    metadata: {}
                    data: {}
                    target:
                      entity_id:
                        - input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: HoldOne
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - repeat:
                      sequence:
                        - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                          action: input_select.select_option
                          metadata: {}
                          data:
                            option: Open
                          target:
                            entity_id:
                              - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                        - delay:
                            hours: 0
                            minutes: 0
                            seconds: 5
                        - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Hold
                          action: input_select.select_option
                          metadata: {}
                          data:
                            option: HoldOne
                          target:
                            entity_id:
                              - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                        - delay:
                            hours: 0
                            minutes: 45
                            seconds: 0
                      until:
                        - condition: numeric_state
                          entity_id: sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
                          below: -8
                  - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Open
                    action: input_select.select_option
                    metadata: {}
                    data:
                      option: Open
                    target:
                      entity_id:
                        - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
                  - wait_for_trigger: []
        default:
          - action: notify.notify
            metadata: {}
            data:
              message: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") - Check State
              title: Automation Failure
          - wait_for_trigger: []
      - wait_for_trigger: []
####################################################
## Set Paddock State to begin sequence ###
####################################################
  - id: "pwm_${FIELD_SLUG}_${BAY_SLUG}_auto_setup"
    alias: "PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Automation Setup"
    description: "Sets up ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") for automated irrigation. Closes drain door, turns on flush active boolean and notifies for a Flush, opens supply door (closes drain door if last bay) and notifies for Pond"
    triggers:
      - trigger: state
        entity_id:
          - input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
        from: null
        to: null
        for:
          hours: 0
          minutes: 1
          seconds: 0
    conditions:
      - condition: not
        conditions:
          - condition: state
            state: "Off"
            entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
    actions:
      - choose:
          - conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: "Flush"
            sequence:
              - action: input_boolean.turn_on
                metadata: {}
                data: {}
                target:
                  entity_id:
                    - input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Close
                action: input_select.select_option
                metadata: {}
                data:
                  option: Close
                target:
                  entity_id:
                    - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
              - metadata: {}
                data:
                  title: "Automation Started:"
                  message: Flushing ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")
                action: notify.notify
                enabled: false
              - wait_for_trigger: []
          - conditions:
              - condition: state
                entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
                state: "Pond"
            sequence:
              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Supply Open
                action: input_select.select_option
                metadata: {}
                data:
                  option: Open
                target:
                  entity_id:
                    - input_select.${FIELD_SLUG}_${BAY_SLUG}_door_control
EOF

if [ "$HAS_NEXT" -eq 0 ]; then
  cat >> "$FILEPATH" <<EOF
              - alias: ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Drain Close
                action: input_select.select_option
                metadata: {}
                data:
                  option: Close
                target:
                  entity_id:
                    - input_select.${FIELD_SLUG}_${NEXT_SLUG}_door_control
EOF
fi

cat >> "$FILEPATH" <<EOF
              - alias: Notify Filling Up
                enabled: false
                action: notify.notify
                data:
                  title: Automation Started
                  message: Filling up ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME")
    mode: restart

  - id: "pwm_${FIELD_SLUG}_${BAY_SLUG}_clock_start"
    alias: "PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Clock Start"
    description: "Start Time On Water Clock countdown for $(to_upper "$BAY_NAME")"
    triggers:
      - entity_id:
          - sensor.pwm_${FIELD_SLUG}_${BAY_SLUG}_water_depth
        for:
          hours: 0
          minutes: 5
          seconds: 0
        above: input_number.${FIELD_SLUG}_${BAY_SLUG}_waterlevelmin
        trigger: numeric_state
    conditions:
      - condition: state
        entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
        state: "on"
    actions:
      - action: timer.start
        target:
          entity_id:
            - timer.${FIELD_SLUG}_${BAY_SLUG}_flushtimeonwater
        data: {}
    mode: restart

  - id: "pwm_${FIELD_SLUG}_${BAY_SLUG}_clock_stop"
    alias: "PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Clock Stop"
    description: "Turn off Flush Activate and set Automation State to 'Off' for $(to_upper "$BAY_NAME") when Flush Time On Water timer finishes"
    triggers:
      - entity_id:
          - timer.${FIELD_SLUG}_${BAY_SLUG}_flushtimeonwater
        from: active
        to: idle
        trigger: state
    conditions:
      - condition: state
        entity_id: input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
        state: Flush
    actions:
      - action: input_boolean.turn_off
        data: {}
        target:
          entity_id: input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
    mode: restart

  - id: "pwm_${FIELD_SLUG}_${BAY_SLUG}_flush_deactivate_on_off"
    alias: "PWM ${FIELD_PRETTY_UPPER} $(to_upper "$BAY_NAME") Flush Deactivate On Off"
    description: "Ensure Flush Active is OFF whenever $(to_upper "$BAY_NAME") automation state is set to Off."
    triggers:
      - trigger: state
        entity_id:
          - input_select.${FIELD_SLUG}_${BAY_SLUG}_automation_state
        from: "Flush"
        to: null
    conditions: []
    actions:
      - action: input_boolean.turn_off
        data: {}
        target:
          entity_id:
            - input_boolean.${FIELD_SLUG}_${BAY_SLUG}_flushactive
    mode: restart

EOF

  echo "✓ Wrote helper: $FILEPATH"
  i=$(( curr_num + 1 ))
done

###############################################################################
# Optional prune: remove helper YAMLs for bays that are now outside the range #
###############################################################################
if [ "$PRUNE_BAYS" -eq 1 ]; then
  min_valid=$((10#$START))
  max_valid=$(( min_valid + TOTAL_BAYS - 1 ))

  echo "[PRUNE] Valid bay index range for '${FIELD_SLUG}' is ${min_valid}..${max_valid}"
  echo "[PRUNE] Removing bay helpers outside this range in $OUTDIR (if any)"

  for f in "$OUTDIR"/pwm_paddock_helpers_"$FIELD_SLUG"_b_*.yaml; do
    [ -e "$f" ] || break

    bn=$(basename "$f")
    bay_num_str=$(printf '%s\n' "$bn" | sed -E 's/^.*_b_([0-9]+)\.yaml$/\1/')
    case "$bay_num_str" in
      ''|*[!0-9]*)
        continue
        ;;
    esac

    bay_num=$((10#$bay_num_str))

    if [ "$bay_num" -lt "$min_valid" ] || [ "$bay_num" -gt "$max_valid" ]; then
      echo "[PRUNE] Removing helper for bay index $bay_num: $f"
      rm -f "$f"
    fi
  done
fi

echo "[OK] Paddock '${FIELD_SLUG}' ready: JSON updated, paddock file: $PADDOCK_FILE, bays: ${TOTAL_BAYS}"
