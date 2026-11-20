"""
Dota 2 Game State Integration (GSI) receiver.

Players who opt in drop a small cfg file into their Dota install; their own
game client then POSTs its state here every couple of seconds while they are
in a game. That gives us what polling never can: the moment a game starts,
notable moments while it is running, and the result the instant it ends.

GSI only describes the player's OWN hero while they are playing (Valve hides
everyone else), so tracked friends in the same game are found once the game
ends, by looking the match up by ID (see MatchTracker.process_finished_match).

The Dota client waits for our response before sending its next update, so the
request handler only updates in-memory state and replies; everything slow
(Redis, Gemini, Discord) runs in background tasks.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from aiohttp import web

from app.config import TRACKED_PLAYERS, Settings
from app.services.opendota import HERO_NAMES

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 512 * 1024
TOKEN_CACHE_SECONDS = 60

STATE_PRE_GAME = "DOTA_GAMERULES_STATE_PRE_GAME"
STATE_IN_PROGRESS = "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"

# Only announce a start we actually witnessed, not a game joined half way
# through (e.g. the bot restarted or the cfg was installed mid-game).
START_ANNOUNCE_MAX_CLOCK = 300

KILL_STREAK_MILESTONES = (5, 10)
DEATH_MILESTONES = (5, 10)
LATE_MIDAS_CLOCK = 15 * 60
MIN_SECONDS_BETWEEN_MOMENTS = 180

MIDAS_ITEM = "item_hand_of_midas"


@dataclass
class LiveState:
    """What we remember about one player's current game."""
    match_id: str
    hero_name: str = ""
    start_handled: bool = False
    end_handled: bool = False
    moments: int = 0
    last_moment_clock: float = -1e9
    fired: set = field(default_factory=set)
    # None until we have seen one item snapshot for this game
    had_midas: Optional[bool] = None


def _clock_string(clock: float) -> str:
    clock = max(int(clock), 0)
    return f"{clock // 60}:{clock % 60:02d}"


def _has_item(items: dict, item_name: str) -> bool:
    return any(
        isinstance(slot, dict) and slot.get("name") == item_name
        for slot in items.values()
    )


class GSIServer:
    """HTTP endpoint for Dota 2 GSI updates and the live announcements they trigger."""

    def __init__(self, bot, redis_store, gemini_client, match_tracker, settings: Settings):
        self.bot = bot
        self.redis = redis_store
        self.gemini = gemini_client
        self.tracker = match_tracker
        self.settings = settings

        self._live: dict[str, LiveState] = {}
        # token -> (steam_id or None, expiry). Caches misses too, so a wrong
        # token cannot be used to hammer Redis.
        self._token_cache: dict[str, tuple[Optional[str], float]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._runner: Optional[web.AppRunner] = None

    # ------------------------------------------------------------------ HTTP

    async def start(self) -> None:
        app = web.Application(client_max_size=MAX_BODY_BYTES)
        app.router.add_post("/gsi", self._handle_gsi)
        app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.settings.port).start()
        logger.info(f"GSI endpoint listening on port {self.settings.port} (POST /gsi)")

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def _handle_gsi(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400)
        if not isinstance(data, dict):
            return web.Response(status=400)

        auth = data.get("auth")
        token = auth.get("token") if isinstance(auth, dict) else None
        steam_id = await self._resolve_token(token)
        if not steam_id:
            return web.Response(status=401)

        try:
            self._process(steam_id, data)
        except Exception as e:
            logger.exception(f"Error processing GSI update for {steam_id}: {e}")

        return web.Response(status=200)

    async def _resolve_token(self, token) -> Optional[str]:
        if not isinstance(token, str) or not token or len(token) > 128:
            return None

        cached = self._token_cache.get(token)
        if cached and cached[1] > time.monotonic():
            return cached[0]

        try:
            steam_id = await self.redis.get_gsi_player(token)
        except Exception as e:
            logger.error(f"Redis unavailable while checking GSI token: {e}")
            return None

        if steam_id not in TRACKED_PLAYERS:
            steam_id = None
        if len(self._token_cache) > 1000:
            self._token_cache.clear()
        self._token_cache[token] = (steam_id, time.monotonic() + TOKEN_CACHE_SECONDS)
        return steam_id

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error("GSI background task failed", exc_info=task.exception())

    # ----------------------------------------------------------- state logic

    def _process(self, steam_id: str, data: dict) -> None:
        """
        Update the player's live state from one GSI update and spawn any
        announcements it triggers. Must not await: it runs inside the request
        handler and has to keep per-player updates in order.
        """
        map_ = data.get("map")
        player = data.get("player")
        hero = data.get("hero")
        if not isinstance(map_, dict) or not isinstance(player, dict) or not isinstance(hero, dict):
            return

        # Only real matchmaking/lobby games the player is actually playing:
        # spectating has no top-level "activity", demo and bot games have
        # match ID 0, custom games set customgamename.
        match_id = str(map_.get("matchid") or "0")
        if match_id == "0" or player.get("activity") != "playing" or map_.get("customgamename"):
            return

        name = TRACKED_PLAYERS[steam_id]
        state = self._live.get(steam_id)
        if state is None or state.match_id != match_id:
            state = LiveState(match_id=match_id)
            self._live[steam_id] = state

        hero_id = hero.get("id") or 0
        if isinstance(hero_id, int) and hero_id > 0:
            state.hero_name = HERO_NAMES.get(hero_id, f"Hero #{hero_id}")

        game_state = map_.get("game_state")
        clock = map_.get("clock_time") or 0
        kills = player.get("kills") or 0
        deaths = player.get("deaths") or 0
        assists = player.get("assists") or 0

        # --- game end (checked first: nothing else matters after it)
        win_team = map_.get("win_team")
        if win_team and win_team != "none":
            if not state.end_handled:
                state.end_handled = True
                won = player.get("team_name") == win_team
                self._spawn(self._announce_end(
                    steam_id, name, state, won, f"{kills}/{deaths}/{assists}", _clock_string(clock)
                ))
            return

        # --- game start
        if (
            not state.start_handled
            and state.hero_name
            and game_state in (STATE_PRE_GAME, STATE_IN_PROGRESS)
        ):
            state.start_handled = True
            if clock < START_ANNOUNCE_MAX_CLOCK:
                self._spawn(self._announce_start(steam_id, name, state))

        if game_state != STATE_IN_PROGRESS:
            return

        # --- notable moments
        items = data.get("items")
        has_midas = _has_item(items, MIDAS_ITEM) if isinstance(items, dict) else None
        bought_midas = state.had_midas is False and has_midas is True
        if has_midas is not None:
            state.had_midas = has_midas

        moment: Optional[tuple[str, str]] = None  # (key, situation for the roast)
        kill_streak = player.get("kill_streak") or 0

        for milestone in KILL_STREAK_MILESTONES:
            key = f"streak{milestone}"
            if kill_streak >= milestone and key not in state.fired:
                state.fired.add(key)
                moment = (key, f"vai numa kill streak de {kill_streak} sem morrer ({kills}/{deaths}/{assists})")

        for milestone in DEATH_MILESTONES:
            key = f"deaths{milestone}"
            if deaths >= milestone and key not in state.fired:
                state.fired.add(key)
                # A handful of deaths is only worth a roast if they are feeding
                if milestone > DEATH_MILESTONES[0] or kills < 2:
                    moment = (key, f"já morreu {deaths} vezes e tem {kills} kills ({kills}/{deaths}/{assists})")

        if bought_midas and clock >= LATE_MIDAS_CLOCK and "midas" not in state.fired:
            state.fired.add("midas")
            moment = ("midas", f"acabou de comprar Hand of Midas aos {_clock_string(clock)} de jogo")

        if (
            moment
            and state.moments < self.settings.gsi_max_moments
            and clock - state.last_moment_clock >= MIN_SECONDS_BETWEEN_MOMENTS
        ):
            state.moments += 1
            state.last_moment_clock = clock
            self._spawn(self._announce_moment(steam_id, name, state, moment[0], moment[1], _clock_string(clock)))

    # --------------------------------------------------------- announcements

    async def _claim(self, state: LiveState, steam_id: str, event: str) -> bool:
        """Claim a one-off event in Redis so restarts cannot repeat it."""
        try:
            return await self.redis.claim_once(f"gsi:{state.match_id}:{steam_id}:{event}")
        except Exception as e:
            logger.error(f"Redis unavailable, skipping live announcement ({event}): {e}")
            return False

    async def _announce_start(self, steam_id: str, name: str, state: LiveState) -> None:
        if not await self._claim(state, steam_id, "start"):
            return
        logger.info(f"[GSI] {name} started match {state.match_id} as {state.hero_name}")
        await self.bot.send_live_message(
            f"🎮 **{name}** just started a game as **{state.hero_name}**"
        )

    async def _announce_moment(
        self, steam_id: str, name: str, state: LiveState, key: str, situation: str, clock: str
    ) -> None:
        if not await self._claim(state, steam_id, key):
            return
        logger.info(f"[GSI] moment for {name} in match {state.match_id}: {key}")
        comment = await self.gemini.generate_live_comment(name, state.hero_name, clock, situation)
        if not comment:
            comment = situation
        await self.bot.send_live_message(
            f"🔴 **LIVE** · **{name}** ({state.hero_name}, {clock}): {comment}"
        )

    async def _announce_end(
        self, steam_id: str, name: str, state: LiveState, won: bool, kda: str, clock: str
    ) -> None:
        if not await self._claim(state, steam_id, "end"):
            return
        logger.info(f"[GSI] {name} finished match {state.match_id}: {'win' if won else 'loss'}")

        result = "✅ won" if won else "❌ lost"
        hero = f" as **{state.hero_name}**" if state.hero_name else ""
        interim = await self.bot.send_live_message(
            f"🏁 **{name}** just {result}{hero} ({kda}, {clock}). Report card incoming…"
        )

        # Full report cards (IMP score + roast) for this player and any other
        # tracked players in the same match, as soon as the details exist.
        try:
            handled = await self.tracker.process_finished_match(int(state.match_id), steam_id)
        except Exception as e:
            logger.exception(f"Error fast-tracking match {state.match_id}: {e}")
            handled = False

        # The report card replaces the interim line. If it never came, the
        # line stays and the regular poller posts the card later.
        if handled and interim is not None:
            try:
                await interim.delete()
            except Exception as e:
                logger.warning(f"Could not delete interim result message: {e}")
