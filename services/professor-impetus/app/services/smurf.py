"""
Post-game smurf check.

Looks at the enemy team of a finished match and flags accounts with very few
lifetime games, using OpenDota's win/loss totals.

This is a hint, not proof:
- Players who hide their match data are anonymous in the match and cannot be
  checked (and serious smurfs often hide it).
- The count is the games OpenDota knows about, so an old account that only
  recently exposed its match data can look newer than it is.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.services.opendota import HERO_NAMES, MatchData, get_player_total_games

logger = logging.getLogger(__name__)

# Valve reports this account ID for players who hide their match data
ANONYMOUS_ACCOUNT_ID = 4294967295
# Need at least this many checkable enemies to say "no smurfs here"
MIN_KNOWN_FOR_ALL_CLEAR = 3
CHECK_TIMEOUT_SECONDS = 15


@dataclass
class Suspect:
    hero_name: str
    games: int
    kda: str


@dataclass
class SmurfReport:
    """Result of checking one team's opponents."""
    suspects: list = field(default_factory=list)
    known_games: list = field(default_factory=list)  # lifetime games of each checkable enemy
    hidden: int = 0                                  # enemies that could not be checked

    def embed_line(self) -> str:
        """One line for the Discord report card."""
        hidden = f" · {self.hidden} hidden" if self.hidden else ""
        if self.suspects:
            return "\n".join(
                f"🕵️ Suspicious: enemy **{s.hero_name}** has only {s.games:,} games ({s.kda})"
                for s in self.suspects
            ) + hidden
        if not self.known_games:
            return "❔ All enemies hide their match data"
        low, high = min(self.known_games), max(self.known_games)
        if len(self.known_games) == 1:
            return f"✅ No smurfs found: the 1 visible enemy has {low:,} games{hidden}"
        return (
            f"✅ No smurfs found: the {len(self.known_games)} visible enemies "
            f"have {low:,}–{high:,} games{hidden}"
        )

    def prompt_note(self) -> Optional[str]:
        """Context for the roast prompt (Portuguese), or None if inconclusive."""
        if self.suspects:
            who = "; ".join(
                f"{s.hero_name} inimigo tem apenas {s.games} jogos na conta (KDA {s.kda})"
                for s in self.suspects
            )
            return (
                f"VERIFICAÇÃO DE SMURFS: {who}. É suspeito de ser smurf, mas não é prova. "
                "Podes usar isto no roast."
            )
        if len(self.known_games) >= MIN_KNOWN_FOR_ALL_CLEAR:
            return (
                "VERIFICAÇÃO DE SMURFS: nenhum inimigo parece smurf (contas com "
                f"{min(self.known_games)} a {max(self.known_games)} jogos). "
                "Se o jogador costuma culpar smurfs, goza com isso: desta vez não havia nenhum."
            )
        return None


async def check_enemies(match: MatchData, max_games: int) -> Optional[SmurfReport]:
    """
    Check the enemy team of a match for likely smurfs.

    Args:
        match: The tracked player's match (needs all_players with account IDs)
        max_games: An enemy with fewer lifetime games than this is suspicious

    Returns:
        SmurfReport, or None if the match has no roster to check or the
        lookups failed.
    """
    enemies = [
        p for p in (match.all_players or [])
        if p.is_radiant != match.is_radiant
    ]
    if not enemies:
        return None

    checkable = [
        p for p in enemies
        if p.account_id and p.account_id != ANONYMOUS_ACCOUNT_ID
    ]
    report = SmurfReport(hidden=len(enemies) - len(checkable))

    try:
        totals = await asyncio.wait_for(
            asyncio.gather(*(get_player_total_games(p.account_id) for p in checkable)),
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Smurf check timed out for match {match.match_id}")
        return None

    if checkable and all(t is None for t in totals):
        # OpenDota unavailable: say nothing rather than "all hidden"
        return None

    for player, total in zip(checkable, totals):
        # 0 known games means OpenDota has no history for the account,
        # which is "unknown", not "brand new"
        if not total:
            report.hidden += 1
            continue
        report.known_games.append(total)
        if total < max_games:
            report.suspects.append(Suspect(
                hero_name=HERO_NAMES.get(player.hero_id, f"Hero #{player.hero_id}"),
                games=total,
                kda=f"{player.kills}/{player.deaths}/{player.assists}",
            ))

    report.suspects.sort(key=lambda s: s.games)
    return report
