"""
Discord Bot Setup.
Handles Discord client, events, and message views.
"""

import io
import logging
import re
from typing import Optional

import discord
from discord import app_commands, ui

logger = logging.getLogger(__name__)


class ViewMatchButton(ui.View):
    """View with a button to open the match on Stratz."""

    def __init__(self, match_id: int):
        super().__init__(timeout=None)

        # Add the button as a link
        match_url = f"https://stratz.com/matches/{match_id}"
        self.add_item(ui.Button(
            label="🔍 View Full Match",
            url=match_url,
            style=discord.ButtonStyle.link,
        ))


def build_match_embed(
    player_name: str,
    hero_name: str,
    is_victory: bool,
    kda: str,
    duration: str,
    imp_score: float,
    grade: str,
    roast: str,
    smurf_line: Optional[str] = None,
    live_feed: Optional[list] = None,
) -> discord.Embed:
    """
    Build a rich embed for the match announcement.
    
    Args:
        player_name: Display name of the player
        hero_name: Hero played
        is_victory: Whether the player won
        kda: K/D/A string
        duration: Match duration string
        imp_score: IMP score
        grade: Letter grade
        roast: Roast message from Gemini
    
    Returns:
        Discord Embed object
    """
    # Color based on result
    if is_victory:
        color = discord.Color.green()
        result_emoji = "✅"
        result_text = "Victory"
    else:
        color = discord.Color.red()
        result_emoji = "❌"
        result_text = "Defeat"
    
    # Grade emoji
    grade_emojis = {
        "S": "🌟",
        "A": "🔥",
        "B": "👍",
        "C": "😐",
        "D": "👎",
        "F": "💀",
    }
    grade_emoji = grade_emojis.get(grade, "📊")
    
    # Build embed
    embed = discord.Embed(
        title=f"🎮 New Match: {player_name}",
        color=color,
    )
    
    # Match info
    embed.add_field(
        name="Hero",
        value=f"**{hero_name}**",
        inline=True,
    )
    embed.add_field(
        name="Result",
        value=f"{result_emoji} {result_text}",
        inline=True,
    )
    embed.add_field(
        name="Duration",
        value=f"⏱️ {duration}",
        inline=True,
    )
    
    # Stats
    embed.add_field(
        name="KDA",
        value=f"⚔️ **{kda}**",
        inline=True,
    )
    embed.add_field(
        name="IMP Score",
        value=f"{grade_emoji} **{imp_score:+.1f}** ({grade})",
        inline=True,
    )
    embed.add_field(
        name="\u200b",  # Empty field for spacing
        value="\u200b",
        inline=True,
    )
    
    # Post-game smurf check of the enemy team
    if smurf_line:
        embed.add_field(
            name="Smurf check",
            value=smurf_line[:1024],
            inline=False,
        )
    
    # What happened during the game, for players with live tracking
    if live_feed:
        lines = [f"`{clock}` {text}" for clock, text in live_feed]
        # Embed fields are capped at 1024 characters: drop the oldest lines
        while lines and sum(len(line) + 1 for line in lines) > 1024:
            lines.pop(0)
        if lines:
            embed.add_field(
                name="Live moments",
                value="\n".join(lines),
                inline=False,
            )
    
    # Roast as description
    embed.description = f"💬 *{roast}*"
    
    # Footer
    embed.set_footer(text="Professor Impetus")
    
    return embed


GSI_CONFIG_FILENAME = "gamestate_integration_impetus.cfg"

LIVE_SETUP_INSTRUCTIONS = """**Live Dota 2 tracking for {player}**

This uses Valve's built-in Game State Integration. Nothing gets installed: the attached file is plain text you can open and read. It tells your Dota client to send your own in-game state (hero, K/D/A, gold, items, abilities, game clock, result, plus game events such as tips and chat lines, which the bot ignores) to the Impetus bot while you play.

**1.** Save the attached `{filename}` into this folder (create `gamestate_integration` if it does not exist):
Windows: `Steam\\steamapps\\common\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\`
macOS: `~/Library/Application Support/Steam/steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration/`
**2.** In Steam: right-click Dota 2 → Properties → Launch Options → add `-gamestateintegration`
**3.** Restart Dota 2.

Only games played on the {player} Steam account are tracked; other accounts on the same PC are ignored.

The file contains your personal token, so do not share it. Running this command again gives you a new file and disables the old one. To stop, delete the file."""


STEAM_ID64_BASE = 76561197960265728

DOTA_ID_HELP = (
    "Your Dota ID is the number at the end of your profile link, for example "
    "`https://stratz.com/players/<ID>` or `https://www.opendota.com/players/<ID>`. "
    "It is also the Friend ID shown on your profile inside Dota 2. "
    "Paste the number or the whole link."
)


def resolve_dota_id(text: str, players: dict[str, str]) -> Optional[str]:
    """
    Find the tracked player a pasted Dota ID belongs to.

    Accepts the account ID (the number in a Stratz/OpenDota/Dotabuff profile
    URL, also the in-game Friend ID), that whole URL, or a Steam ID 64.

    Returns:
        The player's Steam ID 64, or None if the text holds no tracked ID.
    """
    for number in re.findall(r"\d{1,20}", text or ""):
        value = int(number)
        for steam_id in (str(value), str(value + STEAM_ID64_BASE)):
            if steam_id in players:
                return steam_id
    return None


def build_gsi_config(uri: str, token: str) -> str:
    """Build the Dota 2 Game State Integration cfg file for one player."""
    return f'''"Impetus"
{{
    "uri"       "{uri}"
    "timeout"   "5.0"
    "buffer"    "0.5"
    "throttle"  "2.0"
    "heartbeat" "30.0"
    "data"
    {{
        "map"       "1"
        "player"    "1"
        "hero"      "1"
        "items"     "1"
        "abilities" "1"
        "events"    "1"
    }}
    "auth"
    {{
        "token" "{token}"
    }}
}}
'''


class ProfessorBot(discord.Client):
    """Discord client for Professor Impetus."""
    
    def __init__(self, channel_id: int, frontend_url: str):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channel_id = channel_id
        self.frontend_url = frontend_url
        self._channel: Optional[discord.TextChannel] = None
        
        self.tree = app_commands.CommandTree(self)
        self._commands_synced = False
        self._gsi_redis = None
        self._gsi_public_url = ""
    
    def enable_live_setup(self, redis_store, public_url: str, players: dict[str, str]) -> None:
        """
        Register the /dota-live-setup slash command.
        
        Args:
            redis_store: RedisStore used to issue GSI tokens
            public_url: Public base URL of the GSI endpoint ("" if unknown)
            players: Steam ID 64 -> display name of the tracked players
        """
        self._gsi_redis = redis_store
        self._gsi_public_url = public_url

        @self.tree.command(
            name="dota-live-setup",
            description="Get your personal config file for live Dota 2 tracking",
        )
        @app_commands.describe(
            dota_id="The number at the end of your Stratz/OpenDota profile link (or paste the link)"
        )
        @app_commands.guild_only()
        async def dota_live_setup(
            interaction: discord.Interaction,
            dota_id: app_commands.Range[str, 1, 200],
        ):
            steam_id = resolve_dota_id(dota_id, players)
            if steam_id is None:
                await interaction.response.send_message(
                    "That ID is not one of the players Impetus tracks.\n\n" + DOTA_ID_HELP,
                    ephemeral=True,
                )
                return
            await self._handle_live_setup(interaction, steam_id, players[steam_id])
    
    async def _handle_live_setup(
        self,
        interaction: discord.Interaction,
        steam_id: str,
        player_name: str,
    ) -> None:
        """Issue a fresh GSI token and send the cfg file, visible only to the caller."""
        if not self._gsi_public_url:
            await interaction.response.send_message(
                "Live tracking is not set up yet: the bot has no public URL "
                "(set `GSI_PUBLIC_URL` or generate a Railway domain).",
                ephemeral=True,
            )
            return
        
        try:
            token = await self._gsi_redis.create_gsi_token(steam_id)
        except Exception as e:
            logger.error(f"Could not create GSI token for {player_name}: {e}")
            await interaction.response.send_message(
                "Could not create your token right now, try again in a minute.",
                ephemeral=True,
            )
            return
        
        logger.info(f"Issued GSI token for {player_name} to Discord user {interaction.user.id}")
        cfg = build_gsi_config(f"{self._gsi_public_url}/gsi", token)
        await interaction.response.send_message(
            LIVE_SETUP_INSTRUCTIONS.format(player=player_name, filename=GSI_CONFIG_FILENAME),
            file=discord.File(io.BytesIO(cfg.encode("utf-8")), filename=GSI_CONFIG_FILENAME),
            ephemeral=True,
        )
    
    async def on_ready(self):
        """Called when bot is connected and ready."""
        logger.info(f"Logged in as {self.user}")
        self._channel = self.get_channel(self.channel_id)
        if self._channel:
            logger.info(f"Connected to channel: {self._channel.name}")
        else:
            logger.warning(f"Could not find channel {self.channel_id}")
        
        await self._sync_commands()
    
    async def _sync_commands(self) -> None:
        """Publish slash commands to the announcement channel's server (once)."""
        if self._commands_synced or self._gsi_redis is None or not self._channel:
            return
        try:
            guild = self._channel.guild
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self._commands_synced = True
            logger.info(f"Slash commands synced to server: {guild.name}")
        except Exception as e:
            logger.warning(
                f"Could not sync slash commands ({e}). The bot may need to be "
                f"re-invited with the applications.commands scope."
            )
    
    async def send_embed(
        self, embed: discord.Embed, view: Optional[ui.View] = None
    ) -> Optional[int]:
        """
        Send an embed (optionally with buttons) to the configured channel.
        
        Returns:
            The new message's ID (so it can be edited later), or None on failure
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return None
        
        try:
            kwargs = {"view": view} if view is not None else {}
            message = await self._channel.send(
                embed=embed, allowed_mentions=discord.AllowedMentions.none(), **kwargs
            )
            return message.id
        except Exception as e:
            logger.exception(f"Error sending embed: {e}")
            return None
    
    async def edit_embed(self, message_id: int, embed: discord.Embed) -> bool:
        """
        Replace the embed of a message this bot sent earlier.
        
        Returns:
            True if edited successfully
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            return False
        
        try:
            await self._channel.get_partial_message(message_id).edit(embed=embed)
            return True
        except Exception as e:
            logger.warning(f"Could not edit message {message_id}: {e}")
            return False
    
    async def send_match_announcement(
        self,
        player_name: str,
        match_id: int,
        hero_name: str,
        is_victory: bool,
        kda: str,
        duration: str,
        imp_score: float,
        grade: str,
        roast: str,
        smurf_line: Optional[str] = None,
        replace_message_id: Optional[int] = None,
        live_feed: Optional[list] = None,
    ) -> bool:
        """
        Send a match announcement to the configured channel.
        
        Args:
            replace_message_id: If set, edit this existing message (the
                player's live post) into the announcement instead of sending
                a new one. Falls back to a new message if the edit fails.
            live_feed: [clock, text] lines from live tracking to include
        
        Returns:
            True if sent successfully
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return False
        
        try:
            embed = build_match_embed(
                player_name=player_name,
                hero_name=hero_name,
                is_victory=is_victory,
                kda=kda,
                duration=duration,
                imp_score=imp_score,
                grade=grade,
                roast=roast,
                smurf_line=smurf_line,
                live_feed=live_feed,
            )
            
            view = ViewMatchButton(match_id)
            
            if replace_message_id is not None:
                try:
                    await self._channel.get_partial_message(replace_message_id).edit(
                        embed=embed, view=view
                    )
                    logger.info(
                        f"Turned live post into match announcement for {player_name} (match {match_id})"
                    )
                    return True
                except Exception as e:
                    logger.warning(
                        f"Could not edit live post {replace_message_id}, sending a new message: {e}"
                    )
            
            await self._channel.send(embed=embed, view=view)
            logger.info(f"Sent match announcement for {player_name} (match {match_id})")
            return True
            
        except Exception as e:
            logger.exception(f"Error sending match announcement: {e}")
            return False
    
    async def send_video_header(self) -> bool:
        """
        Send the daily video header message.
        
        Returns:
            True if sent successfully
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return False
        
        try:
            await self._channel.send(
                "📚 **Daily Dota 2 Learning Content**\n"
                "Here's today's top educational video!"
            )
            return True
        except Exception as e:
            logger.exception(f"Error sending video header: {e}")
            return False
    
    async def send_video_recommendation(
        self,
        video,  # YouTubeVideo type (avoid import cycle)
        rank: int,
    ) -> bool:
        """
        Send a video recommendation embed to the channel.
        
        Args:
            video: YouTubeVideo object
            rank: Video ranking (1, 2, or 3)
            
        Returns:
            True if sent successfully
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return False
        
        try:
            # Medal emoji based on rank
            rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            rank_emoji = rank_emojis.get(rank, "🎬")
            
            embed = discord.Embed(
                title=f"{rank_emoji} {video.title}",
                url=video.url,
                color=discord.Color.red(),
            )
            
            # Set thumbnail
            if video.thumbnail_url:
                embed.set_image(url=video.thumbnail_url)
            
            # Add fields
            embed.add_field(
                name="Channel",
                value=video.channel_name,
                inline=True,
            )
            embed.add_field(
                name="Views",
                value=f"{video.view_count:,}",
                inline=True,
            )
            
            embed.set_footer(text="Professor Impetus - Daily Learning")
            
            await self._channel.send(embed=embed)
            logger.info(f"Sent video recommendation: {video.title}")
            return True
            
        except Exception as e:
            logger.exception(f"Error sending video recommendation: {e}")
            return False
    
    async def send_nerd_of_day(
        self,
        player_name: str,
        steam_id: str,
        games_played: int,
        total_hours: float,
        wins: int,
        losses: int,
        roast: str,
    ) -> bool:
        """
        Send the Nerd of the Day announcement to the channel.
        
        Args:
            player_name: Display name of the nerd
            steam_id: Steam ID for profile link
            games_played: Total games played yesterday
            total_hours: Total hours played
            wins: Number of wins
            losses: Number of losses
            roast: Roast message from Gemini
            
        Returns:
            True if sent successfully
        """
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)
        
        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return False
        
        try:
            # Build the embed
            embed = discord.Embed(
                title=f"👑 Nerd do Dia: {player_name}",
                color=discord.Color.gold(),
            )
            
            # Stats
            win_rate = (wins / games_played * 100) if games_played > 0 else 0
            
            embed.add_field(
                name="🎮 Jogos",
                value=f"**{games_played}**",
                inline=True,
            )
            embed.add_field(
                name="⏱️ Tempo",
                value=f"**{total_hours:.1f}h**",
                inline=True,
            )
            embed.add_field(
                name="📊 W/L",
                value=f"**{wins}W** / **{losses}L** ({win_rate:.0f}%)",
                inline=True,
            )
            
            # Roast as description
            embed.description = f"💬 *{roast}*"
            
            # Footer
            embed.set_footer(text="Professor Impetus - Nerd do Dia")
            
            # Add button to view player profile
            view = ui.View(timeout=None)
            player_url = f"{self.frontend_url}/player/{steam_id}"
            view.add_item(ui.Button(
                label="👤 Ver Perfil",
                url=player_url,
                style=discord.ButtonStyle.link,
            ))
            
            await self._channel.send(embed=embed, view=view)
            logger.info(f"Sent Nerd of the Day: {player_name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error sending Nerd of the Day: {e}")
            return False

    async def send_nerd_of_day_error(self) -> bool:
        """Send an error notification when Nerd of the Day data couldn't be fetched."""
        if not self._channel:
            self._channel = self.get_channel(self.channel_id)

        if not self._channel:
            logger.error(f"Channel {self.channel_id} not found")
            return False

        try:
            embed = discord.Embed(
                title="⚠️ Nerd do Dia — Indisponível",
                description=(
                    "Não foi possível obter dados dos jogadores hoje. "
                    "As APIs do OpenDota e Stratz estavam indisponíveis."
                ),
                color=discord.Color.orange(),
            )
            embed.set_footer(text="Professor Impetus - Nerd do Dia")
            await self._channel.send(embed=embed)
            logger.info("Sent Nerd of the Day error notification")
            return True
        except Exception as e:
            logger.exception(f"Error sending Nerd of the Day error notification: {e}")
            return False

