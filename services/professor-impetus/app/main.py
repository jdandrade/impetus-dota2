"""
Professor Impetus - Entry Point

Discord bot that tracks Dota 2 matches and generates roast messages
using the internal Impetus scoring engine.
"""

import asyncio
import logging
import sys

from app.config import get_settings, get_gsi_public_url, TRACKED_PLAYERS
from app.bot import ProfessorBot
from app.tracker import MatchTracker
from app.gsi import GSIServer
from app.pro_feed import ProMatchFeed
from app.release_notes import announce_release
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
        if settings.steam_api_key:
            logger.info(
                f"Match detection: Steam Web API every {settings.steam_poll_interval_seconds}s "
                f"(OpenDota fallback every {settings.poll_interval_seconds}s)"
            )
        else:
            logger.info(f"Match detection: OpenDota every {settings.poll_interval_seconds}s (no STEAM_API_KEY)")
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
    
    # Live tracking via Dota 2 Game State Integration (opt-in per player)
    gsi_server = None
    if settings.gsi_enabled:
        gsi_public_url = get_gsi_public_url(settings)
        gsi_server = GSIServer(
            bot=bot,
            redis_store=redis_store,
            gemini_client=gemini_client,
            match_tracker=match_tracker,
            settings=settings,
        )
        match_tracker.live_posts = gsi_server
        bot.enable_live_setup(redis_store, gsi_public_url, TRACKED_PLAYERS)
        if gsi_public_url:
            logger.info(f"Live tracking (GSI) enabled at {gsi_public_url}/gsi")
        else:
            logger.warning(
                "Live tracking (GSI): no public URL (set GSI_PUBLIC_URL or "
                "generate a Railway domain); /dota-live-setup will not hand out configs"
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
    
    # Pro match feed (series starting in big tournaments, with stream links)
    pro_feed = None
    if settings.pro_feed_enabled:
        pro_feed = ProMatchFeed(bot=bot, redis_store=redis_store, settings=settings)
    else:
        logger.info("Pro match feed disabled")
    
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
    
    async def run_pro_feed():
        try:
            await pro_feed.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Pro match feed error: {e}")
    
    async def run_release_announcement():
        try:
            await announce_release(bot, redis_store)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Release announcement error: {e}")
    
    # Start bot with trackers
    async with bot:
        if gsi_server:
            try:
                await gsi_server.start()
            except Exception as e:
                logger.exception(f"Failed to start GSI endpoint: {e}")
                gsi_server = None
        bot.loop.create_task(run_match_tracker())
        bot.loop.create_task(run_release_announcement())
        if pro_feed:
            bot.loop.create_task(run_pro_feed())
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
            if pro_feed:
                pro_feed.stop()
            if gsi_server:
                await gsi_server.stop()
            await redis_store.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

