"""
Pro match feed.

Posts once when a series starts in a notable tournament, with links to the
tournament's official streams, so the group can watch it as learning
material. It never shows scores or results: no spoilers.

Sources (both free, no API key):
- OpenDota `/live`: games currently being played, including league games
  with team names.
- Valve's public league endpoint: tournament name, tier, prize pool and
  stream URLs.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import discord
from discord import ui

logger = logging.getLogger(__name__)

OPENDOTA_LIVE_URL = "https://api.opendota.com/api/live"
LEAGUE_DATA_URL = "https://www.dota2.com/webapi/IDOTA2League/GetLeagueData/v001"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

# Valve league tiers: 1 = amateur, 2 and above = professional
MIN_LEAGUE_TIER = 2
# A game older than this is not "starting" any more (covers the draft and
# the broadcast delay); it is skipped rather than announced late.
MAX_START_AGE_SECONDS = 40 * 60
# OpenDota keeps finished games in the list for a while; ignore stale rows.
MAX_UPDATE_AGE_SECONDS = 10 * 60
LEAGUE_CACHE_SECONDS = 6 * 60 * 60
LEAGUE_RETRY_SECONDS = 10 * 60
SERIES_CLAIM_TTL_SECONDS = 3 * 24 * 60 * 60
MAX_STREAM_BUTTONS = 3

# Valve `broadcast_provider` values
PROVIDER_LABELS = {2: "Twitch", 3: "YouTube"}
PROVIDER_ORDER = {2: 0, 3: 1}


@dataclass
class League:
    league_id: int
    name: str
    tier: int
    prize_pool: int
    # (button label, URL), best first
    streams: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class LiveSeries:
    league_id: int
    series_id: int
    match_id: int
    radiant: str
    dire: str

    @property
    def claim_key(self) -> str:
        if self.series_id:
            return f"profeed:series:{self.series_id}"
        return f"profeed:match:{self.match_id}"


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_url(url) -> Optional[str]:
    """Return an https URL, or None if it is not usable as a link button."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or " " in url or len(url) > 500:
        return None
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    elif not url.startswith("https://"):
        if "://" in url:
            return None  # some other scheme
        url = "https://" + url
    return url if "." in url else None


def parse_streams(streams) -> list[tuple[str, str]]:
    """Pick up to MAX_STREAM_BUTTONS stream links: English first, Twitch first."""
    candidates = []
    for index, stream in enumerate(streams if isinstance(streams, list) else []):
        if not isinstance(stream, dict):
            continue
        url = _normalize_url(stream.get("stream_url"))
        if not url:
            continue
        provider = _as_int(stream.get("broadcast_provider"))
        language = _as_int(stream.get("language"))
        label = PROVIDER_LABELS.get(provider, "Stream")
        candidates.append((language != 0, PROVIDER_ORDER.get(provider, 2), index, label, url))

    picked: list[tuple[str, str]] = []
    seen_urls = set()
    for _, _, _, label, url in sorted(candidates):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        picked.append((label, url))
        if len(picked) == MAX_STREAM_BUTTONS:
            break
    return picked


def parse_league(league_id: int, data) -> Optional[League]:
    """Parse a GetLeagueData response."""
    info = data.get("info") if isinstance(data, dict) else None
    if not isinstance(info, dict) or not info.get("name"):
        return None
    prize = data.get("prize_pool") if isinstance(data.get("prize_pool"), dict) else {}
    return League(
        league_id=league_id,
        name=str(info["name"]).strip(),
        tier=_as_int(info.get("tier")),
        prize_pool=_as_int(prize.get("total_prize_pool")),
        streams=parse_streams(data.get("streams")),
    )


def find_starting_series(games, now: float) -> list[LiveSeries]:
    """
    Pick the league games from OpenDota's live list that have just started.

    One entry per series; finished, stale and long-running games are left out.
    """
    found: dict[str, LiveSeries] = {}
    for game in games if isinstance(games, list) else []:
        if not isinstance(game, dict):
            continue
        league_id = _as_int(game.get("league_id"))
        match_id = _as_int(game.get("match_id"))
        if not league_id or not match_id:
            continue
        if _as_int(game.get("deactivate_time")):
            continue  # already over
        if now - _as_int(game.get("last_update_time")) > MAX_UPDATE_AGE_SECONDS:
            continue
        if now - _as_int(game.get("activate_time")) > MAX_START_AGE_SECONDS:
            continue
        radiant = str(game.get("team_name_radiant") or "").strip()
        dire = str(game.get("team_name_dire") or "").strip()
        if not radiant or not dire:
            continue

        series = LiveSeries(
            league_id=league_id,
            series_id=_as_int(game.get("series_id")),
            match_id=match_id,
            radiant=radiant,
            dire=dire,
        )
        found.setdefault(series.claim_key, series)
    return list(found.values())


def build_series_embed(series: LiveSeries, league: League) -> discord.Embed:
    """The "series starting" post. Deliberately has no score or result."""
    radiant = discord.utils.escape_markdown(series.radiant)
    dire = discord.utils.escape_markdown(series.dire)
    embed = discord.Embed(
        title=f"🔴 {radiant} vs {dire}"[:256],
        description=f"**{discord.utils.escape_markdown(league.name)}** · a começar agora",
        color=0xDC2626,
    )
    embed.set_footer(text="Pro match • sem spoilers, o Professor não diz quem ganha")
    return embed


def build_stream_view(league: League) -> Optional[ui.View]:
    if not league.streams:
        return None
    view = ui.View(timeout=None)
    for label, url in league.streams:
        view.add_item(ui.Button(label=f"▶ {label}", style=discord.ButtonStyle.link, url=url))
    return view


class ProMatchFeed:
    """Polls for pro series that are starting and announces each one once."""

    def __init__(self, bot, redis_store, settings):
        self.bot = bot
        self.redis = redis_store
        self.settings = settings
        self._running = False
        # league ID -> (expires at, League or None if unknown/unavailable)
        self._leagues: dict[int, tuple[float, Optional[League]]] = {}

    async def start(self) -> None:
        self._running = True
        await self.bot.wait_until_ready()
        logger.info(
            f"Pro match feed started (every {self.settings.pro_feed_poll_seconds}s, "
            f"prize pool >= ${self.settings.pro_feed_min_prize_pool})"
        )
        while self._running:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Pro match feed poll failed: {e}")
            await asyncio.sleep(self.settings.pro_feed_poll_seconds)

    def stop(self) -> None:
        self._running = False

    async def poll_once(self) -> None:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            games = await self._get_json(session, OPENDOTA_LIVE_URL)
            if games is None:
                return
            for series in find_starting_series(games, time.time()):
                league = await self._get_league(session, series.league_id)
                if league is None or not self._is_notable(league):
                    continue
                await self._announce(series, league)

    def _is_notable(self, league: League) -> bool:
        return (
            league.tier >= MIN_LEAGUE_TIER
            and league.prize_pool >= self.settings.pro_feed_min_prize_pool
        )

    async def _announce(self, series: LiveSeries, league: League) -> None:
        try:
            if not await self.redis.claim_once(series.claim_key, SERIES_CLAIM_TTL_SECONDS):
                return
        except Exception as e:
            # Without Redis we cannot tell whether it was posted already
            logger.error(f"Redis unavailable, skipping pro match post: {e}")
            return

        message_id = await self.bot.send_embed(
            build_series_embed(series, league), view=build_stream_view(league)
        )
        if message_id is None:
            try:
                await self.redis.release_claim(series.claim_key)
            except Exception as e:
                logger.error(f"Could not release pro match claim: {e}")
            return
        logger.info(f"Pro match posted: {series.radiant} vs {series.dire} ({league.name})")

    async def _get_league(self, session: aiohttp.ClientSession, league_id: int) -> Optional[League]:
        cached = self._leagues.get(league_id)
        if cached and cached[0] > time.time():
            return cached[1]

        data = await self._get_json(session, LEAGUE_DATA_URL, {"league_id": league_id})
        league = parse_league(league_id, data) if data is not None else None
        ttl = LEAGUE_CACHE_SECONDS if league else LEAGUE_RETRY_SECONDS
        self._leagues[league_id] = (time.time() + ttl, league)
        return league

    @staticmethod
    async def _get_json(session: aiohttp.ClientSession, url: str, params: Optional[dict] = None):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"[ProFeed] {url} returned HTTP {resp.status}")
                    return None
                return await resp.json(content_type=None)
        except Exception as e:
            logger.warning(f"[ProFeed] {url} failed ({type(e).__name__})")
            return None
