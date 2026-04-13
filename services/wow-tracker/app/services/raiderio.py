"""
Raider.IO API client for WoW Mythic+ data.

Free API, no authentication required.
Docs: https://raider.io/api
"""

import logging
import asyncio
from dataclasses import dataclass, field

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://raider.io/api/v1"

# Current M+ season identifier
CURRENT_SEASON = "season-mn-1"


@dataclass
class GroupMember:
    """A player in a Mythic+ group."""
    name: str
    realm: str
    class_name: str
    spec_name: str
    role: str  # tank, healer, dps


@dataclass
class MythicPlusRun:
    """A single Mythic+ dungeon run from character profile."""
    keystone_run_id: int
    dungeon: str
    short_name: str
    mythic_level: int
    clear_time_ms: int
    par_time_ms: int
    num_keystone_upgrades: int  # 0=depleted, 1=timed, 2=+2, 3=+3
    completed_at: str  # ISO timestamp
    affixes: list[dict]  # [{name, description}]
    score: float
    spec_name: str
    role: str  # tank, healer, dps
    url: str
    background_image_url: str

    @property
    def is_timed(self) -> bool:
        return self.num_keystone_upgrades > 0

    @property
    def time_diff_pct(self) -> float:
        """Percentage over/under par time. Negative = under (good)."""
        return ((self.clear_time_ms - self.par_time_ms) / self.par_time_ms) * 100

    @property
    def clear_time_str(self) -> str:
        """Format clear time as MM:SS."""
        total_seconds = self.clear_time_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    @property
    def par_time_str(self) -> str:
        """Format par time as MM:SS."""
        total_seconds = self.par_time_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"


@dataclass
class RunDetails:
    """Full details of a Mythic+ run from the run-details endpoint."""
    keystone_run_id: int
    dungeon: str
    mythic_level: int
    clear_time_ms: int
    par_time_ms: int
    num_chests: int
    score: float
    roster: list[GroupMember] = field(default_factory=list)
    deaths: list[dict] = field(default_factory=list)
    total_deaths: int = 0


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


class RaiderIOClient:
    """Async client for the Raider.IO API."""

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None
        self._rate_limiter = RateLimiter()

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
                    logger.error(f"Raider.IO error {resp.status} for {url}")
                    return None
                self._rate_limiter.record_success()
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return None

    async def get_recent_runs(
        self, name: str, realm: str, region: str
    ) -> list[MythicPlusRun]:
        """Fetch a character's recent Mythic+ runs."""
        data = await self._get(
            "/characters/profile",
            {
                "region": region,
                "realm": realm,
                "name": name,
                "fields": "mythic_plus_recent_runs",
            },
        )
        if not data:
            return []

        runs = []
        for run_data in data.get("mythic_plus_recent_runs", []):
            try:
                spec = run_data.get("spec", {})
                runs.append(
                    MythicPlusRun(
                        keystone_run_id=run_data["keystone_run_id"],
                        dungeon=run_data["dungeon"],
                        short_name=run_data["short_name"],
                        mythic_level=run_data["mythic_level"],
                        clear_time_ms=run_data["clear_time_ms"],
                        par_time_ms=run_data["par_time_ms"],
                        num_keystone_upgrades=run_data["num_keystone_upgrades"],
                        completed_at=run_data["completed_at"],
                        affixes=[
                            {"name": a["name"], "description": a.get("description", "")}
                            for a in run_data.get("affixes", [])
                        ],
                        score=run_data.get("score", 0.0),
                        spec_name=spec.get("name", "Unknown"),
                        role=run_data.get("role", spec.get("role", "dps")),
                        url=run_data.get("url", ""),
                        background_image_url=run_data.get("background_image_url", ""),
                    )
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to parse run: {e}")
                continue

        return runs

    async def get_run_details(
        self, run_id: int, season: str = CURRENT_SEASON
    ) -> RunDetails | None:
        """Fetch full details for a specific run (roster, deaths)."""
        data = await self._get(
            "/mythic-plus/run-details",
            {"season": season, "id": str(run_id)},
        )
        if not data:
            return None

        # Parse roster
        roster = []
        for member in data.get("roster", []):
            char = member.get("character", {})
            class_info = char.get("class", {})
            spec_info = char.get("spec", {})
            realm_info = char.get("realm", {})

            roster.append(
                GroupMember(
                    name=char.get("name", "Unknown"),
                    realm=realm_info.get("name", "") if isinstance(realm_info, dict) else str(realm_info),
                    class_name=class_info.get("name", "") if isinstance(class_info, dict) else str(class_info),
                    spec_name=spec_info.get("name", "") if isinstance(spec_info, dict) else str(spec_info),
                    role=member.get("role", "dps"),
                )
            )

        # Parse deaths
        logged = data.get("logged_details") or {}
        deaths = logged.get("deaths", [])

        # Map character IDs to names for death tracking
        death_names = []
        if deaths and roster:
            # Build ID -> name map from encounter rosters
            id_map = {}
            for encounter in logged.get("encounters", []):
                for r in encounter.get("roster", []):
                    c = r.get("character", {})
                    cid = c.get("id")
                    if cid:
                        id_map[cid] = c.get("name", "Unknown")

            death_names = [
                {
                    "name": id_map.get(d.get("character_id"), "Unknown"),
                    "character_id": d.get("character_id"),
                    "died_at_ms": d.get("approximate_died_at", 0),
                }
                for d in deaths
            ]

        dungeon_info = data.get("dungeon", {})

        return RunDetails(
            keystone_run_id=data.get("keystone_run_id", run_id),
            dungeon=dungeon_info.get("name", data.get("dungeon", "Unknown")) if isinstance(dungeon_info, dict) else str(dungeon_info),
            mythic_level=data.get("mythic_level", 0),
            clear_time_ms=data.get("clear_time_ms", 0),
            par_time_ms=data.get("keystone_time_ms", 0),
            num_chests=data.get("num_chests", 0),
            score=data.get("score", 0.0),
            roster=roster,
            deaths=death_names,
            total_deaths=len(deaths),
        )
