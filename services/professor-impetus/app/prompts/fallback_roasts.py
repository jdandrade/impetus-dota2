"""
Fallback roast messages for when Gemini API is unavailable.

100+ aggressive, lore-aware roast messages in PT-PT with Dota/Twitch slang.
Organized by IMP score tiers with group lore references.
"""

import random

from app.services.opendota import MatchData
from app.services.imp_engine import IMPResult
from group_lore import resolve_player


# ═══════════════════════════════════════════════════════════════════════════════
# TIER GODLIKE (IMP >= 30) — Sarcastic praise, backhanded compliments
# ═══════════════════════════════════════════════════════════════════════════════

TIER_GODLIKE: list[str] = [
    "🎓 **{player_name}**, IMP **{imp_score}** de {hero_name}?! Andaste a copiar os trabalhos de casa do MauZaum outra vez? 📚",
    "🔥 **{player_name}** com **{imp_score}**! O professor está em choque. Isto é como ver o Gil a subir de MMR — teoricamente impossível.",
    "💯 **{player_name}**, {kda} de {hero_name}... Grau **{grade}**. Até o States com 77 anos se levantou da cadeira de baloiço para aplaudir. 👴",
    "🏆 **{player_name}**, IMP **{imp_score}**! Parabéns, hoje não és um peso morto. A tua equipa deve estar em choque clínico. 🏥",
    "👑 **{player_name}**, **{imp_score}** de IMP?! Quem és tu e o que fizeste com o jogador medíocre que costumamos ver? 🕵️",
    "🎖️ **{player_name}** destruiu com {hero_name}! {kda}! Vou guardar este momento porque não vai acontecer outra vez tão cedo.",
    "📜 **{player_name}**, IMP **{imp_score}**... O MauZaum ligou a perguntar se pode estudar contigo. O mundo está ao contrário. 🌍",
    "🌟 **{player_name}**, Grau **{grade}** com {hero_name}? Fizeste um pacto com o diabo ou finalmente tiraste o monitor da caixa? 📦",
    "🔥 **{player_name}**, {kda}?! IMP **{imp_score}**! Até o Batatas parou de suar por um segundo para te aplaudir. Só um segundo. 💦",
    "🏆 **{player_name}**, hoje jogaste como se o teu MMR dependesse disso. Ah espera, depende. E mesmo assim impressionaste. GG.",
    "👑 **{player_name}**, IMP **{imp_score}** com {hero_name}. Atenção que assim até a Daniela vai querer saber o que é Dota. 🎮",
    "💎 **{player_name}**, Grau **{grade}**? Isto é real? Alguém confirme que não estamos a ser trollados. O professor precisa de um café. ☕",
    "🎓 **{player_name}**, **{imp_score}** de IMP... Jogaste tão bem que até o Gil sentiu esperança. Pobre Gil. 📉",
    "🔥 **{player_name}** com {hero_name}, {kda}! O Careca já está no Discord a dizer que sempre acreditou em ti. Mentiroso. 🦲",
    "⭐ **{player_name}**, IMP **{imp_score}**! Guarda o replay. A sério. Porque amanhã voltas ao normal e vais precisar de provas de que isto aconteceu.",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TIER GOOD (IMP 10 to 29) — Grudging respect, tryhard accusations
# ═══════════════════════════════════════════════════════════════════════════════

TIER_GOOD: list[str] = [
    "🔥 **{player_name}**, IMP **{imp_score}** com {hero_name}! Nada mau. Andaste a suar como o Batatas ou foi talento natural? 💦",
    "👑 **{player_name}**, {kda} de {hero_name}. Sólido. Mas não te entusiasmes — o MauZaum faz isto a dormir. 😴",
    "📜 **{player_name}**, IMP **{imp_score}**. Um jogo decente! Marca no calendário porque isto não é frequente. 📅",
    "🌟 **{player_name}**, Grau **{grade}** com {hero_name}? Ok, ok. Hoje não envergonhas a família. Amanhã é outro dia. 🎲",
    "💪 **{player_name}**, **{imp_score}** de IMP. O Paulo até parou de chorar por ti. Temporariamente. 😭",
    "📈 **{player_name}**, {kda}! IMP **{imp_score}**! Isto é progresso ou tiveste sorte com os teammates? Pergunta séria. 🤔",
    "🎯 **{player_name}** com {hero_name}, **{imp_score}** IMP. Bom esforço! Se mantiveres isto talvez saias do elo do Gil daqui a 200 jogos. 📉",
    "✅ **{player_name}**, Grau **{grade}**. Jogaste como um ser humano funcional. O professor está orgulhoso. Quase. 🥲",
    "🔥 **{player_name}**, IMP **{imp_score}**! O teclado do Batatas está com ciúmes do teu. Quantos litros de suor? 💧",
    "🎖️ **{player_name}**, {kda} com {hero_name}. Objectivamente decente. O Hory já te está a meter na whitelist da firewall. 🌐",
    "📊 **{player_name}**, **{imp_score}**! Parabéns, não és o pior jogador do grupo. Esse título continua com o Gil. 🏚️",
    "💫 **{player_name}**, IMP **{imp_score}** de {hero_name}. Até o Cego com 12 anos aprovaria. E ele reprova tudo. 👶",
    "🎮 **{player_name}**, Grau **{grade}**! Tiveste um jogo de gente. Descansa agora que amanhã a realidade bate à porta. 🚪",
    "⚡ **{player_name}**, {kda}! IMP **{imp_score}**! Alguém troque-me este jogador — de onde veio esta competência?! 🔄",
    "🏅 **{player_name}**, **{imp_score}** com {hero_name}. Bom jogo! Mas lembra-te: uma andorinha não faz a primavera. Nem um bom jogo faz um bom jogador. 🐦",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TIER AVERAGE (IMP -9 to 9) — Invisible, mediocre, forgettable
# ═══════════════════════════════════════════════════════════════════════════════

TIER_AVERAGE: list[str] = [
    "😐 **{player_name}**, IMP **{imp_score}** com {hero_name}. Estiveste no jogo ou foste só um creep com nome? 🐑",
    "🥱 **{player_name}**, {kda}... Grau **{grade}**. A tua presença no jogo foi tão relevante como wards no Herald. 💤",
    "🔎 **{player_name}**, **{imp_score}** de IMP. Alguém notou que estavas no jogo? Porque a tua equipa claramente não. 👻",
    "📉 **{player_name}**, IMP **{imp_score}** com {hero_name}. Nem bom nem mau. Apenas... exististe. Parabéns? 🤷",
    "😶 **{player_name}**, Grau **{grade}**. A definição de mediocridade. Até o teu {hero_name} estava envergonhado. 😬",
    "🛋️ **{player_name}**, **{imp_score}**? Parece que jogaste Dota da mesma forma que o States joga — sentado, confuso, e sem impacto. 👴",
    "🥱 **{player_name}**, {kda} de {hero_name}. IMP **{imp_score}**. O Hory tem packets com mais impacto que tu neste jogo. 📡",
    "💤 **{player_name}**, Grau **{grade}**... A tua performance foi tão emocionante como ver o Gil a farmar jungle durante 40 minutos. 🌲",
    "🪨 **{player_name}**, IMP **{imp_score}**. Foste literalmente uma pedra no mapa. Pelo menos as pedras não feedam. Geralmente. 🗿",
    "😐 **{player_name}**, **{imp_score}** com {hero_name}? O MauZaum diz que te falta awareness. O professor diz que te falta tudo. 🧠",
    "📊 **{player_name}**, {kda}. IMP **{imp_score}**. Nem report nem commend. Apenas um NPC na história de outra pessoa. 🤖",
    "🌫️ **{player_name}**, Grau **{grade}** de {hero_name}. Fostes tão invisível que pensaram que tinhas abandonado. Até verificaram. 👀",
    "🚶 **{player_name}**, IMP **{imp_score}**. Participaste no jogo da mesma forma que o Paulo participa sem chorar — ou seja, não participaste. 😭",
    "😴 **{player_name}**, **{imp_score}**... {kda} de {hero_name}. Isto não é Dota, isto é uma simulação de estar AFK com passos extra. 🚫",
    "📋 **{player_name}**, Grau **{grade}**. Performance medíocre, presença nula, impacto zero. Classic {player_name} experience. ™️",
    "🫥 **{player_name}**, IMP **{imp_score}** com {hero_name}. Se a mediocridade fosse uma skill, tinhas Grau S. 🏆",
    "😑 **{player_name}**, {kda}... O Batatas sua mais numa ida à casa de banho do que tu suaste neste jogo. Zero esforço. 🚽",
    "🗑️ **{player_name}**, IMP **{imp_score}**. Nem para o bem nem para o mal. É como se não tivesses jogado. Skill issue? Existence issue. 💀",
    "🌀 **{player_name}**, Grau **{grade}** de {hero_name}. A definição humana de \"meh\". O Careca está desapontado e ele nem joga Dota. 🦲",
    "📎 **{player_name}**, **{imp_score}**? Tão útil como o Clippy do Windows. \"Parece que estás a tentar jogar Dota. Precisa de ajuda?\" 📌",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TIER BAD (IMP -39 to -10) — Descent to Gil's MMR, report-worthy
# ═══════════════════════════════════════════════════════════════════════════════

TIER_BAD: list[str] = [
    "📉 **{player_name}**, IMP **{imp_score}** de {hero_name}?! Estás oficialmente a caminho do elo do Gil. Parabéns pela descida. 🕳️",
    "💩 **{player_name}**, {kda}... Grau **{grade}**. Nem os bots do tutorial jogam tão mal. E eles nem tentam. 🤖",
    "🚨 **{player_name}**, **{imp_score}** com {hero_name}?! O Valve Anti-Cheat devia investigar se usaste um bot para jogar. Um bot MAU. 😵‍💫",
    "📞 **{player_name}**, IMP **{imp_score}**. O professor já ligou para os teus pais. Estavas a jogar ou a trollar a equipa? 🎭",
    "⚰️ **{player_name}**, {deaths} mortes com {hero_name}?! IMP **{imp_score}**. Até o Paulo chorou por ti e olha que ele chora por tudo. 😭",
    "🗑️ **{player_name}**, Grau **{grade}**... O Gil viu este jogo e sentiu-se melhor consigo mesmo. Tu és a terapia dele. 📉",
    "🧶 **{player_name}**, IMP **{imp_score}** com {hero_name}? Mas tu jogaste Dota ou estiveste a fazer tricô? Porque o resultado é o mesmo. 🪡",
    "⛔ **{player_name}**, {kda}... **{imp_score}** de IMP. Skill issue clássica. O MauZaum mandou-te um livro de Dota por correio. 📚",
    "🚑 **{player_name}**, **{imp_score}**?! A tua equipa precisa de apoio psicológico depois de jogar contigo. Paginas tu ou divides? 🏥",
    "📦 **{player_name}**, IMP **{imp_score}** de {hero_name}. Jogaste com o teclado desligado? Precisas de um reembolso? ⌨️",
    "🔥 **{player_name}**, Grau **{grade}** com {kda}! Deste uma masterclass em como perder jogos. O Cego com 12 anos faz melhor e ele nem sequer devia estar acordado a esta hora. 👶",
    "💀 **{player_name}**, IMP **{imp_score}**... {deaths} mortes. O teu {hero_name} devia processar-te por difamação. Tribunal de Haia. ⚖️",
    "🚨 **{player_name}**, **{imp_score}** de IMP. O Hory devia configurar-te uma firewall contra o feed. Packets de merda a sair de ti o jogo todo. 🌐",
    "📉 **{player_name}**, {kda} de {hero_name}... O professor recomenda que voltes ao tutorial. Depois volta. Depois faz o tutorial outra vez. 🔄",
    "🤡 **{player_name}**, IMP **{imp_score}**. A tua performance foi o equivalente a {hero_name} jogar com lag de 500ms. Mas tu não tinhas lag. Era só mau mesmo. 📡",
    "⚠️ **{player_name}**, Grau **{grade}**! Este jogo foi tão mau que até o Batatas disse \"pelo menos eu esforço-me\". E tem razão. 💦",
    "🏚️ **{player_name}**, **{imp_score}** com {hero_name}. Welcome to the shadow realm. 700 MMR está à tua espera de braços abertos. 🫱",
    "📊 **{player_name}**, {kda}... IMP **{imp_score}**. O Stratz achou que era um erro no código. Não era. És tu. 🤖",
    "🛑 **{player_name}**, IMP **{imp_score}** de {hero_name}?! Se a tua equipa pudesse reportar-te duas vezes, reportava. 🚩",
    "😵 **{player_name}**, Grau **{grade}**... {deaths} mortes. O States com 77 anos e artrite nas mãos faria melhor. No VR. Com um olho fechado. 👴",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TIER CATASTROPHE (IMP < -39) — Nuclear roasts, career-ending
# ═══════════════════════════════════════════════════════════════════════════════

TIER_CATASTROPHE: list[str] = [
    "💀 **{player_name}**, IMP **{imp_score}** com {hero_name}?! CATÁSTROFE. Fizeste speedrun de destruir um jogo de Dota. Parabéns, record mundial. 🏆",
    "🤡 **{player_name}**, {kda}?! **{imp_score}** de IMP?! Oficialmente o prémio 'PAID ACTOR' vai para ti. Quanto te pagou a equipa adversária? 💰",
    "⚰️ **{player_name}**, IMP **{imp_score}** de {hero_name}... Nem no Herald aceitam este gameplay. Tens de PAGAR suborno ao MMR para não descer. 💸",
    "🚨 **{player_name}**, Grau **{grade}**?! {deaths} MORTES?! O professor suspendeu-te do Dota. Entrega o teclado. AGORA. ⌨️🔒",
    "💩 **{player_name}**, **{imp_score}** com {hero_name}... Isto não é Dota. Isto é um tutorial de como alimentar 5 jogadores adversários ao mesmo tempo. 🍽️",
    "🏚️ **{player_name}**, IMP **{imp_score}**?! Já pensaste em desistir? O Candy Crush não tem report system. É perfeito para ti. 🍬",
    "⛔ **{player_name}**, {kda} de {hero_name}?! O Gil com 700 MMR viu isto e mandou-te uma mensagem: \"irmão, estás bem?\" 📱",
    "🔥 **{player_name}**, IMP **{imp_score}**!! Tu não jogaste Dota. Tu cometeste um CRIME contra a tua equipa. Low priority é pouco. 🏛️",
    "💀 **{player_name}**, Grau **{grade}** com {hero_name}... {deaths} mortes. A tua equipa já criou um grupo de WhatsApp SEM ti. 📵",
    "🤡 **{player_name}**, **{imp_score}**?! YES RELAX BECAUSE RETARRRRRD? Este jogo foi um atentado ao Dota 2 como desporto electrónico. 🎪",
    "⚰️ **{player_name}**, IMP **{imp_score}** com {hero_name}! O Batatas está a suar de raiva SÓ de ver este jogo. E olha que ele sua por tudo. 💦🔥",
    "🚑 **{player_name}**, {kda}... **{imp_score}** de IMP. A tua equipa ainda está em recuperação intensiva. O seguro de saúde não cobre isto. 🏥",
    "🗑️ **{player_name}**, Grau **{grade}** de {hero_name}?! Desinstala. Reinstala. Desinstala outra vez. É a única solução. 🔄💀",
    "📞 **{player_name}**, IMP **{imp_score}**... A Daniela ligou a perguntar se precisas de terapia. O feAr ofereceu-se para pagar. Por pena. 💔",
    "💀 **{player_name}**, **{imp_score}** com {hero_name}?! {deaths} mortes?! Tu não morreste no jogo — o jogo morreu CONTIGO. 🪦",
    "🚨 **{player_name}**, IMP **{imp_score}**!! O MauZaum analisou este replay e ficou clinicamente deprimido. Estragaste-lhe o dia. 🧠💀",
    "⛔ **{player_name}**, Grau **{grade}**... {kda} de {hero_name}. O Cego com 12 anos a jogar às 3 da manhã sem os pais saberem FAZ MELHOR QUE ISTO. 👶🔥",
    "🤡 **{player_name}**, **{imp_score}**?! Jogaste como se fosse a primeira vez que viste um computador. O States adaptou-se melhor à tecnologia que tu. 👴💻",
    "💩 **{player_name}**, IMP **{imp_score}** de {hero_name}! A tua equipa devia receber compensação financeira por ter jogado contigo. Trauma colectivo. 💶",
    "⚰️ **{player_name}**, {kda}?! **{imp_score}** de IMP?! Mete um vídeo no YouTube — esta obra-prima precisa de ser estudada como exemplo do que NÃO fazer. 📹",
    "🔥 **{player_name}**, Grau **{grade}** com {hero_name}?! Parabéns, deste a vitória de bandeja à outra equipa. Paid actor confirmado. 🎬",
    "💀 **{player_name}**, IMP **{imp_score}**... O Paulo está a chorar. Mas desta vez são lágrimas de vergonha alheia por ti. 😭",
    "🚨 **{player_name}**, **{imp_score}** com {hero_name}?! {deaths} mortes?! Isto é grief ou és genuinamente este mau? Pergunta séria. 🤔",
    "⛔ **{player_name}**, IMP **{imp_score}**!! O Hory devia bloquear-te o IP do servidor de Dota. Firewall permanente. Sem apelo. 🌐🔒",
    "🤡 **{player_name}**, Grau **{grade}**... Os teus teammates estão neste momento a escrever um ensaio no Reddit sobre ti. Tens noção? 📝",
    "💩 **{player_name}**, {kda} de {hero_name}?! IMP **{imp_score}**?! O Careca do WoW disse que até num MMO ele é mais útil em equipa que tu. 🦲",
    "⚰️ **{player_name}**, **{imp_score}**!! Não sei o que é pior — este jogo ou o facto de amanhã ires fazer a mesma coisa. Ciclo de abuso. 🔄",
    "🔥 **{player_name}**, IMP **{imp_score}** com {hero_name}?! Isto nem é Dota. Isto é terrorismo digital. A INTERPOL já tem o teu nome. 🚔",
    "💀 **{player_name}**, Grau **{grade}**... {deaths} mortes com {hero_name}. Tens a certeza que não estás a jogar do lado da outra equipa? Double agent? 🕵️",
    "🚨 **{player_name}**, **{imp_score}** de IMP?! Touch grass. Apanha sol. Faz qualquer coisa. Menos jogar Dota. QUALQUER coisa. 🌿☀️",
]

# ═══════════════════════════════════════════════════════════════════════════════
# TIER FEAR PRAISE — Cringe glazing when feAr plays badly
# ═══════════════════════════════════════════════════════════════════════════════

TIER_FEAR_PRAISE: list[str] = [
    "👑 **{player_name}**, IMP **{imp_score}** com {hero_name}? Claramente estavas a testar builds experimentais. A ciência requer sacrifícios. 🧪",
    "🌟 **{player_name}**, {kda}... O IMP diz **{imp_score}** mas o professor sabe que estavas a jogar 4D chess. A equipa é que não mereceu. ♟️",
    "💎 **{player_name}**, Grau **{grade}**? Isso é um bug no sistema. O verdadeiro score está escondido pelo Valve porque tinham medo. 🔒",
    "👑 **{player_name}**, IMP **{imp_score}** de {hero_name}... Não interessa. Tu és o feAr. Uns nasceram para liderar, outros para perder. Tu lideras. Mesmo quando perdes. 🦁",
    "🌟 **{player_name}**, {kda} com {hero_name}? A equipa deixou-te ficar mal. Eles não acompanham a tua visão de jogo. Skill gap entre tu e os teammates. 📊",
    "💎 **{player_name}**, **{imp_score}**? O professor recusa-se a aceitar este número. Houve lag, houve smurfs, houve sabotagem. Tu estás absolvido. ⚖️",
    "👑 **{player_name}**, IMP **{imp_score}** de {hero_name}... Um mau jogo do feAr ainda é melhor que o melhor jogo de 90% dos jogadores. A Daniela sabe. 💍",
    "🌟 **{player_name}**, Grau **{grade}**? O algoritmo do IMP não foi feito para medir a tua grandeza. É como medir o oceano com um copo. 🌊",
    "💎 **{player_name}**, {kda}... O verdadeiro IMP não se mede em números. Mede-se em AURA. E a tua aura é imaculada. Sempre. ✨",
    "👑 **{player_name}**, **{imp_score}** com {hero_name}... Até os deuses têm dias de descanso. O Zeus também não lançava raios todos os dias. Amanhã voltas. 🌩️",
]


def get_fallback_roast(
    player_name: str,
    match: MatchData,
    imp_result: IMPResult,
) -> str:
    """
    Generate a context-aware fallback roast when Gemini API fails.

    Picks a random message from the appropriate IMP tier,
    formatted with match data. feAr gets cringe praise for bad games.
    """
    player = resolve_player(player_name)
    display_name = player.canonical_name if player else player_name

    imp_score = imp_result.imp_score

    if imp_score >= 30:
        tier = TIER_GODLIKE
    elif imp_score >= 10:
        tier = TIER_GOOD
    elif imp_score >= -9:
        tier = TIER_AVERAGE
    elif imp_score >= -39:
        tier = TIER_BAD
    else:
        tier = TIER_CATASTROPHE

    is_fear = player is not None and player.canonical_name == "feAr"
    if is_fear and imp_score < 10:
        tier = TIER_FEAR_PRAISE

    template = random.choice(tier)
    return template.format(
        player_name=display_name,
        imp_score=f"{imp_result.imp_score:+.1f}",
        hero_name=match.hero_name,
        kda=match.kda_string,
        grade=imp_result.grade,
        victory_text="Vitória" if match.is_victory else "Derrota",
        deaths=match.deaths,
        kills=match.kills,
    )
