"""
Configuration module for AoE2 Match Tracker.
Loads environment variables and defines tracked players.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Discord
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_channel_id: int = Field(default=1112808395653775541, env="DISCORD_CHANNEL_ID")

    # Gemini API
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # Polling intervals
    poll_interval_seconds: int = Field(default=600, env="POLL_INTERVAL_SECONDS")
    off_hours_poll_interval: int = Field(default=1800, env="OFF_HOURS_POLL_INTERVAL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Tracked AoE2 players
# Key: slug for Redis keys
# "player" links to the canonical name in group-lore
TRACKED_PLAYERS = {
    "fear": {
        "profile_id": 18252764,
        "aoe2_alias": "feAr^",
        "player": "feAr",
    },
    "cego": {
        "profile_id": 18252806,
        "aoe2_alias": "bad man",
        "player": "Cego",
    },
    "gil": {
        "profile_id": 4070473,
        "aoe2_alias": "Rodrigo",
        "player": "Gil",
    },
    "mauzaum": {
        "profile_id": 775280,
        "aoe2_alias": "MZ",
        "player": "MauZaum",
    },
    "paulo": {
        "profile_id": 1839468,
        "aoe2_alias": "Roflicious",
        "player": "Paulo",
    },
}

# Build a quick lookup: profile_id → player_key
PROFILE_TO_PLAYER = {
    info["profile_id"]: key for key, info in TRACKED_PLAYERS.items()
}


def get_poll_interval(settings: Settings) -> int:
    """
    Get adaptive poll interval based on current Portugal time.

    Off-hours (2am-8am Portugal): 30 min polling
    Normal hours (8am-2am Portugal): 10 min polling
    """
    from datetime import datetime
    import pytz

    portugal_tz = pytz.timezone("Europe/Lisbon")
    current_hour = datetime.now(portugal_tz).hour

    if 2 <= current_hour < 8:
        return settings.off_hours_poll_interval

    return settings.poll_interval_seconds


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
