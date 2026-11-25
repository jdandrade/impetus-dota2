"""
Release announcement.

On startup the bot posts the note for RELEASE_VERSION once. The version is
claimed in Redis, so restarts and redeploys never repeat it. To announce a
new release, bump RELEASE_VERSION and rewrite RELEASE_NOTES.
"""

import logging

import discord

logger = logging.getLogger(__name__)

RELEASE_VERSION = "0.4.0"

RELEASE_NOTES = """
🚀 **Impetus v0.4.0 Released!**

O Professor andou a estudar. Infelizmente para vocês.

🔴 **LIVE Tracking: ainda só o feAr é que tem coragem**
• Até agora só o feAr ativou isto. Os restantes estão com medo de quê, exatamente?
• Ativar ficou mais fácil: `/dota-live-setup` e colar o vosso Dota ID
• O ID é o número no fim do vosso link do Stratz (`stratz.com/players/<ID>`), ou o Friend ID no perfil dentro do Dota. Também podem colar o link inteiro.
• Recebem um ficheiro de texto e 3 passos. É o Game State Integration oficial da Valve, não se instala nada.

👀 **O Professor repara em mais coisas**
• Muito mais coisas. Continuo sem vos dizer quais.
• E já não repete sempre a mesma piada.

🧾 **Um post por jogo**
• O post LIVE transforma-se no report card quando o jogo acaba. Menos spam, a mesma humilhação.

📺 **Pro matches**
• Quando começa uma série num torneio a sério, o Professor avisa e deixa os links das streams
• Sem spoilers: nunca diz quem ganhou. Vejam e aprendam qualquer coisa.
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
