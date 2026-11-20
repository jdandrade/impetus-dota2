"""
Redis State Store.
Tracks processed matches and posted videos to prevent duplicates.
"""

import hashlib
import json
import logging
import secrets
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Key for stored posted videos set
POSTED_VIDEOS_KEY = "youtube:posted_videos"
# TTL for posted videos (30 days)
VIDEO_TTL_SECONDS = 60 * 60 * 24 * 30
# How many recent match IDs to remember per player
SEEN_MATCHES_KEPT = 20


class RedisStore:
    """Redis-backed state store for match and video tracking."""
    
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
    
    # Match deduplication
    #
    # Each player has a sorted set of the last SEEN_MATCHES_KEPT match IDs
    # (score = match ID). Unlike the YouTube helpers below, these methods
    # RAISE on Redis failure: the caller must skip the announcement rather
    # than treat "could not read state" as "never seen" and repost.

    @staticmethod
    def _seen_key(steam_id: str) -> str:
        return f"player:{steam_id}:seen_matches"

    def _require_client(self) -> redis.Redis:
        if not self._client:
            raise RuntimeError("Redis client is not connected")
        return self._client

    async def get_seen_match_ids(self, steam_id: str) -> set[int]:
        """
        Get the recently seen match IDs for a player.

        Seeds the set from the legacy single-value `last_match` key the
        first time it is read, so upgrading does not re-announce anything.

        Raises:
            Exception: if Redis is unavailable.
        """
        client = self._require_client()
        key = self._seen_key(steam_id)

        members = await client.zrange(key, 0, -1)
        if members:
            return {int(m) for m in members}

        legacy = await client.get(f"player:{steam_id}:last_match")
        if legacy:
            await client.zadd(key, {str(int(legacy)): int(legacy)})
            logger.info(f"Migrated legacy last match {legacy} for {steam_id}")
            return {int(legacy)}

        return set()

    async def claim_match(self, steam_id: str, match_id: int) -> bool:
        """
        Atomically record a match as seen for a player.

        Returns:
            True if the match was not recorded before (caller owns the
            announcement), False if it was already there.

        Raises:
            Exception: if Redis is unavailable.
        """
        client = self._require_client()
        key = self._seen_key(steam_id)

        added = await client.zadd(key, {str(match_id): match_id}, nx=True)
        # Keep only the newest SEEN_MATCHES_KEPT IDs. No TTL: an expiring key
        # makes an inactive player's old match look new again.
        await client.zremrangebyrank(key, 0, -(SEEN_MATCHES_KEPT + 1))
        return bool(added)

    # GSI (live game tracking)
    #
    # Only a SHA-256 of each token is stored, so reading Redis does not
    # reveal usable tokens. These raise on Redis failure, like the match
    # methods above.

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def create_gsi_token(self, steam_id: str) -> str:
        """Create a GSI token for a player, revoking their previous one."""
        client = self._require_client()
        player_key = f"gsi:player:{steam_id}:token_hash"

        old_hash = await client.get(player_key)
        if old_hash:
            await client.delete(f"gsi:token:{old_hash}")

        token = secrets.token_urlsafe(24)
        token_hash = self._token_hash(token)
        await client.set(f"gsi:token:{token_hash}", steam_id)
        await client.set(player_key, token_hash)
        return token

    async def get_gsi_player(self, token: str) -> Optional[str]:
        """Return the Steam ID 64 a GSI token belongs to, or None."""
        client = self._require_client()
        return await client.get(f"gsi:token:{self._token_hash(token)}")

    async def get_json(self, key: str) -> Optional[dict]:
        """Read a JSON object, or None if the key does not exist."""
        client = self._require_client()
        raw = await client.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        """Store a JSON object with a TTL."""
        client = self._require_client()
        await client.set(key, json.dumps(value), ex=ttl_seconds)

    async def claim_once(self, key: str, ttl_seconds: Optional[int] = 60 * 60 * 24) -> bool:
        """
        Atomically claim a one-off event. True only for the first caller.
        Pass ttl_seconds=None for a claim that never expires.
        """
        client = self._require_client()
        return bool(await client.set(key, "1", nx=True, ex=ttl_seconds))

    async def release_claim(self, key: str) -> None:
        """Undo claim_once, so the event can be claimed again."""
        client = self._require_client()
        await client.delete(key)

    # YouTube video deduplication methods
    
    async def has_video_been_posted(self, video_id: str) -> bool:
        """
        Check if a YouTube video has already been posted.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if video was already posted
        """
        if not self._client:
            return False
        
        try:
            return await self._client.sismember(POSTED_VIDEOS_KEY, video_id)
        except Exception as e:
            logger.error(f"Error checking if video {video_id} was posted: {e}")
            return False
    
    async def mark_video_as_posted(self, video_id: str) -> bool:
        """
        Mark a YouTube video as posted.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if successful
        """
        if not self._client:
            return False
        
        try:
            await self._client.sadd(POSTED_VIDEOS_KEY, video_id)
            # Refresh TTL on the set
            await self._client.expire(POSTED_VIDEOS_KEY, VIDEO_TTL_SECONDS)
            logger.debug(f"Marked video {video_id} as posted")
            return True
        except Exception as e:
            logger.error(f"Error marking video {video_id} as posted: {e}")
            return False
    
    async def filter_unposted_videos(self, video_ids: list[str]) -> list[str]:
        """
        Filter out videos that have already been posted.
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            List of video IDs that haven't been posted
        """
        if not self._client or not video_ids:
            return video_ids
        
        try:
            unposted = []
            for video_id in video_ids:
                if not await self.has_video_been_posted(video_id):
                    unposted.append(video_id)
            return unposted
        except Exception as e:
            logger.error(f"Error filtering unposted videos: {e}")
            return video_ids

