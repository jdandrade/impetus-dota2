/**
 * OpenDota API Client
 *
 * Fetches match data from the OpenDota public API.
 * API Docs: https://docs.opendota.com/
 */

const OPENDOTA_API_URL = "https://api.opendota.com/api";

/**
 * Player data from OpenDota match response.
 * Only includes fields we need for IMP calculation.
 */
export interface OpenDotaPlayer {
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
    // Item slots (6 main + 1 neutral)
    item_0: number;
    item_1: number;
    item_2: number;
    item_3: number;
    item_4: number;
    item_5: number;
    item_neutral: number;
    backpack_0: number;
    backpack_1: number;
    backpack_2: number;
    // Player identity
    personaname?: string;
    rank_tier?: number | null;
    // Derived/computed fields
    isRadiant: boolean;
}

/**
 * Minimal match data structure from OpenDota.
 * Full response has many more fields, but we only extract what we need.
 */
export interface OpenDotaMatch {
    match_id: number;
    duration: number; // seconds
    radiant_win: boolean;
    game_mode: number;
    avg_rank_tier: number | null;
    players: OpenDotaPlayer[];
}

/**
 * Game mode mapping (partial - common modes)
 */
const GAME_MODES: Record<number, string> = {
    0: "unknown",
    1: "all_pick",
    2: "captains_mode",
    3: "random_draft",
    4: "single_draft",
    5: "all_random",
    12: "least_played",
    16: "captains_draft",
    18: "ability_draft",
    22: "ranked_all_pick",
    23: "turbo",
};

/**
 * Hero ID to name mapping (complete as of 7.38)
 */
const HERO_NAMES: Record<number, string> = {
    1: "Anti-Mage",
    2: "Axe",
    3: "Bane",
    4: "Bloodseeker",
    5: "Crystal Maiden",
    6: "Drow Ranger",
    7: "Earthshaker",
    8: "Juggernaut",
    9: "Mirana",
    10: "Morphling",
    11: "Shadow Fiend",
    12: "Phantom Lancer",
    13: "Puck",
    14: "Pudge",
    15: "Razor",
    16: "Sand King",
    17: "Storm Spirit",
    18: "Sven",
    19: "Tiny",
    20: "Vengeful Spirit",
    21: "Windranger",
    22: "Zeus",
    23: "Kunkka",
    25: "Lina",
    26: "Lion",
    27: "Shadow Shaman",
    28: "Slardar",
    29: "Tidehunter",
    30: "Witch Doctor",
    31: "Lich",
    32: "Riki",
    33: "Enigma",
    34: "Tinker",
    35: "Sniper",
    36: "Necrophos",
    37: "Warlock",
    38: "Beastmaster",
    39: "Queen of Pain",
    40: "Venomancer",
    41: "Faceless Void",
    42: "Wraith King",
    43: "Death Prophet",
    44: "Phantom Assassin",
    45: "Pugna",
    46: "Templar Assassin",
    47: "Viper",
    48: "Luna",
    49: "Dragon Knight",
    50: "Dazzle",
    51: "Clockwerk",
    52: "Leshrac",
    53: "Nature's Prophet",
    54: "Lifestealer",
    55: "Dark Seer",
    56: "Clinkz",
    57: "Omniknight",
    58: "Enchantress",
    59: "Huskar",
    60: "Night Stalker",
    61: "Broodmother",
    62: "Bounty Hunter",
    63: "Weaver",
    64: "Jakiro",
    65: "Batrider",
    66: "Chen",
    67: "Spectre",
    68: "Ancient Apparition",
    69: "Doom",
    70: "Ursa",
    71: "Spirit Breaker",
    72: "Gyrocopter",
    73: "Alchemist",
    74: "Invoker",
    75: "Silencer",
    76: "Outworld Destroyer",
    77: "Lycan",
    78: "Brewmaster",
    79: "Shadow Demon",
    80: "Lone Druid",
    81: "Chaos Knight",
    82: "Meepo",
    83: "Treant Protector",
    84: "Ogre Magi",
    85: "Undying",
    86: "Rubick",
    87: "Disruptor",
    88: "Nyx Assassin",
    89: "Naga Siren",
    90: "Keeper of the Light",
    91: "Io",
    92: "Visage",
    93: "Slark",
    94: "Medusa",
    95: "Troll Warlord",
    96: "Centaur Warrunner",
    97: "Magnus",
    98: "Timbersaw",
    99: "Bristleback",
    100: "Tusk",
    101: "Skywrath Mage",
    102: "Abaddon",
    103: "Elder Titan",
    104: "Legion Commander",
    105: "Techies",
    106: "Ember Spirit",
    107: "Earth Spirit",
    108: "Underlord",
    109: "Terrorblade",
    110: "Phoenix",
    111: "Oracle",
    112: "Winter Wyvern",
    113: "Arc Warden",
    114: "Monkey King",
    119: "Dark Willow",
    120: "Pangolier",
    121: "Grimstroke",
    123: "Hoodwink",
    126: "Void Spirit",
    128: "Snapfire",
    129: "Mars",
    131: "Ringmaster",
    135: "Dawnbreaker",
    136: "Marci",
    137: "Primal Beast",
    138: "Muerta",
    145: "Kez",
    155: "Largo",
};

/**
 * Get hero name by ID, with fallback.
 */
export function getHeroName(heroId: number): string {
    return HERO_NAMES[heroId] || `Hero #${heroId}`;
}

/**
 * Hero ID to URL slug mapping for CDN images.
 * Format matches OpenDota CDN: https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{slug}.png
 */
const HERO_SLUGS: Record<number, string> = {
    1: "antimage",
    2: "axe",
    3: "bane",
    4: "bloodseeker",
    5: "crystal_maiden",
    6: "drow_ranger",
    7: "earthshaker",
    8: "juggernaut",
    9: "mirana",
    10: "morphling",
    11: "nevermore",
    12: "phantom_lancer",
    13: "puck",
    14: "pudge",
    15: "razor",
    16: "sand_king",
    17: "storm_spirit",
    18: "sven",
    19: "tiny",
    20: "vengefulspirit",
    21: "windrunner",
    22: "zuus",
    23: "kunkka",
    25: "lina",
    26: "lion",
    27: "shadow_shaman",
    28: "slardar",
    29: "tidehunter",
    30: "witch_doctor",
    31: "lich",
    32: "riki",
    33: "enigma",
    34: "tinker",
    35: "sniper",
    36: "necrolyte",
    37: "warlock",
    38: "beastmaster",
    39: "queenofpain",
    40: "venomancer",
    41: "faceless_void",
    42: "skeleton_king",
    43: "death_prophet",
    44: "phantom_assassin",
    45: "pugna",
    46: "templar_assassin",
    47: "viper",
    48: "luna",
    49: "dragon_knight",
    50: "dazzle",
    51: "rattletrap",
    52: "leshrac",
    53: "furion",
    54: "life_stealer",
    55: "dark_seer",
    56: "clinkz",
    57: "omniknight",
    58: "enchantress",
    59: "huskar",
    60: "night_stalker",
    61: "broodmother",
    62: "bounty_hunter",
    63: "weaver",
    64: "jakiro",
    65: "batrider",
    66: "chen",
    67: "spectre",
    68: "ancient_apparition",
    69: "doom_bringer",
    70: "ursa",
    71: "spirit_breaker",
    72: "gyrocopter",
    73: "alchemist",
    74: "invoker",
    75: "silencer",
    76: "obsidian_destroyer",
    77: "lycan",
    78: "brewmaster",
    79: "shadow_demon",
    80: "lone_druid",
    81: "chaos_knight",
    82: "meepo",
    83: "treant",
    84: "ogre_magi",
    85: "undying",
    86: "rubick",
    87: "disruptor",
    88: "nyx_assassin",
    89: "naga_siren",
    90: "keeper_of_the_light",
    91: "wisp",
    92: "visage",
    93: "slark",
    94: "medusa",
    95: "troll_warlord",
    96: "centaur",
    97: "magnataur",
    98: "shredder",
    99: "bristleback",
    100: "tusk",
    101: "skywrath_mage",
    102: "abaddon",
    103: "elder_titan",
    104: "legion_commander",
    105: "techies",
    106: "ember_spirit",
    107: "earth_spirit",
    108: "abyssal_underlord",
    109: "terrorblade",
    110: "phoenix",
    111: "oracle",
    112: "winter_wyvern",
    113: "arc_warden",
    114: "monkey_king",
    119: "dark_willow",
    120: "pangolier",
    121: "grimstroke",
    123: "hoodwink",
    126: "void_spirit",
    128: "snapfire",
    129: "mars",
    131: "ringmaster",
    135: "dawnbreaker",
    136: "marci",
    137: "primal_beast",
    138: "muerta",
    145: "kez",
    155: "largo",
};

/**
 * Get hero image URL from Steam CDN.
 * @param heroId - Dota 2 hero ID
 * @param type - Image type: 'icon' (small square), 'portrait' (full portrait), 'landscape' (horizontal)
 */
export function getHeroImageUrl(heroId: number, type: "icon" | "portrait" | "landscape" = "icon"): string {
    const slug = HERO_SLUGS[heroId];

    if (!slug) {
        // Fallback to a placeholder
        return `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/default.png`;
    }

    // Steam CDN URLs for different formats
    switch (type) {
        case "icon":
            return `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/icons/${slug}.png`;
        case "portrait":
            return `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${slug}.png`;
        case "landscape":
            // Landscape format (used in match scoreboards)
            return `https://cdn.dota2.com/apps/dota2/images/heroes/${slug}_lg.png`;
        default:
            return `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${slug}.png`;
    }
}

/**
 * Get rank medal image URL.
 * @param rankTier - OpenDota rank tier (e.g., 75 = Ancient 5)
 */
export function getRankImageUrl(rankTier: number | null): string | null {
    if (!rankTier || rankTier <= 0) return null;

    // Rank tier format: first digit is medal (1-8), second is stars (0-5)
    const medal = Math.floor(rankTier / 10);

    // Valve's rank images
    // Medal: 1=Herald, 2=Guardian, 3=Crusader, 4=Archon, 5=Legend, 6=Ancient, 7=Divine, 8=Immortal
    if (medal < 1 || medal > 8) return null;

    // OpenDota uses their own CDN for rank medals
    return `https://www.opendota.com/assets/images/dota2/rank_icons/rank_icon_${medal}.png`;
}

/**
 * Get rank name from tier.
 */
export function getRankName(rankTier: number | null): string {
    if (!rankTier || rankTier <= 0) return "Unranked";

    const medal = Math.floor(rankTier / 10);
    const stars = rankTier % 10;

    const medalNames: Record<number, string> = {
        1: "Herald",
        2: "Guardian",
        3: "Crusader",
        4: "Archon",
        5: "Legend",
        6: "Ancient",
        7: "Divine",
        8: "Immortal",
    };

    const name = medalNames[medal] || "Unknown";
    return stars > 0 ? `${name} ${stars}` : name;
}

/**
 * Get game mode name by ID.
 */
export function getGameModeName(gameModeId: number): string {
    return GAME_MODES[gameModeId] || "unknown";
}

/**
 * Request OpenDota to parse a match replay.
 * This queues the match for parsing - player names and other data will be available after parsing completes.
 * 
 * @returns Job object with job_id if successful, null otherwise
 */
export async function requestMatchParse(matchId: string): Promise<{ job_id: number } | null> {
    try {
        const response = await fetch(`${OPENDOTA_API_URL}/request/${matchId}`, {
            method: "POST",
        });

        if (!response.ok) {
            console.warn(`Failed to request parse for match ${matchId}: ${response.status}`);
            return null;
        }

        const data = await response.json();
        console.log(`Parse requested for match ${matchId}, job_id: ${data.job?.jobId}`);
        return { job_id: data.job?.jobId };
    } catch (error) {
        console.error(`Error requesting parse for match ${matchId}:`, error);
        return null;
    }
}

/**
 * Check if a match appears to be fully parsed.
 * Unparsed matches have many players with null account_id and missing personaname.
 */
export function isMatchFullyParsed(players: OpenDotaPlayer[]): boolean {
    // Count players with missing data (no account_id AND no personaname)
    const unparsedCount = players.filter(p => !p.account_id && !p.personaname).length;

    // If more than 3 players are missing data, likely unparsed
    return unparsedCount <= 3;
}

/**
 * Fetch player profile from OpenDota to get their name.
 * Returns null if player not found or has private profile.
 */
export async function fetchPlayerProfile(accountId: number): Promise<{ personaname: string; rank_tier: number | null } | null> {
    try {
        const response = await fetch(`${OPENDOTA_API_URL}/players/${accountId}`);
        if (!response.ok) return null;

        const data = await response.json();
        return {
            personaname: data.profile?.personaname || null,
            rank_tier: data.rank_tier || null,
        };
    } catch {
        return null;
    }
}

/**
 * Enrich players with missing names by fetching their profiles.
 * Batches requests and only fetches for players with account_id but no personaname.
 */
export async function enrichPlayerProfiles(players: OpenDotaPlayer[]): Promise<OpenDotaPlayer[]> {
    const enrichPromises = players.map(async (player) => {
        // Skip if already has a name or no account_id
        if (player.personaname || !player.account_id) {
            return player;
        }

        // Fetch profile
        const profile = await fetchPlayerProfile(player.account_id);
        if (profile) {
            return {
                ...player,
                personaname: profile.personaname || player.personaname,
                rank_tier: profile.rank_tier || player.rank_tier,
            };
        }

        return player;
    });

    return Promise.all(enrichPromises);
}

/**
 * Fetch match details from OpenDota API.
 */
export async function getMatchDetails(matchId: string): Promise<OpenDotaMatch> {
    const response = await fetch(`${OPENDOTA_API_URL}/matches/${matchId}`);

    if (!response.ok) {
        if (response.status === 404) {
            throw new Error(`Match ${matchId} not found. It may not be parsed yet.`);
        }
        throw new Error(`OpenDota API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Transform player data to include isRadiant flag with safety defaults
    const players: OpenDotaPlayer[] = data.players.map((p: Record<string, unknown>) => ({
        account_id: (p.account_id as number | null) ?? null,
        player_slot: (p.player_slot as number) ?? 0,
        hero_id: (p.hero_id as number) ?? 0,
        kills: (p.kills as number) ?? 0,
        deaths: (p.deaths as number) ?? 0,
        assists: (p.assists as number) ?? 0,
        last_hits: (p.last_hits as number) ?? 0,
        denies: (p.denies as number) ?? 0,
        gold_per_min: (p.gold_per_min as number) ?? 0,
        xp_per_min: (p.xp_per_min as number) ?? 0,
        hero_damage: (p.hero_damage as number) ?? 0,
        tower_damage: (p.tower_damage as number) ?? 0,
        hero_healing: (p.hero_healing as number) ?? 0,
        level: (p.level as number) ?? 1,
        net_worth: (p.net_worth as number) ?? 0,
        // Item slots
        item_0: (p.item_0 as number) ?? 0,
        item_1: (p.item_1 as number) ?? 0,
        item_2: (p.item_2 as number) ?? 0,
        item_3: (p.item_3 as number) ?? 0,
        item_4: (p.item_4 as number) ?? 0,
        item_5: (p.item_5 as number) ?? 0,
        item_neutral: (p.item_neutral as number) ?? 0,
        backpack_0: (p.backpack_0 as number) ?? 0,
        backpack_1: (p.backpack_1 as number) ?? 0,
        backpack_2: (p.backpack_2 as number) ?? 0,
        // Player identity
        personaname: (p.personaname as string | undefined) ?? undefined,
        rank_tier: (p.rank_tier as number | null) ?? null,
        // Player slots 0-127 are Radiant, 128-255 are Dire
        isRadiant: ((p.player_slot as number) ?? 0) < 128,
    }));

    return {
        match_id: data.match_id,
        duration: data.duration,
        radiant_win: data.radiant_win,
        game_mode: data.game_mode,
        avg_rank_tier: data.avg_rank_tier,
        players,
    };
}

/**
 * Convert OpenDota rank tier (e.g., 75 = Ancient 5) to a 0-100 scale.
 * Rank tiers: 10-15 (Herald), 20-25 (Guardian), 30-35 (Crusader), 
 *             40-45 (Archon), 50-55 (Legend), 60-65 (Ancient), 
 *             70-75 (Divine), 80+ (Immortal)
 */
export function normalizeRankTier(rankTier: number | null): number {
    if (!rankTier) return 50; // Default to median if unknown

    // Convert 10-80+ to 0-100
    const normalized = Math.min(100, Math.max(0, ((rankTier - 10) / 70) * 100));
    return Math.round(normalized);
}

/**
 * Benchmark bucket from OpenDota.
 * Each bucket has a percentile and the stat value at that percentile.
 */
export interface BenchmarkBucket {
    percentile: number;
    value: number;
}

/**
 * Hero benchmarks response structure.
 */
export interface HeroBenchmarks {
    hero_id: number;
    result: {
        gold_per_min: BenchmarkBucket[];
        xp_per_min: BenchmarkBucket[];
        kills_per_min: BenchmarkBucket[];
        last_hits_per_min: BenchmarkBucket[];
        hero_damage_per_min: BenchmarkBucket[];
        hero_healing_per_min: BenchmarkBucket[];
        tower_damage: BenchmarkBucket[];
        stuns_per_min?: BenchmarkBucket[];
        lhten?: BenchmarkBucket[];
    };
}

/**
 * Fetch hero benchmarks from OpenDota API.
 * Benchmarks show stat distributions at various percentiles for a hero.
 */
export async function getHeroBenchmarks(heroId: number): Promise<HeroBenchmarks> {
    const response = await fetch(`${OPENDOTA_API_URL}/benchmarks?hero_id=${heroId}`);

    if (!response.ok) {
        throw new Error(`OpenDota benchmarks error: ${response.status} ${response.statusText}`);
    }

    return response.json();
}

/**
 * Calculate a player's percentile for a stat given benchmark buckets.
 * Uses linear interpolation between benchmark points.
 * 
 * @param value - The player's stat value
 * @param buckets - The benchmark buckets for that stat
 * @returns Percentile (0.0 to 1.0)
 */
export function calculatePercentile(value: number, buckets: BenchmarkBucket[]): number {
    if (!buckets || buckets.length === 0) {
        return 0.5; // Default to median if no data
    }

    // Sort buckets by value (ascending)
    const sorted = [...buckets].sort((a, b) => a.value - b.value);

    // If below lowest benchmark
    if (value <= sorted[0].value) {
        return sorted[0].percentile;
    }

    // If above highest benchmark
    if (value >= sorted[sorted.length - 1].value) {
        return sorted[sorted.length - 1].percentile;
    }

    // Find the two buckets to interpolate between
    for (let i = 0; i < sorted.length - 1; i++) {
        const lower = sorted[i];
        const upper = sorted[i + 1];

        if (value >= lower.value && value <= upper.value) {
            // Linear interpolation
            const ratio = (value - lower.value) / (upper.value - lower.value);
            return lower.percentile + ratio * (upper.percentile - lower.percentile);
        }
    }

    return 0.5; // Fallback
}

/**
 * Calculate all benchmark percentiles for a player.
 * Converts raw stats to per-minute values and calculates percentiles.
 */
export function calculatePlayerBenchmarks(
    player: OpenDotaPlayer,
    durationMinutes: number,
    benchmarks: HeroBenchmarks
): Record<string, number> {
    const b = benchmarks.result;

    return {
        gpm: calculatePercentile(player.gold_per_min, b.gold_per_min),
        xpm: calculatePercentile(player.xp_per_min, b.xp_per_min),
        kills_per_min: calculatePercentile(player.kills / durationMinutes, b.kills_per_min),
        last_hits_per_min: calculatePercentile(player.last_hits / durationMinutes, b.last_hits_per_min),
        hero_damage_per_min: calculatePercentile(player.hero_damage / durationMinutes, b.hero_damage_per_min),
        hero_healing_per_min: calculatePercentile(player.hero_healing / durationMinutes, b.hero_healing_per_min),
        tower_damage: calculatePercentile(player.tower_damage, b.tower_damage),
    };
}

