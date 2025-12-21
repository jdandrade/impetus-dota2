"""
IMP Scoring Algorithm v4 - Stratz Replica (Regression-Calibrated)

This module implements the IMP scoring formula reverse-engineered from Stratz
using Ridge Regression on 140 player samples.

Phase 14: Automated Calibration
- Coefficients derived from Ridge Regression analysis
- Formula: IMP = Intercept + Σ(stat * coefficient)
- Separate models for Core and Support players
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
ENGINE_VERSION = "0.5.0-stratz-calibrated"

# ============================================
# REGRESSION COEFFICIENTS (from Ridge Regression)
# Trained on 140 player samples from Stratz
# R² = 0.63 (Core), 0.72 (Support)
# ============================================

# These are the RAW coefficients from the ESTIMATED FORMULA output
# They can be applied directly to raw stat values

# Global scale factor to match Stratz score range
# Our raw scores are ~2x higher than Stratz, so we compress by 0.5
GLOBAL_SCALE = 0.5

# Win/Loss bonus (applied before scaling)
WIN_BONUS = 8.0
LOSS_PENALTY = -30.0  # Strong penalty to push losers negative

CORE_COEFFICIENTS = {
    # Intercept (baseline score)
    "intercept": -5.79,
    
    # Negative impacts (penalties)
    "deaths": -3.36,           # BIGGEST negative factor
    "tower_damage_per_min": -0.05,  # Slight negative (controls for duration)
    "xpm": -0.008,             # Small negative?
    "hero_damage_per_min": -0.03,
    
    # Positive impacts (boosts)
    "tower_damage": 0.0015,    # Raw tower damage
    "kills_per_min": 32.31,    # High kills/min is good
    "assists": 1.02,           # Assists help
    "gpm": 0.017,              # Farm matters
    "networth": 0.0005,        # Rich = good
    "kills": 0.50,             # Kills help a bit
    "level": 0.20,             # Higher level = good
}

SUPPORT_COEFFICIENTS = {
    # Intercept (baseline score)
    "intercept": -2.41,
    
    # Negative impacts (penalties)
    "deaths": -3.01,           # Deaths hurt supports too
    "xpm": -0.008,
    "is_victory": -9.13,       # Adjusted later
    "hero_damage": -0.00003,   # Hero damage slightly negative for supports
    
    # Positive impacts (boosts)
    "assists": 1.06,           # Assists are KEY for supports
    "tower_damage": 0.005,     # Tower damage helps
    "kills_per_min": 44.42,    # Kills/min helps
    "level": 0.84,             # Level matters
    "assists_per_min": 18.49,  # High assist rate is great
    "kills": 0.30,
    "gpm": 0.010,
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
    "assists_per_min": "Assists/min",
    "tower_damage": "Tower Damage",
    "tower_damage_per_min": "Tower Dmg/min",
    "hero_damage": "Hero Damage",
    "hero_damage_per_min": "Hero Dmg/min",
    "networth": "Net Worth",
    "level": "Level",
    "hero_healing": "Healing",
    "is_victory": "Win/Loss",
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


def _is_core_role(role: str) -> bool:
    """Check if role is a core (carry, mid, offlane)."""
    return role in ["carry", "mid", "offlane"]


def _is_support_role(role: str) -> bool:
    """Check if role is a support."""
    return role in ["support", "hard_support"]


def calculate_imp_score(request: CalculateIMPRequest) -> CalculateIMPResponse:
    """
    Calculate IMP score using the Stratz-calibrated regression model.
    
    Formula: IMP = Intercept + Σ(stat * coefficient)
    
    Uses separate coefficient sets for Core vs Support players.
    """
    
    stats = request.stats
    role = request.role
    is_winner = request.context.team_result == "win"
    duration_minutes = request.duration_seconds / 60.0
    
    # Get the appropriate coefficient set
    is_core = _is_core_role(role)
    coefficients = CORE_COEFFICIENTS if is_core else SUPPORT_COEFFICIENTS
    
    # ============================================
    # Step 1: Prepare stat values
    # ============================================
    
    # Calculate per-minute stats
    safe_duration = max(duration_minutes, 1.0)
    kills_per_min = stats.kills / safe_duration
    assists_per_min = stats.assists / safe_duration
    tower_damage_per_min = stats.tower_damage / safe_duration
    hero_damage_per_min = stats.hero_damage / safe_duration
    
    # ============================================
    # Step 2: Calculate raw IMP score
    # ============================================
    
    contributing_factors: list[ContributingFactor] = []
    raw_imp = coefficients.get("intercept", 0.0)
    
    # Track contributions for transparency
    contributions = {}
    
    if is_core:
        # Core formula
        contributions["deaths"] = stats.deaths * coefficients["deaths"]
        contributions["tower_damage"] = stats.tower_damage * coefficients["tower_damage"]
        contributions["kills_per_min"] = kills_per_min * coefficients["kills_per_min"]
        contributions["assists"] = stats.assists * coefficients["assists"]
        contributions["gpm"] = stats.gpm * coefficients["gpm"]
        contributions["networth"] = stats.net_worth * coefficients.get("networth", 0)
        contributions["level"] = stats.level * coefficients.get("level", 0)
        
        # Optional: XPM penalty
        if "xpm" in coefficients:
            contributions["xpm"] = stats.xpm * coefficients["xpm"]
    else:
        # Support formula
        contributions["deaths"] = stats.deaths * coefficients["deaths"]
        contributions["assists"] = stats.assists * coefficients["assists"]
        contributions["tower_damage"] = stats.tower_damage * coefficients["tower_damage"]
        contributions["kills_per_min"] = kills_per_min * coefficients["kills_per_min"]
        contributions["assists_per_min"] = assists_per_min * coefficients.get("assists_per_min", 0)
        contributions["level"] = stats.level * coefficients.get("level", 0)
        contributions["gpm"] = stats.gpm * coefficients.get("gpm", 0)
    
    # Sum all contributions
    for stat_name, contribution in contributions.items():
        raw_imp += contribution
        
        # Create contributing factor for API response
        if contribution != 0:
            impact = "positive" if contribution > 0 else "negative" if contribution < 0 else "neutral"
            weight = abs(coefficients.get(stat_name, 1.0))
            
            # Get the original stat value
            if stat_name == "deaths":
                stat_value = stats.deaths
            elif stat_name == "kills":
                stat_value = stats.kills
            elif stat_name == "assists":
                stat_value = stats.assists
            elif stat_name == "gpm":
                stat_value = stats.gpm
            elif stat_name == "xpm":
                stat_value = stats.xpm
            elif stat_name == "kills_per_min":
                stat_value = round(kills_per_min, 2)
            elif stat_name == "assists_per_min":
                stat_value = round(assists_per_min, 2)
            elif stat_name == "tower_damage":
                stat_value = stats.tower_damage
            elif stat_name == "networth":
                stat_value = stats.net_worth
            elif stat_name == "level":
                stat_value = stats.level
            else:
                stat_value = 0
            
            contributing_factors.append(
                ContributingFactor(
                    name=STAT_DISPLAY_NAMES.get(stat_name, stat_name),
                    value=stat_value,
                    impact=impact,
                    weight=min(weight, 7.0),  # Cap for validation
                )
            )
    
    # ============================================
    # Step 3: Apply Win/Loss adjustment
    # ============================================
    
    # Apply win/loss bonus before scaling
    if is_winner:
        raw_imp += WIN_BONUS
    else:
        raw_imp += LOSS_PENALTY
    
    contributing_factors.append(
        ContributingFactor(
            name="Win/Loss",
            value=1 if is_winner else 0,
            impact="positive" if is_winner else "negative",
            weight=abs(WIN_BONUS),
        )
    )
    
    # ============================================
    # Step 4: Apply global scale and clamp
    # ============================================
    
    # Scale to match Stratz score range
    raw_imp = raw_imp * GLOBAL_SCALE
    
    imp_score = _clamp(raw_imp, IMP_MIN, IMP_MAX)
    imp_score = round(imp_score, 1)
    
    grade = _get_grade(imp_score)
    percentile = _calculate_percentile_from_score(imp_score)
    
    # ============================================
    # Step 5: Generate Summary
    # ============================================
    
    if imp_score >= 40:
        quality = "MVP"
    elif imp_score >= 20:
        quality = "excellent"
    elif imp_score >= 5:
        quality = "solid"
    elif imp_score >= -5:
        quality = "average"
    elif imp_score >= -20:
        quality = "below average"
    else:
        quality = "poor"
    
    role_display = role.replace("_", " ").title()
    summary = f"{quality.title()} {role_display} performance"
    
    # Sort factors by absolute contribution
    contributing_factors.sort(
        key=lambda f: abs(f.weight * f.value) if f.name != "Win/Loss" else 0,
        reverse=True
    )
    
    # ============================================
    # Build Response
    # ============================================
    
    return CalculateIMPResponse(
        success=True,
        data=IMPData(
            imp_score=imp_score,
            grade=grade,
            percentile=percentile,
            summary=summary,
            contributing_factors=contributing_factors[:8],  # Top 8 factors
        ),
        meta=IMPMeta(
            engine_version=ENGINE_VERSION,
            calculated_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
