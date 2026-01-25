# IPM — Inventory Product Manager

## Scope
- Consumables tracked by location.
- Stock tracked in units (kg/L/ea etc), not containers.
- Offline-first; local JSON backing store.

## Data
- Primary data: `local_data/ipm/`
  - `inventory.json`
  - `config.json`
  - `backups/`

## User Flows
- Add/edit product
- Adjust/consume stock
- Move stock between locations
- Reporting (by location, by season)
- Settings CRUD: categories/subcategories/locations/actives/groups/units
- Backup/restore/reset

## Multi-user Considerations
- Allow concurrent stock moves if safe.
- Protect/lock master list edits.

## Versioning
- Module VERSION
- Schema versioning (config/inventory)
- Version sensor exposed

## Entities & Services
Document key HA entities and scripts here.

## Backend / Tooling
Document any CLI/shell/python entrypoints here.
