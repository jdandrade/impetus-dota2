"""
Match Tracker.
Main polling loop that detects new matches and triggers announcements.
"""

import asyncio
import logging
import time
from typing import Optional

from app.config import TRACKED_PLAYERS, convert_steam_id64_to_account_id, Settings, get_poll_interval
from app.bot import ProfessorBot
from app.services.opendota import (
    get_latest_match_with_fallback,
    get_match_data,
    request_match_parse,
    MatchData,
)
from app.services import steam_api
from app.services.smurf import SmurfReport, check_enemies
from app.services.imp_engine import calculate_imp, IMPResult
from app.services.gemini import GeminiClient
from app.services.redis_store import RedisStore

logger = logging.getLogger(__name__)

# Matches that ended longer ago than this are recorded but not announced
MAX_ANNOUNCE_AGE_SECONDS = 24 * 60 * 60
# How many polls to wait for the details of a detected match before giving up
MAX_DETAIL_ATTEMPTS = 30
# Fast track (match end reported live): how long to wait for match details
FAST_TRACK_ATTEMPTS = 20
FAST_TRACK_RETRY_SECONDS = 15


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
        # When each player was last checked through OpenDota (monotonic)
        self._last_opendota_poll: dict[str, float] = {}
        # Failed detail fetches per detected match ID
        self._detail_attempts: dict[int, int] = {}
        # Smurf check results per (match ID, side)
        self._smurf_reports: dict[tuple, SmurfReport] = {}
    
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
        
        # Read dedup state first: it lets us skip the expensive match
        # details call when nothing is new. If Redis is down, do nothing.
        try:
            seen = await self.redis.get_seen_match_ids(steam_id)
        except Exception as e:
            logger.error(f"Redis unavailable while checking {fallback_name}, skipping: {e}")
            return
        
        match = await self._fetch_new_match(steam_id, account_id, fallback_name, seen)
        if not match:
            return
        
        if not await self._should_announce(steam_id, fallback_name, match):
            return
        
        logger.info(f"New match detected for {match.player_name or fallback_name}: {match.match_id}")
        
        await self._announce(fallback_name, match)
    
    async def _announce(self, fallback_name: str, match: MatchData) -> None:
        """Score a match, generate the roast and post the report card."""
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
        
        smurfs = await self._smurf_report(match)
        
        # Generate roast - use group nickname for proper recognition
        player_name = fallback_name
        roast = await self.gemini.generate_roast(
            player_name=player_name,
            match=match,
            imp_result=imp_result,
            smurf_note=smurfs.prompt_note() if smurfs else None,
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
            smurf_line=smurfs.embed_line() if smurfs else None,
        )
    
    async def _smurf_report(self, match: MatchData) -> Optional[SmurfReport]:
        """
        Smurf check of the enemy team, or None if disabled or unavailable.
        Cached per match and side so friends on the same team share it.
        Never raises: the report card must go out regardless.
        """
        if not self.settings.smurf_check_enabled:
            return None
        
        key = (match.match_id, match.is_radiant)
        if key in self._smurf_reports:
            return self._smurf_reports[key]
        
        try:
            report = await check_enemies(match, self.settings.smurf_max_games)
        except Exception as e:
            logger.exception(f"Smurf check failed for match {match.match_id}: {e}")
            return None
        
        if report is not None:
            if len(self._smurf_reports) > 50:
                self._smurf_reports.clear()
            self._smurf_reports[key] = report
            if report.suspects:
                logger.info(
                    f"Smurf check, match {match.match_id}: "
                    + ", ".join(f"{s.hero_name} ({s.games} games)" for s in report.suspects)
                )
        return report
    
    async def process_finished_match(self, match_id: int, steam_id: str) -> bool:
        """
        Fast track for a match we KNOW just ended (reported live by a
        player's game client): wait for its details to become available and
        post the report card for that player and for every other tracked
        player in the same match.
        
        Uses the same dedup claims as the poller, so whichever gets to a
        match first announces it and the other skips it.
        
        Args:
            match_id: The finished match
            steam_id: Steam ID 64 of the player whose client reported it
        
        Returns:
            True if the reporting player's match was resolved (announced now
            or already handled), False if details never became available.
        """
        accounts = {
            convert_steam_id64_to_account_id(sid): (sid, name)
            for sid, name in TRACKED_PLAYERS.items()
        }
        reporter_account = convert_steam_id64_to_account_id(steam_id)
        reporter_name = TRACKED_PLAYERS.get(steam_id, "Unknown")
        api_key = self.settings.steam_api_key
        
        found: dict[int, MatchData] = {}
        for attempt in range(FAST_TRACK_ATTEMPTS):
            if attempt:
                await asyncio.sleep(FAST_TRACK_RETRY_SECONDS)
            
            if api_key:
                found = await steam_api.get_match_players(
                    api_key, match_id, {acc: name for acc, (_, name) in accounts.items()}
                )
            if reporter_account not in found:
                match = await get_match_data(match_id, reporter_account, reporter_name)
                if match:
                    found[reporter_account] = match
            if reporter_account in found:
                break
        else:
            logger.warning(
                f"Fast track: no details for match {match_id} after "
                f"{FAST_TRACK_ATTEMPTS} attempts, leaving it to the poller"
            )
            return False
        
        for account_id, match in found.items():
            sid, name = accounts[account_id]
            if await self._should_announce(sid, name, match):
                logger.info(f"Fast track: announcing match {match_id} for {name}")
                await self._announce(name, match)
        
        return True
    
    async def _fetch_new_match(
        self,
        steam_id: str,
        account_id: int,
        fallback_name: str,
        seen: set[int],
    ) -> Optional[MatchData]:
        """
        Return the player's latest match if it looks new, else None.
        
        With a Steam API key: Steam detects the match ID (cheap, polled
        often); details come from Steam, falling back to OpenDota.
        Without a key, or when Steam cannot answer for this player: the
        OpenDota -> Stratz path, at most once per OpenDota poll interval.
        """
        api_key = self.settings.steam_api_key
        
        if api_key:
            latest_id = await steam_api.get_latest_match_id(api_key, account_id)
            
            if latest_id is not None:
                if not await self._is_candidate(steam_id, fallback_name, latest_id, seen):
                    return None
                
                match = await steam_api.get_match_data(api_key, latest_id, account_id, fallback_name)
                if not match:
                    match = await get_match_data(latest_id, account_id, fallback_name)
                if not match:
                    await self._note_missing_details(steam_id, fallback_name, latest_id)
                return match
            
            # Steam could not answer. OpenDota cannot be polled at the Steam
            # cadence, so only fall back once per OpenDota poll interval.
            last = self._last_opendota_poll.get(steam_id, 0.0)
            if time.monotonic() - last < self.settings.poll_interval_seconds:
                return None
        
        self._last_opendota_poll[steam_id] = time.monotonic()
        return await get_latest_match_with_fallback(account_id, fallback_name, seen)
    
    async def _note_missing_details(self, steam_id: str, fallback_name: str, match_id: int) -> None:
        """
        Count a failed details fetch for a detected match. After
        MAX_DETAIL_ATTEMPTS, record the match as seen and give up, so an
        unresolvable match cannot burn API calls on every poll forever.
        """
        attempts = self._detail_attempts.get(match_id, 0) + 1
        self._detail_attempts[match_id] = attempts
        
        if attempts < MAX_DETAIL_ATTEMPTS:
            if attempts == 1:
                logger.warning(
                    f"Match {match_id} detected for {fallback_name} but details "
                    f"are not available yet, retrying on next polls"
                )
            return
        
        try:
            await self.redis.claim_match(steam_id, match_id)
        except Exception as e:
            logger.error(f"Redis unavailable while giving up on match {match_id}: {e}")
            return
        self._detail_attempts.pop(match_id, None)
        logger.error(
            f"Giving up on match {match_id} for {fallback_name}: no details "
            f"after {attempts} attempts (not announced)"
        )
    
    async def _is_candidate(
        self,
        steam_id: str,
        fallback_name: str,
        match_id: int,
        seen: set[int],
    ) -> bool:
        """
        Cheap pre-check on a match ID, before fetching match details.
        Seeds a player with no stored state silently.
        """
        if match_id in seen or match_id in self._announced.get(steam_id, set()):
            return False
        
        if not seen:
            try:
                await self.redis.claim_match(steam_id, match_id)
            except Exception as e:
                logger.error(f"Redis unavailable while seeding {fallback_name}: {e}")
                return False
            self._announced.setdefault(steam_id, set()).add(match_id)
            logger.info(f"No stored state for {fallback_name}, seeding with match {match_id} (not announced)")
            return False
        
        # Older than something already seen: a stale API response
        return match_id > max(seen)
    
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
