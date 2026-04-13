"""
Discord bot for WoW Mythic+ run announcements.

Builds rich embeds with dungeon info, group composition, and AI roasts.
"""

import logging

import discord

from app.services.raiderio import MythicPlusRun, RunDetails

logger = logging.getLogger(__name__)

# Role emojis
ROLE_EMOJI = {
    "tank": "🛡️",
    "healer": "💚",
    "dps": "⚔️",
}

# Colors
COLOR_TIMED = 0x00FF00  # Green
COLOR_DEPLETED = 0xFF0000  # Red


class RunView(discord.ui.View):
    """Button view linking to Raider.IO run page."""

    def __init__(self, run_url: str):
        super().__init__(timeout=None)
        if run_url:
            self.add_item(
                discord.ui.Button(
                    label="🔍 View on Raider.IO",
                    url=run_url,
                    style=discord.ButtonStyle.link,
                )
            )


def build_run_embed(
    run: MythicPlusRun,
    details: RunDetails | None,
    tracked_players: list[dict],
    group_roster: list[dict],
    roast: str,
) -> discord.Embed:
    """Build a Discord embed for a Mythic+ run announcement."""

    # Determine if this is a group run
    is_group_run = len(tracked_players) > 1
    player_names = ", ".join(p["nickname"] for p in tracked_players)

    # Title
    if is_group_run:
        title = f"⚔️ +{run.mythic_level} {run.dungeon}"
    else:
        title = f"⚔️ {player_names} — +{run.mythic_level} {run.dungeon}"

    # Color based on timed/depleted
    color = COLOR_TIMED if run.is_timed else COLOR_DEPLETED

    embed = discord.Embed(
        title=title,
        color=color,
        description=f"*{roast}*",
    )

    # Time field
    time_diff = abs(run.time_diff_pct)
    if run.is_timed:
        upgrade_str = f"+{run.num_keystone_upgrades}"
        time_text = f"{run.clear_time_str} / {run.par_time_str} ({time_diff:.1f}% under) ✅ {upgrade_str}"
    else:
        time_text = f"{run.clear_time_str} / {run.par_time_str} ({time_diff:.1f}% over) ❌ Depleted"

    embed.add_field(name="⏱️ Time", value=time_text, inline=False)

    # Group composition
    if group_roster:
        # Sort: tank first, then healer, then DPS
        role_order = {"tank": 0, "healer": 1, "dps": 2}
        sorted_roster = sorted(group_roster, key=lambda m: role_order.get(m["role"], 2))

        # Build tracked player name set for highlighting
        tracked_chars = {p["character"].lower() for p in tracked_players}

        roster_lines = []
        for m in sorted_roster:
            emoji = ROLE_EMOJI.get(m["role"], "⚔️")
            line = f"{emoji} **{m['name']}** — {m['spec']} {m['class']}"

            # Add nickname for tracked players
            for tp in tracked_players:
                if tp["character"].lower() == m["name"].lower():
                    line += f" ({tp['nickname']})"
                    break

            roster_lines.append(line)

        embed.add_field(name="👥 Group", value="\n".join(roster_lines), inline=False)

    # Affixes
    if run.affixes:
        affix_names = " • ".join(a["name"] for a in run.affixes)
        embed.add_field(name="🌀 Affixes", value=affix_names, inline=False)

    # Deaths (if available from run details)
    if details and details.total_deaths > 0:
        death_text = f"{details.total_deaths} death{'s' if details.total_deaths != 1 else ''}"

        # Add per-player breakdown if available
        if details.deaths:
            death_counts: dict[str, int] = {}
            for d in details.deaths:
                name = d.get("name", "Unknown")
                death_counts[name] = death_counts.get(name, 0) + 1

            if death_counts:
                breakdown = ", ".join(f"{name} ({count}x)" for name, count in sorted(death_counts.items(), key=lambda x: -x[1]))
                death_text += f"\n{breakdown}"

        embed.add_field(name="💀 Deaths", value=death_text, inline=False)

    # Dungeon image
    if run.background_image_url:
        bg_url = run.background_image_url
        if not bg_url.startswith("http"):
            bg_url = f"https://cdn.raiderio.net{bg_url}"
        embed.set_image(url=bg_url)

    # Footer
    embed.set_footer(text="Professor Impetus • WoW Division")

    # Score
    if run.score > 0:
        embed.add_field(name="📊 Score", value=f"{run.score:.1f}", inline=True)

    return embed
