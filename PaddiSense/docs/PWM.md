# PWM — Precision Water Management

## Scope
- Paddock/bay automation modes (Off/Flush/Pond/Drain etc.)
- Device assignment and bay configuration
- Offline-first automation

## Control Contract (Critical)
- HA/PWM controls **valves/actuators only**
- Never control raw relays directly from HA
- Two-actuator devices are logically paired

## Fault Handling
- Watchdog enabled
- On fault: alert + mark unavailable
- No forced stop/recovery from HA (policy may evolve)

## Data
- `local_data/pwm/`
  - `config.json`
  - `backups/`

## User Flows
- Paddock creation/edit
- Bay configuration (depth targets, offsets)
- Device assignment wizard
- Dashboard operations

## Versioning
- Module VERSION
- Version sensor exposed

## Entities & Services
Document key HA entities, scripts, and automations here.

## Automation Logic
Describe the current mode behaviors and safety constraints here.
