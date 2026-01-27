"""
Nerd of the Day Tracker.
Posts daily Nerd of the Day to Discord at 00:00 Portuguese time.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz

from app.bot import ProfessorBot
from app.config import TRACKED_PLAYERS, convert_steam_id64_to_account_id, Settings
from app.services.opendota import get_player_yesterday_stats, YesterdayStats
from app.services.gemini import GeminiClient

logger = logging.getLogger(__name__)


class NerdOfTheDayTracker:
    """Posts the Nerd of the Day to Discord at 00:00 Portuguese time."""
    
    # Portugal timezone (handles DST automatically)
    PORTUGAL_TZ = pytz.timezone("Europe/Lisbon")
    
    # Target time
    TARGET_HOUR = 0  # Midnight
    TARGET_MINUTE = 0
    
    def __init__(
        self,
        bot: ProfessorBot,
        gemini_client: GeminiClient,
        settings: Settings,
    ):
        """
        Initialize the Nerd of the Day tracker.
        
        Args:
            bot: Discord bot instance
            gemini_client: Gemini client for roast generation
            settings: Application settings
        """
        self.bot = bot
        self.gemini = gemini_client
        self.settings = settings
        self._running = False
    
    async def start(self) -> None:
        """Start the daily nerd posting loop."""
        self._running = True
        logger.info("Starting Nerd of the Day tracker (posting at 00:00 Portuguese time)...")
        
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, Nerd tracker initialized")
        
        while self._running and not self.bot.is_closed():
            try:
                # Wait until target time
                await self._wait_until_target_time()
                
                if not self._running:
                    break
                
                # Post Nerd of the Day
                await self._post_nerd_of_day()
                
                # Sleep for an hour to avoid double-posting
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("Nerd tracker cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in Nerd tracker loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(300)
    
    def stop(self) -> None:
        """Stop the daily nerd posting loop."""
        self._running = False
        logger.info("Stopping Nerd tracker...")
    
    async def _wait_until_target_time(self) -> None:
        """Sleep until midnight Portuguese time."""
        now = datetime.now(self.PORTUGAL_TZ)
        target = now.replace(
            hour=self.TARGET_HOUR,
            minute=self.TARGET_MINUTE,
            second=0,
            microsecond=0,
        )
        
        # If target time has passed today, wait until tomorrow
        if now >= target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Nerd tracker: Waiting {wait_seconds/3600:.1f} hours until {target.isoformat()}")
        
        await asyncio.sleep(wait_seconds)
    
    async def _post_nerd_of_day(self) -> None:
        """Fetch stats for all players and post the Nerd of the Day."""
        try:
            logger.info("Fetching yesterday's stats for all tracked players...")
            
            # Fetch stats for all tracked players
            player_stats: dict[str, tuple[str, YesterdayStats]] = {}
            
            for steam_id, fallback_name in TRACKED_PLAYERS.items():
                account_id = convert_steam_id64_to_account_id(steam_id)
                
                stats = await get_player_yesterday_stats(account_id, fallback_name)
                if stats and stats.games_played > 0:
                    player_stats[steam_id] = (fallback_name, stats)
                    logger.info(f"{fallback_name}: {stats.games_played} games, {stats.total_hours:.1f}h")
                
                # Rate limit between API calls
                await asyncio.sleep(2)
            
            if not player_stats:
                logger.info("No players played yesterday, skipping Nerd of the Day")
                return
            
            # Find the nerd (most games played)
            nerd_steam_id = max(
                player_stats.keys(),
                key=lambda sid: player_stats[sid][1].games_played
            )
            nerd_name, nerd_stats = player_stats[nerd_steam_id]
            
            logger.info(f"Nerd of the Day: {nerd_name} with {nerd_stats.games_played} games!")
            
            # Extract roast material from stats
            most_played_role = None
            most_played_role_games = 0
            most_played_role_wins = 0
            
            role_data = nerd_stats.get_most_played_role()
            if role_data:
                most_played_role, most_played_role_games, most_played_role_wins = role_data
            
            best_wr_role = None
            best_wr_role_games = 0
            best_wr_role_wins = 0
            
            best_role_data = nerd_stats.get_best_win_rate_role()
            if best_role_data:
                best_wr_role, best_wr_role_games, best_wr_role_wins = best_role_data
            
            most_spammed_hero = None
            most_spammed_games = 0
            most_spammed_wins = 0
            
            hero_data = nerd_stats.get_most_spammed_hero()
            if hero_data:
                most_spammed_hero, most_spammed_games, most_spammed_wins = hero_data
            
            # Get outlier games
            worst_game = nerd_stats.get_worst_game()
            best_game = nerd_stats.get_best_game()
            
            worst_game_hero = None
            worst_game_kda = None
            if worst_game:
                worst_game_hero = worst_game.hero_name
                worst_game_kda = f"{worst_game.kills}/{worst_game.deaths}/{worst_game.assists}"
            
            best_game_hero = None
            best_game_kda = None
            if best_game:
                best_game_hero = best_game.hero_name
                best_game_kda = f"{best_game.kills}/{best_game.deaths}/{best_game.assists}"
            
            # Generate roast
            roast = await self.gemini.generate_nerd_roast(
                player_name=nerd_name,
                games_played=nerd_stats.games_played,
                total_hours=nerd_stats.total_hours,
                wins=nerd_stats.wins,
                losses=nerd_stats.losses,
                win_rate=nerd_stats.win_rate,
                most_played_role=most_played_role,
                most_played_role_games=most_played_role_games,
                most_played_role_wins=most_played_role_wins,
                best_winrate_role=best_wr_role,
                best_winrate_role_games=best_wr_role_games,
                best_winrate_role_wins=best_wr_role_wins,
                most_spammed_hero=most_spammed_hero,
                most_spammed_hero_games=most_spammed_games,
                most_spammed_hero_wins=most_spammed_wins,
                worst_game_hero=worst_game_hero,
                worst_game_kda=worst_game_kda,
                best_game_hero=best_game_hero,
                best_game_kda=best_game_kda,
            )
            
            # Send to Discord
            await self.bot.send_nerd_of_day(
                player_name=nerd_name,
                steam_id=nerd_steam_id,
                games_played=nerd_stats.games_played,
                total_hours=nerd_stats.total_hours,
                wins=nerd_stats.wins,
                losses=nerd_stats.losses,
                roast=roast,
            )
            
            logger.info(f"Successfully posted Nerd of the Day: {nerd_name}")
            
        except Exception as e:
            logger.exception(f"Error posting Nerd of the Day: {e}")
    
    async def trigger_now(self) -> None:
        """
        Manually trigger a Nerd of the Day post (for testing).
        Bypasses the schedule and posts immediately.
        """
        logger.info("Manually triggered Nerd of the Day post")
        await self._post_nerd_of_day()
