# ASM — Asset Service Manager

## Scope
- Assets, parts, service/inspection events.
- Offline-first; local JSON backing store.

## Data
- Primary data: `local_data/asm/`
  - `data.json`
  - `config.json`
  - `backups/`

## User Flows
- Add/edit assets
- Add/edit parts, adjust stock
- Record service events (with optional parts consumption)
- View history, reports
- Export/backup/restore/reset

## Multi-user Considerations
- Concurrent event logging
- Protect master category/service-type edits if editable

## Versioning
- Module VERSION
- Version sensor exposed

## Entities & Services
Document key HA entities and scripts here.

## Backend / Tooling
Document any CLI/shell/python entrypoints here.
