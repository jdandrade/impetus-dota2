/**
 * Fallback Data Provider
 * 
 * Orchestrates API calls with automatic fallback on rate limits.
 * Primary: OpenDota → Fallback: Stratz
 */

import {
    DotaDataProvider,
    MatchData,
    PlayerProfileData,
    PlayerRecentMatchData,
    PeerData,
    WinLossData,
    ProviderError,
} from "./types";
import { openDotaProvider } from "./opendota";
import { stratzProvider } from "./stratz";

/**
 * Configuration for the fallback provider.
 */
interface FallbackConfig {
    primary: DotaDataProvider;
    fallback: DotaDataProvider;
    enableFallback: boolean;
}

/**
 * Fallback provider that automatically retries with secondary provider on 429.
 */
export class FallbackDataProvider implements DotaDataProvider {
    name = "fallback";

    private config: FallbackConfig;
    private fallbackCount = 0; // Track how often we fallback (for logging)

    constructor(config?: Partial<FallbackConfig>) {
        this.config = {
            primary: openDotaProvider,
            fallback: stratzProvider,
            enableFallback: true,
            ...config,
        };
    }

    /**
     * Execute a method with fallback logic.
     */
    private async withFallback<T>(
        methodName: string,
        primaryFn: () => Promise<T>,
        fallbackFn: () => Promise<T>
    ): Promise<T> {
        try {
            return await primaryFn();
        } catch (error) {
            // Only fallback on 429 rate limit errors
            if (
                error instanceof ProviderError &&
                error.isRateLimited() &&
                this.config.enableFallback
            ) {
                this.fallbackCount++;
                console.log(
                    `[FallbackProvider] ${methodName}: Rate limited by ${error.provider}, falling back to ${this.config.fallback.name} (fallback #${this.fallbackCount})`
                );

                try {
                    return await fallbackFn();
                } catch (fallbackError) {
                    console.error(
                        `[FallbackProvider] ${methodName}: Fallback also failed`,
                        fallbackError
                    );
                    throw error; // Re-throw original error if fallback fails
                }
            }

            // Non-429 errors: just throw
            throw error;
        }
    }

    async getMatch(matchId: number): Promise<MatchData | null> {
        return this.withFallback(
            "getMatch",
            () => this.config.primary.getMatch(matchId),
            () => this.config.fallback.getMatch(matchId)
        );
    }

    async getPlayerProfile(accountId: string): Promise<PlayerProfileData | null> {
        return this.withFallback(
            "getPlayerProfile",
            () => this.config.primary.getPlayerProfile(accountId),
            () => this.config.fallback.getPlayerProfile(accountId)
        );
    }

    async getPlayerRecentMatches(accountId: string, limit: number = 20): Promise<PlayerRecentMatchData[]> {
        return this.withFallback(
            "getPlayerRecentMatches",
            () => this.config.primary.getPlayerRecentMatches(accountId, limit),
            () => this.config.fallback.getPlayerRecentMatches(accountId, limit)
        );
    }

    async getPlayerPeers(accountId: string, limit: number = 100): Promise<PeerData[]> {
        // Note: Stratz doesn't have a direct peers endpoint, so fallback may return empty
        return this.withFallback(
            "getPlayerPeers",
            () => this.config.primary.getPlayerPeers(accountId, limit),
            () => this.config.fallback.getPlayerPeers(accountId, limit)
        );
    }

    async getPlayerWinLoss(accountId: string): Promise<WinLossData> {
        return this.withFallback(
            "getPlayerWinLoss",
            () => this.config.primary.getPlayerWinLoss(accountId),
            () => this.config.fallback.getPlayerWinLoss(accountId)
        );
    }

    /**
     * Get the number of times we've fallen back to secondary provider.
     */
    getFallbackCount(): number {
        return this.fallbackCount;
    }

    /**
     * Reset the fallback counter.
     */
    resetFallbackCount(): void {
        this.fallbackCount = 0;
    }
}

// Export default instance with OpenDota as primary, Stratz as fallback
export const dataProvider = new FallbackDataProvider();

// Re-export types for convenience
export * from "./types";
