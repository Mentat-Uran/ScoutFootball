# ScoutFootball — Local-First Football Analytics & Player Research

ScoutFootball is a local-first, open-source football analytics and research toolkit. It combines reproducible data workflows, interpretable rating experiments, match prediction baselines, and a browser-based local workbench.

The project is personally maintained and non-profit. It is not a SaaS product, data marketplace, or cloud collaboration service. Public code does not change the license or redistribution terms of third-party data.

## Scope

- Python pipeline for ingesting lawful local data, validating contracts, building features, and running research experiments.
- DuckDB/Parquet-oriented local data layout.
- FastAPI and static frontend surfaces for local analysis.
- Player-rating and match-prediction candidates with explicit uncertainty and evidence boundaries.
- Browser-local scouting, briefing, and tactical-board workflows where documented.

The rating system is a research candidate, not a validated measure of real player ability. Samples, estimates, model outputs, and static snapshots must not be presented as official live data or complete coverage.

Project positioning and current capability boundaries are documented in [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) and [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md). The current research plan is [`docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md`](docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md).

## Local setup

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), and Node.js for frontend checks.

```bash
uv sync
uv run python -m scoutfootball --help
uv run pytest -q                 # unit/integration; e2e requires -m e2e explicitly
node --check frontend/app.js
```

To run the local service:

```bash
uv run python -m scoutfootball serve --host 127.0.0.1 --port 8000
```

The service is intended to remain local by default. Do not expose it to an untrusted network without reviewing the security and data boundaries first.

## Data and attribution

Do not commit personal files, credentials, raw private datasets, local logs, model caches, downloaded binaries, or live server data. Third-party sources must be imported lawfully and retain their attribution, license, date, and scope. Manual imports are preferred where a source does not grant redistribution rights; no restricted-site scraping is part of the default project.

The public repository contains source code and only deliberately selected sample or static assets. A local checkout may contain additional ignored data required for experiments.

## Automation

The repository includes opt-in workflows for checks and release tasks. Existing data, export, optimization, and release workflows are manual-only through `workflow_dispatch`. The deliberately small `brief-ci.yml` runs on pull requests targeting `main` and pushes to non-`main` branches; it does not run on pushes to `main`. A passing workflow is not a deployment or data-license claim.

## Contributing

Read [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and the relevant contract or capability document before changing behavior. Keep changes reproducible, document evidence boundaries, and add focused tests for changed contracts.

## License

The project code is released under the [MIT License](LICENSE). Third-party data, logos, names, images, and external services remain subject to their own terms.
