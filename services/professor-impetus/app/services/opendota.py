"""
OpenDota API Client.
Fetches latest match data for tracked players with FULL stats.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

OPENDOTA_API_BASE = "https://api.opendota.com/api"

@dataclass
class PlayerMinimal:
    """Minimal player data for role detection."""
    hero_id: int
    net_worth: int
    lane: Optional[int]  # 1=safelane, 2=mid, 3=offlane
    is_radiant: bool


@dataclass
class MatchData:
    """Match data from OpenDota."""
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
    lane: Optional[int] = None  # 1=safelane, 2=mid, 3=offlane
    all_players: Optional[list] = None  # List of PlayerMinimal for role detection
    
    @property
    def is_victory(self) -> bool:
        """Check if player won the match."""
        if self.is_radiant:
            return self.radiant_win
        return not self.radiant_win
    
    @property
    def kda_string(self) -> str:
        """Format K/D/A as string."""
        return f"{self.kills}/{self.deaths}/{self.assists}"
    
    @property
    def duration_string(self) -> str:
        """Format duration as MM:SS."""
        minutes = self.duration_seconds // 60
        seconds = self.duration_seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def get_role(self) -> str:
        """
        Detect player role using lane data + net worth heuristics.
        This is the unified role detection logic used across all systems.
        
        Lane values from OpenDota:
          1 = Safelane (can be Carry Pos 1 or Hard Support Pos 5)
          2 = Mid (Pos 2)
          3 = Offlane (can be Offlane Pos 3 or Soft Support Pos 4)
        
        For shared lanes (1 and 3), we use net worth to differentiate core vs support.
        """
        if self.all_players is None:
            # Fallback to old GPM-based detection if no player data
            if self.gpm >= 600:
                return "carry"
            elif self.xpm >= 600 and self.gpm >= 450:
                return "mid"
            elif self.gpm >= 400:
                return "offlane"
            elif self.assists >= 10:
                return "support"
            else:
                return "hard_support"
        
        # Get teammates
        teammates = [p for p in self.all_players if p.is_radiant == self.is_radiant]
        
        # If lane data is available, use it
        if self.lane is not None and 1 <= self.lane <= 3:
            if self.lane == 2:
                return "mid"
            
            # For safelane (1) and offlane (3), compare net worth with lane partner
            lane_partners = [p for p in teammates if p.lane == self.lane]
            
            if len(lane_partners) >= 2:
                # Sort by net worth, highest first
                sorted_by_nw = sorted(lane_partners, key=lambda p: p.net_worth, reverse=True)
                is_highest_nw = sorted_by_nw[0].hero_id == self.hero_id
                
                if self.lane == 1:
                    # Safelane: higher NW = carry, lower NW = hard support
                    return "carry" if is_highest_nw else "hard_support"
                else:
                    # Offlane: higher NW = offlane, lower NW = soft support
                    return "offlane" if is_highest_nw else "support"
        
        # Fallback: pure net worth ranking within team
        sorted_by_nw = sorted(teammates, key=lambda p: p.net_worth, reverse=True)
        rank = next((i for i, p in enumerate(sorted_by_nw) if p.hero_id == self.hero_id), 4)
        
        roles = ["carry", "mid", "offlane", "support", "hard_support"]
        return roles[min(rank, 4)]


# Hero ID to name mapping (most common heroes)
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


async def request_match_parse(match_id: int) -> bool:
    """
    Request OpenDota to parse a match replay.
    This queues the match for parsing - complete data will be available after parsing.
    
    Args:
        match_id: Match ID to request parsing for
    
    Returns:
        True if request was successful
    """
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{OPENDOTA_API_BASE}/request/{match_id}"
            async with session.post(url) as resp:
                if resp.status == 200:
                    logger.info(f"Parse requested for match {match_id}")
                    return True
                else:
                    logger.warning(f"Failed to request parse for {match_id}: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Error requesting parse for {match_id}: {e}")
            return False


async def get_latest_match(account_id: int) -> Optional[MatchData]:
    """
    Fetch the latest match for a player from OpenDota with FULL stats.
    
    Steps:
    1. Get latest match ID from /players/{id}/recentMatches
    2. Fetch full match details from /matches/{match_id}
    3. Find the player in the match and extract all stats
    
    Args:
        account_id: Dota 2 account ID (NOT Steam ID 64)
    
    Returns:
        MatchData if found, None otherwise
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Get the latest match ID
            matches_url = f"{OPENDOTA_API_BASE}/players/{account_id}/recentMatches"
            async with session.get(matches_url) as resp:
                if resp.status != 200:
                    logger.error(f"OpenDota API error: {resp.status}")
                    return None
                
                matches = await resp.json()
                if not matches:
                    logger.warning(f"No matches found for account {account_id}")
                    return None
                
                match_id = matches[0].get("match_id")
            
            # Step 2: Get player profile for name
            player_url = f"{OPENDOTA_API_BASE}/players/{account_id}"
            async with session.get(player_url) as resp:
                player_data = await resp.json() if resp.status == 200 else {}
                player_name = player_data.get("profile", {}).get("personaname", "Unknown")
            
            # Step 3: Fetch FULL match details
            match_url = f"{OPENDOTA_API_BASE}/matches/{match_id}"
            async with session.get(match_url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch match {match_id}: {resp.status}")
                    return None
                
                match_data = await resp.json()
            
            # Step 4: Find the player in the match
            player_stats = None
            for player in match_data.get("players", []):
                if player.get("account_id") == account_id:
                    player_stats = player
                    break
            
            if not player_stats:
                logger.error(f"Player {account_id} not found in match {match_id}")
                return None
            
            # Step 5: Extract all players for role detection
            all_players = []
            for p in match_data.get("players", []):
                all_players.append(PlayerMinimal(
                    hero_id=p.get("hero_id", 0),
                    net_worth=p.get("net_worth", 0),
                    lane=p.get("lane"),  # 1=safelane, 2=mid, 3=offlane
                    is_radiant=p.get("player_slot", 0) < 128,
                ))
            
            # Step 6: Build MatchData with FULL stats
            hero_id = player_stats.get("hero_id", 0)
            duration = match_data.get("duration", 0)
            
            return MatchData(
                match_id=match_id,
                hero_id=hero_id,
                hero_name=HERO_NAMES.get(hero_id, f"Hero #{hero_id}"),
                kills=player_stats.get("kills", 0),
                deaths=player_stats.get("deaths", 0),
                assists=player_stats.get("assists", 0),
                gpm=player_stats.get("gold_per_min", 0),
                xpm=player_stats.get("xp_per_min", 0),
                net_worth=player_stats.get("net_worth", 0),
                level=player_stats.get("level", 1),
                hero_damage=player_stats.get("hero_damage", 0),
                tower_damage=player_stats.get("tower_damage", 0),
                hero_healing=player_stats.get("hero_healing", 0),
                last_hits=player_stats.get("last_hits", 0),
                denies=player_stats.get("denies", 0),
                duration_seconds=duration,
                is_radiant=player_stats.get("player_slot", 0) < 128,
                radiant_win=match_data.get("radiant_win", False),
                player_slot=player_stats.get("player_slot", 0),
                player_name=player_name,
                lane=player_stats.get("lane"),  # Add lane data
                all_players=all_players,  # Add all players for role detection
            )
            
        except Exception as e:
            logger.exception(f"Error fetching match for account {account_id}: {e}")
            return None
