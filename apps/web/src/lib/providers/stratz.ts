/**
 * Stratz API Provider
 * 
 * GraphQL-based API with higher rate limits than OpenDota.
 * Limits: 10,000/day, 250/min, 20/sec
 */

import {
    DotaDataProvider,
    MatchData,
    PlayerMatchData,
    PlayerProfileData,
    PlayerRecentMatchData,
    PeerData,
    WinLossData,
    ProviderError,
} from "./types";

const STRATZ_API_URL = "https://api.stratz.com/graphql";

// Get token from environment (not committed to repo)
const getStratzToken = (): string | null => {
    if (typeof process !== "undefined") {
        return process.env.NEXT_PUBLIC_STRATZ_API_TOKEN || null;
    }
    return null;
};

/**
 * Execute a GraphQL query against Stratz API.
 */
async function stratzQuery<T>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
    const token = getStratzToken();
    if (!token) {
        throw new ProviderError("Stratz API token not configured", 401, "stratz");
    }

    const response = await fetch(STRATZ_API_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
            "User-Agent": "STRATZ_API",
        },
        body: JSON.stringify({ query, variables }),
    });

    if (!response.ok) {
        throw new ProviderError(
            `Stratz API error: ${response.status}`,
            response.status,
            "stratz"
        );
    }

    const json = await response.json();
    if (json.errors) {
        throw new ProviderError(
            `Stratz GraphQL error: ${json.errors[0]?.message}`,
            400,
            "stratz"
        );
    }

    return json.data as T;
}

/**
 * Convert Stratz player slot (0-9) to OpenDota format (0-4, 128-132).
 */
function toOpenDotaSlot(slot: number, isRadiant: boolean): number {
    if (isRadiant) {
        return slot; // 0-4 for Radiant
    }
    return 128 + (slot - 5); // 128-132 for Dire
}

/**
 * Stratz API Provider implementation.
 */
export class StratzProvider implements DotaDataProvider {
    name = "stratz";

    async getMatch(matchId: number): Promise<MatchData | null> {
        const query = `
            query GetMatch($matchId: Long!) {
                match(id: $matchId) {
                    id
                    didRadiantWin
                    durationSeconds
                    startDateTime
                    gameMode
                    players {
                        steamAccountId
                        heroId
                        kills
                        deaths
                        assists
                        numLastHits
                        numDenies
                        goldPerMinute
                        experiencePerMinute
                        heroDamage
                        towerDamage
                        heroHealing
                        level
                        networth
                        item0Id
                        item1Id
                        item2Id
                        item3Id
                        item4Id
                        item5Id
                        neutral0Id
                        position
                        isRadiant
                        lane
                        steamAccount {
                            name
                        }
                    }
                }
            }
        `;

        try {
            interface StratzMatchResponse {
                match: {
                    id: number;
                    didRadiantWin: boolean;
                    durationSeconds: number;
                    startDateTime: number;
                    gameMode: number;
                    players: Array<{
                        steamAccountId: number | null;
                        heroId: number;
                        kills: number;
                        deaths: number;
                        assists: number;
                        numLastHits: number;
                        numDenies: number;
                        goldPerMinute: number;
                        experiencePerMinute: number;
                        heroDamage: number;
                        towerDamage: number;
                        heroHealing: number;
                        level: number;
                        networth: number;
                        item0Id: number;
                        item1Id: number;
                        item2Id: number;
                        item3Id: number;
                        item4Id: number;
                        item5Id: number;
                        neutral0Id: number;
                        position: number;
                        isRadiant: boolean;
                        lane: number;
                        steamAccount?: { name: string };
                    }>;
                } | null;
            }

            const data = await stratzQuery<StratzMatchResponse>(query, { matchId });
            if (!data.match) return null;

            const match = data.match;
            const players: PlayerMatchData[] = match.players.map((p, index) => ({
                account_id: p.steamAccountId,
                player_slot: toOpenDotaSlot(index, p.isRadiant),
                hero_id: p.heroId,
                kills: p.kills,
                deaths: p.deaths,
                assists: p.assists,
                last_hits: p.numLastHits,
                denies: p.numDenies,
                gold_per_min: p.goldPerMinute,
                xp_per_min: p.experiencePerMinute,
                hero_damage: p.heroDamage || 0,
                tower_damage: p.towerDamage || 0,
                hero_healing: p.heroHealing || 0,
                level: p.level,
                net_worth: p.networth,
                item_0: p.item0Id || 0,
                item_1: p.item1Id || 0,
                item_2: p.item2Id || 0,
                item_3: p.item3Id || 0,
                item_4: p.item4Id || 0,
                item_5: p.item5Id || 0,
                item_neutral: p.neutral0Id || 0,
                personaname: p.steamAccount?.name,
                lane: p.lane,
                isRadiant: p.isRadiant,
            }));

            return {
                match_id: match.id,
                radiant_win: match.didRadiantWin,
                duration: match.durationSeconds,
                start_time: match.startDateTime,
                game_mode: match.gameMode,
                players,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[Stratz] getMatch error:", error);
            return null;
        }
    }

    async getPlayerProfile(accountId: string): Promise<PlayerProfileData | null> {
        const query = `
            query GetPlayer($steamAccountId: Long!) {
                player(steamAccountId: $steamAccountId) {
                    steamAccountId
                    steamAccount {
                        name
                        avatar
                        seasonRank
                    }
                }
            }
        `;

        try {
            interface StratzPlayerResponse {
                player: {
                    steamAccountId: number;
                    steamAccount: {
                        name: string;
                        avatar: string;
                        seasonRank: number | null;
                    };
                } | null;
            }

            const data = await stratzQuery<StratzPlayerResponse>(query, {
                steamAccountId: parseInt(accountId),
            });

            if (!data.player) return null;

            return {
                account_id: data.player.steamAccountId,
                personaname: data.player.steamAccount.name,
                avatarfull: data.player.steamAccount.avatar,
                rank_tier: data.player.steamAccount.seasonRank,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[Stratz] getPlayerProfile error:", error);
            return null;
        }
    }

    async getPlayerRecentMatches(accountId: string, limit: number = 20): Promise<PlayerRecentMatchData[]> {
        const query = `
            query GetPlayerMatches($steamAccountId: Long!, $take: Int!) {
                player(steamAccountId: $steamAccountId) {
                    matches(request: { take: $take }) {
                        id
                        didRadiantWin
                        durationSeconds
                        startDateTime
                        players(steamAccountId: $steamAccountId) {
                            heroId
                            kills
                            deaths
                            assists
                            lane
                            isRadiant
                            position
                        }
                    }
                }
            }
        `;

        try {
            interface StratzMatchesResponse {
                player: {
                    matches: Array<{
                        id: number;
                        didRadiantWin: boolean;
                        durationSeconds: number;
                        startDateTime: number;
                        players: Array<{
                            heroId: number;
                            kills: number;
                            deaths: number;
                            assists: number;
                            lane: number;
                            isRadiant: boolean;
                            position: number;
                        }>;
                    }>;
                } | null;
            }

            const data = await stratzQuery<StratzMatchesResponse>(query, {
                steamAccountId: parseInt(accountId),
                take: limit,
            });

            if (!data.player) return [];

            return data.player.matches.map((m) => {
                const p = m.players[0]; // The requested player
                return {
                    match_id: m.id,
                    hero_id: p?.heroId || 0,
                    kills: p?.kills || 0,
                    deaths: p?.deaths || 0,
                    assists: p?.assists || 0,
                    duration: m.durationSeconds,
                    start_time: m.startDateTime,
                    radiant_win: m.didRadiantWin,
                    player_slot: p?.isRadiant ? p.position : 128 + p.position,
                    lane: p?.lane,
                };
            });
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[Stratz] getPlayerRecentMatches error:", error);
            return [];
        }
    }

    async getPlayerPeers(accountId: string, limit: number = 100): Promise<PeerData[]> {
        // Stratz doesn't have a direct peers endpoint like OpenDota
        // We'd need to fetch matches and aggregate teammates
        // For now, return empty array (fallback won't help here)
        console.warn("[Stratz] getPlayerPeers not fully implemented, returning empty");
        return [];
    }

    async getPlayerWinLoss(accountId: string): Promise<WinLossData> {
        const query = `
            query GetPlayerWinLoss($steamAccountId: Long!) {
                player(steamAccountId: $steamAccountId) {
                    winCount
                    matchCount
                }
            }
        `;

        try {
            interface StratzWinLossResponse {
                player: {
                    winCount: number;
                    matchCount: number;
                } | null;
            }

            const data = await stratzQuery<StratzWinLossResponse>(query, {
                steamAccountId: parseInt(accountId),
            });

            if (!data.player) return { win: 0, lose: 0 };

            return {
                win: data.player.winCount,
                lose: data.player.matchCount - data.player.winCount,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[Stratz] getPlayerWinLoss error:", error);
            return { win: 0, lose: 0 };
        }
    }
}

// Export singleton instance
export const stratzProvider = new StratzProvider();
