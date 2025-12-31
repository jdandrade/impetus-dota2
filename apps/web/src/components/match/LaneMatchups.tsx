"use client";

/**
 * Lane Matchups Component
 * Displays lane outcomes similar to Stratz.
 */

import { LaneMatchup, calculateLaneMatchups, hasLaneData } from "@/lib/lane-analysis";
import { OpenDotaPlayer } from "@/lib/opendota";
import Image from "next/image";
import { Swords, ArrowUp, ArrowRight, ArrowDown } from "lucide-react";

interface LaneMatchupsProps {
    players: OpenDotaPlayer[];
}

// Hero icon component with optional highlight for lane winners
function HeroIcon({ heroId, size = 32, highlight }: { heroId: number; size?: number; highlight?: "radiant" | "dire" | null }) {
    const borderClass = highlight === "radiant"
        ? "border-2 border-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]"
        : highlight === "dire"
            ? "border-2 border-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]"
            : "border border-gray-700";

    return (
        <Image
            src={`https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/icons/${getHeroInternalName(heroId)}.png`}
            alt={`Hero ${heroId}`}
            width={size}
            height={size}
            className={`rounded-full ${borderClass}`}
            unoptimized
        />
    );
}

// Get lane display info
function getLaneInfo(lane: "top" | "mid" | "bot"): { name: string; icon: React.ReactNode } {
    switch (lane) {
        case "top":
            return { name: "Top Lane", icon: <ArrowUp className="w-4 h-4" /> };
        case "mid":
            return { name: "Middle Lane", icon: <ArrowRight className="w-4 h-4" /> };
        case "bot":
            return { name: "Bottom Lane", icon: <ArrowDown className="w-4 h-4" /> };
    }
}

// Outcome display configuration
function getOutcomeDisplay(outcome: "radiant" | "dire" | "draw") {
    switch (outcome) {
        case "radiant":
            return { text: "Radiant Won", color: "text-green-400" };
        case "dire":
            return { text: "Dire Won", color: "text-red-400" };
        case "draw":
            return { text: "Draw", color: "text-gray-400" };
    }
}

// Lane matchup card component
function LaneCard({ matchup }: { matchup: LaneMatchup }) {
    const laneInfo = getLaneInfo(matchup.lane);
    const outcomeDisplay = getOutcomeDisplay(matchup.outcome);

    // Determine which side to highlight (null for draw)
    const radiantHighlight = matchup.outcome === "radiant" ? "radiant" : null;
    const direHighlight = matchup.outcome === "dire" ? "dire" : null;

    return (
        <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 flex flex-col items-center gap-3">
            {/* Hero icons: Radiant vs Dire */}
            <div className="flex items-center gap-3">
                {/* Radiant heroes */}
                <div className="flex gap-1">
                    {matchup.radiantHeroes.map((heroId, i) => (
                        <HeroIcon key={`r-${i}`} heroId={heroId} size={36} highlight={radiantHighlight} />
                    ))}
                </div>

                {/* VS divider */}
                <span className="text-gray-500 text-sm font-medium px-2">vs</span>

                {/* Dire heroes */}
                <div className="flex gap-1">
                    {matchup.direHeroes.map((heroId, i) => (
                        <HeroIcon key={`d-${i}`} heroId={heroId} size={36} highlight={direHighlight} />
                    ))}
                </div>
            </div>

            {/* Outcome and lane name */}
            <div className="flex items-center gap-2 text-sm">
                <span className={`font-semibold ${outcomeDisplay.color}`}>
                    {outcomeDisplay.text}
                </span>
                <span className="text-gray-500">•</span>
                <span className="text-gray-400 flex items-center gap-1">
                    {laneInfo.icon}
                    {laneInfo.name}
                </span>
            </div>
        </div>
    );
}

// Hero internal name mapping (simplified - matches common heroes)
const HERO_INTERNAL_NAMES: Record<number, string> = {
    1: "antimage", 2: "axe", 3: "bane", 4: "bloodseeker", 5: "crystal_maiden",
    6: "drow_ranger", 7: "earthshaker", 8: "juggernaut", 9: "mirana", 10: "morphling",
    11: "nevermore", 12: "phantom_lancer", 13: "puck", 14: "pudge", 15: "razor",
    16: "sand_king", 17: "storm_spirit", 18: "sven", 19: "tiny", 20: "vengefulspirit",
    21: "windrunner", 22: "zuus", 23: "kunkka", 25: "lina", 26: "lion",
    27: "shadow_shaman", 28: "slardar", 29: "tidehunter", 30: "witch_doctor",
    31: "lich", 32: "riki", 33: "enigma", 34: "tinker", 35: "sniper",
    36: "necrolyte", 37: "warlock", 38: "beastmaster", 39: "queenofpain", 40: "venomancer",
    41: "faceless_void", 42: "skeleton_king", 43: "death_prophet", 44: "phantom_assassin",
    45: "pugna", 46: "templar_assassin", 47: "viper", 48: "luna", 49: "dragon_knight",
    50: "dazzle", 51: "rattletrap", 52: "leshrac", 53: "furion", 54: "life_stealer",
    55: "dark_seer", 56: "clinkz", 57: "omniknight", 58: "enchantress", 59: "huskar",
    60: "night_stalker", 61: "broodmother", 62: "bounty_hunter", 63: "weaver",
    64: "jakiro", 65: "batrider", 66: "chen", 67: "spectre", 68: "ancient_apparition",
    69: "doom_bringer", 70: "ursa", 71: "spirit_breaker", 72: "gyrocopter",
    73: "alchemist", 74: "invoker", 75: "silencer", 76: "obsidian_destroyer",
    77: "lycan", 78: "brewmaster", 79: "shadow_demon", 80: "lone_druid",
    81: "chaos_knight", 82: "meepo", 83: "treant", 84: "ogre_magi",
    85: "undying", 86: "rubick", 87: "disruptor", 88: "nyx_assassin",
    89: "naga_siren", 90: "keeper_of_the_light", 91: "wisp", 92: "visage",
    93: "slark", 94: "medusa", 95: "troll_warlord", 96: "centaur",
    97: "magnataur", 98: "shredder", 99: "bristleback", 100: "tusk",
    101: "skywrath_mage", 102: "abaddon", 103: "elder_titan", 104: "legion_commander",
    105: "techies", 106: "ember_spirit", 107: "earth_spirit", 108: "abyssal_underlord",
    109: "terrorblade", 110: "phoenix", 111: "oracle", 112: "winter_wyvern",
    113: "arc_warden", 114: "monkey_king", 119: "dark_willow", 120: "pangolier",
    121: "grimstroke", 123: "hoodwink", 126: "void_spirit", 128: "snapfire",
    129: "mars", 135: "dawnbreaker", 136: "marci", 137: "primal_beast",
    138: "muerta", 145: "ringmaster", 146: "kez",
};

function getHeroInternalName(heroId: number): string {
    return HERO_INTERNAL_NAMES[heroId] || `hero_${heroId}`;
}

export default function LaneMatchups({ players }: LaneMatchupsProps) {
    // Check if lane data is available
    if (!hasLaneData(players)) {
        return null; // Don't render if no lane data (unparsed match)
    }

    const matchups = calculateLaneMatchups(players);

    if (matchups.length === 0) {
        return null;
    }

    // Sort lanes: top, mid, bot
    const sortedMatchups = matchups.sort((a, b) => {
        const order = { top: 0, mid: 1, bot: 2 };
        return order[a.lane] - order[b.lane];
    });

    return (
        <div className="bg-gray-900/40 border border-gray-800 rounded-2xl p-6">
            {/* Header */}
            <div className="flex items-center gap-2 mb-4">
                <Swords className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold text-white">Lane Matchups</h2>
            </div>

            {/* Lane cards grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {sortedMatchups.map((matchup) => (
                    <LaneCard key={matchup.lane} matchup={matchup} />
                ))}
            </div>
        </div>
    );
}
