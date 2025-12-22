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
from app.services.redis_store import RedisStore
from app.services.gemini import GeminiClient

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
    tracker = MatchTracker(
        bot=bot,
        redis_store=redis_store,
        gemini_client=gemini_client,
        settings=settings,
    )
    
    # Start tracker as background task
    async def run_tracker():
        try:
            await tracker.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Tracker error: {e}")
    
    # Start bot with tracker
    async with bot:
        bot.loop.create_task(run_tracker())
        try:
            await bot.start(settings.discord_token)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            tracker.stop()
            await redis_store.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
