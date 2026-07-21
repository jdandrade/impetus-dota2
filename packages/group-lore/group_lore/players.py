"""
Player identities for the Impetus Discord group.

Each player has a canonical name, personality archetype, roast instructions,
and a list of aliases (in-game names across all games).
"""

from dataclasses import dataclass, field


@dataclass
class Player:
    canonical_name: str
    emoji: str
    archetype: str
    personality_pt: str
    roast_instruction_pt: str
    aliases: list[str] = field(default_factory=list)


# All tracked players in the Discord group
PLAYERS: dict[str, Player] = {
    "fear": Player(
        canonical_name="feAr",
        emoji="😡",
        archetype="O Tiltado / Caçador de Smurfs",
        personality_pt=(
            "O feAr é o rager oficial do grupo. Perde e a culpa NUNCA é dele: o inimigo "
            "era smurf, os teammates eram bots, o matchmaking está rigged, havia lag. "
            "Chama smurf a TODA a gente que o mata. Roasta-o SEM PIEDADE sobre a raiva, "
            "as desculpas e as acusações de smurf. Varia os ângulos - não repitas sempre "
            "a mesma piada. A mulher do feAr é a Daniela - coitada, tem de o ouvir a ragear."
        ),
        roast_instruction_pt=(
            "DESTRÓI o feAr sem piedade, em TODOS os jogos. Ele acha que toda a gente "
            "que o mata é smurf e que o matchmaking está rigged contra ele. Se perdeu, "
            "goza com as desculpas que ele já está a inventar (smurfs, lag, equipa de bots). "
            "Se ganhou, foi carregado ou finalmente calhou-lhe um jogo \"sem smurfs\". "
            "Varia as piadas de raiva de formas criativas."
        ),
        aliases=["fear^", "fear", "feardk"],
    ),
    "mauzaum": Player(
        canonical_name="MauZaum",
        emoji="🧠",
        archetype="O Favorito / O Intelectual",
        personality_pt=(
            "O MauZaum é o aluno favorito do Professor Impetus. É o ruivo intelectual do "
            "grupo. Quando alguém joga bem, pergunta se \"andou a estudar com o MauZaum\". "
            "Nota: \"Mister Miagy\" é a MESMA pessoa que MauZaum - trata sempre como MauZaum."
        ),
        roast_instruction_pt=(
            "O MauZaum é o teu aluno favorito, o intelectual ruivo. "
            "Elogia a sua inteligência superior. Se jogou mal, foi culpa dos colegas que não "
            "acompanham o seu cérebro gigante."
        ),
        aliases=["mauzaum", "mister miagy", "mister_miagy", "padrezaum", "mz"],
    ),
    "cego": Player(
        canonical_name="Cego",
        emoji="👶",
        archetype="O Puto de 12 anos",
        personality_pt=(
            "O Cego é o mais novo do grupo - tem 12 anos. É tão novo que nem era vivo "
            "quando o Dota original foi lançado. Faz piadas sobre a idade dele de formas "
            "VARIADAS - não uses sempre a mesma piada. Exemplos de ângulos (usa apenas "
            "como inspiração, NÃO repitas): jogos de crianças, hora de dormir, escola, "
            "puberdade, não ter idade para ranked, etc. É também o rei das picks off-meta."
        ),
        roast_instruction_pt=(
            "O Cego tem 12 anos - nem era vivo quando o Dota lançou. Faz piadas "
            "sobre a idade dele de formas VARIADAS (escola, hora de dormir, puberdade, jogos de crianças). "
            "NÃO uses sempre a mesma piada. Se fez picks estranhas, é a \"cegueira mental\" dele."
        ),
        aliases=["rybur", "bad man", "cego"],
    ),
    "batatas": Player(
        canonical_name="Batatas",
        emoji="💦",
        archetype="O Tryhard Suado",
        personality_pt=(
            "O Batatas é o jogador mais suado do grupo. Transpira o teclado TODO. Só quer "
            "ganhar a todo o custo. Se perder, a culpa é SEMPRE da equipa, nunca dele. "
            "Quando alguém é demasiado tryhard = \"a suar como o Batatas\"."
        ),
        roast_instruction_pt=(
            "O Batatas é o tryhard suado. Se ganhou, andou a transpirar "
            "o teclado todo. Se perdeu, vai culpar a equipa - porque ele NUNCA tem culpa."
        ),
        aliases=["luciuslunaris", "batatas", "baconlayss"],
    ),
    "hory": Player(
        canonical_name="Hory",
        emoji="🌐",
        archetype="O Gajo da Internet",
        personality_pt=(
            "O Hory é o expert em redes do grupo. Faz piadas sobre protocolos de rede, "
            "TCP/IP, ping, packet loss, routing tables, DNS, firewalls. Piadas de IT guy."
        ),
        roast_instruction_pt=(
            "O Hory é o gajo da IT. Faz piadas sobre protocolos de rede, "
            "ping, packet loss, TCP/IP, DNS. Usa metáforas de networking no roast."
        ),
        aliases=["hory"],
    ),
    "gil": Player(
        canonical_name="Gil",
        emoji="📉",
        archetype="O Fundo do Poço",
        personality_pt=(
            "O Gil tem 700 MMR - é inacreditável quão baixo ele está. É o benchmark do "
            "fracasso. Perder ou jogar mal = \"descida ao inferno do Gil\" ou \"a caminho "
            "do elo do Gil\". Já ninguém espera nada dele."
        ),
        roast_instruction_pt=(
            "O Gil tem 700 MMR - é inacreditável. É o fundo do poço. "
            "Qualquer má performance é \"a caminho do elo do Gil\". Já ninguém espera nada dele."
        ),
        aliases=["rodrigo", "gil"],
    ),
    "careca": Player(
        canonical_name="Careca",
        emoji="🦲",
        archetype="O Gooner do WoW",
        personality_pt=(
            "O Careca é um gooner. Só joga WoW. É um gigante. Está SEMPRE certo. "
            "O único que joga WoW a sério no grupo."
        ),
        roast_instruction_pt=(
            "O Careca é o veterano de WoW do grupo. Está SEMPRE certo. "
            "Se alguém joga mal, o Careca já tinha avisado. Se joga bem, é porque "
            "seguiu os conselhos do Careca."
        ),
        aliases=["careca", "dabadi", "babibi"],
    ),
    "paulo": Player(
        canonical_name="Paulo",
        emoji="😭",
        archetype="O Chorão",
        personality_pt=(
            "O Paulo é o gajo que está sempre a chorar. É benfiquista de coração. "
            "Chora por tudo e por nada. Se perde, chora. Se ganha, chora de alívio."
        ),
        roast_instruction_pt=(
            "O Paulo é o chorão do grupo. Benfiquista de coração. "
            "Se correu mal, já está a chorar. Se correu bem, chora de alívio. "
            "Faz referências ao Benfica e às lágrimas dele."
        ),
        aliases=["paulo", "zenyär", "zenyar", "zeny", "roflicious"],
    ),
}


def resolve_player(name: str) -> Player | None:
    """
    Match any alias (case-insensitive) to a canonical Player.
    Returns None if no match found.
    """
    name_lower = name.lower()
    for player in PLAYERS.values():
        for alias in player.aliases:
            if alias in name_lower:
                return player
    return None


def build_players_prompt_block() -> str:
    """Build the players section for any system prompt."""
    lines = []
    lines.append("═" * 75)
    lines.append("OS JOGADORES DO GRUPO (usa APENAS estes nomes, NUNCA o nome in-game):")
    lines.append("═" * 75)
    lines.append("")
    for player in PLAYERS.values():
        lines.append(f"{player.emoji} {player.canonical_name} ({player.archetype}):")
        lines.append(f"   {player.personality_pt}")
        lines.append("")
    return "\n".join(lines)


def build_name_mappings() -> dict[str, str]:
    """Build alias -> canonical_name dict for prompt name resolution."""
    mappings = {}
    for player in PLAYERS.values():
        for alias in player.aliases:
            mappings[alias] = player.canonical_name
    return mappings
