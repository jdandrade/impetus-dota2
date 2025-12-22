import discord
import requests
import logging
import asyncio
import random
from dotenv import load_dotenv
import os
import openai

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Load environment variables
load_dotenv()

# Securely load API keys
STRATZ_API_KEY = os.getenv("STRATZ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not STRATZ_API_KEY or not DISCORD_TOKEN:
    raise ValueError("Missing API tokens! Make sure STRATZ_API_KEY and DISCORD_TOKEN are set in .env")

if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key! Set OPENAI_API_KEY in .env")

# Stratz API Key (Replace with your actual API key)
# DISCORD_CHANNEL_ID = 1341417157061509153  # Replace with the channel where you want match announcements -> test
DISCORD_CHANNEL_ID = 1341725863535710218  # Replace with the channel where you want match announcements

# Store last known match IDs to prevent duplicate announcements
tracked_players = {
    # Replace with real SteamID64s of players to track
    "76561198349926313": None,  # fear
    "76561198031378148": None,  # rybur
    "76561198044301453": None,  # batatas
    "76561197986252478": None,  # gil
    "76561197970508852": None,  # states
    "76561197994301802": None,  # mauzaum
    "76561198014373442": None,  # hory
}

def convert_steam_id64_to_account_id(steam_id_64):
    """Converts SteamID64 to SteamAccountID"""
    account_id = int(steam_id_64) - 76561197960265728
    return account_id


async def track_dota_matches():
    """Periodically checks for new matches and announces them only when IMP Score is available."""
    await client.wait_until_ready()
    logging.info("Starting match tracking...")

    # Step 1: Fetch initial match IDs silently
    for steam_id_64 in tracked_players.keys():
        player_name, match_id, _, hero_name, won_match, game_mode, kills, deaths, assists, result = get_latest_match_imp(steam_id_64)
        if match_id:
            tracked_players[steam_id_64] = match_id  # Store the latest match ID without posting
            logging.info(f"Initialized tracking for {player_name} (SteamID: {steam_id_64}) with last match {match_id}")

    # Step 2: Start polling for new matches
    while not client.is_closed():
        for steam_id_64 in tracked_players.keys():
            player_name, match_id, imp_score, hero_name, won_match, game_mode, kills, deaths, assists, result = get_latest_match_imp(steam_id_64)

            # Check if we have a new match
            if match_id and match_id != tracked_players.get(steam_id_64):
                logging.info(f"New match detected for {player_name} (Match ID: {match_id}), waiting for IMP Score...")

                # ❗ Immediately lock this match as being processed
                tracked_players[steam_id_64] = match_id

                # Wait for IMP Score to be available
                max_wait_time = 900  # Max wait time in seconds
                wait_interval = 60  # Check every period
                elapsed_time = 0

                while imp_score is None and elapsed_time < max_wait_time:
                    await asyncio.sleep(wait_interval)
                    player_name, match_id, imp_score, hero_name, won_match, game_mode, kills, deaths, assists, result = get_latest_match_imp(steam_id_64)
                    elapsed_time += wait_interval
                    logging.info(
                        f"Retrying IMP fetch for {player_name} (Match ID: {match_id}), attempt at {elapsed_time}s")

                # Only announce if IMP Score is available
                if imp_score is not None:
                    #tracked_players[steam_id_64] = match_id  # Update last known match ID
                    channel = client.get_channel(DISCORD_CHANNEL_ID)

                    if channel:
                        # Generate the roast in real-time using GPT-4-turbo
                        roast_message = await generate_funny_message(
                            player_name, match_id, imp_score, hero_name, f"{kills}/{deaths}/{assists}", won_match,
                            game_mode, result
                        )
                        #message = generate_funny_message(player_name, match_id, imp_score)
                        kda_text = f"{kills}/{deaths}/{assists}"

                        await channel.send(
                            f"New Match Detected for **{player_name}!**\n"
                            f"Match ID: `{match_id}`\n"
                            f"Mode: `{game_mode}`\n"
                            f"Hero: `{hero_name}`\n"
                            f"KDA: `{kda_text}`\n"
                            f"isVictory: `{won_match}`\n"
                            f"Nota: `{imp_score}`\n"
                            f"{roast_message}\n"
                        )
                        logging.info(f"Announced match {match_id} for {player_name} with IMP Score {imp_score}")
                else:
                    logging.warning(
                        f"Skipped posting match {match_id} for {player_name} (IMP Score still missing after 5 minutes)")

        await asyncio.sleep(300)  # Check every 5 minutes


def get_latest_match_imp(steam_id_64):
    """Fetches the latest match IMP score for a given SteamID64"""
    steam_account_id = convert_steam_id64_to_account_id(steam_id_64)

    url = "https://api.stratz.com/graphql"
    headers = {
        "Authorization": f"Bearer {STRATZ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "STRATZ_API"  # ✅ Correct User-Agent as per Stratz API
    }

    query = {
        "query": f"""
        query {{
          player(steamAccountId: {steam_account_id}) {{
            steamAccount {{
                name
            }}
            matches(request: {{ take: 1 }}) {{
              id
              durationSeconds
              players {{
                steamAccountId
                imp
                hero {{
                  displayName
                }}
                isVictory
                kills
                deaths
                assists
                role
                award
              }}
              lobbyType
            }}
          }}
        }}
        """
    }

    try:
        response = requests.post(url, json=query, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # logging.info(f"API Response Data: {data}")  # Log full response for debugging

            # Check if player and matches exist
            if not data.get("data") or not data["data"].get("player"):
                logging.warning(f"No player data found for SteamAccountID: {steam_account_id}")
                return None, None, None, None, None, None, None, None, None, None

            player_name = data["data"]["player"]["steamAccount"]["name"]
            if not data["data"]["player"].get("matches"):
                logging.warning(f"No matches found for {player_name} ({steam_account_id})")
                return player_name, None, None, None, None, None, None, None, None, None

            match = data["data"]["player"]["matches"][0]
            match_id = match["id"]
            imp_scores = {player["steamAccountId"]: player["imp"] for player in match["players"]}
            hero_names = {player["steamAccountId"]: player["hero"]["displayName"] for player in match["players"]}
            match_results = {player["steamAccountId"]: player["isVictory"] for player in match["players"]}
            kills = {player["steamAccountId"]: player["kills"] for player in match["players"]}
            deaths = {player["steamAccountId"]: player["deaths"] for player in match["players"]}
            assists = {player["steamAccountId"]: player["assists"] for player in match["players"]}
            game_mode = match["lobbyType"]

            result = data

            return (
                player_name,
                match_id,
                imp_scores.get(int(steam_account_id), "N/A"),
                hero_names.get(int(steam_account_id), "Unknown"),
                match_results.get(int(steam_account_id), None),  # True if won, False if lost
                game_mode,
                kills.get(int(steam_account_id), 0),
                deaths.get(int(steam_account_id), 0),
                assists.get(int(steam_account_id), 0),
                result
            )

        else:
            logging.error(f"Error fetching data from Stratz: {response.status_code} - {response.text}")

    except Exception as e:
        logging.exception(f"Error fetching match data: {e}")

    return None, None, None, None, None, None, None, None, None


async def generate_funny_message(player_name, match_id, imp_score, hero_name, kda, is_victory, game_mode, result):
    """Generates a funny roast using GPT-4-turbo based on the player's performance."""
    system_prompt2 = """
    És o Stratz, o professor todo-poderoso de Dota 2. Avalias jogadores após cada jogo como se fosses o Snape do Dota: seco, irónico, decepcionado e cruel. Nunca ficas verdadeiramente impressionado.

    Estilo:
    - Sê direto, sarcástico e brutal. Nunca escrevas parágrafos. Usa 2 a 3 frases no máximo.
    - Escreve como um Twitch chatter tóxico: inglês misturado, memes, mas SEM parecer cringe ou forçado.
    - Foca-te em detalhes reais da performance: KDA miserável, escolha duvidosa de herói, jogo perdido com boa nota, jogo ganho com má nota, etc.
    - Insultos? Sim. Mas usa humor com contexto. Prefere frases como “isto nem no Herald funciona” a coisas genéricas como “retard”.
    - Se o IMP for negativo, assume que o jogador devia ser suspenso. Se for positivo, trata como milagre, mas sempre com sarcasmo.
    - Escreve sempre em Português de Portugal, mas usa inglês para memes e expressões conhecidas.
    - Usa o nome do herói no roast, como "Queen of Pain? Mais parece Queen of Throw."

    Nunca repitas mensagens. Nunca escrevas textos longos. Sê criativo e específico.
    """
    system_prompt= """
    You are Stratz, the all-knowing, all-seeing professor of Dota 2. Your job is to evaluate students (players) after each match.
    Your tone is dry, disappointed, and brutally sarcastic, like Professor Snape giving grades.

    Rules:
    - If IMP is negative, be passive-aggressive, act like you’ve given up on the player, and make them feel like they wasted everyone’s time.
    - If IMP is positive, act surprised, like you can’t believe they managed to be competent for once.
    - Write like a Twitch chatter: casual, short sentences, ironic, toxic and funny. 
    - You can use the worst kind of insults you know. 
    - You should use curse-words.
    - NEVER write long paragraphs. Keep it short and brutal.
    - Write in Portuguese of Portugal but you can use english expressions.
    - Keep using the hero name to make fun of the player. Saying things like "Queen of Pain? More like Queen of THROW!" is the type of start we want to get on the roast.
    """

    user_prompt = f"""
    Player: {player_name}
    Match ID: {match_id}
    Hero: {hero_name}
    IMP Score: {imp_score}
    KDA: {kda}
    Victory: {'Yes' if is_victory else 'No'}
    Game Mode: {game_mode}

    Faz um roast curto, sarcástico e contextualizado com base nesta performance de Dota 2. Máximo 2-3 linhas. Escreve como se estivesses a corrigir um teste miserável.
    """
    #Faz um roast curto e brutal para este jogador baseado na perfomance dele de dota 2. Máximo 2-3 linhas.


    try:
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt2},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200
        )

        roast_message = response.choices[0].message.content
        return roast_message.strip()

    except Exception as e:
        logging.error(f"Error fetching roast from OpenAI: {e}")
        return generate_local_funny_message(player_name, match_id, imp_score)


def generate_local_funny_message(player_name, match_id, imp_score):
    """Generates a funny message based on the IMP score"""
    if imp_score >= 30:
        compliments = [
            f"🎓 **{player_name}** acabou de receber **{imp_score}**! Isto sim é um aluno exemplar. Parabéns, génio! 📚",
            f"🔥 **{player_name}** destruiu tudo com um IMP de **{imp_score}**! O professor está impressionado. 🎖️",
            f"💯 **{player_name}** jogou como um verdadeiro mestre! **{imp_score}**. Agora podes dar aulas aos noobs. 🏆",
            f"🏆 **{player_name}**, IMP **{imp_score}**? És um mito, um deus, uma lenda... Mas ainda assim, MauZaum já fez melhor.",
            f"👑 **{player_name}**, IMP **{imp_score}**! Hoje és rei. Amanhã? Quem sabe."
        ]
        return random.choice(compliments)
    elif 10 <= imp_score < 30:
        good_messages = [
            f"🔥 **{player_name}**, IMP **{imp_score}**! Finalmente um jogo onde não envergonhas a tua equipa. 🚀",
            f"👑 **{player_name}**, IMP **{imp_score}**! Um jogo sólido, um jogador decente... mas ainda não és MauZaum.",
            f"📜 **{player_name}**, IMP **{imp_score}**. Bom esforço! Se treinares mais um pouco, talvez consigas um autógrafo do MauZaum.",
            f"🌟 **{player_name}**, IMP **{imp_score}**. És o Messi do Dota. Mas mesmo assim, MauZaum já fez melhor."
        ]
        return random.choice(good_messages)
    elif -9 <= imp_score < 10:
        average_jokes = [
            f"📖 **{player_name}**, foste avaliado com **{imp_score}**. Estás quase lá, mas ainda és um nabo. 😏",
            f"🤔 **{player_name}**, **{imp_score}**? Isso é um 50 na tua cabeça, mas um 5 para o professor. Trabalha mais! 📑",
            f"😬 **{player_name}**, **{imp_score}**... Não é mau, mas o professor esperava melhor. Onde anda o talento? 🎭",
            f"🥱 **{player_name}**, IMP **{imp_score}**... Estavas a jogar ou só a passear pelo mapa? Porque ninguém notou a tua presença. 😴",
            f"🔎 **{player_name}**, **{imp_score}**? Ok, jogaste. Mas fizeste alguma coisa útil? Pergunta séria.",
            f"🛠️ **{player_name}**, IMP **{imp_score}**. Se melhorares só um bocadinho, talvez a equipa pare de te odiar. Talvez.",
            f"📉 **{player_name}**, IMP **{imp_score}**. Nem é bom nem é mau. O problema é que ninguém se importa.",
            f"🤡 **{player_name}**, IMP **{imp_score}**. Isto não é Dota, isto foi um exercício de futilidade."
        ]
        return random.choice(average_jokes)
    elif -39 <= imp_score < -9:
        bad_messages = [
            f"📢 **{player_name}**, jogaste tão mal que o Valve Anti-Cheat já está a investigar se usaste um bot para jogar. **{imp_score}**? 😵‍💫",
            f"📦 **{player_name}**, com **{imp_score}**, podemos presumir que jogaste com o teclado desligado. Precisas de um reembolso? ⌨️",
            f"😵 **{player_name}**, o teu IMP foi **{imp_score}**? Isso é um insulto ao próprio jogo. Tens o microondas ligado enquanto jogas? 🍕",
            f"🚨 **{player_name}**, **{imp_score}**??? Mas tu jogaste Dota ou estiveste a fazer tricô? 🧶",
            f"💩 **{player_name}**, foste avaliado com um IMP de **{imp_score}**. Nem os bots jogam tão mal. 🤡",
            f"🤔 **{player_name}**, IMP **{imp_score}**? Isso é um 10 na tua cabeça, mas um -30 para o professor. Trabalha mais! 📑",
            f"🚀 **{player_name}**, IMP **{imp_score}**. O teu jogo foi tão mau que o Stratz achou que era um erro no código. 🤖",
            f"📜 **{player_name}**, IMP **{imp_score}**... És oficialmente um candidato ao prémio 'Como Jogar Mal Sem Ser Banido'. 🏅"
        ]
        return random.choice(bad_messages)

    else:
        roasts = [
            f"💩 **{player_name}**, foste avaliado com um miserável **{imp_score}**. Nem os bots jogam tão mal. 🤡",
            f"🚨 **{player_name}**, **{imp_score}**??? Mas tu jogaste Dota ou estiveste a fazer tricô? 🧶",
            f"📉 **{player_name}**, IMP **{imp_score}**... O professor recomenda que vás estudar mecânicas. O teu desempenho foi uma desgraça. 😵‍💫",
            f"🏚️ **{player_name}**, um sólido **{imp_score}**. Já pensaste em desistir do Dota? Talvez o Candy Crush seja mais o teu nível. 🍬",
            f"💩 **{player_name}**, IMP **{imp_score}**? Isto não é Dota, é um tutorial de como alimentar a equipa inimiga. 🤡",
            f"📉 **{player_name}**, parabéns! **{imp_score}**. Nem um bot no modo easy jogava pior. Estás a testar um novo estilo de jogo chamado ‘peso morto’? 🎒",
            f"🛑 **{player_name}**, com **{imp_score}**, oficialmente entraste para a lista de jogadores que deviam ser banidos por mau desempenho. 😬",
            f"🚨 **{player_name}**, IMP **{imp_score}**??? O professor já ligou para os teus pais, estás suspenso do Dota. 📞",
            f"🔥 **{player_name}**, IMP **{imp_score}**... és o motivo pelo qual os teus colegas de equipa estão a reconsiderar a vida. Boa sorte a fugir do report! 🏃‍♂️",
            f"⛔ **{player_name}**, IMP **{imp_score}**? Nem os Heralds aceitavam-te no clube deles. Tens de pagar suborno ao MMR para subir. 💰",
            f"⚰️ **{player_name}**, IMP **{imp_score}**... Acabaste de dar uma aula prática de como perder um jogo sozinho. 👏👏👏",
            f"😵 **{player_name}**, o teu IMP foi **{imp_score}**? Isso é um insulto ao próprio jogo. Tens o microondas ligado enquanto jogas? 🍕",
            f"📦 **{player_name}**, IMP **{imp_score}**... vais precisar de um reembolso pelo teu teclado porque claramente não o usaste. ⌨️",
            f"🏚️ **{player_name}**, um IMP de **{imp_score}**? Vais precisar de terapia depois disto. Considera trocar Dota por um jogo mais fácil, tipo Tetris. 🎮",
            f"💀 **{player_name}**, IMP **{imp_score}**? CATASTROFE. Tu jogaste Dota ou fizeste um speedrun de perder o mais rápido possível?",
            f"🤡 **{player_name}**, com **{imp_score}**, oficialmente levaste o prémio 'BIG RETARD THE PLEYERR'. Mete um vídeo no YouTube, esta obra-prima precisa de ser estudada. 📹",
            f"📉 **{player_name}**, **{imp_score}**... Mas tu estás a jogar com um monitor ligado? Porque o resultado parece alguém a jogar Dota de olhos vendados. 🎮",
            f"🚑 **{player_name}**, o teu IMP é **{imp_score}** e a tua equipa ainda está em recuperação intensiva. 🚨",
            f"🏚️ **{player_name}**, IMP **{imp_score}**? Já consideraste a reforma antecipada do Dota? Candy Crush pode ser mais o teu nível. 🍬",
            f"🛑 **{player_name}**, **{imp_score}**??!! YES RELAX BECAUSE RETARRRRRD?",
            f"⚰️ **{player_name}**, IMP **{imp_score}**... Os Heralds disseram que mesmo para eles tu és um pouco mau. 😬",
            f"🔥 **{player_name}**, parabéns, com **{imp_score}** conseguiste dar a vitória à outra equipa. Tens contrato com eles ou foi de graça? Paid Actor?",
            f"📞 **{player_name}**, Stratz está a ligar... quer saber se foi um bug ou se jogaste mesmo assim."
        ]
        return random.choice(roasts)


@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    await client.loop.create_task(track_dota_matches())  # Start background task for match tracking


client.run(DISCORD_TOKEN)
