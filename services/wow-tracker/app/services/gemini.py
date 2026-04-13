"""
Gemini AI client for WoW Mythic+ roast generation.
"""

import logging

import google.generativeai as genai

from app.prompts.mythicplus_roast import SYSTEM_PROMPT, build_run_prompt

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for generating M+ roasts via Gemini."""

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
        dungeon: str,
        mythic_level: int,
        is_timed: bool,
        clear_time_str: str,
        par_time_str: str,
        time_diff_pct: float,
        num_upgrades: int,
        group_roster: list[dict],
        affixes: list[str],
        total_deaths: int,
        death_details: list[dict] | None = None,
    ) -> str:
        """Generate an AI roast for a Mythic+ run."""
        try:
            user_prompt = build_run_prompt(
                tracked_players=tracked_players,
                dungeon=dungeon,
                mythic_level=mythic_level,
                is_timed=is_timed,
                clear_time_str=clear_time_str,
                par_time_str=par_time_str,
                time_diff_pct=time_diff_pct,
                num_upgrades=num_upgrades,
                group_roster=group_roster,
                affixes=affixes,
                total_deaths=total_deaths,
                death_details=death_details,
            )

            response = await self.roast_model.generate_content_async(user_prompt)
            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini roast generation failed: {e}")
            # Fallback roast
            player_names = ", ".join(p["nickname"] for p in tracked_players)
            if is_timed:
                return f"{player_names} timed uma +{mythic_level} {dungeon}. Até um relógio parado acerta duas vezes por dia."
            else:
                return f"{player_names} depleted uma +{mythic_level} {dungeon}. Skill issue."
