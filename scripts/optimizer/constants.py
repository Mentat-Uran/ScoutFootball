"""
optimizer.constants
───────────────────
Shared constants, team-name aliases, position mappings, and helper functions
used across the optimizer pipeline.

Extracted from optimize_ratings_gpu.py during the modularisation refactor.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import torch

if TYPE_CHECKING:
    import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════
# Position / dimension constants
# ═══════════════════════════════════════════════════════════════════════════

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

# ── Prior matrices ────────────────────────────────────────────────────────

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

# ── Dimension caps per position (max weight any dimension can carry) ──────

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

# ═══════════════════════════════════════════════════════════════════════════
# Team aggregation constants
# ═══════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════
# Position → core metric mapping (used by consistency losses)
# ═══════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════
# Team-name normalisation
# ═══════════════════════════════════════════════════════════════════════════
# FBref, Understat 和 Football-Data 使用不同的队名格式。
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


# ═══════════════════════════════════════════════════════════════════════════
# Team-name helper
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SeasonSplit:
    """Chronological split by complete seasons."""

    name: str
    train_seasons: tuple[str, ...]
    test_seasons: tuple[str, ...]


@dataclass
class TeamPointsCalibrator:
    """Z-score affine calibration from predicted team ratings to actual points.

    Fitted on train seasons, reused for holdout/test seasons to fix range compression.
    """

    method: str
    slope: float
    intercept: float
    pred_mean: float
    pred_std: float
    actual_mean: float
    actual_std: float
    min_slope: float = 0.05
    max_slope: float = 8.0
    league_offsets: dict[str, float] | None = None
    league_residual_means: dict[str, float] | None = None
    league_counts: dict[str, int] | None = None
    league_prior_n: float = 60.0
    league_offset_cap: float = 8.0


# ═══════════════════════════════════════════════════════════════════════════
# Position mapping helpers
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Position refinement (MF/DF → more specific roles)
# ═══════════════════════════════════════════════════════════════════════════


def refine_role_positions(df: "pd.DataFrame") -> "pd.DataFrame":
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
    import pandas as pd

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


# ═══════════════════════════════════════════════════════════════════════════
# Position-weight caps (for optimiser)
# ═══════════════════════════════════════════════════════════════════════════


def apply_position_weight_caps(weights: torch.Tensor) -> torch.Tensor:
    """限制明显不符合角色职责的维度权重，并保持每行归一化。"""
    caps = torch.tensor(POSITION_DIMENSION_CAPS, dtype=weights.dtype, device=weights.device)
    capped = torch.minimum(weights, caps)
    missing = torch.clamp(1.0 - capped.sum(dim=1, keepdim=True), min=0.0)
    room = torch.clamp(caps - capped, min=0.0)
    room_sum = room.sum(dim=1, keepdim=True).clamp_min(1e-8)
    adjusted = capped + missing * room / room_sum
    return adjusted / adjusted.sum(dim=1, keepdim=True).clamp_min(1e-8)


# ═══════════════════════════════════════════════════════════════════════════
# Team aggregation config helper
# ═══════════════════════════════════════════════════════════════════════════


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
