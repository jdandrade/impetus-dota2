"""
Steam Web API client (Valve's official Dota 2 match API).

Primary source for detecting new matches: the key allows ~100k calls/day,
so we can poll far more often than OpenDota/Stratz permit.

Every function returns None on any failure so the caller can fall back to
OpenDota. The API key is sent as a query parameter, so exceptions are logged
by type only -- never log the exception text or the request URL.
"""

import logging
import time
from typing import Optional

import aiohttp

from app.services.opendota import HERO_NAMES, MatchData, PlayerMinimal

logger = logging.getLogger(__name__)

STEAM_MATCH_API_BASE = "https://api.steampowered.com/IDOTA2Match_570"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

# GetMatchHistory result.status when the player has not enabled
# "Expose Public Match Data" in the Dota 2 client.
STATUS_PRIVATE_PROFILE = 15

INITIAL_BACKOFF = 30
MAX_BACKOFF = 600

_backoff = 0
_backoff_until = 0.0

# Last problem logged per subject, so a persistent failure (private profile,
# bad key) is logged once instead of on every poll.
_last_problem: dict[str, Optional[str]] = {}


def _report(subject: str, problem: Optional[str]) -> None:
    """Log a problem for a subject only when it changes; None clears it."""
    if _last_problem.get(subject) == problem:
        return
    _last_problem[subject] = problem
    if problem is None:
        logger.info(f"[Steam] {subject}: working again")
    else:
        logger.warning(f"[Steam] {subject}: {problem}")


def _record_failure() -> None:
    global _backoff, _backoff_until
    _backoff = INITIAL_BACKOFF if _backoff == 0 else min(_backoff * 2, MAX_BACKOFF)
    _backoff_until = time.time() + _backoff


def _record_success() -> None:
    global _backoff, _backoff_until
    _backoff = 0
    _backoff_until = 0.0


async def _get(method: str, api_key: str, params: dict) -> Optional[dict]:
    """Call an IDOTA2Match_570 method and return its `result` object."""
    if time.time() < _backoff_until:
        return None

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(
                f"{STEAM_MATCH_API_BASE}/{method}/v1/",
                params={"key": api_key, **params},
            ) as resp:
                if resp.status != 200:
                    _record_failure()
                    hint = " (check STEAM_API_KEY)" if resp.status in (401, 403) else ""
                    _report("api", f"HTTP {resp.status}{hint}, backing off {_backoff}s")
                    return None
                data = await resp.json(content_type=None)
    except Exception as e:
        _record_failure()
        _report("api", f"request failed ({type(e).__name__}), backing off {_backoff}s")
        return None

    _record_success()
    _report("api", None)
    result = data.get("result") if isinstance(data, dict) else None
    return result if isinstance(result, dict) else None


async def get_latest_match_id(api_key: str, account_id: int) -> Optional[int]:
    """
    Get the newest match ID for a player via GetMatchHistory.

    Returns None if the API is unavailable, the player's match data is
    private, or they have no matches.
    """
    result = await _get(
        "GetMatchHistory",
        api_key,
        {"account_id": account_id, "matches_requested": 5},
    )
    if result is None:
        return None

    subject = f"account {account_id}"
    status = result.get("status")
    if status != 1:
        if status == STATUS_PRIVATE_PROFILE:
            _report(subject, 'match history is private (needs "Expose Public Match Data"), using OpenDota')
        else:
            _report(subject, f"GetMatchHistory status {status}: {result.get('statusDetail', '')}")
        return None

    match_ids = [m["match_id"] for m in result.get("matches", []) if m.get("match_id")]
    if not match_ids:
        _report(subject, "GetMatchHistory returned no matches")
        return None

    _report(subject, None)
    # Do not trust ordering: the newest match has the highest ID.
    return max(match_ids)


async def get_match_data(
    api_key: str,
    match_id: int,
    account_id: int,
    player_name: str,
) -> Optional[MatchData]:
    """
    Get one player's stats for a match via GetMatchDetails.

    Returns None if the match is not available yet or the player cannot be
    found in it (e.g. shown as anonymous).
    """
    result = await _get("GetMatchDetails", api_key, {"match_id": match_id})
    if result is None:
        return None

    if result.get("error"):
        logger.info(f"[Steam] GetMatchDetails {match_id}: {result['error']}")
        return None

    players = result.get("players") or []
    stats = next((p for p in players if p.get("account_id") == account_id), None)
    if stats is None or not result.get("duration"):
        logger.info(f"[Steam] GetMatchDetails {match_id}: no usable data for account {account_id}")
        return None

    all_players = [
        PlayerMinimal(
            hero_id=p.get("hero_id", 0),
            net_worth=p.get("net_worth", 0),
            lane=None,  # Not provided by the Steam API
            is_radiant=p.get("player_slot", 0) < 128,
        )
        for p in players
    ]

    hero_id = stats.get("hero_id", 0)
    player_slot = stats.get("player_slot", 0)

    return MatchData(
        match_id=match_id,
        hero_id=hero_id,
        hero_name=HERO_NAMES.get(hero_id, f"Hero #{hero_id}"),
        kills=stats.get("kills", 0),
        deaths=stats.get("deaths", 0),
        assists=stats.get("assists", 0),
        gpm=stats.get("gold_per_min", 0),
        xpm=stats.get("xp_per_min", 0),
        net_worth=stats.get("net_worth", 0),
        level=stats.get("level", 1),
        hero_damage=stats.get("hero_damage", 0),
        tower_damage=stats.get("tower_damage", 0),
        hero_healing=stats.get("hero_healing", 0),
        last_hits=stats.get("last_hits", 0),
        denies=stats.get("denies", 0),
        duration_seconds=result.get("duration", 0),
        is_radiant=player_slot < 128,
        radiant_win=bool(result.get("radiant_win", False)),
        player_slot=player_slot,
        player_name=player_name,
        lane=None,
        all_players=all_players,
        start_time=result.get("start_time"),
    )
