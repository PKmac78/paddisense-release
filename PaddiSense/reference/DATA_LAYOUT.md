# Data Layout

## Protected Local Data
All runtime data is stored outside git under `/config/local_data/`.

### Expected Paths
- `local_data/ipm/`
- `local_data/asm/`
- `local_data/weather/`
- `local_data/weather_api/`
- `local_data/pwm/`
- `local_data/registry/` (target)

## Backup Policy (Per Module)
- Backups stored under `local_data/<module>/backups/`
- Migrations must create pre-change backups
- Imports must create pre-import backups

## Schema Versioning
- Each JSON store should include a `version` field.
- Backward-incompatible changes require migration logic and documentation.
