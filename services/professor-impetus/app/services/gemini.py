"""
Gemini API Client.
Generates roast messages using Google Gemini Flash.
"""

import logging
from typing import Optional

import google.generativeai as genai

from app.services.opendota import MatchData
from app.services.imp_engine import IMPResult
from app.prompts.roast_prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini API."""
    
    # Try these models in order
    MODEL_OPTIONS = [
        "gemini-2.5-flash-preview-05-20",  # Latest 2.5 Flash
        "gemini-1.5-flash",                 # Fallback
    ]
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        genai.configure(api_key=api_key)
        
        # Try to initialize with available model
        self.model = None
        for model_name in self.MODEL_OPTIONS:
            try:
                self.model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=SYSTEM_PROMPT,
                )
                logger.info(f"Gemini client initialized with model: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Could not initialize model {model_name}: {e}")
        
        if not self.model:
            logger.error("Failed to initialize any Gemini model!")
            # Use first as default
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SYSTEM_PROMPT,
            )
    
    async def generate_roast(
        self,
        player_name: str,
        match: MatchData,
        imp_result: IMPResult,
    ) -> str:
        """
        Generate a roast message for a player's performance.
        
        Args:
            player_name: Display name of the player
            match: Match data from OpenDota
            imp_result: IMP score result from our API
        
        Returns:
            Roast message string
        """
        try:
            user_prompt = build_user_prompt(
                player_name=player_name,
                match_id=match.match_id,
                hero_name=match.hero_name,
                imp_score=imp_result.imp_score,
                grade=imp_result.grade,
                kda=match.kda_string,
                is_victory=match.is_victory,
                duration=match.duration_string,
            )
            
            logger.debug(f"Generating roast for {player_name} with prompt: {user_prompt[:100]}...")
            
            # Generate response (sync API, but fast)
            response = self.model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=200,
                    temperature=0.9,
                )
            )
            
            roast = response.text.strip()
            logger.info(f"Generated roast for {player_name}: {roast[:50]}...")
            return roast
            
        except Exception as e:
            logger.exception(f"Error generating roast for {player_name}: {e}")
            return self._fallback_roast(player_name, imp_result.imp_score)
    
    def _fallback_roast(self, player_name: str, imp_score: float) -> str:
        """Generate a simple fallback roast if Gemini fails."""
        if imp_score >= 20:
            return f"**{player_name}**, com um IMP de **{imp_score:.1f}**, até o professor está surpreso. Milagre do Natal? 🎄"
        elif imp_score >= 0:
            return f"**{player_name}**, **{imp_score:.1f}** de IMP... Nem bom nem mau, apenas medíocre. 😐"
        else:
            return f"**{player_name}**, IMP **{imp_score:.1f}**?! O professor já ligou para os teus pais. 📞"
