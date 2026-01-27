"""
Discord Bot Setup.
Handles Discord client, events, and message views.
"""

import logging
from typing import Optional

import discord
from discord import ui

logger = logging.getLogger(__name__)


class ViewMatchButton(ui.View):
    """View with a button to open the match on our frontend."""
    
    def __init__(self, match_id: int, frontend_url: str):
        super().__init__(timeout=None)
        
        # Add the button as a link
        match_url = f"{frontend_url}/match/{match_id}"
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
    
    # Roast as description
    embed.description = f"💬 *{roast}*"
    
    # Footer
    embed.set_footer(text="Professor Impetus")
    
    return embed


class ProfessorBot(discord.Client):
    """Discord client for Professor Impetus."""
    
    def __init__(self, channel_id: int, frontend_url: str):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channel_id = channel_id
        self.frontend_url = frontend_url
        self._channel: Optional[discord.TextChannel] = None
    
    async def on_ready(self):
        """Called when bot is connected and ready."""
        logger.info(f"Logged in as {self.user}")
        self._channel = self.get_channel(self.channel_id)
        if self._channel:
            logger.info(f"Connected to channel: {self._channel.name}")
        else:
            logger.warning(f"Could not find channel {self.channel_id}")
    
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
    ) -> bool:
        """
        Send a match announcement to the configured channel.
        
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
            )
            
            view = ViewMatchButton(match_id, self.frontend_url)
            
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
                "Here are today's top educational videos!"
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

