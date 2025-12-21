#!/usr/bin/env python3
"""
Phase 13: Stratz Ground Truth Data Fetcher

Fetches IMP scores and player stats from Stratz GraphQL API
to reverse-engineer their formula via regression analysis.

Usage:
    STRATZ_API_TOKEN=your_token python scripts/fetch_stratz_truth.py
"""

import os
import csv
import time
from typing import Any

import requests

# ============================================
# Configuration
# ============================================

STRATZ_GRAPHQL_URL = "https://api.stratz.com/graphql"
OUTPUT_FILE = "data/stratz_dataset.csv"
NUM_MATCHES = 100

# High MMR bracket IDs (Immortal = 80, Divine = 70)
HIGH_MMR_BRACKETS = [80, 70]

# ============================================
# GraphQL Query
# ============================================

MATCHES_QUERY = """
query GetHighMMRMatches($take: Int!, $skip: Int!) {
    matches(
        request: {
            take: $take
            skip: $skip
            bracketBasicIds: [IMMORTAL, DIVINE]
            isLeague: false
            isStats: true
        }
    ) {
        id
        durationSeconds
        didRadiantWin
        bracket
        players {
            heroId
            position
            role
            isRadiant
            lane
            imp
            kills
            deaths
            assists
            goldPerMinute
            experiencePerMinute
            heroDamage
            towerDamage
            heroHealing
            networth
            level
            item0Id
            item1Id
            item2Id
            item3Id
            item4Id
            item5Id
        }
    }
}
"""

# Alternative query if the above doesn't work
LIVE_MATCHES_QUERY = """
query GetRecentMatches($take: Int!) {
    page {
        matches(
            request: {
                take: $take
                bracketBasicIds: [IMMORTAL, DIVINE]
            }
        ) {
            id
            durationSeconds
            didRadiantWin
            players {
                heroId
                position
                role
                isRadiant
                imp
                kills
                deaths
                assists
                goldPerMinute
                experiencePerMinute
                heroDamage
                towerDamage
                heroHealing
                networth
                level
            }
        }
    }
}
"""

# Fallback: Query specific match IDs if bulk query doesn't work
SINGLE_MATCH_QUERY = """
query GetMatch($matchId: Long!) {
    match(id: $matchId) {
        id
        durationSeconds
        didRadiantWin
        bracket
        players {
            heroId
            position
            role
            isRadiant
            lane
            imp
            kills
            deaths
            assists
            goldPerMinute
            experiencePerMinute
            heroDamage
            towerDamage
            heroHealing
            networth
            level
        }
    }
}
"""

# ============================================
# Helper Functions
# ============================================

def get_api_token() -> str:
    """Get API token from environment variable."""
    token = os.environ.get("STRATZ_API_TOKEN")
    if not token:
        raise ValueError(
            "STRATZ_API_TOKEN environment variable not set.\n"
            "Get your token from: https://stratz.com/api"
        )
    return token


def execute_query(query: str, variables: dict[str, Any], token: str) -> dict:
    """Execute a GraphQL query against Stratz API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "STRATZ_API"
    }
    
    response = requests.post(
        STRATZ_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        print(response.text[:500])
        raise Exception(f"Stratz API returned {response.status_code}")
    
    data = response.json()
    
    if "errors" in data:
        print(f"GraphQL Errors: {data['errors']}")
        raise Exception(f"GraphQL errors: {data['errors']}")
    
    return data


def determine_role_type(position: int | None, role: str | None) -> str:
    """
    Convert Stratz role/position to Core or Support.
    
    Stratz positions:
    - POSITION_1: Carry (Core)
    - POSITION_2: Mid (Core)
    - POSITION_3: Offlane (Core)
    - POSITION_4: Soft Support (Support)
    - POSITION_5: Hard Support (Support)
    """
    if position is not None:
        if position in [1, 2, 3]:
            return "core"
        elif position in [4, 5]:
            return "support"
    
    if role:
        role_lower = role.lower() if isinstance(role, str) else ""
        if "core" in role_lower or "carry" in role_lower or "mid" in role_lower:
            return "core"
        elif "support" in role_lower:
            return "support"
    
    return "unknown"


def extract_player_data(match: dict, player: dict) -> dict | None:
    """Extract relevant fields from a player's match data."""
    # Skip if no IMP score
    imp = player.get("imp")
    if imp is None:
        return None
    
    # Determine win/loss
    is_radiant = player.get("isRadiant", False)
    radiant_win = match.get("didRadiantWin", False)
    is_victory = (is_radiant and radiant_win) or (not is_radiant and not radiant_win)
    
    # Get role type
    position = player.get("position")
    role = player.get("role")
    role_type = determine_role_type(position, role)
    
    # Duration in minutes for per-minute calculations
    duration_seconds = match.get("durationSeconds", 1)
    duration_minutes = duration_seconds / 60.0
    
    return {
        "match_id": match.get("id"),
        "hero_id": player.get("heroId"),
        "position": position,
        "role_type": role_type,
        "is_victory": 1 if is_victory else 0,
        "duration_minutes": round(duration_minutes, 2),
        
        # Target variable
        "imp": imp,
        
        # Raw stats
        "kills": player.get("kills", 0),
        "deaths": player.get("deaths", 0),
        "assists": player.get("assists", 0),
        "gpm": player.get("goldPerMinute", 0),
        "xpm": player.get("experiencePerMinute", 0),
        "hero_damage": player.get("heroDamage", 0),
        "tower_damage": player.get("towerDamage", 0),
        "hero_healing": player.get("heroHealing", 0),
        "networth": player.get("networth", 0),
        "level": player.get("level", 1),
        
        # Computed per-minute stats
        "kills_per_min": round(player.get("kills", 0) / max(duration_minutes, 1), 3),
        "deaths_per_min": round(player.get("deaths", 0) / max(duration_minutes, 1), 3),
        "assists_per_min": round(player.get("assists", 0) / max(duration_minutes, 1), 3),
        "hero_damage_per_min": round(player.get("heroDamage", 0) / max(duration_minutes, 1), 2),
        "tower_damage_per_min": round(player.get("towerDamage", 0) / max(duration_minutes, 1), 2),
        "hero_healing_per_min": round(player.get("heroHealing", 0) / max(duration_minutes, 1), 2),
        
        # KDA ratio
        "kda": round((player.get("kills", 0) + player.get("assists", 0)) / max(player.get("deaths", 1), 1), 2),
    }


def fetch_matches_bulk(token: str, num_matches: int) -> list[dict]:
    """Fetch matches in bulk using the matches query."""
    all_players = []
    batch_size = 25
    
    for skip in range(0, num_matches, batch_size):
        take = min(batch_size, num_matches - skip)
        print(f"Fetching matches {skip + 1} to {skip + take}...")
        
        try:
            data = execute_query(
                MATCHES_QUERY,
                {"take": take, "skip": skip},
                token
            )
            
            matches = data.get("data", {}).get("matches", [])
            
            for match in matches:
                if not match:
                    continue
                    
                players = match.get("players", [])
                for player in players:
                    player_data = extract_player_data(match, player)
                    if player_data:
                        all_players.append(player_data)
            
            print(f"  Collected {len(all_players)} player records so far")
            
            # Rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching batch: {e}")
            continue
    
    return all_players


def fetch_sample_matches(token: str, match_ids: list[int]) -> list[dict]:
    """Fetch specific matches by ID as a fallback."""
    all_players = []
    
    for match_id in match_ids:
        print(f"Fetching match {match_id}...")
        
        try:
            data = execute_query(
                SINGLE_MATCH_QUERY,
                {"matchId": match_id},
                token
            )
            
            match = data.get("data", {}).get("match")
            if not match:
                continue
                
            players = match.get("players", [])
            for player in players:
                player_data = extract_player_data(match, player)
                if player_data:
                    all_players.append(player_data)
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"Error fetching match {match_id}: {e}")
            continue
    
    return all_players


def save_to_csv(players: list[dict], filepath: str) -> None:
    """Save player data to CSV file."""
    if not players:
        print("No data to save!")
        return
    
    # Get fieldnames from first record
    fieldnames = list(players[0].keys())
    
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(players)
    
    print(f"Saved {len(players)} records to {filepath}")


# ============================================
# Main Execution
# ============================================

def main():
    print("=" * 60)
    print("Phase 13: Stratz Ground Truth Data Fetcher")
    print("=" * 60)
    
    # Get API token
    try:
        token = get_api_token()
        print(f"API Token: {token[:8]}...{token[-4:]}")
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print(f"\nFetching {NUM_MATCHES} high MMR matches from Stratz...")
    print("-" * 60)
    
    # Try bulk fetch first
    players = fetch_matches_bulk(token, NUM_MATCHES)
    
    # If we didn't get enough data, try some known match IDs
    if len(players) < 100:
        print("\nBulk fetch returned limited data. Trying sample matches...")
        # Generate a range of match IDs around the working test match
        # Each match has 10 players, so 50 matches = 500 players
        base_match_id = 8612546740
        sample_match_ids = [
            base_match_id,
            base_match_id - 1,
            base_match_id - 2,
            base_match_id - 3,
            base_match_id - 4,
            base_match_id - 5,
            base_match_id - 10,
            base_match_id - 20,
            base_match_id - 50,
            base_match_id - 100,
            base_match_id - 200,
            base_match_id - 500,
            base_match_id - 1000,
            base_match_id - 2000,
            base_match_id - 5000,
            base_match_id - 10000,
            base_match_id - 20000,
            base_match_id - 50000,
            base_match_id - 100000,
            base_match_id + 1,
            base_match_id + 2,
            base_match_id + 3,
            base_match_id + 4,
            base_match_id + 5,
            base_match_id + 10,
            base_match_id + 20,
            base_match_id + 50,
            base_match_id + 100,
            base_match_id + 200,
            base_match_id + 500,
        ]
        additional = fetch_sample_matches(token, sample_match_ids)
        players.extend(additional)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total player records: {len(players)}")
    
    if players:
        cores = [p for p in players if p.get("role_type") == "core"]
        supports = [p for p in players if p.get("role_type") == "support"]
        print(f"  - Core players: {len(cores)}")
        print(f"  - Support players: {len(supports)}")
        
        wins = [p for p in players if p.get("is_victory") == 1]
        losses = [p for p in players if p.get("is_victory") == 0]
        print(f"  - Winners: {len(wins)}")
        print(f"  - Losers: {len(losses)}")
        
        if wins:
            avg_win_imp = sum(p["imp"] for p in wins) / len(wins)
            print(f"  - Avg IMP (Winners): {avg_win_imp:.2f}")
        if losses:
            avg_loss_imp = sum(p["imp"] for p in losses) / len(losses)
            print(f"  - Avg IMP (Losers): {avg_loss_imp:.2f}")
    
    # Save to CSV
    save_to_csv(players, OUTPUT_FILE)
    print(f"\nOutput saved to: {OUTPUT_FILE}")
    print("\nNext step: Run 'python scripts/solve_formula.py' to analyze the data.")


if __name__ == "__main__":
    main()
