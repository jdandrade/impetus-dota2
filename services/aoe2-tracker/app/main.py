"""
AoE2 Match Tracker — Main entry point.

Initializes Discord bot, Redis, Gemini, and WorldsEdge client.
Starts the AoE2Tracker as a concurrent task.
"""

import logging
import asyncio

import discord
import redis.asyncio as aioredis

from app.config import get_settings
from app.services.worldsedge import WorldsEdgeClient
from app.services.redis_store import RedisStore
from app.services.gemini import GeminiClient
from app.tracker import AoE2Tracker
from app.bot import build_match_embed, MatchView

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    settings = get_settings()

    # Initialize Redis
    logger.info("Connecting to Redis...")
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        logger.info("Redis connected.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return

    redis_store = RedisStore(redis_client)

    # Initialize Gemini
    logger.info("Initializing Gemini...")
    gemini = GeminiClient(settings.gemini_api_key)

    # Initialize WorldsEdge client
    worldsedge = WorldsEdgeClient()

    # Initialize Discord bot
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    channel = None

    @client.event
    async def on_ready():
        nonlocal channel
        logger.info(f"Discord bot ready: {client.user}")
        channel = client.get_channel(settings.discord_channel_id)
        if channel:
            logger.info(f"Posting to channel: #{channel.name}")
        else:
            logger.error(f"Channel {settings.discord_channel_id} not found!")

    async def send_announcement(match, tracked_players, all_teams, aliases, roast, tracked_vs_tracked):
        """Callback for tracker to send Discord announcements."""
        if not channel:
            logger.error("Discord channel not available")
            return

        try:
            embed = build_match_embed(
                match=match,
                tracked_players=tracked_players,
                all_teams=all_teams,
                aliases=aliases,
                roast=roast,
                tracked_vs_tracked=tracked_vs_tracked,
            )
            view = MatchView(match.match_id)
            await channel.send(embed=embed, view=view)
            player_names = ", ".join(p["nickname"] for p in tracked_players)
            logger.info(f"Announced: {player_names} — {match.clean_map_name} {match.game_mode}")
        except Exception as e:
            logger.error(f"Failed to send announcement: {e}", exc_info=True)

    # Create tracker
    tracker = AoE2Tracker(
        settings=settings,
        worldsedge=worldsedge,
        redis_store=redis_store,
        gemini=gemini,
        send_callback=send_announcement,
    )

    # Start bot and tracker concurrently
    async def run_tracker():
        await client.wait_until_ready()
        await tracker.start()

    async def run_bot():
        try:
            async with client:
                client.loop.create_task(run_tracker())
                await client.start(settings.discord_token)
        except asyncio.CancelledError:
            pass
        finally:
            tracker.stop()
            await worldsedge.close()
            await redis_client.close()
            logger.info("Shutdown complete.")

    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
