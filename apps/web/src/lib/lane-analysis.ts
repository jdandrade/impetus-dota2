/**
 * Lane Analysis Utility
 * Calculates lane matchup outcomes from parsed match data.
 */

import { OpenDotaPlayer } from "./opendota";

export interface LaneMatchup {
    lane: "top" | "mid" | "bot";
    radiantHeroes: number[];
    direHeroes: number[];
    outcome: "radiant" | "dire" | "draw";
    radiantGold: number;
    direGold: number;
}

// Get gold at a specific minute (defaults to minute 10 for laning phase)
function getGoldAtMinute(player: OpenDotaPlayer, minute: number = 10): number {
    if (player.gold_t && player.gold_t.length > minute) {
        return player.gold_t[minute];
    }
    // Fallback: estimate from net worth (less accurate)
    return player.net_worth;
}

// Convert lane number to lane position name
// OpenDota: 1=bot, 2=mid, 3=top
function getLaneName(lane: number): "top" | "mid" | "bot" | null {
    switch (lane) {
        case 1: return "bot";
        case 2: return "mid";
        case 3: return "top";
        default: return null;
    }
}

/**
 * Calculate lane matchup outcomes from match player data.
 * 
 * @param players - All 10 players from the match
 * @returns Array of lane matchups with outcomes
 */
export function calculateLaneMatchups(players: OpenDotaPlayer[]): LaneMatchup[] {
    const matchups: LaneMatchup[] = [];

    // Group players by lane and team
    const laneGroups: Record<string, { radiant: OpenDotaPlayer[], dire: OpenDotaPlayer[] }> = {
        top: { radiant: [], dire: [] },
        mid: { radiant: [], dire: [] },
        bot: { radiant: [], dire: [] },
    };

    for (const player of players) {
        if (player.lane === undefined || player.lane < 1 || player.lane > 3) {
            continue; // Skip players without valid lane data
        }

        const laneName = getLaneName(player.lane);
        if (!laneName) continue;

        if (player.isRadiant) {
            laneGroups[laneName].radiant.push(player);
        } else {
            laneGroups[laneName].dire.push(player);
        }
    }

    // Calculate outcome for each lane
    for (const lane of ["top", "mid", "bot"] as const) {
        const { radiant, dire } = laneGroups[lane];

        // Skip lanes with no players on either side
        if (radiant.length === 0 && dire.length === 0) {
            continue;
        }

        // Calculate total gold at minute 10 for each side
        const radiantGold = radiant.reduce((sum, p) => sum + getGoldAtMinute(p), 0);
        const direGold = dire.reduce((sum, p) => sum + getGoldAtMinute(p), 0);

        // Determine outcome based on gold difference
        const goldDiff = Math.abs(radiantGold - direGold);
        let outcome: "radiant" | "dire" | "draw";

        if (goldDiff < 500) {
            outcome = "draw";
        } else if (radiantGold > direGold) {
            outcome = "radiant";
        } else {
            outcome = "dire";
        }

        matchups.push({
            lane,
            radiantHeroes: radiant.map(p => p.hero_id),
            direHeroes: dire.map(p => p.hero_id),
            outcome,
            radiantGold,
            direGold,
        });
    }

    return matchups;
}

/**
 * Check if lane data is available for a match.
 * Lane data requires the match to be parsed.
 */
export function hasLaneData(players: OpenDotaPlayer[]): boolean {
    return players.some(p => p.lane !== undefined && p.lane >= 1 && p.lane <= 3);
}
