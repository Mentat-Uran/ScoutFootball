# AGENTS.md

This file describes the public repository rules for ScoutFootball contributors and coding agents.

## Sources of truth

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md): project positioning and non-profit, local-first scope.
- [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md): delivered, partial, sample, local-only, planned, and unverified capabilities.
- [`docs/TASKS.md`](docs/TASKS.md): current executable task queue.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): dependency order and exit gates.
- [`docs/DATA_CONTRACTS.md`](docs/DATA_CONTRACTS.md): data schemas and provenance rules.
- [`docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`](docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md): rating-system research plan.

When documents disagree, prefer the charter for positioning, the capability table for maturity, current code/tests for implementation facts, and the data contracts for schemas.

## Development rules

- Keep the default product local-first, personally maintained, non-profit, and free of default cloud sync, accounts, telemetry, or SaaS assumptions.
- Do not describe samples, estimates, model outputs, static snapshots, or planned work as official live data or validated player-ability truth.
- Treat third-party data, images, logos, names, and external services as separately licensed. Preserve source, date, attribution, and redistribution boundaries.
- Transfermarkt and other restricted sources are manual or explicitly authorized imports only; do not add scraping or access-control bypasses.
- Keep data processing reproducible and idempotent. Record dataset snapshots, input hashes, parameters, seeds, and metrics for model experiments.
- Keep browser-local state clearly separate from server-side or cross-device state.
- Escape or sanitize imported and generated values before inserting them into HTML. Use the existing export and validation helpers.

## Local checks

```bash
uv sync
uv run pytest -q
node --check frontend/app.js
```

Run focused tests for the files changed. Do not claim a full data or runtime validation when only static checks were run.

## Git and publication

- Inspect `git status`, the current branch, and the diff before staging.
- Stage only files belonging to the change. Never commit `.env` files, credentials, personal data, raw private datasets, logs, caches, model caches, downloaded binaries, or local runtime output.
- Checked-in GitHub workflows are manual-only through `workflow_dispatch`. Do not add push, pull-request, scheduled, or other automatic triggers without an explicit project decision.
- Keep commits small and explain behavior changes in the commit message and documentation.
