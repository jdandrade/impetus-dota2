"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import {
  Zap,
  TrendingUp,
  Loader2,
  Search,
  BarChart3,
  Users,
  Target,
} from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [matchId, setMatchId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    // Navigate to the match page
    router.push(`/match/${cleanId}`);
  };

  return (
    <div className="min-h-screen bg-cyber-bg">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-brand-primary/5 via-transparent to-brand-secondary/5 pointer-events-none" />

      <div className="relative max-w-4xl mx-auto px-6 py-16">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-6">
            <Zap className="w-4 h-4 text-brand-primary" />
            <span className="text-sm text-cyber-text-muted">Alpha v0.2.0</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-4">
            <span className="text-gradient">Impetus</span>
            <span className="text-cyber-text"> Protocol</span>
          </h1>

          <p className="text-xl text-cyber-text-muted max-w-2xl mx-auto">
            Next-generation Dota 2 performance analytics.
            <br />
            Powered by the OpenIMP scoring engine.
          </p>
        </motion.header>

        {/* Search Area */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="max-w-xl mx-auto mb-16"
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

          <p className="mt-3 text-sm text-cyber-text-muted text-center">
            Fetches live data from OpenDota API • Full team scoreboard with IMP scores
          </p>
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
              Z-score calculations using hero-specific benchmarks from OpenDota
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
              Role-Based Weighting
            </h3>
            <p className="text-sm text-cyber-text-muted">
              Carry, Mid, Offlane, Support each weighted by role-specific metrics
            </p>
          </div>
        </motion.div>

        {/* Sample Matches */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="text-center"
        >
          <h3 className="text-sm font-semibold text-cyber-text-muted uppercase tracking-wider mb-4">
            Try These Matches
          </h3>
          <div className="flex flex-wrap justify-center gap-3">
            {["8612546740", "8610000000", "8615000000"].map((id) => (
              <button
                key={id}
                onClick={() => {
                  setMatchId(id);
                  router.push(`/match/${id}`);
                }}
                className="px-4 py-2 rounded-lg glass hover:bg-cyber-surface-light/50
                         text-cyber-text-muted hover:text-cyber-text transition-all
                         font-mono text-sm"
              >
                #{id}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Footer */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="mt-24 text-center text-cyber-text-muted text-sm"
        >
          <p>impetus.gg • Open Source Dota 2 Analytics</p>
        </motion.footer>
      </div>
    </div>
  );
}
