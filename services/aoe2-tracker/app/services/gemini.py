"""
Gemini AI client for AoE2 match roast generation.
"""

import logging

import google.generativeai as genai

from app.prompts.aoe2_roast import SYSTEM_PROMPT, build_match_prompt

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for generating AoE2 match roasts via Gemini."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.roast_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                max_output_tokens=1500,
                temperature=0.9,
            ),
        )

    async def generate_roast(
        self,
        tracked_players: list[dict],
        map_name: str,
        game_mode: str,
        duration_str: str,
        duration_seconds: int,
        is_ranked: bool,
        all_teams: dict[int, list[dict]],
        tracked_on_same_team: bool,
        tracked_vs_tracked: bool,
    ) -> str:
        """Generate an AI roast for an AoE2 match."""
        try:
            user_prompt = build_match_prompt(
                tracked_players=tracked_players,
                map_name=map_name,
                game_mode=game_mode,
                duration_str=duration_str,
                duration_seconds=duration_seconds,
                is_ranked=is_ranked,
                all_teams=all_teams,
                tracked_on_same_team=tracked_on_same_team,
                tracked_vs_tracked=tracked_vs_tracked,
            )

            response = await self.roast_model.generate_content_async(user_prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini roast generation failed: {e}")
            # Fallback roast
            player_names = ", ".join(p["nickname"] for p in tracked_players)
            any_won = any(p["won"] for p in tracked_players)
            if any_won:
                return f"{player_names} ganhou um jogo de AoE2. Até um relógio parado acerta duas vezes por dia."
            else:
                return f"{player_names} perdeu um jogo de AoE2. Skill issue."
