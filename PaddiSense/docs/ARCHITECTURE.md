# PaddiSense Architecture

## Purpose
High-level system architecture for PaddiSense (Home Assistant OS) with offline-first operation.

## Core Principles
- HAOS only
- Offline-first (no internet required for core workflows)
- Local-only by default (explicit export/import for sharing)
- Updates must not overwrite local state (`server.yaml`, `secrets.yaml`, `local_data/`, `.storage/`)

## Separation of Concerns
### Repo-distributed (Git/HACS)
- Module packages (`package.yaml`)
- Dashboards/views/templates
- Tooling scripts (shell/python) if used
- Default schema/templates (seed JSON)

### Per-server protected
- `server.yaml`
- `secrets.yaml`
- `local_data/**`
- `.storage/**` (unless a deliberate migration exists)

## Module Topology
- Farm Registry (shared core, standalone)
- IPM (inventory)
- ASM (assets/parts/service events)
- Weather (local gateway + API stations)
- PWM (water management)

## Data Strategy
- Local JSON is the primary backing store for operational data.
- HA entities are views over JSON state (sensors/helpers/templates).
- All write operations must validate input and be resilient offline.

## Versioning
- SemVer per module (VERSION file).
- Each module exposes a version sensor in HA.

## Security Model
- No secrets in git.
- No remote control surfaces without explicit configuration.
- Principle of least privilege for integrations.

## Open Decisions
Track unresolved architectural questions here:
- Registry storage location and migration approach
- Multi-user record locking strategy
- Update/installer UX (thin integration wizard scope)
