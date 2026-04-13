"""
Redis state management for WoW Mythic+ tracker.

Tracks last announced run per character and prevents duplicate
group run announcements.
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

    async def get_last_run_id(self, char_key: str) -> Optional[int]:
        """Get the last announced run ID for a character."""
        val = await self.redis.get(f"wow:player:{char_key}:last_run_id")
        if val is not None:
            return int(val)
        return None

    async def set_last_run_id(self, char_key: str, run_id: int):
        """Store the last announced run ID for a character."""
        await self.redis.set(
            f"wow:player:{char_key}:last_run_id",
            str(run_id),
            ex=KEY_TTL,
        )

    async def is_run_announced(self, run_id: int) -> bool:
        """Check if a run has already been announced (group dedup)."""
        val = await self.redis.get(f"wow:run:{run_id}:announced")
        return val is not None

    async def mark_run_announced(self, run_id: int):
        """Mark a run as announced to prevent duplicate group posts."""
        await self.redis.set(
            f"wow:run:{run_id}:announced",
            "1",
            ex=KEY_TTL,
        )
