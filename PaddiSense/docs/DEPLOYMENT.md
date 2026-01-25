# Deployment

## Supported Platform
- Home Assistant OS (HAOS) only.

## Install Models
### Developer Install
- Git clone into `/config/PaddiSense`
- Enable packages/dashboards per docs
- Use local `server.yaml` and `secrets.yaml` (never committed)

### Grower Install (Target)
- Thin installer integration (HACS) + setup wizard
- Package-by-package enablement
- Controlled updates and backups

## Local Files (Protected)
- `/config/server.yaml` (per-server config, NOT in git)
- `/config/secrets.yaml` (NOT in git)
- `/config/local_data/**` (NOT in git)
- `/config/.storage/**` (do not touch unless migrating deliberately)

## Update Rules
- Updates may change repo-distributed files only.
- Never overwrite local secrets or operational data.
- If schema/data changes are required, implement explicit migrations with backups.

## Backup & Restore (Expectations)
- Modules should support export/import for their JSON stores.
- Recommend “pre-update” backup.
- Document restore steps and rollback strategy.

## Installation Checklist (High Level)
- [ ] Repo present under `/config/PaddiSense`
- [ ] `server.yaml` created from example (local)
- [ ] `secrets.yaml` populated (local)
- [ ] Packages included from `/config/configuration.yaml`
- [ ] Dashboards loaded
- [ ] Module init run where needed
- [ ] Verify version sensors per module
