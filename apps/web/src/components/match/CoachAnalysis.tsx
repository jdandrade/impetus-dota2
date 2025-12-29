"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, ChevronDown, Loader2, AlertCircle } from "lucide-react";
import { generateCoachingAnalysis } from "@/lib/gemini";
import { getItemDisplayName } from "@/lib/items";
import { getHeroName, type Role } from "@/lib/opendota";
import ReactMarkdown from "react-markdown";

interface TrackedPlayer {
    playerIndex: number;
    accountId: number;
    displayName: string;
    heroId: number;
    heroName: string;
    role: Role;
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
    impScore?: number;
    impGrade?: string;
}

interface CoachAnalysisProps {
    trackedPlayers: TrackedPlayer[];
    radiantWin: boolean;
    duration: number;
    allPlayers: Array<{
        heroId: number;
        isRadiant: boolean;
    }>;
}

export default function CoachAnalysis({
    trackedPlayers,
    radiantWin,
    duration,
    allPlayers
}: CoachAnalysisProps) {
    const [selectedPlayer, setSelectedPlayer] = useState<TrackedPlayer | null>(null);
    const [showDropdown, setShowDropdown] = useState(false);
    const [analysis, setAnalysis] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Don't render if no tracked players in match
    if (trackedPlayers.length === 0) {
        return null;
    }

    const handleGenerateClick = () => {
        if (trackedPlayers.length === 1) {
            // Only one tracked player - generate immediately
            generateAnalysis(trackedPlayers[0]);
        } else {
            // Multiple tracked players - show dropdown
            setShowDropdown(true);
        }
    };

    const generateAnalysis = async (player: TrackedPlayer) => {
        setSelectedPlayer(player);
        setShowDropdown(false);
        setLoading(true);
        setError(null);
        setAnalysis(null);

        const apiKey = process.env.NEXT_PUBLIC_GEMINI_API_KEY;
        if (!apiKey) {
            setError("Gemini API key not configured");
            setLoading(false);
            return;
        }

        try {
            const won = player.isRadiant === radiantWin;

            // Get enemy and teammate heroes
            const teammates = allPlayers
                .filter(p => p.isRadiant === player.isRadiant && p.heroId !== player.heroId)
                .map(p => getHeroName(p.heroId));
            const enemies = allPlayers
                .filter(p => p.isRadiant !== player.isRadiant)
                .map(p => getHeroName(p.heroId));

            // Get item names
            const items = player.items.map(id => id > 0 ? getItemDisplayName(id) : "Empty");
            const neutralItem = player.itemNeutral > 0 ? getItemDisplayName(player.itemNeutral) : undefined;

            const result = await generateCoachingAnalysis({
                playerName: player.displayName,
                heroName: player.heroName,
                role: player.role,
                isRadiant: player.isRadiant,
                won,
                duration,
                kills: player.kills,
                deaths: player.deaths,
                assists: player.assists,
                gpm: player.gpm,
                xpm: player.xpm,
                netWorth: player.netWorth,
                heroDamage: player.heroDamage,
                towerDamage: player.towerDamage,
                items,
                neutralItem,
                impScore: player.impScore,
                impGrade: player.impGrade,
                enemyHeroes: enemies,
                teammateHeroes: teammates,
            }, apiKey);

            setAnalysis(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to generate analysis");
        } finally {
            setLoading(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
        >
            <div className="glass rounded-2xl overflow-hidden border-2 border-brand-primary/30 shadow-[0_0_30px_-10px_rgba(0,255,170,0.3)]">
                {/* Header */}
                <div className="bg-gradient-to-r from-brand-primary/10 to-brand-secondary/10 p-4 border-b border-brand-primary/20">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-brand-primary/20 flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-brand-primary" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-cyber-text flex items-center gap-2">
                                AI Coach Analysis
                                <span className="text-xs px-2 py-0.5 rounded-full bg-brand-primary/20 text-brand-primary font-medium">
                                    Beta
                                </span>
                            </h2>
                            <p className="text-sm text-cyber-text-muted">
                                Personalized feedback for tracked players
                            </p>
                        </div>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6">
                    {/* Not yet generated */}
                    {!analysis && !loading && !showDropdown && (
                        <div className="text-center">
                            <p className="text-cyber-text-muted mb-4">
                                Get AI-powered coaching tips for{" "}
                                {trackedPlayers.length === 1 ? (
                                    <span className="text-brand-primary font-semibold">
                                        {trackedPlayers[0].displayName}
                                    </span>
                                ) : (
                                    <span className="text-brand-primary font-semibold">
                                        {trackedPlayers.map(p => p.displayName).join(" or ")}
                                    </span>
                                )}
                            </p>
                            <button
                                onClick={handleGenerateClick}
                                className="px-6 py-3 rounded-xl bg-gradient-to-r from-brand-primary to-brand-secondary 
                                         text-cyber-bg font-bold hover:opacity-90 transition-opacity
                                         flex items-center gap-2 mx-auto"
                            >
                                <Sparkles className="w-5 h-5" />
                                How Can I Do Better?
                            </button>
                        </div>
                    )}

                    {/* Player Selection Dropdown */}
                    <AnimatePresence>
                        {showDropdown && (
                            <motion.div
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="text-center"
                            >
                                <p className="text-cyber-text-muted mb-4">Select a player to analyze:</p>
                                <div className="flex gap-3 justify-center flex-wrap">
                                    {trackedPlayers.map((player) => (
                                        <button
                                            key={player.playerIndex}
                                            onClick={() => generateAnalysis(player)}
                                            className="px-4 py-2 rounded-lg bg-cyber-surface-light hover:bg-brand-primary/20 
                                                     border border-cyber-border hover:border-brand-primary/50
                                                     transition-all flex items-center gap-2"
                                        >
                                            <span className="font-semibold text-cyber-text">
                                                {player.displayName}
                                            </span>
                                            <span className="text-xs text-cyber-text-muted">
                                                ({player.heroName})
                                            </span>
                                        </button>
                                    ))}
                                </div>
                                <button
                                    onClick={() => setShowDropdown(false)}
                                    className="mt-4 text-sm text-cyber-text-muted hover:text-cyber-text"
                                >
                                    Cancel
                                </button>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Loading State */}
                    {loading && (
                        <div className="text-center py-8">
                            <Loader2 className="w-8 h-8 animate-spin text-brand-primary mx-auto mb-4" />
                            <p className="text-cyber-text-muted">
                                Analyzing {selectedPlayer?.displayName}&apos;s performance...
                            </p>
                        </div>
                    )}

                    {/* Error State */}
                    {error && (
                        <div className="text-center py-4">
                            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400">
                                <AlertCircle className="w-5 h-5" />
                                {error}
                            </div>
                            <button
                                onClick={() => {
                                    setError(null);
                                    setAnalysis(null);
                                    setSelectedPlayer(null);
                                }}
                                className="block mx-auto mt-4 text-sm text-cyber-text-muted hover:text-cyber-text"
                            >
                                Try Again
                            </button>
                        </div>
                    )}

                    {/* Analysis Result */}
                    {analysis && selectedPlayer && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                        >
                            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-cyber-border/50">
                                <span className="text-lg font-bold text-brand-primary">
                                    {selectedPlayer.displayName}
                                </span>
                                <span className="text-cyber-text-muted">on</span>
                                <span className="text-cyber-text font-medium">
                                    {selectedPlayer.heroName}
                                </span>
                                <span className={`text-sm px-2 py-0.5 rounded ${selectedPlayer.isRadiant === radiantWin
                                        ? "bg-green-500/20 text-green-400"
                                        : "bg-red-500/20 text-red-400"
                                    }`}>
                                    {selectedPlayer.isRadiant === radiantWin ? "Won" : "Lost"}
                                </span>
                            </div>

                            <div className="prose prose-invert prose-sm max-w-none 
                                          prose-headings:text-brand-primary prose-headings:font-bold
                                          prose-strong:text-cyber-text prose-strong:font-semibold
                                          prose-li:text-cyber-text-muted prose-li:marker:text-brand-primary
                                          prose-p:text-cyber-text-muted">
                                <ReactMarkdown>{analysis}</ReactMarkdown>
                            </div>

                            {/* Regenerate or analyze another */}
                            <div className="mt-6 pt-4 border-t border-cyber-border/50 flex gap-3 justify-center">
                                <button
                                    onClick={() => generateAnalysis(selectedPlayer)}
                                    className="px-4 py-2 rounded-lg bg-cyber-surface-light hover:bg-cyber-surface-light/70 
                                             text-cyber-text-muted hover:text-cyber-text transition-colors text-sm"
                                >
                                    Regenerate
                                </button>
                                {trackedPlayers.length > 1 && (
                                    <button
                                        onClick={() => {
                                            setAnalysis(null);
                                            setSelectedPlayer(null);
                                            setShowDropdown(true);
                                        }}
                                        className="px-4 py-2 rounded-lg bg-brand-primary/10 hover:bg-brand-primary/20 
                                                 text-brand-primary transition-colors text-sm flex items-center gap-1"
                                    >
                                        <ChevronDown className="w-4 h-4" />
                                        Analyze Another Player
                                    </button>
                                )}
                            </div>
                        </motion.div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
