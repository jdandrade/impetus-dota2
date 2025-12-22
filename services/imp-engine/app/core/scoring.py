"""
IMP Scoring Algorithm v5 - Penta-Role Engine

Phase 19: Upgraded from Core/Support to granular 5-position model.
Uses coefficients derived from Ridge Regression on 6,236 Stratz samples.

Each position (Pos 1-5) has its own coefficient set:
- Position 1: Safe Lane Carry (n=1247, R²=0.6733)
- Position 2: Mid Lane (n=1246, R²=0.7081)
- Position 3: Offlane (n=1248, R²=0.6949)
- Position 4: Soft Support (n=1246, R²=0.6879)
- Position 5: Hard Support (n=1249, R²=0.6809)

Formula: IMP = Intercept + Σ(stat * coefficient) + WinLossBonus
"""

from datetime import datetime, timezone
from typing import Literal

from app.models.request import CalculateIMPRequest
from app.models.response import (
    CalculateIMPResponse,
    ContributingFactor,
    IMPData,
    IMPMeta,
)

# Engine version
ENGINE_VERSION = "0.6.0-penta-role"

# ============================================
# PENTA-ROLE COEFFICIENTS (from Ridge Regression)
# Trained on 6,236 player samples from Stratz
# Average R² = 0.689 across all roles
# ============================================

# Win/Loss bonuses (applied after regression score)
# These override the regression's is_victory coefficient
WIN_BONUS = 12.0
LOSS_PENALTY = -8.0

# Safe Lane Carry (n=1247, R²=0.6733, MAE=9.5956)
POSITION_1_COEFFICIENTS = {
    "intercept": -4.3649,
    "deaths_per_min": -23.912013,
    "assists_per_min": 16.272023,
    "kills_per_min": -14.740573,
    "death_rate": -13.112811,
    "kills": 1.971527,
    "deaths": -1.276859,
    "assists": 0.838599,
    "ka_ratio": -0.48297,
    "duration_minutes": -0.35762,
    "level": 0.32737,
    "denies": 0.265896,
    "kda_ratio": 0.210637,
    "last_hits": 0.022987,
    "gpm": 0.012919,
    "healing_per_min": 0.005106,
    "tower_damage_per_min": 0.004401,
    "farm_efficiency": 0.003331,
    "xpm": -0.000904,
    "hero_damage_per_min": 0.000792,
    "networth": -0.000489,
    "damage_efficiency": -0.000459,
    "hero_damage": -0.000228,
    "hero_healing": 0.000188,
}

# Mid Lane (n=1246, R²=0.7081, MAE=9.3456)
POSITION_2_COEFFICIENTS = {
    "intercept": -2.6509,
    "death_rate": -13.851965,
    "assists_per_min": 8.010835,
    "deaths_per_min": -6.651517,
    "kills_per_min": -5.38882,
    "ka_ratio": 2.329863,
    "kills": 1.654526,
    "deaths": -1.622213,
    "assists": 0.899231,
    "kda_ratio": 0.46211,
    "denies": 0.393173,
    "level": 0.378092,
    "duration_minutes": -0.278948,
    "healing_per_min": -0.031113,
    "gpm": 0.017591,
    "last_hits": 0.015407,
    "farm_efficiency": -0.006813,
    "tower_damage_per_min": 0.005822,
    "xpm": -0.001969,
    "damage_efficiency": -0.001875,
    "hero_healing": 0.000936,
    "hero_damage_per_min": 0.000886,
    "hero_damage": -0.000251,
    "networth": -0.000212,
}

# Offlane (n=1248, R²=0.6949, MAE=8.876)
POSITION_3_COEFFICIENTS = {
    "intercept": -4.4639,
    "assists_per_min": 19.072005,
    "death_rate": -15.327975,
    "deaths_per_min": -7.131863,
    "ka_ratio": 4.829715,
    "deaths": -1.567984,
    "kills": 1.37336,
    "level": 0.756783,
    "assists": 0.630882,
    "kda_ratio": 0.480432,
    "kills_per_min": 0.393051,
    "denies": 0.375646,
    "duration_minutes": -0.257055,
    "gpm": 0.015043,
    "last_hits": 0.013532,
    "healing_per_min": 0.009469,
    "hero_damage_per_min": -0.00485,
    "farm_efficiency": -0.00485,
    "xpm": -0.003559,
    "damage_efficiency": -0.003071,
    "tower_damage_per_min": -0.002158,
    "networth": -0.000475,
}

# Soft Support (n=1246, R²=0.6879, MAE=8.9342)
POSITION_4_COEFFICIENTS = {
    "intercept": -2.5562,
    "deaths_per_min": -22.070328,
    "death_rate": -13.418473,
    "assists_per_min": 9.726072,
    "ka_ratio": 8.79605,
    "kills_per_min": -4.518062,
    "kills": 1.459887,
    "deaths": -1.296564,
    "assists": 0.905028,
    "level": 0.734925,
    "duration_minutes": -0.447605,
    "denies": 0.246111,
    "kda_ratio": 0.164577,
    "last_hits": 0.02553,
    "tower_damage_per_min": -0.021798,
    "farm_efficiency": -0.007705,
    "xpm": -0.0077,
    "gpm": 0.003424,
    "healing_per_min": 0.002528,
    "hero_damage_per_min": 0.001517,
    "tower_damage": 0.00067,
    "hero_damage": -0.000338,
    "hero_healing": 0.000171,
}

# Hard Support (n=1249, R²=0.6809, MAE=8.9456)
POSITION_5_COEFFICIENTS = {
    "intercept": -1.1954,
    "deaths_per_min": -20.54682,
    "death_rate": -13.612081,
    "assists_per_min": 11.235089,
    "ka_ratio": 7.676888,
    "deaths": -1.524418,
    "kills": 1.305451,
    "assists": 0.849128,
    "level": 0.681932,
    "denies": 0.425801,
    "duration_minutes": -0.33586,
    "kills_per_min": 0.137809,
    "kda_ratio": 0.039967,
    "last_hits": 0.023022,
    "farm_efficiency": -0.022223,
    "gpm": 0.020422,
    "xpm": -0.006087,
    "tower_damage_per_min": -0.004541,
    "hero_damage_per_min": -0.003115,
    "healing_per_min": 0.002395,
    "damage_efficiency": -0.000368,
    "tower_damage": 0.000257,
    "hero_damage": -0.000197,
    "networth": -0.000182,
}

# Role mapping from API role names to position numbers
ROLE_TO_POSITION = {
    "carry": 1,
    "mid": 2,
    "offlane": 3,
    "support": 4,
    "hard_support": 5,
}

# All coefficients by position
POSITION_COEFFICIENTS = {
    1: POSITION_1_COEFFICIENTS,
    2: POSITION_2_COEFFICIENTS,
    3: POSITION_3_COEFFICIENTS,
    4: POSITION_4_COEFFICIENTS,
    5: POSITION_5_COEFFICIENTS,
}

# ============================================
# SCORE LIMITS AND GRADES
# ============================================

IMP_MAX = 65.0
IMP_MIN = -65.0

GRADE_THRESHOLDS: list[tuple[float, Literal["S", "A", "B", "C", "D", "F"]]] = [
    (40, "S"),   # +40 and above = Elite MVP
    (20, "A"),   # +20 to +40 = Great
    (5, "B"),    # +5 to +20 = Above average
    (-5, "C"),   # -5 to +5 = Average
    (-20, "D"),  # -20 to -5 = Below average
    (-65, "F"),  # Below -20 = Poor
]

# Display names for contributing factors
STAT_DISPLAY_NAMES = {
    "deaths": "Deaths",
    "kills": "Kills",
    "assists": "Assists",
    "gpm": "GPM",
    "xpm": "XPM",
    "kills_per_min": "Kills/min",
    "deaths_per_min": "Deaths/min",
    "assists_per_min": "Assists/min",
    "tower_damage": "Tower Damage",
    "tower_damage_per_min": "Tower Dmg/min",
    "hero_damage": "Hero Damage",
    "hero_damage_per_min": "Hero Dmg/min",
    "networth": "Net Worth",
    "level": "Level",
    "hero_healing": "Healing",
    "healing_per_min": "Healing/min",
    "kda_ratio": "KDA Ratio",
    "ka_ratio": "K+A Rate",
    "death_rate": "Death Rate",
    "farm_efficiency": "Farm Rate",
    "damage_efficiency": "Dmg Efficiency",
    "duration_minutes": "Game Length",
    "last_hits": "Last Hits",
    "denies": "Denies",
}


def _get_grade(score: float) -> Literal["S", "A", "B", "C", "D", "F"]:
    """Convert a numeric score to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def _calculate_percentile_from_score(score: float) -> int:
    """Estimate percentile from IMP score (0-100)."""
    # Map -65 to +65 to 0-100 percentile
    normalized = (score - IMP_MIN) / (IMP_MAX - IMP_MIN)
    return int(_clamp(normalized * 100, 0, 100))


def _get_position(role: str) -> int:
    """Convert role name to position number (1-5)."""
    return ROLE_TO_POSITION.get(role, 1)  # Default to carry if unknown


def _get_role_description(position: int) -> str:
    """Get human-readable role description."""
    descriptions = {
        1: "Carry",
        2: "Mid",
        3: "Offlane",
        4: "Support",
        5: "Hard Support",
    }
    return descriptions.get(position, "Unknown")


def calculate_imp_score(request: CalculateIMPRequest) -> CalculateIMPResponse:
    """
    Calculate IMP score using the Penta-Role regression model.
    
    Each position (1-5) has its own coefficient set derived from ~1,250 samples.
    Formula: IMP = Intercept + Σ(stat * coefficient) + WinLossBonus
    """
    
    stats = request.stats
    role = request.role
    is_winner = request.context.team_result == "win"
    duration_minutes = request.duration_seconds / 60.0
    safe_duration = max(duration_minutes, 1.0)
    
    # Step A: Determine position
    position = _get_position(role)
    coefficients = POSITION_COEFFICIENTS.get(position, POSITION_1_COEFFICIENTS)
    
    # ============================================
    # Step B: Prepare all stat values
    # ============================================
    
    # Raw stats
    kills = stats.kills
    deaths = stats.deaths
    assists = stats.assists
    gpm = stats.gpm
    xpm = stats.xpm
    networth = stats.net_worth
    level = stats.level
    hero_damage = stats.hero_damage
    tower_damage = stats.tower_damage
    hero_healing = stats.hero_healing
    last_hits = stats.last_hits
    denies = stats.denies
    
    # Per-minute stats
    kills_per_min = kills / safe_duration
    deaths_per_min = deaths / safe_duration
    assists_per_min = assists / safe_duration
    hero_damage_per_min = hero_damage / safe_duration
    tower_damage_per_min = tower_damage / safe_duration
    healing_per_min = hero_healing / safe_duration
    
    # Engineered features
    kda_ratio = (kills + assists) / max(deaths, 1)
    ka_ratio = (kills + assists) / safe_duration
    death_rate = deaths / safe_duration
    farm_efficiency = networth / safe_duration
    damage_efficiency = hero_damage / max(networth, 1) if networth > 0 else 0
    
    # All stats in a dictionary for easy lookup
    stat_values = {
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "gpm": gpm,
        "xpm": xpm,
        "networth": networth,
        "level": level,
        "hero_damage": hero_damage,
        "tower_damage": tower_damage,
        "hero_healing": hero_healing,
        "last_hits": last_hits,
        "denies": denies,
        "kills_per_min": kills_per_min,
        "deaths_per_min": deaths_per_min,
        "assists_per_min": assists_per_min,
        "hero_damage_per_min": hero_damage_per_min,
        "tower_damage_per_min": tower_damage_per_min,
        "healing_per_min": healing_per_min,
        "kda_ratio": kda_ratio,
        "ka_ratio": ka_ratio,
        "death_rate": death_rate,
        "farm_efficiency": farm_efficiency,
        "damage_efficiency": damage_efficiency,
        "duration_minutes": duration_minutes,
    }
    
    # ============================================
    # Step C: Calculate raw IMP score
    # ============================================
    
    # Start with intercept
    raw_imp = coefficients.get("intercept", 0.0)
    
    # Track contributions for transparency
    contributions: dict[str, float] = {}
    
    # Apply all coefficients (EXCEPT is_victory - handled separately)
    for stat_name, coefficient in coefficients.items():
        if stat_name in ("intercept", "is_victory"):
            continue
        
        if stat_name in stat_values:
            value = stat_values[stat_name]
            contribution = value * coefficient
            contributions[stat_name] = contribution
            raw_imp += contribution
    
    # ============================================
    # Step D: Apply Win/Loss Bonus (Override)
    # ============================================
    
    # The regression's is_victory coefficient is unreliable due to collinearity
    # We apply a manual bonus/penalty to ensure winners trend positive
    if is_winner:
        raw_imp += WIN_BONUS
    else:
        raw_imp += LOSS_PENALTY
    
    # ============================================
    # Step E: Clamp and finalize score
    # ============================================
    
    final_imp = _clamp(raw_imp, IMP_MIN, IMP_MAX)
    
    # ============================================
    # Step F: Build contributing factors list
    # ============================================
    
    # Sort by absolute contribution (most impactful first)
    sorted_contributions = sorted(
        contributions.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )
    
    contributing_factors: list[ContributingFactor] = []
    for stat_name, contribution in sorted_contributions[:8]:  # Top 8 factors
        if abs(contribution) < 0.01:
            continue
        
        display_name = STAT_DISPLAY_NAMES.get(stat_name, stat_name.replace("_", " ").title())
        value = stat_values.get(stat_name, 0)
        weight = coefficients.get(stat_name, 0)
        
        impact: Literal["positive", "neutral", "negative"]
        if contribution > 1:
            impact = "positive"
        elif contribution < -1:
            impact = "negative"
        else:
            impact = "neutral"
        
        contributing_factors.append(
            ContributingFactor(
                name=display_name,
                value=round(value, 2),
                impact=impact,
                weight=round(abs(weight), 4),
            )
        )
    
    # ============================================
    # Step G: Generate summary
    # ============================================
    
    grade = _get_grade(final_imp)
    percentile = _calculate_percentile_from_score(final_imp)
    role_desc = _get_role_description(position)
    
    # Generate context-aware summary
    if grade == "S":
        summary = f"Outstanding {role_desc} performance"
    elif grade == "A":
        summary = f"Excellent {role_desc} performance"
    elif grade == "B":
        summary = f"Good {role_desc} performance"
    elif grade == "C":
        summary = f"Average {role_desc} performance"
    elif grade == "D":
        summary = f"Below average {role_desc} performance"
    else:
        summary = f"Poor {role_desc} performance"
    
    # ============================================
    # Return response
    # ============================================
    
    return CalculateIMPResponse(
        success=True,
        data=IMPData(
            imp_score=round(final_imp, 1),
            grade=grade,
            percentile=percentile,
            contributing_factors=contributing_factors,
            summary=summary,
        ),
        meta=IMPMeta(
            engine_version=ENGINE_VERSION,
            calculated_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
