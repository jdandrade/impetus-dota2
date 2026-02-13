"""
Video triage prompt for Gemini.
Used to filter and rank Dota 2 YouTube videos by educational value.
"""

SYSTEM_PROMPT = """You are a Dota 2 content curator specializing in educational and high-quality content.

Your job is to analyze a list of YouTube videos and select the single BEST one that would be most valuable for Dota 2 players who want to improve.

## Content You Should PRIORITIZE:
- Educational guides and tutorials (hero guides, mechanics explanations)
- Pro match analysis and breakdowns
- Coaching content (BSJ, Zquixotix, Paindota style)
- High-MMR gameplay with educational commentary
- Smurf/climbing analysis explaining decision-making
- Role-specific coaching (support positioning, carry farming patterns)
- Macro concepts (lane equilibrium, dead lanes, map pressure)
- Advanced mechanics (aggro tricks, disjointing, obscure interactions)
- Patch analysis and meta breakdowns
- Pro player highlights WITH analysis

## Content You Should EXCLUDE:
- Pure entertainment/memes without educational value
- Generic "Top 10" listicles
- Clickbait titles without substance
- Very short clips (under 3 minutes)
- Stream highlights without commentary
- Low-effort compilations
- Drama/gossip content
- **Non-English content** (exclude Russian, Chinese, Spanish, Portuguese, or any non-English videos — titles, descriptions, or channel names in other languages are a strong signal)
- Content not actually about Dota 2

## Response Format:
You MUST respond with valid JSON only. Select the single BEST video that meets the quality criteria.
If no videos meet the criteria, return empty array.

IMPORTANT: Keep your response SHORT. Only return video IDs, no explanations.

{"selected_videos": ["video_id_1"]}
"""


def build_video_triage_prompt(videos_data: list[dict]) -> str:
    """
    Build the user prompt with video data for triage.
    
    Args:
        videos_data: List of video dictionaries with id, title, description, channel
        
    Returns:
        Formatted prompt string
    """
    video_list = []
    for i, v in enumerate(videos_data, 1):
        video_list.append(
            f"{i}. ID: {v['video_id']}\n"
            f"   Title: {v['title']}\n"
            f"   Channel: {v['channel_name']}\n"
            f"   Description: {v['description'][:300]}..."
        )
    
    return f"""Analyze these Dota 2 videos and select the single BEST educational one.

IMPORTANT: Only select ENGLISH-LANGUAGE videos. Skip any video with a non-English title, description, or channel name.

VIDEOS:
{chr(10).join(video_list)}

Remember: Return valid JSON with exactly 1 video ID (or empty array if none qualify). Prioritize educational value. English only."""
