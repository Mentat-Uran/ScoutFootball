"""Canonical architecture manifest for the scaffold."""

from __future__ import annotations

import datetime as _dt

from . import __version__
from .schemas import (
    Capability,
    CapabilityRegistry,
    DataContract,
    DataContractRegistry,
    DataDirectorySpec,
    ModuleBoundary,
    ProjectArchitecture,
    SourceLicense,
    build_core_table_definitions,
)


def build_default_architecture() -> ProjectArchitecture:
    return ProjectArchitecture(
        package_name="scoutfootball",
        status=(
            "Phase 10 pipeline and API layer initialized; "
            "CLI ingest/build-features/train/validate/serve commands, "
            "data validation gates, probability calibration, "
            "FastAPI read-only endpoints, and Streamlit multi-page app all operational."
        ),
        module_boundaries=(
            ModuleBoundary(
                name="adapters",
                purpose="External data ingestion and manual import boundaries.",
                planned_components=(
                    "statsbomb_open",
                    "football_data",
                    "clubelo",
                    "understat",
                    "fbref",
                    "transfermarkt_manual",
                ),
            ),
            ModuleBoundary(
                name="entities",
                purpose="Canonical team/player identity resolution and bridge tables.",
                planned_components=("normalization", "matching", "bridge_tables"),
            ),
            ModuleBoundary(
                name="storage",
                purpose="DuckDB, Parquet and filesystem layout utilities.",
                planned_components=("duckdb_io", "parquet_io", "metadata_logging"),
            ),
            ModuleBoundary(
                name="features",
                purpose="Feature table generation without future leakage.",
                planned_components=("team_match", "player_match", "rolling_features"),
            ),
            ModuleBoundary(
                name="models",
                purpose="Interpretable modeling tasks and artifact boundaries.",
                planned_components=("market_value", "match_prediction", "style_embedding"),
            ),
            ModuleBoundary(
                name="evaluation",
                purpose="Time-series backtests, calibration and model reports.",
                planned_components=("backtests", "calibration", "reporting"),
            ),
            ModuleBoundary(
                name="viz",
                purpose="Plotly chart definitions for research outputs.",
                planned_components=("player_compare", "trend_charts", "probability_matrix"),
            ),
            ModuleBoundary(
                name="app",
                purpose="Streamlit views that only read local artifacts.",
                planned_components=("player_compare_page", "market_value_page", "match_page"),
            ),
            ModuleBoundary(
                name="recruitment",
                purpose=(
                    "Versioned recruitment briefs, role profiles and decision "
                    "dossiers.  Personal local objects, not external facts."
                ),
                planned_components=("brief", "role_profile", "decision_dossier"),
            ),
            ModuleBoundary(
                name="opposition",
                purpose=(
                    "Source-limited match briefings, pattern cards, scenario "
                    "trees and post-match reviews.  Personal local objects; "
                    "each fact section carries an explicit fact_tier."
                ),
                planned_components=(
                    "briefing",
                    "pattern_card",
                    "scenario_tree",
                    "post_match_review",
                ),
            ),
        ),
        data_directories=(
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/statsbomb_open",
                purpose="Immutable official open-data JSON snapshots.",
                source_name="statsbomb_open",
                license_name="StatsBomb Open Data User Protocol",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/football_data",
                purpose="Downloaded CSV baselines for fixtures, results and odds.",
                source_name="football_data",
                license_name="Football-Data.co.uk non-commercial",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/clubelo",
                purpose="Team Elo snapshots before silver normalization.",
                source_name="clubelo",
                license_name="ClubElo public data",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/understat",
                purpose="Cached supplemental attacking metrics.",
                source_name="understat",
                license_name="Understat public data",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/fbref",
                purpose="Low-frequency cached standard-table extracts.",
                source_name="fbref",
                license_name="FBref personal research only; no redistribution",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/transfermarkt_manual",
                purpose="Manually provided market and contract snapshots.",
                source_name="transfermarkt_manual",
                license_name="Transfermarkt manual import only",
            ),
            DataDirectorySpec(
                layer="raw",
                relative_path="raw/reep",
                purpose=(
                    "Local Reep identity-register snapshots for identifier mapping review; "
                    "not market-value, performance, or truth-label inputs."
                ),
                source_name="reep",
                license_name="CC0 1.0 Universal",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/dimensions",
                purpose="Normalized competitions, teams, players and seasons.",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/facts",
                purpose="Normalized matches, lineups, events and market snapshots.",
            ),
            DataDirectorySpec(
                layer="silver",
                relative_path="silver/bridge",
                purpose="Cross-source identity bridge tables and review logs.",
            ),
            DataDirectorySpec(
                layer="gold",
                relative_path="gold/marts",
                purpose="Analytical marts for research and reporting.",
            ),
            DataDirectorySpec(
                layer="gold",
                relative_path="gold/feature_store",
                purpose="Reusable feature tables keyed by entity and cutoff date.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/training_sets",
                purpose="Frozen training datasets with version metadata.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/artifacts",
                purpose="Serialized models, configs and feature manifests.",
            ),
            DataDirectorySpec(
                layer="models",
                relative_path="models/oof_predictions",
                purpose="Out-of-fold predictions for validation and calibration.",
            ),
            DataDirectorySpec(
                layer="reports",
                relative_path="reports/html",
                purpose="Rendered local HTML research reports.",
            ),
            DataDirectorySpec(
                layer="reports",
                relative_path="reports/pdf",
                purpose="Exported PDF reports when later enabled.",
            ),
            DataDirectorySpec(
                layer="logs",
                relative_path="logs/ingestion",
                purpose="Source request logs, hashes and ingest manifests.",
            ),
            DataDirectorySpec(
                layer="logs",
                relative_path="logs/validation",
                purpose="Schema checks, data-quality reports and drift warnings.",
            ),
        ),
        supported_commands=(
            "uv sync",
            "uv run pytest",
            "uv run ruff check .",
            "uv run python -m scoutfootball info",
            "uv run python -m scoutfootball capabilities",
            "uv run python -m scoutfootball data-contracts",
            "uv run python -m scoutfootball list-adapters [--source S] [--capability C] [--json]",
            "uv run python -m scoutfootball adapter-compatibility [--source S] [--json]",
            "uv run python -m scoutfootball ingest",
            "uv run python -m scoutfootball build-features",
            "uv run python -m scoutfootball train",
            "uv run python -m scoutfootball train-rating-nn",
            "uv run python -m scoutfootball validate",
            "uv run python -m scoutfootball source-health",
            "uv run python -m scoutfootball inspect-raw-source",
            "uv run python -m scoutfootball reep-identity-lookup",
            "uv run python -m scoutfootball contract-quality",
            "uv run python -m scoutfootball model-admission",
            "uv run python -m scoutfootball discard-model-run <run_id>",
            "uv run python -m scoutfootball reject-model-run <run_id> --decision <text>",
            "uv run python -m scoutfootball promote-model-run <run_id> --decision <text>",
            "uv run python -m scoutfootball rollback-model-run <backup_id> --decision <text>",
            "uv run python -m scoutfootball validate-decision-package <path>",
            "uv run python -m scoutfootball record-source-snapshot",
            "uv run python -m scoutfootball record-source-policy",
            "uv run python -m scoutfootball record-quality-audit",
            "uv run python -m scoutfootball record-quality-threshold",
            "uv run python -m scoutfootball preflight",
            "uv run python -m scoutfootball preflight --evidence-out <path>",
            "uv run python -m scoutfootball optimizer-preflight",
            "uv run python -m scoutfootball action-value",
            "uv run python -m scoutfootball action-value-matches",
            "uv run python -m scoutfootball export-ratings",
            "uv run python -m scoutfootball import-truth-labels",
            "uv run python -m scoutfootball import-transfermarkt-truth-labels",
            "uv run python -m scoutfootball transfermarkt-identity-review",
            "uv run python -m scoutfootball reconcile-transfermarkt-truth-labels",
            "uv run python -m scoutfootball audit-truth-labels",
            "uv run python -m scoutfootball backtest",
            "uv run python -m scoutfootball tune-predictions",
            "uv run python -m scoutfootball optimize-ensemble",
            "uv run python -m scoutfootball serve",
            "uv run python -m scoutfootball tournament",
            "uv run python -m scoutfootball create-brief",
            "uv run python -m scoutfootball list-briefs",
            "uv run python -m scoutfootball show-brief <brief_id>",
            "uv run python -m scoutfootball validate-brief <path>",
            "uv run python -m scoutfootball create-briefing",
            "uv run python -m scoutfootball list-briefings",
            "uv run python -m scoutfootball show-briefing <briefing_id>",
            "uv run python -m scoutfootball validate-briefing <path>",
            "uv run python -m scoutfootball create-dossier",
            "uv run python -m scoutfootball list-dossiers",
            "uv run python -m scoutfootball show-dossier <dossier_id>",
            "uv run python -m scoutfootball validate-dossier <path>",
            "uv run python -m scoutfootball create-review",
            "uv run python -m scoutfootball list-reviews",
            "uv run python -m scoutfootball show-review <review_id>",
            "uv run python -m scoutfootball validate-review <path>",
            "uv run python -m scoutfootball export-local-pack [--output <path>]",
            "uv run python -m scoutfootball import-local-pack [--from <path>] [--confirm]",
            "uv run streamlit run src/scoutfootball/app/streamlit_app.py",
        ),
    )


def build_capability_registry() -> CapabilityRegistry:
    """Build the canonical capability registry from static definitions.

    Capabilities are grouped by domain and include cross-references to
    CLI commands, API paths, and frontend views where applicable. This
    registry is the single source of truth for "what can ScoutFootball do"
    and is consumed by the ``capabilities`` CLI command, tests, and docs.
    """
    caps = (
        Capability(
            id="pipeline.adapters",
            name="适配器清单注册表",
            description=(
                "机器可读的源适配器清单和本地准入矩阵：声明每个注册数据源的能力、"
                "字段映射、转换损失及其与数据契约的关系。是 I1 开放互操作基线的入口，"
                "只读元数据，不触发实际数据接入。"
            ),
            domain="data_pipeline",
            cli_commands=("list-adapters", "adapter-compatibility"),
            api_paths=("/adapters", "/adapters/compatibility"),
            notes=(
                "Manifest 是保守的：未记录的能力或映射直接省略，不猜测。"
                "Tracking/video 能力位保留但当前无适配器声明，"
                "需待合规样本数据就绪后才进入后续 I1 切片。"
            ),
        ),
        Capability(
            id="pipeline.ingest",
            name="数据接入",
            description=(
                "从 StatsBomb、Football-Data、ClubElo 等数据源"
                "拉取原始数据并落地到本地 Parquet。"
            ),
            domain="data_pipeline",
            cli_commands=("ingest",),
            data_artifacts=(
                "raw/statsbomb_open",
                "raw/football_data",
                "raw/clubelo",
                "raw/understat",
                "raw/fbref",
                "raw/transfermarkt_manual",
            ),
        ),
        Capability(
            id="pipeline.build_features",
            name="特征工程",
            description=(
                "从原始数据构建球队级、球员级特征表，"
                "含时间窗口滚动特征，无未来泄露。"
            ),
            domain="data_pipeline",
            cli_commands=("build-features",),
            data_artifacts=("gold/feature_store",),
        ),
        Capability(
            id="pipeline.validate",
            name="数据验证门禁",
            description=(
                "训练前的数据质量校验：schema、行数、非空率、"
                "唯一性、时间连续性、来源覆盖度。"
            ),
            domain="data_pipeline",
            cli_commands=(
                "validate",
                "preflight",
                "optimizer-preflight",
                "source-health",
                "inspect-raw-source",
                "reep-identity-lookup",
                "contract-quality",
                "model-admission",
                "research-health",
                "discard-model-run",
                "reject-model-run",
                "promote-model-run",
                "rollback-model-run",
                "validate-decision-package",
                "record-source-snapshot",
                "record-source-policy",
                "record-quality-audit",
                "record-quality-threshold",
            ),
            api_paths=("/health", "/artifacts"),
        ),
        Capability(
            id="ratings.training",
            name="球员评分训练",
            description="多模型球员评分训练：市场价值、阵容评分、神经网络候选。",
            domain="player_ratings",
            cli_commands=("train", "train-rating-nn"),
            data_artifacts=(
                "models/artifacts",
                "models/training_sets",
                "models/oof_predictions",
            ),
        ),
        Capability(
            id="ratings.export",
            name="评分导出",
            description="将优化后的球员评分导出为 DuckDB 数据库，供前端和 API 使用。",
            domain="player_ratings",
            cli_commands=("export-ratings",),
            api_paths=("/ratings", "/ratings/meta", "/ratings/snapshots"),
            frontend_views=("players", "value"),
        ),
        Capability(
            id="ratings.truth_labels",
            name="真值标签管理",
            description="导入球探评审和 Transfermarkt 快照作为真值标签，审计监督合规性。",
            domain="player_ratings",
            cli_commands=(
                "import-truth-labels",
                "import-transfermarkt-truth-labels",
                "transfermarkt-identity-review",
                "reconcile-transfermarkt-truth-labels",
                "audit-truth-labels",
            ),
            api_paths=(
                "/reports/truth-labels",
                "/reports/transfermarkt-identities",
            ),
        ),
        Capability(
            id="predictions.match",
            name="比赛结果预测",
            description="Poisson、Dixon-Coles、集成模型等多种比赛结果预测，含概率校准。",
            domain="match_predictions",
            cli_commands=("backtest", "tune-predictions", "optimize-ensemble"),
            api_paths=(
                "/predictions/{home_team}/{away_team}",
                "/predictions/meta",
                "/predictions/ensemble/weights",
                "/predictions/models/comparison",
                "/predictions/staleness",
                "/predictions/team-accuracy/{team_id}",
                "/predictions/{home_team}/{away_team}/attribution",
                "/predictions/{home_team}/{away_team}/attribution/ci",
                "/predictions/{home_team}/{away_team}/ensemble-attribution",
                "/predictions/{home_team}/{away_team}/ensemble-attribution/ci",
                "/predictions/{home_team}/{away_team}/diagnostics",
                "/predictions/{home_team}/{away_team}/h2h",
                "/predictions/{home_team}/{away_team}/h2h-bias-correction",
                "/predictions/{home_team}/{away_team}/momentum",
            ),
            frontend_views=("matches",),
        ),
        Capability(
            id="predictions.calibration",
            name="概率校准与回测",
            description="时间序列回测、保序回归校准、RPS/Brier/Log Loss 指标、置信区间。",
            domain="match_predictions",
            cli_commands=("backtest", "tune-predictions"),
            api_paths=(
                "/predictions/calibration",
                "/predictions/backtest",
                "/predictions/tuning",
                "/predictions/drift",
                "/predictions/drift/timeline",
                "/predictions/calibration/reliability",
                "/predictions/calibration/scoreline",
                "/predictions/calibration/comparison",
                "/predictions/calibration/confidence-distribution",
                "/predictions/calibration/error-analysis",
                "/predictions/calibration/outcome-distribution",
                "/predictions/calibration/temporal-validation",
                "/predictions/calibration/probability-heatmap",
                "/predictions/calibration/ci-plot",
                "/predictions/calibration/ci-coverage",
                "/predictions/calibration/ci-width",
                "/predictions/calibration/fold-comparison",
                "/predictions/calibration/league-errors",
                "/predictions/calibration/feature-importance",
                "/predictions/calibration/drift-heatmap",
                "/predictions/calibration/error-clustering",
                "/predictions/calibration/data-drift",
                "/predictions/calibration/stress-test",
                "/predictions/calibration/team-drift",
                "/predictions/calibration/team-profile",
                "/predictions/calibration/uncertainty",
                "/predictions/calibration/profit-loss",
                "/predictions/calibration/trajectory",
                "/predictions/calibration/difficulty",
                "/predictions/calibration/streaks",
                "/predictions/calibration/report-card",
                "/predictions/calibration/anomalies",
            ),
            frontend_views=("matches", "calibration", "backtest"),
        ),
        Capability(
            id="predictions.value_bet",
            name="价值投注分析",
            description="对比模型概率与市场赔率，识别价值投注机会。",
            domain="match_predictions",
            api_paths=("/predictions/{home_team}/{away_team}/value",),
            frontend_views=("matches",),
        ),
        Capability(
            id="team.analysis",
            name="球队分析",
            description="球队实力对比、风格聚类、风格演变、战术画像、赛程难度。",
            domain="team_analysis",
            api_paths=(
                "/teams",
                "/teams/compare",
                "/teams/strength",
                "/teams/style-clusters",
                "/teams/style-clusters/similarity",
                "/teams/style-atlas",
                "/teams/style-matchup",
                "/teams/style-evolution",
                "/teams/{team}/style-neighbors",
                "/teams/{team}/style-percentiles",
                "/teams/{team}/style-drift",
                "/teams/{team}/style-drift-neighbors",
                "/teams/cross-league-depth",
            ),
            frontend_views=("teams", "league"),
        ),
        Capability(
            id="team.action_profile",
            name="球队动作画像",
            description="基于事件数据的球队动作风格画像和跨联赛对比。",
            domain="team_analysis",
            api_paths=(
                "/teams/action-profile",
                "/teams/action-atlas",
                "/teams/action-evolution",
                "/teams/{team}/action-percentiles",
                "/teams/{team}/action-similarity",
                "/teams/cross-league-action",
            ),
            frontend_views=("actions",),
        ),
        Capability(
            id="league.season_projection",
            name="联赛赛季预测",
            description="蒙特卡洛模拟联赛最终排名、夺冠/降级概率、赛程难度分析。",
            domain="team_analysis",
            api_paths=(
                "/league/season-projection",
                "/league/form-table",
                "/league/fixture-difficulty",
            ),
            frontend_views=("league",),
        ),
        Capability(
            id="player.comparison",
            name="球员对比",
            description="多球员并排对比，百分位矩阵、指标排名、风格相似度。",
            domain="player_analysis",
            api_paths=(
                "/players",
                "/players/compare",
                "/players/compare-multi",
                "/players/{player_name}",
                "/players/{player_name}/similar",
                "/players/{player_name}/career-trajectory",
                "/player/{player_name}/profile",
            ),
            frontend_views=("compare", "players"),
        ),
        Capability(
            id="player.style_fit",
            name="球员风格适配",
            description="球员与球队风格匹配度、位置角色适配、风格邻居。",
            domain="player_analysis",
            api_paths=(
                "/players/{player_name}/style-fit",
                "/players/{player_name}/role-fit",
                "/players/{player_name}/peer-benchmark",
            ),
            frontend_views=("players",),
        ),
        Capability(
            id="position.analysis",
            name="位置分析",
            description="位置深度画像、位置风格演变、跨联赛位置对比、位置动作画像。",
            domain="player_analysis",
            api_paths=(
                "/positions/depth-profile",
                "/positions/style-evolution",
                "/positions/action-profile",
                "/positions/trend-overlay",
                "/positions/{position_group}/style-drift",
                "/positions/{position_group}/style-drift-neighbors",
                "/positions/{position_group}/cross-league",
                "/positions/{position_group}/action-similarity",
            ),
            frontend_views=("players",),
        ),
        Capability(
            id="action_value.core",
            name="动作价值计算",
            description="基于 SPADL 的事件-动作转换，xT 期望值计算，球员动作价值聚合。",
            domain="action_value",
            cli_commands=("action-value", "action-value-matches"),
            api_paths=(
                "/action-values",
                "/action-values/evidence",
                "/action-values/evidence/{player_id}",
                "/action-values/players/{player_id}/context",
                "/action-values/players/{player_id}/rating-links",
                "/action-values/matches",
                "/value-summary",
            ),
            frontend_views=("actions",),
        ),
        Capability(
            id="action_value.position_similarity",
            name="动作位置相似度",
            description="基于动作分布的位置相似度分析，跨联赛动作对比。",
            domain="action_value",
            api_paths=(
                "/positions/{position_group}/action-similarity",
                "/teams/cross-league-action",
            ),
            frontend_views=("actions",),
        ),
        Capability(
            id="scouting.targets",
            name="球探目标推荐",
            description="基于球队需求的引援目标推荐，风格匹配度、位置缺口分析。",
            domain="scouting",
            api_paths=(
                "/teams/{team}/scouting-targets",
                "/teams/{team}/scouting-style-match/{position_group}",
                "/teams/{team}/scouting-dashboard",
                "/teams/{team}/position-gap-report",
                "/teams/style-clusters/recruits",
            ),
            frontend_views=("scouting",),
        ),
        Capability(
            id="scouting.watchlist",
            name="观察名单与短名单",
            description="上升/下滑球员观察名单、球探短名单、评审队列管理。",
            domain="scouting",
            api_paths=(
                "/scouting/risers-decliners",
                "/watchlist",
                "/shortlist",
                "/review-queue",
            ),
            frontend_views=("scouting",),
        ),
        Capability(
            id="scouting.workspace",
            name="球探工作区",
            description="本地球探评审工作区，支持多工作区版本管理和并发控制。",
            domain="scouting",
            api_paths=(
                "/scouting-workspaces",
                "/scouting-workspaces/capabilities",
                "/scouting-workspaces/latest",
                "/scouting-workspaces/{workspace_id}",
                "/scouting-workspaces/{workspace_id} (PUT)",
            ),
            frontend_views=("scouting",),
        ),
        Capability(
            id="recruitment.briefs",
            name="招募需求 brief",
            description=(
                "版本化招募需求 brief：球队、位置、角色、预算、年龄、合同、"
                "联赛、语言和风险偏好。维护者本地对象，非外部事实。"
                "支持原子写、备份、乐观并发和 Core 契约复用。"
            ),
            domain="recruitment",
            cli_commands=(
                "create-brief",
                "list-briefs",
                "show-brief",
                "validate-brief",
            ),
            api_paths=(
                "/recruitment/briefs",
                "/recruitment/briefs (POST)",
                "/recruitment/briefs/{brief_id}",
                "/recruitment/briefs/{brief_id}/backups",
                "/recruitment/briefs/{brief_id}/backups/{backup_filename}",
                "/recruitment/briefs/{brief_id}/diff",
                "/recruitment/briefs/{brief_id}/restore (POST)",
                "/recruitment/contracts",
            ),
        ),
        Capability(
            id="recruitment.dossiers",
            name="决策档案",
            description=(
                "版本化决策档案：整合支持证据、反证、对比、风险和人工判断，"
                "形成从需求 brief 到人工结论的可追溯 round-trip。"
                "维护者本地对象，非外部事实。"
                "支持原子写、备份、乐观并发和 Core 契约复用。"
            ),
            domain="recruitment",
            cli_commands=(
                "create-dossier",
                "list-dossiers",
                "show-dossier",
                "validate-dossier",
            ),
            api_paths=(
                "/recruitment/dossiers",
                "/recruitment/dossiers (POST)",
                "/recruitment/dossiers/{dossier_id}",
                "/recruitment/dossiers/{dossier_id} (PUT)",
                "/recruitment/dossiers/{dossier_id}/backups",
                "/recruitment/dossiers/{dossier_id}/backups/{backup_filename}",
                "/recruitment/dossiers/{dossier_id}/diff",
                "/recruitment/dossiers/{dossier_id}/restore (POST)",
            ),
        ),
        Capability(
            id="opposition.briefings",
            name="比赛对手简报",
            description=(
                "来源受限的比赛对手简报：每条事实段携带 fact_tier "
                "(official/recorded/estimated/unknown)，区分官方、记录、"
                "估计和未知。维护者本地对象，非外部事实。"
                "支持原子写、备份、乐观并发和 Core 契约复用。"
            ),
            domain="opposition",
            cli_commands=(
                "create-briefing",
                "list-briefings",
                "show-briefing",
                "validate-briefing",
            ),
            api_paths=(
                "/opposition/briefs",
                "/opposition/briefs (POST)",
                "/opposition/briefs/{briefing_id}",
                "/opposition/briefs/{briefing_id} (PUT)",
                "/opposition/briefs/{briefing_id}/backups",
                "/opposition/briefs/{briefing_id}/backups/{backup_filename}",
                "/opposition/briefs/{briefing_id}/diff",
                "/opposition/briefs/{briefing_id}/restore (POST)",
                "/opposition/contracts",
            ),
        ),
        Capability(
            id="opposition.post_match_reviews",
            name="赛后复盘",
            description=(
                "版本化赛后复盘：比较假设-计划-执行-结果，记录被证伪的模式、"
                "新问题和支持/反对证据，形成从赛前简报到赛后结论的可追溯 "
                "round-trip。每条证据携带 fact_tier，区分官方、记录、估计和"
                "未知。维护者本地对象，非外部事实。"
                "支持原子写、备份、乐观并发和 Core 契约复用。"
            ),
            domain="opposition",
            cli_commands=(
                "create-review",
                "list-reviews",
                "show-review",
                "validate-review",
            ),
            api_paths=(
                "/opposition/reviews",
                "/opposition/reviews (POST)",
                "/opposition/reviews/{review_id}",
                "/opposition/reviews/{review_id} (PUT)",
                "/opposition/reviews/{review_id}/backups",
                "/opposition/reviews/{review_id}/backups/{backup_filename}",
                "/opposition/reviews/{review_id}/diff",
                "/opposition/reviews/{review_id}/restore (POST)",
            ),
        ),
        Capability(
            id="worldcup.tournament",
            name="世界杯锦标赛管理",
            description="2026 世界杯 48 队锦标赛状态管理：积分榜、晋级计算、淘汰赛生成。",
            domain="world_cup",
            cli_commands=(
                "tournament",
                "tournament show",
                "tournament standings",
                "tournament apply",
                "tournament clear",
                "tournament reset",
                "tournament matches",
                "tournament scenarios",
                "tournament qualification",
                "tournament tiebreaks",
            ),
            api_paths=(
                "/world-cup/groups",
                "/world-cup/schedule",
                "/worldcup/teams",
                "/world-cup/contracts",
                "/world-cup/tournament/summary",
                "/world-cup/tournament/standings",
                "/world-cup/tournament/standings-probabilities",
                "/world-cup/tournament/overall-leaderboard",
                "/world-cup/tournament/qualification-impact",
                "/world-cup/tournament/tiebreak-diagnostics",
                "/world-cup/tournament/matches",
                "/world-cup/tournament/match-predictions",
                "/world-cup/tournament/match-impact",
                "/world-cup/tournament/top-matches",
                "/world-cup/tournament/scenarios/{team}",
                "/world-cup/tournament/group-simulation",
                "/world-cup/tournament/export",
                "/world-cup/tournament/import (POST)",
                "/world-cup/tournament/import/preview (POST)",
                "/world-cup/tournament/result (POST/DELETE)",
                "/world-cup/tournament/reset (POST)",
                "/world-cup/match-briefings/{home}/{away}/spotlight",
                "/world-cup/teams/{team}/form-trend",
            ),
            frontend_views=("wc_schedule", "wc_knockout", "wc_tournament"),
        ),
        Capability(
            id="worldcup.knockout",
            name="世界杯淘汰赛",
            description="淘汰赛对阵生成、结果录入、晋级路径、概率模拟。",
            domain="world_cup",
            cli_commands=(
                "tournament knockout",
                "tournament knockout generate",
                "tournament knockout show",
                "tournament knockout apply",
                "tournament knockout clear",
            ),
            api_paths=(
                "/world-cup/knockout",
                "/world-cup/tournament/knockout",
                "/world-cup/tournament/knockout/{match_id}/briefing",
                "/world-cup/tournament/knockout/{match_id}/review",
                "/world-cup/tournament/knockout/reviews",
                "/world-cup/tournament/knockout/probabilities",
                "/world-cup/tournament/knockout/scenarios/{team}",
                "/world-cup/tournament/knockout/match-impact",
                "/world-cup/tournament/knockout/generate (POST)",
                "/world-cup/tournament/knockout/result (POST/DELETE)",
            ),
            frontend_views=("wc_knockout", "wc_tournament"),
        ),
        Capability(
            id="worldcup.predictions",
            name="世界杯预测",
            description="世界杯小组赛预测、出线概率、淘汰赛概率、比赛预测。",
            domain="world_cup",
            api_paths=(
                "/world-cup/predictions",
                "/world-cup/predictions/{home_team}/{away_team}",
                "/world-cup/match-briefings/{home_team}/{away_team}",
                "/world-cup/outlook/{team}",
            ),
            frontend_views=("wc_probability", "wc_compare"),
        ),
        Capability(
            id="worldcup.squads",
            name="世界杯名单分析",
            description="各队大名单、阵容平衡对比、球探需求分析。",
            domain="world_cup",
            api_paths=(
                "/world-cup/squads/{team}",
                "/world-cup/squads/{team}/scouting-needs",
                "/world-cup/squad-balance-comparison/{team_a}/{team_b}",
            ),
            frontend_views=("wc_squads", "wc_compare"),
        ),
        Capability(
            id="api.server",
            name="API 服务",
            description="FastAPI 只读 API 服务，支持 CORS、静态文件托管、工作区写操作。",
            domain="infrastructure",
            cli_commands=("serve",),
            api_paths=(
                "/health",
                "/health/detailed",
                "/health/research",
                "/license",
                "/search",
                "/local-pack/export",
                "/local-pack/import (POST)",
                "/tactical-board/capabilities",
                "/tactical-board/export/mp4 (POST)",
            ),
        ),
        Capability(
            id="local.portable_pack",
            name="本地便携包",
            description=(
                "将本地招募 brief 与对手 briefing 打包为带 section SHA-256 的"
                " JSON 便携包，用于跨机器迁移、本地备份和恢复；"
                "导入时按 section 校验哈希、按 record 处理冲突，"
                "不依赖云同步或外部账号。"
            ),
            domain="infrastructure",
            cli_commands=(
                "export-local-pack",
                "import-local-pack",
            ),
            api_paths=(
                "/local-pack/export",
                "/local-pack/import (POST)",
            ),
        ),
        Capability(
            id="frontend.analyst_console",
            name="分析师工作台",
            description=(
                "单页前端应用，包含球员、球队、预测、球探、"
                "动作价值、世界杯等多个分析视图。"
            ),
            domain="infrastructure",
            frontend_views=(
                "overview",
                "players",
                "compare",
                "value",
                "matches",
                "teams",
                "league",
                "scouting",
                "actions",
                "reports",
                "tactical",
                "wc_schedule",
                "wc_squads",
                "wc_compare",
                "wc_probability",
                "wc_knockout",
                "wc_tournament",
                "license",
                "data",
                "calibration",
                "backtest",
                "help",
                "workflow",
                "versions",
            ),
            data_artifacts=("frontend/data/",),
        ),
        Capability(
            id="data.artifacts",
            name="数据产物清单",
            description="所有数据产物的元数据清单、版本信息、来源归属。",
            domain="infrastructure",
            cli_commands=("info", "capabilities", "data-contracts"),
            api_paths=(
                "/artifacts",
                "/model-runs",
                "/reports/model-runs",
                "/reports/model-runs/{run_id}",
            ),
            frontend_views=("data",),
        ),
    )

    domains = tuple(sorted({c.domain for c in caps}))

    return CapabilityRegistry(
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        package_version=__version__,
        domains=domains,
        capabilities=caps,
    )


def _source_licenses() -> dict[str, SourceLicense]:
    """Return the canonical source license definitions."""
    return {
        "statsbomb_open": SourceLicense(
            source_name="statsbomb_open",
            license_name="StatsBomb Open Data User Protocol",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="https://github.com/statsbomb/open-data",
            notes="Free for research; attribution required.",
        ),
        "football_data": SourceLicense(
            source_name="football_data",
            license_name="Football-Data.co.uk non-commercial",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="https://www.football-data.co.uk/",
            notes="Free for non-commercial use; attribution suggested.",
        ),
        "clubelo": SourceLicense(
            source_name="clubelo",
            license_name="ClubElo public data",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="http://api.clubelo.com/",
            notes="Public data; attribution suggested.",
        ),
        "understat": SourceLicense(
            source_name="understat",
            license_name="Understat public data",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="https://understat.com/",
            notes="Public data; scrape respects robots.txt and ToS.",
        ),
        "fbref": SourceLicense(
            source_name="fbref",
            license_name="FBref personal research only",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="https://fbref.com/",
            notes="Personal research only; no redistribution of raw data.",
        ),
        "transfermarkt_manual": SourceLicense(
            source_name="transfermarkt_manual",
            license_name="Transfermarkt manual import only",
            attribution_required=True,
            redistribution_allowed=False,
            commercial_use_allowed=False,
            source_url="https://www.transfermarkt.com/",
            notes="Manual import only; no automated scraping.",
        ),
        "reep": SourceLicense(
            source_name="reep",
            license_name="CC0 1.0 Universal",
            attribution_required=False,
            redistribution_allowed=True,
            commercial_use_allowed=True,
            source_url="https://github.com/withqwerty/reep",
            notes=(
                "Repository-published Wikidata-derived identity register; local use is limited "
                "to identifier mapping review and does not establish market-value "
                "or performance facts."
            ),
        ),
    }


def build_data_contract_registry() -> DataContractRegistry:
    """Build the canonical data contract registry.

    Combines core table schemas with source license, lineage and
    coverage metadata into a single machine-readable catalog.
    Raw-layer artifacts carry explicit source licenses; derived
    layers inherit from their upstream sources.
    """
    licenses = _source_licenses()
    arch = build_default_architecture()
    table_defs = build_core_table_definitions()

    raw_dirs = [d for d in arch.data_directories if d.layer == "raw"]
    raw_contracts = tuple(
        DataContract(
            artifact_id=d.relative_path,
            layer=d.layer,
            purpose=d.purpose,
            license=licenses.get(d.source_name) if d.source_name else None,
            recorded=d.recorded,
            recorded_note=d.recorded_note,
        )
        for d in raw_dirs
    )

    silver_contracts = tuple(
        DataContract(
            artifact_id=t.name,
            layer=t.layer,
            purpose=t.purpose,
            primary_keys=t.primary_keys,
            columns=t.columns,
        )
        for t in table_defs
    )

    derived_dirs = [
        d for d in arch.data_directories if d.layer not in ("raw", "silver")
    ]
    derived_contracts = tuple(
        DataContract(
            artifact_id=d.relative_path,
            layer=d.layer,
            purpose=d.purpose,
            recorded=d.recorded,
            recorded_note=d.recorded_note,
        )
        for d in derived_dirs
    )

    all_contracts = raw_contracts + silver_contracts + derived_contracts
    layers = tuple(sorted({c.layer for c in all_contracts}))

    return DataContractRegistry(
        generated_at=_dt.datetime.now(_dt.UTC).isoformat(),
        package_version=__version__,
        layers=layers,
        contracts=all_contracts,
    )
