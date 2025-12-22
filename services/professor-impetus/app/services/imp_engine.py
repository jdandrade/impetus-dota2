"""
Internal IMP Engine Client.
Calls our own scoring API instead of Stratz.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from app.services.opendota import MatchData

logger = logging.getLogger(__name__)


@dataclass
class IMPResult:
    """Result from IMP Engine API."""
    imp_score: float
    grade: str
    percentile: int
    summary: str


async def calculate_imp(match: MatchData, imp_engine_url: str) -> Optional[IMPResult]:
    """
    Calculate IMP score using our internal API.
    
    Args:
        match: Match data from OpenDota
        imp_engine_url: Base URL of the IMP Engine service
    
    Returns:
        IMPResult if successful, None otherwise
    """
    endpoint = f"{imp_engine_url}/api/v1/calculate-imp"
    
    # Determine role
    role = match.get_role()
    
    # Build request payload
    payload = {
        "match_id": match.match_id,
        "player_slot": match.player_slot,
        "hero_id": match.hero_id,
        "hero_name": match.hero_name,
        "role": role,
        "duration_seconds": match.duration_seconds,
        "stats": {
            "kills": match.kills,
            "deaths": match.deaths,
            "assists": match.assists,
            "last_hits": match.last_hits,
            "denies": match.denies,
            "gpm": match.gpm,
            "xpm": match.xpm,
            "hero_damage": match.hero_damage,
            "tower_damage": match.tower_damage,
            "hero_healing": match.hero_healing,
            "net_worth": match.net_worth,
            "level": match.level,
        },
        "context": {
            "team_result": "win" if match.is_victory else "loss",
            "game_mode": "ranked",
            "avg_rank": 75,
            "is_radiant": match.is_radiant,
        },
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"IMP Engine error {resp.status}: {text}")
                    return None
                
                data = await resp.json()
                
                if not data.get("success"):
                    logger.error(f"IMP Engine returned failure: {data}")
                    return None
                
                imp_data = data.get("data", {})
                
                return IMPResult(
                    imp_score=imp_data.get("imp_score", 0),
                    grade=imp_data.get("grade", "C"),
                    percentile=imp_data.get("percentile", 50),
                    summary=imp_data.get("summary", ""),
                )
                
        except Exception as e:
            logger.exception(f"Error calling IMP Engine: {e}")
            return None
