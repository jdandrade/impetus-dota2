"""
Request models for the IMP Engine API.
"""

from pydantic import BaseModel, Field


class MatchStats(BaseModel):
    """Core performance statistics from a match."""

    kills: int = Field(..., ge=0, description="Number of kills")
    deaths: int = Field(..., ge=0, description="Number of deaths")
    assists: int = Field(..., ge=0, description="Number of assists")
    last_hits: int = Field(..., ge=0, description="Last hits count")
    denies: int = Field(..., ge=0, description="Denies count")
    gpm: int = Field(..., ge=0, description="Gold per minute")
    xpm: int = Field(..., ge=0, description="Experience per minute")
    hero_damage: int = Field(..., ge=0, description="Total hero damage dealt")
    tower_damage: int = Field(..., ge=0, description="Total tower damage dealt")
    hero_healing: int = Field(..., ge=0, description="Total hero healing done")
    net_worth: int = Field(..., ge=0, description="Final net worth")
    level: int = Field(..., ge=1, le=30, description="Final hero level")


class MatchContext(BaseModel):
    """Game context for normalization."""

    team_result: str = Field(..., pattern="^(win|loss)$", description="Match result")
    game_mode: str = Field(..., description="Game mode (ranked, unranked, etc.)")
    avg_rank: int = Field(..., ge=0, le=100, description="Average match rank (0-100)")
    is_radiant: bool = Field(..., description="Whether player was on Radiant side")


class CalculateIMPRequest(BaseModel):
    """Request payload for IMP score calculation."""

    match_id: int = Field(..., description="Unique match identifier")
    player_slot: int = Field(..., ge=0, le=255, description="Player slot (0-4 Radiant, 128-132 Dire)")
    hero_id: int = Field(..., ge=1, description="Dota 2 hero ID")
    hero_name: str = Field(..., min_length=1, description="Hero display name")
    role: str = Field(
        ...,
        pattern="^(carry|mid|offlane|support|hard_support)$",
        description="Player role",
    )
    duration_seconds: int = Field(..., ge=0, description="Match duration in seconds")
    stats: MatchStats = Field(..., description="Core performance statistics")
    context: MatchContext = Field(..., description="Game context for normalization")
    benchmarks: dict[str, float] | None = Field(
        default=None,
        description="Optional benchmark percentiles (0.0-1.0) for each stat",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "match_id": 7890123456,
                "player_slot": 0,
                "hero_id": 74,
                "hero_name": "Invoker",
                "role": "mid",
                "duration_seconds": 2400,
                "stats": {
                    "kills": 12,
                    "deaths": 3,
                    "assists": 18,
                    "last_hits": 280,
                    "denies": 15,
                    "gpm": 620,
                    "xpm": 685,
                    "hero_damage": 32500,
                    "tower_damage": 4200,
                    "hero_healing": 0,
                    "net_worth": 24800,
                    "level": 25,
                },
                "context": {
                    "team_result": "win",
                    "game_mode": "ranked",
                    "avg_rank": 75,
                    "is_radiant": True,
                },
            }
        }
    }
