"""
Discord bot for AoE2 match announcements.

Builds rich embeds with match info, team composition, and AI roasts.
"""

import logging

import discord

from app.services.worldsedge import AoE2Match

logger = logging.getLogger(__name__)

# Colors
COLOR_WIN = 0x00FF00  # Green — tracked player(s) won
COLOR_LOSS = 0xFF0000  # Red — tracked player(s) lost
COLOR_SPLIT = 0xFFAA00  # Amber — tracked players on opposing teams


class MatchView(discord.ui.View):
    """Button view linking to match details."""

    def __init__(self, match_id: int):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="🔍 View on AoE2 Insights",
                url=f"https://www.aoe2insights.com/match/{match_id}/",
                style=discord.ButtonStyle.link,
            )
        )


def build_match_embed(
    match: AoE2Match,
    tracked_players: list[dict],
    all_teams: dict[int, list[dict]],
    aliases: dict[int, str],
    roast: str,
    tracked_vs_tracked: bool,
) -> discord.Embed:
    """Build a Discord embed for an AoE2 match announcement."""

    is_group = len(tracked_players) > 1
    player_names = ", ".join(p["nickname"] for p in tracked_players)

    # Map name is only reliable for 1v1 — WorldsEdge API returns the
    # host's map preference for team games, not the actual map played.
    show_map = not match.is_team_game
    map_name = match.clean_map_name if show_map else None
    map_suffix = f" on {map_name}" if map_name else ""

    # Title
    if tracked_vs_tracked:
        teams_by_player: dict[int, list[str]] = {}
        for p in tracked_players:
            teams_by_player.setdefault(p["team_id"], []).append(p["nickname"])
        team_strs = [" & ".join(names) for names in teams_by_player.values()]
        title = f"⚔️ {' vs '.join(team_strs)} — {match.game_mode}{map_suffix}"
    elif is_group:
        title = f"🏰 {player_names} — {match.game_mode}{map_suffix}"
    else:
        title = f"🏰 {player_names} — {match.game_mode}{map_suffix}"

    # Color
    if tracked_vs_tracked:
        color = COLOR_SPLIT
    elif any(p["won"] for p in tracked_players):
        color = COLOR_WIN
    else:
        color = COLOR_LOSS

    embed = discord.Embed(
        title=title,
        color=color,
        description=f"*{roast}*",
    )

    # Duration field
    embed.add_field(
        name="⏱️ Duration",
        value=match.duration_str,
        inline=True,
    )

    # Map field (only for 1v1 — unreliable for team games)
    if map_name:
        embed.add_field(
            name="🗺️ Map",
            value=map_name,
            inline=True,
        )

    # Result + ELO for tracked players
    result_lines = []
    for p in tracked_players:
        result_emoji = "✅" if p["won"] else "❌"
        result_text = "Victory" if p["won"] else "Defeat"
        line = f"{result_emoji} **{p['nickname']}** ({p['civ']}) — {result_text}"
        if p.get("old_rating") and p.get("new_rating"):
            change = p["new_rating"] - p["old_rating"]
            sign = "+" if change >= 0 else ""
            line += f" ({sign}{change} ELO)"
        result_lines.append(line)

    embed.add_field(
        name="🏆 Result",
        value="\n".join(result_lines),
        inline=False,
    )

    # Team rosters
    tracked_pids = {p["profile_id"] for p in tracked_players}
    for team_id in sorted(all_teams.keys()):
        team = all_teams[team_id]
        team_won = any(p.get("won") for p in team)
        team_emoji = "🟢" if team_won else "🔴"

        roster_lines = []
        for p in team:
            name = p["alias"]
            if p["profile_id"] in tracked_pids:
                # Bold tracked players and show nickname
                nickname = next(
                    tp["nickname"] for tp in tracked_players
                    if tp["profile_id"] == p["profile_id"]
                )
                name = f"**{p['alias']}** ({nickname})"
            rating_str = ""
            if p.get("old_rating"):
                rating_str = f" [{p['old_rating']}]"
            roster_lines.append(f"🏰 {name} — {p['civ']}{rating_str}")

        embed.add_field(
            name=f"{team_emoji} Team {team_id + 1}",
            value="\n".join(roster_lines) or "Unknown",
            inline=True,
        )

    # Footer
    embed.set_footer(text="Professor Impetus • AoE2 Division")

    return embed
