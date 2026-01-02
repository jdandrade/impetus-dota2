/**
 * Tracked players configuration for the web app.
 * These players get special features like AI coaching analysis.
 */

// Steam ID 64 -> Display name mapping
export const TRACKED_PLAYERS: Record<string, string> = {
    "76561198349926313": "fear",
    "76561198031378148": "rybur",
    "76561198044301453": "batatas",
    "76561197986252478": "gil",
    "76561197994301802": "mauzaum",
    "76561198014373442": "hory",
    "76561199837733852": "mister miagy",
};

// Steam 32 Account IDs (computed from Steam64)
// Formula: Steam32 = Steam64 - 76561197960265728
export const TRACKED_ACCOUNT_IDS: Record<number, string> = {
    389660585: "fear",    // 76561198349926313 - 76561197960265728
    71112420: "rybur",    // 76561198031378148 - 76561197960265728
    84035725: "batatas",  // 76561198044301453 - 76561197960265728
    25986750: "gil",      // 76561197986252478 - 76561197960265728
    34036074: "mauzaum",  // 76561197994301802 - 76561197960265728
    54107714: "hory",     // 76561198014373442 - 76561197960265728
    1877468124: "mister miagy", // 76561199837733852 - 76561197960265728
};

/**
 * Check if an account ID belongs to a tracked player
 */
export function isTrackedPlayer(accountId: number | null | undefined): boolean {
    if (!accountId) return false;
    return accountId in TRACKED_ACCOUNT_IDS;
}

/**
 * Get tracked player name by account ID
 */
export function getTrackedPlayerName(accountId: number | null | undefined): string | null {
    if (!accountId) return null;
    return TRACKED_ACCOUNT_IDS[accountId] || null;
}
