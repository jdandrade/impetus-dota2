"""
Release announcement.

On startup the bot posts the note for RELEASE_VERSION once. The version is
claimed in Redis, so restarts and redeploys never repeat it. To announce a
new release, bump RELEASE_VERSION and rewrite RELEASE_NOTES.
"""

import logging

import discord

logger = logging.getLogger(__name__)

RELEASE_VERSION = "0.3.0"

RELEASE_NOTES = """
🚀 **Impetus v0.3.0 Released!**

O Professor esteve calado uns dias. Voltou pior.

🔴 **LIVE Tracking (novo, opcional)**
• O Professor passa a ver os vossos jogos em direto. Um único post por jogo, atualizado ao vivo.
• Ele repara em coisas. Não vos digo quais. Vão descobrir da pior maneira.
• Para ativar: `/dota-live-setup` e seguir os 3 passos
• É o Game State Integration oficial da Valve: um ficheiro de texto, sem instalar nada

🕵️ **Smurf Check**
• O Professor agora investiga a equipa inimiga depois de cada jogo
• feAr, isto é para ti. Cuidado com o que desejas.

⚡ **Resultados mais rápidos**
• Os report cards chegam muito mais cedo
• Precisam de ter "Expose Public Match Data" ligado no Dota

🔧 **Bug Fixes:**
• O Professor já não repete o mesmo jogo vezes sem conta (pede desculpa, mas só desta vez)
"""


async def announce_release(bot, redis_store) -> None:
    """Post the current release note to the channel, once per version."""
    await bot.wait_until_ready()
    key = f"release:announced:{RELEASE_VERSION}"
    
    try:
        if not await redis_store.claim_once(key, ttl_seconds=None):
            return
    except Exception as e:
        # Without Redis we cannot know whether it was posted already
        logger.error(f"Redis unavailable, skipping release announcement: {e}")
        return
    
    embed = discord.Embed(
        title=f"🎉 Impetus v{RELEASE_VERSION}",
        description=RELEASE_NOTES,
        color=0x9333EA,  # Brand purple
    )
    embed.set_footer(text="Professor Impetus • OpenIMP Scoring Engine")
    
    if await bot.send_embed(embed) is None:
        # Not delivered: release the claim so the next start tries again
        try:
            await redis_store.release_claim(key)
        except Exception as e:
            logger.error(f"Could not release announcement claim: {e}")
        logger.error(f"Release announcement v{RELEASE_VERSION} could not be sent")
        return
    
    logger.info(f"Release announcement v{RELEASE_VERSION} sent")
