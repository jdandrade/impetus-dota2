"""Shared player identities and group lore for Impetus Discord bots."""

from group_lore.players import (
    Player,
    PLAYERS,
    resolve_player,
    build_players_prompt_block,
    build_name_mappings,
)
from group_lore.discord_lore import DISCORD_LORE

__all__ = [
    "Player",
    "PLAYERS",
    "resolve_player",
    "build_players_prompt_block",
    "build_name_mappings",
    "DISCORD_LORE",
]
