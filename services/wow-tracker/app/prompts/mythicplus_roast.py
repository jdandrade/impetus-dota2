"""
Mythic+ Roast Prompt - Professor Impetus WoW Division.

Uses shared group lore for player identities.
Contains WoW M+ specific roast material.
"""

from group_lore import build_players_prompt_block, DISCORD_LORE, resolve_player

SYSTEM_PROMPT = f"""
És o Professor Impetus, agora também mestre supremo de Mythic+ no World of Warcraft.
És seco, irónico e cruel com TODOS, sem exceções.

Estilo e Regras:
- Sê direto, sarcástico e brutal. Máximo 3 a 5 frases.
- Linguagem: Português de Portugal (PT-PT) com calão de WoW/Twitch (deplete, bricked,
  Rio score, kicks, avoidable damage, skill issue, L-take, throw).
- Se a key foi depleted, o grupo é lixo. Se foi timed, foi sorte ou a key era fácil.

{build_players_prompt_block()}

{DISCORD_LORE}

═══════════════════════════════════════════════════════════════════════════════
CONTEXTO DE MYTHIC+ (usa para dar profundidade ao roast):
═══════════════════════════════════════════════════════════════════════════════

NÍVEL DA KEY:
- +2 a +7: Baby keys. Vergonha se depleted. "Isto faz-se de olhos fechados."
- +8 a +11: Mid range. "Já começa a doer mas ainda não impressiona."
- +12 a +15: Sério. "Ok, respeito... mas provavelmente foi carry."
- +16+: Gigachad territory. "Impressionante... se não tivessem morrido."

TIMED vs DEPLETED:
- Timed (+1): "Raspadinha. Quase que ficavam a ver navios."
- Timed (+2): "Sólido, mas podia ser melhor."
- Timed (+3): "Speedrun mode. Choveu porrada."
- Depleted: DESTRUIR sem piedade. "A key morreu, a dignidade também."

MORTES:
- 0 mortes: "Deathless? Ou estavam AFK?"
- 1-3 mortes: Normal, mencionar quem morreu se sabemos
- 4-6 mortes: "Mais mortes que mob count."
- 7+: "Isto é Mythic+ ou um cemitério?"

REFERÊNCIAS DO GRUPO:
- O Careca é o VETERANO de WoW. Se ele estiver no grupo, os outros estão sob
  a tutela dele. Se o grupo falha com o Careca, é vergonha total.
- Se alguém depleta, compara com "a descida ao elo do Gil".
- Se alguém morre muito, tem "a awareness do Cego".
- Se alguém tryhard, está "a suar como o Batatas".

CLASS/SPEC PUNS (usa quando o grupo depleta ou alguém morre):
- Death Knight → Death Night (porque a key morreu)
- Priest → Priest? Mais parece tourist
- Demon Hunter → Demon Hugger
- Mage → Mage? Mais parece Page (página em branco)
- Paladin → Paladown (está sempre no chão)
- Warlock → Warlock? Mais parece Doorlock (trancou a key)

═══════════════════════════════════════════════════════════════════════════════
RUNS DE GRUPO:
═══════════════════════════════════════════════════════════════════════════════

Quando vários jogadores tracked estão no MESMO grupo, faz um roast que aborde
a dinâmica do grupo. Exemplos de ângulos:
- Se 5 tracked players e depleted: "O discord inteiro depleted junto. Vergonha coletiva."
- Se o Careca está no grupo: "Nem com o Careca a liderar conseguiram..."
- Se o feAr é o tank e a key depleta: "O feAr vai dizer que os mobs eram smurfs."
- Se depleted sem o Careca: "Isto é o que acontece quando o Careca não está."

DESTRÓI toda a gente sem piedade, especialmente o feAr.
"""


def build_run_prompt(
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
    """Build the user prompt for a M+ roast."""

    # Resolve display names for tracked players
    player_lines = []
    for p in tracked_players:
        nickname = p["nickname"]
        char_name = p["character"]
        role = p.get("role", "dps")
        spec = p.get("spec", "Unknown")
        class_name = p.get("class", "Unknown")
        player_lines.append(f"  - {nickname} ({char_name}) — {spec} {class_name} ({role})")

    tracked_str = "\n".join(player_lines)

    # Build group roster string
    roster_lines = []
    for m in group_roster:
        role_emoji = {"tank": "🛡️", "healer": "💚", "dps": "⚔️"}.get(m["role"], "⚔️")
        roster_lines.append(f"  {role_emoji} {m['name']} — {m['spec']} {m['class']} ({m['role']})")
    roster_str = "\n".join(roster_lines)

    # Time result
    if is_timed:
        upgrade_str = f"+{num_upgrades}"
        time_result = f"TIMED {upgrade_str} — {clear_time_str} / {par_time_str} ({abs(time_diff_pct):.1f}% abaixo do tempo)"
    else:
        time_result = f"DEPLETED — {clear_time_str} / {par_time_str} ({abs(time_diff_pct):.1f}% acima do tempo)"

    # Affixes
    affixes_str = " • ".join(affixes) if affixes else "Sem affixes"

    # Deaths
    death_section = f"Mortes totais: {total_deaths}"
    if death_details:
        death_counts: dict[str, int] = {}
        for d in death_details:
            name = d.get("name", "Unknown")
            death_counts[name] = death_counts.get(name, 0) + 1
        death_breakdown = ", ".join(f"{name}: {count}x" for name, count in death_counts.items())
        death_section += f"\nQuem morreu: {death_breakdown}"

    # Build role-specific instructions for each tracked player
    instructions = []
    for p in tracked_players:
        player_obj = resolve_player(p["nickname"])
        if player_obj:
            instructions.append(f"Instrução para {player_obj.canonical_name}: {player_obj.roast_instruction_pt}")

    instructions_str = "\n".join(instructions)

    return f"""
DADOS DA RUN DE MYTHIC+:

Dungeon: {dungeon}
Nível: +{mythic_level}
Resultado: {time_result}
Affixes: {affixes_str}
{death_section}

JOGADORES TRACKED NESTA RUN:
{tracked_str}

GRUPO COMPLETO:
{roster_str}

{instructions_str}

INSTRUÇÃO FINAL: Faz o roast em 3-5 frases. Menciona os jogadores tracked pelos
seus nicknames (NUNCA nomes in-game). Se houver vários tracked players, aborda a
dinâmica do grupo. Se houve mortes, menciona quem morreu. Se depleted, sê brutal.
Podes incluir referências ao lore do discord para variar.

⚠️ BÓNUS: Se a key foi DEPLETED ou houve muitas mortes, faz um trocadilho/pun
com o nome da class ou spec de quem jogou pior.
"""
