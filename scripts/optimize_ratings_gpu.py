#!/usr/bin/env python3
"""
球员评分权重优化器 — PyTorch GPU 版本
在 Windows + RTX 5070 Ti 上运行，几秒完成一次优化循环。

使用方法 (Windows):
  1. pip install torch pandas numpy scipy pyarrow matplotlib
  2. 把 data/ 目录复制到 Windows 机器上
  3. python optimize_ratings_gpu.py --data_dir ./data

Mac 快速模式 (几分钟完成):
  python optimize_ratings_gpu.py --data_dir ./data --quick

  --quick 自动降低: steps=80, pop=6, patience=15, 跳过 CV/稳定性/重要性。
  如需进一步加速: --quick --steps 40 --pop 3

Mac 完整模式 (较慢但更准):
  python optimize_ratings_gpu.py --data_dir ./data --steps 150 --pop 8 --patience 25

实时可视化:
  默认启用 Plotly 交互式图表，显示 Loss 曲线、Spearman/Pearson 跟踪、
  组件分解、位置权重热力图、联赛相关性、训练状态等 8 个子图。
  支持导出为交互式 HTML 报告。远程服务器或无 GUI 环境加 --no-viz 禁用。
  依赖: pip install plotly dash dash-bootstrap-components
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr

# ── 可视化 (使用新的 Plotly 版本) ────────────────────────────────────────
try:
    from optimize_viz import create_visualizer
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from optimize_viz import create_visualizer

# 旧版 matplotlib 可视化保留为备选
import platform as _platform

try:
    import matplotlib
    if _platform.system() == "Darwin":
        _backend_set = False
        for _backend in ["macosx", "TkAgg", "Qt5Agg"]:
            try:
                matplotlib.use(_backend)
                _backend_set = True
                break
            except Exception:
                continue
        if not _backend_set:
            matplotlib.use("Agg")
    else:
        matplotlib.use("Agg")
    _HAS_MATPLOTLIB = True
    _VIZ_INTERACTIVE = matplotlib.get_backend() != "agg"
except ImportError:
    _HAS_MATPLOTLIB = False
    _VIZ_INTERACTIVE = False

# ── 位置映射 ──────────────────────────────────────────────────────────────

POSITIONS = ["ST", "W", "AM", "CM", "DM", "FB", "CB", "GK"]
DIMENSIONS = ["availability", "attack", "defense", "possession", "quality"]
ATTACK_METRICS = ["npxg_p90", "assists_p90", "g_a_volume"]
POS_TO_IDX = {p: i for i, p in enumerate(POSITIONS)}
N_POS = len(POSITIONS)
N_DIM = len(DIMENSIONS)
N_ATK = len(ATTACK_METRICS)
N_PARAMS = (
    N_POS * N_DIM + N_POS * N_ATK + 4 + 4 + 3 + 2
)  # = 77 (added trend_weight, experience_weight)

POSITION_DIMENSION_PRIOR = [
    [0.15, 0.38, 0.08, 0.14, 0.25],  # ST
    [0.12, 0.30, 0.10, 0.25, 0.23],  # W
    [0.12, 0.28, 0.10, 0.28, 0.22],  # AM
    [0.14, 0.16, 0.18, 0.32, 0.20],  # CM
    [0.14, 0.08, 0.30, 0.28, 0.20],  # DM
    [0.15, 0.10, 0.28, 0.27, 0.20],  # FB
    [0.16, 0.05, 0.42, 0.20, 0.17],  # CB
    [0.20, 0.05, 0.35, 0.20, 0.20],  # GK
]
ATTACK_WEIGHT_PRIOR = [
    [0.45, 0.15, 0.40],  # ST
    [0.30, 0.30, 0.40],  # W
    [0.20, 0.40, 0.40],  # AM
    [0.15, 0.35, 0.50],  # CM
    [0.10, 0.25, 0.65],  # DM
    [0.10, 0.45, 0.45],  # FB
    [0.20, 0.20, 0.60],  # CB
    [0.05, 0.05, 0.90],  # GK
]
QUALITY_SUBWEIGHT_PRIOR = [0.35, 0.25, 0.25, 0.15]
POSITION_DIMENSION_CAPS = [
    [0.20, 1.00, 1.00, 1.00, 0.30],  # ST: 出勤是可靠性信号，不能替代进攻输出
    [0.20, 1.00, 1.00, 1.00, 0.28],  # W
    [0.20, 0.35, 1.00, 1.00, 0.30],  # AM
    [0.18, 0.22, 1.00, 1.00, 0.24],  # CM: 防止出勤/进攻/quality 泛化霸榜
    [0.20, 0.12, 1.00, 1.00, 0.24],  # DM
    [0.20, 0.16, 1.00, 1.00, 0.28],  # FB
    [0.18, 0.10, 1.00, 1.00, 0.25],  # CB
    [0.18, 0.06, 1.00, 1.00, 0.28],  # GK
]
TEAM_AGG_MINUTES_CAP = 1500.0
TEAM_AGG_CORE_MINUTES = 450.0
TEAM_AGG_CORE_SCALE = 180.0
TEAM_AGG_CAPPED_MINUTES_BLEND = 0.55

# Position slot caps: limit each position group's contribution to team aggregation.
# This prevents a position group (e.g., many CBs) from dominating the team rating.
POSITION_SLOT_GROUPS = {
    "GK": "GK",
    "CB": "CB",
    "FB": "FB",
    "DM": "MF",
    "CM": "MF",
    "AM": "ATT",
    "W": "ATT",
    "ST": "ATT",
}
POSITION_SLOT_CAPS = {
    "GK": 1.0,
    "CB": 2.5,
    "FB": 1.5,
    "MF": 2.5,
    "ATT": 2.5,
}

# ── 队名归一化 ──────────────────────────────────────────────────────────
# FBref、Understat 和 Football-Data 使用不同的队名格式。
# 这个映射把所有变体统一到 Football-Data 的写法，因为积分数据来自 Football-Data。
TEAM_NAME_ALIASES: dict[str, str] = {
    # Premier League
    "arsenal": "Arsenal",
    "aston villa": "Aston Villa",
    "bournemouth": "Bournemouth",
    "brentford": "Brentford",
    "brighton": "Brighton",
    "brighton and hove albion": "Brighton",
    "burnley": "Burnley",
    "chelsea": "Chelsea",
    "crystal palace": "Crystal Palace",
    "everton": "Everton",
    "fulham": "Fulham",
    "ipswich town": "Ipswich",
    "ipswich": "Ipswich",
    "leeds united": "Leeds",
    "leeds": "Leeds",
    "leicester city": "Leicester",
    "leicester": "Leicester",
    "liverpool": "Liverpool",
    "luton town": "Luton",
    "luton": "Luton",
    "manchester city": "Man City",
    "man city": "Man City",
    "manchester united": "Man United",
    "man united": "Man United",
    "man utd": "Man United",
    "manchester utd": "Man United",
    "newcastle united": "Newcastle",
    "newcastle": "Newcastle",
    "norwich city": "Norwich",
    "norwich": "Norwich",
    "nottingham forest": "Nott'm Forest",
    "nottm forest": "Nott'm Forest",
    "sheffield united": "Sheffield United",
    "sheffield utd": "Sheffield United",
    "southampton": "Southampton",
    "tottenham hotspur": "Tottenham",
    "tottenham": "Tottenham",
    "spurs": "Tottenham",
    "watford": "Watford",
    "west bromwich albion": "West Brom",
    "west brom": "West Brom",
    "west ham united": "West Ham",
    "west ham": "West Ham",
    "wolverhampton wanderers": "Wolves",
    "wolverhampton": "Wolves",
    "wolves": "Wolves",
    # La Liga
    "alaves": "Alaves",
    "deportivo alaves": "Alaves",
    "athletic bilbao": "Ath Bilbao",
    "athletic club": "Ath Bilbao",
    "atletico madrid": "Ath Madrid",
    "atletico": "Ath Madrid",
    "barcelona": "Barcelona",
    "fc barcelona": "Barcelona",
    "barca": "Barcelona",
    "betis": "Betis",
    "real betis": "Betis",
    "cadiz": "Cadiz",
    "cadiz cf": "Cadiz",
    "celta vigo": "Celta",
    "celta": "Celta",
    "deportivo la coruna": "La Coruna",
    "deportivo": "La Coruna",
    "eibar": "Eibar",
    "elche": "Elche",
    "espanyol": "Espanol",
    "rcd espanyol": "Espanol",
    "getafe": "Getafe",
    "girona": "Girona",
    "granada": "Granada",
    "granada cf": "Granada",
    "huesca": "Huesca",
    "sd huesca": "Huesca",
    "leganes": "Leganes",
    "cd leganes": "Leganes",
    "levante": "Levante",
    "mallorca": "Mallorca",
    "rcd mallorca": "Mallorca",
    "osasuna": "Osasuna",
    "rayo vallecano": "Rayo Vallecano",
    "rayo": "Rayo Vallecano",
    "vallecano": "Rayo Vallecano",
    "real madrid": "Real Madrid",
    "real sociedad": "Real Sociedad",
    "sociedad": "Real Sociedad",
    "sevilla": "Sevilla",
    "sevilla fc": "Sevilla",
    "valencia": "Valencia",
    "valencia cf": "Valencia",
    "valladolid": "Valladolid",
    "real valladolid": "Valladolid",
    "villarreal": "Villarreal",
    "villarreal cf": "Villarreal",
    "las palmas": "Las Palmas",
    "ud las palmas": "Las Palmas",
    "almeria": "Almeria",
    "ud almeria": "Almeria",
    "oviedo": "Oviedo",
    "real oviedo": "Oviedo",
    "girona fc": "Girona",
    # Bundesliga
    "augsburg": "Augsburg",
    "fc augsburg": "Augsburg",
    "bayer leverkusen": "Leverkusen",
    "leverkusen": "Leverkusen",
    "bayern munich": "Bayern Munich",
    "bayern": "Bayern Munich",
    "fc bayern munich": "Bayern Munich",
    "bayern munchen": "Bayern Munich",
    "borussia dortmund": "Dortmund",
    "dortmund": "Dortmund",
    "borussia monchengladbach": "M'gladbach",
    "monchengladbach": "M'gladbach",
    "borussia mgladbach": "M'gladbach",
    "borussia m.gladbach": "M'gladbach",
    "gladbach": "M'gladbach",
    "darmstadt": "Darmstadt",
    "sv darmstadt": "Darmstadt",
    "eintracht frankfurt": "Ein Frankfurt",
    "eintracht": "Ein Frankfurt",
    "freiburg": "Freiburg",
    "sc freiburg": "Freiburg",
    "hamburger sv": "Hamburg",
    "hamburg": "Hamburg",
    "hannover 96": "Hannover",
    "hannover": "Hannover",
    "hertha berlin": "Hertha",
    "hertha bsc": "Hertha",
    "hoffenheim": "Hoffenheim",
    "tsg hoffenheim": "Hoffenheim",
    "koln": "Koln",
    "fc koln": "Koln",
    "cologne": "Koln",
    "fc cologne": "Koln",
    "leipzig": "RB Leipzig",
    "rb leipzig": "RB Leipzig",
    "mainz": "Mainz",
    "mainz 05": "Mainz",
    "paderborn": "Paderborn",
    "sc paderborn": "Paderborn",
    "schalke 04": "Schalke 04",
    "schalke": "Schalke 04",
    "stuttgart": "Stuttgart",
    "vfb stuttgart": "Stuttgart",
    "union berlin": "Union Berlin",
    "werder bremen": "Werder Bremen",
    "wolfsburg": "Wolfsburg",
    "vfl wolfsburg": "Wolfsburg",
    "bochum": "Bochum",
    "vfl bochum": "Bochum",
    "heidenheim": "Heidenheim",
    "fc heidenheim": "Heidenheim",
    "st pauli": "St Pauli",
    "st. pauli": "St Pauli",
    "fc st pauli": "St Pauli",
    "holstein kiel": "Holstein Kiel",
    # Serie A
    "atalanta": "Atalanta",
    "bologna": "Bologna",
    "bologna fc": "Bologna",
    "cagliari": "Cagliari",
    "cagliari calcio": "Cagliari",
    "catania": "Catania",
    "chievo": "Chievo",
    "ac chievo": "Chievo",
    "empoli": "Empoli",
    "empoli fc": "Empoli",
    "fiorentina": "Fiorentina",
    "acf fiorentina": "Fiorentina",
    "frosinone": "Frosinone",
    "genoa": "Genoa",
    "genoa cfc": "Genoa",
    "hellas verona": "Verona",
    "verona": "Verona",
    "inter milan": "Inter",
    "inter": "Inter",
    "internazionale": "Inter",
    "fc internazionale": "Inter",
    "juventus": "Juventus",
    "lazio": "Lazio",
    "ss lazio": "Lazio",
    "lecce": "Lecce",
    "us lecce": "Lecce",
    "ac milan": "Milan",
    "milan": "Milan",
    "napoli": "Napoli",
    "ssc napoli": "Napoli",
    "parma": "Parma",
    "parma calcio": "Parma",
    "parma calcio 1913": "Parma",
    "pescara": "Pescara",
    "roma": "Roma",
    "as roma": "Roma",
    "salernitana": "Salernitana",
    "sassuolo": "Sassuolo",
    "spezia": "Spezia",
    "torino": "Torino",
    "torino fc": "Torino",
    "udinese": "Udinese",
    "udinese calcio": "Udinese",
    "venezia": "Venezia",
    "venezia fc": "Venezia",
    "cittadella": "Cittadella",
    "benevento": "Benevento",
    "brescia": "Brescia",
    "monza": "Monza",
    "ac monza": "Monza",
    "como": "Como",
    "como 1907": "Como",
    "cremonese": "Cremonese",
    "us cremonese": "Cremonese",
    # Ligue 1
    "lens": "Lens",
    "rc lens": "Lens",
    "lille": "Lille",
    "lille osc": "Lille",
    "lyon": "Lyon",
    "olympique lyonnais": "Lyon",
    "marseille": "Marseille",
    "olympique marseille": "Marseille",
    "om": "Marseille",
    "monaco": "Monaco",
    "as monaco": "Monaco",
    "montpellier": "Montpellier",
    "montpellier hsc": "Montpellier",
    "nantes": "Nantes",
    "fc nantes": "Nantes",
    "nice": "Nice",
    "ogc nice": "Nice",
    "psg": "Paris SG",
    "paris saint-germain": "Paris SG",
    "paris saint-germain fc": "Paris SG",
    "paris sg": "Paris SG",
    "paris saint germain": "Paris SG",
    "reims": "Reims",
    "stade de reims": "Reims",
    "rennes": "Rennes",
    "stade rennais": "Rennes",
    "saint-etienne": "St Etienne",
    "saint etienne": "St Etienne",
    "as saint-etienne": "St Etienne",
    "strasbourg": "Strasbourg",
    "rc strasbourg": "Strasbourg",
    "toulouse": "Toulouse",
    "toulouse fc": "Toulouse",
    "bordeaux": "Bordeaux",
    "girondins bordeaux": "Bordeaux",
    "metz": "Metz",
    "fc metz": "Metz",
    "amiens": "Amiens",
    "sc amiens": "Amiens",
    "angers": "Angers",
    "angers sco": "Angers",
    "brest": "Brest",
    "stade brestois": "Brest",
    "clermont": "Clermont",
    "clermont foot": "Clermont",
    "le havre": "Le Havre",
    "fc lorient": "Lorient",
    "lorient": "Lorient",
    "ajaccio": "Ajaccio",
    "ac ajaccio": "Ajaccio",
    "troyes": "Troyes",
    "estac troyes": "Troyes",
    "dijon": "Dijon",
    "dijon fco": "Dijon",
    "caen": "Caen",
    "sm caen": "Caen",
    "nimes": "Nimes",
    "nimes olympique": "Nimes",
    "auxerre": "Auxerre",
    "aj auxerre": "Auxerre",
    "lens rc": "Lens",
}


def normalize_team_name(name: str) -> str:
    """Normalize team name to canonical form for cross-source matching.

    Strips accents, lowercases, and looks up in TEAM_NAME_ALIASES.
    Falls back to the original stripped name if no alias is found.
    """
    if not name or not isinstance(name, str):
        return str(name) if name is not None else ""
    # Strip accents for matching
    normalized = unicodedata.normalize("NFKD", name.strip())
    ascii_name = "".join(c for c in normalized if not unicodedata.combining(c))
    lower = ascii_name.strip().lower()
    return TEAM_NAME_ALIASES.get(lower, name.strip())


@dataclass(frozen=True)
class SeasonSplit:
    """Chronological split by complete seasons."""

    name: str
    train_seasons: tuple[str, ...]
    test_seasons: tuple[str, ...]


@dataclass(frozen=True)
class TeamPointsCalibrator:
    """Monotonic train-fitted mapping from team strength rating to season points."""

    method: str
    slope: float
    intercept: float
    pred_mean: float
    pred_std: float
    actual_mean: float
    actual_std: float
    min_slope: float
    max_slope: float
    league_offsets: dict[str, float] | None = None
    league_residual_means: dict[str, float] | None = None
    league_counts: dict[str, int] | None = None
    league_prior_n: float = 60.0
    league_offset_cap: float = 8.0


def map_position(pos_str):
    if not isinstance(pos_str, str):
        return "CM"
    s = pos_str.upper()
    if "GK" in s:
        return "GK"
    if "FW" in s and "MF" in s:
        return "W"
    if "MF" in s and "FW" in s:
        return "AM"
    if "DF" in s and "MF" in s:
        return "FB"
    if "MF" in s and "DF" in s:
        return "DM"
    if "FW" in s:
        return "ST"
    if "DF" in s:
        return "CB"
    if "MF" in s:
        return "CM"
    return "CM"


def map_position_detailed(pos_str):
    """Parse position string from FBref or Understat into
    (sub_position, position_source, position_confidence).

    Understat uses single letters: D, M, F, S, and combinations: D S, D M, D M S, F M, F M S
    FBref uses abbreviations: GK, DF, MF, FW, and combinations: DF,MF / MF,FW / FW,MF

    Confidence levels:
    - high: FBref multi-position combo (e.g., "DF,MF") - most informative
    - medium: Understat multi-position combo (e.g., "D M S") or FBref single position
    - low: Understat single letter (e.g., "D") - least informative
    """
    if not isinstance(pos_str, str) or not pos_str.strip():
        return ("CM", str(pos_str), "low")

    s = pos_str.strip().upper()
    source = pos_str.strip()

    # GK is unambiguous
    if "GK" in s:
        return ("GK", source, "high")

    # Detect source format: FBref uses DF/MF/FW with possible commas,
    # Understat uses D/M/F/S with spaces
    # FBref format: contains "DF" or "MF" or "FW" (2-letter codes)
    is_fbref = any(code in s for code in ["DF", "MF", "FW"])
    is_understat = not is_fbref and any(code in s.split() for code in ["D", "M", "F", "S"])

    if is_fbref:
        # FBref format parsing
        has_df = "DF" in s
        has_mf = "MF" in s
        has_fw = "FW" in s

        if has_df and has_mf:
            # DF,MF 和 MF,DF 都是翼卫/边后卫特征
            return ("FB", source, "high")
        if has_mf and has_fw:
            # MF,FW could be W or AM - use order as hint
            # "FW,MF" tends to be more attacking (W), "MF,FW" tends to be AM
            if s.index("FW") < s.index("MF"):
                return ("W", source, "high")
            return ("AM", source, "high")
        if has_df and has_fw:
            return ("W", source, "medium")  # rare combo
        if has_fw:
            return ("ST", source, "medium")
        if has_df:
            return ("CB", source, "medium")  # DF alone could be CB or FB - medium confidence
        if has_mf:
            return ("CM", source, "medium")
        return ("CM", source, "low")

    if is_understat:
        # Understat format: space-separated single letters D/M/F/S
        # IMPORTANT: S = Substitute, NOT Striker. Must be ignored for position.
        tokens = set(s.split())
        has_d = "D" in tokens
        has_m = "M" in tokens
        has_f = "F" in tokens
        # S = Substitute, not a position indicator — ignore it
        # has_s is deliberately NOT used in position logic

        if has_d and has_m and has_f:
            return ("FB", source, "medium")  # D M F -> wingback
        if has_d and has_m:
            return ("FB", source, "medium")  # D M -> wingback/fullback
        if has_d and has_f:
            return ("CB", source, "low")  # D F -> CB with low confidence
        if has_f and has_m:
            # F M: order matters — F listed first suggests more attacking
            # "F M S" is common for wingers, "M F" would be AM
            if s.split().index("F") < s.split().index("M"):
                return ("W", source, "medium")  # F before M -> winger
            return ("AM", source, "medium")  # M before F -> attacking mid
        if has_d:
            return ("CB", source, "low")  # D alone -> default CB, low confidence
        if has_f:
            return ("ST", source, "low")  # F alone -> striker, low confidence
        if has_m:
            return ("CM", source, "low")  # M alone -> CM, low confidence
        # S alone or no recognized position -> fallback
        return ("CM", source, "low")

    # Fallback: try the old logic for any other format
    return (map_position(pos_str), source, "low")


def refine_role_positions(df: pd.DataFrame) -> pd.DataFrame:
    """用历史粗位置和当前输出特征修正明显的角色误分。

    FBref 的 `pos` 在部分赛季会把边锋、前腰和翼卫统一写成 `MF`，
    直接映射会把 Salah、Olise、Dimarco 这类球员挤进 CM 池。同时，
    纯 `DF` 不区分 CB/FB，导致边后卫全被塞进 CB 池而评分虚高。

    修正逻辑：
    1. DF → FB：助攻/传中/进攻贡献显著高于 CB 典型值的边后卫
    2. MF → FB：历史有 DF,MF 线索且传中/防守量达标的翼卫
    3. MF → W/AM：进攻产量达标的边锋/前腰

    阈值根据 position_confidence 调整：
    - low（Understat 单字母）：更积极重判，阈值更低
    - high（FBref 多位置组合）：更保守重判，阈值更高
    - medium：使用默认阈值
    重判后 low → medium，因为特征证据提升了位置置信度。
    """
    if "source_position" not in df.columns:
        return df

    refined = df.copy()
    source = refined["source_position"].fillna("").astype(str).str.upper()
    history_by_player = refined.groupby("player")["source_position"].agg(
        lambda values: " ".join(
            sorted({str(value).upper() for value in values if pd.notna(value)})
        ),
    )
    history = refined["player"].map(history_by_player).fillna("")

    has_fw_history = history.str.contains("FW", regex=False)
    has_df_history = history.str.contains("DF", regex=False)
    has_wingback_history = history.str.contains("DF,MF", regex=False) | history.str.contains(
        "MF,DF",
        regex=False,
    )

    def _safe_numeric_col(col_name):
        if col_name in refined.columns:
            return pd.to_numeric(refined[col_name], errors="coerce").fillna(0.0)
        return pd.Series(0.0, index=refined.index)

    npg = _safe_numeric_col("npg_p90")
    assists = _safe_numeric_col("assists_p90")
    volume = _safe_numeric_col("g_a_volume")
    crosses = _safe_numeric_col("crosses_p90")
    defense = _safe_numeric_col("defense_composite")
    minutes = _safe_numeric_col("minutes")

    current_cb = refined["sub_position"].eq("CB")
    current_cm = refined["sub_position"].eq("CM")
    raw_mf = source.eq("MF")
    raw_df = source.eq("DF")

    # --- position_confidence masks ---
    conf = refined.get("position_confidence", pd.Series("medium", index=refined.index))
    if not isinstance(conf, pd.Series):
        conf = pd.Series("medium", index=refined.index)
    conf = conf.fillna("medium").astype(str)
    is_low = conf.eq("low")
    is_high = conf.eq("high")

    # --- DF → FB 重判 ---
    # 边后卫特征：助攻/传中显著高于 CB 均值，且有足够出场时间。
    sufficient_minutes = minutes >= 450
    fb_by_history = has_wingback_history & has_df_history

    # Default (medium) thresholds
    fb_attack_default = (
        (assists >= 0.10)
        | (crosses >= 1.0)
        | ((assists >= 0.06) & (crosses >= 0.6))
    )
    # Low confidence: lower thresholds (more aggressive reclassification)
    fb_attack_low = (
        (assists >= 0.07)
        | (crosses >= 0.7)
        | ((assists >= 0.04) & (crosses >= 0.4))
    )
    # High confidence: higher thresholds (more conservative reclassification)
    fb_attack_high = (
        (assists >= 0.15)
        | (crosses >= 1.5)
        | ((assists >= 0.10) & (crosses >= 1.0))
    )

    fb_attack = (
        (is_low & fb_attack_low)
        | (is_high & fb_attack_high)
        | (~is_low & ~is_high & fb_attack_default)
    )

    refined.loc[
        current_cb & raw_df & sufficient_minutes & (fb_attack | fb_by_history),
        "sub_position",
    ] = "FB"

    # --- MF → FB 重判 ---
    # 收紧阈值：只有真正翼卫特征的才重判，避免定位球主罚中场被误判
    # 必须同时满足：高传中 + 有后卫历史 + 防守达标
    # Default (medium) thresholds
    wingback_default = (
        (crosses >= 2.5)
        & (defense >= 0.8)
    )
    # Low confidence — 仍需双重条件
    wingback_low = (
        (crosses >= 2.0)
        & (defense >= 0.6)
    )
    # High confidence
    wingback_high = (
        (crosses >= 3.0)
        & (defense >= 1.0)
    )

    wingback_feature = (
        (is_low & wingback_low)
        | (is_high & wingback_high)
        | (~is_low & ~is_high & wingback_default)
    )
    # MF→FB 必须同时有 DF 历史和翼卫特征，缺一不可
    wingback_like = has_df_history & wingback_feature

    # --- MF → W/AM 重判 ---
    # Default (medium) thresholds
    forward_like_default = (
        (has_fw_history & ((npg >= 0.20) | (assists >= 0.20) | (volume >= 8.0)))
        | ((npg >= 0.32) & (volume >= 10.0))
    )
    pure_attacking_mid_default = (~has_fw_history) & (npg >= 0.24) & (assists >= 0.16)

    # Low confidence thresholds
    forward_like_low = (
        (has_fw_history & ((npg >= 0.15) | (assists >= 0.15) | (volume >= 6.0)))
        | ((npg >= 0.25) & (volume >= 8.0))
    )
    pure_attacking_mid_low = (~has_fw_history) & (npg >= 0.18) & (assists >= 0.12)

    # High confidence thresholds
    forward_like_high = (
        (has_fw_history & ((npg >= 0.28) | (assists >= 0.28) | (volume >= 10.0)))
        | ((npg >= 0.38) & (volume >= 12.0))
    )
    pure_attacking_mid_high = (~has_fw_history) & (npg >= 0.30) & (assists >= 0.20)

    forward_like = (
        (is_low & forward_like_low)
        | (is_high & forward_like_high)
        | (~is_low & ~is_high & forward_like_default)
    )
    pure_attacking_mid = (
        (is_low & pure_attacking_mid_low)
        | (is_high & pure_attacking_mid_high)
        | (~is_low & ~is_high & pure_attacking_mid_default)
    )

    # Track which players get reclassified for confidence upgrade
    reclassified = pd.Series(False, index=refined.index)

    fb_mask = current_cm & raw_mf & wingback_like
    w_mask = current_cm & raw_mf & forward_like & ~wingback_like
    am_mask = current_cm & raw_mf & pure_attacking_mid & ~wingback_like

    refined.loc[fb_mask, "sub_position"] = "FB"
    refined.loc[w_mask, "sub_position"] = "W"
    refined.loc[am_mask, "sub_position"] = "AM"

    reclassified = fb_mask | w_mask | am_mask

    # Also mark DF→FB reclassifications
    df_fb_mask = current_cb & raw_df & sufficient_minutes & (fb_attack | fb_by_history)
    reclassified = reclassified | df_fb_mask

    # Upgrade position_confidence from low → medium for reclassified players
    if "position_confidence" in refined.columns:
        refined.loc[reclassified & is_low, "position_confidence"] = "medium"

    refined["pos_idx"] = (
        refined["sub_position"].map(POS_TO_IDX).fillna(POS_TO_IDX["CM"]).astype(int)
    )

    return refined


def apply_position_weight_caps(weights: torch.Tensor) -> torch.Tensor:
    """限制明显不符合角色职责的维度权重，并保持每行归一化。"""
    caps = torch.tensor(POSITION_DIMENSION_CAPS, dtype=weights.dtype, device=weights.device)
    capped = torch.minimum(weights, caps)
    missing = torch.clamp(1.0 - capped.sum(dim=1, keepdim=True), min=0.0)
    room = torch.clamp(caps - capped, min=0.0)
    room_sum = room.sum(dim=1, keepdim=True).clamp_min(1e-8)
    adjusted = capped + missing * room / room_sum
    return adjusted / adjusted.sum(dim=1, keepdim=True).clamp_min(1e-8)


def team_aggregation_config() -> dict[str, float]:
    """Return the robust team-season aggregation settings for reports."""
    return {
        "minutes_cap": TEAM_AGG_MINUTES_CAP,
        "core_minutes": TEAM_AGG_CORE_MINUTES,
        "core_scale": TEAM_AGG_CORE_SCALE,
        "capped_minutes_blend": TEAM_AGG_CAPPED_MINUTES_BLEND,
        "core_rotation_blend": 1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND,
        "position_slot_groups": POSITION_SLOT_GROUPS,
        "position_slot_caps": POSITION_SLOT_CAPS,
    }


# ── 数据加载 ──────────────────────────────────────────────────────────────

def load_data(data_dir: Path):
    """加载 FBref 球员数据 (standard + misc + shooting) + Football-Data 球队积分。"""
    fbref = pd.read_parquet(data_dir / "raw" / "fbref" / "player_stats_big5_3seasons.parquet")

    goals = fbref[("Performance", "Gls")].values.astype(np.float32)
    assists_col = fbref[("Performance", "Ast")].values.astype(np.float32)
    pk = fbref[("Performance", "PK")].values.astype(np.float32)
    minutes = fbref[("Playing Time", "Min")].values.astype(np.float32)
    starts = fbref[("Playing Time", "Starts")].values.astype(np.float32)
    matches = fbref[("Playing Time", "MP")].values.astype(np.float32)
    positions = fbref[("pos", "")].values
    leagues_raw = fbref.index.get_level_values("league")
    # Bundesliga rows have NaN league in FBref; fill before str conversion
    leagues_raw = leagues_raw.fillna("GER-Bundesliga").astype(str).values
    seasons = fbref.index.get_level_values("season").values
    teams = fbref.index.get_level_values("team").values
    players = fbref.index.get_level_values("player").values

    # Normalize league names
    league_name_map = {
        "ENG-Premier League": "Premier League",
        "ESP-La Liga": "La Liga",
        "FRA-Ligue 1": "Ligue 1",
        "ITA-Serie A": "Serie A",
        "GER-Bundesliga": "Bundesliga",
    }
    leagues = np.array([league_name_map.get(league, league) for league in leagues_raw])

    npg = goals - pk
    safe_min = np.maximum(minutes, 1.0)
    npg_p90 = npg / safe_min * 90
    assists_p90 = assists_col / safe_min * 90
    g_a_volume = npg + assists_col

    pos_details = [map_position_detailed(p) for p in positions]
    sub_pos = np.array([d[0] for d in pos_details])
    pos_idx = np.array([POS_TO_IDX.get(p, 4) for p in sub_pos])
    position_source = [d[1] for d in pos_details]
    position_confidence = [d[2] for d in pos_details]

    # Build base DataFrame
    df = pd.DataFrame({
        "player": players, "team": teams, "league": leagues, "season": seasons,
        "source_position": positions,
        "sub_position": sub_pos, "pos_idx": pos_idx,
        "position_source": position_source, "position_confidence": position_confidence,
        "matches": matches, "starts": starts, "minutes": minutes,
        "npg_p90": npg_p90, "assists_p90": assists_p90, "g_a_volume": g_a_volume,
    })

    # Normalize team names to Football-Data canonical form
    df["team"] = df["team"].apply(normalize_team_name)

    # Load and merge misc stats (tackles, interceptions, fouls, crosses)
    misc_path = data_dir / "raw" / "fbref" / "player_misc_5seasons.parquet"
    if not misc_path.exists():
        misc_path = data_dir / "raw" / "fbref" / "player_misc_3seasons.parquet"
    if misc_path.exists():
        misc = pd.read_parquet(misc_path)
        misc_idx = misc.index.to_frame(index=False)
        # Normalize league names in misc index
        misc_league_norm = misc_idx["league"].map(league_name_map).fillna(misc_idx["league"])
        misc_data = pd.DataFrame({
            "merge_key": (
                misc_idx["player"].astype(str) + "|" +
                misc_league_norm.astype(str) + "|" +
                misc_idx["season"].astype(str)
            ),
            "tackles_won": pd.to_numeric(misc[("Performance", "TklW")], errors="coerce").values,
            "interceptions": pd.to_numeric(misc[("Performance", "Int")], errors="coerce").values,
            "fouls": pd.to_numeric(misc[("Performance", "Fls")], errors="coerce").values,
            "fouls_drawn": pd.to_numeric(misc[("Performance", "Fld")], errors="coerce").values,
            "crosses": pd.to_numeric(misc[("Performance", "Crs")], errors="coerce").values,
            "yellow_cards": pd.to_numeric(misc[("Performance", "CrdY")], errors="coerce").values,
        })
        misc_data = misc_data.drop_duplicates(subset=["merge_key"], keep="first")
        df["merge_key"] = (
            df["player"].astype(str)
            + "|"
            + df["league"].astype(str)
            + "|"
            + df["season"].astype(str)
        )
        df = df.merge(misc_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
        print(
            "  Misc stats merged: "
            f"tackles={df['tackles_won'].notna().sum()}, "
            f"interceptions={df['interceptions'].notna().sum()}"
        )
    else:
        df["tackles_won"] = np.nan
        df["interceptions"] = np.nan
        df["fouls"] = np.nan
        df["fouls_drawn"] = np.nan
        df["crosses"] = np.nan
        df["yellow_cards"] = np.nan

    # Load and merge shooting stats
    shoot_path = data_dir / "raw" / "fbref" / "player_shooting_5seasons.parquet"
    if not shoot_path.exists():
        shoot_path = data_dir / "raw" / "fbref" / "player_shooting_3seasons.parquet"
    if shoot_path.exists():
        shooting = pd.read_parquet(shoot_path)
        shoot_idx = shooting.index.to_frame(index=False)
        shoot_league_norm = shoot_idx["league"].map(league_name_map).fillna(shoot_idx["league"])
        shoot_data = pd.DataFrame({
            "merge_key": (
                shoot_idx["player"].astype(str) + "|" +
                shoot_league_norm.astype(str) + "|" +
                shoot_idx["season"].astype(str)
            ),
            "shots": pd.to_numeric(shooting[("Standard", "Sh")], errors="coerce").values,
            "shots_on_target": pd.to_numeric(shooting[("Standard", "SoT")], errors="coerce").values,
            "shot_accuracy": pd.to_numeric(shooting[("Standard", "SoT%")], errors="coerce").values,
        })
        shoot_data = shoot_data.drop_duplicates(subset=["merge_key"], keep="first")
        df["merge_key"] = (
            df["player"].astype(str)
            + "|"
            + df["league"].astype(str)
            + "|"
            + df["season"].astype(str)
        )
        df = df.merge(shoot_data, on="merge_key", how="left")
        df = df.drop(columns=["merge_key"])
        print(
            "  Shooting stats merged: "
            f"shots={df['shots'].notna().sum()}, "
            f"sot={df['shots_on_target'].notna().sum()}"
        )
    else:
        df["shots"] = np.nan
        df["shots_on_target"] = np.nan
        df["shot_accuracy"] = np.nan

    # Compute per-90 defensive/possession metrics (after merge, safe_min from df)
    safe_min_df = df["minutes"].values.astype(np.float32)
    safe_min_df = np.maximum(safe_min_df, 1.0)
    df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_df * 90
    df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_df * 90
    df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_df * 90
    df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_df * 90
    df["fouls_p90"] = df["fouls"].fillna(0) / safe_min_df * 90
    df["shots_p90"] = df["shots"].fillna(0) / safe_min_df * 90
    df["sot_p90"] = df["shots_on_target"].fillna(0) / safe_min_df * 90

    # Defense composite (enhanced):
    #   tackles_won_p90 * 0.35  — primary defensive action
    #   interceptions_p90 * 0.30 — reading the game
    #   fouls_p90 * -0.10        — discipline penalty (fewer fouls = better)
    #   fouls_drawn_p90 * 0.10   — physical engagement proxy
    #   crosses_p90 * 0.15       — for FB/FB, defensive work rate includes crossing
    # Only use real data where available; missing tackles/interceptions → NaN
    has_defense_data = df["tackles_won"].notna() & df["interceptions"].notna()
    df["defense_composite"] = np.where(
        has_defense_data,
        (
            df["tackles_p90"] * 0.35
            + df["interceptions_p90"] * 0.30
            - df["fouls_p90"] * 0.10
            + df["fouls_drawn_p90"] * 0.10
            + df["crosses_p90"] * 0.15
        ),
        np.nan,
    )
    # Possession composite: crosses + fouls drawn (proxy for ball involvement)
    df["possession_composite"] = np.where(
        has_defense_data,
        df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5,
        np.nan,
    )

    # Cross-season trend: compute per-player improvement across seasons.
    # The trend feature must be causal for historical rows; using a player's
    # latest season for all rows leaks future performance into old seasons.
    # Sort by player and season for trend computation
    df = df.sort_values(["player", "season"])
    df["season_rank"] = df.groupby("player").cumcount()
    past_avg = (
        df.groupby("player")[["npg_p90", "defense_composite", "possession_composite"]]
        .expanding()
        .mean()
        .groupby(level=0)
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    df["npg_trend"] = (df["npg_p90"] - past_avg["npg_p90"]).fillna(0.0)
    df["def_trend"] = (df["defense_composite"] - past_avg["defense_composite"]).fillna(0.0)
    df["pos_trend"] = (df["possession_composite"] - past_avg["possession_composite"]).fillna(0.0)

    # Experience factor: seasons observed up to this row, not future career length.
    df["experience_factor"] = np.clip((df["season_rank"] + 1) / 3, 0.5, 1.0)

    df = df.sort_values("minutes", ascending=False)
    df = df.drop_duplicates(subset=["player", "season", "league"], keep="first")

    # Load Understat data for additional seasons
    understat_path = data_dir / "raw" / "understat" / "players_10seasons.parquet"
    if understat_path.exists():
        print("  加载 Understat 数据...")
        understat = pd.read_parquet(understat_path)
        
        # Normalize league names
        understat_league_map = {
            "EPL": "Premier League",
            "La_Liga": "La Liga",
            "Bundesliga": "Bundesliga",
            "Serie_A": "Serie A",
            "Ligue_1": "Ligue 1",
        }
        understat["league"] = (
            understat["league"].map(understat_league_map).fillna(understat["league"])
        )
        
        # Convert numeric columns
        for col in ["games", "time", "goals", "xG", "assists", "xA", "npxG", "shots", "key_passes"]:
            understat[col] = pd.to_numeric(understat[col], errors="coerce")
        
        # Normalize season format: "201617" -> "1617"
        def _normalize_season(s):
            s = str(s)
            if len(s) == 6 and s.startswith("20"):
                return s[2:]  # "201617" -> "1617"
            return s
        
        understat["season"] = understat["season"].apply(_normalize_season)
        
        # Calculate per-90 metrics
        safe_min_us = np.maximum(understat["time"].values.astype(np.float32), 1.0)
        understat["minutes"] = understat["time"].values.astype(np.float32)
        understat["matches"] = understat["games"].values.astype(np.float32)
        understat["starts"] = understat["games"].values.astype(np.float32)  # Approximate
        
        # Position mapping
        understat_pos_details = understat["position"].apply(map_position_detailed)
        understat["sub_position"] = understat_pos_details.apply(lambda x: x[0])
        understat["pos_idx"] = understat["sub_position"].map(POS_TO_IDX).fillna(4).astype(int)
        understat["position_source"] = understat_pos_details.apply(lambda x: x[1])
        understat["position_confidence"] = understat_pos_details.apply(lambda x: x[2])
        
        # Per-90 metrics
        understat["npg_p90"] = (
            (understat["goals"].values - understat["goals"].values * 0.1)
            / safe_min_us
            * 90
        )
        understat["assists_p90"] = understat["assists"].values / safe_min_us * 90
        understat["g_a_volume"] = understat["goals"].values + understat["assists"].values
        
        # Select and rename columns
        understat_df = understat[[
            "player_name", "team_title", "league", "season", "position",
            "sub_position", "pos_idx", "position_source", "position_confidence",
            "matches", "starts", "minutes",
            "npg_p90", "assists_p90", "g_a_volume",
        ]].copy()
        understat_df = understat_df.rename(
            columns={
                "player_name": "player",
                "team_title": "team",
                "position": "source_position",
            },
        )

        # Normalize Understat team names to Football-Data canonical form
        understat_df["team"] = understat_df["team"].apply(normalize_team_name)
        
        # Add missing columns with NaN (not 0) for defense/possession stats.
        # NaN rows are excluded from percentile ranking, so they get the
        # position median (50th percentile) instead of being forced to 0.
        for col in [
            "tackles_won",
            "interceptions",
            "fouls",
            "fouls_drawn",
            "crosses",
            "yellow_cards",
            "shots",
            "shots_on_target",
            "shot_accuracy",
            "tackles_p90",
            "interceptions_p90",
            "crosses_p90",
            "fouls_drawn_p90",
            "fouls_p90",
            "shots_p90",
            "sot_p90",
            "defense_composite",
            "possession_composite",
        ]:
            understat_df[col] = np.nan
        
        # Find seasons in Understat but not in FBref
        fbref_seasons = set(df["season"].unique())
        understat_only = understat_df[~understat_df["season"].isin(fbref_seasons)]
        print(f"    Understat 独有赛季: {sorted(understat_only['season'].unique())}")
        
        # Combine: FBref takes priority for overlapping seasons
        df = pd.concat([df, understat_only], ignore_index=True, sort=False)
        print(f"    合并后: {len(df)} 行")
        
        # Recompute per-90 and composite metrics for all rows.
        # Understat rows have NaN defense/possession — keep NaN so percentile
        # ranking assigns them the position median instead of 0.
        safe_min_all = np.maximum(df["minutes"].values.astype(np.float32), 1.0)
        df["tackles_p90"] = df["tackles_won"].fillna(0) / safe_min_all * 90
        df["interceptions_p90"] = df["interceptions"].fillna(0) / safe_min_all * 90
        df["crosses_p90"] = df["crosses"].fillna(0) / safe_min_all * 90
        df["fouls_drawn_p90"] = df["fouls_drawn"].fillna(0) / safe_min_all * 90
        df["fouls_p90"] = df["fouls"].fillna(0) / safe_min_all * 90
        # defense/possession composite: NaN where underlying stats are NaN
        has_defense = df["tackles_won"].notna() & df["interceptions"].notna()
        df["defense_composite"] = np.where(
            has_defense,
            (
                df["tackles_p90"] * 0.35
                + df["interceptions_p90"] * 0.30
                - df["fouls_p90"] * 0.10
                + df["fouls_drawn_p90"] * 0.10
                + df["crosses_p90"] * 0.15
            ),
            np.nan,
        )
        has_possession = df["crosses"].notna() & df["fouls_drawn"].notna()
        df["possession_composite"] = np.where(
            has_possession,
            df["crosses_p90"] * 0.5 + df["fouls_drawn_p90"] * 0.5,
            np.nan,
        )
        
        # Recompute trend and experience for all rows
        df = df.sort_values(["player", "season"])
        df["season_rank"] = df.groupby("player").cumcount()
        df["experience_factor"] = np.clip((df["season_rank"] + 1) / 3, 0.5, 1.0)
        
        # Recompute trends
        past_avg = (
            df.groupby("player")[["npg_p90", "defense_composite", "possession_composite"]]
            .expanding()
            .mean()
            .groupby(level=0)
            .shift(1)
            .reset_index(level=0, drop=True)
        )
        df["npg_trend"] = (df["npg_p90"] - past_avg["npg_p90"]).fillna(0.0)
        df["def_trend"] = (df["defense_composite"] - past_avg["defense_composite"]).fillna(0.0)
        df["pos_trend"] = (
            df["possession_composite"] - past_avg["possession_composite"]
        ).fillna(0.0)

    df = refine_role_positions(df)

    # Team standings + match-level data (for Dixon-Coles)
    fd = pd.read_parquet(data_dir / "raw" / "football_data" / "combined_results.parquet")
    standings_rows = []
    match_rows = []
    for _, row in fd.iterrows():
        season = str(row.get("season", ""))
        league = str(row.get("league", ""))
        home, away = str(row["HomeTeam"]), str(row["AwayTeam"])
        hg, ag = float(row["FTHG"]), float(row["FTAG"])
        hp = 3 if hg > ag else (1 if hg == ag else 0)
        ap = 3 - hp if hg != ag else 1
        standings_rows.append({"team": home, "league": league, "season": season,
                               "points": hp, "gf": hg, "ga": ag})
        standings_rows.append({"team": away, "league": league, "season": season,
                               "points": ap, "gf": ag, "ga": hg})
        match_rows.append({
            "home_team": home, "away_team": away,
            "home_goals": hg, "away_goals": ag,
            "season": season, "league": league,
        })
    standings = pd.DataFrame(standings_rows)
    matches_df = pd.DataFrame(match_rows)
    # Normalize Football-Data team names (some CSVs have inconsistent casing)
    standings["team"] = standings["team"].apply(normalize_team_name)
    team_pts = standings.groupby(["team", "league", "season"]).agg(
        total_points=("points", "sum"),
    ).reset_index()

    # Diagnostics: report team name matching rate
    player_teams = set(df["team"].dropna().unique())
    pts_teams = set(team_pts["team"].dropna().unique())
    matched_teams = player_teams & pts_teams
    unmatched_player = player_teams - pts_teams
    if unmatched_player:
        print(
            f"  队名匹配: {len(matched_teams)}/{len(player_teams)} 球员侧球队匹配积分侧, "
            f"未匹配: {sorted(unmatched_player)[:20]}"
        )
    else:
        print(f"  队名匹配: {len(matched_teams)}/{len(player_teams)} 全部匹配")

    # Report NaN stats coverage
    for col in ["defense_composite", "possession_composite"]:
        n_total = len(df)
        n_nan = int(df[col].isna().sum())
        if n_nan > 0:
            print(f"  {col}: {n_nan}/{n_total} 行缺失 ({n_nan/n_total*100:.1f}%)")

    return df, team_pts, matches_df


def _percentile_against_reference(df, reference_df, column):
    """Map values to per-position percentiles from a reference frame."""
    percentiles = np.full(len(df), 50.0, dtype=np.float32)
    if column not in df.columns or column not in reference_df.columns:
        return percentiles

    for pos_idx in sorted(set(df["pos_idx"].dropna().unique())):
        eval_mask = df["pos_idx"].to_numpy() == pos_idx
        ref_mask = reference_df["pos_idx"].to_numpy() == pos_idx
        ref_values = pd.to_numeric(reference_df.loc[ref_mask, column], errors="coerce")
        ref_values = ref_values[np.isfinite(ref_values)].to_numpy(dtype=np.float32)
        if len(ref_values) == 0:
            continue

        sorted_ref = np.sort(ref_values)
        values = pd.to_numeric(df.loc[eval_mask, column], errors="coerce").to_numpy(
            dtype=np.float32,
        )
        finite = np.isfinite(values)
        pct = np.full(len(values), 50.0, dtype=np.float32)
        left = np.searchsorted(sorted_ref, values[finite], side="left")
        right = np.searchsorted(sorted_ref, values[finite], side="right")
        pct[finite] = ((left + right) / 2.0 / len(sorted_ref) * 100.0).astype(np.float32)
        percentiles[eval_mask] = np.clip(pct, 0.0, 100.0)

    return pd.Series(percentiles, index=df.index, dtype=np.float32)


def _season_sort_key(value):
    text = str(value)
    match = re.search(r"\d{4}", text)
    if match:
        return int(match.group()), text
    return 0, text


def _sorted_seasons(df):
    return tuple(sorted({str(season) for season in df["season"].dropna()}, key=_season_sort_key))


def make_season_splits(
    df,
    *,
    n_splits=3,
    test_seasons=1,
    min_train_seasons=2,
    gap_seasons=0,
):
    """Create expanding-window CV splits by complete season."""
    seasons = _sorted_seasons(df)
    if test_seasons < 1:
        raise ValueError("test_seasons must be at least 1")
    if min_train_seasons < 1:
        raise ValueError("min_train_seasons must be at least 1")
    if gap_seasons < 0:
        raise ValueError("gap_seasons must be non-negative")

    starts = []
    last_start = len(seasons) - test_seasons
    for test_start in range(min_train_seasons + gap_seasons, last_start + 1):
        train_end = test_start - gap_seasons
        if train_end >= min_train_seasons:
            starts.append(test_start)

    if not starts:
        raise ValueError(
            "not enough seasons for chronological validation: "
            f"seasons={list(seasons)}, min_train={min_train_seasons}, "
            f"gap={gap_seasons}, test={test_seasons}",
        )

    selected_starts = starts[-n_splits:] if n_splits and n_splits > 0 else starts
    splits = []
    for fold_idx, test_start in enumerate(selected_starts, start=1):
        train_end = test_start - gap_seasons
        split = SeasonSplit(
            name=f"fold_{fold_idx}",
            train_seasons=seasons[:train_end],
            test_seasons=seasons[test_start:test_start + test_seasons],
        )
        _assert_no_split_leakage(split)
        splits.append(split)
    return splits


def make_holdout_split(df, *, test_seasons=1, min_train_seasons=2, gap_seasons=0):
    """Use the latest complete season block as the final holdout."""
    return make_season_splits(
        df,
        n_splits=1,
        test_seasons=test_seasons,
        min_train_seasons=min_train_seasons,
        gap_seasons=gap_seasons,
    )[-1]


def _assert_no_split_leakage(split):
    train_set = set(split.train_seasons)
    test_set = set(split.test_seasons)
    overlap = train_set.intersection(test_set)
    if overlap:
        raise ValueError(f"season leakage detected in {split.name}: {sorted(overlap)}")
    if split.train_seasons and split.test_seasons:
        train_last = _season_sort_key(split.train_seasons[-1])
        test_first = _season_sort_key(split.test_seasons[0])
        if train_last >= test_first:
            raise ValueError(
                f"non-chronological split {split.name}: "
                f"train_last={split.train_seasons[-1]}, test_first={split.test_seasons[0]}",
            )


def _filter_by_seasons(df, seasons):
    seasons_set = {str(season) for season in seasons}
    return df.loc[df["season"].astype(str).isin(seasons_set)].copy()


def _safe_spearman(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) < 2 or np.nanstd(pred_arr) == 0 or np.nanstd(actual_arr) == 0:
        return float("nan")
    corr, _ = spearmanr(pred_arr, actual_arr)
    return float(corr)


def _safe_pearson(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) < 2 or np.nanstd(pred_arr) == 0 or np.nanstd(actual_arr) == 0:
        return float("nan")
    corr, _ = pearsonr(pred_arr, actual_arr)
    return float(corr)


def _standardized_mse(pred, actual):
    pred_arr = np.asarray(pred, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    if len(pred_arr) == 0:
        return float("nan")
    pred_std = np.nanstd(pred_arr)
    actual_std = np.nanstd(actual_arr)
    if pred_std == 0 or actual_std == 0:
        return float("nan")
    pred_z = (pred_arr - np.nanmean(pred_arr)) / pred_std
    actual_z = (actual_arr - np.nanmean(actual_arr)) / actual_std
    return float(np.nanmean((pred_z - actual_z) ** 2))


def fit_team_points_calibrator(
    matched_df: pd.DataFrame,
    *,
    min_slope: float = 0.05,
    max_slope: float = 8.0,
    use_league_offsets: bool = True,
    league_prior_n: float = 60.0,
    league_offset_cap: float = 8.0,
) -> TeamPointsCalibrator:
    """Fit a leakage-safe monotonic mapping from strength ratings to points.

    The raw team aggregate is a squad-strength score, not a season-points model.
    This z-score affine layer fixes the known range compression while preserving
    the learned ordering. It must be fitted on train seasons and then reused for
    holdout/test seasons.
    """
    if matched_df.empty:
        return TeamPointsCalibrator(
            method="zscore_affine_empty",
            slope=0.0,
            intercept=0.0,
            pred_mean=0.0,
            pred_std=0.0,
            actual_mean=0.0,
            actual_std=0.0,
            min_slope=float(min_slope),
            max_slope=float(max_slope),
        )

    pred = pd.to_numeric(matched_df["pred_rating"], errors="coerce").to_numpy(dtype=float)
    actual = pd.to_numeric(matched_df["actual_points"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(pred) & np.isfinite(actual)
    if valid.sum() < 2:
        actual_mean = float(np.nanmean(actual[valid])) if valid.any() else 0.0
        return TeamPointsCalibrator(
            method="zscore_affine_degenerate",
            slope=0.0,
            intercept=actual_mean,
            pred_mean=float(np.nanmean(pred[valid])) if valid.any() else 0.0,
            pred_std=0.0,
            actual_mean=actual_mean,
            actual_std=0.0,
            min_slope=float(min_slope),
            max_slope=float(max_slope),
        )

    pred = pred[valid]
    actual = actual[valid]
    pred_mean = float(np.mean(pred))
    actual_mean = float(np.mean(actual))
    pred_std = float(np.std(pred))
    actual_std = float(np.std(actual))
    if pred_std < 1e-8 or actual_std < 1e-8:
        slope = 0.0
        intercept = actual_mean
        method = "zscore_affine_constant"
    else:
        slope = float(np.clip(actual_std / pred_std, min_slope, max_slope))
        intercept = actual_mean - slope * pred_mean
        method = "zscore_affine_train_fit"

    league_offsets = None
    league_residual_means = None
    league_counts = None
    if use_league_offsets and "league" in matched_df.columns:
        prepared = matched_df.loc[valid].copy()
        prepared["pred_points_global"] = intercept + slope * pred
        prepared["residual"] = (
            pd.to_numeric(prepared["actual_points"], errors="coerce")
            - prepared["pred_points_global"]
        )
        league_grouped = prepared.groupby("league", observed=True)["residual"].agg(
            ["count", "mean"],
        )
        if not league_grouped.empty:
            league_counts = {
                str(league): int(row["count"])
                for league, row in league_grouped.iterrows()
            }
            league_residual_means = {
                str(league): float(row["mean"])
                for league, row in league_grouped.iterrows()
            }
            prior = max(float(league_prior_n), 0.0)
            cap = max(float(league_offset_cap), 0.0)
            offsets = {}
            for league, row in league_grouped.iterrows():
                shrink = float(row["count"]) / (float(row["count"]) + prior) if prior > 0 else 1.0
                offset = float(row["mean"]) * shrink
                offsets[str(league)] = float(np.clip(offset, -cap, cap))
            league_offsets = offsets

    return TeamPointsCalibrator(
        method=method,
        slope=slope,
        intercept=float(intercept),
        pred_mean=pred_mean,
        pred_std=pred_std,
        actual_mean=actual_mean,
        actual_std=actual_std,
        min_slope=float(min_slope),
        max_slope=float(max_slope),
        league_offsets=league_offsets,
        league_residual_means=league_residual_means,
        league_counts=league_counts,
        league_prior_n=float(league_prior_n),
        league_offset_cap=float(league_offset_cap),
    )


def apply_team_points_calibrator(
    matched_df: pd.DataFrame,
    calibrator: TeamPointsCalibrator | None,
) -> pd.DataFrame:
    """Attach calibrated season-point predictions to a matched result frame."""
    if calibrator is None or matched_df.empty:
        return matched_df
    result = matched_df.copy()
    pred = pd.to_numeric(result["pred_rating"], errors="coerce").to_numpy(dtype=float)
    result["pred_points_global"] = calibrator.intercept + calibrator.slope * pred
    if calibrator.league_offsets:
        offsets = result["league"].astype(str).map(calibrator.league_offsets).fillna(0.0)
        result["pred_points_league_offset"] = offsets.to_numpy(dtype=float)
        result["pred_points_calibrated"] = result["pred_points_global"] + offsets
    else:
        result["pred_points_league_offset"] = 0.0
        result["pred_points_calibrated"] = result["pred_points_global"]
    return result


def build_matched_results(feat, team_pts_df, team_avgs):
    """Match predicted team-season ratings with actual points.

    Teams with NaN or non-finite total_points are excluded from matching.
    Uses normalize_team_name for cross-source team name matching.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    n_before = len(valid_pts)
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]
    n_excluded = n_before - len(valid_pts)

    # Build lookup with normalized team names
    points_lookup = {
        (normalize_team_name(row["team"]), str(row["league"]), str(row["season"])): float(
            row["total_points"],
        )
        for _, row in valid_pts.iterrows()
    }
    rows = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        # Normalize team name for matching
        normalized_team = normalize_team_name(team)
        key = (normalized_team, str(league), str(season))
        if key not in points_lookup:
            continue
        rows.append(
            {
                "team": str(team),
                "normalized_team": normalized_team,
                "league": str(league),
                "season": str(season),
                "pred_rating": float(team_avgs[i]),
                "actual_points": points_lookup[key],
            },
        )
    result = pd.DataFrame(rows)
    result.attrs["n_excluded_na"] = n_excluded
    return result


def team_coverage_table(feat, team_pts_df):
    """Report team-season coverage before interpreting holdout metrics."""
    actual = team_pts_df.loc[:, ["team", "league", "season"]].copy()
    if actual.empty:
        return pd.DataFrame(
            columns=[
                "league",
                "season",
                "target_teams",
                "rated_teams",
                "matched_teams",
                "coverage",
            ],
        )

    actual = actual.astype(str).drop_duplicates()
    # Normalize team names in actual
    actual["team"] = actual["team"].apply(normalize_team_name)

    rated = pd.DataFrame(
        {
            "team": [normalize_team_name(team) for team in feat["ts_team_names"]],
            "league": [str(league) for league in feat["ts_leagues"]],
            "season": [str(season) for season in feat["ts_seasons"]],
        },
    ).drop_duplicates()
    # Defensive: replace "nan" league with "Bundesliga" (FBref NaN league issue)
    rated["league"] = rated["league"].replace("nan", "Bundesliga")
    matched = actual.merge(rated, on=["team", "league", "season"], how="inner")

    group_cols = ["league", "season"]
    target_counts = actual.groupby(group_cols, observed=True).size().rename("target_teams")
    rated_counts = rated.groupby(group_cols, observed=True).size().rename("rated_teams")
    matched_counts = matched.groupby(group_cols, observed=True).size().rename("matched_teams")
    coverage = (
        pd.concat([target_counts, rated_counts, matched_counts], axis=1)
        .fillna(0)
        .reset_index()
    )
    for column in ["target_teams", "rated_teams", "matched_teams"]:
        coverage[column] = coverage[column].astype(int)
    coverage["coverage"] = coverage["matched_teams"] / coverage["target_teams"].where(
        coverage["target_teams"] > 0,
    )
    coverage = coverage.sort_values(["season", "league"]).reset_index(drop=True)
    return coverage


def rating_calibration_table(matched_df, n_bins=5):
    """Compare predicted rating percentiles with actual point percentiles."""
    if matched_df.empty:
        return pd.DataFrame(
            columns=[
                "bin",
                "n",
                "pred_percentile_mean",
                "actual_percentile_mean",
                "calibration_gap",
            ],
        )

    prepared = matched_df.copy()
    prepared["pred_percentile"] = prepared["pred_rating"].rank(method="average", pct=True) * 100
    prepared["actual_percentile"] = prepared["actual_points"].rank(method="average", pct=True) * 100
    bins = max(1, min(int(n_bins), len(prepared)))
    prepared["bin"] = pd.qcut(
        prepared["pred_percentile"],
        q=bins,
        labels=False,
        duplicates="drop",
    )
    grouped = prepared.groupby("bin", dropna=False, observed=True).agg(
        n=("team", "size"),
        pred_percentile_mean=("pred_percentile", "mean"),
        actual_percentile_mean=("actual_percentile", "mean"),
    )
    grouped = grouped.reset_index()
    grouped["calibration_gap"] = (
        grouped["pred_percentile_mean"] - grouped["actual_percentile_mean"]
    )
    return grouped


def calibration_mae(matched_df, n_bins=5):
    table = rating_calibration_table(matched_df, n_bins=n_bins)
    if table.empty:
        return float("nan")
    weights = table["n"].to_numpy(dtype=float)
    gaps = np.abs(table["calibration_gap"].to_numpy(dtype=float))
    return float(np.average(gaps, weights=weights))


def rating_metrics(matched_df, *, n_bins=5):
    if matched_df.empty:
        return {
            "n_team_seasons": 0,
            "spearman": float("nan"),
            "pearson": float("nan"),
            "rank_loss": float("nan"),
            "z_mse": float("nan"),
            "calibration_mae": float("nan"),
            "raw_pred_range": float("nan"),
            "actual_points_range": float("nan"),
            "raw_spread_ratio": float("nan"),
            "points_mae": float("nan"),
            "points_rmse": float("nan"),
            "points_bias": float("nan"),
            "points_spread_ratio": float("nan"),
        }
    spearman = _safe_spearman(matched_df["pred_rating"], matched_df["actual_points"])
    pearson = _safe_pearson(matched_df["pred_rating"], matched_df["actual_points"])
    rank_loss = 1.0 - spearman if np.isfinite(spearman) else float("nan")
    pred_arr = pd.to_numeric(matched_df["pred_rating"], errors="coerce").to_numpy(dtype=float)
    actual_arr = pd.to_numeric(matched_df["actual_points"], errors="coerce").to_numpy(dtype=float)
    actual_std = np.nanstd(actual_arr)
    pred_std = np.nanstd(pred_arr)
    raw_spread_ratio = (
        float(pred_std / actual_std)
        if np.isfinite(pred_std) and np.isfinite(actual_std) and actual_std > 0
        else float("nan")
    )
    raw_pred_range = (
        float(np.nanmax(pred_arr) - np.nanmin(pred_arr)) if len(pred_arr) else float("nan")
    )
    actual_points_range = (
        float(np.nanmax(actual_arr) - np.nanmin(actual_arr)) if len(actual_arr) else float("nan")
    )
    points_mae = float("nan")
    points_rmse = float("nan")
    points_bias = float("nan")
    points_spread_ratio = float("nan")
    if "pred_points_calibrated" in matched_df.columns:
        points_arr = pd.to_numeric(
            matched_df["pred_points_calibrated"],
            errors="coerce",
        ).to_numpy(dtype=float)
        diff = points_arr - actual_arr
        points_mae = float(np.nanmean(np.abs(diff)))
        points_rmse = float(np.sqrt(np.nanmean(diff ** 2)))
        points_bias = float(np.nanmean(diff))
        points_std = np.nanstd(points_arr)
        points_spread_ratio = (
            float(points_std / actual_std)
            if np.isfinite(points_std) and np.isfinite(actual_std) and actual_std > 0
            else float("nan")
        )
    return {
        "n_team_seasons": int(len(matched_df)),
        "spearman": spearman,
        "pearson": pearson,
        "rank_loss": rank_loss,
        "z_mse": _standardized_mse(matched_df["pred_rating"], matched_df["actual_points"]),
        "calibration_mae": calibration_mae(matched_df, n_bins=n_bins),
        "raw_pred_range": raw_pred_range,
        "actual_points_range": actual_points_range,
        "raw_spread_ratio": raw_spread_ratio,
        "points_mae": points_mae,
        "points_rmse": points_rmse,
        "points_bias": points_bias,
        "points_spread_ratio": points_spread_ratio,
    }


def evaluate_params(
    params,
    eval_df,
    team_pts_df,
    rank_reference_df,
    device,
    *,
    split_name,
    calibration_bins=5,
    points_calibrator: TeamPointsCalibrator | None = None,
):
    """Evaluate params on a slice without letting that slice define train statistics."""
    feat_eval = build_feature_tensors(eval_df, rank_reference_df=rank_reference_df)
    ratings = compute_ratings_torch(feat_eval, params.to(device), device)
    team_avgs = compute_team_avg_ratings(feat_eval, ratings, device)
    matched_df = build_matched_results(feat_eval, team_pts_df, team_avgs)
    matched_df = apply_team_points_calibrator(matched_df, points_calibrator)
    coverage = team_coverage_table(feat_eval, team_pts_df)
    metrics = rating_metrics(matched_df, n_bins=calibration_bins)
    metrics["split"] = split_name
    metrics["n_players"] = int(len(eval_df))
    metrics["target_team_seasons"] = (
        int(coverage["target_teams"].sum()) if not coverage.empty else 0
    )
    metrics["rated_team_seasons"] = int(coverage["rated_teams"].sum()) if not coverage.empty else 0
    metrics["team_coverage"] = (
        float(coverage["matched_teams"].sum() / coverage["target_teams"].sum())
        if not coverage.empty and coverage["target_teams"].sum() > 0
        else float("nan")
    )
    # Report N/A teams excluded from evaluation
    excluded_na = matched_df.attrs.get("n_excluded_na", 0)
    metrics["n_excluded_na_teams"] = excluded_na
    return {
        "features": feat_eval,
        "matched": matched_df,
        "metrics": metrics,
        "calibration": rating_calibration_table(matched_df, n_bins=calibration_bins),
        "coverage": coverage,
    }


def league_metrics(matched_df, *, min_n=5, calibration_bins=5):
    rows = []
    if matched_df.empty:
        return pd.DataFrame(rows)
    for league in sorted(matched_df["league"].dropna().unique()):
        league_frame = matched_df.loc[matched_df["league"] == league].copy()
        if len(league_frame) < min_n:
            continue
        metrics = rating_metrics(league_frame, n_bins=calibration_bins)
        metrics["league"] = league
        rows.append(metrics)
    return pd.DataFrame(rows)


def permutation_feature_importance(
    params,
    eval_df,
    team_pts_df,
    rank_reference_df,
    device,
    *,
    columns=None,
    n_repeats=1,
    seed=42,
    calibration_bins=5,
):
    """Estimate feature importance by Spearman drop after shuffling one feature."""
    if columns is None:
        columns = [
            "minutes",
            "starts",
            "matches",
            "npg_p90",
            "assists_p90",
            "g_a_volume",
            "defense_composite",
            "possession_composite",
            "npg_trend",
        ]
    base_eval = evaluate_params(
        params,
        eval_df,
        team_pts_df,
        rank_reference_df,
        device,
        split_name="importance_base",
        calibration_bins=calibration_bins,
    )
    base_spearman = base_eval["metrics"]["spearman"]
    rng = np.random.default_rng(seed)
    rows = []
    for column in columns:
        if column not in eval_df.columns or eval_df[column].nunique(dropna=True) <= 1:
            continue
        drops = []
        shuffled_scores = []
        for _ in range(max(1, int(n_repeats))):
            shuffled = eval_df.copy()
            values = shuffled[column].to_numpy(copy=True)
            rng.shuffle(values)
            shuffled[column] = values
            shuffled_eval = evaluate_params(
                params,
                shuffled,
                team_pts_df,
                rank_reference_df,
                device,
                split_name=f"shuffle_{column}",
                calibration_bins=calibration_bins,
            )
            shuffled_spearman = shuffled_eval["metrics"]["spearman"]
            if np.isfinite(base_spearman) and np.isfinite(shuffled_spearman):
                drops.append(base_spearman - shuffled_spearman)
            shuffled_scores.append(shuffled_spearman)
        rows.append(
            {
                "feature": column,
                "baseline_spearman": base_spearman,
                "shuffled_spearman_mean": float(np.nanmean(shuffled_scores)),
                "spearman_drop_mean": float(np.nanmean(drops)) if drops else float("nan"),
                "spearman_drop_std": float(np.nanstd(drops)) if drops else float("nan"),
                "n_repeats": int(max(1, int(n_repeats))),
            },
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values("spearman_drop_mean", ascending=False, na_position="last")
    return result


def compute_input_hash(data_dir: Path) -> str:
    """Compute SHA256 hash of key input files for reproducibility."""
    import hashlib

    hasher = hashlib.sha256()
    key_files = [
        "gold/feature_store/rating_feature_matrix.parquet",
        "raw/football_data/combined_results.parquet",
        "gold/feature_store/player_ratings_optimized.parquet",
    ]
    for rel_path in key_files:
        fpath = data_dir / rel_path
        if fpath.exists():
            hasher.update(fpath.read_bytes())
    return hasher.hexdigest()[:16]


def save_model_run(
    params: np.ndarray,
    metrics: dict,
    args: argparse.Namespace | None = None,
    output_dir: Path | None = None,
    feat_hash: str | None = None,
):
    """Save model run with full provenance to data/models/runs/<timestamp>/.

    Saves:
    - optimized_params.npy
    - meta.json with: params summary, seed, input hash, metrics, position metrics,
      error case summary, composite objective weights
    """
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (output_dir or Path("data/models/runs")) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save params
    np.save(run_dir / "optimized_params.npy", params)

    # Build meta
    meta = {
        "timestamp": timestamp,
        "params_shape": list(params.shape),
        "params_mean": float(params.mean()),
        "params_std": float(params.std()),
        "input_hash": feat_hash,
        "metrics": {
            k: float(v) if isinstance(v, (int, float, np.floating)) else str(v)
            for k, v in metrics.items()
        },
    }

    if args is not None:
        meta["args"] = {
            "pop_size": getattr(args, "pop", None),
            "n_steps": getattr(args, "steps", None),
            "lr": getattr(args, "lr", None),
            "patience": getattr(args, "patience", None),
            "seed": getattr(args, "seed", None),
            "spearman_weight": getattr(args, "spearman_weight", None),
            "ndcg_weight": getattr(args, "ndcg_weight", None),
            "position_consistency_weight": getattr(args, "position_consistency_weight", None),
            "points_regression_weight": getattr(args, "points_regression_weight", None),
            "distribution_weight": getattr(args, "distribution_weight", None),
            "tail_calibration_weight": getattr(args, "tail_calibration_weight", None),
            "league_bias_weight": getattr(args, "league_bias_weight", None),
            "extreme_penalty_weight": getattr(args, "extreme_penalty_weight", None),
            "prior_weight": getattr(args, "prior_weight", None),
            "warmup_steps": getattr(args, "warmup_steps", None),
            "min_lr_ratio": getattr(args, "min_lr_ratio", None),
            "grad_clip": getattr(args, "grad_clip", None),
            "league_calibration_prior_n": getattr(args, "league_calibration_prior_n", None),
            "league_calibration_cap": getattr(args, "league_calibration_cap", None),
            "disable_league_calibration": getattr(args, "disable_league_calibration", None),
        }

    with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  模型运行登记已保存: {run_dir}")
    return run_dir


def _json_ready(value):
    """Convert numpy/pandas scalars and NaN values to JSON-safe objects."""
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [_json_ready(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _json_ready(value.to_dict())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


# ── 向量化评分 (PyTorch) ──────────────────────────────────────────────────

def build_feature_tensors(df, rank_reference_df=None):
    """预计算所有特征张量，包括防守和控球维度。

    rank_reference_df 用于把验证/测试集映射到训练集分布，避免用测试集整体分布
    计算百分位或联赛分钟中位数。
    """
    n_rows = len(df)
    reference_df = df if rank_reference_df is None else rank_reference_df

    # Per-position percentile ranks for all dimensions. For validation/test
    # slices, percentile thresholds come only from the train reference frame.
    rank_cols = {
        "npg_p90": "npg_pct",
        "assists_p90": "ast_pct",
        "g_a_volume": "vol_pct",
        "defense_composite": "def_pct",
        "possession_composite": "pos_pct",
    }
    if "npg_trend" in df.columns:
        rank_cols["npg_trend"] = "trend_pct"

    pct_df = pd.DataFrame(index=df.index)
    for src_col, out_col in rank_cols.items():
        pct_df[out_col] = _percentile_against_reference(
            df,
            reference_df,
            src_col,
        )

    npg_pct = pct_df["npg_pct"].to_numpy(dtype=np.float32)
    ast_pct = pct_df["ast_pct"].to_numpy(dtype=np.float32)
    vol_pct = pct_df["vol_pct"].to_numpy(dtype=np.float32)
    def_pct = pct_df["def_pct"].to_numpy(dtype=np.float32)
    pos_pct = pct_df["pos_pct"].to_numpy(dtype=np.float32)
    trend_pct = pct_df.get(
        "trend_pct",
        pd.Series(np.full(n_rows, 50.0, dtype=np.float32), index=df.index),
    ).to_numpy(dtype=np.float32)

    # League encoding
    league_names = sorted(df["league"].unique())
    league_to_idx = {league: i for i, league in enumerate(league_names)}
    league_idx = np.array([league_to_idx.get(league, 0) for league in df["league"].values])

    # League median minutes
    league_med = reference_df.groupby("league")["minutes"].median()
    global_minutes_median = float(pd.to_numeric(reference_df["minutes"], errors="coerce").median())
    if not np.isfinite(global_minutes_median):
        global_minutes_median = 1800.0
    league_med_arr = np.array(
        [league_med.get(league, global_minutes_median) for league in df["league"].values],
        dtype=np.float32,
    )

    # Team-season grouping (use reset index positions)
    df_reset = df.reset_index(drop=True)
    team_agg_weight = _build_team_aggregation_weights(df_reset)
    team_season_groups = df_reset.groupby(["team", "league", "season"]).groups
    ts_indices = []
    ts_team_names = []
    ts_leagues = []
    ts_seasons = []
    team_group_idx = np.empty(n_rows, dtype=np.int64)
    for (team, league, season), indices in team_season_groups.items():
        group_i = len(ts_indices)
        idx_arr = np.array(
            indices.values if hasattr(indices, "values") else list(indices),
            dtype=np.int64,
        )
        team_group_idx[idx_arr] = group_i
        ts_indices.append(idx_arr)
        ts_team_names.append(team)
        ts_leagues.append(league)
        ts_seasons.append(season)

    return {
        "N": n_rows,
        "n_team_groups": len(ts_indices),
        "team_group_idx": torch.tensor(team_group_idx, dtype=torch.long),
        "team_agg_weight": torch.tensor(team_agg_weight, dtype=torch.float32),
        "pos_idx": torch.tensor(df["pos_idx"].values, dtype=torch.long),
        "npg_pct": torch.tensor(npg_pct, dtype=torch.float32),
        "ast_pct": torch.tensor(ast_pct, dtype=torch.float32),
        "vol_pct": torch.tensor(vol_pct, dtype=torch.float32),
        "def_pct": torch.tensor(def_pct, dtype=torch.float32),
        "pos_pct": torch.tensor(pos_pct, dtype=torch.float32),
        "trend_pct": torch.tensor(trend_pct, dtype=torch.float32),
        "experience": torch.tensor(
            np.clip(
                df["experience_factor"].values
                if "experience_factor" in df.columns
                else np.ones(n_rows),
                0.5,
                1.0,
            ),
            dtype=torch.float32,
        ),
        "minutes": torch.tensor(df["minutes"].values, dtype=torch.float32),
        "starts": torch.tensor(df["starts"].values, dtype=torch.float32),
        "matches": torch.tensor(df["matches"].values, dtype=torch.float32),
        "league_med": torch.tensor(league_med_arr, dtype=torch.float32),
        "league_idx": torch.tensor(league_idx, dtype=torch.long),
        "n_leagues": len(league_names),
        "league_names": league_names,
        "ts_indices": ts_indices,
        "ts_team_names": ts_team_names,
        "ts_leagues": ["Bundesliga" if str(league) == "nan" else league for league in ts_leagues],
        "ts_seasons": ts_seasons,
        "df": df,
    }


def _build_team_aggregation_weights(df_reset: pd.DataFrame) -> np.ndarray:
    """Build robust team-season weights that do not reward raw minutes twice.

    Player ratings already include availability/reliability. For team strength,
    pure minutes weighting lets high-minute average CM/CB/GK profiles drag a
    squad above stronger but more rotated sides. This uses a capped-minutes share
    blended with a core-rotation share, approximating a squad median without
    dropping the first-team signal.
    """
    if df_reset.empty:
        return np.array([], dtype=np.float32)

    minutes = pd.to_numeric(df_reset["minutes"], errors="coerce").fillna(0.0).clip(lower=0.0)
    capped = np.sqrt(np.minimum(minutes.to_numpy(dtype=np.float64), TEAM_AGG_MINUTES_CAP))
    z = np.clip(
        (minutes.to_numpy(dtype=np.float64) - TEAM_AGG_CORE_MINUTES) / TEAM_AGG_CORE_SCALE,
        -50.0,
        50.0,
    )
    core = 1.0 / (1.0 + np.exp(-z))

    work = df_reset.loc[:, ["team", "league", "season"]].copy()
    work["capped"] = capped
    work["core"] = core
    group = work.groupby(["team", "league", "season"], sort=False)
    group_size = group["capped"].transform("size").to_numpy(dtype=np.float64)

    capped_sum = group["capped"].transform("sum").to_numpy(dtype=np.float64)
    core_sum = group["core"].transform("sum").to_numpy(dtype=np.float64)
    capped_share = np.divide(
        capped,
        capped_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=capped_sum > 0,
    )
    core_share = np.divide(
        core,
        core_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=core_sum > 0,
    )

    weights = (
        TEAM_AGG_CAPPED_MINUTES_BLEND * capped_share
        + (1.0 - TEAM_AGG_CAPPED_MINUTES_BLEND) * core_share
    )

    # Apply position slot caps
    if "sub_position" in df_reset.columns:
        slot_group = df_reset["sub_position"].map(POSITION_SLOT_GROUPS).fillna("MF")
        work["slot_group"] = slot_group.values
        work["team_season"] = (
            work["team"] + "|" + work["league"] + "|" + work["season"]
        )
        work["weight"] = weights

        # Compute slot totals per team-season
        slot_totals = work.groupby(
            ["team_season", "slot_group"], sort=False
        )["weight"].transform("sum")
        slot_caps = slot_group.map(POSITION_SLOT_CAPS).fillna(2.5)

        # Scale down weights where slot total exceeds cap
        overcap = slot_totals > slot_caps.values
        if overcap.any():
            scale_factor = np.where(overcap, slot_caps.values / slot_totals, 1.0)
            weights = weights * scale_factor

    # Normalize within team-season
    work["weight"] = weights
    weight_sum = work.groupby(["team", "league", "season"], sort=False)["weight"].transform(
        "sum",
    ).to_numpy(dtype=np.float64)
    normalized = np.divide(
        weights,
        weight_sum,
        out=np.divide(1.0, group_size, out=np.zeros_like(group_size), where=group_size > 0),
        where=weight_sum > 0,
    )
    return normalized.astype(np.float32)


def compute_ratings_torch(feat, params, device):
    """向量化评分，无循环。"""
    # Unpack parameters
    idx = 0
    # Position weights: 8×5
    pw_raw = params[idx:idx + N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = torch.softmax(pw_raw, dim=1)  # [8, 5]
    # 77 个参数仍然参与训练，但位置维度不能完全自由漂移。只用球队积分做监督时，
    # 优化器很容易把 CM/GK 的出勤或 quality 当成通用捷径；这里只封顶明显
    # 不符合角色职责的维度，超出部分回流到该位置仍可使用的其他维度。
    pw = apply_position_weight_caps(pw)
    idx += N_POS * N_DIM

    # Attack weights: 8×3
    aw_raw = params[idx:idx + N_POS * N_ATK].reshape(N_POS, N_ATK)
    aw = torch.softmax(aw_raw, dim=1)  # [8, 3]
    idx += N_POS * N_ATK

    # Availability sub-weights: 4
    avail_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Quality sub-weights: 4
    qual_sw = torch.softmax(params[idx:idx + 4], dim=0)
    idx += 4

    # Scalar params
    league_log_scale = params[idx]  # raw, retained as the league-curve shape control
    idx += 1
    _rel_min_scale = torch.sigmoid(params[idx])  # retained for 77-param compatibility
    rel_starts_scale = torch.sigmoid(params[idx + 1])  # [0, 1] -> maps to [0.3, 0.7]
    idx += 2
    # Trend weight: how much to boost players who are improving
    trend_weight = torch.sigmoid(params[idx]) * 10  # [0, 10] points bonus
    idx += 1
    # Experience weight: how much to boost multi-season players
    exp_weight = torch.sigmoid(params[idx]) * 5  # [0, 5] points bonus

    # Gather position weights for each player
    pos_idx = feat["pos_idx"].to(device)
    player_pw = pw[pos_idx]  # [N, 5]
    player_aw = aw[pos_idx]  # [N, 3]

    minutes = feat["minutes"].to(device)
    starts_t = feat["starts"].to(device)
    matches_t = feat["matches"].to(device)
    league_med = feat["league_med"].to(device)

    # ── Availability ──
    min_share = torch.clamp(minutes / league_med, max=1.0) * 100
    start_rate_score = starts_t / torch.clamp(matches_t, min=1) * 100
    avail_pct = torch.clamp(matches_t / 38, max=1.0) * 100
    role_stab = torch.full_like(minutes, 50.0)

    availability = (min_share * avail_sw[0] + start_rate_score * avail_sw[1]
                    + avail_pct * avail_sw[2] + role_stab * avail_sw[3])

    # ── Attack (percentile-based, pre-computed) ──
    npg_pct = feat["npg_pct"].to(device)
    ast_pct = feat["ast_pct"].to(device)
    vol_pct = feat["vol_pct"].to(device)

    # 前场球员的进攻百分位已经在位置内排序，优化器又可能给 ST/W 很高的 attack
    # 维度权重。如果最后再按位置整体打折，会同时惩罚出勤、防守和控球，解释性较差；
    # 这里只压缩进攻维度本身，让高产前锋仍然靠真实进攻输出拿分，但避免进球/助攻
    # 单一维度把 Top 排名挤满。AM 只做轻微压缩，供未来位置映射修正后使用。
    attack_scale = torch.ones(N_POS, device=device)
    w_idx = POS_TO_IDX.get("W", 1)
    am_idx = POS_TO_IDX.get("AM", 2)
    fb_idx = POS_TO_IDX.get("FB", 5)
    # ST 不压缩 attack：前锋本应由进攻主导，quality cap 已防止 quality 绕路霸榜
    attack_scale[w_idx] = 0.96
    attack_scale[am_idx] = 0.97
    # FB 进攻输出（助攻/传中）不应等同前场：FB 的进攻是附加值，不是核心职责
    # 0.82 压缩让高助攻 FB 仍能获得进攻加分，但不会靠进攻维度霸榜
    attack_scale[fb_idx] = 0.82
    cm_idx = POS_TO_IDX.get("CM", 3)
    dm_idx = POS_TO_IDX.get("DM", 4)
    # FBref 粗位置会把部分边锋/前腰写成 MF。位置重判已处理明显样本；
    # 剩余 CM 的进攻输出仍应作为中场附加价值，而不是等同前场核心产量。
    attack_scale[cm_idx] = 0.92
    attack_scale[dm_idx] = 0.82

    attack = (
        npg_pct * player_aw[:, 0]
        + ast_pct * player_aw[:, 1]
        + vol_pct * player_aw[:, 2]
    ) * attack_scale[pos_idx]

    # ── Defense (percentile-based, real data) ──
    def_pct = feat["def_pct"].to(device)
    defense = def_pct  # Already percentile-ranked within position group

    # ── Possession (percentile-based, real data) ──
    pos_pct = feat["pos_pct"].to(device)
    possession = pos_pct  # Already percentile-ranked within position group

    # ── Quality ──
    quality = (npg_pct * qual_sw[0] + ast_pct * qual_sw[1]
               + def_pct * qual_sw[2] + pos_pct * qual_sw[3])
    # quality 是跨维度效率项，不应让中场通过"进攻百分位 + 出勤"获得前锋级
    # 影响力。ST 的 quality 已被 cap 限制在 0.30，不需要额外下调；
    # CM/DM 下调，避免优化器把中场 quality 当作低风险的统一捷径。
    quality_scale = torch.ones(N_POS, dtype=quality.dtype, device=device)
    quality_scale[cm_idx] = 0.88
    quality_scale[dm_idx] = 0.94
    quality = quality * quality_scale[pos_idx]

    # ── Base score ──
    base = (availability * player_pw[:, 0] + attack * player_pw[:, 1]
            + defense * player_pw[:, 2] + possession * player_pw[:, 3]
            + quality * player_pw[:, 4])

    # ── Reliability (出场时间惩罚) ──
    # 低分钟数样本仍然不可靠，但旧曲线把 500 分钟球员压到 0.3，容易把
    # 半季主力、冬窗转会和伤愈回归球员惩罚过重。这里改成更温和的线性爬坡：
    # <400 分钟保留 0.42 底分，400-1200 分钟快速恢复，>=1200 分钟视为满可信。
    min_threshold = 400.0
    min_ceiling = 1200.0
    min_floor = 0.42
    min_progress = torch.clamp(
        (minutes - min_threshold) / (min_ceiling - min_threshold),
        min=0.0,
        max=1.0,
    )
    min_rel = min_floor + (1.0 - min_floor) * min_progress

    # 首发率惩罚 (保持原有逻辑)
    sr = starts_t / torch.clamp(matches_t, min=1)
    rel_starts_ref = 0.3 + rel_starts_scale * 0.4
    start_rel = 0.85 + 0.15 * torch.clamp(sr / rel_starts_ref, max=1.0)

    # ── 高首发率伤病保护 ──
    # 首发率 >= 70% 的球员，低分钟数大概率是伤病/转会导致，不是替补刷分。
    # 对这类球员，分钟惩罚的底分从 0.42 提升到 0.72，爬坡终点从 1200 降到 900。
    # 这样一个首发率 90%、500 分钟的球员 reliability ≈ 0.85 而非 0.49。
    high_start_mask = sr >= 0.70
    injury_min_floor = 0.72
    injury_min_ceiling = 900.0
    injury_min_progress = torch.clamp(
        (minutes - min_threshold) / (injury_min_ceiling - min_threshold),
        min=0.0,
        max=1.0,
    )
    injury_min_rel = injury_min_floor + (1.0 - injury_min_floor) * injury_min_progress
    # 只对高首发率且低分钟的球员应用保护（分钟>=1200时两者相同，无需切换）
    min_rel = torch.where(high_start_mask & (minutes < min_ceiling), injury_min_rel, min_rel)

    reliability = min_rel * start_rel

    # ── League coefficient ──
    # 外部联赛强度只能作为温和校准，而不是硬排名：当前特征已经是跨联赛球员
    # 原始表现百分位，英超球员本身会因数据分布拿到较高基础分。如果再用线性
    # UEFA 比值，会把 Top 30 推成英超名单；如果完全不用强度先验，又会低估
    # 联赛竞争环境。这里保留 Big 5 强度先验，但用 0.14-0.20 的窄幂曲线压缩
    # 差距。上一版 0.14-0.20 的指数过窄，Ligue 1/Serie A 的高百分位球员
    # 容易被推到接近英超同档。这里改成 0.28-0.42 的中等幂曲线：弱一档
    # 联赛会被明确折扣，但不会把 La Liga/Bundesliga 顶级球员整体压扁。
    league_name_to_coeff = {
        "Premier League": 119.52,
        "La Liga": 93.00,
        "Bundesliga": 92.90,
        "Ligue 1": 83.50,
        "Serie A": 81.93,
    }
    league_names_sorted = feat["league_names"]
    coeff_values = [league_name_to_coeff.get(league, 80.0) for league in league_names_sorted]
    league_coeffs = torch.tensor(coeff_values, dtype=torch.float32, device=device)
    league_ratio = league_coeffs / torch.max(league_coeffs)
    league_curve_exponent = 0.28 + 0.14 * torch.sigmoid(league_log_scale)
    league_strength = torch.pow(league_ratio, league_curve_exponent)

    league_idx = feat["league_idx"].to(device)
    player_league_coeff = league_strength[league_idx]

    # ── Trend bonus ──
    trend_pct = feat["trend_pct"].to(device)
    trend_bonus = (trend_pct - 50) / 50 * trend_weight  # centered at 0, range [-tw, +tw]

    # ── Experience bonus ──
    experience = feat["experience"].to(device)
    exp_bonus = (experience - 0.5) / 0.5 * exp_weight  # centered at 0, range [0, ew]

    # ── Final score ──
    overall = base * reliability * player_league_coeff + trend_bonus + exp_bonus

    return overall


def compute_team_avg_ratings_torch(feat, ratings, device):
    """计算每队每赛季稳健平均评分，保持 Torch 计算图用于反向传播。"""
    group_idx = feat["team_group_idx"].to(device)
    if "team_agg_weight" in feat:
        weights = feat["team_agg_weight"].to(device)
    else:
        minutes = feat["minutes"].to(device)
        weights = torch.clamp(minutes, min=1)
    n_groups = int(feat["n_team_groups"])

    weighted_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weight_sum = torch.zeros(n_groups, dtype=ratings.dtype, device=device)
    weighted_sum = weighted_sum.index_add(0, group_idx, ratings * weights)
    weight_sum = weight_sum.index_add(0, group_idx, weights)
    return weighted_sum / torch.clamp(weight_sum, min=1e-8)


def compute_team_avg_ratings(feat, ratings, device):
    """计算每队每赛季稳健平均评分，返回 NumPy 供报告使用。"""
    return compute_team_avg_ratings_torch(feat, ratings, device).detach().cpu().numpy()


def build_team_target_tensors(feat, team_pts_df, device):
    """把可匹配的球队赛季积分预编译成张量索引，避免训练步内 pandas 查询。

    Teams with NaN or non-finite total_points are excluded.
    """
    # Filter out teams with NaN or non-finite total_points
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }
    matched_group_idx = []
    actual_points = []
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        # Defensive: replace "nan" league with "Bundesliga" (FBref NaN league issue)
        league_str = str(league)
        if league_str == "nan":
            league_str = "Bundesliga"
        key = (str(team), league_str, str(season))
        if key in points_lookup:
            matched_group_idx.append(i)
            actual_points.append(points_lookup[key])

    return (
        torch.tensor(matched_group_idx, dtype=torch.long, device=device),
        torch.tensor(actual_points, dtype=torch.float32, device=device),
    )


def _corrcoef_torch(x, y, eps=1e-8):
    """Pearson correlation with numerical guards."""
    x = x - x.mean()
    y = y - y.mean()
    denom = torch.sqrt(torch.sum(x * x) * torch.sum(y * y)).clamp_min(eps)
    return torch.sum(x * y) / denom


def soft_rank_torch(values, temperature=4.0):
    """Dependency-free smooth ascending ranks for Spearman-style optimization."""
    temp = max(float(temperature), 1e-6)
    x = values.reshape(-1)
    pairwise = (x[:, None] - x[None, :]) / temp
    return torch.sigmoid(pairwise).sum(dim=1)


def differentiable_rank_loss(pred, actual, spearman_weight=0.7, temperature=4.0):
    """Blend soft Spearman and Pearson into a single differentiable objective."""
    pred_rank = soft_rank_torch(pred, temperature=temperature)
    actual_rank = soft_rank_torch(actual.detach(), temperature=temperature)
    soft_spearman = _corrcoef_torch(pred_rank, actual_rank)
    pearson_corr = _corrcoef_torch(pred, actual)
    w = float(np.clip(spearman_weight, 0.0, 1.0))
    objective = w * soft_spearman + (1.0 - w) * pearson_corr
    return -objective, soft_spearman, pearson_corr


def calibrate_points_torch(pred_strength, actual_points, eps=1e-6):
    """Differentiable quadratic calibration from strength to point scale.

    Uses y = a*x^2 + b*x + c fitted on training data, which can capture
    the nonlinear relationship between player rating aggregates and team points.
    Falls back to linear if quadratic fit is unstable.
    """
    pred_detached = pred_strength.detach()
    actual_detached = actual_points.detach()

    # Normalize pred to [0, 1] range for numerical stability
    pred_min = pred_detached.min()
    pred_max = pred_detached.max()
    pred_range = (pred_max - pred_min).clamp(min=eps)
    pred_norm = (pred_strength - pred_min) / pred_range  # [0, 1]

    # Fit quadratic: actual = a*pred_norm^2 + b*pred_norm + c
    # Using least squares with pred_norm, pred_norm^2 as features
    x1 = pred_norm.detach()
    x2 = pred_norm.detach() ** 2
    ones = torch.ones_like(x1)

    # Design matrix [1, x, x^2]
    X = torch.stack([ones, x1, x2], dim=1)  # (n, 3)
    y = actual_detached.unsqueeze(1)  # (n, 1)

    # Normal equations: (X^T X) beta = X^T y
    XtX = X.T @ X + eps * torch.eye(3, device=X.device)  # regularization
    Xty = X.T @ y
    try:
        beta = torch.linalg.solve(XtX, Xty).squeeze(1)  # (3,)
    except Exception:
        # Fallback to linear
        beta = torch.stack([actual_detached.mean(), actual_detached.std(), torch.tensor(0.0, device=X.device)])

    c, b, a = beta[0], beta[1], beta[2]

    # Apply: calibrated = a*pred_norm^2 + b*pred_norm + c
    calibrated = a * pred_norm ** 2 + b * pred_norm + c

    # Ensure the output has the right spread (rescale if needed)
    cal_std = calibrated.detach().std(unbiased=False).clamp(min=eps)
    actual_std = actual_detached.std(unbiased=False).clamp(min=eps)
    # Soft rescale to match actual spread
    calibrated = (calibrated - calibrated.detach().mean()) / cal_std * actual_std + actual_detached.mean()

    return calibrated


def points_regression_loss(pred_strength, actual_points):
    """Optimize calibrated point distance, not just ordering."""
    pred_points = calibrate_points_torch(pred_strength, actual_points)
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    residual = (pred_points - actual_points.detach()) / scale
    return torch.mean(residual ** 2), pred_points


def distribution_matching_loss(pred_points, actual_points):
    """1D Wasserstein-style loss between calibrated predicted and actual points."""
    if len(pred_points) < 2:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    pred_sorted = torch.sort(pred_points).values
    actual_sorted = torch.sort(actual_points.detach()).values
    return torch.mean(((pred_sorted - actual_sorted) / scale) ** 2)


def tail_calibration_loss(pred_points, actual_points, tail_quantile=0.20):
    """Upweight title-race and relegation-zone teams in calibrated point loss."""
    n = int(actual_points.numel())
    if n < 5:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    actual_detached = actual_points.detach()
    low_cut = torch.quantile(actual_detached, float(tail_quantile))
    high_cut = torch.quantile(actual_detached, float(1.0 - tail_quantile))
    tail_mask = (actual_detached <= low_cut) | (actual_detached >= high_cut)
    if int(tail_mask.sum().item()) == 0:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    scale = actual_detached.std(unbiased=False).clamp_min(1.0)
    residual = (pred_points[tail_mask] - actual_detached[tail_mask]) / scale
    return torch.mean(residual ** 2)


def quantile_matching_loss(pred_points, actual_points, quantiles=(0.1, 0.25, 0.5, 0.75, 0.9)):
    """Force predicted distribution quantiles to match actual distribution quantiles.

    Unlike distribution_matching_loss (Wasserstein on sorted values), this explicitly
    targets specific quantile levels, which helps stretch the predicted range.
    """
    if len(pred_points) < 5:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=pred_points.device)
    actual_detached = actual_points.detach()
    scale = actual_detached.std(unbiased=False).clamp_min(1.0)
    losses = []
    for q in quantiles:
        pred_q = torch.quantile(pred_points, q)
        actual_q = torch.quantile(actual_detached, q)
        losses.append(((pred_q - actual_q) / scale) ** 2)
    return torch.stack(losses).mean()


def range_penalty_loss(pred_points, actual_points):
    """Directly penalize the gap between predicted and actual value ranges.

    This is the key loss to fix distribution compression: pred_range=24 vs actual_range=77.
    """
    pred_range = pred_points.max() - pred_points.min()
    actual_range = actual_points.detach().max() - actual_points.detach().min()
    actual_range = actual_range.clamp(min=1.0)
    # Penalize relative range gap: (1 - pred_range/actual_range)^2
    return (1.0 - pred_range / actual_range) ** 2


def league_bias_loss(
    feat,
    matched_group_idx,
    pred_points,
    actual_points,
    device,
    min_teams=5,
):
    """Penalize systematic calibrated point bias by league-season source league."""
    if int(actual_points.numel()) < min_teams:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)
    group_indices = matched_group_idx.detach().cpu().tolist()
    leagues = [str(feat["ts_leagues"][int(group_i)]) for group_i in group_indices]
    if not leagues:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)

    residual = pred_points - actual_points.detach()
    scale = actual_points.detach().std(unbiased=False).clamp_min(1.0)
    losses = []
    for league in sorted(set(leagues)):
        mask_values = [item == league for item in leagues]
        if sum(mask_values) < min_teams:
            continue
        mask = torch.tensor(mask_values, dtype=torch.bool, device=device)
        league_bias = residual[mask].mean() / scale
        losses.append(league_bias ** 2)
    if not losses:
        return torch.tensor(0.0, dtype=pred_points.dtype, device=device)
    return torch.stack(losses).mean()


# ── Dixon-Coles 比分预测似然 ────────────────────────────────────────────

def build_dc_match_tensors(matches_df, feat, device):
    """Build match-level tensors for Dixon-Coles likelihood computation.

    Matches team-season groups from feat with match results from Football-Data.
    Only includes matches where both teams have a team-season group in feat.
    """
    # Build lookup: (normalized_team, league, season) -> group index
    team_season_to_group = {}
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"]),
    ):
        key = (normalize_team_name(team), str(league), str(season))
        team_season_to_group[key] = i

    home_group_idx = []
    away_group_idx = []
    home_goals = []
    away_goals = []

    for _, row in matches_df.iterrows():
        home_key = (
            normalize_team_name(str(row["home_team"])),
            str(row["league"]),
            str(row["season"]),
        )
        away_key = (
            normalize_team_name(str(row["away_team"])),
            str(row["league"]),
            str(row["season"]),
        )
        if home_key in team_season_to_group and away_key in team_season_to_group:
            home_group_idx.append(team_season_to_group[home_key])
            away_group_idx.append(team_season_to_group[away_key])
            home_goals.append(float(row["home_goals"]))
            away_goals.append(float(row["away_goals"]))

    if not home_group_idx:
        return None

    return {
        "home_group_idx": torch.tensor(home_group_idx, dtype=torch.long, device=device),
        "away_group_idx": torch.tensor(away_group_idx, dtype=torch.long, device=device),
        "home_goals": torch.tensor(home_goals, dtype=torch.float32, device=device),
        "away_goals": torch.tensor(away_goals, dtype=torch.float32, device=device),
        "n_matches": len(home_group_idx),
    }


def _poisson_log_pmf(k, lam, eps=1e-8):
    """Log PMF of Poisson: log(P(X=k|λ)) = k*log(λ) - λ - log(k!)"""
    lam_safe = lam.clamp(min=eps)
    return k * torch.log(lam_safe) - lam_safe - torch.lgamma(k + 1.0)


def _dixon_coles_log_tau(x, y, lam_home, lam_away, rho, eps=1e-8):
    """Dixon-Coles low-score correction factor in log space.

    τ corrects Poisson independence for outcomes (0,0), (1,0), (0,1), (1,1).
    Returns log(τ(x, y, λ, μ, ρ)); for scores > 1 returns 0 (log(1)).
    """
    log_tau = torch.zeros_like(lam_home)

    # (0, 0): τ = 1 - λ*μ*ρ
    mask_00 = (x == 0) & (y == 0)
    if mask_00.any():
        val = 1.0 - lam_home[mask_00] * lam_away[mask_00] * rho
        log_tau = log_tau.masked_scatter(mask_00, torch.log(val.clamp(min=eps)))

    # (1, 0): τ = 1 + λ*ρ
    mask_10 = (x == 1) & (y == 0)
    if mask_10.any():
        val = 1.0 + lam_home[mask_10] * rho
        log_tau = log_tau.masked_scatter(mask_10, torch.log(val.clamp(min=eps)))

    # (0, 1): τ = 1 + μ*ρ
    mask_01 = (x == 0) & (y == 1)
    if mask_01.any():
        val = 1.0 + lam_away[mask_01] * rho
        log_tau = log_tau.masked_scatter(mask_01, torch.log(val.clamp(min=eps)))

    # (1, 1): τ = 1 - ρ
    mask_11 = (x == 1) & (y == 1)
    if mask_11.any():
        val = 1.0 - rho
        log_tau = log_tau.masked_scatter(mask_11, torch.log(val.clamp(min=eps)))

    return log_tau


def dixon_coles_log_likelihood(
    team_avgs,
    dc_tensors,
    rho=-0.13,
    base_rate=0.25,
    rating_scale=0.05,
    home_advantage=0.25,
    eps=1e-8,
):
    """Compute Dixon-Coles mean negative log-likelihood from team ratings.

    Expected goals model:
        λ_home = exp(base + scale*(R_home - R_away) + home_adv)
        λ_away = exp(base + scale*(R_away - R_home))

    The ρ parameter corrects Poisson independence for low-score outcomes
    (Dixon & Coles 1997). Returns mean NLL (lower = better fit).

    Gradients flow back through team_avgs → player ratings → params.
    """
    if dc_tensors is None or dc_tensors["n_matches"] == 0:
        return torch.tensor(0.0, device=team_avgs.device, requires_grad=True)

    home_idx = dc_tensors["home_group_idx"]
    away_idx = dc_tensors["away_group_idx"]
    hg = dc_tensors["home_goals"]
    ag = dc_tensors["away_goals"]

    rating_home = team_avgs.index_select(0, home_idx)
    rating_away = team_avgs.index_select(0, away_idx)

    # Expected goals (log-space for stability, then exp)
    diff = rating_scale * (rating_home - rating_away)
    log_lam_home = base_rate + diff + home_advantage
    log_lam_away = base_rate - diff
    lam_home = torch.exp(log_lam_home).clamp(min=eps, max=12.0)
    lam_away = torch.exp(log_lam_away).clamp(min=eps, max=12.0)

    # Poisson log-likelihood for each team
    ll_home = _poisson_log_pmf(hg, lam_home)
    ll_away = _poisson_log_pmf(ag, lam_away)

    # Dixon-Coles low-score correction
    log_tau = _dixon_coles_log_tau(hg, ag, lam_home, lam_away, rho)

    # Negative mean log-likelihood (loss to minimize)
    return -(ll_home + ll_away + log_tau).mean()


# ── 复合目标组件 ─────────────────────────────────────────────────────────

POSITION_CORE_METRICS = {
    "ST": "npg_p90",
    "W": "g_a_volume",
    "AM": "assists_p90",
    "CM": "possession_composite",
    "DM": "defense_composite",
    "FB": "crosses_p90",
    "CB": "defense_composite",
    "GK": "defense_composite",
}


def ndcg_loss(feat, ratings, team_pts_df, device, k=20, temperature=4.0):
    """Differentiable NDCG@K loss across league-season groups.

    Returns 1 - mean(NDCG@K), so lower is better.
    Uses soft-rank discounts for differentiable predicted ranking.
    """
    # Build team average ratings per team-season group
    team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)

    # Build actual points lookup (same logic as build_team_target_tensors)
    valid_pts = team_pts_df.copy()
    valid_pts["total_points"] = pd.to_numeric(valid_pts["total_points"], errors="coerce")
    valid_pts = valid_pts[
        valid_pts["total_points"].notna() & np.isfinite(valid_pts["total_points"])
    ]

    points_lookup = {
        (str(row["team"]), str(row["league"]), str(row["season"])): float(row["total_points"])
        for _, row in valid_pts.iterrows()
    }

    # Group team-season indices by league-season
    league_season_groups: dict[tuple[str, str], list[int]] = {}
    for i, (team, league, season) in enumerate(
        zip(feat["ts_team_names"], feat["ts_leagues"], feat["ts_seasons"], strict=False)
    ):
        key = (str(team), str(league), str(season))
        if key in points_lookup:
            ls_key = (str(league), str(season))
            league_season_groups.setdefault(ls_key, []).append(i)

    if not league_season_groups:
        return torch.tensor(0.0, device=device, requires_grad=True)

    ndcg_values = []
    for _ls_key, group_indices in league_season_groups.items():
        if len(group_indices) < 3:
            continue

        idx_t = torch.tensor(group_indices, dtype=torch.long, device=device)
        pred_ratings = team_avgs.index_select(0, idx_t)
        actual_points = torch.tensor(
            [points_lookup[(str(feat["ts_team_names"][i]),
                            str(feat["ts_leagues"][i]),
                            str(feat["ts_seasons"][i]))]
             for i in group_indices],
            dtype=torch.float32,
            device=device,
        )

        # soft_rank_torch gives ascending ranks; negate ratings so stronger
        # predictions receive lower rank values. Avoid argsort here because it
        # would detach NDCG from the prediction graph.
        pred_soft_rank = soft_rank_torch(-pred_ratings, temperature=temperature)

        # Normalize actual points to [0, 1] for relevance
        pts_min = actual_points.min()
        pts_max = actual_points.max()
        pts_range = pts_max - pts_min
        if pts_range < 1e-8:
            continue
        rel = (actual_points - pts_min) / pts_range

        top_k = min(k, len(group_indices))
        gains = torch.pow(2.0, rel) - 1.0
        soft_discounts = 1.0 / torch.log2(pred_soft_rank + 2.0)
        gate_temperature = max(float(temperature) / 4.0, 0.5)
        top_gate = torch.sigmoid((top_k - pred_soft_rank) / gate_temperature)
        dcg = torch.sum(gains * soft_discounts * top_gate)

        # Ideal DCG: sort by actual relevance descending
        ideal_sorted_rel = torch.sort(rel, descending=True).values[:top_k]
        positions = torch.arange(1, top_k + 1, dtype=torch.float32, device=device)
        discounts = 1.0 / torch.log2(positions + 1.0)
        idcg = torch.sum((torch.pow(2.0, ideal_sorted_rel) - 1.0) * discounts)
        if idcg < 1e-8:
            continue

        ndcg_values.append(dcg / idcg)

    if not ndcg_values:
        return torch.tensor(0.0, device=device, requires_grad=True)

    mean_ndcg = torch.stack(ndcg_values).mean()
    return 1.0 - mean_ndcg


def position_consistency_loss(feat, ratings, device, temperature=4.0):
    """Penalize inconsistency between rating rank and core-stat rank within each position.

    Returns mean(1 - soft_spearman) across positions.
    """
    pos_idx = feat["pos_idx"].to(device)
    df = feat["df"]

    losses = []
    for pos_name, core_metric in POSITION_CORE_METRICS.items():
        pos_i = POS_TO_IDX[pos_name]
        mask = (pos_idx == pos_i)
        n_pos = int(mask.sum().item())
        if n_pos < 5:
            continue

        # Get core metric values from the DataFrame
        if core_metric not in df.columns:
            continue
        metric_series = pd.to_numeric(df[core_metric], errors="coerce")
        # Exclude NaN rows from position consistency loss — Understat rows
        # without defense/possession data should not distort the metric.
        valid_mask = mask & torch.tensor(
            metric_series.notna().values, dtype=torch.bool, device=device,
        )
        n_valid = int(valid_mask.sum().item())
        if n_valid < 5:
            continue
        metric_values = metric_series.fillna(0.0).values
        metric_t = torch.tensor(metric_values, dtype=torch.float32, device=device)
        pos_ratings = ratings[valid_mask]
        pos_metrics = metric_t[valid_mask]

        # Skip if all values are identical (no ranking signal)
        if pos_metrics.std() < 1e-8 or pos_ratings.std() < 1e-8:
            continue

        # Soft Spearman between ratings and core metric
        rating_rank = soft_rank_torch(pos_ratings, temperature=temperature)
        metric_rank = soft_rank_torch(pos_metrics.detach(), temperature=temperature)
        soft_sp = _corrcoef_torch(rating_rank, metric_rank)
        losses.append(1.0 - soft_sp)

    if not losses:
        return torch.tensor(0.0, device=device, requires_grad=True)

    return torch.stack(losses).mean()


def extreme_penalty(ratings, sigma=3.0):
    """L2 penalty on ratings beyond sigma standard deviations from mean.

    Penalizes extreme ratings that may result from attendance shortcuts.
    """
    mean = ratings.mean()
    std = ratings.std()
    z = (ratings - mean) / (std + 1e-8)
    extreme_mask = (z.abs() > z.new_full([], sigma)).float()
    penalty = (extreme_mask * (z - sigma * z.sign()) ** 2).mean()
    return penalty


def objective_torch(
    feat,
    team_pts_df,
    params,
    device,
    spearman_weight=0.30,
    soft_rank_temperature=4.0,
    ndcg_weight=0.12,
    position_consistency_weight=0.10,
    points_regression_weight=0.20,
    distribution_weight=0.05,
    quantile_weight=0.08,
    range_penalty_weight=0.10,
    tail_calibration_weight=0.08,
    league_bias_weight=0.05,
    extreme_penalty_weight=0.02,
    prior_weight=0.01,
    dc_likelihood_weight=0.08,
    dc_tensors=None,
    prior_params=None,
    verbose=False,
    return_components=False,
):
    """Composite objective with ranking, calibrated points, distribution and guardrails."""
    ratings = compute_ratings_torch(feat, params, device)
    team_avgs = compute_team_avg_ratings_torch(feat, ratings, device)
    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts_df, device)

    if len(matched_group_idx) < 10:
        dummy = torch.tensor(1.0, device=device, requires_grad=True)
        if return_components:
            return dummy, {}
        return dummy

    pred_t = team_avgs.index_select(0, matched_group_idx)

    # 1. Spearman/Pearson loss
    rank_loss, soft_sp, pr = differentiable_rank_loss(
        pred_t,
        actual_t,
        temperature=soft_rank_temperature,
    )

    # 2. NDCG loss
    ndcg = ndcg_loss(feat, ratings, team_pts_df, device, k=20, temperature=soft_rank_temperature)

    # 3. Position consistency loss
    pos_loss = position_consistency_loss(feat, ratings, device, temperature=soft_rank_temperature)

    # 4. Calibrated team-points losses
    points_loss, pred_points = points_regression_loss(pred_t, actual_t)
    dist_loss = distribution_matching_loss(pred_points, actual_t)
    quant_loss = quantile_matching_loss(pred_points, actual_t)
    range_pen = range_penalty_loss(pred_points, actual_t)
    tail_loss = tail_calibration_loss(pred_points, actual_t)
    lg_bias_loss = league_bias_loss(feat, matched_group_idx, pred_points, actual_t, device)

    # 5b. Dixon-Coles match-level likelihood
    dc_loss = torch.tensor(0.0, device=device)
    if dc_tensors is not None and dc_likelihood_weight > 0:
        dc_loss = dixon_coles_log_likelihood(team_avgs, dc_tensors)

    # 6. Player-score guardrail. This is not the team-points tail loss.
    ext_pen = extreme_penalty(ratings)

    # 6. Prior regularization
    if prior_params is not None:
        prior_reg = ((params - prior_params) ** 2).mean()
    else:
        prior_reg = torch.tensor(0.0, device=device)

    total = (
        spearman_weight * rank_loss
        + ndcg_weight * ndcg
        + position_consistency_weight * pos_loss
        + points_regression_weight * points_loss
        + distribution_weight * dist_loss
        + quantile_weight * quant_loss
        + range_penalty_weight * range_pen
        + tail_calibration_weight * tail_loss
        + league_bias_weight * lg_bias_loss
        + dc_likelihood_weight * dc_loss
        + extreme_penalty_weight * ext_pen
        + prior_weight * prior_reg
    )

    if verbose:
        print(
            f"  rank={rank_loss.item():.4f} ndcg={ndcg.item():.4f} "
            f"pos={pos_loss.item():.4f} points={points_loss.item():.4f} "
            f"dist={dist_loss.item():.4f} quant={quant_loss.item():.4f} "
            f"range={range_pen.item():.4f} tail={tail_loss.item():.4f} "
            f"league_bias={lg_bias_loss.item():.4f} "
            f"dc={dc_loss.item():.4f} "
            f"ext={ext_pen.item():.4f} "
            f"prior={prior_reg.item():.4f} total={total.item():.4f}"
        )

    if return_components:
        components = {
            "rank_loss": float(rank_loss.detach().cpu()),
            "ndcg": float(ndcg.detach().cpu()),
            "pos_loss": float(pos_loss.detach().cpu()),
            "points_loss": float(points_loss.detach().cpu()),
            "distribution": float(dist_loss.detach().cpu()),
            "quantile": float(quant_loss.detach().cpu()),
            "range_penalty": float(range_pen.detach().cpu()),
            "tail": float(tail_loss.detach().cpu()),
            "league_bias": float(lg_bias_loss.detach().cpu()),
            "dc_likelihood": float(dc_loss.detach().cpu()),
            "extreme": float(ext_pen.detach().cpu()),
            "prior": float(prior_reg.detach().cpu()),
            "soft_spearman": float(soft_sp.detach().cpu()),
            "soft_pearson": float(pr.detach().cpu()),
            "pred_points_std": float(pred_points.detach().std(unbiased=False).cpu()),
            "actual_points_std": float(actual_t.detach().std(unbiased=False).cpu()),
        }
        return total, components

    return total


# ── 优化循环 ──────────────────────────────────────────────────────────────

def cosine_lr_scale(
    step: int,
    total_steps: int,
    warmup_steps: int = 20,
    min_lr_ratio: float = 0.08,
) -> float:
    """Warm up linearly, then decay with a cosine floor."""
    total_steps = max(int(total_steps), 1)
    warmup_steps = max(0, min(int(warmup_steps), total_steps))
    min_lr_ratio = float(np.clip(min_lr_ratio, 0.0, 1.0))
    if warmup_steps > 0 and step < warmup_steps:
        return max((step + 1) / warmup_steps, min_lr_ratio)
    decay_steps = max(total_steps - warmup_steps, 1)
    progress = (step - warmup_steps) / decay_steps
    progress = float(np.clip(progress, 0.0, 1.0))
    cosine = 0.5 * (1.0 + np.cos(np.pi * progress))
    return min_lr_ratio + (1.0 - min_lr_ratio) * cosine


def optimize(
    feat,
    team_pts,
    device,
    n_steps=500,
    lr=0.035,
    pop_size=32,
    spearman_weight=0.30,
    soft_rank_temperature=4.0,
    ndcg_weight=0.12,
    position_consistency_weight=0.10,
    points_regression_weight=0.20,
    distribution_weight=0.05,
    quantile_weight=0.08,
    range_penalty_weight=0.10,
    tail_calibration_weight=0.08,
    league_bias_weight=0.05,
    extreme_penalty_weight=0.02,
    prior_strength=0.01,
    dc_likelihood_weight=0.08,
    dc_tensors=None,
    init_scale=0.35,
    patience=80,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=None,
    enable_viz=True,
    output_dir=None,
):
    """
    多起点并行优化。
    对 pop_size 组随机初始化的参数同时优化，取最优。
    """
    print(f"  设备: {device}")
    print(f"  种群: {pop_size}, 步数: {n_steps}, 学习率: {lr}")
    print(
        "  目标: "
        f"spearman={spearman_weight:.2f} ndcg={ndcg_weight:.2f} "
        f"pos_consistency={position_consistency_weight:.2f} "
        f"points={points_regression_weight:.2f} dist={distribution_weight:.2f} "
        f"tail={tail_calibration_weight:.2f} league_bias={league_bias_weight:.2f} "
        f"dc_likelihood={dc_likelihood_weight:.2f} "
        f"player_extreme={extreme_penalty_weight:.2f} prior={prior_strength:.2f}"
    )
    print(
        "  调度: "
        f"warmup={warmup_steps}, min_lr_ratio={min_lr_ratio:.2f}, grad_clip={grad_clip:.2f}"
    )

    if seed is not None:
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if device.type == "cuda":
            torch.cuda.manual_seed_all(int(seed))

    matched_group_idx, actual_t = build_team_target_tensors(feat, team_pts, device)
    if len(matched_group_idx) < 10:
        raise ValueError("可匹配的球队赛季少于 10 个，无法稳定优化")

    prior_params = _get_default_params_tensor(device)

    # 初始化可视化器 (使用新版 Plotly)
    viz = create_visualizer(n_steps=n_steps, pop_size=pop_size, enable=enable_viz)
    viz.start()

    # 初始化参数种群
    all_params = []
    all_losses = []
    all_final_corrs = []

    for pop_i in range(pop_size):
        # Warm-start from the explainable v3 prior, then explore around it.
        if pop_i == 0:
            params = prior_params.clone()
        else:
            params = prior_params + torch.randn(N_PARAMS, device=device) * init_scale

        # Adam optimizer
        params_t = params.clone().detach().requires_grad_(True)
        optimizer = torch.optim.AdamW([params_t], lr=lr)

        best_loss = float("inf")
        best_params = params_t.clone().detach()
        patience_counter = 0

        for step in range(n_steps):
            lr_scale = cosine_lr_scale(
                step,
                n_steps,
                warmup_steps=warmup_steps,
                min_lr_ratio=min_lr_ratio,
            )
            for group in optimizer.param_groups:
                group["lr"] = lr * lr_scale

            optimizer.zero_grad()

            total_loss, components = objective_torch(
                feat,
                team_pts,
                params_t,
                device,
                spearman_weight=spearman_weight,
                soft_rank_temperature=soft_rank_temperature,
                ndcg_weight=ndcg_weight,
                position_consistency_weight=position_consistency_weight,
                points_regression_weight=points_regression_weight,
                distribution_weight=distribution_weight,
                quantile_weight=quantile_weight,
                range_penalty_weight=range_penalty_weight,
                tail_calibration_weight=tail_calibration_weight,
                league_bias_weight=league_bias_weight,
                extreme_penalty_weight=extreme_penalty_weight,
                prior_weight=prior_strength,
                dc_likelihood_weight=dc_likelihood_weight,
                dc_tensors=dc_tensors,
                prior_params=prior_params,
                return_components=True,
            )

            total_loss.backward()
            if grad_clip and grad_clip > 0:
                torch.nn.utils.clip_grad_norm_([params_t], max_norm=float(grad_clip))
            optimizer.step()

            current_loss = float(total_loss.detach().cpu())

            # 更新可视化 (每 5 步更新一次)
            if step % 5 == 0:
                # 提取位置权重用于热力图
                params_cpu = params_t.detach().cpu()
                pw_raw = params_cpu[:N_POS * N_DIM].reshape(N_POS, N_DIM)
                pw_np = torch.softmax(pw_raw, dim=1).numpy()
                position_weights = {
                    pos: {dim: pw_np[i, j] for j, dim in enumerate(DIMENSIONS)}
                    for i, pos in enumerate(POSITIONS)
                }
                
                viz.update(
                    step=step,
                    pop_idx=pop_i,
                    loss=current_loss,
                    spearman=components.get("soft_spearman", 0.0),
                    pearson=components.get("soft_pearson", 0.0),
                    components=components,
                    position_weights=position_weights,
                )

            if current_loss < best_loss:
                best_loss = current_loss
                best_params = params_t.clone().detach()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter > patience:
                break

        # Final evaluation with Spearman (non-differentiable but correct metric)
        final_ratings = compute_ratings_torch(feat, best_params, device)
        final_team_avgs = compute_team_avg_ratings(feat, final_ratings, device)

        idx_np = matched_group_idx.detach().cpu().numpy()
        pred_arr = final_team_avgs[idx_np]
        actual_arr = actual_t.detach().cpu().numpy()
        sp, _ = spearmanr(pred_arr, actual_arr)
        pr, _ = pearsonr(pred_arr, actual_arr)

        all_params.append(best_params.cpu())
        all_losses.append(-sp)
        all_final_corrs.append((sp, pr))

        if (pop_i + 1) % 5 == 0 or pop_i == 0:
            print(f"  [{pop_i+1}/{pop_size}] best Spearman={sp:.4f}  Pearson={pr:.4f}")

    # Pick best
    best_idx = int(np.argmin(all_losses))
    best_sp, best_pr = all_final_corrs[best_idx]
    print(f"\n  最优: Spearman={best_sp:.4f}  Pearson={best_pr:.4f}  (第 {best_idx+1} 组)")

    # 训练结束，保存可视化报告
    viz.finalize(best_params=all_params[best_idx], best_spearman=best_sp, best_pearson=best_pr)
    if output_dir is not None:
        viz.save(Path(output_dir) / "training_report.html")
        viz.save_json(Path(output_dir) / "training_history.json")
    viz.close()

    return all_params[best_idx].to(device)


def _inv_softmax(probs):
    """Approximate inverse softmax."""
    p = np.array(probs, dtype=np.float32)
    p = np.clip(p, 1e-10, 1.0)
    return np.log(p) - np.log(p).mean()


def _get_default_params_tensor(device):
    """Default v3 weights converted to parameter tensor."""
    params = []
    for row in POSITION_DIMENSION_PRIOR:
        params.extend(_inv_softmax(row))
    for row in ATTACK_WEIGHT_PRIOR:
        params.extend(_inv_softmax(row))
    params.extend(_inv_softmax([0.45, 0.25, 0.20, 0.10]))
    params.extend(_inv_softmax(QUALITY_SUBWEIGHT_PRIOR))
    params.extend([1.0, 0.0, 0.0])  # league_log_scale, rel_min, rel_starts
    # trend_weight (sigmoid=0.5 -> 5), experience_weight (sigmoid=0.5 -> 2.5)
    params.extend([0.0, 0.0])
    return torch.tensor(params, dtype=torch.float32, device=device)


def run_cross_validation(
    df,
    team_pts,
    device,
    *,
    n_splits=3,
    test_seasons=1,
    min_train_seasons=2,
    gap_seasons=0,
    n_steps=150,
    lr=0.035,
    pop_size=8,
    spearman_weight=0.30,
    soft_rank_temperature=4.0,
    ndcg_weight=0.12,
    position_consistency_weight=0.10,
    points_regression_weight=0.20,
    distribution_weight=0.05,
    quantile_weight=0.08,
    range_penalty_weight=0.10,
    tail_calibration_weight=0.08,
    league_bias_weight=0.05,
    extreme_penalty_weight=0.02,
    prior_strength=0.01,
    init_scale=0.35,
    patience=40,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=42,
    calibration_bins=5,
    league_calibration_prior_n=60.0,
    league_calibration_cap=8.0,
    disable_league_calibration=False,
):
    """Run expanding-window CV; each fold optimizes only on its train seasons."""
    splits = make_season_splits(
        df,
        n_splits=n_splits,
        test_seasons=test_seasons,
        min_train_seasons=min_train_seasons,
        gap_seasons=gap_seasons,
    )
    default_params = _get_default_params_tensor(device)
    rows = []
    for fold_idx, split in enumerate(splits, start=1):
        print(
            f"\n  CV {split.name}: train={list(split.train_seasons)} "
            f"test={list(split.test_seasons)}"
        )
        train_df = _filter_by_seasons(df, split.train_seasons)
        test_df = _filter_by_seasons(df, split.test_seasons)
        train_team_pts = _filter_by_seasons(team_pts, split.train_seasons)
        test_team_pts = _filter_by_seasons(team_pts, split.test_seasons)
        train_feat = build_feature_tensors(train_df)
        fold_params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
            spearman_weight=spearman_weight,
            soft_rank_temperature=soft_rank_temperature,
            ndcg_weight=ndcg_weight,
            position_consistency_weight=position_consistency_weight,
            points_regression_weight=points_regression_weight,
            distribution_weight=distribution_weight,
            tail_calibration_weight=tail_calibration_weight,
            league_bias_weight=league_bias_weight,
            extreme_penalty_weight=extreme_penalty_weight,
            prior_strength=prior_strength,
            init_scale=init_scale,
            patience=patience,
            warmup_steps=warmup_steps,
            min_lr_ratio=min_lr_ratio,
            grad_clip=grad_clip,
            seed=seed + fold_idx,
        )
        for model_name, params in [("baseline_v3", default_params), ("optimized", fold_params)]:
            train_raw = evaluate_params(
                params,
                train_df,
                train_team_pts,
                train_df,
                device,
                split_name="train",
                calibration_bins=calibration_bins,
            )
            points_calibrator = fit_team_points_calibrator(
                train_raw["matched"],
                use_league_offsets=not disable_league_calibration,
                league_prior_n=league_calibration_prior_n,
                league_offset_cap=league_calibration_cap,
            )
            for split_name, eval_df, eval_team_pts in [
                ("train", train_df, train_team_pts),
                ("test", test_df, test_team_pts),
            ]:
                evaluation = evaluate_params(
                    params,
                    eval_df,
                    eval_team_pts,
                    train_df,
                    device,
                    split_name=split_name,
                    calibration_bins=calibration_bins,
                    points_calibrator=points_calibrator,
                )
                row = {
                    "fold": fold_idx,
                    "fold_name": split.name,
                    "model": model_name,
                    "split": split_name,
                    "train_seasons": ",".join(split.train_seasons),
                    "test_seasons": ",".join(split.test_seasons),
                }
                row.update(evaluation["metrics"])
                rows.append(row)
    return pd.DataFrame(rows)


def run_parameter_stability(
    train_df,
    test_df,
    train_team_pts,
    test_team_pts,
    device,
    *,
    n_runs=3,
    n_steps=150,
    lr=0.035,
    pop_size=8,
    spearman_weight=0.30,
    soft_rank_temperature=4.0,
    ndcg_weight=0.12,
    position_consistency_weight=0.10,
    points_regression_weight=0.20,
    distribution_weight=0.05,
    quantile_weight=0.08,
    range_penalty_weight=0.10,
    tail_calibration_weight=0.08,
    league_bias_weight=0.05,
    extreme_penalty_weight=0.02,
    prior_strength=0.01,
    init_scale=0.35,
    patience=40,
    warmup_steps=20,
    min_lr_ratio=0.08,
    grad_clip=5.0,
    seed=42,
    calibration_bins=5,
    league_calibration_prior_n=60.0,
    league_calibration_cap=8.0,
    disable_league_calibration=False,
):
    """Repeat optimization across seeds and summarize metric/parameter variance."""
    if n_runs <= 1:
        return pd.DataFrame(), {}

    train_feat = build_feature_tensors(train_df)
    rows = []
    params_rows = []
    for run_idx in range(n_runs):
        run_seed = seed + run_idx * 101
        print(f"\n  稳定性 run {run_idx + 1}/{n_runs}: seed={run_seed}")
        params = optimize(
            train_feat,
            train_team_pts,
            device,
            n_steps=n_steps,
            lr=lr,
            pop_size=pop_size,
            spearman_weight=spearman_weight,
            soft_rank_temperature=soft_rank_temperature,
            ndcg_weight=ndcg_weight,
            position_consistency_weight=position_consistency_weight,
            points_regression_weight=points_regression_weight,
            distribution_weight=distribution_weight,
            tail_calibration_weight=tail_calibration_weight,
            league_bias_weight=league_bias_weight,
            extreme_penalty_weight=extreme_penalty_weight,
            prior_strength=prior_strength,
            init_scale=init_scale,
            patience=patience,
            warmup_steps=warmup_steps,
            min_lr_ratio=min_lr_ratio,
            grad_clip=grad_clip,
            seed=run_seed,
        )
        train_raw = evaluate_params(
            params,
            train_df,
            train_team_pts,
            train_df,
            device,
            split_name="train",
            calibration_bins=calibration_bins,
        )
        points_calibrator = fit_team_points_calibrator(
            train_raw["matched"],
            use_league_offsets=not disable_league_calibration,
            league_prior_n=league_calibration_prior_n,
            league_offset_cap=league_calibration_cap,
        )
        train_eval = evaluate_params(
            params,
            train_df,
            train_team_pts,
            train_df,
            device,
            split_name="train",
            calibration_bins=calibration_bins,
            points_calibrator=points_calibrator,
        )
        test_eval = evaluate_params(
            params,
            test_df,
            test_team_pts,
            train_df,
            device,
            split_name="test",
            calibration_bins=calibration_bins,
            points_calibrator=points_calibrator,
        )
        rows.append(
            {
                "run": run_idx + 1,
                "seed": run_seed,
                "train_spearman": train_eval["metrics"]["spearman"],
                "test_spearman": test_eval["metrics"]["spearman"],
                "train_rank_loss": train_eval["metrics"]["rank_loss"],
                "test_rank_loss": test_eval["metrics"]["rank_loss"],
                "overfit_rank_loss_gap": (
                    test_eval["metrics"]["rank_loss"] - train_eval["metrics"]["rank_loss"]
                ),
            },
        )
        params_rows.append(params.detach().cpu().numpy())

    stability_df = pd.DataFrame(rows)
    params_matrix = np.vstack(params_rows)
    param_std = np.std(params_matrix, axis=0)
    summary = {
        "runs": int(n_runs),
        "test_spearman_mean": float(stability_df["test_spearman"].mean()),
        "test_spearman_std": float(stability_df["test_spearman"].std(ddof=0)),
        "test_spearman_min": float(stability_df["test_spearman"].min()),
        "test_spearman_max": float(stability_df["test_spearman"].max()),
        "param_std_mean": float(np.mean(param_std)),
        "param_std_max": float(np.max(param_std)),
    }
    return stability_df, summary


def _print_metric_block(title, baseline_eval, optimized_eval):
    base = baseline_eval["metrics"]
    opt = optimized_eval["metrics"]
    print(f"\n{title}")
    print("-" * 80)
    print(
        "  baseline_v3: "
        f"Spearman={base['spearman']:.4f}  Pearson={base['pearson']:.4f}  "
        f"rank_loss={base['rank_loss']:.4f}  calib_MAE={base['calibration_mae']:.2f}  "
        f"points_MAE={base['points_mae']:.2f}  "
        f"raw_spread={base['raw_spread_ratio']:.2f}  "
        f"N={base['n_team_seasons']}"
    )
    print(
        "  optimized:   "
        f"Spearman={opt['spearman']:.4f}  Pearson={opt['pearson']:.4f}  "
        f"rank_loss={opt['rank_loss']:.4f}  calib_MAE={opt['calibration_mae']:.2f}  "
        f"points_MAE={opt['points_mae']:.2f}  "
        f"raw_spread={opt['raw_spread_ratio']:.2f}  "
        f"N={opt['n_team_seasons']}"
    )
    print(
        "  improvement: "
        f"Spearman {opt['spearman'] - base['spearman']:+.4f}  "
        f"rank_loss {opt['rank_loss'] - base['rank_loss']:+.4f}"
    )


# ── 主流程 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="球员评分权重优化器 (GPU)")
    parser.add_argument("--data_dir", type=str, default="./data",
                        help="数据目录路径 (包含 raw/ 和 gold/)")
    parser.add_argument("--steps", type=int, default=500, help="每组优化步数")
    parser.add_argument("--lr", type=float, default=0.035, help="初始学习率")
    parser.add_argument("--pop", type=int, default=32, help="种群大小 (并行起点数)")
    parser.add_argument("--spearman-weight", type=float, default=0.42,
                        help="Spearman/Pearson 排名损失在复合目标中的权重")
    parser.add_argument("--soft-rank-temperature", type=float, default=4.0,
                        help="soft-rank 温度；越小越接近硬排名但梯度更容易饱和")
    parser.add_argument("--ndcg-weight", type=float, default=0.16,
                        help="NDCG@20 损失在复合目标中的权重")
    parser.add_argument("--position-consistency-weight", type=float, default=0.12,
                        help="位置核心指标一致性损失在复合目标中的权重")
    parser.add_argument("--points-regression-weight", type=float, default=0.16,
                        help="训练集校准后球队积分回归损失在复合目标中的权重")
    parser.add_argument("--distribution-weight", type=float, default=0.10,
                        help="校准后积分分布匹配损失在复合目标中的权重")
    parser.add_argument("--tail-calibration-weight", type=float, default=0.14,
                        help="争冠/降级尾部球队校准损失在复合目标中的权重")
    parser.add_argument("--league-bias-weight", type=float, default=0.08,
                        help="训练集联赛平均积分残差惩罚在复合目标中的权重")
    parser.add_argument("--extreme-penalty-weight", type=float, default=0.05,
                        help="球员评分离群 guardrail 在复合目标中的权重")
    parser.add_argument("--prior-weight", type=float, default=0.04,
                        help="锚定 v3 默认权重的正则强度")
    parser.add_argument("--prior-strength", type=float, default=None,
                        help="锚定 v3 默认权重的正则强度 (deprecated, use --prior-weight)")
    parser.add_argument("--init-scale", type=float, default=0.35,
                        help="多起点围绕 v3 默认参数的随机扰动标准差")
    parser.add_argument("--patience", type=int, default=80, help="单个起点的 early-stop 耐心步数")
    parser.add_argument("--warmup-steps", type=int, default=20, help="学习率线性 warmup 步数")
    parser.add_argument("--min-lr-ratio", type=float, default=0.08,
                        help="余弦衰减后的最小学习率比例")
    parser.add_argument("--grad-clip", type=float, default=5.0,
                        help="梯度裁剪阈值；<=0 表示禁用")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--test-seasons", type=int, default=1, help="最终 holdout 使用最近几个赛季")
    parser.add_argument(
        "--min-train-seasons",
        type=int,
        default=2,
        help="每个时间切分最少训练赛季数",
    )
    parser.add_argument("--gap-seasons", type=int, default=0, help="训练和测试之间跳过的赛季数")
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=3,
        help="时间序列交叉验证 fold 数；0 表示跳过",
    )
    parser.add_argument("--cv-steps", type=int, default=None, help="CV 每 fold 优化步数")
    parser.add_argument("--cv-pop", type=int, default=None, help="CV 每 fold 起点数")
    parser.add_argument("--stability-runs", type=int, default=3, help="不同 seed 稳定性运行次数")
    parser.add_argument("--stability-steps", type=int, default=None, help="稳定性运行每次优化步数")
    parser.add_argument("--stability-pop", type=int, default=None, help="稳定性运行每次起点数")
    parser.add_argument("--importance-repeats", type=int, default=1, help="特征置换重要性重复次数")
    parser.add_argument("--calibration-bins", type=int, default=5, help="校准检查分箱数")
    parser.add_argument("--league-calibration-prior-n", type=float, default=60.0,
                        help="训练集联赛残差 offset 的收缩强度；越大越保守")
    parser.add_argument("--league-calibration-cap", type=float, default=8.0,
                        help="训练集联赛残差 offset 的绝对值上限")
    parser.add_argument(
        "--disable-league-calibration",
        action="store_true",
        help="禁用 train-fitted 联赛残差 offset，仅使用全局积分校准",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速模式：大幅降低种群/步数/耐心，适合 Mac CPU/MPS 本地快速迭代",
    )
    parser.add_argument(
        "--no-viz",
        action="store_true",
        help="禁用实时可视化（适用于无 GUI 环境或远程服务器）",
    )
    args = parser.parse_args()

    # Quick mode: Mac-friendly defaults
    if args.quick:
        if args.steps == 500:
            args.steps = 80
        if args.pop == 32:
            args.pop = 6
        if args.patience == 80:
            args.patience = 15
        if args.warmup_steps == 20:
            args.warmup_steps = 8
        if args.cv_folds == 3:
            args.cv_folds = 0
        if args.stability_runs == 3:
            args.stability_runs = 0
        if args.importance_repeats == 1:
            args.importance_repeats = 0

    # Backward compatibility: --prior-strength overrides --prior-weight if set
    if args.prior_strength is not None:
        args.prior_weight = args.prior_strength

    data_dir = Path(args.data_dir).resolve()
    print("=" * 80)
    print("球员评分权重优化器 (PyTorch GPU)")
    print("=" * 80)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("\nApple MPS (Metal)")
    else:
        device = torch.device("cpu")
        print("\nCPU (没有 GPU 加速)")

    # Load data
    print("\n[1] 加载数据...")
    t0 = time.time()
    data_load_result = load_data(data_dir)
    if len(data_load_result) == 3:
        df, team_pts, matches_df = data_load_result
    else:
        df, team_pts = data_load_result
        matches_df = None

    # 出场标记：不足 20 场的球员仍参与评分，但不参与优化训练
    min_matches_opt = 20
    if "matches" in df.columns:
        df["low_appearance"] = df["matches"] < min_matches_opt
        n_low = df["low_appearance"].sum()
        print(f"  出场标记 (<{min_matches_opt}场): {n_low} 人标记为 low_appearance")

    print(f"  球员: {len(df)}, 球队赛季: {len(team_pts)}")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # Compute input hash for reproducibility
    feat_hash = compute_input_hash(data_dir)
    print(f"  输入哈希: {feat_hash}")

    print("\n[2] 时间切分...")
    holdout = make_holdout_split(
        df,
        test_seasons=args.test_seasons,
        min_train_seasons=args.min_train_seasons,
        gap_seasons=args.gap_seasons,
    )
    train_df = _filter_by_seasons(df, holdout.train_seasons)
    test_df = _filter_by_seasons(df, holdout.test_seasons)
    train_team_pts = _filter_by_seasons(team_pts, holdout.train_seasons)
    test_team_pts = _filter_by_seasons(team_pts, holdout.test_seasons)

    # 优化训练排除 low_appearance 球员（仍参与最终评分）
    if "low_appearance" in train_df.columns:
        n_low_train = train_df["low_appearance"].sum()
        train_df = train_df[~train_df["low_appearance"]].copy()
        print(f"  训练集排除 low_appearance: {n_low_train} 人")

    print(f"  train seasons: {list(holdout.train_seasons)}")
    print(f"  test seasons:  {list(holdout.test_seasons)}")
    print(f"  train players={len(train_df)}, test players={len(test_df)}")

    print("\n[3] 基线 (v3 默认权重, 不训练)...")
    default_params = _get_default_params_tensor(device)
    baseline_train_raw_eval = evaluate_params(
        default_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
    )
    baseline_points_calibrator = fit_team_points_calibrator(
        baseline_train_raw_eval["matched"],
        use_league_offsets=not args.disable_league_calibration,
        league_prior_n=args.league_calibration_prior_n,
        league_offset_cap=args.league_calibration_cap,
    )
    baseline_train_eval = evaluate_params(
        default_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
        points_calibrator=baseline_points_calibrator,
    )
    baseline_test_eval = evaluate_params(
        default_params,
        test_df,
        test_team_pts,
        train_df,
        device,
        split_name="test",
        calibration_bins=args.calibration_bins,
        points_calibrator=baseline_points_calibrator,
    )
    print(
        f"  train Spearman={baseline_train_eval['metrics']['spearman']:.4f}  "
        f"test Spearman={baseline_test_eval['metrics']['spearman']:.4f}"
    )

    print(f"\n[4] 只在训练赛季优化 (pop={args.pop}, steps={args.steps}, lr={args.lr})...")
    t0 = time.time()
    train_feat = build_feature_tensors(train_df)
    best_params = optimize(
        train_feat,
        train_team_pts,
        device,
        n_steps=args.steps,
        lr=args.lr,
        pop_size=args.pop,
        spearman_weight=args.spearman_weight,
        soft_rank_temperature=args.soft_rank_temperature,
        ndcg_weight=args.ndcg_weight,
        position_consistency_weight=args.position_consistency_weight,
        points_regression_weight=args.points_regression_weight,
        distribution_weight=args.distribution_weight,
        tail_calibration_weight=args.tail_calibration_weight,
        league_bias_weight=args.league_bias_weight,
        extreme_penalty_weight=args.extreme_penalty_weight,
        prior_strength=args.prior_weight,
        init_scale=args.init_scale,
        patience=args.patience,
        warmup_steps=args.warmup_steps,
        min_lr_ratio=args.min_lr_ratio,
        grad_clip=args.grad_clip,
        seed=args.seed,
        enable_viz=not args.no_viz,
        output_dir=data_dir / "gold" / "feature_store",
    )
    print(f"  总耗时: {time.time()-t0:.1f}s")

    optimized_train_raw_eval = evaluate_params(
        best_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
    )
    optimized_points_calibrator = fit_team_points_calibrator(
        optimized_train_raw_eval["matched"],
        use_league_offsets=not args.disable_league_calibration,
        league_prior_n=args.league_calibration_prior_n,
        league_offset_cap=args.league_calibration_cap,
    )
    optimized_train_eval = evaluate_params(
        best_params,
        train_df,
        train_team_pts,
        train_df,
        device,
        split_name="train",
        calibration_bins=args.calibration_bins,
        points_calibrator=optimized_points_calibrator,
    )
    optimized_test_eval = evaluate_params(
        best_params,
        test_df,
        test_team_pts,
        train_df,
        device,
        split_name="test",
        calibration_bins=args.calibration_bins,
        points_calibrator=optimized_points_calibrator,
    )

    print("\n[5] Train/Test 对比:")
    _print_metric_block("  训练集", baseline_train_eval, optimized_train_eval)
    _print_metric_block("  Holdout 测试集", baseline_test_eval, optimized_test_eval)
    overfit_gap = (
        optimized_test_eval["metrics"]["rank_loss"] - optimized_train_eval["metrics"]["rank_loss"]
    )
    print(f"\n  过拟合检查: test_rank_loss - train_rank_loss = {overfit_gap:+.4f}")

    print("\n[6] 优化后权重:")
    print("-" * 80)
    best_params_cpu = best_params.detach().cpu()
    pw_raw = best_params_cpu[:N_POS * N_DIM].reshape(N_POS, N_DIM)
    pw = apply_position_weight_caps(torch.softmax(pw_raw, dim=1)).cpu().numpy()
    print(f"{'位置':<5} {'出勤':>7} {'进攻':>7} {'防守':>7} {'控球':>7} {'质量':>7}")
    print("-" * 80)
    for i, pos in enumerate(POSITIONS):
        print(
            f"{pos:<5} {pw[i,0]:>7.4f} {pw[i,1]:>7.4f} "
            f"{pw[i,2]:>7.4f} {pw[i,3]:>7.4f} {pw[i,4]:>7.4f}"
        )

    # Attack weights
    aw_raw = best_params_cpu[N_POS * N_DIM:N_POS * N_DIM + N_POS * N_ATK].reshape(
        N_POS,
        N_ATK,
    )
    aw = torch.softmax(aw_raw, dim=1).cpu().numpy()
    print(f"\n{'位置':<5} {'npxG_p90':>9} {'ast_p90':>9} {'G+A_vol':>9}")
    print("-" * 40)
    for i, pos in enumerate(POSITIONS):
        print(f"{pos:<5} {aw[i,0]:>9.4f} {aw[i,1]:>9.4f} {aw[i,2]:>9.4f}")

    print("\n[7] Holdout 球队覆盖率:")
    holdout_coverage = optimized_test_eval["coverage"]
    if holdout_coverage.empty:
        print("  没有可报告的球队覆盖率")
    else:
        for _, row in holdout_coverage.iterrows():
            print(
                f"  {row['league']:<22} {row['season']:<8} "
                f"matched={int(row['matched_teams']):>2}/"
                f"{int(row['target_teams']):<2} "
                f"rated={int(row['rated_teams']):>2} "
                f"coverage={row['coverage']:.2f}"
            )

    print("\n[8] Holdout 联赛分层评估:")
    holdout_league_metrics = league_metrics(
        optimized_test_eval["matched"],
        min_n=5,
        calibration_bins=args.calibration_bins,
    )
    if holdout_league_metrics.empty:
        print("  样本不足，未生成联赛分层指标")
    else:
        for _, row in holdout_league_metrics.iterrows():
            print(
                f"  {row['league']:<22} Spearman={row['spearman']:.3f}  "
                f"Pearson={row['pearson']:.3f}  calib_MAE={row['calibration_mae']:.2f}  "
                f"N={int(row['n_team_seasons'])}"
            )

    print("\n[9] Holdout 校准检查:")
    calibration_test = optimized_test_eval["calibration"]
    for _, row in calibration_test.iterrows():
        print(
            f"  bin={int(row['bin']) if pd.notna(row['bin']) else -1} "
            f"N={int(row['n'])} "
            f"pred_pct={row['pred_percentile_mean']:.1f} "
            f"actual_pct={row['actual_percentile_mean']:.1f} "
            f"gap={row['calibration_gap']:+.1f}"
        )

    cv_metrics = pd.DataFrame()
    cv_error = None
    if args.cv_folds > 0:
        print("\n[10] 时间序列交叉验证:")
        try:
            cv_metrics = run_cross_validation(
                df,
                team_pts,
                device,
                n_splits=args.cv_folds,
                test_seasons=args.test_seasons,
                min_train_seasons=args.min_train_seasons,
                gap_seasons=args.gap_seasons,
                n_steps=args.cv_steps or max(50, args.steps // 3),
                lr=args.lr,
                pop_size=args.cv_pop or max(2, args.pop // 4),
                spearman_weight=args.spearman_weight,
                soft_rank_temperature=args.soft_rank_temperature,
                ndcg_weight=args.ndcg_weight,
                position_consistency_weight=args.position_consistency_weight,
                points_regression_weight=args.points_regression_weight,
                distribution_weight=args.distribution_weight,
                tail_calibration_weight=args.tail_calibration_weight,
                league_bias_weight=args.league_bias_weight,
                extreme_penalty_weight=args.extreme_penalty_weight,
                prior_strength=args.prior_weight,
                init_scale=args.init_scale,
                patience=min(args.patience, 40),
                warmup_steps=min(
                    args.warmup_steps,
                    max(1, (args.cv_steps or max(50, args.steps // 3)) // 5),
                ),
                min_lr_ratio=args.min_lr_ratio,
                grad_clip=args.grad_clip,
                seed=args.seed,
                calibration_bins=args.calibration_bins,
                league_calibration_prior_n=args.league_calibration_prior_n,
                league_calibration_cap=args.league_calibration_cap,
                disable_league_calibration=args.disable_league_calibration,
            )
            cv_test = cv_metrics.loc[
                (cv_metrics["model"] == "optimized") & (cv_metrics["split"] == "test")
            ]
            base_test = cv_metrics.loc[
                (cv_metrics["model"] == "baseline_v3") & (cv_metrics["split"] == "test")
            ]
            print(
                "  optimized test Spearman: "
                f"mean={cv_test['spearman'].mean():.4f}, "
                f"std={cv_test['spearman'].std(ddof=0):.4f}"
            )
            print(
                "  baseline_v3 test Spearman: "
                f"mean={base_test['spearman'].mean():.4f}, "
                f"std={base_test['spearman'].std(ddof=0):.4f}"
            )
        except ValueError as error:
            cv_error = str(error)
            print(f"  跳过 CV: {cv_error}")

    stability_df = pd.DataFrame()
    stability_summary = {}
    if args.stability_runs > 1:
        print("\n[11] 参数稳定性:")
        stability_df, stability_summary = run_parameter_stability(
            train_df,
            test_df,
            train_team_pts,
            test_team_pts,
            device,
            n_runs=args.stability_runs,
            n_steps=args.stability_steps or max(50, args.steps // 3),
            lr=args.lr,
            pop_size=args.stability_pop or max(2, args.pop // 4),
            spearman_weight=args.spearman_weight,
            soft_rank_temperature=args.soft_rank_temperature,
            ndcg_weight=args.ndcg_weight,
            position_consistency_weight=args.position_consistency_weight,
            points_regression_weight=args.points_regression_weight,
            distribution_weight=args.distribution_weight,
            tail_calibration_weight=args.tail_calibration_weight,
            league_bias_weight=args.league_bias_weight,
            extreme_penalty_weight=args.extreme_penalty_weight,
            prior_strength=args.prior_weight,
            init_scale=args.init_scale,
            patience=min(args.patience, 40),
            warmup_steps=min(
                args.warmup_steps,
                max(1, (args.stability_steps or max(50, args.steps // 3)) // 5),
            ),
            min_lr_ratio=args.min_lr_ratio,
            grad_clip=args.grad_clip,
            seed=args.seed,
            calibration_bins=args.calibration_bins,
            league_calibration_prior_n=args.league_calibration_prior_n,
            league_calibration_cap=args.league_calibration_cap,
            disable_league_calibration=args.disable_league_calibration,
        )
        print(
            "  test Spearman: "
            f"mean={stability_summary['test_spearman_mean']:.4f}, "
            f"std={stability_summary['test_spearman_std']:.4f}, "
            f"min={stability_summary['test_spearman_min']:.4f}, "
            f"max={stability_summary['test_spearman_max']:.4f}"
        )
        print(
            "  param std: "
            f"mean={stability_summary['param_std_mean']:.4f}, "
            f"max={stability_summary['param_std_max']:.4f}"
        )

    feature_importance = pd.DataFrame()
    if args.importance_repeats > 0:
        print("\n[12] 特征置换重要性 (Holdout):")
        feature_importance = permutation_feature_importance(
            best_params,
            test_df,
            test_team_pts,
            train_df,
            device,
            n_repeats=args.importance_repeats,
            seed=args.seed,
            calibration_bins=args.calibration_bins,
        )
        if feature_importance.empty:
            print("  样本不足，未生成特征重要性")
        else:
            for _, row in feature_importance.head(10).iterrows():
                print(
                    f"  {row['feature']:<24} "
                    f"Spearman drop={row['spearman_drop_mean']:+.4f}"
                )

    # Save
    output = data_dir / "gold" / "feature_store"
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "optimized_params.npy", best_params.detach().cpu().numpy())
    print(f"\n[13] 参数已保存: {output / 'optimized_params.npy'}")

    # Save model run registry
    try:
        save_model_run(
            params=best_params.cpu().numpy(),
            metrics=optimized_test_eval["metrics"],
            args=args,
            output_dir=data_dir / "models" / "runs",
            feat_hash=feat_hash,
        )
    except Exception as exc:
        print(f"  模型运行登记保存失败: {exc}")

    holdout_predictions = optimized_test_eval["matched"].rename(
        columns={
            "pred_rating": "optimized_rating",
            "pred_points_global": "optimized_points_global",
            "pred_points_league_offset": "optimized_points_league_offset",
            "pred_points_calibrated": "optimized_points_calibrated",
        },
    )
    if not holdout_predictions.empty and not baseline_test_eval["matched"].empty:
        baseline_holdout = baseline_test_eval["matched"].loc[
            :,
            [
                "team",
                "league",
                "season",
                "pred_rating",
                "pred_points_global",
                "pred_points_league_offset",
                "pred_points_calibrated",
            ],
        ].rename(
            columns={
                "pred_rating": "baseline_v3_rating",
                "pred_points_global": "baseline_v3_points_global",
                "pred_points_league_offset": "baseline_v3_points_league_offset",
                "pred_points_calibrated": "baseline_v3_points_calibrated",
            },
        )
        holdout_predictions = holdout_predictions.merge(
            baseline_holdout,
            on=["team", "league", "season"],
            how="left",
        )
    holdout_predictions.to_parquet(output / "rating_holdout_predictions.parquet", index=False)
    if not cv_metrics.empty:
        cv_metrics.to_parquet(output / "rating_cv_metrics.parquet", index=False)
    if not stability_df.empty:
        stability_df.to_parquet(output / "rating_parameter_stability.parquet", index=False)
    if not feature_importance.empty:
        feature_importance.to_parquet(output / "rating_feature_importance.parquet", index=False)
    if not holdout_league_metrics.empty:
        holdout_league_metrics.to_parquet(output / "rating_league_metrics.parquet", index=False)
    if not holdout_coverage.empty:
        holdout_coverage.to_parquet(output / "rating_team_coverage.parquet", index=False)
    calibration_test.to_parquet(output / "rating_calibration_test.parquet", index=False)

    meta = {
        "optimizer": "adamw_composite_objective",
        "metric_scope": "holdout_test",
        "n_params": N_PARAMS,
        "device": str(device),
        "seed": args.seed,
        "pop": args.pop,
        "steps": args.steps,
        "lr": args.lr,
        "spearman_weight": args.spearman_weight,
        "ndcg_weight": args.ndcg_weight,
        "position_consistency_weight": args.position_consistency_weight,
        "points_regression_weight": args.points_regression_weight,
        "distribution_weight": args.distribution_weight,
        "tail_calibration_weight": args.tail_calibration_weight,
        "league_bias_weight": args.league_bias_weight,
        "extreme_penalty_weight": args.extreme_penalty_weight,
        "prior_weight": args.prior_weight,
        "soft_rank_temperature": args.soft_rank_temperature,
        "init_scale": args.init_scale,
        "patience": args.patience,
        "warmup_steps": args.warmup_steps,
        "min_lr_ratio": args.min_lr_ratio,
        "grad_clip": args.grad_clip,
        "league_calibration_prior_n": args.league_calibration_prior_n,
        "league_calibration_cap": args.league_calibration_cap,
        "disable_league_calibration": args.disable_league_calibration,
        "points_calibration": {
            "baseline_v3": baseline_points_calibrator,
            "optimized": optimized_points_calibrator,
            "fit_scope": "train seasons only",
        },
        "holdout": {
            "train_seasons": list(holdout.train_seasons),
            "test_seasons": list(holdout.test_seasons),
            "baseline_train": baseline_train_eval["metrics"],
            "baseline_test": baseline_test_eval["metrics"],
            "optimized_train": optimized_train_eval["metrics"],
            "optimized_test": optimized_test_eval["metrics"],
            "overfit_rank_loss_gap": overfit_gap,
        },
        "team_aggregation": team_aggregation_config(),
        "baseline_spearman": baseline_test_eval["metrics"]["spearman"],
        "baseline_pearson": baseline_test_eval["metrics"]["pearson"],
        "optimized_spearman": optimized_test_eval["metrics"]["spearman"],
        "optimized_pearson": optimized_test_eval["metrics"]["pearson"],
        "cv": {
            "folds": args.cv_folds,
            "error": cv_error,
            "metrics": cv_metrics,
        },
        "stability": {
            "runs": args.stability_runs,
            "summary": stability_summary,
            "runs_detail": stability_df,
        },
        "feature_importance": feature_importance,
        "league_metrics": holdout_league_metrics,
        "team_coverage": holdout_coverage,
        "calibration_test": calibration_test,
        "n_players": int(len(df)),
        "n_train_players": int(len(train_df)),
        "n_test_players": int(len(test_df)),
        "n_team_seasons": int(optimized_test_eval["metrics"]["n_team_seasons"]),
    }
    (output / "optimized_params_meta.json").write_text(
        json.dumps(_json_ready(meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  参数元数据已保存: {output / 'optimized_params_meta.json'}")

    # Save re-rated players
    all_feat = build_feature_tensors(df, rank_reference_df=train_df)
    all_ratings = compute_ratings_torch(all_feat, best_params, device)
    scored_df = df.copy()
    scored_df["optimized_score"] = all_ratings.detach().cpu().numpy()

    # 低出场额外扣分：不足 20 场的球员按出场比例打折
    if "low_appearance" in scored_df.columns and "matches" in scored_df.columns:
        min_matches_penalty = 20
        low_mask = scored_df["low_appearance"]
        if low_mask.any():
            # 线性惩罚：0场→扣30%，10场→扣15%，20场→不扣
            penalty = 1.0 - 0.30 * (
                1.0 - scored_df["matches"] / min_matches_penalty
            ).clip(0, 1)
            scored_df.loc[low_mask, "optimized_score"] *= penalty[low_mask]
            n_low = low_mask.sum()
            print(f"  低出场扣分: {n_low} 人 (最多扣 30%)")

    # Compute same_position_score: percentile rank within season + sub_position
    min_position_group_size = 5

    def _compute_position_percentile(group):
        """Compute percentile rank within a group, returning NaN if too few members."""
        if len(group) < min_position_group_size:
            return pd.Series(np.nan, index=group.index)
        return group.rank(pct=True) * 100

    # Primary: season + sub_position percentile
    scored_df["same_position_score"] = (
        scored_df.groupby(["season", "sub_position"])["optimized_score"]
        .transform(_compute_position_percentile)
    )

    # Fallback: sub_position global percentile for groups that were too small
    needs_fallback = scored_df["same_position_score"].isna()
    if needs_fallback.any():
        global_pct = (
            scored_df.loc[needs_fallback]
            .groupby("sub_position")["optimized_score"]
            .transform(
                lambda g: (
                    g.rank(pct=True) * 100
                    if len(g) >= min_position_group_size
                    else pd.Series(np.nan, index=g.index)
                )
            )
        )
        scored_df.loc[needs_fallback, "same_position_score"] = global_pct

    scored_df = scored_df.sort_values("optimized_score", ascending=False)
    scored_df.to_parquet(output / "player_ratings_optimized.parquet", index=False)
    print(f"  球员评分已保存: {output / 'player_ratings_optimized.parquet'}")

    print("\n  Top 20 (优化后):")
    print("-" * 80)
    for i, (_, row) in enumerate(scored_df.head(20).iterrows(), 1):
        print(f"  {i:>3}  {row['player']:<28} {row['team']:<22} "
              f"{row['sub_position']:<3} {row['optimized_score']:>6.1f}")

    # ── Position distribution diagnostics ──
    print("\n  位置分布诊断:")
    print("-" * 60)
    for n in [20, 50, 100]:
        top_n = scored_df.head(n)
        pos_counts = top_n["sub_position"].value_counts()
        total = len(top_n)
        print(f"\n  Top {n} 位置分布:")
        for pos in POSITIONS:
            count = pos_counts.get(pos, 0)
            pct = count / total * 100 if total > 0 else 0
            flag = " ⚠" if pct > 40 else ""
            print(f"    {pos:>3}: {count:>3} ({pct:>5.1f}%){flag}")

    if "position_confidence" in scored_df.columns:
        top100 = scored_df.head(100)
        low_conf = top100[top100["position_confidence"] == "low"]
        if not low_conf.empty:
            print(f"\n  Top 100 中 position_confidence=low 的球员 ({len(low_conf)} 人):")
            print("-" * 80)
            for _, row in low_conf.iterrows():
                print(f"    {row['player']:<28} {row['team']:<22} "
                      f"{row['sub_position']:<3} src={row.get('position_source', 'N/A'):<8} "
                      f"score={row['optimized_score']:>6.1f}")
        else:
            print("\n  Top 100 中无 position_confidence=low 球员")

    if "same_position_score" in scored_df.columns:
        print("\n  同位置评分 Top 5 (按 same_position_score):")
        print("-" * 80)
        for pos in POSITIONS:
            pos_players = scored_df[scored_df["sub_position"] == pos].head(5)
            if pos_players.empty:
                continue
            print(f"\n  {pos}:")
            for _, row in pos_players.iterrows():
                sps = row.get("same_position_score", float("nan"))
                sps_str = f"{sps:>5.1f}" if pd.notna(sps) else "  N/A"
                print(f"    {row['player']:<28} {row['team']:<22} "
                      f"abs={row['optimized_score']:>6.1f}  pos={sps_str}")

    if "position_source" in scored_df.columns:
        print("\n  位置映射统计 (position_source → sub_position):")
        print("-" * 60)
        mapping = (
            scored_df.groupby(["position_source", "sub_position"])
            .size()
            .reset_index(name="count")
        )
        mapping = mapping.sort_values("count", ascending=False)
        for _, row in mapping.head(30).iterrows():
            pos_src = str(row['position_source'])
            print(f"    {pos_src:<12} → {row['sub_position']:<4} ({row['count']:>4})")
        if len(mapping) > 30:
            print(f"    ... 共 {len(mapping)} 种映射，仅显示前 30")


if __name__ == "__main__":
    main()
