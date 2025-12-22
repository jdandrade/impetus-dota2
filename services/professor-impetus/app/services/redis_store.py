"""
Redis State Store.
Tracks processed matches to prevent duplicates.
"""

import logging
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisStore:
    """Redis-backed state store for match tracking."""
    
    def __init__(self, redis_url: str):
        """Initialize with Redis connection URL."""
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.exception(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            logger.info("Disconnected from Redis")
    
    async def get_last_match_id(self, steam_id: str) -> Optional[int]:
        """
        Get the last processed match ID for a player.
        
        Args:
            steam_id: Steam ID 64 of the player
        
        Returns:
            Last match ID or None if not found
        """
        if not self._client:
            return None
        
        try:
            key = f"player:{steam_id}:last_match"
            value = await self._client.get(key)
            return int(value) if value else None
        except Exception as e:
            logger.error(f"Error getting last match for {steam_id}: {e}")
            return None
    
    async def set_last_match_id(self, steam_id: str, match_id: int) -> bool:
        """
        Store the last processed match ID for a player.
        
        Args:
            steam_id: Steam ID 64 of the player
            match_id: Match ID to store
        
        Returns:
            True if successful
        """
        if not self._client:
            return False
        
        try:
            key = f"player:{steam_id}:last_match"
            # Set with 30-day TTL
            await self._client.set(key, str(match_id), ex=60 * 60 * 24 * 30)
            return True
        except Exception as e:
            logger.error(f"Error setting last match for {steam_id}: {e}")
            return False
    
    async def initialize_players(self, steam_ids: list[str]) -> None:
        """
        Initialize tracking for players (no-op if already tracked).
        
        Args:
            steam_ids: List of Steam ID 64s to initialize
        """
        for steam_id in steam_ids:
            exists = await self.get_last_match_id(steam_id)
            if exists is None:
                logger.info(f"Initialized tracking for player {steam_id}")
