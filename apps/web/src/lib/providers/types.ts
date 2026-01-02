/**
 * Shared types for Dota 2 data providers.
 * Both OpenDota and Stratz providers implement these interfaces.
 */

/**
 * Normalized match data from any provider.
 */
export interface MatchData {
    match_id: number;
    radiant_win: boolean;
    duration: number;
    start_time: number;
    game_mode: number;
    players: PlayerMatchData[];
}

/**
 * Player data within a match.
 */
export interface PlayerMatchData {
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
    isRadiant: boolean;
}

/**
 * Player profile data.
 */
export interface PlayerProfileData {
    account_id: number;
    personaname: string;
    avatarfull: string;
    rank_tier?: number | null;
}

/**
 * Recent match summary for player history.
 */
export interface PlayerRecentMatchData {
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

/**
 * Peer (teammate) data.
 */
export interface PeerData {
    account_id: number;
    personaname: string;
    avatarfull: string;
    win: number;
    games: number;
}

/**
 * Win/loss stats.
 */
export interface WinLossData {
    win: number;
    lose: number;
}

/**
 * Provider error with status code for fallback logic.
 */
export class ProviderError extends Error {
    constructor(
        message: string,
        public statusCode: number,
        public provider: string
    ) {
        super(message);
        this.name = "ProviderError";
    }

    isRateLimited(): boolean {
        return this.statusCode === 429;
    }
}

/**
 * Abstract interface for Dota 2 data providers.
 */
export interface DotaDataProvider {
    name: string;

    getMatch(matchId: number): Promise<MatchData | null>;
    getPlayerProfile(accountId: string): Promise<PlayerProfileData | null>;
    getPlayerRecentMatches(accountId: string, limit?: number): Promise<PlayerRecentMatchData[]>;
    getPlayerPeers(accountId: string, limit?: number): Promise<PeerData[]>;
    getPlayerWinLoss(accountId: string): Promise<WinLossData>;
}
