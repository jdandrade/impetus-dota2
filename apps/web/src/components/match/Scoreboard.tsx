"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { Shield, Swords, Trophy, Skull, Target, Coins, Zap, Crown } from "lucide-react";
import type { CalculateIMPResponse } from "@/lib/imp-client";
import { getHeroImageUrl, getRankImageUrl, getRankName } from "@/lib/opendota";
import { getItemImageUrl, getItemDisplayName } from "@/lib/items";
import RoleIcon, { type Role } from "./RoleIcon";

interface PlayerScore {
    playerIndex: number;
    heroId: number;
    heroName: string;
    isRadiant: boolean;
    kills: number;
    deaths: number;
    assists: number;
    gpm: number;
    xpm: number;
    netWorth: number;
    heroDamage: number;
    towerDamage: number;
    items: number[];
    itemNeutral: number;
    role: Role;  // Detected role based on net worth
    // Player identity
    personaname?: string;
    rankTier?: number | null;
    // IMP result
    impResult: CalculateIMPResponse | null;
    error: string | null;
}

interface ScoreboardProps {
    team: "radiant" | "dire";
    isWinner: boolean;
    players: PlayerScore[];
    mvpPlayerIndex?: number;  // Index of the MVP across both teams
}

const GRADE_COLORS: Record<string, string> = {
    S: "text-fuchsia-400 drop-shadow-[0_0_10px_rgba(232,121,249,0.6)]",
    A: "text-purple-400 drop-shadow-[0_0_6px_rgba(168,85,247,0.4)]",
    B: "text-teal-400",
    C: "text-gray-400",
    D: "text-orange-400",
    F: "text-red-500",
};

const GRADE_BG: Record<string, string> = {
    S: "bg-fuchsia-500/20",
    A: "bg-purple-500/20",
    B: "bg-teal-500/10",
    C: "bg-gray-500/10",
    D: "bg-orange-500/10",
    F: "bg-red-500/15",
};

/**
 * Stratz-style score coloring
 * > +20: Purple/Fuchsia (Top Tier)
 * > 0: Green (Positive)
 * <= 0: Gray/Red (Negative)
 */
function getScoreColor(score: number): string {
    if (score >= 40) return "text-fuchsia-400 drop-shadow-[0_0_12px_rgba(232,121,249,0.7)]";
    if (score >= 20) return "text-purple-400 drop-shadow-[0_0_8px_rgba(168,85,247,0.5)]";
    if (score > 0) return "text-green-400";
    if (score > -20) return "text-gray-400";
    return "text-red-400";
}

function getScoreBg(score: number): string {
    if (score >= 40) return "bg-fuchsia-500/10";
    if (score >= 20) return "bg-purple-500/5";
    if (score > 0) return "bg-green-500/5";
    if (score > -20) return "bg-transparent";
    return "bg-red-500/5";
}

/**
 * Format score with sign (Stratz style)
 */
function formatScore(score: number): string {
    const rounded = score.toFixed(1);
    if (score > 0) return `+${rounded}`;
    return rounded;
}

function formatNumber(num: number): string {
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + "k";
    }
    return num.toString();
}

/**
 * ItemSlot Component - Displays a single item or empty slot
 */
function ItemSlot({ itemId, isNeutral = false }: { itemId: number; isNeutral?: boolean }) {
    const imageUrl = getItemImageUrl(itemId);
    const itemName = itemId > 0 ? getItemDisplayName(itemId) : "Empty";

    if (!imageUrl || itemId === 0) {
        return (
            <div
                className={`flex-shrink-0 bg-cyber-surface-light/30 ${isNeutral ? "w-7 h-7 rounded-full" : "w-9 h-7 rounded"
                    }`}
                title={itemName}
            />
        );
    }

    return (
        <div
            className={`relative flex-shrink-0 overflow-hidden ${isNeutral
                ? "w-7 h-7 rounded-full border border-yellow-500/50"
                : "w-9 h-7 rounded"
                }`}
            title={itemName}
        >
            <Image
                src={imageUrl}
                alt={itemName}
                fill
                className="object-cover"
                sizes="36px"
                unoptimized
            />
        </div>
    );
}

/**
 * ItemRow Component - Displays all items for a player
 */
function ItemRow({ items, itemNeutral }: { items: number[]; itemNeutral: number }) {
    return (
        <div className="flex items-center gap-0.5">
            {items.map((itemId, index) => (
                <ItemSlot key={index} itemId={itemId} />
            ))}
            <div className="w-1" />
            <ItemSlot itemId={itemNeutral} isNeutral />
        </div>
    );
}

export default function Scoreboard({ team, isWinner, players, mvpPlayerIndex }: ScoreboardProps) {
    const isRadiant = team === "radiant";
    const TeamIcon = isRadiant ? Shield : Swords;
    const teamColor = isRadiant ? "text-green-400" : "text-red-400";
    const teamBorderColor = isRadiant ? "border-green-500/30" : "border-red-500/30";
    const winnerGlow = isWinner
        ? isRadiant
            ? "shadow-[0_0_40px_-10px_rgba(34,197,94,0.4)]"
            : "shadow-[0_0_40px_-10px_rgba(239,68,68,0.4)]"
        : "";
    const teamBgGlow = isRadiant
        ? "from-green-500/5 to-transparent"
        : "from-red-500/5 to-transparent";

    // Calculate team totals
    const totals = players.reduce(
        (acc, p) => ({
            kills: acc.kills + p.kills,
            deaths: acc.deaths + p.deaths,
            assists: acc.assists + p.assists,
            netWorth: acc.netWorth + p.netWorth,
        }),
        { kills: 0, deaths: 0, assists: 0, netWorth: 0 }
    );

    // Calculate team average IMP
    const validScores = players
        .filter((p) => p.impResult?.data.imp_score !== undefined)
        .map((p) => p.impResult!.data.imp_score);
    const avgImp =
        validScores.length > 0
            ? validScores.reduce((a, b) => a + b, 0) / validScores.length
            : 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`glass rounded-2xl overflow-hidden border-2 ${teamBorderColor} ${winnerGlow}`}
        >
            {/* Team Header */}
            <div
                className={`bg-gradient-to-r ${teamBgGlow} p-4 border-b ${teamBorderColor}`}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <TeamIcon className={`w-7 h-7 ${teamColor}`} />
                        <h2 className={`text-2xl font-bold ${teamColor}`}>
                            {isRadiant ? "Radiant" : "Dire"}
                        </h2>
                        {isWinner && (
                            <motion.div
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: "spring", delay: 0.3 }}
                                className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-yellow-500/20 border border-yellow-500/30"
                            >
                                <Trophy className="w-4 h-4 text-yellow-400" />
                                <span className="text-sm text-yellow-400 font-bold tracking-wide">
                                    VICTORY
                                </span>
                            </motion.div>
                        )}
                    </div>

                    <div className="flex items-center gap-8 text-sm">
                        <div className="flex items-center gap-2">
                            <Target className="w-4 h-4 text-cyber-text-muted" />
                            <span className="text-cyber-text font-mono text-lg">
                                <span className="text-green-400">{totals.kills}</span>
                                <span className="text-cyber-text-muted">/</span>
                                <span className="text-red-400">{totals.deaths}</span>
                                <span className="text-cyber-text-muted">/</span>
                                <span className="text-teal-400">{totals.assists}</span>
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Coins className="w-4 h-4 text-yellow-500" />
                            <span className="text-cyber-text font-mono text-lg">
                                {formatNumber(totals.netWorth)}
                            </span>
                        </div>
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-primary/10">
                            <Zap className="w-4 h-4 text-brand-primary" />
                            <span className={`font-bold text-lg ${getScoreColor(avgImp)}`}>
                                {formatScore(avgImp)}
                            </span>
                            <span className="text-xs text-cyber-text-muted">AVG IMP</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="border-b border-cyber-border text-cyber-text-muted text-sm">
                            <th className="text-left py-3 px-4 font-medium w-[200px]">Hero</th>
                            <th className="text-center py-3 px-2 font-medium">
                                <div className="flex items-center justify-center gap-1">
                                    <Skull className="w-3 h-3" />
                                    <span>K/D/A</span>
                                </div>
                            </th>
                            <th className="text-left py-3 px-2 font-medium">Items</th>
                            <th className="text-center py-3 px-2 font-medium">GPM</th>
                            <th className="text-center py-3 px-2 font-medium">Net Worth</th>
                            <th className="text-center py-3 px-4 font-medium w-[140px]">
                                <div className="flex items-center justify-center gap-1">
                                    <Zap className="w-4 h-4 text-brand-primary" />
                                    <span className="text-brand-primary font-semibold">IMP Score</span>
                                </div>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {players.map((player, index) => {
                            const isMVP = mvpPlayerIndex === player.playerIndex;
                            return (
                                <motion.tr
                                    key={player.playerIndex}
                                    initial={{ opacity: 0, x: isRadiant ? -20 : 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.08 }}
                                    className={`border-b border-cyber-border/50 hover:bg-cyber-surface-light/40 transition-colors
                                        ${player.impResult ? getScoreBg(player.impResult.data.imp_score) : ""}
                                        ${isMVP ? "bg-yellow-500/10" : ""}`}
                                >
                                    {/* Hero + Player Identity */}
                                    <td className="py-2 px-4">
                                        <div className="flex items-center gap-3">
                                            {/* Role Icon */}
                                            <RoleIcon role={player.role} size={18} />
                                            {/* Hero Portrait */}
                                            <div className="relative w-14 h-8 rounded overflow-hidden bg-cyber-surface-light flex-shrink-0">
                                                <Image
                                                    src={getHeroImageUrl(player.heroId, "portrait")}
                                                    alt={player.heroName}
                                                    fill
                                                    className="object-cover object-top"
                                                    sizes="56px"
                                                    unoptimized
                                                />
                                            </div>
                                            {/* Player Info */}
                                            <div className="flex flex-col min-w-0">
                                                {/* Player Name Row */}
                                                <div className="flex items-center gap-1.5">
                                                    {/* Rank Medal */}
                                                    {player.rankTier && player.rankTier > 0 && (
                                                        <div
                                                            className="relative w-5 h-5 flex-shrink-0"
                                                            title={getRankName(player.rankTier)}
                                                        >
                                                            <Image
                                                                src={getRankImageUrl(player.rankTier) || ""}
                                                                alt={getRankName(player.rankTier)}
                                                                fill
                                                                className="object-contain"
                                                                sizes="20px"
                                                                unoptimized
                                                            />
                                                        </div>
                                                    )}
                                                    {/* MVP Crown */}
                                                    {isMVP && (
                                                        <motion.div
                                                            initial={{ scale: 0, rotate: -30 }}
                                                            animate={{ scale: 1, rotate: 0 }}
                                                            transition={{ type: "spring", delay: 0.5 }}
                                                        >
                                                            <Crown className="w-4 h-4 text-yellow-400 drop-shadow-[0_0_6px_rgba(250,204,21,0.6)]" />
                                                        </motion.div>
                                                    )}
                                                    {/* Player Name */}
                                                    <span className={`font-semibold text-sm truncate max-w-[120px] ${isMVP ? "text-yellow-300" : "text-white"}`}>
                                                        {player.personaname || "Anonymous"}
                                                    </span>
                                                </div>
                                                {/* Hero Name Row */}
                                                <span className="text-xs text-cyber-text-muted truncate max-w-[140px]">
                                                    {player.heroName}
                                                </span>
                                            </div>
                                        </div>
                                    </td>

                                    {/* K/D/A */}
                                    <td className="text-center py-2 px-2">
                                        <span className="font-mono text-sm">
                                            <span className="text-green-400 font-semibold">{player.kills}</span>
                                            <span className="text-cyber-text-muted">/</span>
                                            <span className="text-red-400 font-semibold">{player.deaths}</span>
                                            <span className="text-cyber-text-muted">/</span>
                                            <span className="text-teal-400">{player.assists}</span>
                                        </span>
                                    </td>

                                    {/* Items */}
                                    <td className="py-2 px-2">
                                        <ItemRow items={player.items} itemNeutral={player.itemNeutral} />
                                    </td>

                                    {/* GPM */}
                                    <td className="text-center py-2 px-2">
                                        <span className="font-mono text-yellow-400">{player.gpm}</span>
                                    </td>

                                    {/* Net Worth */}
                                    <td className="text-center py-2 px-2">
                                        <span className="font-mono text-yellow-500">
                                            {formatNumber(player.netWorth)}
                                        </span>
                                    </td>

                                    {/* IMP Score - Stratz Style */}
                                    <td className="text-center py-2 px-4">
                                        {player.impResult ? (
                                            <div className="flex items-center justify-center gap-2">
                                                <span
                                                    className={`font-black text-2xl tabular-nums ${getScoreColor(
                                                        player.impResult.data.imp_score
                                                    )}`}
                                                >
                                                    {formatScore(player.impResult.data.imp_score)}
                                                </span>
                                                <span
                                                    className={`text-xs font-bold px-1.5 py-0.5 rounded ${GRADE_COLORS[player.impResult.data.grade]
                                                        } ${GRADE_BG[player.impResult.data.grade]}`}
                                                >
                                                    {player.impResult.data.grade}
                                                </span>
                                            </div>
                                        ) : player.error ? (
                                            <span className="text-red-400 text-sm">Error</span>
                                        ) : (
                                            <span className="text-cyber-text-muted">--</span>
                                        )}
                                    </td>
                                </motion.tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </motion.div>
    );
}
