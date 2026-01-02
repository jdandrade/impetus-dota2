"""
Configuration module for Professor Impetus.
Loads environment variables and defines tracked players.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Discord
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_channel_id: int = Field(default=1341725863535710218, env="DISCORD_CHANNEL_ID")
    
    # Gemini API
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # Internal Impetus API
    imp_engine_url: str = Field(
        default="https://impetus-dota2-production.up.railway.app",
        env="IMP_ENGINE_URL"
    )
    
    # Frontend URL (for View Match button)
    frontend_url: str = Field(
        default="https://impetus-dota2.vercel.app",
        env="FRONTEND_URL"
    )
    
    # Polling intervals
    # Normal hours: 10 min = 600s
    poll_interval_seconds: int = Field(default=600, env="POLL_INTERVAL_SECONDS")
    # Off hours (2am-8am Portugal): 30 min = 1800s
    off_hours_poll_interval: int = Field(default=1800, env="OFF_HOURS_POLL_INTERVAL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Tracked players from legacy bot
# Format: Steam ID 64 -> Display name (for fallback if API fails)
TRACKED_PLAYERS = {
    "76561198349926313": "fear",
    "76561198031378148": "rybur",
    "76561198044301453": "batatas",
    "76561197986252478": "gil",
    "76561197994301802": "mauzaum",
    "76561198014373442": "hory",
    "76561199837733852": "mister miagy",
}


def convert_steam_id64_to_account_id(steam_id_64: str) -> int:
    """Convert SteamID64 to Dota 2 Account ID (used by OpenDota)."""
    return int(steam_id_64) - 76561197960265728


def get_poll_interval(settings: "Settings") -> int:
    """
    Get adaptive poll interval based on current Portugal time.
    
    Off-hours (2am-8am Portugal): 30 min polling
    Normal hours (8am-2am Portugal): 10 min polling
    """
    from datetime import datetime
    import pytz
    
    portugal_tz = pytz.timezone("Europe/Lisbon")
    current_hour = datetime.now(portugal_tz).hour
    
    # Off hours: 2am to 8am (2, 3, 4, 5, 6, 7)
    if 2 <= current_hour < 8:
        return settings.off_hours_poll_interval
    
    return settings.poll_interval_seconds


def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    return Settings()

