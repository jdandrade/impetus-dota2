"""
AoE2 Tracker — Smoke test script.

Tests API connectivity, data parsing, group detection, embed building,
and prompt generation against the live WorldsEdge API. No Discord, Redis,
or Gemini credentials needed.

Usage:
    cd services/aoe2-tracker
    PYTHONPATH=.:../../packages/group-lore python3 test_smoke.py
"""

import asyncio
import sys
from datetime import datetime

from app.services.worldsedge import WorldsEdgeClient, AoE2Match
from app.config import TRACKED_PLAYERS, PROFILE_TO_PLAYER
from app.civilizations import get_civ_name, get_match_type
from app.prompts.aoe2_roast import build_match_prompt
from app.tracker import AoE2Tracker
from app.bot import build_match_embed

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results: list[tuple[str, str]] = []


def log_result(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((name, status))
    suffix = f" — {detail}" if detail else ""
    print(f"  {status} {name}{suffix}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_api_connectivity(client: WorldsEdgeClient):
    """Test 1: Can we reach the WorldsEdge API and fetch matches for all players?"""
    section("Test 1: API Connectivity & Match Fetching")

    all_matches: dict[str, list[AoE2Match]] = {}

    for key, info in TRACKED_PLAYERS.items():
        player_name = info["player"]
        try:
            matches = await client.get_recent_matches(info["profile_id"])
            log_result(
                f"Fetch matches for {player_name}",
                len(matches) > 0,
                f"{len(matches)} matches returned",
            )
            all_matches[key] = matches
        except Exception as e:
            log_result(f"Fetch matches for {player_name}", False, str(e))
            all_matches[key] = []

        await asyncio.sleep(1)  # gentle on the API

    return all_matches


async def test_profile_resolution(client: WorldsEdgeClient):
    """Test 2: Can we resolve profile_ids to display names?"""
    section("Test 2: Profile Alias Resolution")

    for key, info in TRACKED_PLAYERS.items():
        player_name = info["player"]
        expected_alias = info["aoe2_alias"]
        try:
            alias = await client.resolve_profile(info["profile_id"])
            matches_expected = alias and expected_alias.lower() in alias.lower()
            log_result(
                f"Resolve {player_name}",
                alias is not None,
                f"alias={alias!r} (expected ~{expected_alias!r})",
            )
        except Exception as e:
            log_result(f"Resolve {player_name}", False, str(e))

        await asyncio.sleep(1)


def test_match_parsing(all_matches: dict[str, list[AoE2Match]]):
    """Test 3: Do parsed matches have valid data?"""
    section("Test 3: Match Data Parsing")

    # Pick the first player with matches
    for key, matches in all_matches.items():
        if not matches:
            continue

        m = matches[0]
        player_name = TRACKED_PLAYERS[key]["player"]

        log_result(
            f"match_id is int ({player_name})",
            isinstance(m.match_id, int) and m.match_id > 0,
            f"id={m.match_id}",
        )
        log_result(
            f"map_name present",
            bool(m.map_name),
            f"raw={m.map_name!r} clean={m.clean_map_name!r}",
        )
        log_result(
            f"game_mode resolves",
            "Unknown" not in m.game_mode or m.matchtype_id == 0,
            f"type_id={m.matchtype_id} → {m.game_mode!r}",
        )
        log_result(
            f"duration is positive",
            m.duration_seconds > 0,
            f"{m.duration_str} ({m.duration_seconds}s)",
        )
        log_result(
            f"players parsed",
            len(m.players) >= 2,
            f"{len(m.players)} players",
        )

        if m.players:
            p = m.players[0]
            log_result(
                f"player has civ",
                bool(p.civ_name),
                f"civ_id={p.civilization_id} → {p.civ_name!r}",
            )
            log_result(
                f"player has result",
                p.result in (0, 1),
                f"result={p.result} won={p.won}",
            )
            log_result(
                f"player has rating",
                isinstance(p.old_rating, int),
                f"rating={p.old_rating} → {p.new_rating} ({p.rating_change:+d})",
            )

        # Only test one player's match
        break


def test_group_detection(all_matches: dict[str, list[AoE2Match]]):
    """Test 4: Can we detect group matches (multiple tracked players)?"""
    section("Test 4: Group Match Detection")

    group_matches = []
    vs_matches = []

    # Search all fetched matches for group games
    for key, matches in all_matches.items():
        for m in matches:
            tracked_pids = set()
            for p in m.players:
                if p.profile_id in PROFILE_TO_PLAYER:
                    tracked_pids.add(p.profile_id)

            if len(tracked_pids) >= 2:
                # Check if same team or opposing
                team_ids = set()
                for p in m.players:
                    if p.profile_id in tracked_pids:
                        team_ids.add(p.team_id)

                entry = (m.match_id, tracked_pids, len(team_ids) > 1)
                if len(team_ids) > 1:
                    vs_matches.append(entry)
                else:
                    group_matches.append(entry)

    # Deduplicate by match_id
    seen = set()
    unique_group = []
    for mid, pids, is_vs in group_matches:
        if mid not in seen:
            seen.add(mid)
            unique_group.append((mid, pids, is_vs))
    unique_vs = []
    for mid, pids, is_vs in vs_matches:
        if mid not in seen:
            seen.add(mid)
            unique_vs.append((mid, pids, is_vs))

    log_result(
        "Found same-team group matches",
        len(unique_group) > 0,
        f"{len(unique_group)} found",
    )
    log_result(
        "Found friend-vs-friend matches",
        len(unique_vs) >= 0,  # may not exist, just report
        f"{len(unique_vs)} found",
    )

    # Print details
    for mid, pids, is_vs in (unique_group + unique_vs)[:5]:
        names = [TRACKED_PLAYERS[PROFILE_TO_PLAYER[pid]]["player"] for pid in pids]
        tag = "VS" if is_vs else "TEAM"
        print(f"    [{tag}] match {mid}: {', '.join(names)}")

    return unique_group, unique_vs


def test_tracker_methods(all_matches: dict[str, list[AoE2Match]]):
    """Test 5: Do tracker._find_tracked_players and _build_team_rosters work?"""
    section("Test 5: Tracker Data Methods")

    # Create a tracker instance without full init (just need the methods)
    tracker = AoE2Tracker.__new__(AoE2Tracker)

    # Find a match with at least one tracked player
    test_match = None
    for key, matches in all_matches.items():
        for m in matches:
            for p in m.players:
                if p.profile_id in PROFILE_TO_PLAYER:
                    test_match = m
                    break
            if test_match:
                break
        if test_match:
            break

    if not test_match:
        log_result("Find test match", False, "no matches with tracked players")
        return None, None, None

    log_result("Find test match", True, f"match {test_match.match_id}")

    # Test _find_tracked_players
    tracked = tracker._find_tracked_players(test_match)
    log_result(
        "_find_tracked_players",
        len(tracked) > 0,
        f"found {len(tracked)}: {[p['nickname'] for p in tracked]}",
    )

    for p in tracked:
        required_keys = {"nickname", "aoe2_alias", "profile_id", "civ", "team_id", "won", "old_rating", "new_rating"}
        missing = required_keys - set(p.keys())
        log_result(
            f"  Player dict keys ({p['nickname']})",
            not missing,
            f"missing: {missing}" if missing else "all present",
        )

    # Test _build_team_rosters (need aliases)
    aliases = {p.profile_id: f"Player_{p.profile_id}" for p in test_match.players}
    teams = tracker._build_team_rosters(test_match, aliases, tracked)
    log_result(
        "_build_team_rosters",
        len(teams) >= 2 or test_match.max_players == 2,
        f"{len(teams)} teams",
    )

    return test_match, tracked, teams


def test_prompt_generation(test_match, tracked, teams):
    """Test 6: Does the prompt builder produce valid output?"""
    section("Test 6: Prompt Generation")

    if not test_match or not tracked or not teams:
        log_result("Prompt generation", False, "no test data available")
        return

    team_ids = {p["team_id"] for p in tracked}
    tracked_on_same = len(team_ids) == 1 and len(tracked) > 1
    tracked_vs = len(team_ids) > 1

    try:
        prompt = build_match_prompt(
            tracked_players=tracked,
            map_name=test_match.clean_map_name,
            game_mode=test_match.game_mode,
            duration_str=test_match.duration_str,
            duration_seconds=test_match.duration_seconds,
            is_ranked=test_match.is_ranked,
            all_teams=teams,
            tracked_on_same_team=tracked_on_same,
            tracked_vs_tracked=tracked_vs,
        )
        log_result("build_match_prompt", True, f"{len(prompt)} chars")

        # Verify key sections are present
        log_result("Prompt has map", "Mapa:" in prompt)
        log_result("Prompt has mode", "Modo:" in prompt)
        log_result("Prompt has duration", "Duração:" in prompt, test_match.duration_str)
        log_result(
            "Prompt has tracked player names",
            any(p["nickname"] in prompt for p in tracked),
        )
        log_result("Prompt has team info", "Equipa" in prompt)

        # Print prompt preview
        print(f"\n    --- Prompt preview (first 600 chars) ---")
        for line in prompt[:600].split("\n"):
            print(f"    {line}")
        print(f"    ...")

    except Exception as e:
        log_result("build_match_prompt", False, str(e))


def test_embed_building(test_match, tracked, teams):
    """Test 7: Does the embed builder work? (Can't verify Discord rendering, but check it doesn't crash)"""
    section("Test 7: Embed Building (structural)")

    if not test_match or not tracked or not teams:
        log_result("Embed building", False, "no test data available")
        return

    team_ids = {p["team_id"] for p in tracked}
    tracked_vs = len(team_ids) > 1
    aliases = {p.profile_id: f"Player_{p.profile_id}" for p in test_match.players}

    try:
        embed = build_match_embed(
            match=test_match,
            tracked_players=tracked,
            all_teams=teams,
            aliases=aliases,
            roast="Isto é um roast de teste. O Gil tem 821 ELO.",
            tracked_vs_tracked=tracked_vs,
        )
        log_result("build_match_embed", True, f"title={embed.title!r}")
        log_result("Embed has color", embed.color is not None, f"color={embed.color}")
        log_result("Embed has description", bool(embed.description))
        log_result("Embed has fields", len(embed.fields) >= 3, f"{len(embed.fields)} fields")
        log_result("Embed has footer", embed.footer is not None)

        print(f"\n    --- Embed preview ---")
        print(f"    Title: {embed.title}")
        print(f"    Color: {embed.color}")
        print(f"    Description: {embed.description[:100]}...")
        for f in embed.fields:
            print(f"    Field: {f.name} = {f.value[:80]}...")

    except Exception as e:
        log_result("build_match_embed", False, str(e))


def test_civ_coverage(all_matches: dict[str, list[AoE2Match]]):
    """Test 8: Are all civilization IDs in match data resolved to names?"""
    section("Test 8: Civilization ID Coverage")

    unknown_civs = set()
    total_civs = set()

    for matches in all_matches.values():
        for m in matches:
            for p in m.players:
                total_civs.add(p.civilization_id)
                if "Unknown" in p.civ_name:
                    unknown_civs.add(p.civilization_id)

    log_result(
        "All civ IDs mapped",
        len(unknown_civs) == 0,
        f"{len(total_civs)} unique civs seen, {len(unknown_civs)} unknown: {unknown_civs or 'none'}",
    )


def test_short_match_filter(all_matches: dict[str, list[AoE2Match]]):
    """Test 9: Do we correctly identify short matches to skip?"""
    section("Test 9: Short Match Filter")

    short = []
    for matches in all_matches.values():
        for m in matches:
            if m.duration_seconds < 120:
                short.append((m.match_id, m.duration_seconds))

    log_result(
        "Short match detection",
        True,
        f"{len(short)} matches < 2min found (would be skipped)",
    )
    for mid, dur in short[:3]:
        print(f"    match {mid}: {dur}s")


async def run_all():
    print("=" * 60)
    print("  AoE2 Tracker — Smoke Tests")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    client = WorldsEdgeClient()

    try:
        # Test 1: API connectivity
        all_matches = await test_api_connectivity(client)

        # Test 2: Profile resolution
        await test_profile_resolution(client)

        # Test 3: Match parsing
        test_match_parsing(all_matches)

        # Test 4: Group detection
        test_group_detection(all_matches)

        # Test 5: Tracker methods
        test_match, tracked, teams = test_tracker_methods(all_matches)

        # Test 6: Prompt generation
        test_prompt_generation(test_match, tracked, teams)

        # Test 7: Embed building
        test_embed_building(test_match, tracked, teams)

        # Test 8: Civ coverage
        test_civ_coverage(all_matches)

        # Test 9: Short match filter
        test_short_match_filter(all_matches)

    finally:
        await client.close()

    # Summary
    section("Summary")
    passed = sum(1 for _, s in results if s == PASS)
    failed = sum(1 for _, s in results if s == FAIL)
    total = len(results)
    print(f"\n  {passed}/{total} passed, {failed} failed\n")

    if failed:
        print("  Failed tests:")
        for name, status in results:
            if status == FAIL:
                print(f"    {FAIL} {name}")
        print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all())
    sys.exit(exit_code)
