"""
Match Tracker.
Main polling loop that detects new matches and triggers announcements.
"""

import asyncio
import logging

from app.config import TRACKED_PLAYERS, convert_steam_id64_to_account_id, Settings
from app.bot import ProfessorBot
from app.services.opendota import get_latest_match, request_match_parse, MatchData
from app.services.imp_engine import calculate_imp, IMPResult
from app.services.gemini import GeminiClient
from app.services.redis_store import RedisStore

logger = logging.getLogger(__name__)


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
    
    async def start(self) -> None:
        """Start the match tracking loop."""
        self._running = True
        logger.info("Starting match tracker...")
        
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, initializing player tracking...")
        
        # Initialize tracking state
        await self._initialize_players()
        
        # Start polling loop
        while self._running and not self.bot.is_closed():
            await self._poll_matches()
            await asyncio.sleep(self.settings.poll_interval_seconds)
    
    def stop(self) -> None:
        """Stop the match tracking loop."""
        self._running = False
        logger.info("Stopping match tracker...")
    
    async def _initialize_players(self) -> None:
        """
        Initialize tracking by fetching current matches for all players.
        On FIRST RUN: Announces current match for each player (for testing).
        On subsequent runs: Silently initializes without announcing.
        """
        for steam_id, fallback_name in TRACKED_PLAYERS.items():
            account_id = convert_steam_id64_to_account_id(steam_id)
            
            # Check if already initialized in Redis
            last_match = await self.redis.get_last_match_id(steam_id)
            if last_match:
                logger.info(f"Player {fallback_name} already tracked (last match: {last_match})")
                continue
            
            # First run - fetch and ANNOUNCE current match
            match = await get_latest_match(account_id)
            if match:
                logger.info(f"🆕 First run: Announcing current match for {fallback_name} ({match.match_id})")
                
                # Request parse for better data quality (fire and forget)
                asyncio.create_task(request_match_parse(match.match_id))
                
                # Calculate IMP score
                imp_result = await calculate_imp(match, self.settings.imp_engine_url)
                if not imp_result:
                    logger.error(f"Failed to get IMP score for {fallback_name}")
                    imp_result = IMPResult(
                        imp_score=0.0,
                        grade="C",
                        percentile=50,
                        summary="Score unavailable",
                    )
                
                # Generate roast
                player_name = match.player_name or fallback_name
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
                
                # Store as processed
                await self.redis.set_last_match_id(steam_id, match.match_id)
                logger.info(f"✅ Announced and initialized {fallback_name} with match {match.match_id}")
            else:
                logger.warning(f"Could not initialize {fallback_name} (no match data)")
            
            # Rate limit OpenDota calls (2 seconds for safety)
            await asyncio.sleep(2)
    
    async def _poll_matches(self) -> None:
        """Poll for new matches across all tracked players."""
        for steam_id, fallback_name in TRACKED_PLAYERS.items():
            try:
                await self._check_player(steam_id, fallback_name)
                # Rate limit between players
                await asyncio.sleep(1)
            except Exception as e:
                logger.exception(f"Error checking {fallback_name}: {e}")
    
    async def _check_player(self, steam_id: str, fallback_name: str) -> None:
        """
        Check a single player for new matches.
        
        Args:
            steam_id: Steam ID 64
            fallback_name: Display name to use if API fails
        """
        account_id = convert_steam_id64_to_account_id(steam_id)
        
        # Fetch latest match from OpenDota
        match = await get_latest_match(account_id)
        if not match:
            return
        
        # Check if this is a new match
        last_match = await self.redis.get_last_match_id(steam_id)
        if last_match and match.match_id == last_match:
            return  # Already processed
        
        logger.info(f"New match detected for {match.player_name or fallback_name}: {match.match_id}")
        
        # Request parse for better data quality (fire and forget)
        asyncio.create_task(request_match_parse(match.match_id))
        
        # Immediately mark as processed to prevent duplicates
        await self.redis.set_last_match_id(steam_id, match.match_id)
        
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
        
        # Generate roast
        player_name = match.player_name or fallback_name
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
