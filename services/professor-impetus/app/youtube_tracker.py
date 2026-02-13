"""
YouTube Video Tracker.
Posts daily viral Dota 2 videos to Discord at 21:00 GMT.
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.bot import ProfessorBot
from app.config import Settings
from app.services.youtube import YouTubeClient, YouTubeVideo
from app.services.gemini import GeminiClient
from app.services.redis_store import RedisStore
from app.services.email_notifier import EmailNotifier, NoOpEmailNotifier

logger = logging.getLogger(__name__)


class YouTubeTracker:
    """Posts daily viral Dota 2 videos to Discord at 21:00 GMT."""
    
    # Default posting time (21:00 GMT)
    TARGET_HOUR_GMT = 21
    TARGET_MINUTE_GMT = 0
    
    # Search parameters
    MAX_SEARCH_RESULTS = 50
    DAYS_BACK = 7
    MAX_VIDEOS_TO_POST = 1
    
    def __init__(
        self,
        bot: ProfessorBot,
        youtube_client: YouTubeClient,
        gemini_client: GeminiClient,
        redis_store: RedisStore,
        email_notifier: EmailNotifier | NoOpEmailNotifier,
        settings: Settings,
    ):
        """
        Initialize the YouTube tracker.
        
        Args:
            bot: Discord bot instance
            youtube_client: YouTube API client
            gemini_client: Gemini client for triage
            redis_store: Redis store for deduplication
            email_notifier: Email notifier for error alerts
            settings: Application settings
        """
        self.bot = bot
        self.youtube = youtube_client
        self.gemini = gemini_client
        self.redis = redis_store
        self.email = email_notifier
        self.settings = settings
        self._running = False
        
        # Override target hour from settings if configured
        self.target_hour = getattr(settings, 'youtube_post_hour_gmt', self.TARGET_HOUR_GMT)
    
    async def start(self) -> None:
        """Start the daily video posting loop."""
        self._running = True
        logger.info(f"Starting YouTube tracker (posting at {self.target_hour:02d}:00 GMT)...")
        
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, YouTube tracker initialized")
        
        while self._running and not self.bot.is_closed():
            try:
                # Wait until target time
                await self._wait_until_target_time()
                
                if not self._running:
                    break
                
                # Post daily videos
                await self._post_daily_videos()
                
                # Sleep for an hour to avoid double-posting
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                logger.info("YouTube tracker cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in YouTube tracker loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(300)
    
    def stop(self) -> None:
        """Stop the daily video posting loop."""
        self._running = False
        logger.info("Stopping YouTube tracker...")
    
    async def _wait_until_target_time(self) -> None:
        """Sleep until the target posting time (21:00 GMT)."""
        now = datetime.now(timezone.utc)
        target = now.replace(
            hour=self.target_hour,
            minute=self.TARGET_MINUTE_GMT,
            second=0,
            microsecond=0,
        )
        
        # If target time has passed today, wait until tomorrow
        if now >= target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        logger.info(f"Waiting {wait_seconds/3600:.1f} hours until {target.isoformat()}")
        
        await asyncio.sleep(wait_seconds)
    
    async def _post_daily_videos(self) -> None:
        """Fetch, triage, and post daily videos."""
        try:
            logger.info("Starting daily video fetch...")
            
            # Step 1: Fetch videos from YouTube
            videos = await self.youtube.search_dota_videos(
                max_results=self.MAX_SEARCH_RESULTS,
                days_back=self.DAYS_BACK,
            )
            
            if not videos:
                logger.warning("No videos found from YouTube search")
                return
            
            logger.info(f"Fetched {len(videos)} videos from YouTube")
            
            # Step 2: Filter out already posted videos
            unposted_videos = []
            for video in videos:
                if not await self.redis.has_video_been_posted(video.video_id):
                    unposted_videos.append(video)
            
            if not unposted_videos:
                logger.info("All videos have already been posted, skipping")
                return
            
            logger.info(f"{len(unposted_videos)} videos are unposted")
            
            # Step 3: Use Gemini to triage for quality
            selected_ids = await self.gemini.triage_videos(unposted_videos)
            
            if not selected_ids:
                logger.info("No videos passed quality triage, skipping")
                return
            
            # Map selected IDs back to video objects
            id_to_video = {v.video_id: v for v in unposted_videos}
            selected_videos = [
                id_to_video[vid]
                for vid in selected_ids
                if vid in id_to_video
            ][:self.MAX_VIDEOS_TO_POST]
            
            if not selected_videos:
                logger.warning("Selected videos not found in unposted list")
                return
            
            logger.info(f"Posting {len(selected_videos)} videos to Discord")
            
            # Step 4: Post to Discord
            await self.bot.send_video_header()
            
            for rank, video in enumerate(selected_videos, 1):
                await self.bot.send_video_recommendation(video, rank)
                await self.redis.mark_video_as_posted(video.video_id)
                # Small delay between posts
                await asyncio.sleep(1)
            
            logger.info(f"Successfully posted {len(selected_videos)} daily videos")
            
        except Exception as e:
            error_log = f"Error posting daily videos:\n\n{traceback.format_exc()}"
            logger.exception(error_log)
            
            # Send email notification
            self.email.send_error_notification(
                to_email="j_diogo_@hotmail.com",
                subject="YouTube Daily Videos Failed",
                error_log=error_log,
            )
    
    async def trigger_now(self) -> None:
        """
        Manually trigger a video post (for testing).
        Bypasses the schedule and posts immediately.
        """
        logger.info("Manually triggered daily video post")
        await self._post_daily_videos()
