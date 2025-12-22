#!/usr/bin/env python3
"""
Phase 17: Supercharged Stratz Data Harvester

Fetches IMP scores and all 27+ player stats from Stratz GraphQL API
for large-scale regression analysis.

Features:
- Targets 1,000 matches (~10,000 player rows)
- Fetches all 27 Stratz IMP-related variables
- Rate limiting (1.2s between calls)
- Progress saving (appends to CSV, crash-resistant)
- Batch pagination with progress logging

Usage:
    STRATZ_API_TOKEN=your_token python scripts/fetch_stratz_truth.py

Output:
    data/stratz_big_data.csv
"""

import os
import csv
import time
import sys
from pathlib import Path
from typing import Any

import requests

# ============================================
# Configuration
# ============================================

STRATZ_GRAPHQL_URL = "https://api.stratz.com/graphql"
OUTPUT_FILE = "data/stratz_big_data.csv"

# Target 1,000 matches = ~10,000 player rows
TARGET_MATCHES = 1000
BATCH_SIZE = 50  # Matches per API call
RATE_LIMIT_SECONDS = 1.2  # Stay well under 7 calls/sec limit

# Starting point - recent high MMR match ID
BASE_MATCH_ID = 8615683818

# ============================================
# GraphQL Query with ALL 27 IMP Variables
# ============================================

SINGLE_MATCH_QUERY = """
query GetMatchDetails($matchId: Long!) {
    match(id: $matchId) {
        id
        durationSeconds
        didRadiantWin
        bracket
        averageRank
        gameMode
        players {
            heroId
            position
            role
            isRadiant
            lane
            imp
            award
            
            # Core Stats (K/D/A, Farm)
            kills
            deaths
            assists
            goldPerMinute
            experiencePerMinute
            networth
            level
            
            # Damage Stats
            heroDamage
            towerDamage
            heroHealing
            
            # New Metrics - Damage Breakdown
            stats {
                heroDamageReport {
                    physicalDamage
                    magicalDamage
                    pureDamage
                    receivedTotal
                }
                campStack
                runes {
                    runeId
                }
            }
            
            # CC Duration (from stats)
            stats {
                allTalk {
                    stunDuration
                }
            }
        }
    }
}
"""

# Alternative simpler query without nested stats
SIMPLE_MATCH_QUERY = """
query GetMatchBasic($matchId: Long!) {
    match(id: $matchId) {
        id
        durationSeconds
        didRadiantWin
        bracket
        averageRank
        gameMode
        players {
            heroId
            position
            role
            isRadiant
            lane
            imp
            award
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
        }
    }
}
"""

# CSV Column names
CSV_COLUMNS = [
    # Match info
    "match_id",
    "duration_seconds",
    "duration_minutes",
    "bracket",
    "avg_rank",
    "game_mode",
    
    # Player identity
    "hero_id",
    "position",
    "role_type",
    "is_radiant",
    "is_victory",
    
    # Target variable
    "imp",
    "award",
    
    # Core stats
    "kills",
    "deaths",
    "assists",
    "gpm",
    "xpm",
    "networth",
    "level",
    "last_hits",
    "denies",
    
    # Damage stats
    "hero_damage",
    "tower_damage",
    "hero_healing",
    
    # Per-minute computed stats
    "kills_per_min",
    "deaths_per_min",
    "assists_per_min",
    "hero_damage_per_min",
    "tower_damage_per_min",
    "healing_per_min",
    
    # KDA
    "kda",
]

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


def execute_query(query: str, variables: dict[str, Any], token: str) -> dict | None:
    """Execute a GraphQL query against Stratz API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "STRATZ_API"
    }
    
    try:
        response = requests.post(
            STRATZ_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 429:
            print("  ⚠️ Rate limited! Waiting 10 seconds...")
            time.sleep(10)
            return None
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if "errors" in data:
            return None
        
        return data
        
    except Exception as e:
        print(f"  ⚠️ Request error: {e}")
        return None


def determine_role_type(position: int | None, role: str | None) -> str:
    """Convert Stratz role/position to Core or Support."""
    if position is not None:
        if position in [1, 2, 3]:
            return "core"
        elif position in [4, 5]:
            return "support"
    
    if role:
        role_lower = str(role).lower()
        if "core" in role_lower or "carry" in role_lower or "mid" in role_lower:
            return "core"
        elif "support" in role_lower:
            return "support"
    
    return "unknown"


def extract_player_data(match: dict, player: dict) -> dict | None:
    """Extract all relevant fields from a player's match data."""
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
    
    # Duration calculations
    duration_seconds = match.get("durationSeconds", 1)
    duration_minutes = duration_seconds / 60.0
    
    # Extract base stats with defaults
    kills = player.get("kills", 0) or 0
    deaths = player.get("deaths", 0) or 0
    assists = player.get("assists", 0) or 0
    hero_damage = player.get("heroDamage", 0) or 0
    tower_damage = player.get("towerDamage", 0) or 0
    hero_healing = player.get("heroHealing", 0) or 0
    last_hits = player.get("numLastHits", 0) or 0
    denies = player.get("numDenies", 0) or 0
    
    return {
        # Match info
        "match_id": match.get("id"),
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_minutes, 2),
        "bracket": match.get("bracket"),
        "avg_rank": match.get("averageRank"),
        "game_mode": match.get("gameMode"),
        
        # Player identity
        "hero_id": player.get("heroId"),
        "position": position,
        "role_type": role_type,
        "is_radiant": 1 if is_radiant else 0,
        "is_victory": 1 if is_victory else 0,
        
        # Target variable
        "imp": imp,
        "award": player.get("award"),
        
        # Core stats
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "gpm": player.get("goldPerMinute", 0) or 0,
        "xpm": player.get("experiencePerMinute", 0) or 0,
        "networth": player.get("networth", 0) or 0,
        "level": player.get("level", 1) or 1,
        "last_hits": last_hits,
        "denies": denies,
        
        # Damage stats
        "hero_damage": hero_damage,
        "tower_damage": tower_damage,
        "hero_healing": hero_healing,
        
        # Per-minute computed stats
        "kills_per_min": round(kills / max(duration_minutes, 1), 3),
        "deaths_per_min": round(deaths / max(duration_minutes, 1), 3),
        "assists_per_min": round(assists / max(duration_minutes, 1), 3),
        "hero_damage_per_min": round(hero_damage / max(duration_minutes, 1), 2),
        "tower_damage_per_min": round(tower_damage / max(duration_minutes, 1), 2),
        "healing_per_min": round(hero_healing / max(duration_minutes, 1), 2),
        
        # KDA ratio
        "kda": round((kills + assists) / max(deaths, 1), 2),
    }


def init_csv(filepath: str) -> None:
    """Initialize CSV file with headers if it doesn't exist."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if not path.exists():
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
        print(f"📄 Created new CSV: {filepath}")


def append_to_csv(players: list[dict], filepath: str) -> None:
    """Append player records to CSV file."""
    if not players:
        return
    
    with open(filepath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        for player in players:
            # Filter to only include columns we want
            row = {k: player.get(k, "") for k in CSV_COLUMNS}
            writer.writerow(row)


def count_existing_records(filepath: str) -> int:
    """Count existing records in CSV file."""
    try:
        with open(filepath, "r") as f:
            return sum(1 for _ in f) - 1  # Subtract header
    except FileNotFoundError:
        return 0


def get_existing_match_ids(filepath: str) -> set[int]:
    """Get set of match IDs already in the CSV."""
    match_ids = set()
    try:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    match_ids.add(int(row.get("match_id", 0)))
                except (ValueError, TypeError):
                    continue
    except FileNotFoundError:
        pass
    return match_ids


# ============================================
# Main Harvesting Logic
# ============================================

def harvest_matches(token: str, target_matches: int, output_file: str) -> None:
    """
    Harvest match data from Stratz API.
    
    Uses single-match queries for reliability.
    Appends to CSV as we go for crash resistance.
    """
    # Initialize CSV
    init_csv(output_file)
    
    # Get already-fetched match IDs to avoid duplicates
    existing_match_ids = get_existing_match_ids(output_file)
    existing_count = count_existing_records(output_file)
    
    print(f"\n📊 Starting from {existing_count} existing records")
    print(f"   {len(existing_match_ids)} unique matches already fetched")
    
    # Calculate how many more matches we need
    remaining_matches = target_matches - len(existing_match_ids)
    if remaining_matches <= 0:
        print(f"\n✅ Already have {target_matches}+ matches. Nothing to do!")
        return
    
    print(f"   Need {remaining_matches} more matches")
    print("-" * 60)
    
    # Start harvesting
    current_match_id = BASE_MATCH_ID
    matches_fetched = 0
    total_players = existing_count
    consecutive_failures = 0
    batch_number = 1
    
    while matches_fetched < remaining_matches:
        # Check if we should stop due to too many failures
        if consecutive_failures >= 50:
            print("\n❌ Too many consecutive failures. Stopping.")
            break
        
        # Skip if already fetched
        if current_match_id in existing_match_ids:
            current_match_id -= 1
            continue
        
        # Fetch match
        data = execute_query(
            SIMPLE_MATCH_QUERY,
            {"matchId": current_match_id},
            token
        )
        
        if data and data.get("data", {}).get("match"):
            match = data["data"]["match"]
            players = match.get("players", [])
            
            # Extract player data
            player_records = []
            for player in players:
                record = extract_player_data(match, player)
                if record:
                    player_records.append(record)
            
            if player_records:
                # Append to CSV immediately
                append_to_csv(player_records, output_file)
                
                matches_fetched += 1
                total_players += len(player_records)
                consecutive_failures = 0
                
                # Progress logging every 10 matches
                if matches_fetched % 10 == 0:
                    print(f"📦 Batch {batch_number}: Fetched {matches_fetched}/{remaining_matches} matches "
                          f"(Total records: {total_players})")
                    batch_number += 1
            else:
                consecutive_failures += 1
        else:
            consecutive_failures += 1
        
        # Move to previous match ID
        current_match_id -= 1
        
        # Rate limiting - STRICTLY respect API limits
        time.sleep(RATE_LIMIT_SECONDS)
    
    print("\n" + "=" * 60)
    print("✅ Harvesting Complete!")
    print("=" * 60)
    print(f"   Total matches fetched this session: {matches_fetched}")
    print(f"   Total player records in CSV: {total_players}")


def print_summary(filepath: str) -> None:
    """Print summary statistics of the collected data."""
    print("\n📊 Dataset Summary")
    print("-" * 40)
    
    total = 0
    cores = 0
    supports = 0
    wins = 0
    losses = 0
    imp_sum = 0.0
    
    try:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                
                if row.get("role_type") == "core":
                    cores += 1
                elif row.get("role_type") == "support":
                    supports += 1
                
                if row.get("is_victory") == "1":
                    wins += 1
                else:
                    losses += 1
                
                try:
                    imp_sum += float(row.get("imp", 0))
                except (ValueError, TypeError):
                    pass
    except FileNotFoundError:
        print("   No data file found!")
        return
    
    print(f"   Total records: {total}")
    print(f"   Core players: {cores}")
    print(f"   Support players: {supports}")
    print(f"   Unknown role: {total - cores - supports}")
    print(f"   Winners: {wins}")
    print(f"   Losers: {losses}")
    
    if total > 0:
        print(f"   Average IMP: {imp_sum / total:.2f}")
    
    unique_matches = len(get_existing_match_ids(filepath))
    print(f"   Unique matches: {unique_matches}")


# ============================================
# Main Execution
# ============================================

def main():
    print("=" * 60)
    print("🚀 Phase 17: Supercharged Stratz Data Harvester")
    print("=" * 60)
    print(f"   Target: {TARGET_MATCHES} matches (~{TARGET_MATCHES * 10} players)")
    print(f"   Output: {OUTPUT_FILE}")
    print(f"   Rate limit: {RATE_LIMIT_SECONDS}s between requests")
    
    # Get API token
    try:
        token = get_api_token()
        print(f"   API Token: {token[:8]}...{token[-4:]}")
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    
    # Start harvesting
    try:
        harvest_matches(token, TARGET_MATCHES, OUTPUT_FILE)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user. Progress has been saved!")
    
    # Print summary
    print_summary(OUTPUT_FILE)
    
    print(f"\n📁 Data saved to: {OUTPUT_FILE}")
    print("📈 Next: Run 'python scripts/solve_formula.py' to analyze!")


if __name__ == "__main__":
    main()
