"""
Mythic+ run tracker — polls Raider.IO for new runs.

Implements group run detection: when multiple tracked players
are in the same run, it's announced once with all of them.
"""

import logging
import asyncio
from typing import Optional

from group_lore import resolve_player

from app.config import TRACKED_CHARACTERS, get_poll_interval, Settings
from app.services.raiderio import RaiderIOClient, MythicPlusRun, RunDetails
from app.services.redis_store import RedisStore
from app.services.gemini import GeminiClient

logger = logging.getLogger(__name__)


class MythicPlusTracker:
    """Polls Raider.IO for new M+ runs and announces them."""

    def __init__(
        self,
        settings: Settings,
        raiderio: RaiderIOClient,
        redis_store: RedisStore,
        gemini: GeminiClient,
        send_callback,
    ):
        self.settings = settings
        self.raiderio = raiderio
        self.redis_store = redis_store
        self.gemini = gemini
        self.send_callback = send_callback
        self._running = False

    async def start(self):
        """Main tracking loop."""
        self._running = True
        logger.info("MythicPlusTracker starting...")

        # Initialize: store current latest run for each character (no announcement)
        await self._initialize_characters()

        while self._running:
            try:
                await self._poll_runs()
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}", exc_info=True)
                await asyncio.sleep(60)

    def stop(self):
        self._running = False

    async def _initialize_characters(self):
        """On first boot, record current latest run for each character."""
        logger.info("Initializing character state...")
        for char_key, char_info in TRACKED_CHARACTERS.items():
            try:
                last_run_id = await self.redis_store.get_last_run_id(char_key)
                if last_run_id is not None:
                    logger.info(f"  {char_info['name']}: already tracked (last run: {last_run_id})")
                    continue

                runs = await self.raiderio.get_recent_runs(
                    char_info["name"], char_info["realm"], char_info["region"]
                )
                if runs:
                    latest = runs[0]
                    await self.redis_store.set_last_run_id(char_key, latest.keystone_run_id)
                    logger.info(f"  {char_info['name']}: initialized with run {latest.keystone_run_id}")
                else:
                    logger.info(f"  {char_info['name']}: no recent runs found")

                await asyncio.sleep(2)  # Gentle on the API during init
            except Exception as e:
                logger.error(f"Failed to initialize {char_info['name']}: {e}")

    async def _poll_runs(self):
        """Poll all characters with staggered timing."""
        chars = list(TRACKED_CHARACTERS.items())
        poll_interval = get_poll_interval(self.settings)
        delay_between = poll_interval / max(len(chars), 1)

        logger.info(f"Poll cycle: {len(chars)} characters, {poll_interval}s interval, {delay_between:.0f}s between each")

        for char_key, char_info in chars:
            if not self._running:
                break

            try:
                await self._check_character(char_key, char_info)
            except Exception as e:
                logger.error(f"Error checking {char_info['name']}: {e}", exc_info=True)

            await asyncio.sleep(delay_between)

    async def _check_character(self, char_key: str, char_info: dict):
        """Check a single character for new runs."""
        runs = await self.raiderio.get_recent_runs(
            char_info["name"], char_info["realm"], char_info["region"]
        )
        if not runs:
            return

        latest = runs[0]
        last_run_id = await self.redis_store.get_last_run_id(char_key)

        if last_run_id is not None and latest.keystone_run_id == last_run_id:
            return  # No new run

        logger.info(f"New run detected for {char_info['name']}: {latest.dungeon} +{latest.mythic_level} (id: {latest.keystone_run_id})")

        # Update this character's last run immediately
        await self.redis_store.set_last_run_id(char_key, latest.keystone_run_id)

        # Check if this run was already announced (group dedup)
        if await self.redis_store.is_run_announced(latest.keystone_run_id):
            logger.info(f"  Run {latest.keystone_run_id} already announced (group run)")
            return

        # Fetch full run details (roster, deaths)
        details = await self.raiderio.get_run_details(latest.keystone_run_id)

        # Find all tracked players in this run
        tracked_in_run = self._find_tracked_players_in_run(details, latest, char_key, char_info)

        # Update last_run_id for all tracked players in the roster
        if details:
            for tk, ti in TRACKED_CHARACTERS.items():
                for member in details.roster:
                    if member.name.lower() == ti["name"].lower():
                        await self.redis_store.set_last_run_id(tk, latest.keystone_run_id)
                        break

        # Mark run as announced
        await self.redis_store.mark_run_announced(latest.keystone_run_id)

        # Build roster for the embed
        group_roster = []
        if details:
            for m in details.roster:
                group_roster.append({
                    "name": m.name,
                    "realm": m.realm,
                    "class": m.class_name,
                    "spec": m.spec_name,
                    "role": m.role,
                })

        # Generate roast
        roast = await self.gemini.generate_roast(
            tracked_players=tracked_in_run,
            dungeon=latest.dungeon,
            mythic_level=latest.mythic_level,
            is_timed=latest.is_timed,
            clear_time_str=latest.clear_time_str,
            par_time_str=latest.par_time_str,
            time_diff_pct=latest.time_diff_pct,
            num_upgrades=latest.num_keystone_upgrades,
            group_roster=group_roster,
            affixes=[a["name"] for a in latest.affixes],
            total_deaths=details.total_deaths if details else 0,
            death_details=details.deaths if details else None,
        )

        # Send announcement
        await self.send_callback(
            run=latest,
            details=details,
            tracked_players=tracked_in_run,
            group_roster=group_roster,
            roast=roast,
        )

    def _find_tracked_players_in_run(
        self,
        details: Optional[RunDetails],
        run: MythicPlusRun,
        trigger_char_key: str,
        trigger_char_info: dict,
    ) -> list[dict]:
        """Find all tracked players in a run's roster."""
        tracked_in_run = []

        if details and details.roster:
            # Cross-reference roster with tracked characters
            for char_key, char_info in TRACKED_CHARACTERS.items():
                for member in details.roster:
                    if member.name.lower() == char_info["name"].lower():
                        player = resolve_player(char_info["player"])
                        tracked_in_run.append({
                            "nickname": player.canonical_name if player else char_info["player"],
                            "character": member.name,
                            "class": member.class_name,
                            "spec": member.spec_name,
                            "role": member.role,
                        })
                        break

        # Fallback: if no details or no matches found, use the triggering character
        if not tracked_in_run:
            player = resolve_player(trigger_char_info["player"])
            tracked_in_run.append({
                "nickname": player.canonical_name if player else trigger_char_info["player"],
                "character": trigger_char_info["name"],
                "class": "Unknown",
                "spec": run.spec_name,
                "role": run.role,
            })

        return tracked_in_run
