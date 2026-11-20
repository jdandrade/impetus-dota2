"""
Match Tracker.
Main polling loop that detects new matches and triggers announcements.
"""

import asyncio
import logging
import time

from app.config import TRACKED_PLAYERS, convert_steam_id64_to_account_id, Settings, get_poll_interval
from app.bot import ProfessorBot
from app.services.opendota import get_latest_match_with_fallback, request_match_parse, MatchData
from app.services.imp_engine import calculate_imp, IMPResult
from app.services.gemini import GeminiClient
from app.services.redis_store import RedisStore

logger = logging.getLogger(__name__)

# Matches that ended longer ago than this are recorded but not announced
MAX_ANNOUNCE_AGE_SECONDS = 24 * 60 * 60


class MatchTracker:
    """
    Tracks matches for configured players and sends announcements.
    """
    
    def __init__(
        self,
        bot: ProfessorBot,
        redis_store: RedisStore,
        gemini_client: GeminiClient,
        settings: Settings,
    ):
        self.bot = bot
        self.redis = redis_store
        self.gemini = gemini_client
        self.settings = settings
        self._running = False
        # Match IDs handled by this process, per player. Second line of
        # defence so one process can never post the same match twice.
        self._announced: dict[str, set[int]] = {}
    
    async def start(self) -> None:
        """Start the match tracking loop."""
        self._running = True
        logger.info("Starting match tracker...")
        
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, starting match polling...")
        
        # Start polling loop - staggered polling across interval means no extra sleep needed
        while self._running and not self.bot.is_closed():
            await self._poll_matches()
    
    def stop(self) -> None:
        """Stop the match tracking loop."""
        self._running = False
        logger.info("Stopping match tracker...")
    
    async def _poll_matches(self) -> None:
        """
        Poll for new matches across all tracked players.
        
        Players are staggered across the polling interval to avoid burst requests
        that could trigger OpenDota's rate limiting.
        """
        players = list(TRACKED_PLAYERS.items())
        num_players = len(players)
        
        if num_players == 0:
            return
        
        # Calculate delay between players to spread across the polling interval
        # e.g., 600s interval / 6 players = 100s between each player
        poll_interval = get_poll_interval(self.settings)
        delay_between_players = poll_interval / num_players
        
        for i, (steam_id, fallback_name) in enumerate(players):
            try:
                await self._check_player(steam_id, fallback_name)
            except Exception as e:
                logger.exception(f"Error checking {fallback_name}: {e}")
            
            # Wait before checking next player (except for last player)
            if i < num_players - 1:
                await asyncio.sleep(delay_between_players)
    
    async def _check_player(self, steam_id: str, fallback_name: str) -> None:
        """
        Check a single player for new matches.
        
        Args:
            steam_id: Steam ID 64
            fallback_name: Display name to use if API fails
        """
        account_id = convert_steam_id64_to_account_id(steam_id)
        
        # Fetch latest match from OpenDota
        match = await get_latest_match_with_fallback(account_id, fallback_name)
        if not match:
            return
        
        if not await self._should_announce(steam_id, fallback_name, match):
            return
        
        logger.info(f"New match detected for {match.player_name or fallback_name}: {match.match_id}")
        
        # Request parse for better data quality (fire and forget)
        asyncio.create_task(request_match_parse(match.match_id))
        
        # Calculate IMP score using our internal API
        imp_result = await calculate_imp(match, self.settings.imp_engine_url)
        if not imp_result:
            logger.error(f"Failed to get IMP score for match {match.match_id}")
            # Still announce with a fallback score
            imp_result = IMPResult(
                imp_score=0.0,
                grade="C",
                percentile=50,
                summary="Score unavailable",
            )
        
        # Generate roast - use group nickname for proper recognition
        player_name = fallback_name
        roast = await self.gemini.generate_roast(
            player_name=player_name,
            match=match,
            imp_result=imp_result,
        )
        
        # Send Discord announcement
        await self.bot.send_match_announcement(
            player_name=player_name,
            match_id=match.match_id,
            hero_name=match.hero_name,
            is_victory=match.is_victory,
            kda=match.kda_string,
            duration=match.duration_string,
            imp_score=imp_result.imp_score,
            grade=imp_result.grade,
            roast=roast,
        )
    
    async def _should_announce(self, steam_id: str, fallback_name: str, match: MatchData) -> bool:
        """
        Decide whether a fetched match is new and claim it if so.
        
        A match is announced only when ALL of these hold:
        - this process has not announced it already (in-memory guard)
        - Redis state could be read (on any Redis error we skip, never repost)
        - it is not among the player's recently seen match IDs
        - it is newer than every seen match (the APIs sometimes return an
          older game as "latest", e.g. when OpenDota and Stratz disagree)
        - it is recent enough to be worth announcing
        - we won the atomic claim in Redis
        
        A player with no stored state is seeded silently.
        """
        match_id = match.match_id
        if not match_id:
            return False
        
        local_seen = self._announced.setdefault(steam_id, set())
        if match_id in local_seen:
            return False
        
        try:
            seen = await self.redis.get_seen_match_ids(steam_id)
            
            if match_id in seen:
                return False
            
            is_stale = bool(seen) and match_id < max(seen)
            claimed = await self.redis.claim_match(steam_id, match_id)
        except Exception as e:
            logger.error(
                f"Redis unavailable while checking {fallback_name} "
                f"(match {match_id}), skipping announcement: {e}"
            )
            return False
        
        if not claimed:
            return False
        
        local_seen.add(match_id)
        
        if not seen:
            logger.info(f"No stored state for {fallback_name}, seeding with match {match_id} (not announced)")
            return False
        
        if is_stale:
            logger.warning(
                f"Ignoring match {match_id} for {fallback_name}: older than "
                f"already seen match {max(seen)} (stale API response)"
            )
            return False
        
        if match.start_time:
            age = time.time() - (match.start_time + match.duration_seconds)
            if age > MAX_ANNOUNCE_AGE_SECONDS:
                logger.warning(
                    f"Ignoring match {match_id} for {fallback_name}: "
                    f"ended {age / 3600:.1f}h ago"
                )
                return False
        
        return True
