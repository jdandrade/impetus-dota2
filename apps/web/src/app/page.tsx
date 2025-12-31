"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  Zap,
  TrendingUp,
  Loader2,
  Search,
  BarChart3,
  Users,
  Target,
  Clock,
  Newspaper,
  ExternalLink,
  Github,
  Sparkles,
  Gamepad2,
  Crown,
} from "lucide-react";
import { useMatchHistory } from "@/hooks/useMatchHistory";
import {
  getPlayerFullProfile,
  getPlayerTodayStats,
  steam64ToSteam32,
  type PlayerProfile,
} from "@/lib/opendota";

// Default example matches (shown when no history)
const DEFAULT_MATCHES = ["8616515910", "8612546740", "8615000000"];

// Most addicted players (Steam64 IDs and display names)
const ADDICTED_PLAYERS = [
  { steam64: "76561198349926313", name: "Fear" },
  { steam64: "76561198031378148", name: "Cego" },
  { steam64: "76561198044301453", name: "Batatas" },
  { steam64: "76561197986252478", name: "Gil" },
  { steam64: "76561197994301802", name: "Mauzaum" },
  { steam64: "76561198014373442", name: "Hory" },
];

// Meta Watch news items
const NEWS_ITEMS = [
  {
    id: 1,
    category: "Patch",
    title: "Patch 7.40 is Live",
    description: "Largo, the Bard, joins the battle. Map changes and economy updates.",
    link: "https://www.dota2.com/patches/7.40",
    icon: Sparkles,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/20",
  },
  {
    id: 2,
    category: "Analysis",
    title: "BSJ: How to Win More Games",
    description: "Pro tips on improving your gameplay and climbing MMR effectively.",
    link: "https://www.youtube.com/watch?v=q7IEkD1Njlw",
    icon: BarChart3,
    color: "text-purple-400",
    bgColor: "bg-purple-500/20",
  },
  {
    id: 3,
    category: "System",
    title: "OpenIMP Update",
    description: "New Penta-Role regression model deployed for higher accuracy.",
    link: "https://github.com/jdandrade/impetus-dota2",
    icon: Github,
    color: "text-brand-primary",
    bgColor: "bg-brand-primary/20",
  },
];

interface AddictedPlayerOfDay {
  player: { steam64: string; name: string };
  profile: PlayerProfile | null;
  gamesPlayed: number;
  totalDuration: number; // seconds
}

export default function Home() {
  const router = useRouter();
  const [matchId, setMatchId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { history, addToHistory, isHydrated } = useMatchHistory();

  // Most addicted player of the day
  const [addictedOfDay, setAddictedOfDay] = useState<AddictedPlayerOfDay | null>(null);
  const [loadingAddict, setLoadingAddict] = useState(true);

  useEffect(() => {
    async function fetchMostAddictedToday() {
      setLoadingAddict(true);

      try {
        // Fetch today's stats for all players in parallel
        const results = await Promise.all(
          ADDICTED_PLAYERS.map(async (player) => {
            const accountId = steam64ToSteam32(player.steam64);
            const stats = await getPlayerTodayStats(accountId);
            return { player, ...stats };
          })
        );

        // Find the player with most games today
        const mostAddicted = results.reduce((max, curr) =>
          curr.gamesPlayed > max.gamesPlayed ? curr : max
        );

        // Only show if they played at least 1 game today
        if (mostAddicted.gamesPlayed > 0) {
          // Fetch their profile for the avatar
          const accountId = steam64ToSteam32(mostAddicted.player.steam64);
          const profile = await getPlayerFullProfile(accountId);

          setAddictedOfDay({
            player: mostAddicted.player,
            profile,
            gamesPlayed: mostAddicted.gamesPlayed,
            totalDuration: mostAddicted.totalDuration,
          });
        } else {
          setAddictedOfDay(null);
        }
      } catch (err) {
        console.error("Failed to fetch most addicted player:", err);
        setAddictedOfDay(null);
      } finally {
        setLoadingAddict(false);
      }
    }

    fetchMostAddictedToday();
  }, []);

  const handleAnalyze = async () => {
    if (!matchId.trim()) return;

    setLoading(true);
    setError(null);

    // Simple validation - match IDs are numeric
    const cleanId = matchId.trim();
    if (!/^\d+$/.test(cleanId)) {
      setError("Invalid Match ID. Please enter a numeric ID.");
      setLoading(false);
      return;
    }

    // Add to history and navigate
    addToHistory(cleanId);
    router.push(`/match/${cleanId}`);
  };

  const handleQuickMatch = (id: string) => {
    addToHistory(id);
    router.push(`/match/${id}`);
  };

  // Display matches: use history if available, otherwise show defaults
  const displayMatches = isHydrated && history.length > 0
    ? history.slice(0, 5)
    : DEFAULT_MATCHES;

  const matchesLabel = isHydrated && history.length > 0
    ? "Your Recent Matches"
    : "Try These Matches";

  return (
    <div className="min-h-screen bg-cyber-bg">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-brand-primary/5 via-transparent to-brand-secondary/5 pointer-events-none" />

      <div className="relative max-w-5xl mx-auto px-6 py-16">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-6">
            <Zap className="w-4 h-4 text-brand-primary" />
            <span className="text-sm text-cyber-text-muted">v0.6.0 Penta-Role</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-4">
            <span className="text-gradient">Impetus</span>
          </h1>

          <p className="text-xl text-cyber-text-muted max-w-2xl mx-auto">
            Next-gen Dota 2 analytics.
            <br />
            Powered by the <span className="text-brand-primary font-semibold">OpenIMP</span> scoring engine.
          </p>
        </motion.header>

        {/* Search Area */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="max-w-xl mx-auto mb-12"
        >
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-cyber-text-muted" />
              <input
                type="text"
                value={matchId}
                onChange={(e) => setMatchId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                placeholder="Enter Match ID (e.g., 8612546740)"
                className="w-full pl-12 pr-4 py-4 rounded-xl glass text-cyber-text
                         placeholder:text-cyber-text-muted focus:outline-none
                         focus:ring-2 focus:ring-brand-primary/50 transition-all"
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={loading || !matchId.trim()}
              className="px-6 py-4 rounded-xl bg-gradient-to-r from-brand-primary to-brand-secondary
                       text-white font-semibold shadow-glow hover:shadow-glow-teal
                       transition-all duration-300 hover:scale-105
                       disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100
                       flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  <TrendingUp className="w-5 h-5" />
                  Analyze
                </>
              )}
            </button>
          </div>

          {error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-3 text-sm text-red-400 text-center"
            >
              {error}
            </motion.p>
          )}
        </motion.div>

        {/* Nerd of the Day */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.32 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 mb-4">
            <Crown className="w-4 h-4 text-yellow-400" />
            <h3 className="text-sm font-semibold text-cyber-text-muted uppercase tracking-wider">
              Nerd of the Day
            </h3>
          </div>

          {loadingAddict ? (
            <div className="flex justify-center">
              <div className="glass rounded-2xl p-6 inline-flex items-center gap-3">
                <Loader2 className="w-5 h-5 animate-spin text-yellow-400" />
                <span className="text-cyber-text-muted">Finding today&apos;s addict...</span>
              </div>
            </div>
          ) : addictedOfDay ? (
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex justify-center"
            >
              <button
                onClick={() => router.push(`/player/${addictedOfDay.player.steam64}`)}
                className="glass rounded-2xl p-6 hover:bg-cyber-surface-light/50 transition-all group"
              >
                <div className="flex flex-col items-center gap-3">
                  {/* Crown */}
                  <motion.div
                    initial={{ y: -10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.2, type: "spring" }}
                  >
                    <Crown className="w-8 h-8 text-yellow-400 drop-shadow-[0_0_10px_rgba(250,204,21,0.5)]" />
                  </motion.div>

                  {/* Avatar */}
                  <div className="relative w-20 h-20 rounded-full overflow-hidden bg-cyber-surface-light border-2 border-yellow-400/50 group-hover:border-yellow-400 transition-colors">
                    {addictedOfDay.profile?.avatarfull ? (
                      <Image
                        src={addictedOfDay.profile.avatarfull}
                        alt={addictedOfDay.player.name}
                        fill
                        className="object-cover"
                        sizes="80px"
                        unoptimized
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Users className="w-10 h-10 text-cyber-text-muted" />
                      </div>
                    )}
                  </div>

                  {/* Name */}
                  <span className="text-lg font-bold text-cyber-text group-hover:text-yellow-400 transition-colors">
                    {addictedOfDay.player.name}
                  </span>

                  {/* Games count and time */}
                  <div className="flex flex-col items-center gap-2">
                    <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-400/20 border border-yellow-400/30">
                      <Gamepad2 className="w-4 h-4 text-yellow-400" />
                      <span className="text-sm font-semibold text-yellow-400">
                        {addictedOfDay.gamesPlayed} game{addictedOfDay.gamesPlayed !== 1 ? "s" : ""} today
                      </span>
                    </div>
                    {addictedOfDay.totalDuration > 0 && (
                      <span className="text-xs text-cyber-text-muted">
                        {Math.floor(addictedOfDay.totalDuration / 3600)}h {Math.floor((addictedOfDay.totalDuration % 3600) / 60)}m played
                      </span>
                    )}
                  </div>
                </div>
              </button>
            </motion.div>
          ) : (
            <div className="flex justify-center">
              <div className="glass rounded-2xl p-6 inline-flex items-center gap-3">
                <Gamepad2 className="w-5 h-5 text-cyber-text-muted" />
                <span className="text-cyber-text-muted">No games played today yet</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Recent Matches */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-cyber-text-muted" />
            <h3 className="text-sm font-semibold text-cyber-text-muted uppercase tracking-wider">
              {matchesLabel}
            </h3>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {displayMatches.map((id) => (
              <button
                key={id}
                onClick={() => handleQuickMatch(id)}
                className="px-4 py-2 rounded-lg glass hover:bg-cyber-surface-light/50
                         text-cyber-text-muted hover:text-cyber-text transition-all
                         font-mono text-sm group"
              >
                <span className="text-brand-primary/60 group-hover:text-brand-primary">#</span>
                {id}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Most Addicted Players */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 mb-4">
            <Gamepad2 className="w-4 h-4 text-cyber-text-muted" />
            <h3 className="text-sm font-semibold text-cyber-text-muted uppercase tracking-wider">
              Most Addicted Players
            </h3>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {ADDICTED_PLAYERS.map((player) => (
              <button
                key={player.steam64}
                onClick={() => router.push(`/player/${player.steam64}`)}
                className="px-4 py-2 rounded-lg glass hover:bg-cyber-surface-light/50
                         text-cyber-text-muted hover:text-cyber-text transition-all
                         text-sm group flex items-center gap-2"
              >
                <Users className="w-4 h-4 text-brand-secondary/60 group-hover:text-brand-secondary" />
                <span className="font-medium">{player.name}</span>
              </button>
            ))}
          </div>
        </motion.div>

        {/* Features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16"
        >
          {/* Feature 1 */}
          <div className="glass rounded-2xl p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-brand-primary/20 flex items-center justify-center mx-auto mb-4">
              <BarChart3 className="w-6 h-6 text-brand-primary" />
            </div>
            <h3 className="text-lg font-semibold text-cyber-text mb-2">
              Statistical Analysis
            </h3>
            <p className="text-sm text-cyber-text-muted">
              Ridge regression trained on 6,000+ Stratz samples
            </p>
          </div>

          {/* Feature 2 */}
          <div className="glass rounded-2xl p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-brand-secondary/20 flex items-center justify-center mx-auto mb-4">
              <Users className="w-6 h-6 text-brand-secondary" />
            </div>
            <h3 className="text-lg font-semibold text-cyber-text mb-2">
              Full Team Scoreboard
            </h3>
            <p className="text-sm text-cyber-text-muted">
              Radiant vs Dire with K/D/A, GPM, XPM and IMP scores for all 10 players
            </p>
          </div>

          {/* Feature 3 */}
          <div className="glass rounded-2xl p-6 text-center">
            <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mx-auto mb-4">
              <Target className="w-6 h-6 text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-cyber-text mb-2">
              Penta-Role Weighting
            </h3>
            <p className="text-sm text-cyber-text-muted">
              Position 1-5 each weighted by role-specific regression coefficients
            </p>
          </div>
        </motion.div>

        {/* Meta Watch - News Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mb-16"
        >
          <div className="flex items-center gap-2 mb-6">
            <Newspaper className="w-5 h-5 text-cyber-text-muted" />
            <h2 className="text-lg font-semibold text-cyber-text">
              Latest from the Ancients
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {NEWS_ITEMS.map((item) => (
              <a
                key={item.id}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="glass rounded-xl p-5 group hover:bg-cyber-surface-light/50 transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className={`w-10 h-10 rounded-lg ${item.bgColor} flex items-center justify-center`}>
                    <item.icon className={`w-5 h-5 ${item.color}`} />
                  </div>
                  <span className="text-xs text-cyber-text-muted uppercase tracking-wider">
                    {item.category}
                  </span>
                </div>
                <h4 className="font-semibold text-cyber-text mb-2 group-hover:text-brand-primary transition-colors">
                  {item.title}
                </h4>
                <p className="text-sm text-cyber-text-muted mb-3">
                  {item.description}
                </p>
                <div className="flex items-center gap-1 text-xs text-brand-primary opacity-0 group-hover:opacity-100 transition-opacity">
                  Read more <ExternalLink className="w-3 h-3" />
                </div>
              </a>
            ))}
          </div>
        </motion.div>

        {/* Footer */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="text-center text-cyber-text-muted text-sm"
        >
          <p>impetus.gg • Open Source Dota 2 Analytics</p>
        </motion.footer>
      </div>
    </div>
  );
}
