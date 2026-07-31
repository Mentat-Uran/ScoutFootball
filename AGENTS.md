# AGENTS.md

You are a pragmatic AI development assistant. Answers and development must be direct, accurate, and verifiable.

## Current Project Status

The pipeline end-to-end entry points are `scoutfootball ingest` -> `scoutfootball build-features` -> `scoutfootball train`. Before executing tasks, first read the charter and capability table, and verify with the current code/artifacts — do not infer current status from the historical numbers in `docs/AGENTS_HISTORICAL_REFERENCE.md`.

## Pre-work Checks and Documentation Sources of Truth

- `C:\football` is the workspace root directory, not a Git repository; typically work from `C:\football\scoutlab`. First confirm the actual child repository and the nearest `AGENTS.md`, and do not run Git commands directly in the root directory.
- Before starting, at minimum check `git status --short`, `git branch --show-current`, `git worktree list --porcelain`, and recent logs, then decide whether to use an existing worktree or create a new one.
- Documentation responsibilities are fixed; do not maintain conflicting numbers separately across multiple files. Easily-drifting inventories should preferably be generated from code, OpenAPI, manifests, and run reports.

| Concern | Authoritative source |
| --- | --- |
| Project positioning | `docs/PROJECT_CHARTER.md` (highest priority) |
| Current task queue | top of `docs/TASKS.md` |
| Capability maturity and fact boundaries | `docs/CAPABILITIES.md` |
| Long-term dependency order and phase gates | `docs/ROADMAP.md` |
| Industry tooling and technical trade-offs | `docs/FOOTBALL_TOOLING_LANDSCAPE_2026.md` |
| User guide | `README.md` |
| Algorithm explanations | `docs/ALGORITHM.md`, `docs/MODEL_CARD.md` |
| Frontend implementation | `docs/FRONTEND_STATUS.md` |
| API/static snapshot sync | `docs/FRONTEND_SYNC.md` |
| Data contracts | `docs/DATA_CONTRACTS.md` |
| Player rating research gates | `docs/PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md` |
| Historical numbers, old P0–P8 phases, ten-layer architecture, external research basis | `docs/AGENTS_HISTORICAL_REFERENCE.md` (history only, not authoritative) |

- `docs/CODEX_CONTINUOUS_STATE.md`, `docs/deep-research-report.md`, the historical section of `docs/TASKS.md`, and `docs/AGENTS_HISTORICAL_REFERENCE.md` are only historical evidence, not the current task or capability source of truth.
- `docs/ROADMAP.md` does not write weekly, monthly, yearly, or release date targets; it only writes direct dependencies, startup conditions, exit gates, unlock results, and stop conditions. Audit dates, data `as_of`, model time splits, match times, and license retention periods are not roadmap deadlines and can be retained.
- When locating conflicts, `docs/PROJECT_CHARTER.md` is authoritative; current facts are based on code, tests, and artifacts that have passed content-level verification; capability scope is governed by `docs/CAPABILITIES.md`; task status is governed by the top of `docs/TASKS.md`; long-term roadmap only refers to dependencies and gates in `docs/ROADMAP.md`.
- Do not manually copy easily-drifting routing numbers, page counts, line counts, coverage rates, or build status across multiple documents; prefer to generate them from OpenAPI, code, manifests, tests, and run reports.

## Git and Worktree Safety

- Do not overwrite, stage, stash, reset, checkout, or clean user's uncommitted changes. When the workspace is dirty but the changes are unrelated to the task, prefer to bypass; when there is overlap, you must stop and report.
- Remote GitHub access is currently unavailable: the account used for
  `https://github.com/Mentaturan/ScoutFootball_for_World_Cup.git` is suspended
  (observed 2026-07-17: `remote: Your account is suspended`, HTTP 403). All
  remote operations — `git push`, PR creation, release publishing, GitHub
  Actions triggers, `gh` CLI calls — will fail until the account is restored
  via https://support.github.com. Continue committing locally; queue pushes
  and run `git push --set-upstream origin codex/integration` (or the relevant
  branch) once access is restored. Do not retry remote operations in a loop.
- Prefer using existing active worktrees with clear status. When isolation is needed, first check `git worktree list --porcelain`, confirm the target branch is not checked out in another worktree, then create a new worktree with a unique name; do not blindly use a fixed directory or overwrite an existing directory.
- Do not assume `main`, `codex/integration`, or any working tree is in a mergeable state. Before creating branches, squashing, or fast-forwarding, you must verify the baseline, branch pointers, workspace cleanliness, and diff scope.
- Local commits and merges only proceed when the user's current goal explicitly authorizes them; push, remote PR, deployment, formal release, tags, and release assets always require explicit authorization.
- After the merge is completed and verified, delete the temporary worktree created by the agent in this round that has been confirmed clean, to avoid accumulating large snapshots; do not delete existing user worktrees. Before deletion, parse and verify that the absolute path is within the expected `C:\football` subdirectory.
- Do not automatically create Git bundles for each round. `C:\football\backups` is treated as read-only per workspace rules; only create bundles when the user explicitly requests a backup, and first confirm the target path and remaining space.
- `git reset --hard`, history rewriting, and `git checkout --` on unknown changes are prohibited. When branch or worktree conflicts occur, first preserve the scene and choose another safe path.

## Windows and PowerShell Conventions

- This environment defaults to Windows PowerShell. Do not directly copy POSIX syntax such as `PYTHONPATH=src command`, `$(date ...)`, `rm -rf`; use PowerShell syntax, and restore the original value after temporarily modifying environment variables.
- For path operations, prefer absolute paths, `Resolve-Path`, and `-LiteralPath`. Before recursive moves or deletions, you must verify that the resolved target is within the expected worktree; do not hand PowerShell enumeration results to `cmd.exe` or other shells for deletion.
- `uv sync` is only run when the environment is missing, the lock file, or dependencies have changed. If the existing `.venv` has permission or lock conflicts, first check other processes and available worktrees; do not mask the problem by deleting the user environment or repeatedly rebuilding.
- When you need to set the source path, use the existing workable method in the current repository; if you must set `$env:PYTHONPATH`, first save the old value and restore it after the command ends.
- API and frontend joint debugging defaults to the FastAPI same-origin entry `127.0.0.1:8000`. `python -m http.server` only verifies pure static/STATIC fallback, and cannot be used to claim that LIVE API is connected.
- Long-running services or GUIs are only started when verification requires; background processes must be identifiable, stoppable, and must not leave orphan processes occupying ports.

## Local Data and Networking Boundaries

- Core capabilities run locally by default, with no requirement for accounts, public cloud, cloud sync, or telemetry. Any networked import must be explicitly triggered by the user, can be turned off, and retain source and license; do not add default uploads or background telemetry.
- Browser localStorage, browser downloads, same-machine files, and loopback API are all different storage scopes; UI, exports, and documentation must clearly distinguish them; browser-local state cannot be described as server-side audit, cross-device sync, or multi-user collaboration.
- Same-machine workspace writes are only allowed to loopback addresses by default; do not enable remote writes by default for testing convenience. Any remote access switch must remain explicit, limited to trusted networks, and clearly state the risks.
- Third-party commercial data may only be imported by the user via legal local files or explicitly authorized APIs. Do not scrape restricted sites, bypass access controls, submit credentials, attach third-party data, resell, or redistribute.
- User local data, internal evaluations, contracts, videos, minor information, and sensitive health data must not be uploaded, committed to Git, written into public samples, or used for public deployment. Debug logs and failure reports must also avoid leaking these contents.
- Public/open code does not mean third-party data is open. Any reports, static snapshots, models, and exports must inherit input licenses, attribution, redistribution, retention, and deletion boundaries.
- Parquet footer, file existence, or metadata row count does not prove content is usable; only after content-level reads, schema, and key statistical verification are completed at a locked runtime can data be written as a currently usable capability.
- STATIC fallback, samples, synthetic data, estimates, projected rosters, and model outputs must be clearly labeled, and cannot be written as real-time, official, complete coverage, or verified online capabilities.

Historical data row counts, adapter run requirements, and rating-system calibration numbers are in `docs/AGENTS_HISTORICAL_REFERENCE.md` §1–§3. They are not current facts until re-verified at a locked runtime.

## Development Principles

Project positioning, roadmap discipline, audience, and licensing boundaries are governed by `docs/PROJECT_CHARTER.md` and `docs/ROADMAP.md`. The rules below are engineering-level constraints that this file must keep locally; they do not restate charter content.

- Unless the user explicitly modifies the charter, do not plan SaaS, paid tiers, enterprise editions, sales/customer acquisition, revenue KPIs, default cloud sync, or default telemetry.
- After v1.0.0, new features must be merged via PR; direct commits to the main branch are prohibited.
- Data processing must be reproducible, cacheable, and verifiable. ETL must be idempotent and cannot depend on uncontrollable real-time web page state.
- Models must have baseline, time split, metrics, and error analysis. Before adding a new model, write evaluation metrics first; before adding a new long-term data source, write compliance boundaries first.
- Do not write planned modules as implemented capabilities. Do not write StatsBomb small-sample event capabilities as full-league capabilities.
- New features must map to at least one golden workflow of scouting decisions, match preparation, or data/model release; before real browser E2E, contracts, and failure states are complete, do not add top-level navigation or wide routes.
- Page count, route count, data row count, and model parameter count are not success metrics; prioritize improving decision workflow completion rate, evidence completeness rate, and key process reproducible pass rate.
- All capabilities are first classified as delivered, partially delivered, sample/experiment, local state, planned, or unverified; "implemented" cannot be used to mask data coverage, release, or governance gaps.
- Transfermarkt only allows manual or authorized imports. FBref is only a restricted low-frequency supplementary source, and does not bypass CAPTCHAs or anti-scraping. When publicly displaying StatsBomb data products, the data source must be attributed.
- Before adding new public charts, reports, or export products, you must confirm data source attribution and public display boundaries. Before adding new electronic tactical board exports, you must clarify whether the export contains real data, StatsBomb Open Data, or model-derived products; when included, source attribution must be retained.
- The first phase of the electronic tactical board only allows browser-local canvas, JSON projects, and lightweight exports; do not perform training, scraping, batch video transcoding, or heavy model inference in the browser.
- Whenever the frontend writes API, Parquet-derived JSON, local JSON, demo strings, or user-imported fields into `innerHTML`, it must first use existing escaping/sanitizer helpers; CSV exports must go through `csvCell()`; tactical board import/save/read must go through `TACTICAL_BOARD.sanitizeProject()`.
- It is not allowed to silently `str()` non-JSON-serializable objects into static snapshots; `scripts/export_static_frontend_data.py` must use a JSON-safe serializer and error out on non-serializable objects.
- Static fallback must be explicitly labeled STATIC; when both API and static cache are unavailable, loading failure must be displayed, not blank or incorrect data. Browser-local state (watchlist/shortlist/review notes) must not be described as backend audit or cross-device sync; the UI must label "local state".
- `goals - xG` cannot be directly used as finishing ability; sample-size shrinkage or low-confidence labeling must be used. Top N position quotas cannot replace real impact calibration.
- Availability is only a reliability/sample-size signal, not the player's ability itself; without real label verification, do not raise the availability cap back above 0.25.
- Team season aggregation must not fall back to raw minutes weighted mean; if changing aggregation, you must output holdout, league stratification, error cases, and availability permutation importance at the same time.
- When reporting position weights, you must use capped weights; do not treat raw softmax weights as actual model weights.
- Missing defensive, possession, xT/VAEP, and advanced goalkeeper fields must be expressed with missing flags and low-confidence fallback; missing values of 0 cannot be treated as real low ability.
- Before adding neural networks or other complex models, first define labels, evaluation metrics, and baseline; models trained only on team points correlation cannot be used as real player ability models. If implementing a neural network candidate model, you must retain the current rating optimizer as baseline, saving feature manifest, parameters, random seeds, input hash, holdout metrics, in-position metrics, and error case comparison.
- Reinforcement learning, GCN, Transformer, off-ball value, xG+, or tracking/video models cannot enter default capabilities without compliant sample data, labels, baseline, and model card.
- kloppy, floodlight, Common Data Format are currently only schema and conversion references; do not add them directly to `pyproject.toml` before entering the corresponding phase.
- For league-seasons with team coverage below 0.90, only output low-confidence diagnostics; do not write them as complete league rankings or top-four prediction conclusions.
- If the user requests testing the rating optimizer, first run a small-scale test on the current computer; do not call the Windows 5070 Ti server without explicit user permission.
- Dixon-Coles is the second main line of score prediction and cannot jump ahead of the rating system P0/P1/P2.
- Tactical board MP4 export, local ffmpeg, video telestration, tracking data import, and 3D/behind-goal views must only enter implementation after the current canvas model, animation schema, export fallback, report attribution, and roadmap research gates are stable; real-time cloud collaboration will not be implemented unless the user first explicitly modifies the project charter.

## Module Conventions

- Package root: `src/scoutfootball/`. Command entry: `src/scoutfootball/__main__.py`. Pipeline entry: `src/scoutfootball/pipeline.py`.
- New event action value modules go in `src/scoutfootball/action_value/`. New internal actions schemas should be written into `src/scoutfootball/action_value/schema.py` or `src/scoutfootball/schemas/`, and synced with `docs/DATA_CONTRACTS.md`.
- New neural network rating candidate models use `src/scoutfootball/models/player_rating_nn.py` or a sibling module; training scripts should only be thin entry points, not pile core logic into `scripts/`.
- New model run registries should be written into `data/reports/model_runs/` or `data/models/runs/`, and must save dataset snapshot, input hash, parameters, random seeds, dependency versions, and metrics.
- New scouting manual calibration data should be written into `data/gold/feature_store/player_truth_labels.parquet`, `data/reports/review_queue/`, or equivalent local artifacts; do not write manual labels and model predictions into the same field.
- New football-specific charts should extend `src/scoutfootball/viz/` (mplsoccer wrapper at `src/scoutfootball/viz/pitch.py`); do not pile plotting logic into Streamlit pages. Streamlit pages only read local artifacts, do not directly perform heavy training.
- Training artifacts are written to `data/models/` or `data/gold/feature_store/`, and save feature manifest, parameters, random seeds, and input hash. Data compliance and attribution requirements are written into the data source license manifest; StatsBomb Open Data derived products publicly displayed must attribute StatsBomb.
- Specialized evaluation modules: rating feature matrix → `src/scoutfootball/features/rating_matrix.py`; coverage confidence → `src/scoutfootball/evaluation/coverage_confidence.py`; availability diagnostic → `src/scoutfootball/evaluation/availability_diagnostic.py`; in-position metrics → `src/scoutfootball/evaluation/position_metrics.py`; unified confidence → `src/scoutfootball/evaluation/confidence.py`; truth label contract → `src/scoutfootball/evaluation/truth_labels.py`.

### Frontend

- `frontend/` is the static product shell: retain the Liquid Glass style of `frontend/index.html`, `frontend/style.css`, `frontend/app.js`; pages only do local display and lightweight interaction, and do not perform training, scraping, or heavy data processing in the browser. Phase 3 has completed mock->real replacement; pages read FastAPI local artifacts or contract-aligned tracked static snapshots, and no longer depend on hardcoded mock data blocks.
- `frontend/app.js` already has `escapeHtml()`, `escapeAttr()`, `sanitizeCssPercent()`, and `csvCell()`; when adding new HTML templates, attributes, style widths, or CSV exports, prefer reusing these helpers, and do not directly concatenate backend/local strings into HTML.
- Frontend payload field changes must sync API, `scripts/export_static_frontend_data.py`, static JSON, empty states, `docs/DATA_CONTRACTS.md`, and contract tests; action value main fields use `xt_per_90`/`vaep_per_90`, scouting name main field uses `player_name`.
- API paths with static mappings are allowed to fall back on network failure, 5xx, or pure static server 404; 4xx without static mappings must preserve error semantics. Exact routes, schemas, and deprecation status of the FastAPI read-only contract must be generated from the current OpenAPI/code; row counts or "real roster" scope are not maintained in this file.
- New electronic tactical boards should preferably be placed in `frontend/`: use normalized pitch coordinates, local JSON projects, object/layer/frame schemas, keyframe or step-style timelines; first phase exports PNG/PDF/WebM, MP4 only as an optional backend capability after local ffmpeg is detected. The project schema must include at least `board_id`, `title`, `sport`, `pitch_type`, `objects`, `layers`, `frames`, `version`, `created_at`, `updated_at`, `source_attribution`. Export files should preferably be written to `data/reports/tactical_exports/`; if it is only a browser-local download, do not pretend it has entered the model/report artifacts directory.
- Correspondence between frontend long-term views and backend contracts (Overview / Players / Value / Match prediction / Scouting / Action value / Reports / Tactical board) is governed by `docs/FRONTEND_STATUS.md` and `docs/FRONTEND_SYNC.md`; do not duplicate that mapping here.
- Border-radius uniformity rule: all `border-radius` values must use CSS variables defined in `:root` of `style.css`; hardcoded px values in CSS, inline styles, or JS-generated HTML are prohibited. The only exceptions are `999px` (pill shape for chips/tags/toggles) and `50%` (circle for avatars/icons). The canonical scale is `--radius-xl` (18px, large panels) > `--radius-lg` (14px, cards/dialogs) > `--radius-md` (10px, inputs/medium blocks) > `--radius-sm` (6px, small blocks/metric cells) > `--radius-xs` (4px, badges/labels). When generating HTML in `app.js`, reference these variables via `var(--radius-*)` in inline styles — never hardcode `border-radius:6px` or similar.

### Desktop

- `desktop/` is the desktop application packaging directory: `main.js` (Electron main process), `preload.js` (IPC bridge), `backend/server.py` (PyInstaller entry), `scoutfootball-server.spec` (PyInstaller configuration), `package.json` (electron-builder configuration, without `publish` block — publishing is handled by `softprops/action-gh-release` in GitHub Actions). Build artifacts (`dist/`, `backend-dist/`, `backend-build/`, `frontend/`, `node_modules/`) are not committed to git and are excluded via `.gitignore`. Build command: `bash scripts/build-desktop.sh --mac`.

## Technology Defaults

Python, uv, DuckDB + Parquet, pandas, scikit-learn, Streamlit, Plotly, mplsoccer, pytest, Ruff. The frontend continues to use the static `frontend/` as the product shell; the tactical board can evaluate Canvas/SVG or lightweight canvas libraries, but before adding dependencies, you must first prove export, responsiveness, and maintainability benefits. PyTorch is already used for rating optimization/GPU scripts; if neural networks are brought into the main project, you must sync update `pyproject.toml`, lock file, training entry, model artifacts, and evaluation documentation. socceraction is a P2 planned dependency candidate; kloppy, floodlight, common-data-format-validator are only added to `pyproject.toml` after entering P6 and completing dependency evaluation.

## Verification Commands

```bash
uv run ruff check .
uv run pytest
uv run pytest tests/unit/test_rating_optimizer_validation.py
uv run pytest tests/unit/test_rating_optimizer_validation.py tests/unit/test_composite_objective.py tests/unit/test_player_rating_nn.py
uv run pytest tests/integration/ -q
# PRS-0 rating fast gate: ruff + ~250 rating-system unit tests, finishes in a few minutes.
# Run this before iterating on rating/admission/health/identity/contract code.
powershell -ExecutionPolicy Bypass -File scripts/check-rating-fast.ps1
PYTHONPATH=src uv run python -m scoutfootball info
PYTHONPATH=src uv run python -m scoutfootball validate
PYTHONPATH=src uv run python -m scoutfootball ingest
PYTHONPATH=src uv run python -m scoutfootball build-features
PYTHONPATH=src uv run python -m scoutfootball train
PYTHONPATH=src uv run python -m scoutfootball train-rating-nn
uv run streamlit run src/scoutfootball/app/streamlit_app.py
node --check frontend/app.js
# Only verifies STATIC fallback; real API/frontend uses `scoutfootball serve --port 8000` same-origin hosting
python3 -m http.server 8600 --directory frontend
```

## Desktop Packaging

**触发条件**：完成一个有意义的功能里程碑（新端点、新数据源接入、新工作流、用户可见的行为变更）后，自动打包一个 Windows 桌面版本供用户即时使用。纯 bug 修复、文档更新、测试补充、重构不触发打包。

**版本号规则**（语义化版本）：
- PATCH（x.y.Z）：bug 修复、不新增功能
- MINOR（x.Y.0）：新增端点、新数据源、新工作流——向后兼容的功能增量
- MAJOR（X.0.0）：破坏性契约变更（本项目目前未触发）

版本号必须同步更新以下 5 处：
1. `pyproject.toml` 的 `version`
2. `src/scoutfootball/__init__.py` 的 `__version__`
3. `frontend/app.js` 的 `APP_VERSION`
4. `desktop/package.json` 的 `version`
5. `desktop/preload.js` 的 fallback version

**打包流程**（`scripts/build-desktop-windows.ps1`）：
1. PyInstaller 打 Python 后端 → `desktop/backend-dist/scoutfootball-server/scoutfootball-server.exe`
2. 复制 `frontend/` 静态文件到 `desktop/frontend/`
3. electron-builder 打 `win-unpacked/` 目录 + `app.asar`

**TRAE 沙箱限制下的打包注意事项**：
- electron-builder 的 winCodeSign 缓存因 macOS 符号链接权限失败（`Cannot create symbolic link`）。解法：手动用 7za 解压 winCodeSign .7z 文件（忽略 2 个 .dylib 符号链接错误，Windows 不需要它们），删除 .7z 文件让 app-builder 跳过重新解压。
- 如果 electron-builder 在 rcedit 阶段失败，可绕过：直接用 `npx asar pack` 重新打 app.asar 替换旧的，保留上次打包的 `win-unpacked/` 目录（含 Electron 二进制 + backend + data）。
- auto-updater 在打包模式下必须跳过（`if (app.isPackaged) { skip }`），因为没有发布服务器，`app-update.yml` 不存在会导致 ENOENT 错误。
- `waitForBackend` 超时必须 ≥ 30 秒（PyInstaller exe 首次启动需要 15-20 秒解压依赖）。

**产物**：
- `desktop/dist/win-unpacked/ScoutFootball.exe`（可直接运行）
- `desktop/dist/ScoutFootball-{version}-win-x64.zip`（压缩包）

**不内置的数据**：
- `data/raw/transfermarkt_manual/`（Transfermarkt ToS 禁止再分发）
- `data/gold/scoutlab.duckdb`（可选，缺失时 data_loader 自动回退 parquet）

## Reference Index

- Historical numbers, adapter run requirements, rating-system calibration details, ten-layer architecture, external research basis, and old P0–P8 phase records: [`docs/AGENTS_HISTORICAL_REFERENCE.md`](docs/AGENTS_HISTORICAL_REFERENCE.md) — history only, not authoritative.
- Workspace-level rules (parent `AGENTS.md` at `C:\football`): workspace layout, common commands, and notes from inspection.
