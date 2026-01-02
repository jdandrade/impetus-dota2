"""
Stratz API Provider for Professor Impetus bot.

GraphQL-based API with higher rate limits than OpenDota.
Limits: 10,000/day, 250/min, 20/sec
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

import aiohttp

logger = logging.getLogger(__name__)

STRATZ_API_URL = "https://api.stratz.com/graphql"


@dataclass
class StratzMatchData:
    """Match data from Stratz API (matches our MatchData structure)."""
    match_id: int
    hero_id: int
    hero_name: str
    kills: int
    deaths: int
    assists: int
    gpm: int
    xpm: int
    net_worth: int
    level: int
    hero_damage: int
    tower_damage: int
    hero_healing: int
    last_hits: int
    denies: int
    duration_seconds: int
    is_radiant: bool
    radiant_win: bool
    player_slot: int
    player_name: str
    lane: Optional[int] = None
    all_players: Optional[list] = None


# Hero ID to name mapping (same as opendota.py)
HERO_NAMES = {
    1: "Anti-Mage", 2: "Axe", 3: "Bane", 4: "Bloodseeker", 5: "Crystal Maiden",
    6: "Drow Ranger", 7: "Earthshaker", 8: "Juggernaut", 9: "Mirana", 10: "Morphling",
    11: "Shadow Fiend", 12: "Phantom Lancer", 13: "Puck", 14: "Pudge", 15: "Razor",
    16: "Sand King", 17: "Storm Spirit", 18: "Sven", 19: "Tiny", 20: "Vengeful Spirit",
    21: "Windranger", 22: "Zeus", 23: "Kunkka", 25: "Lina", 26: "Lion",
    27: "Shadow Shaman", 28: "Slardar", 29: "Tidehunter", 30: "Witch Doctor",
    31: "Lich", 32: "Riki", 33: "Enigma", 34: "Tinker", 35: "Sniper",
    36: "Necrophos", 37: "Warlock", 38: "Beastmaster", 39: "Queen of Pain", 40: "Venomancer",
    41: "Faceless Void", 42: "Wraith King", 43: "Death Prophet", 44: "Phantom Assassin",
    45: "Pugna", 46: "Templar Assassin", 47: "Viper", 48: "Luna", 49: "Dragon Knight",
    50: "Dazzle", 51: "Clockwerk", 52: "Leshrac", 53: "Nature's Prophet", 54: "Lifestealer",
    55: "Dark Seer", 56: "Clinkz", 57: "Omniknight", 58: "Enchantress", 59: "Huskar",
    60: "Night Stalker", 61: "Broodmother", 62: "Bounty Hunter", 63: "Weaver", 64: "Jakiro",
    65: "Batrider", 66: "Chen", 67: "Spectre", 68: "Ancient Apparition", 69: "Doom",
    70: "Ursa", 71: "Spirit Breaker", 72: "Gyrocopter", 73: "Alchemist", 74: "Invoker",
    75: "Silencer", 76: "Outworld Destroyer", 77: "Lycan", 78: "Brewmaster", 79: "Shadow Demon",
    80: "Lone Druid", 81: "Chaos Knight", 82: "Meepo", 83: "Treant Protector", 84: "Ogre Magi",
    85: "Undying", 86: "Rubick", 87: "Disruptor", 88: "Nyx Assassin", 89: "Naga Siren",
    90: "Keeper of the Light", 91: "Io", 92: "Visage", 93: "Slark", 94: "Medusa",
    95: "Troll Warlord", 96: "Centaur Warrunner", 97: "Magnus", 98: "Timbersaw",
    99: "Bristleback", 100: "Tusk", 101: "Skywrath Mage", 102: "Abaddon", 103: "Elder Titan",
    104: "Legion Commander", 105: "Techies", 106: "Ember Spirit", 107: "Earth Spirit",
    108: "Underlord", 109: "Terrorblade", 110: "Phoenix", 111: "Oracle", 112: "Winter Wyvern",
    113: "Arc Warden", 114: "Monkey King", 119: "Dark Willow", 120: "Pangolier",
    121: "Grimstroke", 123: "Hoodwink", 126: "Void Spirit", 128: "Snapfire",
    129: "Mars", 131: "Ringmaster", 135: "Dawnbreaker", 136: "Marci", 137: "Primal Beast",
    138: "Muerta", 145: "Kez", 155: "Largo",
}


class StratzProvider:
    """Stratz API client for fetching match data."""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.name = "stratz"
    
    async def _query(self, query: str, variables: dict = None) -> Optional[dict]:
        """Execute a GraphQL query against Stratz API."""
        if not self.api_token:
            logger.warning("[Stratz] No API token configured")
            return None
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "User-Agent": "STRATZ_API",
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    STRATZ_API_URL,
                    json={"query": query, "variables": variables or {}},
                    headers=headers,
                ) as resp:
                    if resp.status == 429:
                        logger.warning("[Stratz] Rate limited!")
                        return None
                    if resp.status != 200:
                        logger.error(f"[Stratz] API error: {resp.status}")
                        return None
                    
                    data = await resp.json()
                    if "errors" in data:
                        logger.error(f"[Stratz] GraphQL error: {data['errors']}")
                        return None
                    
                    return data.get("data")
            except Exception as e:
                logger.exception(f"[Stratz] Request failed: {e}")
                return None
    
    async def get_latest_match(
        self, 
        account_id: int, 
        fallback_name: str = "Unknown"
    ) -> Optional[StratzMatchData]:
        """
        Fetch the latest match for a player from Stratz.
        
        Args:
            account_id: Dota 2 account ID
            fallback_name: Name to use if API fails
        
        Returns:
            StratzMatchData if found, None otherwise
        """
        query = """
        query GetPlayerLatestMatch($steamAccountId: Long!) {
            player(steamAccountId: $steamAccountId) {
                steamAccount {
                    name
                }
                matches(request: { take: 1 }) {
                    id
                    didRadiantWin
                    durationSeconds
                    players(steamAccountId: $steamAccountId) {
                        heroId
                        kills
                        deaths
                        assists
                        goldPerMinute
                        experiencePerMinute
                        networth
                        level
                        heroDamage
                        towerDamage
                        heroHealing
                        numLastHits
                        numDenies
                        isRadiant
                        lane
                        position
                    }
                }
            }
        }
        """
        
        result = await self._query(query, {"steamAccountId": account_id})
        if not result or not result.get("player"):
            return None
        
        player = result["player"]
        matches = player.get("matches", [])
        if not matches:
            logger.warning(f"[Stratz] No matches found for account {account_id}")
            return None
        
        match = matches[0]
        player_data = match.get("players", [{}])[0]
        
        if not player_data:
            logger.error(f"[Stratz] Player data not found in match {match.get('id')}")
            return None
        
        hero_id = player_data.get("heroId", 0)
        is_radiant = player_data.get("isRadiant", True)
        
        # Calculate player_slot from position and team
        # Note: Stratz position can be a string enum, convert to int
        position_raw = player_data.get("position", 0)
        position = int(position_raw) if position_raw is not None else 0
        player_slot = position if is_radiant else 128 + position
        
        player_name = player.get("steamAccount", {}).get("name", fallback_name)
        
        return StratzMatchData(
            match_id=match.get("id", 0),
            hero_id=hero_id,
            hero_name=HERO_NAMES.get(hero_id, f"Hero #{hero_id}"),
            kills=player_data.get("kills", 0),
            deaths=player_data.get("deaths", 0),
            assists=player_data.get("assists", 0),
            gpm=player_data.get("goldPerMinute", 0),
            xpm=player_data.get("experiencePerMinute", 0),
            net_worth=player_data.get("networth", 0),
            level=player_data.get("level", 1),
            hero_damage=player_data.get("heroDamage", 0),
            tower_damage=player_data.get("towerDamage", 0),
            hero_healing=player_data.get("heroHealing", 0),
            last_hits=player_data.get("numLastHits", 0),
            denies=player_data.get("numDenies", 0),
            duration_seconds=match.get("durationSeconds", 0),
            is_radiant=is_radiant,
            radiant_win=match.get("didRadiantWin", False),
            player_slot=player_slot,
            player_name=player_name,
            lane=player_data.get("lane"),
            all_players=None,  # Not fetching all players for now
        )


# Singleton instance (initialized with token at runtime)
_stratz_provider: Optional[StratzProvider] = None


def get_stratz_provider(api_token: str) -> StratzProvider:
    """Get or create the Stratz provider instance."""
    global _stratz_provider
    if _stratz_provider is None:
        _stratz_provider = StratzProvider(api_token)
    return _stratz_provider
