/**
 * Gemini API client for AI-powered match analysis.
 * Uses the free tier of Gemini Flash for cost-effective analysis.
 */

const GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent";

interface MatchAnalysisInput {
    playerName: string;
    heroName: string;
    role: string;
    isRadiant: boolean;
    won: boolean;
    duration: number;  // seconds
    kills: number;
    deaths: number;
    assists: number;
    gpm: number;
    xpm: number;
    netWorth: number;
    heroDamage: number;
    towerDamage: number;
    items: string[];  // Item names
    neutralItem?: string;
    impScore?: number;
    impGrade?: string;
    // Enemy team context
    enemyHeroes: string[];
    // Teammate context
    teammateHeroes: string[];
}

/**
 * Generate coaching analysis for a player's match performance.
 */
export async function generateCoachingAnalysis(
    input: MatchAnalysisInput,
    apiKey: string
): Promise<string> {
    const kda = input.deaths === 0
        ? (input.kills + input.assists > 0 ? "Perfect (0 deaths)" : "0.0")
        : ((input.kills + input.assists) / input.deaths).toFixed(1);

    const durationMin = Math.floor(input.duration / 60);
    const itemList = input.items.filter(i => i && i !== "Empty").join(", ");

    const prompt = `You are an expert Dota 2 coach analyzing a match for a player named "${input.playerName}".

## Match Summary
- **Hero**: ${input.heroName} (${input.role})
- **Result**: ${input.won ? "Victory" : "Defeat"} (${input.isRadiant ? "Radiant" : "Dire"})
- **Duration**: ${durationMin} minutes
- **KDA**: ${input.kills}/${input.deaths}/${input.assists} (${kda} KDA)
- **GPM**: ${input.gpm} | **XPM**: ${input.xpm}
- **Net Worth**: ${input.netWorth.toLocaleString()}
- **Hero Damage**: ${input.heroDamage.toLocaleString()}
- **Tower Damage**: ${input.towerDamage.toLocaleString()}
- **Main Items (purchased)**: ${itemList}
${input.neutralItem ? `- **Neutral Item (random drop)**: ${input.neutralItem}` : ""}
${input.impScore !== undefined ? `- **IMP Score**: ${input.impScore.toFixed(1)} (Grade: ${input.impGrade})` : ""}

## Team Context
- **Teammates**: ${input.teammateHeroes.join(", ")}
- **Enemies**: ${input.enemyHeroes.join(", ")}

## Task
Write a personalized "How Can I Do Better?" analysis for ${input.playerName}. Be direct, specific, and actionable. Focus on:

1. **Biggest Issue** - The #1 thing that hurt their performance (be specific)
2. **Item Choices** - Were their MAIN ITEMS optimal against this enemy lineup? Suggest alternatives. (Note: Neutral items are random drops, don't suggest replacing them with purchasable items)
3. **Game Sense** - Based on their stats, what playstyle mistakes might they have made?
4. **Quick Win** - One specific, easy thing they can do next game to immediately improve

Keep the tone friendly but honest. Use Dota terminology. Keep it under 250 words. Format with bold headers and bullet points.`;

    const response = await fetch(`${GEMINI_API_URL}?key=${apiKey}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            contents: [{
                parts: [{ text: prompt }]
            }],
            generationConfig: {
                temperature: 0.7,
                maxOutputTokens: 2048,
            }
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        console.error("Gemini API error:", error);
        throw new Error(`Gemini API error: ${response.status}`);
    }

    const data = await response.json();

    // Extract the generated text
    const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!generatedText) {
        throw new Error("No analysis generated");
    }

    return generatedText;
}
