# Weather (Unified)

## Scope
- Local gateway + optional remote API stations.
- Robust handling of unavailable sensors.
- Crop-sensitive alerting (logic documented here).

## Data
- `local_data/weather/` (local station config)
- `local_data/weather_api/` (API station config)

## Rules
- Offline-first: local station functions without internet.
- API stations require secrets; failure must degrade gracefully.
- Package files must avoid duplicate root YAML keys.

## Station Model
- Slot system (stable naming)
- Per-station entities derived from a consolidated data source

## Alerts
- Define windows, thresholds, and rate limiting here.

## Versioning
- Module VERSION
- Version sensor exposed

## Entities & Services
Document key HA entities and scripts here.

## Backend / Tooling
Document API station management entrypoints here.
