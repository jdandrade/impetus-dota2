"""
Professor Impetus - Entry Point

Discord bot that tracks Dota 2 matches and generates roast messages
using the internal Impetus scoring engine.
"""

import asyncio
import logging
import sys

from app.config import get_settings, TRACKED_PLAYERS
from app.bot import ProfessorBot
from app.tracker import MatchTracker
from app.youtube_tracker import YouTubeTracker
from app.nerd_tracker import NerdOfTheDayTracker
from app.services.redis_store import RedisStore
from app.services.gemini import GeminiClient
from app.services.youtube import YouTubeClient
from app.services.email_notifier import create_email_notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("🎓 Professor Impetus Discord Bot")
    logger.info("=" * 60)
    
    # Load settings
    try:
        settings = get_settings()
        logger.info(f"IMP Engine URL: {settings.imp_engine_url}")
        logger.info(f"Frontend URL: {settings.frontend_url}")
        logger.info(f"Poll interval: {settings.poll_interval_seconds}s")
        logger.info(f"Tracking {len(TRACKED_PLAYERS)} players")
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)
    
    # Initialize Redis
    redis_store = RedisStore(settings.redis_url)
    try:
        await redis_store.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Initialize Gemini
    gemini_client = GeminiClient(settings.gemini_api_key)
    logger.info("Gemini client initialized")
    
    # Initialize Discord bot
    bot = ProfessorBot(
        channel_id=settings.discord_channel_id,
        frontend_url=settings.frontend_url,
    )
    
    # Initialize match tracker
    match_tracker = MatchTracker(
        bot=bot,
        redis_store=redis_store,
        gemini_client=gemini_client,
        settings=settings,
    )
    
    # Initialize YouTube tracker (if API key is configured)
    youtube_tracker = None
    if settings.youtube_api_key:
        try:
            youtube_client = YouTubeClient(settings.youtube_api_key)
            email_notifier = create_email_notifier(
                smtp_server=settings.smtp_server,
                smtp_port=settings.smtp_port,
                smtp_user=settings.smtp_user,
                smtp_password=settings.smtp_password,
                from_email=settings.smtp_from_email,
            )
            youtube_tracker = YouTubeTracker(
                bot=bot,
                youtube_client=youtube_client,
                gemini_client=gemini_client,
                redis_store=redis_store,
                email_notifier=email_notifier,
                settings=settings,
            )
            logger.info(f"YouTube tracker initialized (posting at {settings.youtube_post_hour_gmt}:00 GMT)")
        except Exception as e:
            logger.warning(f"Failed to initialize YouTube tracker: {e}")
    else:
        logger.info("YouTube API key not configured, skipping YouTube tracker")
    
    # Initialize Nerd of the Day tracker (if enabled)
    nerd_tracker = None
    if settings.nerd_of_day_enabled:
        try:
            nerd_tracker = NerdOfTheDayTracker(
                bot=bot,
                gemini_client=gemini_client,
                settings=settings,
            )
            logger.info("Nerd of the Day tracker initialized (posting at 00:00 Portuguese time)")
        except Exception as e:
            logger.warning(f"Failed to initialize Nerd tracker: {e}")
    else:
        logger.info("Nerd of the Day feature disabled")
    
    # Start trackers as background tasks
    async def run_match_tracker():
        try:
            await match_tracker.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Match tracker error: {e}")
    
    async def run_youtube_tracker():
        if not youtube_tracker:
            return
        try:
            await youtube_tracker.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"YouTube tracker error: {e}")
    
    async def run_nerd_tracker():
        if not nerd_tracker:
            return
        try:
            await nerd_tracker.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Nerd tracker error: {e}")
    
    # Start bot with trackers
    async with bot:
        bot.loop.create_task(run_match_tracker())
        if youtube_tracker:
            bot.loop.create_task(run_youtube_tracker())
        if nerd_tracker:
            bot.loop.create_task(run_nerd_tracker())
        try:
            await bot.start(settings.discord_token)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            match_tracker.stop()
            if youtube_tracker:
                youtube_tracker.stop()
            if nerd_tracker:
                nerd_tracker.stop()
            await redis_store.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

