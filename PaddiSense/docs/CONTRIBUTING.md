# Contributing

## Branching
- `main` is always releasable.
- Use feature branches: `feat/<module>-<short-desc>`
- Use hotfix branches: `fix/<short-desc>`

## Pull Request Requirements
Each PR must:
- Specify impacted module(s)
- Include version bump(s) where applicable
- Preserve entity IDs unless MAJOR bump + migration notes
- Confirm no secrets committed
- Include test evidence (see Definition of Done)

## Code Style
- Prefer drop-in replacements when editing YAML.
- Avoid duplicate root YAML keys inside package files.
- Keep modules self-contained and consistent.
- Use clear naming and stable unique_ids.

## Data & Migration Discipline
- Runtime data lives in `local_data/` and is not tracked.
- If schema changes are needed:
  - bump schema version
  - create backup before migration
  - document migration and rollback
