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
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from aiohttp import web

from app.config import TRACKED_PLAYERS, Settings
from app.services.opendota import HERO_NAMES

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 512 * 1024
STEAM_ID64_BASE = 76561197960265728
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

# Info lines (Roshan, aegis, smoke, pause, ...) are posted as-is: no AI roast,
# and they do not use up the roast budget. This caps them per game.
INFO_LINES_MAX = 8
SMOKE_CHECK_SECONDS = 3
ROSHAN_RESPAWN_SECONDS = (8 * 60, 11 * 60)
AEGIS_SECONDS = 5 * 60
OPENING_BOUNTY_CLOCK = 120
# (game clock, tier). Normal-game timings; tier 1 is there from the start.
NEUTRAL_TIERS = ((15 * 60, 2), (25 * 60, 3), (35 * 60, 4), (60 * 60, 5))
TREADS_INT_MANA = 120
SMOKE_EVENT = "CHAT_MESSAGE_SMOKE_ACTIVATED"

MIDAS = "item_hand_of_midas"
RAPIER = "item_rapier"
AEGIS = "item_aegis"
TREADS = "item_power_treads"
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

# Short lines shown as-is: for info lines always, for roasts only when no AI
# roast could be generated. One is picked at random so games do not all read
# the same.
LINES = {
    "death": ("💀 Morreu {reason}", "💀 Foi ao chão {reason}", "💀 Caiu {reason}", "💀 Mais uma morte, {reason}"),
    "first_blood": ("🩸 Deu o first blood", "🩸 First blood... para o inimigo", "🩸 Abriu o marcador, do lado errado"),
    "tip_received": ("💸 Recebeu um tip", "💸 Levou com um tip", "💸 Tip recebido. Não era elogio."),
    "tip_sent": ("💸 Deu um tip", "💸 Mandou um tip", "💸 Anda a distribuir tips"),
    "aegis_mine": ("🛡️ Apanhou a Aegis", "🛡️ Aegis no bolso"),
    "aegis_mine_snatched": ("🛡️ Roubou a Aegis", "🛡️ Aegis roubada, à ladrão"),
    "aegis_mine_denied": ("🛡️ Negou a Aegis", "🛡️ Aegis negada. Ninguém fica com ela."),
    "aegis_expired": ("🛡️ Deixou a Aegis expirar", "🛡️ 5 minutos de Aegis para nada", "🛡️ Aegis fora de prazo"),
    "therapy_midas": ("🩹 Therapy Midas", "🩹 Midas para se sentir melhor", "🩹 Midas de consolação"),
    "rapier": ("🗡️ Comprou Divine Rapier", "🗡️ Rapier. Vai correr bem.", "🗡️ All-in: Divine Rapier"),
    "multi_kill": ("🔥 {n} kills em {s}s", "🔥 {n} de seguida em {s}s", "🔥 Limpou {n} em {s}s"),
    "streak": ("🔥 Kill streak de {n}", "🔥 {n} kills sem morrer", "🔥 Vai em {n} seguidas"),
    "last_hits": ("🌾 {n} last hits aos {m} min", "🌾 Aos {m} min: {n} last hits", "🌾 {n} creeps em {m} minutos"),
    "midas_idle": ("⏳ Midas parado há {s}s", "⏳ Midas pronto há {s}s, a apanhar pó", "⏳ Usa o Midas ({s}s parado)"),
    "midas_late": ("⏳ Midas finalmente usado, {s}s atrasado", "⏳ Lembrou-se do Midas, {s}s depois"),
    "no_tp": ("🚶 Sem TP scroll", "🚶 Onde está o TP?", "🚶 A pé, sem TP"),
    "tp_found": ("🌀 Finalmente comprou TP, {s}s depois", "🌀 TP comprado. Só demorou {s}s."),
    "tp_death": ("🌀 Só arranjou TP porque morreu ({s}s sem ele)", "🌀 Morreu e lá comprou o TP, {s}s depois"),
    "smoke_fomo": ("🌫️ A equipa fez smoke sem ele", "🌫️ Smoke gank... e ele ficou em casa", "🌫️ Ficou de fora do smoke"),
    # info lines
    "smoked": ("🌫️ Em smoke. Vem aí gank.", "🌫️ Smoke ativo", "🌫️ Desapareceu do mapa (smoke)"),
    "pause": ("⏸️ Pausa. Caiu uma bomba em {city}.",),
    "roshan_ours": ("🐲 Roshan morto pela nossa equipa · volta entre {lo} e {hi}",),
    "roshan_theirs": ("🐲 O inimigo matou o Roshan · volta entre {lo} e {hi}",),
    "aegis_ours": ("🛡️ Aegis para a nossa equipa",),
    "aegis_ours_snatched": ("🛡️ A nossa equipa roubou a Aegis",),
    "aegis_theirs": ("🛡️ Aegis para o inimigo",),
    "aegis_theirs_snatched": ("🛡️ O inimigo roubou a Aegis",),
    "aegis_denied": ("🛡️ Aegis negada",),
    "bounties": ("💰 Bounties iniciais: {n}/4",),
    "neutral": ("🎁 Neutral items de tier {n} disponíveis",),
    "treads": ("👟 Trocou os treads {n}x e poupou {mana} de mana",),
}


# Where the "bomb" fell when somebody pauses
PAUSE_CITIES = (
    "Chelyabinsk", "Novosibirsk", "Omsk", "Minsk", "Belgrado", "Sófia", "Bucareste",
    "Varsóvia", "Bratislava", "Zagreb", "Sarajevo", "Skopje", "Chisinau", "Vladivostok",
    "Krasnoyarsk", "Plovdiv", "Novi Sad", "Katowice",
)


def _line(key: str, **values) -> str:
    return random.choice(LINES[key]).format(**values)


@dataclass
class Moment:
    """Something that just happened and belongs in the live post."""
    # Follows the player's name in the roast prompt; may carry model hints
    situation: str
    # Shown as-is for info lines, or when no roast could be generated
    fallback: str
    # False: an info line, posted as-is without an AI roast
    roast: bool = True


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
    smoked: bool = False
    paused: bool = False
    mana: int = 0
    max_mana: int = 0
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
    info_lines: int = 0

    ready: bool = False            # persisted state has been loaded
    loading: bool = False
    ended: bool = False
    result: Optional[str] = None   # "win" | "loss" | "unknown"
    replaced: bool = False         # the post now shows the report card
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
    midas_told_since: Optional[int] = None   # idle Midas was called out
    no_tp_told_since: Optional[int] = None   # missing TP was called out
    smoke_check_clock: Optional[int] = None  # a teammate just used smoke
    aegis_since: Optional[int] = None
    opening_bounties: int = 0
    treads_mana_at_toggle: Optional[int] = None
    tread_toggles: int = 0
    tread_mana_saved: int = 0
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
        smoked=hero.get("smoked") is True,
        paused=map_.get("paused") is True,
        mana=_int(hero.get("mana")),
        max_mana=_int(hero.get("max_mana")),
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
        footer = "Professor Impetus · report card loading…"
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
        self._foreign_accounts: set[tuple[str, str]] = set()
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

        # The token only says whose cfg file this is. The file lives in the
        # Dota install, so it is sent for ANY Steam account that plays on
        # that PC: only track games played on the token owner's own account.
        if not self._is_own_account(steam_id, player):
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
            if game.tread_toggles:
                game.feed.append([
                    _clock_string(snap.clock),
                    _line("treads", n=game.tread_toggles, mana=game.tread_mana_saved),
                ])
            self._spawn(self._finish(game))
            return

        # No post during hero selection / strategy time: the hero is not final
        if snap.game_state not in (STATE_PRE_GAME, STATE_IN_PROGRESS) or not game.hero_name:
            return

        if prev is not None and snap.game_state == STATE_IN_PROGRESS:
            moments = self._detect_moments(game, prev, snap, data.get("events"))

            info = [m.fallback for m in moments if not m.roast]
            info = info[:max(0, INFO_LINES_MAX - game.info_lines)]
            if info:
                game.info_lines += len(info)
                clock = _clock_string(snap.clock)
                game.feed.extend([clock, line] for line in info)
                self._spawn(self._save(game))
                self._request_refresh(game)

            moment = next((m for m in moments if m.roast), None)
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

    def _is_own_account(self, steam_id: str, player: dict) -> bool:
        """True if the account playing is the one the token was issued for."""
        playing = str(player.get("steamid") or "")
        if not playing:
            account_id = str(player.get("accountid") or "")
            if account_id.isdigit():
                playing = str(int(account_id) + STEAM_ID64_BASE)
        if playing == steam_id:
            return True
        
        # Log each foreign account once, not on every update
        if (steam_id, playing) not in self._foreign_accounts:
            if len(self._foreign_accounts) > 100:
                self._foreign_accounts.clear()
            self._foreign_accounts.add((steam_id, playing))
            logger.info(
                f"[GSI] Ignoring updates sent with {TRACKED_PLAYERS[steam_id]}'s token "
                f"from a different Steam account ({playing or 'unknown'})"
            )
        return False

    def _detect_moments(
        self, game: LiveGame, prev: Snapshot, snap: Snapshot, events
    ) -> list[Moment]:
        """
        Compare two consecutive snapshots and return what just happened,
        most roast-worthy first (text in Portuguese). Updates the game's
        trigger bookkeeping.

        The caller roasts at most the first Moment with roast=True and posts
        every info Moment (roast=False) as-is.
        """
        clock = snap.clock
        candidates: list[Moment] = []  # most important first
        ours, theirs = snap.radiant_score, snap.dire_score
        if snap.team == "dire":
            ours, theirs = theirs, ours

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

            first_blood = (
                snap.team in ("radiant", "dire") and ours == 0 and theirs == 1
                and once("first_blood")
            )
            if first_blood:
                reasons.append("e deu o first blood ao inimigo")

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
            if prev.kill_streak >= KILL_STREAK_MILESTONES[0]:
                reasons.append(f"perdendo a kill streak de {prev.kill_streak}")

            if reasons:
                candidates.append(Moment(
                    f"acabou de morrer {', '.join(reasons)} ({snap.kda})",
                    _line("first_blood") if first_blood else _line("death", reason=reasons[0]),
                ))

        # --- tips, Roshan, aegis, bounties, smoke (events block)
        if isinstance(events, list) and snap.player_slot is not None:
            for event in events:
                if not isinstance(event, dict):
                    continue
                kind = event.get("event_type")
                payload = event.get("data")
                event_key = (
                    kind, event.get("game_time"), event.get("sender_player_id"),
                    event.get("receiver_player_id"), event.get("player_id"),
                    payload if isinstance(payload, str) else None,
                )
                if event_key in game.seen_events:
                    continue
                game.seen_events.add(event_key)
                moment = self._event_moment(game, snap, kind, event)
                if moment:
                    candidates.append(moment)

        # --- opening bounty runes (counted from the events above)
        if clock > OPENING_BOUNTY_CLOCK + 15 and game.opening_bounties and once("bounties"):
            candidates.append(Moment("", _line("bounties", n=min(game.opening_bounties, 4)), roast=False))

        # --- smoke: a teammate used it a moment ago; did we get left behind?
        if game.smoke_check_clock is not None and clock >= game.smoke_check_clock:
            game.smoke_check_clock = None
            if snap.alive and not snap.smoked and once(f"smoke_fomo{clock // 600}"):
                candidates.append(Moment(
                    "ficou de fora: a equipa usou Smoke of Deceit e foi gankar sem ele",
                    _line("smoke_fomo"),
                ))
        if snap.smoked and not prev.smoked and once(f"smoked{clock // 600}"):
            candidates.append(Moment("", _line("smoked"), roast=False))

        # --- pause
        if snap.paused and not prev.paused and once("pause"):
            candidates.append(Moment("", _line("pause", city=random.choice(PAUSE_CITIES)), roast=False))

        # --- neutral item tiers
        for tier_clock, tier in NEUTRAL_TIERS:
            if prev.clock < tier_clock <= clock and once(f"neutral{tier}"):
                candidates.append(Moment("", _line("neutral", n=tier), roast=False))

        # --- Power Treads toggling (summed up in one line when the game ends)
        if TREADS in snap.items and snap.max_mana and prev.max_mana:
            change = snap.max_mana - prev.max_mana
            if change == TREADS_INT_MANA:
                game.treads_mana_at_toggle = snap.mana
            elif change == -TREADS_INT_MANA and game.treads_mana_at_toggle is not None:
                saved = game.treads_mana_at_toggle - snap.mana - TREADS_INT_MANA
                game.treads_mana_at_toggle = None
                if saved > 0:
                    game.tread_toggles += 1
                    game.tread_mana_saved += saved

        # --- Aegis held until it expired
        if prev.has_items and snap.has_items:
            if AEGIS in snap.items:
                if game.aegis_since is None:
                    game.aegis_since = clock
            elif game.aegis_since is not None:
                held = clock - game.aegis_since
                game.aegis_since = None
                if held >= AEGIS_SECONDS - 10 and snap.alive and prev.alive:
                    candidates.append(Moment(
                        "deixou a Aegis expirar sem a usar (5 minutos com ela e nada)",
                        _line("aegis_expired"),
                    ))

        # --- purchases
        if prev.has_items and snap.has_items:
            if MIDAS in snap.items and MIDAS not in prev.items and once("midas"):
                if clock >= LATE_MIDAS_CLOCK or snap.deaths >= THERAPY_MIDAS_DEATHS:
                    candidates.append(Moment(
                        f"comprou Hand of Midas aos {_clock_string(clock)} com {snap.kda} "
                        f"(therapy midas: comprar Midas para se sentir melhor em vez de ganhar o jogo)",
                        _line("therapy_midas"),
                    ))
            if RAPIER in snap.items and RAPIER not in prev.items and once(f"rapier{clock // 300}"):
                candidates.append(Moment(f"acabou de comprar uma Divine Rapier ({snap.kda})", _line("rapier")))

        # --- kills
        if snap.kills > prev.kills:
            game.kill_times.extend([clock] * (snap.kills - prev.kills))
            recent = [t for t in game.kill_times if clock - t <= MULTI_KILL_WINDOW]
            if len(recent) >= MULTI_KILL_COUNT and once(f"multi{snap.kills}"):
                candidates.append(Moment(
                    f"fez {len(recent)} kills em {MULTI_KILL_WINDOW} segundos ({snap.kda})",
                    _line("multi_kill", n=len(recent), s=MULTI_KILL_WINDOW),
                ))
                game.kill_times.clear()
        for milestone in KILL_STREAK_MILESTONES:
            if snap.kill_streak >= milestone and once(f"streak{milestone}"):
                candidates.append(Moment(
                    f"vai numa kill streak de {snap.kill_streak} sem morrer ({snap.kda})",
                    _line("streak", n=snap.kill_streak),
                ))

        # --- last hits at 10 and 20 minutes (cores only, see LAST_HIT_CHECKPOINTS)
        for checkpoint, low, high in LAST_HIT_CHECKPOINTS:
            if (
                prev.clock < checkpoint <= clock
                and low <= snap.last_hits < high
                and once("last_hits")
            ):
                candidates.append(Moment(
                    f"chegou aos {checkpoint // 60} minutos com apenas {snap.last_hits} last hits e {snap.gpm} GPM",
                    _line("last_hits", n=snap.last_hits, m=checkpoint // 60),
                ))

        # --- Midas sitting off cooldown
        if MIDAS in snap.items and snap.items[MIDAS].ready and snap.alive:
            if game.midas_ready_since is None:
                game.midas_ready_since = clock
            elif (
                clock - game.midas_ready_since >= MIDAS_IDLE_SECONDS
                and game.midas_idle_roasts < MIDAS_IDLE_ROASTS
            ):
                idle = clock - game.midas_ready_since
                candidates.append(Moment(
                    f"tem o Hand of Midas pronto há {idle} segundos e não o usa",
                    _line("midas_idle", s=idle),
                ))
                game.midas_idle_roasts += 1
                game.midas_told_since = game.midas_ready_since
                game.midas_ready_since = None
        else:
            # Called out earlier and now on cooldown: it was finally used
            if (
                game.midas_told_since is not None
                and MIDAS in snap.items and snap.items[MIDAS].cooldown > 0
            ):
                late = clock - game.midas_told_since
                game.midas_told_since = None
                candidates.append(Moment(
                    f"usou finalmente o Hand of Midas, {late} segundos depois de estar pronto",
                    _line("midas_late", s=late),
                ))
            game.midas_ready_since = None

        # --- walking around without a TP scroll
        if snap.has_items and snap.has_tp and game.no_tp_told_since is not None:
            # Called out earlier and now has one
            without = clock - game.no_tp_told_since
            game.no_tp_told_since = None
            if snap.alive:
                candidates.append(Moment(
                    f"finalmente comprou um TP scroll, depois de {without} segundos sem nenhum",
                    _line("tp_found", s=without),
                ))
            else:
                candidates.append(Moment(
                    f"só arranjou um TP scroll porque morreu, depois de {without} segundos sem nenhum",
                    _line("tp_death", s=without),
                ))
        if snap.has_items and not snap.has_tp and snap.alive and clock >= NO_TP_AFTER_CLOCK:
            if game.no_tp_since is None:
                game.no_tp_since = clock
            elif clock - game.no_tp_since >= NO_TP_SECONDS and once("no_tp"):
                candidates.append(Moment(
                    f"anda há {(clock - game.no_tp_since) // 60} minutos sem TP scroll aos {_clock_string(clock)}",
                    _line("no_tp"),
                ))
                game.no_tp_told_since = game.no_tp_since
        else:
            game.no_tp_since = None

        return candidates

    def _event_moment(self, game: LiveGame, snap: Snapshot, kind, event: dict) -> Optional[Moment]:
        """Turn one new entry of the GSI events block into a Moment, if any."""
        me = snap.player_slot
        clock = snap.clock

        def side_of(slot) -> Optional[str]:
            # Event player IDs are 0-4 for Radiant and 5-9 for Dire
            if not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot <= 9:
                return None
            return "radiant" if slot <= 4 else "dire"

        if kind == "tip":
            if event.get("receiver_player_id") == me:
                return Moment(
                    "acabou de receber um tip de outro jogador (quase de certeza a gozar com ele)",
                    _line("tip_received"),
                )
            if event.get("sender_player_id") == me:
                return Moment("acabou de dar tip a outro jogador", _line("tip_sent"))
            return None

        if kind == "roshan_killed":
            team = event.get("killed_by_team")
            if team not in ("radiant", "dire"):
                return None
            lo, hi = (_clock_string(clock + s) for s in ROSHAN_RESPAWN_SECONDS)
            key = "roshan_ours" if team == snap.team else "roshan_theirs"
            return Moment("", _line(key, lo=lo, hi=hi), roast=False)

        if kind == "aegis_picked_up":
            snatched = bool(event.get("snatched"))
            holder = event.get("player_id")
            if holder == me:
                return Moment(
                    "roubou a Aegis" if snatched else "apanhou a Aegis",
                    _line("aegis_mine_snatched" if snatched else "aegis_mine"),
                )
            side = side_of(holder)
            if side is None:
                return None
            key = "aegis_ours" if side == snap.team else "aegis_theirs"
            return Moment("", _line(key + ("_snatched" if snatched else "")), roast=False)

        if kind == "aegis_denied":
            if event.get("player_id") == me:
                return Moment("negou a Aegis (destruiu-a em vez de a apanhar)", _line("aegis_mine_denied"))
            return Moment("", _line("aegis_denied"), roast=False)

        if kind == "bounty_rune_pickup":
            if clock <= OPENING_BOUNTY_CLOCK and event.get("team") == snap.team:
                game.opening_bounties += 1
            return None

        if kind == "generic_event":
            try:
                payload = json.loads(event.get("data") or "{}")
            except (TypeError, ValueError):
                return None
            if not isinstance(payload, dict) or payload.get("type") != SMOKE_EVENT:
                return None
            caster = payload.get("playerid1")
            # Our own smoke is covered by the "smoked" line
            if caster != me and side_of(caster) == snap.team:
                game.smoke_check_clock = clock + SMOKE_CHECK_SECONDS
            return None

        return None

    # ------------------------------------------------------------ background

    async def take_live_post(self, steam_id: str, match_id: int) -> Optional[tuple[int, list]]:
        """
        Hand a player's live post for a match over to the report card.
        
        Called by the match tracker just before it posts a report card, so
        the card can replace the live post instead of adding a second
        message. After this the live post is never redrawn again.
        
        Returns:
            (message ID, feed of [clock, roast] lines), or None if the
            player has no live post for that match.
        """
        game = self._games.get(steam_id)
        if game is not None and game.match_id == str(match_id):
            if game.message_id is None:
                return None
            game.replaced = True
            # Let a redraw that is already on its way to Discord land first,
            # so it cannot overwrite the report card afterwards.
            while game.refreshing:
                await asyncio.sleep(0.05)
            return game.message_id, list(game.feed)
        
        # Not in memory (restart since the game): use the persisted state
        try:
            raw = await self.redis.get_json(f"gsi:{match_id}:{steam_id}:live")
        except Exception as e:
            logger.error(f"Redis unavailable while looking up live post: {e}")
            return None
        if raw and raw.get("message_id"):
            return raw["message_id"], [list(entry) for entry in raw.get("feed", [])]
        return None

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
            game.info_lines = int(raw.get("info_lines", 0))
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
                    "info_lines": game.info_lines,
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
            # Once the post has become the report card it is no longer ours
            while game.dirty and not game.replaced:
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

    async def _roast(self, game: LiveGame, moment: Moment, snap: Snapshot) -> None:
        situation, fallback = moment.situation, moment.fallback
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
        # Show the frozen result first; the report card replaces it below
        self._request_refresh(game)
        while game.refreshing:
            await asyncio.sleep(0.05)

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
