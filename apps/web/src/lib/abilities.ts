/**
 * Dota 2 Ability Utilities
 *
 * Provides functions to get ability images from Steam CDN.
 * Ability names are fetched dynamically or use fallback patterns.
 */

// Common ability ID ranges:
// - Hero abilities: typically 5000-6000 range
// - Talents: 730 and variants
// - Generic abilities: various ranges

// Special ability IDs that should be filtered or handled specially
const TALENT_IDS = new Set([
    730,   // generic_hidden (talent)
    1545,  // special_bonus variants
    1547,
    1537,
    1654,
    1700,
    1701,
]);

const GENERIC_ABILITY_IDS = new Set([
    730,   // generic_hidden
    5002,  // attribute_bonus (old)
]);

/**
 * Check if an ability ID is a talent
 */
export function isTalent(abilityId: number): boolean {
    // Talents are typically in specific ranges or have specific IDs
    // Most talents are ID 730 or in the 6000+ range for hero-specific talents
    return TALENT_IDS.has(abilityId) || (abilityId >= 6000 && abilityId < 8000);
}

/**
 * Check if ability should be shown in skill build
 */
export function isDisplayableAbility(abilityId: number): boolean {
    // Filter out generic/hidden abilities but keep talents
    return !GENERIC_ABILITY_IDS.has(abilityId) && abilityId > 0;
}

/**
 * Get ability image URL from Steam CDN using ability ID.
 * Falls back to a numbered display if ability name not found.
 */
export function getAbilityImageUrl(abilityId: number): string | null {
    if (!abilityId || abilityId <= 0) return null;

    // For talents, use a generic talent icon
    if (isTalent(abilityId)) {
        return 'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/abilities/talent_tree.png';
    }

    return null; // Will use fallback display
}

/**
 * Get a short label for the ability (Q, W, E, R, or talent indicator)
 */
export function getAbilityLabel(abilityId: number, index: number, heroAbilities: number[]): string {
    if (isTalent(abilityId)) {
        return 'T';
    }

    // Find which ability slot this is (Q, W, E, R, D, F)
    const abilityIndex = heroAbilities.indexOf(abilityId);
    const labels = ['Q', 'W', 'E', 'R', 'D', 'F'];

    if (abilityIndex >= 0 && abilityIndex < labels.length) {
        return labels[abilityIndex];
    }

    // Fallback to level number
    return String(index + 1);
}

/**
 * Get color for ability based on its type
 */
export function getAbilityColor(abilityId: number, heroAbilities: number[]): string {
    if (isTalent(abilityId)) {
        return 'bg-yellow-500/80 text-yellow-900';
    }

    const abilityIndex = heroAbilities.indexOf(abilityId);
    const colors = [
        'bg-blue-500/80 text-white',    // Q
        'bg-green-500/80 text-white',   // W
        'bg-purple-500/80 text-white',  // E
        'bg-red-500/80 text-white',     // R (Ultimate)
        'bg-cyan-500/80 text-white',    // D
        'bg-orange-500/80 text-white',  // F
    ];

    if (abilityIndex >= 0 && abilityIndex < colors.length) {
        return colors[abilityIndex];
    }

    return 'bg-gray-500/80 text-white';
}
