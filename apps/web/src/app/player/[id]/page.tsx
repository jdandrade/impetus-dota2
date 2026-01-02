"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import {
    ArrowLeft,
    Clock,
    Trophy,
    Skull,
    Loader2,
    ExternalLink,
    User,
    TrendingUp,
} from "lucide-react";
import {
    getPlayerFullProfile,
    getPlayerRecentMatches,
    getPlayerWinLoss,
    getPlayerPeers,
    getHeroImageUrl,
    getHeroName,
    getRankImageUrl,
    getRankName,
    getRoleLabel,
    getEnrichedMatchData,
    getMultiKillName,
    steam64ToSteam32,
    type PlayerProfile,
    type PlayerRecentMatch,
    type PlayerWinLoss,
    type EnrichedMatch,
    type PeerData,
} from "@/lib/opendota";
import { getItemImageUrl } from "@/lib/items";
import { getCachedMatchesForPlayer, cacheEnrichedMatch } from "@/lib/match-cache";

function formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatTimeAgo(timestamp: number): string {
    const now = Date.now() / 1000;
    const diff = now - timestamp;

    if (diff < 3600) {
        const mins = Math.floor(diff / 60);
        return `${mins}m ago`;
    } else if (diff < 86400) {
        const hours = Math.floor(diff / 3600);
        return `${hours}h ago`;
    } else {
        const days = Math.floor(diff / 86400);
        return `${days}d ago`;
    }
}

function isPlayerWin(match: PlayerRecentMatch): boolean {
    const isRadiant = match.player_slot < 128;
    return isRadiant === match.radiant_win;
}

export default function PlayerPage() {
    const params = useParams();
    const router = useRouter();
    const rawId = params.id as string;

    // Convert Steam64 to Steam32 if needed
    const accountId = rawId.length > 10 ? steam64ToSteam32(rawId) : rawId;

    const [profile, setProfile] = useState<PlayerProfile | null>(null);
    const [matches, setMatches] = useState<PlayerRecentMatch[]>([]);
    const [winLoss, setWinLoss] = useState<PlayerWinLoss>({ win: 0, lose: 0 });
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Enriched match data (fetched separately)
    const [enrichedData, setEnrichedData] = useState<Record<number, Partial<EnrichedMatch>>>({});
    const fetchedMatchesRef = useRef<Set<number>>(new Set());

    // Teammate data (best and troll)
    const [bestTeammate, setBestTeammate] = useState<PeerData | null>(null);
    const [trollTeammate, setTrollTeammate] = useState<PeerData | null>(null);

    const MATCHES_PER_PAGE = 20;

    useEffect(() => {
        async function loadPlayerData() {
            setLoading(true);
            setError(null);

            try {
                const [profileData, matchesData, winLossData, peersData] = await Promise.all([
                    getPlayerFullProfile(accountId),
                    getPlayerRecentMatches(accountId, MATCHES_PER_PAGE),
                    getPlayerWinLoss(accountId),
                    getPlayerPeers(accountId, 100),
                ]);

                if (!profileData) {
                    setError("Player not found or profile is private");
                    setLoading(false);
                    return;
                }

                setProfile(profileData);
                setMatches(matchesData);
                setWinLoss(winLossData);
                setHasMore(matchesData.length === MATCHES_PER_PAGE);

                // Calculate best and troll teammates (minimum 5 games)
                const MIN_GAMES = 5;
                const eligiblePeers = peersData.filter(p => p.games >= MIN_GAMES);

                if (eligiblePeers.length > 0) {
                    // Best teammate has highest win rate
                    const best = eligiblePeers.reduce((a, b) =>
                        (a.win / a.games) > (b.win / b.games) ? a : b
                    );
                    setBestTeammate(best);

                    // Troll teammate has lowest win rate
                    const troll = eligiblePeers.reduce((a, b) =>
                        (a.win / a.games) < (b.win / b.games) ? a : b
                    );
                    // Only set troll if different from best
                    if (troll.account_id !== best.account_id) {
                        setTrollTeammate(troll);
                    }
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load player data");
            } finally {
                setLoading(false);
            }
        }

        if (accountId) {
            // Reset fetched matches ref when account changes
            fetchedMatchesRef.current = new Set();
            loadPlayerData();
        }
    }, [accountId]);

    // Fetch enriched data for matches (with localStorage caching)
    useEffect(() => {
        async function fetchEnrichedData() {
            if (matches.length === 0) return;

            // First, load any cached data for this player
            const cachedData = getCachedMatchesForPlayer(accountId);

            // Mark cached matches as "fetched" so we don't re-fetch them
            Object.keys(cachedData).forEach(id => fetchedMatchesRef.current.add(Number(id)));

            // Merge cached data into state (only if we have new cached data)
            if (Object.keys(cachedData).length > 0) {
                setEnrichedData(prev => {
                    const merged = { ...cachedData, ...prev };
                    // Only update if there's actually new data
                    if (Object.keys(merged).length !== Object.keys(prev).length) {
                        return merged;
                    }
                    return prev;
                });
            }

            // Find matches that haven't been fetched yet (using ref, not state)
            // Only auto-fetch the first 10 matches to reduce API calls
            const AUTO_FETCH_LIMIT = 10;
            const matchesToFetch = matches
                .slice(0, AUTO_FETCH_LIMIT)
                .filter(m => !fetchedMatchesRef.current.has(m.match_id));
            if (matchesToFetch.length === 0) return;

            // Mark these as being fetched (prevent duplicate fetches)
            matchesToFetch.forEach(m => fetchedMatchesRef.current.add(m.match_id));

            // Fetch in parallel (limit to avoid rate limits)
            const batchSize = 5;
            for (let i = 0; i < matchesToFetch.length; i += batchSize) {
                const batch = matchesToFetch.slice(i, i + batchSize);
                const results = await Promise.all(
                    batch.map(m => getEnrichedMatchData(m.match_id, accountId))
                );

                // Update state and cache with results
                const newData: Record<number, Partial<EnrichedMatch>> = {};
                batch.forEach((match, idx) => {
                    if (results[idx]) {
                        newData[match.match_id] = results[idx]!;
                        // Cache the result
                        cacheEnrichedMatch(match.match_id, accountId, results[idx]!);
                    }
                });

                if (Object.keys(newData).length > 0) {
                    setEnrichedData(prev => ({ ...prev, ...newData }));
                }

                // Small delay between batches to be nice to the API
                if (i + batchSize < matchesToFetch.length) {
                    await new Promise(resolve => setTimeout(resolve, 200));
                }
            }
        }

        fetchEnrichedData();
    }, [matches, accountId]); // Removed enrichedData from deps!

    // Load more matches when scrolling
    const loadMoreMatches = useCallback(async () => {
        if (loadingMore || !hasMore) return;

        setLoadingMore(true);
        try {
            // Use offset parameter - fetch matches older than the last one we have
            const lastMatch = matches[matches.length - 1];
            const newMatches = await getPlayerRecentMatches(accountId, MATCHES_PER_PAGE, lastMatch?.match_id);

            if (newMatches.length === 0) {
                setHasMore(false);
            } else {
                setMatches(prev => [...prev, ...newMatches]);
                setHasMore(newMatches.length === MATCHES_PER_PAGE);
            }
        } catch (err) {
            console.error("Failed to load more matches:", err);
        } finally {
            setLoadingMore(false);
        }
    }, [accountId, matches, loadingMore, hasMore]);

    // Handle scroll event for infinite loading
    const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
        const target = e.target as HTMLDivElement;
        const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

        // Load more when within 100px of bottom
        if (scrollBottom < 100 && hasMore && !loadingMore) {
            loadMoreMatches();
        }
    }, [loadMoreMatches, hasMore, loadingMore]);

    // Manually fetch enriched data for a single match (for older matches)
    const [loadingMatchId, setLoadingMatchId] = useState<number | null>(null);

    const fetchSingleMatchEnriched = useCallback(async (matchId: number) => {
        if (fetchedMatchesRef.current.has(matchId)) return;

        setLoadingMatchId(matchId);
        try {
            const data = await getEnrichedMatchData(matchId, accountId);
            if (data) {
                fetchedMatchesRef.current.add(matchId);
                cacheEnrichedMatch(matchId, accountId, data);
                setEnrichedData(prev => ({ ...prev, [matchId]: data }));
            }
        } catch (err) {
            console.error(`Failed to fetch enriched data for match ${matchId}:`, err);
        } finally {
            setLoadingMatchId(null);
        }
    }, [accountId]);

    // Calculate overall win/loss stats
    const totalGames = winLoss.win + winLoss.lose;
    const winRate = totalGames > 0 ? ((winLoss.win / totalGames) * 100).toFixed(1) : "0";

    // Calculate recent matches win rate
    const recentWins = matches.filter(isPlayerWin).length;
    const recentWinRate = matches.length > 0 ? ((recentWins / matches.length) * 100).toFixed(1) : "0";

    return (
        <div className="min-h-screen bg-cyber-bg">
            {/* Background gradient */}
            <div className="fixed inset-0 bg-gradient-to-br from-brand-primary/5 via-transparent to-brand-secondary/5 pointer-events-none" />

            <div className="relative max-w-4xl mx-auto px-6 py-8">
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
                        Back to Home
                    </button>
                </motion.header>

                {/* Loading State */}
                {loading && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="glass rounded-2xl p-12 text-center"
                    >
                        <Loader2 className="w-12 h-12 animate-spin text-brand-primary mx-auto mb-6" />
                        <h2 className="text-xl font-semibold text-cyber-text">
                            Loading Player Profile...
                        </h2>
                    </motion.div>
                )}

                {/* Error State */}
                {error && !loading && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass rounded-2xl p-8 border-red-500/30 bg-red-500/10"
                    >
                        <h2 className="text-xl font-semibold text-red-400 mb-2">Failed to Load Player</h2>
                        <p className="text-cyber-text-muted">{error}</p>
                    </motion.div>
                )}

                {/* Player Profile */}
                {!loading && !error && profile && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-6"
                    >
                        {/* Profile Card */}
                        <div className="glass rounded-2xl p-6">
                            <div className="flex items-center gap-6">
                                {/* Avatar */}
                                <div className="relative w-24 h-24 rounded-xl overflow-hidden bg-cyber-surface-light flex-shrink-0">
                                    {profile.avatarfull ? (
                                        <Image
                                            src={profile.avatarfull}
                                            alt={profile.personaname}
                                            fill
                                            className="object-cover"
                                            sizes="96px"
                                            unoptimized
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center">
                                            <User className="w-12 h-12 text-cyber-text-muted" />
                                        </div>
                                    )}
                                </div>

                                {/* Player Info */}
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-2">
                                        {/* Rank Medal */}
                                        {profile.rank_tier && (
                                            <div
                                                className="relative w-10 h-10 flex-shrink-0"
                                                title={getRankName(profile.rank_tier)}
                                            >
                                                <Image
                                                    src={getRankImageUrl(profile.rank_tier) || ""}
                                                    alt={getRankName(profile.rank_tier)}
                                                    fill
                                                    className="object-contain"
                                                    sizes="40px"
                                                    unoptimized
                                                />
                                            </div>
                                        )}
                                        <h1 className="text-3xl font-bold text-cyber-text">
                                            {profile.personaname}
                                        </h1>
                                    </div>

                                    <div className="flex items-center gap-4 text-sm text-cyber-text-muted">
                                        {profile.rank_tier && (
                                            <span>{getRankName(profile.rank_tier)}</span>
                                        )}
                                        {profile.leaderboard_rank && (
                                            <span className="text-yellow-400">
                                                Leaderboard #{profile.leaderboard_rank}
                                            </span>
                                        )}
                                    </div>

                                    {/* Win/Loss Stats */}
                                    <div className="flex flex-wrap items-center gap-4 mt-4">
                                        <div className="flex items-center gap-2">
                                            <Trophy className="w-4 h-4 text-green-400" />
                                            <span className="text-green-400 font-semibold">{winLoss.win}W</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Skull className="w-4 h-4 text-red-400" />
                                            <span className="text-red-400 font-semibold">{winLoss.lose}L</span>
                                        </div>
                                        <span className="text-cyber-text-muted">
                                            ({winRate}% WR • {totalGames.toLocaleString()} games)
                                        </span>
                                        {matches.length > 0 && (
                                            <div className="flex items-center gap-2 px-2 py-1 rounded bg-cyber-surface-light/50">
                                                <TrendingUp className="w-4 h-4 text-brand-primary" />
                                                <span className="text-sm">
                                                    <span className={parseFloat(recentWinRate) >= 50 ? "text-green-400" : "text-red-400"}>
                                                        {recentWinRate}%
                                                    </span>
                                                    <span className="text-cyber-text-muted"> last {matches.length}</span>
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* External Links */}
                                <div className="flex flex-col gap-2">
                                    <a
                                        href={`https://www.opendota.com/players/${accountId}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg glass
                                                 text-cyber-text-muted hover:text-cyber-text hover:bg-cyber-surface-light/50
                                                 transition-all text-sm"
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                        OpenDota
                                    </a>
                                    <a
                                        href={`https://stratz.com/players/${accountId}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg glass
                                                 text-cyber-text-muted hover:text-cyber-text hover:bg-cyber-surface-light/50
                                                 transition-all text-sm"
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                        Stratz
                                    </a>
                                </div>
                            </div>
                        </div>

                        {/* Best & Troll Teammates */}
                        {(bestTeammate || trollTeammate) && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Best Teammate */}
                                {bestTeammate && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.3 }}
                                        className="glass rounded-2xl p-4"
                                    >
                                        <div className="flex items-center gap-2 mb-3">
                                            <span className="text-lg">🏆</span>
                                            <h3 className="font-semibold text-green-400">Best Teammate</h3>
                                        </div>
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-cyber-surface-light flex-shrink-0">
                                                {bestTeammate.avatarfull ? (
                                                    <Image
                                                        src={bestTeammate.avatarfull}
                                                        alt={bestTeammate.personaname}
                                                        fill
                                                        className="object-cover"
                                                        unoptimized
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex items-center justify-center">
                                                        <User className="w-6 h-6 text-cyber-text-muted" />
                                                    </div>
                                                )}
                                            </div>
                                            <div>
                                                <div className="font-medium text-cyber-text truncate max-w-[150px]">
                                                    {bestTeammate.personaname || "Unknown"}
                                                </div>
                                                <div className="text-sm">
                                                    <span className="text-green-400 font-semibold">
                                                        {((bestTeammate.win / bestTeammate.games) * 100).toFixed(1)}% WR
                                                    </span>
                                                    <span className="text-cyber-text-muted"> • {bestTeammate.games} games</span>
                                                </div>
                                            </div>
                                        </div>
                                        <p className="text-xs text-cyber-text-muted italic">
                                            &quot;Make love with this guy - you and him will reach top rank together ❤️&quot;
                                        </p>
                                    </motion.div>
                                )}

                                {/* Troll Teammate */}
                                {trollTeammate && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: 0.4 }}
                                        className="glass rounded-2xl p-4"
                                    >
                                        <div className="flex items-center gap-2 mb-3">
                                            <span className="text-lg">🎭</span>
                                            <h3 className="font-semibold text-red-400">Troll Teammate</h3>
                                        </div>
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-cyber-surface-light flex-shrink-0">
                                                {trollTeammate.avatarfull ? (
                                                    <Image
                                                        src={trollTeammate.avatarfull}
                                                        alt={trollTeammate.personaname}
                                                        fill
                                                        className="object-cover"
                                                        unoptimized
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex items-center justify-center">
                                                        <User className="w-6 h-6 text-cyber-text-muted" />
                                                    </div>
                                                )}
                                            </div>
                                            <div>
                                                <div className="font-medium text-cyber-text truncate max-w-[150px]">
                                                    {trollTeammate.personaname || "Unknown"}
                                                </div>
                                                <div className="text-sm">
                                                    <span className="text-red-400 font-semibold">
                                                        {((trollTeammate.win / trollTeammate.games) * 100).toFixed(1)}% WR
                                                    </span>
                                                    <span className="text-cyber-text-muted"> • {trollTeammate.games} games</span>
                                                </div>
                                            </div>
                                        </div>
                                        <p className="text-xs text-cyber-text-muted italic">
                                            &quot;Avoid this player... always inting on purpose because he doesn&apos;t want you to go up in ranking&quot;
                                        </p>
                                    </motion.div>
                                )}
                            </div>
                        )}

                        {/* Match History */}
                        <div className="glass rounded-2xl overflow-hidden">
                            <div className="p-4 border-b border-cyber-border">
                                <h2 className="text-lg font-semibold text-cyber-text flex items-center gap-2">
                                    <Clock className="w-5 h-5 text-cyber-text-muted" />
                                    Recent Matches
                                    <span className="text-sm font-normal text-cyber-text-muted">
                                        (Last {matches.length})
                                    </span>
                                </h2>
                            </div>

                            {matches.length === 0 ? (
                                <div className="p-8 text-center text-cyber-text-muted">
                                    No recent matches found
                                </div>
                            ) : (
                                <div
                                    ref={scrollContainerRef}
                                    onScroll={handleScroll}
                                    className="divide-y divide-cyber-border/50 max-h-[calc(100vh-320px)] overflow-y-auto"
                                >
                                    {matches.map((match, index) => {
                                        const won = isPlayerWin(match);
                                        const enriched = enrichedData[match.match_id];
                                        return (
                                            <motion.div
                                                key={match.match_id}
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: Math.min(index, 20) * 0.03 }}
                                                onClick={() => router.push(`/match/${match.match_id}`)}
                                                className="p-3 flex items-center gap-3 hover:bg-cyber-surface-light/40
                                                          transition-colors cursor-pointer"
                                            >
                                                {/* Hero Portrait with Level */}
                                                <div className="relative w-14 h-8 rounded overflow-hidden bg-cyber-surface-light flex-shrink-0">
                                                    <Image
                                                        src={getHeroImageUrl(match.hero_id, "portrait")}
                                                        alt={getHeroName(match.hero_id)}
                                                        fill
                                                        className="object-cover object-top"
                                                        sizes="56px"
                                                        unoptimized
                                                    />
                                                    {/* Level Badge */}
                                                    {enriched?.level && (
                                                        <div className="absolute bottom-0 left-0 w-5 h-4 bg-black/80 text-[10px] font-bold text-white flex items-center justify-center">
                                                            {enriched.level}
                                                        </div>
                                                    )}
                                                </div>

                                                {/* W/L Badge - Stratz style */}
                                                <div className={`w-7 h-7 rounded flex items-center justify-center flex-shrink-0 font-bold text-sm ${won
                                                    ? "bg-green-500 text-white"
                                                    : "bg-red-500 text-white"
                                                    }`}>
                                                    {won ? "W" : "L"}
                                                </div>

                                                {/* Position Badge */}
                                                {(() => {
                                                    const roleLabel = getRoleLabel(match.lane, match.player_slot);
                                                    return roleLabel ? (
                                                        <div className="w-6 h-6 rounded bg-cyber-surface-light flex items-center justify-center flex-shrink-0 text-xs text-cyber-text-muted font-medium">
                                                            {roleLabel}
                                                        </div>
                                                    ) : null;
                                                })()}

                                                {/* Hero Name, Time & Achievement Badges */}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-medium text-cyber-text text-sm truncate">
                                                            {getHeroName(match.hero_id)}
                                                        </span>
                                                        {/* Achievement Badges */}
                                                        {enriched?.multi_kill && getMultiKillName(enriched.multi_kill) && (
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-medium">
                                                                {getMultiKillName(enriched.multi_kill)}
                                                            </span>
                                                        )}
                                                        {enriched?.first_blood && (
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium">
                                                                First Blood
                                                            </span>
                                                        )}
                                                        {enriched?.net_worth_rank === 1 && (
                                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 font-medium">
                                                                Rich
                                                            </span>
                                                        )}
                                                    </div>
                                                    <span className="text-xs text-cyber-text-muted">
                                                        {formatTimeAgo(match.start_time)} • {formatDuration(match.duration)}
                                                    </span>
                                                </div>

                                                {/* Items - or Load button for older matches */}
                                                {enriched?.items ? (
                                                    <div className="flex gap-0.5 flex-shrink-0 items-center">
                                                        {/* Main 6 items */}
                                                        {enriched.items.slice(0, 6).map((itemId, i) => (
                                                            <div key={i} className="w-6 h-5 rounded-sm bg-cyber-surface-dark overflow-hidden">
                                                                {itemId > 0 && getItemImageUrl(itemId) && (
                                                                    <Image
                                                                        src={getItemImageUrl(itemId)!}
                                                                        alt=""
                                                                        width={24}
                                                                        height={20}
                                                                        className="object-cover"
                                                                        unoptimized
                                                                    />
                                                                )}
                                                            </div>
                                                        ))}
                                                        {/* Neutral item */}
                                                        {enriched.items[6] > 0 && getItemImageUrl(enriched.items[6]) && (
                                                            <div className="w-5 h-5 rounded-full bg-cyber-surface-dark overflow-hidden ml-1 border border-amber-500/50">
                                                                <Image
                                                                    src={getItemImageUrl(enriched.items[6])!}
                                                                    alt=""
                                                                    width={20}
                                                                    height={20}
                                                                    className="object-cover"
                                                                    unoptimized
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                ) : index >= 10 ? (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            fetchSingleMatchEnriched(match.match_id);
                                                        }}
                                                        disabled={loadingMatchId === match.match_id}
                                                        className="text-xs px-2 py-1 rounded bg-cyber-surface-light hover:bg-cyber-surface-light/80 text-cyber-text-muted transition-colors flex items-center gap-1"
                                                    >
                                                        {loadingMatchId === match.match_id ? (
                                                            <>
                                                                <Loader2 className="w-3 h-3 animate-spin" />
                                                                Loading...
                                                            </>
                                                        ) : (
                                                            "Load Items"
                                                        )}
                                                    </button>
                                                ) : null}

                                                {/* KDA & K/D/A */}
                                                <div className="text-right flex-shrink-0 min-w-[70px]">
                                                    {/* KDA Value */}
                                                    {(() => {
                                                        const kda = match.deaths === 0
                                                            ? (match.kills + match.assists > 0 ? "perfect" : 0)
                                                            : ((match.kills + match.assists) / match.deaths).toFixed(1);
                                                        return (
                                                            <div className="text-xs mb-0.5">
                                                                {kda === "perfect" ? (
                                                                    <span className="text-brand-primary font-bold">PERFECT</span>
                                                                ) : (
                                                                    <span className="text-cyber-text-muted">{kda} KDA</span>
                                                                )}
                                                            </div>
                                                        );
                                                    })()}
                                                    {/* K/D/A breakdown */}
                                                    <span className="font-mono text-sm">
                                                        <span className="text-green-400">{match.kills}</span>
                                                        <span className="text-cyber-text-muted"> / </span>
                                                        <span className="text-red-400">{match.deaths}</span>
                                                        <span className="text-cyber-text-muted"> / </span>
                                                        <span style={{ color: '#fac654' }}>{match.assists}</span>
                                                    </span>
                                                </div>

                                                {/* Match ID */}
                                                <div className="text-xs text-cyber-text-muted font-mono flex-shrink-0 hidden lg:block">
                                                    #{match.match_id}
                                                </div>
                                            </motion.div>
                                        );
                                    })}

                                    {/* Loading indicator */}
                                    {loadingMore && (
                                        <div className="p-4 flex items-center justify-center">
                                            <Loader2 className="w-5 h-5 animate-spin text-brand-primary" />
                                            <span className="ml-2 text-sm text-cyber-text-muted">Loading more matches...</span>
                                        </div>
                                    )}

                                    {/* End of matches indicator */}
                                    {!hasMore && matches.length > 20 && (
                                        <div className="p-4 text-center text-sm text-cyber-text-muted">
                                            No more matches to load
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}

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
