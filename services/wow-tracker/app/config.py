"""
Configuration module for WoW Mythic+ Tracker.
Loads environment variables and defines tracked characters.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Discord
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_channel_id: int = Field(default=888477897105506344, env="DISCORD_CHANNEL_ID")

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


# Tracked WoW characters
# Key format: "charname-realm-region" (slugified)
# "player" links to the canonical name in group-lore
TRACKED_CHARACTERS = {
    "feardk-aggra-portugues-eu": {
        "name": "Feardk",
        "realm": "aggra-português",
        "region": "eu",
        "player": "feAr",
    },
    "fearbrew-aggra-portugues-eu": {
        "name": "Fearbrew",
        "realm": "aggra-português",
        "region": "eu",
        "player": "feAr",
    },
    # Temporarily hidden — re-enable when ready
    # "feark-aggra-portugues-eu": {
    #     "name": "Feark",
    #     "realm": "aggra-português",
    #     "region": "eu",
    #     "player": "feAr",
    # },
    "zenyar-grim-batol-eu": {
        "name": "Zenyär",
        "realm": "grim-batol",
        "region": "eu",
        "player": "Paulo",
    },
    "zenyar-frostmane-eu": {
        "name": "Zenyar",
        "realm": "frostmane",
        "region": "eu",
        "player": "Paulo",
    },
    "padrezaum-grim-batol-eu": {
        "name": "Padrezaum",
        "realm": "grim-batol",
        "region": "eu",
        "player": "MauZaum",
    },
    "mauzaum-grim-batol-eu": {
        "name": "MauZaum",
        "realm": "grim-batol",
        "region": "eu",
        "player": "MauZaum",
    },
    "baconlayss-grim-batol-eu": {
        "name": "Baconlayss",
        "realm": "grim-batol",
        "region": "eu",
        "player": "Batatas",
    },
    "rybur-aggra-portugues-eu": {
        "name": "Rybur",
        "realm": "aggra-português",
        "region": "eu",
        "player": "Cego",
    },
    "dabadi-grim-batol-eu": {
        "name": "Dabadi",
        "realm": "grim-batol",
        "region": "eu",
        "player": "Careca",
    },
    "babibi-grim-batol-eu": {
        "name": "Babibi",
        "realm": "grim-batol",
        "region": "eu",
        "player": "Careca",
    },
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
