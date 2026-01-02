/**
 * Dota 2 Data Providers
 * 
 * This module provides an abstraction layer for fetching Dota 2 data.
 * The default export (`dataProvider`) uses OpenDota with Stratz fallback.
 * 
 * Usage:
 *   import { dataProvider } from "@/lib/providers";
 *   const match = await dataProvider.getMatch(12345);
 */

export { dataProvider, FallbackDataProvider } from "./fallback";
export { openDotaProvider, OpenDotaProvider } from "./opendota";
export { stratzProvider, StratzProvider } from "./stratz";
export * from "./types";
