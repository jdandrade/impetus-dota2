"""
Redis state management for AoE2 match tracker.

Tracks last announced match per player and prevents duplicate
group match announcements.
"""

import logging
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# TTL for all keys: 30 days
KEY_TTL = 30 * 24 * 60 * 60


class RedisStore:
    """Redis-backed state store for deduplication."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def get_last_match_id(self, player_key: str) -> Optional[int]:
        """Get the last announced match ID for a player."""
        val = await self.redis.get(f"aoe2:player:{player_key}:last_match_id")
        if val is not None:
            return int(val)
        return None

    async def set_last_match_id(self, player_key: str, match_id: int):
        """Store the last announced match ID for a player."""
        await self.redis.set(
            f"aoe2:player:{player_key}:last_match_id",
            str(match_id),
            ex=KEY_TTL,
        )

    async def is_match_announced(self, match_id: int) -> bool:
        """Check if a match has already been announced (group dedup)."""
        val = await self.redis.get(f"aoe2:match:{match_id}:announced")
        return val is not None

    async def mark_match_announced(self, match_id: int):
        """Mark a match as announced to prevent duplicate group posts."""
        await self.redis.set(
            f"aoe2:match:{match_id}:announced",
            "1",
            ex=KEY_TTL,
        )
