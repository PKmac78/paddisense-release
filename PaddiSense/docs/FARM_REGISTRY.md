# Farm Registry (Shared Core)

## Purpose
Standalone registry providing Grower → Farm → Paddock → Bay structure used by all modules.

## Rules
- Registry is independent of PWM.
- IDs are generated only (no manual entry).
- UI shows names, not IDs.

## Data Model
- Grower: may own multiple farms
- Farm: contains paddocks
- Paddock: contains 0..N bays
- Bay: has optional assignments/metadata
- Season: active season selectable (start/end)

## Storage Strategy
- Default: local JSON under `local_data/registry/`
- Export/import supported for backups and migration.
- Any move into `.storage` requires deliberate migration plan.

## Multi-user
- Prefer per-record locking for edits (or conflict-safe write strategy).
- Show “locked by <user>” where applicable.

## Interfaces
List the HA entities, scripts, and services that interact with the registry here.
