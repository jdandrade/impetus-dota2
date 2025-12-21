/**
 * IMP Engine Client
 *
 * Client library for communicating with the IMP Engine microservice.
 */

const IMP_ENGINE_URL =
    process.env.NEXT_PUBLIC_IMP_ENGINE_URL || "http://localhost:8000";

export interface MatchStats {
    kills: number;
    deaths: number;
    assists: number;
    last_hits: number;
    denies: number;
    gpm: number;
    xpm: number;
    hero_damage: number;
    tower_damage: number;
    hero_healing: number;
    net_worth: number;
    level: number;
}

export interface MatchContext {
    team_result: "win" | "loss";
    game_mode: string;
    avg_rank: number;
    is_radiant: boolean;
}

export interface CalculateIMPRequest {
    match_id: number;
    player_slot: number;
    hero_id: number;
    hero_name: string;
    role: "carry" | "mid" | "offlane" | "support" | "hard_support";
    duration_seconds: number;
    stats: MatchStats;
    context: MatchContext;
    benchmarks?: Record<string, number>;  // Percentiles (0.0 - 1.0) for each stat
}

export interface ContributingFactor {
    name: string;
    value: number;
    impact: "positive" | "neutral" | "negative";
    weight: number;
}

export interface IMPData {
    imp_score: number;
    grade: "S" | "A" | "B" | "C" | "D" | "F";
    percentile: number;
    contributing_factors: ContributingFactor[];
    summary: string;
}

export interface IMPMeta {
    engine_version: string;
    calculated_at: string;
}

export interface CalculateIMPResponse {
    success: boolean;
    data: IMPData;
    meta: IMPMeta;
}

/**
 * Calculate the IMP score for a match.
 */
export async function getMatchImp(
    matchData: CalculateIMPRequest
): Promise<CalculateIMPResponse> {
    const response = await fetch(`${IMP_ENGINE_URL}/api/v1/calculate-imp`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(matchData),
    });

    if (!response.ok) {
        throw new Error(`IMP Engine error: ${response.status} ${response.statusText}`);
    }

    return response.json();
}

/**
 * Check if the IMP Engine is healthy.
 */
export async function checkEngineHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${IMP_ENGINE_URL}/health`);
        const data = await response.json();
        return data.status === "ok";
    } catch {
        return false;
    }
}

/**
 * Dummy match data for testing.
 */
export const DUMMY_MATCH_DATA: CalculateIMPRequest = {
    match_id: 7890123456,
    player_slot: 0,
    hero_id: 74,
    hero_name: "Invoker",
    role: "mid",
    duration_seconds: 2400,
    stats: {
        kills: 12,
        deaths: 3,
        assists: 18,
        last_hits: 280,
        denies: 15,
        gpm: 620,
        xpm: 685,
        hero_damage: 32500,
        tower_damage: 4200,
        hero_healing: 0,
        net_worth: 24800,
        level: 25,
    },
    context: {
        team_result: "win",
        game_mode: "ranked",
        avg_rank: 75,
        is_radiant: true,
    },
};
