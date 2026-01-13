"""
Gemini API Client.
Generates roast messages and triages YouTube videos using Google Gemini Flash.
"""

import json
import logging
from typing import Optional

import google.generativeai as genai

from app.services.opendota import MatchData
from app.services.imp_engine import IMPResult
from app.prompts.roast_prompt import SYSTEM_PROMPT, build_user_prompt
from app.prompts.video_triage_prompt import (
    SYSTEM_PROMPT as VIDEO_TRIAGE_SYSTEM_PROMPT,
    build_video_triage_prompt,
)

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client for Google Gemini API."""
    
    # Gemini 2.5 Flash - stable release
    MODEL_NAME = "gemini-2.5-flash"
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        genai.configure(api_key=api_key)
        
        # Model for roasts
        self.roast_model = genai.GenerativeModel(
            model_name=self.MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        
        # Model for video triage
        self.triage_model = genai.GenerativeModel(
            model_name=self.MODEL_NAME,
            system_instruction=VIDEO_TRIAGE_SYSTEM_PROMPT,
        )
        
        # Keep backwards compatibility
        self.model = self.roast_model
        
        logger.info(f"Gemini client initialized with model: {self.MODEL_NAME}")
    
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
            # Generous cap - model self-limits via prompt, you only pay for tokens used
            response = self.roast_model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=1500,
                    temperature=0.9,
                )
            )
            
            roast = response.text.strip()
            logger.info(f"Generated roast for {player_name} ({len(roast)} chars): {roast}")
            return roast
            
        except Exception as e:
            logger.exception(f"Error generating roast for {player_name}: {e}")
            return self._fallback_roast(player_name, imp_result.imp_score)
    
    async def triage_videos(self, videos: list, max_retries: int = 2) -> list[str]:
        """
        Use Gemini to filter and rank videos by educational value.
        
        Args:
            videos: List of YouTubeVideo objects
            max_retries: Number of retries on failure
            
        Returns:
            List of video IDs for the top 3 educational videos
        """
        # Prepare video data for prompt
        videos_data = [
            {
                "video_id": v.video_id,
                "title": v.title,
                "description": v.description,
                "channel_name": v.channel_name,
            }
            for v in videos
        ]
        
        user_prompt = build_video_triage_prompt(videos_data)
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Triaging {len(videos)} videos (attempt {attempt + 1})...")
                
                response = self.triage_model.generate_content(
                    user_prompt,
                    generation_config=genai.GenerationConfig(
                        max_output_tokens=1500,  # Increased to avoid truncation
                        temperature=0.2,  # Lower temperature for consistent JSON
                    )
                )
                
                # Parse JSON response
                result_text = response.text.strip() if response.text else ""
                logger.debug(f"Triage raw response ({len(result_text)} chars): {result_text[:200]}")
                
                if not result_text:
                    logger.warning("Gemini returned empty response")
                    if attempt < max_retries:
                        continue
                    return []
                
                # Try to extract JSON if response has extra content
                result = self._extract_json(result_text)
                if result is None:
                    raise json.JSONDecodeError("Could not extract JSON", result_text, 0)
                
                selected = result.get("selected_videos", [])
                
                # Handle both formats: ["id1", "id2"] or [{"video_id": "id1"}, ...]
                video_ids = []
                for item in selected:
                    if isinstance(item, str):
                        video_ids.append(item)
                    elif isinstance(item, dict) and "video_id" in item:
                        video_ids.append(item["video_id"])
                
                logger.info(f"Triage selected {len(video_ids)} videos: {video_ids}")
                
                return video_ids
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    continue
                logger.exception(f"Failed to parse triage response after {max_retries + 1} attempts")
                return []
            except Exception as e:
                logger.exception(f"Error triaging videos: {e}")
                return []
        
        return []
    
    def _extract_json(self, text: str) -> dict | None:
        """Try to extract JSON from text that might have extra content."""
        import re
        
        # Strip markdown code blocks first
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # First try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _fallback_roast(self, player_name: str, imp_score: float) -> str:
        """Generate a simple fallback roast if Gemini fails."""
        if imp_score >= 20:
            return f"**{player_name}**, com um IMP de **{imp_score:.1f}**, até o professor está surpreso. Milagre do Natal? 🎄"
        elif imp_score >= 0:
            return f"**{player_name}**, **{imp_score:.1f}** de IMP... Nem bom nem mau, apenas medíocre. 😐"
        else:
            return f"**{player_name}**, IMP **{imp_score:.1f}**?! O professor já ligou para os teus pais. 📞"

