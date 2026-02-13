"""
YouTube API Client.
Fetches Dota 2 videos from YouTube Data API v3.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


@dataclass
class YouTubeVideo:
    """Represents a YouTube video with metadata."""
    
    video_id: str
    title: str
    description: str
    thumbnail_url: str
    view_count: int
    channel_name: str
    published_at: datetime
    
    @property
    def url(self) -> str:
        """Full YouTube URL for this video."""
        return f"https://www.youtube.com/watch?v={self.video_id}"


class YouTubeClient:
    """Client for YouTube Data API v3."""
    
    # Dota 2 topic ID from YouTube's topic taxonomy
    DOTA2_TOPIC_ID = "/m/0h5f2t2"
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        self.youtube = build("youtube", "v3", developerKey=api_key)
        logger.info("YouTube client initialized")
    
    async def search_dota_videos(
        self,
        max_results: int = 50,
        days_back: int = 7,
    ) -> list[YouTubeVideo]:
        """
        Search for Dota 2 videos uploaded in the last N days.
        
        Args:
            max_results: Maximum number of videos to return
            days_back: How many days back to search
            
        Returns:
            List of YouTubeVideo objects sorted by view count (descending)
        """
        try:
            # Calculate date range
            published_after = (
                datetime.now(timezone.utc) - timedelta(days=days_back)
            ).isoformat()
            
            # Search for Dota 2 videos
            # Using query "dota 2" since topic filtering can be inconsistent
            search_response = self.youtube.search().list(
                part="snippet",
                q="dota 2",
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                maxResults=max_results,
                videoDuration="medium",  # 4-20 minutes (filters out shorts and very long streams)
                relevanceLanguage="en",
            ).execute()
            
            video_ids = [
                item["id"]["videoId"]
                for item in search_response.get("items", [])
            ]
            
            if not video_ids:
                logger.warning("No Dota 2 videos found in search")
                return []
            
            # Fetch detailed stats for each video
            return await self._get_video_details(video_ids)
            
        except HttpError as e:
            logger.exception(f"YouTube API error: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error searching YouTube: {e}")
            raise
    
    async def _get_video_details(
        self,
        video_ids: list[str],
    ) -> list[YouTubeVideo]:
        """
        Fetch detailed information for a list of video IDs.
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            List of YouTubeVideo objects with full metadata
        """
        try:
            # Batch request for video details
            videos_response = self.youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids),
            ).execute()
            
            videos = []
            for item in videos_response.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                
                # Filter out non-English videos
                default_audio_lang = snippet.get("defaultAudioLanguage", "")
                default_lang = snippet.get("defaultLanguage", "")
                lang = default_audio_lang or default_lang
                if lang and not lang.startswith("en"):
                    logger.debug(f"Skipping non-English video: {snippet['title']} (lang={lang})")
                    continue
                
                # Parse published date
                published_str = snippet["publishedAt"]
                published_at = datetime.fromisoformat(
                    published_str.replace("Z", "+00:00")
                )
                
                # Get best thumbnail (maxres > high > medium > default)
                thumbnails = snippet["thumbnails"]
                thumbnail_url = (
                    thumbnails.get("maxres", {}).get("url") or
                    thumbnails.get("high", {}).get("url") or
                    thumbnails.get("medium", {}).get("url") or
                    thumbnails.get("default", {}).get("url", "")
                )
                
                video = YouTubeVideo(
                    video_id=item["id"],
                    title=snippet["title"],
                    description=snippet.get("description", "")[:500],  # Truncate long descriptions
                    thumbnail_url=thumbnail_url,
                    view_count=int(stats.get("viewCount", 0)),
                    channel_name=snippet["channelTitle"],
                    published_at=published_at,
                )
                videos.append(video)
            
            # Sort by view count (descending)
            videos.sort(key=lambda v: v.view_count, reverse=True)
            
            logger.info(f"Fetched details for {len(videos)} videos (after language filter)")
            return videos
            
        except HttpError as e:
            logger.exception(f"YouTube API error fetching video details: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error fetching video details: {e}")
            raise
