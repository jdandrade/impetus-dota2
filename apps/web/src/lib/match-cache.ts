/**
 * LocalStorage cache for enriched match data.
 * Limits to 100 most recent matches per player.
 */

import type { EnrichedMatch } from "./opendota";

const CACHE_PREFIX = "impetus:match:";
const MAX_MATCHES_PER_PLAYER = 100;
const PLAYER_INDEX_KEY = "impetus:player-matches:";

interface CacheEntry {
    data: Partial<EnrichedMatch>;
    timestamp: number;
}

interface PlayerMatchIndex {
    matchIds: number[];  // Ordered by recency (most recent first)
}

/**
 * Check if localStorage is available
 */
function isLocalStorageAvailable(): boolean {
    try {
        const test = "__test__";
        localStorage.setItem(test, test);
        localStorage.removeItem(test);
        return true;
    } catch {
        return false;
    }
}

/**
 * Get cache key for a specific match and player
 */
function getCacheKey(matchId: number, accountId: string): string {
    return `${CACHE_PREFIX}${accountId}:${matchId}`;
}

/**
 * Get player index key
 */
function getPlayerIndexKey(accountId: string): string {
    return `${PLAYER_INDEX_KEY}${accountId}`;
}

/**
 * Get player's match index (list of cached match IDs)
 */
function getPlayerMatchIndex(accountId: string): PlayerMatchIndex {
    if (!isLocalStorageAvailable()) return { matchIds: [] };

    try {
        const stored = localStorage.getItem(getPlayerIndexKey(accountId));
        if (stored) {
            return JSON.parse(stored) as PlayerMatchIndex;
        }
    } catch {
        // Corrupted data, reset
    }
    return { matchIds: [] };
}

/**
 * Save player's match index
 */
function savePlayerMatchIndex(accountId: string, index: PlayerMatchIndex): void {
    if (!isLocalStorageAvailable()) return;

    try {
        localStorage.setItem(getPlayerIndexKey(accountId), JSON.stringify(index));
    } catch {
        // Storage full or other error, ignore
    }
}

/**
 * Get cached enriched match data
 */
export function getCachedEnrichedMatch(
    matchId: number,
    accountId: string
): Partial<EnrichedMatch> | null {
    if (!isLocalStorageAvailable()) return null;

    try {
        const stored = localStorage.getItem(getCacheKey(matchId, accountId));
        if (stored) {
            const entry = JSON.parse(stored) as CacheEntry;
            return entry.data;
        }
    } catch {
        // Corrupted data
    }
    return null;
}

/**
 * Cache enriched match data
 */
export function cacheEnrichedMatch(
    matchId: number,
    accountId: string,
    data: Partial<EnrichedMatch>
): void {
    if (!isLocalStorageAvailable()) return;

    try {
        // Get current player index
        const index = getPlayerMatchIndex(accountId);

        // Add this match to the front (most recent)
        const matchIdIndex = index.matchIds.indexOf(matchId);
        if (matchIdIndex > -1) {
            // Already exists, move to front
            index.matchIds.splice(matchIdIndex, 1);
        }
        index.matchIds.unshift(matchId);

        // Enforce limit - remove oldest matches if over limit
        while (index.matchIds.length > MAX_MATCHES_PER_PLAYER) {
            const oldMatchId = index.matchIds.pop();
            if (oldMatchId !== undefined) {
                localStorage.removeItem(getCacheKey(oldMatchId, accountId));
            }
        }

        // Save the match data
        const entry: CacheEntry = {
            data,
            timestamp: Date.now(),
        };
        localStorage.setItem(getCacheKey(matchId, accountId), JSON.stringify(entry));

        // Save updated index
        savePlayerMatchIndex(accountId, index);
    } catch {
        // Storage full or other error - try to clear some space
        try {
            // Clear oldest entries for this player
            const index = getPlayerMatchIndex(accountId);
            const toRemove = index.matchIds.slice(50); // Keep only 50
            toRemove.forEach(id => {
                localStorage.removeItem(getCacheKey(id, accountId));
            });
            index.matchIds = index.matchIds.slice(0, 50);
            savePlayerMatchIndex(accountId, index);
        } catch {
            // Give up
        }
    }
}

/**
 * Get all cached matches for a player (for bulk lookup)
 */
export function getCachedMatchesForPlayer(
    accountId: string
): Record<number, Partial<EnrichedMatch>> {
    if (!isLocalStorageAvailable()) return {};

    const result: Record<number, Partial<EnrichedMatch>> = {};
    const index = getPlayerMatchIndex(accountId);

    for (const matchId of index.matchIds) {
        const cached = getCachedEnrichedMatch(matchId, accountId);
        if (cached) {
            result[matchId] = cached;
        }
    }

    return result;
}

/**
 * Clear all cached matches for a player
 */
export function clearPlayerCache(accountId: string): void {
    if (!isLocalStorageAvailable()) return;

    const index = getPlayerMatchIndex(accountId);
    for (const matchId of index.matchIds) {
        localStorage.removeItem(getCacheKey(matchId, accountId));
    }
    localStorage.removeItem(getPlayerIndexKey(accountId));
}
