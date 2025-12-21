/**
 * Data Transformer
 *
 * Transforms OpenDota match data into the IMP Engine request format.
 */

import type { CalculateIMPRequest } from "./imp-client";
import {
    type OpenDotaMatch,
    type OpenDotaPlayer,
    type HeroBenchmarks,
    getHeroName,
    getGameModeName,
    normalizeRankTier,
    calculatePlayerBenchmarks,
} from "./opendota";

/**
 * Role detection based on net worth ranking within the team.
 * 
 * This heuristic determines roles by comparing net worth among teammates:
 * - Highest net worth = Carry (Position 1)
 * - Second highest = Mid (Position 2)
 * - Third = Offlane (Position 3)
 * - Fourth = Soft Support (Position 4)
 * - Lowest = Hard Support (Position 5)
 * 
 * This matches how Stratz and other analytics determine actual played roles.
 */
function detectRoleByNetWorth(
    player: OpenDotaPlayer,
    allPlayers: OpenDotaPlayer[]
): CalculateIMPRequest["role"] {
    const isRadiant = player.isRadiant;

    // Get teammates only
    const teammates = allPlayers.filter((p) => p.isRadiant === isRadiant);

    // Sort teammates by net worth (descending)
    const sortedByNW = [...teammates].sort((a, b) => b.net_worth - a.net_worth);

    // Find this player's rank in the team by net worth
    const rank = sortedByNW.findIndex((p) => p.hero_id === player.hero_id);

    // Map rank to role
    switch (rank) {
        case 0:
            return "carry";      // Highest NW = Pos 1
        case 1:
            return "mid";        // Second highest = Pos 2
        case 2:
            return "offlane";    // Third = Pos 3
        case 3:
            return "support";    // Fourth = Pos 4
        case 4:
            return "hard_support"; // Lowest = Pos 5
        default:
            return "support";
    }
}

/**
 * Find a player in the match by various identifiers.
 */
export function findPlayer(
    match: OpenDotaMatch,
    identifier: { accountId?: number; playerSlot?: number; heroId?: number; index?: number }
): { player: OpenDotaPlayer; index: number } | null {
    if (identifier.index !== undefined) {
        const player = match.players[identifier.index];
        return player ? { player, index: identifier.index } : null;
    }

    if (identifier.accountId !== undefined) {
        const index = match.players.findIndex((p) => p.account_id === identifier.accountId);
        if (index !== -1) {
            return { player: match.players[index], index };
        }
    }

    if (identifier.playerSlot !== undefined) {
        const index = match.players.findIndex((p) => p.player_slot === identifier.playerSlot);
        if (index !== -1) {
            return { player: match.players[index], index };
        }
    }

    if (identifier.heroId !== undefined) {
        const index = match.players.findIndex((p) => p.hero_id === identifier.heroId);
        if (index !== -1) {
            return { player: match.players[index], index };
        }
    }

    return null;
}

/**
 * Transform OpenDota match data for a specific player into IMP Engine request format.
 *
 * @param match - The OpenDota match data
 * @param playerIndex - Index of the player in the players array (0-9)
 * @param benchmarks - Optional hero benchmarks for percentile calculation
 * @returns The formatted request payload for the IMP Engine
 */
export function transformMatchToPayload(
    match: OpenDotaMatch,
    playerIndex: number,
    benchmarks?: HeroBenchmarks
): CalculateIMPRequest {
    const player = match.players[playerIndex];

    if (!player) {
        throw new Error(`Player at index ${playerIndex} not found in match`);
    }

    const isRadiant = player.isRadiant;
    const teamWon = isRadiant ? match.radiant_win : !match.radiant_win;
    const durationMinutes = match.duration / 60;

    // Calculate benchmark percentiles if available
    const benchmarkPercentiles = benchmarks
        ? calculatePlayerBenchmarks(player, durationMinutes, benchmarks)
        : undefined;

    return {
        match_id: match.match_id,
        player_slot: player.player_slot,
        hero_id: player.hero_id,
        hero_name: getHeroName(player.hero_id),
        role: detectRoleByNetWorth(player, match.players),
        duration_seconds: match.duration,
        stats: {
            kills: player.kills,
            deaths: player.deaths,
            assists: player.assists,
            last_hits: player.last_hits,
            denies: player.denies,
            gpm: player.gold_per_min,
            xpm: player.xp_per_min,
            hero_damage: player.hero_damage,
            tower_damage: player.tower_damage,
            hero_healing: player.hero_healing,
            net_worth: player.net_worth,
            level: player.level,
        },
        context: {
            team_result: teamWon ? "win" : "loss",
            game_mode: getGameModeName(match.game_mode),
            avg_rank: normalizeRankTier(match.avg_rank_tier),
            is_radiant: isRadiant,
        },
        benchmarks: benchmarkPercentiles,
    };
}

/**
 * Transform match data for all players.
 */
export function transformAllPlayers(match: OpenDotaMatch): CalculateIMPRequest[] {
    return match.players.map((_, index) => transformMatchToPayload(match, index));
}
