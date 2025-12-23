"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useParams, useRouter } from "next/navigation";
import {
    ArrowLeft,
    Clock,
    Trophy,
    Loader2,
    Zap,
    ExternalLink,
    AlertTriangle,
} from "lucide-react";
import {
    getMatchDetails,
    getHeroBenchmarks,
    getHeroName,
    enrichPlayerProfiles,
    requestMatchParse,
    isMatchFullyParsed,
    detectRole,
    type OpenDotaMatch,
    type OpenDotaPlayer,
    type HeroBenchmarks,
    type Role,
} from "@/lib/opendota";
import { transformMatchToPayload } from "@/lib/transformer";
import { getMatchImp, type CalculateIMPResponse } from "@/lib/imp-client";
import Scoreboard from "@/components/match/Scoreboard";
import NetWorthGraph from "@/components/match/NetWorthGraph";
import { useMatchHistory } from "@/hooks/useMatchHistory";

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
    items: number[];  // 6 item slots
    itemNeutral: number;
    role: Role;       // Detected role based on net worth
    // Player identity
    personaname?: string;
    accountId?: number | null;
    rankTier?: number | null;
    // Item purchase timeline (parsed matches only)
    purchaseLog?: Array<{ time: number; key: string }>;
    // Skill order (parsed matches only)
    abilityUpgrades?: number[];
    // IMP result
    impResult: CalculateIMPResponse | null;
    error: string | null;
}

type LoadingState = "idle" | "fetching-match" | "fetching-benchmarks" | "calculating-scores" | "done" | "error";

export default function MatchPage() {
    const params = useParams();
    const router = useRouter();
    const matchId = params.id as string;

    const [loadingState, setLoadingState] = useState<LoadingState>("idle");
    const [matchData, setMatchData] = useState<OpenDotaMatch | null>(null);
    const [playerScores, setPlayerScores] = useState<PlayerScore[]>([]);
    const [enrichedPlayers, setEnrichedPlayers] = useState<OpenDotaPlayer[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [parseRequested, setParseRequested] = useState(false);
    const [isFullyParsed, setIsFullyParsed] = useState(true);
    const { addToHistory } = useMatchHistory();

    useEffect(() => {
        if (matchId) {
            // Add to history when viewing a match (works for direct links from Discord)
            addToHistory(matchId);
            // Request parse in background (doesn't block)
            requestMatchParse(matchId).then(result => {
                if (result) setParseRequested(true);
            });
            loadMatchData(matchId);
        }
    }, [matchId, addToHistory]);

    const loadMatchData = async (id: string) => {
        setLoadingState("fetching-match");
        setError(null);
        setProgress(10);

        try {
            // Step 1: Fetch match details from OpenDota
            const match = await getMatchDetails(id);
            setMatchData(match);
            setProgress(20);

            // Step 1b: Enrich players with missing names (fetches from /players endpoint)
            const enriched = await enrichPlayerProfiles(match.players);
            setEnrichedPlayers(enriched);
            setProgress(30);

            // Check if match is fully parsed (has player data)
            setIsFullyParsed(isMatchFullyParsed(enriched));

            // Initialize player scores with role detection
            const initialScores: PlayerScore[] = enriched.map((p, index) => ({
                playerIndex: index,
                heroId: p.hero_id,
                heroName: getHeroName(p.hero_id),
                isRadiant: p.isRadiant,
                kills: p.kills,
                deaths: p.deaths,
                assists: p.assists,
                gpm: p.gold_per_min,
                xpm: p.xp_per_min,
                netWorth: p.net_worth,
                heroDamage: p.hero_damage,
                towerDamage: p.tower_damage,
                items: [p.item_0, p.item_1, p.item_2, p.item_3, p.item_4, p.item_5],
                itemNeutral: p.item_neutral,
                role: detectRole(p, enriched),
                // Player identity (now enriched)
                personaname: p.personaname,
                accountId: p.account_id,
                rankTier: p.rank_tier,
                // Item purchase timeline
                purchaseLog: p.purchase_log,
                // Skill order
                abilityUpgrades: p.ability_upgrades_arr,
                impResult: null,
                error: null,
            }));
            setPlayerScores(initialScores);

            // Step 2: Fetch benchmarks for all heroes in parallel
            setLoadingState("fetching-benchmarks");
            const uniqueHeroIds = Array.from(new Set(match.players.map((p) => p.hero_id)));

            const benchmarkPromises = uniqueHeroIds.map(async (heroId) => {
                try {
                    const benchmarks = await getHeroBenchmarks(heroId);
                    return { heroId, benchmarks };
                } catch (e) {
                    console.warn(`Failed to fetch benchmarks for hero ${heroId}:`, e);
                    return { heroId, benchmarks: null };
                }
            });

            const benchmarkResults = await Promise.all(benchmarkPromises);
            const benchmarkMap = new Map<number, HeroBenchmarks | null>();
            benchmarkResults.forEach(({ heroId, benchmarks }) => {
                benchmarkMap.set(heroId, benchmarks);
            });
            setProgress(60);

            // Step 3: Calculate IMP scores for all players in parallel
            setLoadingState("calculating-scores");

            const scorePromises = match.players.map(async (player, index) => {
                try {
                    const benchmarks = benchmarkMap.get(player.hero_id) || undefined;
                    const payload = transformMatchToPayload(match, index, benchmarks);
                    const result = await getMatchImp(payload);
                    return { index, result, error: null };
                } catch (e) {
                    return {
                        index,
                        result: null,
                        error: e instanceof Error ? e.message : "Failed to calculate"
                    };
                }
            });

            const scoreResults = await Promise.all(scorePromises);
            setProgress(90);

            // Update player scores with IMP results
            setPlayerScores((prev) =>
                prev.map((p) => {
                    const scoreResult = scoreResults.find((r) => r.index === p.playerIndex);
                    if (scoreResult) {
                        return {
                            ...p,
                            impResult: scoreResult.result,
                            error: scoreResult.error,
                        };
                    }
                    return p;
                })
            );

            setProgress(100);
            setLoadingState("done");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load match");
            setLoadingState("error");
        }
    };

    const radiantPlayers = playerScores.filter((p) => p.isRadiant);
    const direPlayers = playerScores.filter((p) => !p.isRadiant);

    return (
        <div className="min-h-screen bg-cyber-bg">
            {/* Background gradient */}
            <div className="fixed inset-0 bg-gradient-to-br from-brand-primary/5 via-transparent to-brand-secondary/5 pointer-events-none" />

            <div className="relative max-w-7xl mx-auto px-6 py-8">
                {/* Header */}
                <motion.header
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <button
                        onClick={() => router.push("/")}
                        className="inline-flex items-center gap-2 text-cyber-text-muted hover:text-cyber-text
                     transition-colors mb-6"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Search
                    </button>

                    <div className="flex items-center justify-between">
                        <div>
                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full glass mb-3">
                                <Zap className="w-3 h-3 text-brand-primary" />
                                <span className="text-xs text-cyber-text-muted">Match Analysis</span>
                            </div>
                            <h1 className="text-3xl md:text-4xl font-bold text-cyber-text">
                                Match <span className="text-brand-primary">#{matchId}</span>
                            </h1>
                        </div>

                        {matchData && (
                            <div className="text-right">
                                <div className="flex items-center gap-2 text-cyber-text-muted mb-1">
                                    <Clock className="w-4 h-4" />
                                    <span>
                                        {Math.floor(matchData.duration / 60)}:
                                        {(matchData.duration % 60).toString().padStart(2, "0")}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2 mb-3">
                                    <Trophy className={`w-4 h-4 ${matchData.radiant_win ? "text-green-400" : "text-red-400"}`} />
                                    <span className={matchData.radiant_win ? "text-green-400" : "text-red-400"}>
                                        {matchData.radiant_win ? "Radiant Victory" : "Dire Victory"}
                                    </span>
                                </div>
                                <a
                                    href={`https://stratz.com/matches/${matchId}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg glass
                                             text-cyber-text-muted hover:text-cyber-text hover:bg-cyber-surface-light/50
                                             transition-all text-sm"
                                >
                                    <ExternalLink className="w-4 h-4" />
                                    View on Stratz
                                </a>
                            </div>
                        )}
                    </div>
                </motion.header>

                {/* Parsing Banner - shows when match data is incomplete */}
                {!isFullyParsed && loadingState === "done" && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mb-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 flex items-center gap-3"
                    >
                        <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                        <div>
                            <p className="text-yellow-400 font-medium">Match Replay Not Fully Parsed</p>
                            <p className="text-sm text-cyber-text-muted">
                                Some player names may be unavailable.
                                {parseRequested ? " Parse requested - refresh in a few minutes for updated data." : " We've requested a parse from OpenDota."}
                            </p>
                        </div>
                        <a
                            href={`https://www.opendota.com/matches/${matchId}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-auto px-3 py-1.5 rounded-lg bg-yellow-500/20 text-yellow-400 text-sm hover:bg-yellow-500/30 transition-colors flex-shrink-0"
                        >
                            View on OpenDota
                        </a>
                    </motion.div>
                )}

                {/* Loading State */}
                {loadingState !== "done" && loadingState !== "error" && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="glass rounded-2xl p-12 text-center"
                    >
                        <Loader2 className="w-12 h-12 animate-spin text-brand-primary mx-auto mb-6" />
                        <h2 className="text-xl font-semibold text-cyber-text mb-2">
                            {loadingState === "fetching-match" && "Fetching Match Data..."}
                            {loadingState === "fetching-benchmarks" && "Loading Hero Benchmarks..."}
                            {loadingState === "calculating-scores" && "Calculating IMP Scores..."}
                            {loadingState === "idle" && "Initializing..."}
                        </h2>
                        <div className="max-w-xs mx-auto mt-4">
                            <div className="h-2 bg-cyber-surface-light rounded-full overflow-hidden">
                                <motion.div
                                    className="h-full bg-gradient-to-r from-brand-primary to-brand-secondary"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${progress}%` }}
                                    transition={{ duration: 0.3 }}
                                />
                            </div>
                            <p className="text-sm text-cyber-text-muted mt-2">{progress}% complete</p>
                        </div>
                    </motion.div>
                )}

                {/* Error State */}
                {loadingState === "error" && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass rounded-2xl p-8 border-red-500/30 bg-red-500/10"
                    >
                        <h2 className="text-xl font-semibold text-red-400 mb-2">Failed to Load Match</h2>
                        <p className="text-cyber-text-muted mb-4">{error}</p>
                        <button
                            onClick={() => loadMatchData(matchId)}
                            className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                        >
                            Try Again
                        </button>
                    </motion.div>
                )}

                {/* Scoreboard */}
                {loadingState === "done" && matchData && (() => {
                    // MVP Logic: Crown goes to player with HIGHEST IMP score
                    let mvpPlayerIndex: number | undefined = undefined;
                    let highestScore = -Infinity;
                    playerScores.forEach((p) => {
                        if (p.impResult && p.impResult.data.imp_score > highestScore) {
                            highestScore = p.impResult.data.imp_score;
                            mvpPlayerIndex = p.playerIndex;
                        }
                    });

                    return (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="space-y-8"
                        >
                            {/* Radiant */}
                            <Scoreboard
                                team="radiant"
                                isWinner={matchData.radiant_win}
                                players={radiantPlayers}
                                mvpPlayerIndex={mvpPlayerIndex}
                            />

                            {/* Dire */}
                            <Scoreboard
                                team="dire"
                                isWinner={!matchData.radiant_win}
                                players={direPlayers}
                                mvpPlayerIndex={mvpPlayerIndex}
                            />

                            {/* Gold Advantage Graph */}
                            <NetWorthGraph players={enrichedPlayers} />
                        </motion.div>
                    );
                })()}

                {/* Footer */}
                <motion.footer
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="mt-16 text-center text-cyber-text-muted text-sm"
                >
                    <p>impetus.gg • Open Source Dota 2 Analytics</p>
                </motion.footer>
            </div>
        </div>
    );
}
