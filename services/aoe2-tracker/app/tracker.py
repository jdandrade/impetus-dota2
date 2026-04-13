"""
AoE2 match tracker — polls WorldsEdge API for new matches.

Implements group match detection: when multiple tracked players
are in the same match, it's announced once with all of them.
Also detects friend-vs-friend matches (tracked players on opposing teams).
"""

import logging
import asyncio
from typing import Optional

from group_lore import resolve_player

from app.config import TRACKED_PLAYERS, PROFILE_TO_PLAYER, get_poll_interval, Settings
from app.services.worldsedge import WorldsEdgeClient, AoE2Match
from app.services.redis_store import RedisStore
from app.services.gemini import GeminiClient

logger = logging.getLogger(__name__)

# Skip matches shorter than 2 minutes (likely disconnects)
MIN_MATCH_DURATION = 120


class AoE2Tracker:
    """Polls WorldsEdge API for new AoE2 matches and announces them."""

    def __init__(
        self,
        settings: Settings,
        worldsedge: WorldsEdgeClient,
        redis_store: RedisStore,
        gemini: GeminiClient,
        send_callback,
    ):
        self.settings = settings
        self.worldsedge = worldsedge
        self.redis_store = redis_store
        self.gemini = gemini
        self.send_callback = send_callback
        self._running = False

    async def start(self):
        """Main tracking loop."""
        self._running = True
        logger.info("AoE2Tracker starting...")

        # Initialize: store current latest match for each player (no announcement)
        await self._initialize_players()

        while self._running:
            try:
                await self._poll_matches()
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}", exc_info=True)
                await asyncio.sleep(60)

    def stop(self):
        self._running = False

    async def _initialize_players(self):
        """On first boot, record current latest match for each player."""
        logger.info("Initializing player state...")
        for player_key, player_info in TRACKED_PLAYERS.items():
            try:
                last_match_id = await self.redis_store.get_last_match_id(player_key)
                if last_match_id is not None:
                    logger.info(f"  {player_info['aoe2_alias']}: already tracked (last match: {last_match_id})")
                    continue

                matches = await self.worldsedge.get_recent_matches(player_info["profile_id"])
                if matches:
                    latest = matches[0]
                    await self.redis_store.set_last_match_id(player_key, latest.match_id)
                    logger.info(f"  {player_info['aoe2_alias']}: initialized with match {latest.match_id}")
                else:
                    logger.info(f"  {player_info['aoe2_alias']}: no recent matches found")

                await asyncio.sleep(2)  # Gentle on the API during init
            except Exception as e:
                logger.error(f"Failed to initialize {player_info['aoe2_alias']}: {e}")

    async def _poll_matches(self):
        """Poll all players with staggered timing."""
        players = list(TRACKED_PLAYERS.items())
        poll_interval = get_poll_interval(self.settings)
        delay_between = poll_interval / max(len(players), 1)

        logger.info(f"Poll cycle: {len(players)} players, {poll_interval}s interval, {delay_between:.0f}s between each")

        for player_key, player_info in players:
            if not self._running:
                break

            try:
                await self._check_player(player_key, player_info)
            except Exception as e:
                logger.error(f"Error checking {player_info['aoe2_alias']}: {e}", exc_info=True)

            await asyncio.sleep(delay_between)

    async def _check_player(self, player_key: str, player_info: dict):
        """Check a single player for new matches."""
        matches = await self.worldsedge.get_recent_matches(player_info["profile_id"])
        if not matches:
            return

        latest = matches[0]
        last_match_id = await self.redis_store.get_last_match_id(player_key)

        if last_match_id is not None and latest.match_id == last_match_id:
            return  # No new match

        # Skip very short games (disconnects/lobby issues)
        if latest.duration_seconds < MIN_MATCH_DURATION:
            logger.info(f"Skipping short match {latest.match_id} for {player_info['aoe2_alias']} ({latest.duration_seconds}s)")
            await self.redis_store.set_last_match_id(player_key, latest.match_id)
            return

        logger.info(
            f"New match detected for {player_info['aoe2_alias']}: "
            f"{latest.clean_map_name} {latest.game_mode} (id: {latest.match_id})"
        )

        # Update this player's last match immediately
        await self.redis_store.set_last_match_id(player_key, latest.match_id)

        # Check if this match was already announced (group dedup)
        if await self.redis_store.is_match_announced(latest.match_id):
            logger.info(f"  Match {latest.match_id} already announced (group match)")
            return

        # Find all tracked players in this match
        tracked_in_match = self._find_tracked_players(latest)

        # Update last_match_id for all tracked players in this match
        for p in tracked_in_match:
            pk = PROFILE_TO_PLAYER.get(p["profile_id"])
            if pk:
                await self.redis_store.set_last_match_id(pk, latest.match_id)

        # Mark match as announced
        await self.redis_store.mark_match_announced(latest.match_id)

        # Resolve display names for all players in the match
        aliases = await self.worldsedge.resolve_match_aliases(latest)

        # Determine group dynamics
        tracked_team_ids = {p["team_id"] for p in tracked_in_match}
        tracked_on_same_team = len(tracked_team_ids) == 1 and len(tracked_in_match) > 1
        tracked_vs_tracked = len(tracked_team_ids) > 1

        # Build full team rosters for embed and prompt
        all_teams = self._build_team_rosters(latest, aliases, tracked_in_match)

        # Generate roast
        roast = await self.gemini.generate_roast(
            tracked_players=tracked_in_match,
            map_name=latest.clean_map_name,
            game_mode=latest.game_mode,
            duration_str=latest.duration_str,
            duration_seconds=latest.duration_seconds,
            is_ranked=latest.is_ranked,
            all_teams=all_teams,
            tracked_on_same_team=tracked_on_same_team,
            tracked_vs_tracked=tracked_vs_tracked,
        )

        # Send announcement
        await self.send_callback(
            match=latest,
            tracked_players=tracked_in_match,
            all_teams=all_teams,
            aliases=aliases,
            roast=roast,
            tracked_vs_tracked=tracked_vs_tracked,
        )

    def _find_tracked_players(self, match: AoE2Match) -> list[dict]:
        """Find all tracked players in a match's roster."""
        tracked_in_match = []

        for mp in match.players:
            player_key = PROFILE_TO_PLAYER.get(mp.profile_id)
            if player_key is None:
                continue

            player_info = TRACKED_PLAYERS[player_key]
            player_obj = resolve_player(player_info["player"])
            nickname = player_obj.canonical_name if player_obj else player_info["player"]

            tracked_in_match.append({
                "nickname": nickname,
                "aoe2_alias": player_info["aoe2_alias"],
                "profile_id": mp.profile_id,
                "civ": mp.civ_name,
                "civilization_id": mp.civilization_id,
                "team_id": mp.team_id,
                "won": mp.won,
                "old_rating": mp.old_rating,
                "new_rating": mp.new_rating,
                "rating_change": mp.rating_change,
            })

        return tracked_in_match

    def _build_team_rosters(
        self,
        match: AoE2Match,
        aliases: dict[int, str],
        tracked_in_match: list[dict],
    ) -> dict[int, list[dict]]:
        """Build full team rosters with display info."""
        tracked_pids = {p["profile_id"] for p in tracked_in_match}
        teams: dict[int, list[dict]] = {}

        for mp in match.players:
            player_dict = {
                "profile_id": mp.profile_id,
                "alias": aliases.get(mp.profile_id, f"Player {mp.profile_id}"),
                "civ": mp.civ_name,
                "team_id": mp.team_id,
                "won": mp.won,
                "old_rating": mp.old_rating,
                "new_rating": mp.new_rating,
                "is_tracked": mp.profile_id in tracked_pids,
            }
            teams.setdefault(mp.team_id, []).append(player_dict)

        return teams
