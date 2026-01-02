/**
 * OpenDota API Provider
 * 
 * REST-based API (primary provider).
 * Limits: 3,000/day, 60/min
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

const OPENDOTA_API_URL = "https://api.opendota.com/api";

/**
 * Fetch wrapper that throws ProviderError on non-ok responses.
 */
async function openDotaFetch<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${OPENDOTA_API_URL}${endpoint}`);

    if (!response.ok) {
        throw new ProviderError(
            `OpenDota API error: ${response.status}`,
            response.status,
            "opendota"
        );
    }

    return response.json();
}

/**
 * OpenDota API Provider implementation.
 */
export class OpenDotaProvider implements DotaDataProvider {
    name = "opendota";

    async getMatch(matchId: number): Promise<MatchData | null> {
        try {
            interface OpenDotaMatch {
                match_id: number;
                radiant_win: boolean;
                duration: number;
                start_time: number;
                game_mode: number;
                players: Array<{
                    account_id: number | null;
                    player_slot: number;
                    hero_id: number;
                    kills: number;
                    deaths: number;
                    assists: number;
                    last_hits: number;
                    denies: number;
                    gold_per_min: number;
                    xp_per_min: number;
                    hero_damage: number;
                    tower_damage: number;
                    hero_healing: number;
                    level: number;
                    net_worth: number;
                    item_0: number;
                    item_1: number;
                    item_2: number;
                    item_3: number;
                    item_4: number;
                    item_5: number;
                    item_neutral: number;
                    personaname?: string;
                    lane?: number;
                    gold_t?: number[];
                }>;
            }

            const data = await openDotaFetch<OpenDotaMatch>(`/matches/${matchId}`);

            const players: PlayerMatchData[] = data.players.map((p) => ({
                account_id: p.account_id,
                player_slot: p.player_slot,
                hero_id: p.hero_id,
                kills: p.kills,
                deaths: p.deaths,
                assists: p.assists,
                last_hits: p.last_hits,
                denies: p.denies,
                gold_per_min: p.gold_per_min,
                xp_per_min: p.xp_per_min,
                hero_damage: p.hero_damage || 0,
                tower_damage: p.tower_damage || 0,
                hero_healing: p.hero_healing || 0,
                level: p.level,
                net_worth: p.net_worth,
                item_0: p.item_0 || 0,
                item_1: p.item_1 || 0,
                item_2: p.item_2 || 0,
                item_3: p.item_3 || 0,
                item_4: p.item_4 || 0,
                item_5: p.item_5 || 0,
                item_neutral: p.item_neutral || 0,
                personaname: p.personaname,
                lane: p.lane,
                gold_t: p.gold_t,
                isRadiant: p.player_slot < 128,
            }));

            return {
                match_id: data.match_id,
                radiant_win: data.radiant_win,
                duration: data.duration,
                start_time: data.start_time,
                game_mode: data.game_mode,
                players,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[OpenDota] getMatch error:", error);
            return null;
        }
    }

    async getPlayerProfile(accountId: string): Promise<PlayerProfileData | null> {
        try {
            interface OpenDotaPlayer {
                profile: {
                    account_id: number;
                    personaname: string;
                    avatarfull: string;
                };
                rank_tier: number | null;
            }

            const data = await openDotaFetch<OpenDotaPlayer>(`/players/${accountId}`);

            return {
                account_id: data.profile.account_id,
                personaname: data.profile.personaname,
                avatarfull: data.profile.avatarfull,
                rank_tier: data.rank_tier,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[OpenDota] getPlayerProfile error:", error);
            return null;
        }
    }

    async getPlayerRecentMatches(accountId: string, limit: number = 20): Promise<PlayerRecentMatchData[]> {
        try {
            interface OpenDotaRecentMatch {
                match_id: number;
                hero_id: number;
                kills: number;
                deaths: number;
                assists: number;
                duration: number;
                start_time: number;
                radiant_win: boolean;
                player_slot: number;
                lane?: number;
            }

            const data = await openDotaFetch<OpenDotaRecentMatch[]>(
                `/players/${accountId}/matches?limit=${limit}`
            );

            return data.map((m) => ({
                match_id: m.match_id,
                hero_id: m.hero_id,
                kills: m.kills,
                deaths: m.deaths,
                assists: m.assists,
                duration: m.duration,
                start_time: m.start_time,
                radiant_win: m.radiant_win,
                player_slot: m.player_slot,
                lane: m.lane,
            }));
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[OpenDota] getPlayerRecentMatches error:", error);
            return [];
        }
    }

    async getPlayerPeers(accountId: string, limit: number = 100): Promise<PeerData[]> {
        try {
            interface OpenDotaPeer {
                account_id: number;
                personaname: string;
                avatarfull: string;
                win: number;
                games: number;
            }

            const data = await openDotaFetch<OpenDotaPeer[]>(
                `/players/${accountId}/peers?limit=${limit}`
            );

            return data.map((p) => ({
                account_id: p.account_id,
                personaname: p.personaname,
                avatarfull: p.avatarfull,
                win: p.win,
                games: p.games,
            }));
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[OpenDota] getPlayerPeers error:", error);
            return [];
        }
    }

    async getPlayerWinLoss(accountId: string): Promise<WinLossData> {
        try {
            interface OpenDotaWinLoss {
                win: number;
                lose: number;
            }

            const data = await openDotaFetch<OpenDotaWinLoss>(`/players/${accountId}/wl`);

            return {
                win: data.win || 0,
                lose: data.lose || 0,
            };
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            console.error("[OpenDota] getPlayerWinLoss error:", error);
            return { win: 0, lose: 0 };
        }
    }
}

// Export singleton instance
export const openDotaProvider = new OpenDotaProvider();
