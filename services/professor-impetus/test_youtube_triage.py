"""
Test script to preview YouTube video triage output.
Run: python3 test_youtube_triage.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from app.services.youtube import YouTubeClient
from app.services.gemini import GeminiClient


async def main():
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if not youtube_api_key:
        print("❌ YOUTUBE_API_KEY not set in .env")
        return
    
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set in .env")
        return
    
    print("=" * 60)
    print("🔍 Fetching Dota 2 videos from YouTube...")
    print("=" * 60)
    
    # Step 1: Fetch videos
    youtube = YouTubeClient(youtube_api_key)
    videos = await youtube.search_dota_videos(max_results=20, days_back=7)
    
    print(f"\n📹 Found {len(videos)} videos:\n")
    for i, v in enumerate(videos, 1):
        print(f"{i:2}. [{v.view_count:>10,} views] {v.channel_name}")
        print(f"    {v.title[:70]}...")
        print(f"    {v.url}")
        print()
    
    # Step 2: Triage with Gemini
    print("=" * 60)
    print("🤖 Asking Gemini to select top 3 educational videos...")
    print("=" * 60)
    
    gemini = GeminiClient(gemini_api_key)
    selected_ids = await gemini.triage_videos(videos)
    
    # Map back to video objects
    id_to_video = {v.video_id: v for v in videos}
    selected = [id_to_video[vid] for vid in selected_ids if vid in id_to_video]
    
    print(f"\n✅ Gemini selected {len(selected)} videos:\n")
    print("-" * 60)
    
    rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, v in enumerate(selected, 1):
        emoji = rank_emojis.get(rank, "🎬")
        print(f"{emoji} #{rank}: {v.title}")
        print(f"   Channel: {v.channel_name}")
        print(f"   Views: {v.view_count:,}")
        print(f"   URL: {v.url}")
        print()
    
    print("-" * 60)
    print("📺 These would be posted to Discord at 21:00 GMT")


if __name__ == "__main__":
    asyncio.run(main())
