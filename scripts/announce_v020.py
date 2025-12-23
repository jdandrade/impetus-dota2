#!/usr/bin/env python3
"""
One-time script to announce v0.2.0 release on Discord.
Run with: python scripts/announce_v020.py
Requires: DISCORD_TOKEN and DISCORD_CHANNEL_ID environment variables
"""

import os
import asyncio
import discord
from discord import Embed

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "1341725863535710218"))

ANNOUNCEMENT = """
🚀 **Impetus v0.2.0 Released!**

O Professor está de volta com novidades fresquinhas direto do Laboratório de Análise:

✨ **New Features:**
• **Net Worth Graph** - Agora podes ver a vantagem de gold ao longo do tempo em cada match
• **Most Addicted Players** - Hall of Fame dos viciados em Dota
• **Nerd of the Day** - Quem jogou mais games hoje? Agora sabes 👑
• **Player Profile** - Nova página de perfil com todo o histórico de matches

🔧 **Bug Fixes:**
• Fixed hero name bug (Slardar já não aparece como Shadow Shaman 😅)

👉 **Experimenta agora:** https://impetus-dota2.vercel.app
"""


async def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        return

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            embed = Embed(
                title="🎉 Impetus v0.2.0",
                description=ANNOUNCEMENT,
                color=0x9333ea,  # Brand purple
            )
            embed.set_footer(text="Professor Impetus • OpenIMP Scoring Engine")
            await channel.send(embed=embed)
            print("Announcement sent!")
        else:
            print(f"Error: Could not find channel {DISCORD_CHANNEL_ID}")
        await client.close()

    await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
