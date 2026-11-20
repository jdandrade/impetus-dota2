"""
Dota 2 Game State Integration (GSI) receiver.

Players who opt in drop a small cfg file into their Dota install; their own
game client then POSTs its state here every couple of seconds while they are
in a game.

For each game we keep ONE Discord post per player: a live scoreboard that is
edited in place as the game goes on, with a running feed of roasts triggered
by what the player does (see _detect_moments). When the game ends the post is
frozen with the result and the match is handed to
MatchTracker.process_finished_match, which posts the usual report cards.

GSI only describes the player's OWN hero while they are playing (Valve hides
everyone else), so tracked friends in the same game are found at the end, by
looking the match up by ID.

The Dota client waits for our response before sending its next update, so the
request handler only updates in-memory state and replies; everything slow
(Redis, Gemini, Discord) runs in background tasks.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from aiohttp import web

from app.config import TRACKED_PLAYERS, Settings
from app.services.opendota import HERO_NAMES

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 512 * 1024
TOKEN_CACHE_SECONDS = 60

STATE_PRE_GAME = "DOTA_GAMERULES_STATE_PRE_GAME"
STATE_IN_PROGRESS = "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"

# How often the live post is refreshed when nothing notable happens
REFRESH_SECONDS = 30
# A game whose client went silent this long is closed as "no result"
STALE_GAME_SECONDS = 600
# Minimum game time between two roasts
MIN_SECONDS_BETWEEN_MOMENTS = 120
# Roast lines shown while the game is live (all of them once it ends)
LIVE_FEED_LINES = 5
LIVE_STATE_TTL = 60 * 60 * 24

KILL_STREAK_MILESTONES = (5, 10)
DEATH_MILESTONES = (10, 15)
MULTI_KILL_COUNT = 3
MULTI_KILL_WINDOW = 20
DEATH_SPREE_COUNT = 3
DEATH_SPREE_WINDOW = 180
REBUY_DEATH_WINDOW = 90
UNSPENT_GOLD = 2000
LATE_MIDAS_CLOCK = 15 * 60
THERAPY_MIDAS_DEATHS = 4
MIDAS_IDLE_SECONDS = 45
MIDAS_IDLE_ROASTS = 1
NO_TP_AFTER_CLOCK = 10 * 60
NO_TP_SECONDS = 180
WAND_FULL_CHARGES = 10
# (game clock, min, max): last hits in [min, max) are worth a roast. Role is
# unknown mid-game, so anything below min is assumed to be a support.
LAST_HIT_CHECKPOINTS = ((10 * 60, 12, 35), (20 * 60, 40, 90))

MIDAS = "item_hand_of_midas"
RAPIER = "item_rapier"
WANDS = ("item_magic_wand", "item_holy_locket")

# Active items that could have saved a life; dying with one ready is a roast.
SAVE_ITEMS = {
    "item_black_king_bar": "BKB",
    "item_glimmer_cape": "Glimmer Cape",
    "item_force_staff": "Force Staff",
    "item_hurricane_pike": "Hurricane Pike",
    "item_ghost": "Ghost Scepter",
    "item_ethereal_blade": "Ethereal Blade",
    "item_cyclone": "Eul's",
    "item_wind_waker": "Wind Waker",
    "item_blade_mail": "Blade Mail",
    "item_lotus_orb": "Lotus Orb",
    "item_satanic": "Satanic",
    "item_manta": "Manta Style",
    "item_invis_sword": "Shadow Blade",
    "item_silver_edge": "Silver Edge",
    "item_pipe": "Pipe",
    "item_crimson_guard": "Crimson Guard",
    "item_mekansm": "Mekansm",
    "item_guardian_greaves": "Guardian Greaves",
    "item_bloodstone": "Bloodstone",
    "item_cheese": "Cheese",
    "item_faerie_fire": "Faerie Fire",
}

INVENTORY_SLOTS = ("slot0", "slot1", "slot2", "slot3", "slot4", "slot5", "neutral0")


@dataclass
class ItemState:
    ready: bool
    cooldown: float
    charges: int


@dataclass
class Snapshot:
    """The parts of one GSI update we use."""
    clock: int = 0
    game_state: str = ""
    team: str = ""
    radiant_score: int = 0
    dire_score: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    last_hits: int = 0
    denies: int = 0
    kill_streak: int = 0
    gold: int = 0
    gpm: int = 0
    xpm: int = 0
    level: int = 0
    alive: bool = True
    buyback_gold_spent: int = 0
    player_slot: Optional[int] = None
    items: dict = field(default_factory=dict)        # item name -> ItemState
    item_names: list = field(default_factory=list)   # display order
    has_items: bool = False                          # items block present
    has_tp: bool = False
    ult_ready: bool = False
    ult_cooldown: float = 1.0

    @property
    def kda(self) -> str:
        return f"{self.kills}/{self.deaths}/{self.assists}"


@dataclass
class LiveGame:
    """Everything we remember about one player's current game."""
    steam_id: str
    name: str
    match_id: str
    hero_name: str = ""
    snap: Optional[Snapshot] = None

    # Persisted in Redis so a restart continues the same post
    message_id: Optional[int] = None
    feed: list = field(default_factory=list)   # [clock string, roast]
    fired: set = field(default_factory=set)
    moments: int = 0

    ready: bool = False            # persisted state has been loaded
    loading: bool = False
    ended: bool = False
    result: Optional[str] = None   # "win" | "loss" | "unknown"
    last_seen: float = 0.0
    last_edit: float = 0.0
    refreshing: bool = False
    dirty: bool = False

    # Trigger bookkeeping (not persisted)
    last_moment_clock: float = -1e9
    kill_times: list = field(default_factory=list)
    death_times: list = field(default_factory=list)
    last_buyback_clock: Optional[int] = None
    midas_ready_since: Optional[int] = None
    midas_idle_roasts: int = 0
    no_tp_since: Optional[int] = None
    seen_events: set = field(default_factory=set)

    @property
    def redis_key(self) -> str:
        return f"gsi:{self.match_id}:{self.steam_id}:live"


def _clock_string(clock: float) -> str:
    clock = int(clock)
    sign = "-" if clock < 0 else ""
    clock = abs(clock)
    return f"{sign}{clock // 60}:{clock % 60:02d}"


def _int(value) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _item_display_name(item_name: str) -> str:
    return item_name.removeprefix("item_").replace("_", " ").title()


def parse_snapshot(data: dict) -> Snapshot:
    """Build a Snapshot from a GSI update (map/player/hero already validated)."""
    map_, player, hero = data["map"], data["player"], data["hero"]
    snap = Snapshot(
        clock=_int(map_.get("clock_time")),
        game_state=map_.get("game_state") or "",
        team=player.get("team_name") or "",
        radiant_score=_int(map_.get("radiant_score")),
        dire_score=_int(map_.get("dire_score")),
        kills=_int(player.get("kills")),
        deaths=_int(player.get("deaths")),
        assists=_int(player.get("assists")),
        last_hits=_int(player.get("last_hits")),
        denies=_int(player.get("denies")),
        kill_streak=_int(player.get("kill_streak")),
        gold=_int(player.get("gold")),
        gpm=_int(player.get("gpm")),
        xpm=_int(player.get("xpm")),
        level=_int(hero.get("level")),
        alive=hero.get("alive") is not False,
        buyback_gold_spent=_int(player.get("gold_spent_on_buybacks")),
        player_slot=player.get("player_slot") if isinstance(player.get("player_slot"), int) else None,
    )

    items = data.get("items")
    if isinstance(items, dict):
        snap.has_items = True
        for slot in INVENTORY_SLOTS:
            item = items.get(slot)
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name or name == "empty":
                continue
            cooldown = item.get("cooldown") or 0
            snap.items[name] = ItemState(
                ready=item.get("can_cast") is True and cooldown == 0,
                cooldown=cooldown,
                charges=_int(item.get("charges")),
            )
            snap.item_names.append(name)
        tp = items.get("teleport0")
        snap.has_tp = isinstance(tp, dict) and tp.get("name") not in (None, "", "empty")

    abilities = data.get("abilities")
    if isinstance(abilities, dict):
        for ability in abilities.values():
            if (
                isinstance(ability, dict)
                and ability.get("ultimate") is True
                and not ability.get("passive")
                and _int(ability.get("level")) > 0
            ):
                snap.ult_cooldown = ability.get("cooldown") or 0
                snap.ult_ready = ability.get("can_cast") is True and snap.ult_cooldown == 0
                break

    return snap


def build_live_embed(game: LiveGame) -> discord.Embed:
    """Render the live post for a game from its latest snapshot."""
    snap = game.snap or Snapshot()
    hero = game.hero_name or "?"

    if not game.ended:
        title = f"🔴 LIVE · {game.name} · {hero}"
        color = discord.Color.blurple()
    elif game.result == "win":
        title = f"🏁 {game.name} · {hero} · Victory"
        color = discord.Color.green()
    elif game.result == "loss":
        title = f"🏁 {game.name} · {hero} · Defeat"
        color = discord.Color.red()
    else:
        title = f"⚫ {game.name} · {hero} · left the game"
        color = discord.Color.dark_grey()

    feed = game.feed if game.ended else game.feed[-LIVE_FEED_LINES:]
    lines = [f"`{clock}` {text}" for clock, text in feed]
    # Embed descriptions are capped at 4096 characters: drop the oldest lines
    while lines and sum(len(line) + 1 for line in lines) > 3800:
        lines.pop(0)
    if lines:
        description = "\n".join(lines)
    elif game.ended:
        description = "_A clean game. Suspicious._"
    else:
        description = "_Watching. Waiting for something worth roasting…_"

    embed = discord.Embed(title=title, description=description, color=color)

    ours, theirs = snap.radiant_score, snap.dire_score
    if snap.team == "dire":
        ours, theirs = theirs, ours
    embed.add_field(name="Game time", value=f"⏱️ {_clock_string(snap.clock)}", inline=True)
    embed.add_field(name="Score", value=f"**{ours}** – {theirs}", inline=True)
    embed.add_field(name="KDA", value=f"⚔️ **{snap.kda}**", inline=True)
    embed.add_field(name="LH / DN", value=f"{snap.last_hits} / {snap.denies}", inline=True)
    embed.add_field(name="GPM / XPM", value=f"{snap.gpm} / {snap.xpm}", inline=True)
    embed.add_field(name="Level", value=str(snap.level), inline=True)
    if snap.item_names:
        embed.add_field(
            name="Items",
            value=", ".join(_item_display_name(n) for n in snap.item_names)[:1024],
            inline=False,
        )

    footer = "Professor Impetus · live from the game client"
    if game.ended and game.result in ("win", "loss"):
        footer = "Professor Impetus · report card follows"
    embed.set_footer(text=footer)
    return embed


class GSIServer:
    """HTTP endpoint for Dota 2 GSI updates and the live post they drive."""

    def __init__(self, bot, redis_store, gemini_client, match_tracker, settings: Settings):
        self.bot = bot
        self.redis = redis_store
        self.gemini = gemini_client
        self.tracker = match_tracker
        self.settings = settings

        self._games: dict[str, LiveGame] = {}
        # token -> (steam_id or None, expiry). Caches misses too, so a wrong
        # token cannot be used to hammer Redis.
        self._token_cache: dict[str, tuple[Optional[str], float]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._runner: Optional[web.AppRunner] = None
        self._watchdog: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ HTTP

    async def start(self) -> None:
        app = web.Application(client_max_size=MAX_BODY_BYTES)
        app.router.add_post("/gsi", self._handle_gsi)
        app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.settings.port).start()
        self._watchdog = asyncio.create_task(self._watch_stale_games())
        logger.info(f"GSI endpoint listening on port {self.settings.port} (POST /gsi)")

    async def stop(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
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
        Update the player's live game from one GSI update and spawn whatever
        it triggers. Must not await: it runs inside the request handler and
        has to keep per-player updates in order.
        """
        map_ = data.get("map")
        player = data.get("player")
        hero = data.get("hero")
        if not isinstance(map_, dict) or not isinstance(player, dict) or not isinstance(hero, dict):
            return

        # Only real games the player is actually playing: spectating has no
        # top-level "activity", demo and bot games have match ID 0, custom
        # games set customgamename.
        match_id = str(map_.get("matchid") or "0")
        if match_id == "0" or player.get("activity") != "playing" or map_.get("customgamename"):
            return

        game = self._games.get(steam_id)
        if game is None or game.match_id != match_id:
            if game is not None and not game.ended:
                self._close_without_result(game)
            game = LiveGame(steam_id=steam_id, name=TRACKED_PLAYERS[steam_id], match_id=match_id)
            self._games[steam_id] = game

        game.last_seen = time.monotonic()
        prev = game.snap
        snap = parse_snapshot(data)
        game.snap = snap

        hero_id = hero.get("id")
        if isinstance(hero_id, int) and hero_id > 0:
            game.hero_name = HERO_NAMES.get(hero_id, f"Hero #{hero_id}")

        if not game.ready:
            if not game.loading:
                game.loading = True
                self._spawn(self._load(game))
            return
        if game.ended:
            return

        win_team = map_.get("win_team")
        if win_team and win_team != "none":
            game.ended = True
            game.result = "win" if snap.team == win_team else "loss"
            self._spawn(self._finish(game))
            return

        # No post during hero selection / strategy time: the hero is not final
        if snap.game_state not in (STATE_PRE_GAME, STATE_IN_PROGRESS) or not game.hero_name:
            return

        if prev is not None and snap.game_state == STATE_IN_PROGRESS:
            moment = self._detect_moment(game, prev, snap, data.get("events"))
            if (
                moment
                and game.moments < self.settings.gsi_max_moments
                and snap.clock - game.last_moment_clock >= MIN_SECONDS_BETWEEN_MOMENTS
            ):
                game.moments += 1
                game.last_moment_clock = snap.clock
                self._spawn(self._roast(game, moment, snap))

        if game.message_id is None or time.monotonic() - game.last_edit >= REFRESH_SECONDS:
            self._request_refresh(game)

    def _detect_moment(
        self, game: LiveGame, prev: Snapshot, snap: Snapshot, events
    ) -> Optional[tuple[str, str]]:
        """
        Compare two consecutive snapshots and return the most roast-worthy
        thing that just happened, or None. Updates the game's trigger
        bookkeeping.
        
        Returns:
            (situation, fallback), both in Portuguese. `situation` follows
            the player's name in the roast prompt and may carry hints for
            the model. `fallback` is a short line shown as-is if no roast
            could be generated.
        """
        clock = snap.clock
        candidates: list[tuple[str, str]] = []  # most important first

        def once(key: str) -> bool:
            if key in game.fired:
                return False
            game.fired.add(key)
            return True

        # --- buyback (remembered for "bought back and died again")
        if snap.buyback_gold_spent > prev.buyback_gold_spent:
            game.last_buyback_clock = clock

        # --- deaths
        if snap.deaths > prev.deaths:
            game.death_times.append(clock)
            # Each kind of blunder is roasted once per game, so a player
            # who keeps dying the same way does not fill the post.
            reasons = []

            unused = [
                label for item, label in SAVE_ITEMS.items()
                if item in prev.items and prev.items[item].ready
                and item in snap.items and snap.items[item].cooldown == 0
                and once(f"unused:{item}")
            ]
            if unused:
                reasons.append(f"com {' e '.join(unused)} por usar")
            for wand in WANDS:
                if (
                    wand in prev.items and wand in snap.items
                    and prev.items[wand].charges >= WAND_FULL_CHARGES
                    and snap.items[wand].charges >= WAND_FULL_CHARGES
                    and once("wand")
                ):
                    reasons.append(f"com a Magic Wand cheia ({snap.items[wand].charges} cargas)")
                    break
            if prev.ult_ready and snap.ult_cooldown == 0 and once("ult"):
                reasons.append("com o ultimate por usar")
            if prev.gold >= UNSPENT_GOLD and once("gold"):
                reasons.append(f"com {prev.gold} de gold no bolso")
            if RAPIER in prev.items and once(f"rapier_death{snap.deaths}"):
                reasons.append("com a Divine Rapier na mão")
            if (
                game.last_buyback_clock is not None
                and clock - game.last_buyback_clock <= REBUY_DEATH_WINDOW
            ):
                reasons.append(f"{clock - game.last_buyback_clock}s depois do buyback")
                game.last_buyback_clock = None
            recent = [t for t in game.death_times if clock - t <= DEATH_SPREE_WINDOW]
            if len(recent) >= DEATH_SPREE_COUNT and once("spree"):
                reasons.append(f"pela {len(recent)}ª vez em {DEATH_SPREE_WINDOW // 60} minutos")
            for milestone in DEATH_MILESTONES:
                if snap.deaths >= milestone and once(f"deaths{milestone}"):
                    reasons.append(f"pela {snap.deaths}ª vez")

            if reasons:
                candidates.append((
                    f"acabou de morrer {', '.join(reasons)} ({snap.kda})",
                    f"💀 Morreu {reasons[0]}",
                ))

        # --- tips and aegis (events block)
        if isinstance(events, list) and snap.player_slot is not None:
            for event in events:
                if not isinstance(event, dict):
                    continue
                kind = event.get("event_type")
                event_key = (
                    kind, event.get("game_time"), event.get("sender_player_id"),
                    event.get("receiver_player_id"), event.get("player_id"),
                )
                if event_key in game.seen_events:
                    continue
                game.seen_events.add(event_key)
                if kind == "tip" and event.get("receiver_player_id") == snap.player_slot:
                    candidates.append((
                        "acabou de receber um tip de outro jogador (quase de certeza a gozar com ele)",
                        "💸 Recebeu um tip",
                    ))
                elif kind == "tip" and event.get("sender_player_id") == snap.player_slot:
                    candidates.append(("acabou de dar tip a outro jogador", "💸 Deu um tip"))
                elif kind == "aegis_picked_up" and event.get("player_id") == snap.player_slot:
                    how = "Roubou" if event.get("snatched") else "Apanhou"
                    candidates.append((f"{how.lower()} a Aegis", f"🛡️ {how} a Aegis"))

        # --- purchases
        if prev.has_items and snap.has_items:
            if MIDAS in snap.items and MIDAS not in prev.items and once("midas"):
                if clock >= LATE_MIDAS_CLOCK or snap.deaths >= THERAPY_MIDAS_DEATHS:
                    candidates.append((
                        f"comprou Hand of Midas aos {_clock_string(clock)} com {snap.kda} "
                        f"(therapy midas: comprar Midas para se sentir melhor em vez de ganhar o jogo)",
                        "🩹 Therapy Midas",
                    ))
            if RAPIER in snap.items and RAPIER not in prev.items and once(f"rapier{clock // 300}"):
                candidates.append((f"acabou de comprar uma Divine Rapier ({snap.kda})", "🗡️ Comprou Divine Rapier"))

        # --- kills
        if snap.kills > prev.kills:
            game.kill_times.extend([clock] * (snap.kills - prev.kills))
            recent = [t for t in game.kill_times if clock - t <= MULTI_KILL_WINDOW]
            if len(recent) >= MULTI_KILL_COUNT and once(f"multi{snap.kills}"):
                candidates.append((
                    f"fez {len(recent)} kills em {MULTI_KILL_WINDOW} segundos ({snap.kda})",
                    f"🔥 {len(recent)} kills em {MULTI_KILL_WINDOW}s",
                ))
                game.kill_times.clear()
        for milestone in KILL_STREAK_MILESTONES:
            if snap.kill_streak >= milestone and once(f"streak{milestone}"):
                candidates.append((
                    f"vai numa kill streak de {snap.kill_streak} sem morrer ({snap.kda})",
                    f"🔥 Kill streak de {snap.kill_streak}",
                ))

        # --- last hits at 10 and 20 minutes (cores only, see LAST_HIT_CHECKPOINTS)
        for checkpoint, low, high in LAST_HIT_CHECKPOINTS:
            if (
                prev.clock < checkpoint <= clock
                and low <= snap.last_hits < high
                and once("last_hits")
            ):
                candidates.append((
                    f"chegou aos {checkpoint // 60} minutos com apenas {snap.last_hits} last hits e {snap.gpm} GPM",
                    f"🌾 {snap.last_hits} last hits aos {checkpoint // 60} min",
                ))

        # --- Midas sitting off cooldown
        if MIDAS in snap.items and snap.items[MIDAS].ready and snap.alive:
            if game.midas_ready_since is None:
                game.midas_ready_since = clock
            elif (
                clock - game.midas_ready_since >= MIDAS_IDLE_SECONDS
                and game.midas_idle_roasts < MIDAS_IDLE_ROASTS
            ):
                candidates.append((
                    f"tem o Hand of Midas pronto há {clock - game.midas_ready_since} segundos e não o usa",
                    f"⏳ Midas parado há {clock - game.midas_ready_since}s",
                ))
                game.midas_idle_roasts += 1
                game.midas_ready_since = None
        else:
            game.midas_ready_since = None

        # --- walking around without a TP scroll
        if snap.has_items and not snap.has_tp and snap.alive and clock >= NO_TP_AFTER_CLOCK:
            if game.no_tp_since is None:
                game.no_tp_since = clock
            elif clock - game.no_tp_since >= NO_TP_SECONDS and once("no_tp"):
                candidates.append((
                    f"anda há {(clock - game.no_tp_since) // 60} minutos sem TP scroll aos {_clock_string(clock)}",
                    "🚶 Sem TP scroll",
                ))
        else:
            game.no_tp_since = None

        return candidates[0] if candidates else None

    # ------------------------------------------------------------ background

    async def _load(self, game: LiveGame) -> None:
        """Restore a game's persisted state (post ID, feed) after a restart."""
        try:
            raw = await self.redis.get_json(game.redis_key)
        except Exception as e:
            logger.error(f"Redis unavailable while loading live game for {game.name}: {e}")
            await asyncio.sleep(10)
            game.loading = False  # retried on a later update
            return

        if raw:
            game.message_id = raw.get("message_id")
            game.feed = [list(entry) for entry in raw.get("feed", [])]
            game.fired = set(raw.get("fired", []))
            game.moments = int(raw.get("moments", 0))
            if raw.get("ended"):
                game.ended = True
                game.result = raw.get("result")
            logger.info(f"[GSI] Resumed live game {game.match_id} for {game.name}")
        else:
            logger.info(f"[GSI] {game.name} is in match {game.match_id}")
        game.ready = True

    async def _save(self, game: LiveGame) -> None:
        try:
            await self.redis.set_json(
                game.redis_key,
                {
                    "message_id": game.message_id,
                    "feed": game.feed,
                    "fired": sorted(game.fired),
                    "moments": game.moments,
                    "ended": game.ended,
                    "result": game.result,
                },
                LIVE_STATE_TTL,
            )
        except Exception as e:
            logger.error(f"Redis unavailable while saving live game for {game.name}: {e}")

    def _request_refresh(self, game: LiveGame) -> None:
        """Redraw the live post soon. Edits for one game never overlap."""
        game.dirty = True
        if not game.refreshing:
            game.refreshing = True
            self._spawn(self._refresh(game))

    async def _refresh(self, game: LiveGame) -> None:
        try:
            while game.dirty:
                game.dirty = False
                game.last_edit = time.monotonic()
                embed = build_live_embed(game)
                if game.message_id is None:
                    game.message_id = await self.bot.send_embed(embed)
                    if game.message_id is not None:
                        await self._save(game)
                else:
                    await self.bot.edit_embed(game.message_id, embed)
        finally:
            game.refreshing = False

    async def _roast(self, game: LiveGame, moment: tuple[str, str], snap: Snapshot) -> None:
        situation, fallback = moment
        clock = _clock_string(snap.clock)
        logger.info(f"[GSI] moment for {game.name} in match {game.match_id} at {clock}: {situation}")
        comment = await self.gemini.generate_live_comment(
            player_name=game.name,
            hero_name=game.hero_name,
            clock=clock,
            situation=situation,
            previous=[text for _, text in game.feed[-4:]],
        )
        if not comment:
            comment = fallback
        game.feed.append([clock, comment])
        await self._save(game)
        self._request_refresh(game)

    async def _finish(self, game: LiveGame) -> None:
        logger.info(f"[GSI] {game.name} finished match {game.match_id}: {game.result}")
        await self._save(game)
        self._request_refresh(game)

        # Report cards (IMP score + roast) for this player and any other
        # tracked players in the same match, as soon as the details exist.
        try:
            if not await self.redis.claim_once(f"gsi:{game.match_id}:{game.steam_id}:end"):
                return
        except Exception as e:
            logger.error(f"Redis unavailable, leaving match {game.match_id} to the poller: {e}")
            return
        try:
            await self.tracker.process_finished_match(int(game.match_id), game.steam_id)
        except Exception as e:
            logger.exception(f"Error fast-tracking match {game.match_id}: {e}")

    def _close_without_result(self, game: LiveGame) -> None:
        """The client stopped reporting before the game ended (quit, crash)."""
        game.ended = True
        game.result = "unknown"
        logger.info(f"[GSI] {game.name} left match {game.match_id} without a result")
        if game.message_id is not None:
            self._spawn(self._save(game))
            self._request_refresh(game)

    async def _watch_stale_games(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.monotonic()
            for game in list(self._games.values()):
                if game.ready and not game.ended and now - game.last_seen > STALE_GAME_SECONDS:
                    self._close_without_result(game)
