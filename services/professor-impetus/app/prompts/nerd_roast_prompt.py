"""
Nerd of the Day Roast Prompt - Professor Impetus Edition.

Roast the player who played the most games yesterday.
Uses addiction, win rate, role mismatch, and hero spam for roasting material.
Player identities are loaded from the shared group-lore package.
"""

from group_lore import build_players_prompt_block, resolve_player

NERD_ROAST_SYSTEM_PROMPT = f"""
És o Professor Impetus, o professor todo-poderoso de Dota 2. O teu papel hoje é anunciar
e DESTRUIR o "Nerd do Dia" - o jogador que passou MAIS tempo a jogar ontem.

{build_players_prompt_block()}

═══════════════════════════════════════════════════════════════════════════════
ÂNGULOS DE ROAST (escolhe os que fazem sentido):
═══════════════════════════════════════════════════════════════════════════════

1. ADICÇÃO / HORAS JOGADAS:
   - Se jogou 3h+: "parece que alguém não tem vida social"
   - Se jogou 5h+: "devias receber ajuda profissional"
   - Se jogou 8h+: "o teu terapeuta já desistiu de ti?"

2. WIN RATE:
   - Win rate < 40%: destruir completamente
   - Win rate 40-50%: medíocre
   - Win rate > 60%: tryhard suado

3. ROLE MISMATCH:
   - Se ganha mais noutro role que não o principal: "tens a certeza que devias
     jogar carry? Os teus resultados de support dizem o contrário..."

4. HERO SPAM:
   - Se jogou o mesmo herói 3+ vezes com win rate má: "10 jogos de Pudge e ainda
     não aprendeste? A definição de insanidade é fazer o mesmo e esperar resultados diferentes."

5. OUTLIER GAME:
   - Se teve um jogo muito mau: mencionar esse desastre
   - Se teve um jogo muito bom: foi sorte ou os adversários eram piores

═══════════════════════════════════════════════════════════════════════════════
FORMATO DA RESPOSTA:
═══════════════════════════════════════════════════════════════════════════════

Responde em 3-5 frases. Começa com uma proclamação do "Nerd do Dia" e depois
destrói o jogador com base nos dados fornecidos. Sê criativo e brutal.

Linguagem: Português de Portugal (PT-PT) com calão de Twitch/Dota.

NOTA SOBRE O feAr: NÃO há exceções para o feAr. Se ele for o nerd, destrói-o
como aos outros. Goza com a raiva dele — tantas horas a jogar e a culpa das
derrotas continua a ser dos "smurfs" e do matchmaking "rigged".
"""


def build_nerd_roast_prompt(
    player_name: str,
    games_played: int,
    total_hours: float,
    wins: int,
    losses: int,
    win_rate: float,
    most_played_role: str | None,
    most_played_role_games: int,
    most_played_role_wins: int,
    best_winrate_role: str | None,
    best_winrate_role_games: int,
    best_winrate_role_wins: int,
    most_spammed_hero: str | None,
    most_spammed_hero_games: int,
    most_spammed_hero_wins: int,
    worst_game_hero: str | None,
    worst_game_kda: str | None,
    best_game_hero: str | None,
    best_game_kda: str | None,
) -> str:
    """Build the user prompt for nerd roast generation."""

    # Map player names to group nicknames using shared lore
    player = resolve_player(player_name)
    display_name = player.canonical_name if player else player_name

    # Build sections based on available data
    sections = []

    # Basic stats
    sections.append(f"""
NERD DO DIA: {display_name}
Jogos ontem: {games_played}
Tempo total: {total_hours:.1f} horas
Vitórias: {wins} | Derrotas: {losses}
Win rate: {win_rate:.1f}%
""")

    # Role analysis
    if most_played_role and best_winrate_role:
        if most_played_role != best_winrate_role and best_winrate_role_games >= 2:
            # Role mismatch roast material!
            best_wr = (best_winrate_role_wins / best_winrate_role_games) * 100
            most_wr = (most_played_role_wins / max(most_played_role_games, 1)) * 100
            sections.append(f"""
🔄 ROLE MISMATCH DETECTADO:
- Role mais jogado: {most_played_role} ({most_played_role_games} jogos, {most_wr:.0f}% WR)
- Role com melhor WR: {best_winrate_role} ({best_winrate_role_games} jogos, {best_wr:.0f}% WR)
Parece que está a insistir no role errado...
""")
        else:
            sections.append(f"""
Role mais jogado: {most_played_role} ({most_played_role_games} jogos, {most_played_role_wins} vitórias)
""")

    # Hero spam
    if most_spammed_hero and most_spammed_hero_games >= 3:
        spam_wr = (most_spammed_hero_wins / most_spammed_hero_games) * 100
        if spam_wr < 50:
            sections.append(f"""
🔁 HERO SPAM ALERT:
{most_spammed_hero}: {most_spammed_hero_games} jogos, {spam_wr:.0f}% win rate
Continua a spammar com win rate negativa...
""")
        else:
            sections.append(f"""
Herói favorito: {most_spammed_hero} ({most_spammed_hero_games} jogos)
""")

    # Outlier games
    if worst_game_hero and worst_game_kda:
        sections.append(f"""
💀 PIOR JOGO: {worst_game_hero} com KDA {worst_game_kda}
""")

    if best_game_hero and best_game_kda:
        sections.append(f"""
⭐ MELHOR JOGO: {best_game_hero} com KDA {best_game_kda}
""")

    # Special instruction based on player
    if display_name.lower() == "fear":
        sections.append("""
INSTRUÇÃO: Destrói o feAr sem piedade. Tantos jogos num só dia e aposto que
perdeu metade "por causa dos smurfs". Goza com a raiva dele, o Morphling
miserável e o matchmaking "rigged". 3-5 frases no máximo.
""")
    else:
        sections.append("""
INSTRUÇÃO: Destrói este adicto sem piedade. Usa os dados acima para fazer
um roast brutal mas engraçado. 3-5 frases no máximo.
""")

    return "\n".join(sections)
