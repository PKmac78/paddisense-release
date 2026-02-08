# CLAUDE.md — PaddiSense Core Rules (Minimal)

PaddiSense is a modular farm-management platform for **Home Assistant OS (HAOS)** built as **packages + dashboards** with **local JSON data**.

## Non-negotiables
- **HAOS only**
- **Offline-first:** core workflows must run without internet.
- **Local-only by default:** secrets and operational data stay on the server unless explicitly exported.
- **Updates must not overwrite local state:** never touch `secrets.yaml`, `server.yaml`, `local_data/`, or `.storage` unless a deliberate migration exists.
- **Mobile-first UI:** large touch targets, high contrast, dark-mode compatible; avoid hardcoded colors where feasible.

## Repository boundaries
- Repo contains: packages (YAML), dashboards, scripts/tools, default schemas/templates.
- Per-server local files (protected): `server.yaml`, `secrets.yaml`, `local_data/**`, `.storage/**`.

## Module design standard
Each module is **self-contained**:
- One module folder (e.g. `ipm/`, `asm/`, `weather/`, `pwm/`)
- Prefer **single `package.yaml`** per module (avoid duplicate root YAML keys).
- Runtime data stored under `/config/local_data/<module>/` (not tracked in git).
- Each module has a `VERSION` file and exposes a **version sensor** in HA.

## Shared Core: Farm Registry
- Farm Registry is **standalone** and consumed by all modules.
- IDs are **generated only** (no manual ID entry); UI shows names, not IDs.
- Support export/import for backups and migration between servers.

## PWM / ESPHome control contract
- HA/PWM controls **valves/actuators only** (never raw relays).
- Devices may have 1–2 actuators; if 2, they are logically paired (same role).
- Watchdog/faults: raise alert + mark unavailable; **do not force stop**.

## Git hygiene
- No secrets in git.
- Preserve entity IDs unless MAJOR bump + migration notes.
- Keep `main` always releasable; use feature/fix branches and PRs.

## Where detailed docs live
This file stays minimal. Put implementation details in repo docs, e.g.:
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/IPM.md`, `docs/ASM.md`, `docs/WEATHER.md`, `docs/PWM.md`, `docs/WSS.md`
- `reference/` for schemas and command docs
