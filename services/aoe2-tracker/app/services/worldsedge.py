"""
WorldsEdge API client for Age of Empires 2 DE match data.

Free API, no authentication required.
Successor to Relic Link API (aoe-api.reliclink.com).
"""

import logging
import asyncio
from dataclasses import dataclass, field

import aiohttp

from app.civilizations import get_civ_name, get_match_type

logger = logging.getLogger(__name__)

BASE_URL = "https://aoe-api.worldsedgelink.com"


@dataclass
class MatchPlayer:
    """A player in an AoE2 match."""
    profile_id: int
    civilization_id: int
    team_id: int
    result: int  # 1=win, 0=loss
    old_rating: int
    new_rating: int

    @property
    def won(self) -> bool:
        return self.result == 1

    @property
    def civ_name(self) -> str:
        return get_civ_name(self.civilization_id)

    @property
    def rating_change(self) -> int:
        return self.new_rating - self.old_rating


@dataclass
class AoE2Match:
    """A single AoE2 match from match history."""
    match_id: int
    map_name: str
    matchtype_id: int
    max_players: int
    description: str
    start_time: int  # unix timestamp
    completion_time: int  # unix timestamp
    players: list[MatchPlayer] = field(default_factory=list)

    @property
    def duration_seconds(self) -> int:
        return max(0, self.completion_time - self.start_time)

    @property
    def duration_str(self) -> str:
        """Format duration as MM:SS."""
        total = self.duration_seconds
        minutes = total // 60
        seconds = total % 60
        return f"{minutes}:{seconds:02d}"

    @property
    def game_mode(self) -> str:
        return get_match_type(self.matchtype_id)

    @property
    def is_ranked(self) -> bool:
        return self.matchtype_id in {6, 7, 8, 9, 13, 14}

    @property
    def is_team_game(self) -> bool:
        return self.max_players > 2

    @property
    def clean_map_name(self) -> str:
        """Strip .rms/.rms2 suffix and clean up map name.

        NOTE: For team games (2v2+), the WorldsEdge API returns the
        host's map preference, not the actual map played. The map name
        is only reliable for 1v1 matches.
        """
        name = self.map_name
        for suffix in (".rms2", ".rms"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        name = name.replace("_", " ")
        return name

    def get_teams(self) -> dict[int, list[MatchPlayer]]:
        """Group players by team ID."""
        teams: dict[int, list[MatchPlayer]] = {}
        for p in self.players:
            teams.setdefault(p.team_id, []).append(p)
        return teams


class RateLimiter:
    """Simple rate limiter with exponential backoff."""

    def __init__(self):
        self._consecutive_429s = 0
        self._backoff_until = 0.0

    def record_429(self):
        self._consecutive_429s += 1
        backoff = min(5 * (2 ** self._consecutive_429s), 300)
        self._backoff_until = asyncio.get_event_loop().time() + backoff
        logger.warning(f"Rate limited. Backing off for {backoff}s")

    def record_success(self):
        self._consecutive_429s = 0
        self._backoff_until = 0.0

    async def wait_if_needed(self):
        now = asyncio.get_event_loop().time()
        if now < self._backoff_until:
            wait = self._backoff_until - now
            logger.info(f"Rate limit backoff: waiting {wait:.1f}s")
            await asyncio.sleep(wait)


class WorldsEdgeClient:
    """Async client for the WorldsEdge AoE2 API."""

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None
        self._rate_limiter = RateLimiter()
        # Cache: profile_id → alias (display name)
        self._alias_cache: dict[int, str] = {}

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

    async def close(self):
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, endpoint: str, params: dict) -> dict | None:
        """Make a GET request with rate limiting."""
        await self._ensure_session()
        await self._rate_limiter.wait_if_needed()

        url = f"{BASE_URL}{endpoint}"
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 429:
                    self._rate_limiter.record_429()
                    return None
                if resp.status == 400:
                    logger.warning(f"Bad request for {url}: {await resp.text()}")
                    return None
                if resp.status != 200:
                    logger.error(f"WorldsEdge error {resp.status} for {url}")
                    return None
                self._rate_limiter.record_success()
                data = await resp.json()
                if data.get("result", {}).get("code") != 0:
                    logger.warning(f"API error: {data.get('result', {})}")
                    return None
                return data
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return None

    async def resolve_profile(self, profile_id: int) -> str | None:
        """Resolve a profile_id to a display name (alias)."""
        if profile_id in self._alias_cache:
            return self._alias_cache[profile_id]

        data = await self._get(
            "/community/leaderboard/getPersonalStat",
            {"title": "age2", "profile_ids": f"[{profile_id}]"},
        )
        if not data:
            return None

        for sg in data.get("statGroups", []):
            for member in sg.get("members", []):
                pid = member.get("profile_id")
                alias = member.get("alias", f"Player {pid}")
                if pid:
                    self._alias_cache[pid] = alias
                if pid == profile_id:
                    return alias
        return None

    async def get_recent_matches(self, profile_id: int) -> list[AoE2Match]:
        """Fetch a player's recent match history."""
        data = await self._get(
            "/community/leaderboard/getRecentMatchHistory",
            {"title": "age2", "profile_ids": f"[{profile_id}]"},
        )
        if not data:
            return []

        matches = []
        for m in data.get("matchHistoryStats", []):
            try:
                # Parse players from matchhistorymember (has rating data)
                players = []
                member_map = {}
                for member in m.get("matchhistorymember", []):
                    member_map[member["profile_id"]] = member

                for result in m.get("matchhistoryreportresults", []):
                    pid = result["profile_id"]
                    member = member_map.get(pid, {})
                    players.append(
                        MatchPlayer(
                            profile_id=pid,
                            civilization_id=result.get("civilization_id", 0),
                            team_id=result.get("teamid", 0),
                            result=result.get("resulttype", 0),
                            old_rating=member.get("oldrating", 0),
                            new_rating=member.get("newrating", 0),
                        )
                    )

                matches.append(
                    AoE2Match(
                        match_id=m["id"],
                        map_name=m.get("mapname", "Unknown"),
                        matchtype_id=m.get("matchtype_id", 0),
                        max_players=m.get("maxplayers", 0),
                        description=m.get("description", ""),
                        start_time=m.get("startgametime", 0),
                        completion_time=m.get("completiontime", 0),
                        players=players,
                    )
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to parse match: {e}")
                continue

        # Sort by start_time descending (most recent first)
        matches.sort(key=lambda x: x.start_time, reverse=True)
        return matches

    async def resolve_match_aliases(self, match: AoE2Match) -> dict[int, str]:
        """Resolve display names for all players in a match.
        Returns profile_id → alias mapping."""
        aliases = {}
        for p in match.players:
            if p.profile_id in self._alias_cache:
                aliases[p.profile_id] = self._alias_cache[p.profile_id]
            else:
                alias = await self.resolve_profile(p.profile_id)
                if alias:
                    aliases[p.profile_id] = alias
                else:
                    aliases[p.profile_id] = f"Player {p.profile_id}"
        return aliases
