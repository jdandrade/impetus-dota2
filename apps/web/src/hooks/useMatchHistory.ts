"use client";

import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "impetus_match_history";
const MAX_HISTORY = 5;

/**
 * Hook for managing recent match history in localStorage.
 * Handles hydration correctly by only accessing localStorage after mount.
 */
export function useMatchHistory() {
    const [history, setHistory] = useState<string[]>([]);
    const [isHydrated, setIsHydrated] = useState(false);

    // Load history from localStorage after mount (to avoid hydration mismatch)
    useEffect(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed)) {
                    setHistory(parsed);
                }
            }
        } catch (e) {
            console.error("Failed to load match history:", e);
        }
        setIsHydrated(true);
    }, []);

    // Save history to localStorage whenever it changes
    useEffect(() => {
        if (isHydrated && history.length > 0) {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
            } catch (e) {
                console.error("Failed to save match history:", e);
            }
        }
    }, [history, isHydrated]);

    /**
     * Add a match ID to the history.
     * Moves to front if already exists, limits to MAX_HISTORY items.
     */
    const addToHistory = useCallback((matchId: string) => {
        setHistory((prev) => {
            // Remove if already exists
            const filtered = prev.filter((id) => id !== matchId);
            // Add to front
            const updated = [matchId, ...filtered];
            // Limit to max history
            return updated.slice(0, MAX_HISTORY);
        });
    }, []);

    /**
     * Clear all match history.
     */
    const clearHistory = useCallback(() => {
        setHistory([]);
        try {
            localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
            console.error("Failed to clear match history:", e);
        }
    }, []);

    return {
        history,
        addToHistory,
        clearHistory,
        isHydrated,
    };
}
