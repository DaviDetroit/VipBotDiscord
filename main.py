from calendar import c
import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import asyncio
import json
import random
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, timedelta, timezone, time  # <- corrigido aqui
from calendar import monthrange
import yt_dlp
from discord import FFmpegPCMAudio
import time as time_module
from discord.ui import Button, View
import pytz
import requests
import logging
import aiohttp
load_dotenv()

logging.basicConfig(
    level = logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S' 
)



def conectar(database_name: str):
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=database_name
    )

def conectar_vips():
    return conectar(os.getenv("DB_VIPS"))



def conectar_futebol():
    return conectar(os.getenv("DB_FUTEBOL"))

def salvar_jogo_banco(time1, time2, data, horario, canal_id):
    conexao = conectar_futebol()
    cursor = conexao.cursor()

    sql = """
    INSERT INTO jogos (home, away, data, horario, canal_id)
    VALUES (%s, %s, %s, %s, %s)
    """

    cursor.execute(sql, (time1, time2, data, horario, canal_id))
    conexao.commit()
    cursor.close()
    conexao.close()

def buscar_jogos_pendentes():
    conexao = conectar_futebol()
    cursor = conexao.cursor(dictionary=True)
    agora = datetime.now().date()
    sql = "SELECT * FROM jogos WHERE data >= %s"
    cursor.execute(sql, (agora,))
    jogos = cursor.fetchall()
    cursor.close()
    conexao.close()
    return jogos




def adicionar_pontos_db(user_id: int, pontos: int, nome_discord: str = None):
    con = conectar_futebol()
    cur = con.cursor()
    if nome_discord is None:
        u = bot.get_user(int(user_id))
        nome_discord = f"{u.name}#{u.discriminator}" if u else str(user_id)
    cur.execute(
        """
        INSERT INTO pontuacoes (user_id, nome_discord, pontos)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE pontos = pontos + VALUES(pontos), nome_discord = VALUES(nome_discord)
        """,
        (user_id, nome_discord, pontos)
    )
    con.commit()
    con.close()

# Pega os pontos atuais do usuário
def pegar_pontos(user_id: int):
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute("SELECT pontos FROM pontuacoes WHERE user_id = %s", (user_id,))
    resultado = cur.fetchone()
    con.close()
    return resultado[0] if resultado else 0

def pegar_torcedores(time):
    conn = conectar_futebol()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT user_id FROM times_usuarios WHERE time_normalizado = %s", (time,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return [row["user_id"] for row in rows]






TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.reactions = True
intents.voice_states = True
CANAL_AVISO_ID=1387107714525827152

bot = commands.Bot(command_prefix="!", intents=intents)

mensagens_bom_dia = [
    "🌞 Bom dia, pessoal! Vamos começar o dia com energia positiva!",
    "☕ Bom dia! Já tomaram aquele cafezinho?",
    "💪 Bom dia, guerreiros! Que hoje seja um dia produtivo!",
    "✨ Bom dia! Que seu dia seja iluminado!",
    "🌻 Bom dia! Bora conquistar nossos objetivos hoje!",
    "🌅 Bom dia! Que hoje seja melhor que ontem!",
    "🎶 Bom dia! Que a alegria seja sua trilha sonora hoje!",
    "<:JinxFU:1390638686877777920> Bom dia é o caralho, vai todo mundo se fuder!",
    "Já pensou que as vezes o seu dia tá ruim, e pode piorar mais ainda? Quer dizer.. Bom Dia!",
    "🍀 Bom dia! Que a sorte esteja ao seu lado!",
    "😄 Bom dia! Um sorriso já é metade do caminho para um ótimo dia.",
    "📈 Bom dia! Hoje é dia de progresso!",
    "🌈 Bom dia! Que sua manhã seja colorida de coisas boas.",
    "🥐 Bom dia! Já tomou café da manhã? Energia é tudo!",
    "⚡ Bom dia! Que sua motivação seja sua força!",
    "🎯 Bom dia! Foco e disciplina levam longe.",
    "🌞 Bom diaaa, meus consagrados! Que o dia de vocês seja tão iluminado quanto um PIX caindo na conta 💸. E falando em PIX... quem quiser começar o dia abençoado, é só mandar aquele agrado pro Orfeuson@hotmail.com 😏☕",
    "🐓 Cocoricóôôôôô! Bom diaaa! (leia com voz de galo, por favor) 🐓",
    "🌊 Bom dia! Deixe as preocupações fluírem e siga leve.",
    "❤️ Bom dia! Desejo a todos muito amor hoje.",
    "💤 Bom dia! Quem acordou cedo hoje merece um troféu... 🏆",
    "🌞 Bom dia, família! Que hoje seja leve, produtivo e cheio de vitórias. E se quiser começar o dia ajudando um guerreiro, o PIX tá aí: **Orfeuson@hotmail.com** 😎",
    "☕ Bom diaaa! Que sua energia seja forte como café sem açúcar. Caso falte o café… você já sabe onde mandar: **PIX: Orfeuson@hotmail.com** 😂",
    "✨ Bom dia! Hoje é dia de vencer, sorrir e prosperar. Se a preguiça bater, lembra que um PIX anima qualquer um: **Orfeuson@hotmail.com** 💸",
    "😅 Bom dia, pessoal! O sol nasceu e os boletos também… quem quiser dar uma força: **PIX do salvador: Orfeuson@hotmail.com**",
    "🚀 Bom dia! Acorde, levante e corra atrás dos seus sonhos. Mas se o sonho for pagar as contas, manda um PIX: **Orfeuson@hotmail.com** 🤣",
    "🌻 Bom diaaa! Que hoje seja tão bom quanto receber um PIX inesperado… aliás, falando nisso: **Orfeuson@hotmail.com** 🙌",
    "🔥 Bom dia, guerreiros! Bora encarar mais um dia com coragem e fé. Quem quiser turbinar a sorte: **PIX: Orfeuson@hotmail.com** 💪",
    "😂 Bom dia! Lembre-se: quem acorda cedo é recompensado… e quem manda PIX pro amigo é abençoado! **Orfeuson@hotmail.com**",
    "📈 Bom dia! Que sua vida suba igual gráfico da bolsa em alta. Pra ajudar no investimento: **PIX: Orfeuson@hotmail.com** 💹",
    "🎉 Bom diaaa! Que hoje você receba notícias boas, abraços sinceros… e, quem sabe, até um PIX. Pra não perder o costume: **Orfeuson@hotmail.com**",
    "🧠 Você sabia? O cérebro humano gera eletricidade suficiente para acender uma lâmpada fraca!",
    "🌍 A Terra não é uma esfera perfeita — ela é levemente achatada nos polos por causa da rotação.",
    "🐙 O polvo tem **três corações** e o sangue dele é azul por causa do cobre na hemoglobina.",
    "🚀 A Estação Espacial Internacional viaja a mais de **27.000 km/h** e dá uma volta na Terra a cada 90 minutos.",
    "🐝 As abelhas conseguem reconhecer rostos humanos, algo raro no reino animal.",
    "🌌 Existem mais estrelas no universo do que grãos de areia em todas as praias da Terra.",
    "🔥 O Sol é tão grande que caberiam **1,3 milhão de Terras** dentro dele.",
    "🐧 O pinguim-imperador pode ficar até **20 minutos** debaixo d’água sem respirar.",
    "🎵 A música pode alterar o ritmo dos batimentos cardíacos e até ajudar no controle da ansiedade.",
    "💡 Thomas Edison não inventou a lâmpada — ele apenas criou a versão mais prática e comercial.",
    "🤖 **Curiosidade:** O bot **ChicoBento** não é só um ajudante de cargos e VIPs — ele também pode te dar dicas rápidas sobre o servidor! Basta ir no canal 🆘┃ajuda.",
    "🏷️ **Curiosidade:** Usar o **ChicoBento** para escolher cores de cargos ou funções VIP é uma forma prática de personalizar seu perfil no servidor sem depender de admins.",
    "⚡ **Curiosidade:** Bots como o **ChicoBento** conseguem processar comandos quase instantaneamente, permitindo que você gerencie funções do servidor com rapidez e segurança.",
    "🎨 **Curiosidade:** Além de ajudar com VIPs e boosters, o **ChicoBento** facilita a personalização estética, como cores e nomes de cargos, dando um toque único aos membros.",
    "🆘 **Curiosidade:** Para qualquer dúvida sobre funções do servidor, você pode chamar o **ChicoBento** no canal 🆘┃ajuda, economizando tempo e evitando confusão com outros membros.",
    "🤩 **Curiosidade:** Servidores que usam bots de gerenciamento como o **ChicoBento** geralmente têm comunidades mais organizadas, porque automatizam tarefas repetitivas e mantêm tudo funcionando de forma fluida."
]


mensagens_boa_tarde = [
    "Opa, boa tarde! Fala aí 😎",
    "Boa tarde! E aí, como tá a vida?",
    "Boa tarde! Cheguei, sentiu minha falta? 😏",
    "Boa tarde! Suave por aí?",
    "Boa tarde! E aí, o que manda?",
    "Boa tarde! Tudo certo ou só quase?",
    "Boa tarde! Bora fazer essa tarde render?",
    "Boa tarde! E aí, firmeza?",
    "Boa tarde! Passando pra lembrar que você é brabo 😌",
    "Boa tarde! Tarde boa é tarde com você online 😂",
    "Boa tarde! E aí, tá de boas ou no caos?",
    "Boa tarde! Fala comigo, não me ignora 👀",
    "Boa tarde! Chega mais, bora trocar ideia!",
    "Boa tarde! Tá on? Bora movimentar isso aqui 😎",
    "Boa tarde! Força aí, que o dia ainda não acabou 💪",
    "Boa tarde! Tô só observando a galera… 👀",
    "Boa tarde! Hoje tá com cara de dia bom, hein?",
    "Boa tarde! Só passando pra deixar aquele salve ✌️",
    "Boa tarde! E aí, aprontando o quê?",
    "Boa tarde! Se anima aí que a tarde tá só começando!"
]
@bot.event
async def on_ready():
    logging.info(f"Bot conectado como {bot.user}")
    jogos_pendentes = buscar_jogos_pendentes()

    # ===== Evita iniciar 2 vezes =====
    if not verificar_posts.is_running():
        verificar_posts.start()

    if not ranking_mensal.is_running():
        ranking_mensal.start()

    if not verificar_vips.is_running():
        verificar_vips.start()

    if not verificar_vips_expirados.is_running():
        verificar_vips_expirados.start()

    if not sincronizar_reacoes.is_running():
        sincronizar_reacoes.start()


    

    # ===== Verificador de gols =====
    if await jogos_ao_vivo():
        if not verificar_gols.is_running():
            verificar_gols.start()
            logging.info("✅ Verificador de gols iniciado!")
    else:
        logging.info("⚠️ Nenhum jogo ao vivo no momento.")

    # ===== BOM DIA =====
    agora = datetime.now(timezone.utc) - timedelta(hours=3)
    hora = agora.hour
    dia_semana = agora.weekday()
    semana_atual = agora.isocalendar()[1]
    
    if hora < 12:
        canal = bot.get_channel(1380564680552091789)
        if canal:
            mensagem = random.choice(mensagens_bom_dia)
            await canal.send(mensagem)
    if 12 <= hora < 18:
        canal = bot.get_channel(1380564680552091789)
        if canal:
            mensagem = random.choice(mensagens_boa_tarde)
            await canal.send(mensagem)

    # ===== TOP ATIVOS DOMINGO =====
    if dia_semana == 6:  # domingo
        canal = bot.get_channel(CANAL_TOP_ID)
        if canal:
            await enviar_top_ativos_semanal_once(semana_atual, canal)

    conn = conectar_vips()
    c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS moderador_alertas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                denunciante_id BIGINT,
                moderador_id BIGINT,
                data_denuncia TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            c.execute("ALTER TABLE moderador_alertas ADD COLUMN denunciante_id BIGINT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE moderador_alertas ADD COLUMN moderador_id BIGINT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE moderador_alertas ADD COLUMN data_denuncia TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception:
            pass

        sql = "SELECT moderador_id, COUNT(DISTINCT denunciante_id) as total FROM moderador_alertas GROUP BY moderador_id HAVING total >= 3"
        c.execute(sql)
        rows = c.fetchall()
        for moderador_id, total in rows:
            await enviar_alerta(moderador_id, total)
    except Exception as e:
        logging.error(f"Falha ao reconstruir contadores/alertas: {e}")
    finally:
        try:
            c.close()
            conn.close()
        except Exception:
            pass
    try:
        if not limpar_canal_tickets.is_running():
            limpar_canal_tickets.start()
    except Exception as e:
        logging.error(f"Falha ao iniciar limpeza de canal de tickets: {e}")

@tasks.loop(minutes=3)
async def limpar_canal_tickets():
    channel = bot.get_channel(ID_CANAL_TICKET)
    if not channel:
        return
    try:
        def check(m):
            return (TICKET_EMBED_MESSAGE_ID is None) or (m.id != TICKET_EMBED_MESSAGE_ID)
        await channel.purge(check=check, limit=100)
    except Exception:
        pass


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    message = reaction.message
    emoji = str(reaction.emoji)

    # ======================================================
    # 1) SISTEMA DE POSTS (👍 / 👎)
    # ======================================================
    if message.channel.id == 1386805780140920954:
        tipo = None
        if emoji == "👍":
            tipo = "up"
        elif emoji == "👎":
            tipo = "down"

        if tipo:
            conexao = conectar_vips()
            cursor = conexao.cursor()

            try:
                cursor.execute(
                    "INSERT INTO reacoes (message_id, user_id, tipo) VALUES (%s, %s, %s)",
                    (message.id, user.id, tipo)
                )
                conexao.commit()
            except:
                pass  # já votou

            cursor.execute(
                "SELECT COUNT(*) FROM reacoes WHERE message_id=%s AND tipo=%s",
                (message.id, tipo)
            )
            count = cursor.fetchone()[0]

            if tipo == "up":
                cursor.execute("UPDATE posts SET upvotes=%s WHERE id=%s", (count, message.id))
            else:
                cursor.execute("UPDATE posts SET downvotes=%s WHERE id=%s", (count, message.id))

            conexao.commit()
            cursor.close()
            conexao.close()
            return  # impede que passe para apostas

    # ======================================================
    # 2) SISTEMA DE APOSTAS
    # ======================================================

    # Verificar se a mensagem é de um jogo
    con = conectar_futebol()
    cur = con.cursor(dictionary=True)

    cur.execute("""
        SELECT fixture_id, bet_deadline, betting_open, home, away 
        FROM jogos WHERE message_id = %s
    """, (message.id,))
    jogo = cur.fetchone()
    con.close()

    # Não é jogo → sai
    if not jogo:
        return

    fixture_id = jogo["fixture_id"]
    bet_deadline = jogo["bet_deadline"]
    betting_open = jogo["betting_open"]
    home = jogo["home"]
    away = jogo["away"]

    # --- Mapeia emojis ---
    palpite = None

    nome_casa = MAPEAMENTO_TIMES.get(home.lower(), home.lower()).replace(" ", "_")
    emoji_casa = EMOJI_TIMES.get(nome_casa, "⚽")

    nome_fora = MAPEAMENTO_TIMES.get(away.lower(), away.lower()).replace(" ", "_")
    emoji_fora = EMOJI_TIMES.get(nome_fora, "⚽")

    emoji_empate = EMOJI_EMPATE

    if emoji == emoji_casa:
        palpite = "home"
    elif emoji == emoji_fora:
        palpite = "away"
    elif emoji == emoji_empate:
        palpite = "draw"
    else:
        return  # não é emoji de aposta

    # --- Verifica prazo (baseado na hora da mensagem) ---
    agora = datetime.now(timezone.utc)
    deadline_msg = message.created_at.replace(tzinfo=timezone.utc) + timedelta(minutes=10)

    if betting_open == 0 or agora > deadline_msg:
        if betting_open == 1:
            con = conectar_futebol()
            cur = con.cursor()
            cur.execute("UPDATE jogos SET betting_open = 0 WHERE fixture_id=%s", (fixture_id,))
            con.commit()
            con.close()

        try:
            await user.send("⏰ Já se passaram os 10 minutos para apostar nesta partida.")
        except:
            pass
        try:
            await reaction.remove(user)
        except:
            pass
        return

    # --- Registra aposta ---
    sucesso = registrar_aposta_db(user.id, fixture_id, palpite)

    if not sucesso:
        try:
            await reaction.remove(user)
        except:
            pass
        return

    # --- DM de confirmação ---
    try:
        if palpite == "home":
            time_escolhido = home
        elif palpite == "away":
            time_escolhido = away
        else:
            time_escolhido = "draw"
        await user.send(
            f"🏟️ Partida: **{home} x {away}**\n"
            f"<:Jinx:1390379001515872369> Palpite escolhido: **{time_escolhido}**\n"
            "🍀 Boa sorte!"
        )
    except:
        pass





@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.channel.id != 1386805780140920954:
        return

    tipo = None
    if str(reaction.emoji) == "👍":
        tipo = "up"
    elif str(reaction.emoji) == "👎":
        tipo = "down"
    else:
        return

    conexao = conectar_vips()
    cursor = conexao.cursor()
    # Deleta 
    cursor.execute(
        "DELETE FROM reacoes WHERE message_id=%s AND user_id=%s AND tipo=%s",
        (reaction.message.id, user.id, tipo)
    )
    conexao.commit()
    
    # Conta as reações

    cursor.execute(
        "SELECT COUNT(*) FROM reacoes WHERE message_id=%s AND tipo=%s",
        (reaction.message.id, tipo)
    )
    count = cursor.fetchone()[0]

    if tipo == "up":
        cursor.execute("UPDATE posts SET upvotes=%s WHERE id=%s", (count, reaction.message.id))
    else:
        cursor.execute("UPDATE posts SET downvotes=%s WHERE id=%s", (count, reaction.message.id))

    conexao.commit()
    cursor.close()


@tasks.loop(hours=24)  # roda uma vez por dia
async def verificar_posts():
    conexao = conectar_vips()
    cursor = conexao.cursor(dictionary=True)

    # pega posts mais antigos que 7 dias e ainda não removidos
    cursor.execute("""
        SELECT id, channel_id, upvotes, downvotes, timestamp 
        FROM posts 
        WHERE removed=FALSE AND timestamp <= (NOW() - INTERVAL 7 DAY)
    """)
    posts = cursor.fetchall()

    for post in posts:
        if post["downvotes"] > post["upvotes"]:
            try:
                channel = bot.get_channel(post["channel_id"])
                msg = await channel.fetch_message(post["id"])
                await msg.delete()

                cursor.execute("UPDATE posts SET removed=TRUE WHERE id=%s", (post["id"],))
                conexao.commit()
                logging.info(f"Mensagem {post['id']} excluída por votos negativos.")
            except Exception as e:
                logging.error(f"Erro ao excluir mensagem {post['id']}: {e}")

    cursor.close()
    conexao.close()


@tasks.loop(minutes=10)  # roda a cada 10 minutos
async def sincronizar_reacoes():
    canal = bot.get_channel(1386805780140920954)
    if not canal:
        return

    conexao = conectar_vips()
    cursor = conexao.cursor()

    async for mensagem in canal.history(limit=100):  # pode ajustar o limite
        # Pega reações atuais
        upvotes = 0
        downvotes = 0
        for reaction in mensagem.reactions:
            if str(reaction.emoji) == "👍":
                upvotes = reaction.count - 1 if mensagem.author.bot else reaction.count
            elif str(reaction.emoji) == "👎":
                downvotes = reaction.count - 1 if mensagem.author.bot else reaction.count

        # Atualiza o banco
        cursor.execute(
            "INSERT IGNORE INTO posts (id, user_id, channel_id, upvotes, downvotes, removed, timestamp) VALUES (%s, %s, %s, %s, %s, FALSE, NOW())",
            (mensagem.id, mensagem.author.id, canal.id, upvotes, downvotes)
        )
        cursor.execute(
            "UPDATE posts SET upvotes=%s, downvotes=%s WHERE id=%s",
            (upvotes, downvotes, mensagem.id)
        )

    conexao.commit()
    cursor.close()
    conexao.close()
@tasks.loop(hours=24)
async def ranking_mensal():
    agora = datetime.now()
    
    # define o mês anterior
    if agora.month == 1:
        mes = 12
        ano = agora.year - 1
    else:
        mes = agora.month - 1
        ano = agora.year
    
    primeiro_dia = datetime(ano, mes, 1)
    ultimo_dia = datetime(ano, mes, monthrange(ano, mes)[1], 23, 59, 59)

    conexao = conectar_vips()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, id, upvotes
        FROM posts
        WHERE removed=FALSE
          AND timestamp BETWEEN %s AND %s
        ORDER BY upvotes DESC
        LIMIT 1
    """, (primeiro_dia, ultimo_dia))

    top_post = cursor.fetchone()

    cursor.close()
    conexao.close()

    if top_post:
        user = await bot.fetch_user(top_post["user_id"])
        channel = bot.get_channel(1386805780140920954)  # canal mural
        await channel.send(
            f"<a:489897catfistbump:1414720257720848534> "
            f"Usuário com o post mais curtido do mês {mes}/{ano}: {user.mention}! "
            f"<a:a36fc0b021624a25b50e1bd237cd024c:1411136694844915902>"
        )


@bot.command()
async def enviar_mensagem(ctx, *, mensagem):
    canal_id = 1380564680552091789
    canal_enviar = bot.get_channel(canal_id)
    if canal_enviar:
        await canal_enviar.send(mensagem)
        await ctx.send(f"✅ Mensagem enviada para {canal_enviar.mention}!")
    else:
        await ctx.send("Não encontrei o canal correto")


    














@bot.command()
@commands.has_permissions(administrator=True)
async def vip_mensagem(ctx):
    global vip_message_id
    import json

    # Embed principal
    embed = discord.Embed(
        title="<:Jinx:1390379001515872369> Bem-vindo ao Sistema VIP e Boost!",
        description=(
            "<:discotoolsxyzicon_6:1444750406763679764> | <:discotoolsxyzicon_5:1444750402061991956> **SEJA VIP OU BOOSTER!**\n\n"
            "<:240586sly:1445364127987142656> O VIP custa **R$5,00 mensal** e oferece os mesmos benefícios do Booster.\n\n"
            "<:Stars:1387223064227348591> **Benefícios:**\n"
            "<:jinxedsignal:1387222975161434246> Cargo personalizado\n"
            "<:jinxedsignal:1387222975161434246> Permissão para streamar em qualquer canal\n"
            "<:jinxedsignal:1387222975161434246> Categoria exclusiva com o cargo VIP ou Booster\n"
            "<:jinxedsignal:1387222975161434246> Acesso à call premium\n"
            "<:jinxedsignal:1387222975161434246> Amizades verdadeiras\n"
            "<:jinxedsignal:1387222975161434246> Jesus vai te amar\n"
            "<:jinxedsignal:1387222975161434246> Vai estar me ajudando\n"
            "<:jinxedsignal:1387222975161434246> Novos benefícios futuramente! <:JinxKissu:1408843869784772749>\n\n"
            "<a:heart_glitch:1408844002647740437> Clique em <:discotoolsxyzicon_6:1444750406763679764> abaixo para solicitar o VIP.\n"
            "<:notification:1390647107316355165> Após o clique, um administrador será notificado para continuar o processo.\n"
            "_Acesso válido por 30 dias._ 🗓️"
        ),
        color=discord.Color(0xfb3060)
    )

    # Banner maior no topo
    embed.set_image(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749215669424218/JINXEDd1.png?ex=692dd70f&is=692c858f&hm=8fdcc6669a7e1435ff7e1f4ab8617848326eab3e094f3d0b01fc970d59f7fa9c&")

    # Thumbnail à direita
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749579605119148/discotools-xyz-icon.png?ex=692dd765&is=692c85e5&hm=a631e3a40d1f2fb68a0ed37614387aaf3946950d31e4aa91fcf35005f568717a&")

    # Mensagem menor embaixo
    embed.set_footer(text="VIP exclusivo para os jogadores mais dedicados!")

    # Envia a mensagem e adiciona reação
    mensagem = await ctx.send(embed=embed)
    emoji_coroa = discord.utils.get(ctx.guild.emojis, id=1444750406763679764)
    if emoji_coroa:
        await mensagem.add_reaction(emoji_coroa)
    else:
        await mensagem.add_reaction("<:discotoolsxyzicon_6:1444750406763679764>")

    # Salva o ID da mensagem para persistência após restart
    vip_message_id = mensagem.id
    with open("vip.json", "w") as f:
        json.dump({"vip_message_id": vip_message_id}, f)

vip_message_id = None

# Dicionário que guarda apostas ativas
# Estrutura:
# apostas_ativas[message_id] = {
#     "fixture_id": 123,
#     "home": "galo",
#     "away": "flamengo",
#     "emoji_home": "<:Galo:123>",
#     "emoji_away": "<:Flamengo:123>",
#     "emoji_empate": "⚪",
#     "tempo_fechamento": datetime,
# }
apostas_ativas = {}


@bot.event
async def on_raw_reaction_add(payload):
    global vip_message_id, apostas_ativas

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    # ============================
    # 1) ----- SISTEMA VIP -------
    # ============================
    if vip_message_id is None:
        try:
            import json
            with open("vip.json", "r") as f:
                data = json.load(f)
                vip_message_id = data.get("vip_message_id")
        except:
            pass  # Sem problema, pode ficar vazio

    if payload.message_id == vip_message_id and getattr(payload.emoji, "id", None) == 1444750406763679764:
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        dono = await bot.fetch_user(614476239683584004)

        try:
            await dono.send(f"<:discotoolsxyzicon_6:1444750406763679764> {member.name}#{member.discriminator} quer ser VIP!")
        except:
            canal_fallback = discord.utils.get(guild.text_channels, name="⚠️┃avisos")
            if canal_fallback:
                await canal_fallback.send(f"<:discotoolsxyzicon_6:1444750406763679764> {member.mention} quer ser VIP!")



    # ========================================
    # 2) ----- SISTEMA DE APOSTAS POR REAÇÃO --
    # ========================================
    if payload.message_id in apostas_ativas:

        aposta = apostas_ativas[payload.message_id]
        emoji = str(payload.emoji)
        user_id = payload.user_id

        # Se passou do tempo → ignora
        from datetime import datetime
        if datetime.utcnow() > aposta["tempo_fechamento"]:
            try:
                user = await bot.fetch_user(user_id)
                await user.send("⏰ Já se passaram os 10 minutos para apostar nesta partida.")
            except:
                pass
            return

        escolha = None

        # Checar qual emoji o usuário clicou
        if emoji == aposta["emoji_home"]:
            escolha = aposta["home"]
        elif emoji == aposta["emoji_away"]:
            escolha = aposta["away"]
        elif emoji == aposta["emoji_empate"]:
            escolha = "draw"
        else:
            return  # Reação irrelevante

        # -------- SALVAR NO MYSQL --------
        try:
            con = conectar_futebol()
            cursor = con.cursor()

            # 1) Verifica modo clown
            cursor.execute("SELECT ativo FROM clown_bet WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()

            modo_clown = 1 if (row and row[0] == 1) else 0

            # Se usou o clown, consome
            if modo_clown == 1:
                cursor.execute("UPDATE clown_bet SET ativo = 0 WHERE user_id = %s", (user_id,))

            # 2) Salva aposta com modo_clown
            sql = """
                INSERT INTO apostas (user_id, fixture_id, palpite, modo_clown)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    palpite = VALUES(palpite),
                    modo_clown = VALUES(modo_clown)
            """

            cursor.execute(sql, (user_id, aposta["fixture_id"], escolha, modo_clown))
            con.commit()

            cursor.close()
            con.close()

        except Exception as e:
            logging.error("Erro ao salvar aposta:", e)
            return

        # Envia confirmação no DM
        user = await bot.fetch_user(user_id)
        try:
            await user.send(f"⚽ Sua aposta foi registrada: **{escolha.title()}**")
        except:
            pass




@bot.command()
@commands.has_permissions(administrator=True)
async def dar_vip(ctx, membro: discord.Member, duracao: str):
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    if not cargo_vip:
        await ctx.send("❌ Cargo 'Jinxed Vip' não encontrado.")
        return

    duracao = duracao.strip().lower()
    if len(duracao) < 2 or not duracao[:-1].isdigit() or duracao[-1] not in {"d", "m", "y"}:
        await ctx.send("❌ Formato inválido! Use 30d, 2m ou 1y.")
        return

    valor = int(duracao[:-1])
    unidade = duracao[-1]
    if unidade == "d":
        delta = timedelta(days=valor)
    elif unidade == "m":
        delta = timedelta(days=30 * valor)
    else:
        delta = timedelta(days=365 * valor)

    if cargo_vip in membro.roles:
        await ctx.send(f"❌ {membro.display_name} já possui o cargo VIP.")
        return

    await membro.add_roles(cargo_vip, reason="Concessão de VIP")

    try:
        conexao = conectar_vips()
        cursor = conexao.cursor()

        data_inicio = datetime.now(timezone.utc)
        data_fim = data_inicio + delta

        cursor.execute(
            """
            INSERT INTO vips (id, nome_discord, data_inicio, data_fim)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nome_discord = VALUES(nome_discord),
                data_inicio = VALUES(data_inicio),
                data_fim = VALUES(data_fim)
            """,
            (membro.id, f"{membro.name}#{membro.discriminator}", data_inicio, data_fim)
        )
        conexao.commit()
        cursor.close()
        conexao.close()

        try:
            await membro.send(f"<:Jinx_Watching:1390380695712694282> Você recebeu VIP por {duracao}!")
        except:
            pass
        await ctx.send(f"<:Jinx_Watching:1390380695712694282> {membro.display_name} agora é VIP por {duracao}.")
    except Exception as e:
        await ctx.send("❌ Erro ao salvar VIP no banco de dados.")
        logging.error(f"Erro dar_vip: {e}")

    



@bot.command()
@commands.has_permissions(administrator=True)
async def remover_vip(ctx, membro: discord.Member):
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    if not cargo_vip:
        await ctx.send("❌ Cargo 'Jinxed Vip' não encontrado.")
        return

    if cargo_vip not in membro.roles:
        await ctx.send(f"<:jinxedola:1390368939380445225> {membro.display_name} não possui o cargo VIP.")
        return

    try:
        await membro.remove_roles(cargo_vip)

        conexao = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME_VIPS")
        )
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM vips WHERE id = %s", (membro.id,))
        conexao.commit()
        cursor.close()
        conexao.close()

        await ctx.send(f"<:Jinx_Watching:1390380695712694282> Cargo VIP removido de {membro.mention}.")

    except Exception as e:
        await ctx.send("❌ Erro ao remover VIP do banco de dados.")
        logging.error(f"Erro ao remover VIP: {e}")





@tasks.loop(hours=12)
async def verificar_vips():
    agora = datetime.now()

    try:
        conexao = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_VIPS")
        )

        with conexao.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, data_fim, avisado7d FROM vips")
            vips = cursor.fetchall()

            for vip in vips:
                user_id = vip['id']
                data_fim = vip['data_fim']
                avisado7d = vip['avisado7d']

                dias_restantes = (data_fim - agora).days
                user = await bot.fetch_user(user_id)

                if 0 < dias_restantes <= 7 and not avisado7d:
                    try:
                        channel = bot.get_channel(1387107714525827152)
                        await channel.send(f"O VIP de <@{user_id}> está acabando!")
                        await user.send("📢 Seu VIP está acabando! Faltam 7 dias!")
                        cursor.execute("UPDATE vips SET avisado7d = 1 WHERE id = %s", (user_id,))
                        conexao.commit()
                    except discord.Forbidden:
                        pass

                if dias_restantes <= 0:
                    for guild in bot.guilds:
                        membro = guild.get_member(user_id)
                        if membro:
                            cargo_vip = discord.utils.get(guild.roles, name="Jinxed Vip")
                            if cargo_vip in membro.roles:
                                await membro.remove_roles(cargo_vip)

                    cursor.execute("DELETE FROM vips WHERE id = %s", (user_id,))
                    conexao.commit()

    except Exception as e:
        logging.error(f"Erro ao verificar VIPs: {e}")

    finally:
        if conexao.is_connected():
            conexao.close()





CANAL_TOP_ID = 1380564680552091789
CARGO_IGNORADO = 1380564679243333852
COOLDOWN = 40
ultimo_reagir = 0  
BOT_MUSICA_PROIBIDO = 411916947773587456
CANAIS_MUSICAS_LIBERADO = [1380564681093156940,1380564681093156941]
BOT_REACTION = [
    "Achando que eu vou falar com você docinho?",
    "Sabia que mencionar bot e nada são a mesma coisa? HAHAHAAHHA",
    "Imagina ser tão feio a ponto de me mencionar",
    "Mencionar não adianta de nada docinho",
    "Oque você pensa sobre mencionar um bot? Tem ninguém pra conversar não?",
    "Para de me mencionar, obrigada",
    "Vai corinthiaaaans",
    "Meu Deus, você está mencionando um bot? Isso não é bom para a saúde do servidor!",
    "Nada de me mencionar por aqui, se quiser conversar, seja apenas SOCIAL!",
]
ID_CARGO_MUTE = 1445066766144376934
@bot.event
async def on_message(message):
    global ultimo_reagir

    # Ignorar bots
    
    if message.author.id == BOT_MUSICA_PROIBIDO:
        if message.channel.id not in CANAIS_MUSICAS_LIBERADO:
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention} você não tem vip para poder colocar o bot de música em qualquer lugar!")
                logging.info(f"Tentativa de colocar o bot de música em {message.channel.mention} por {message.author.mention}")
            except:
                pass
            return
    if message.author.bot:
        return
    # ============================
    #  SISTEMA MONITORAMENTO
    # ============================
    conn = conectar_vips()
    c = conn.cursor()
    user_id = message.author.id
    c.execute("SELECT denunciante_id FROM avisados WHERE user_id = %s", (user_id,))
    result = c.fetchone()

    if result:
        denunciante_id = result[0]
        if any(m.id == int(denunciante_id) for m in message.mentions):
            c.execute("SELECT mensagens FROM atividade WHERE user_id = %s", (user_id,))
            row = c.fetchone()
            if row:
                warnings = row[0]
            else:
                warnings = 0

            #Primeiro aviso
            if warnings == 0:
                await message.channel.send(
                    f"{message.author.mention} ⚠️ Aviso: você mencionou a pessoa que te denunciou. "
                    "Se repetir, receberá mute automático de 3 horas."
                )
                semana_atual = datetime.now(timezone.utc).isocalendar()[1]
                c.execute(
                    "INSERT INTO atividade (user_id, nome_discord, mensagens, semana) VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE mensagens = mensagens + 1",
                    (user_id, f"{message.author.name}#{message.author.discriminator}", 1, semana_atual)
                )
                conn.commit()
                # Segundo aviso → Mute automático
            else:
                mute_role = message.guild.get_role(ID_CARGO_MUTE)

                await message.author.add_roles(
                    mute_role,
                    reason="Perturbação reincidente — mute automático"
                )
                await message.channel.send(
                    f"{message.author.mention} 🔇 Você recebeu mute automático de **3 horas**."
                )
                asyncio.create_task(remover_mute_apos_3h(message.author))
    c.close()
    conn.close()
    

    # ============================
    #  SISTEMA DE MURAL (REAÇÃO + DB)
    # ============================
    if message.channel.id == 1386805780140920954 and message.attachments:
        await message.add_reaction("👍")
        await message.add_reaction("👎")

        conexao_mural = conectar_vips()
        cursor_mural = conexao_mural.cursor()

        cursor_mural.execute(
            """
            INSERT IGNORE INTO posts 
            (id, user_id, channel_id, upvotes, downvotes, removed, timestamp)
            VALUES (%s, %s, %s, 0, 0, FALSE, NOW())
            """,
            (message.id, message.author.id, message.channel.id)
        )

        conexao_mural.commit()
        cursor_mural.close()
        conexao_mural.close()

    # ============================
    #  DICIONÁRIO DE REAÇÕES POR TEXTO
    # ============================
    reacoes_jogos = {
        "lol\n": "<a:1b09ea8103ca4e519e8ff2c2ecb0b7f3:1409880647677378671>",
        "minecraft": "<a:ovelhaloca:1409884416964034590>",
        "mine\n": "<a:ovelhaloca:1409884416964034590>",
        "valorant": "<a:vava:1409884608950173908>",
        "sifu": "<:Sifu:1409884805402857665>",
        "rematch": "⚽",
        "little nightmares": "<:Litte:1391467637246132295>",
        "brawlhalla": "<:Brawl:1410274778971111434>",
        "roblox": "<:Roblox_Player_2019:1409885436767371364>",
        "resident evil": "<:Leon:1409885570619932793>",
        "naruto": "<a:586e603a2a0b495db52185c7b55aae4b:1409885946354335956>",
        "dbz": "<a:22db139b5bff4e4389db335417680d19:1409886253658279936>",
        "jojo\n": "<:imagem_20251118_090924909removeb:1440313019614630030>",
        "dragon ball": "<a:22db139b5bff4e4389db335417680d19:1409886253658279936>",
        "fortnite": "<:82963fortnite:1410351278579519620>",
        "gta": "<a:6d5a39e9d772479c9e66ef343850312c:1410351267099836619>",
        "among us": "<a:36349amongusfornitedance:1410351263064916044>",
        "cs:go": "<:70385csgo:1410352338178150420>",
        "one piece": "<:__:1410352761148674129>",
        "blue lock": "<:bl:1410628296554840125>",
        "read dead": "<:RDR:1410628111850278912>",
        "dante": "<:3938dantesmile:1437791755096293510>",
        "dmc": "<:3938dantesmile:1437791755096293510>",
        "devil may cry": "<:3938dantesmile:1437791755096293510>",
        "vergil": "<:9488vergil:1437791981001773197>",

        # Reações gerais
        "te amo": "<a:t_:1410629102460866662>",
        "amo vc": "<a:t_:1410629102460866662>",
        "me come": "<a:84409hehehe:1410630694752878623>",
        "medo": "<:942937heeeee:1410630968020307988>",
        "putaria": "<a:84409hehehe:1410630694752878623>",
        "safada": "<a:84409hehehe:1410630694752878623>",
        "que triste": "<:47767duobbl:1410631842427703356>",
        "dançar": "<a:21306happydance:1410632136918175904>",
        "kkkkkkkkkkkkkk": "<a:ed1e00c7097847f48b561a084357b523:1410632680009109544>",
        "que?": "<a:4c21d58306094c4eba2d4e3cd7a1cc7b:1410632816965845222>",
        "que fofo": "<a:438beaf6a7ba43cc90429c74642703e5:1410632930451132563>",
        "contra\n": "<:bd5d14f51cbd4a8d9c5b0baa81c831f8:1410633411357577246>",
        "vs\n": "<:bd5d14f51cbd4a8d9c5b0baa81c831f8:1410633411357577246>",
        "mk\n": "<:f4c937e43ab44ecc95e1a72c14d68a0d:1410633419020439592>",
        "mortal kombat": "<:f4c937e43ab44ecc95e1a72c14d68a0d:1410633419020439592>",
        "scorpion": "<a:98bbba5eb3314918887e43b8d7dedc5b:1410633451241078784>",
        "sub zero": "<:imagem_20250828_113557653removeb:1410634062812680263>",
        "neymar": "<:ney:1410634540527124551>",
        "cr7": "<:imagem_20250828_113842284:1410634720189878432>",
        "messi": "<:imagem_20250828_113903436:1410634809365233836>",
        "brawl stars": "<:imagem_20250828_134308029:1410666034062688286>",
        "akuni": "<:93820aurorareading:1411015127251292351>",
        "mbappe": "<:86897mbappefootball:1437441637218390156>",
        "vini jr": "<:65748vinijrfootball:1437441624173973634>",
        "vini malvadeza": "<:65748vinijrfootball:1437441624173973634>",
        "repo": "<:8814repo:1437442117717856428>",
        "67" : "<a:42642667:1444748898592755764>"
    }

    # ============================
    #  REAÇÃO AUTOMÁTICA POR TEXTO
    # ============================
    texto = message.content.lower()

    for termo, emoji in reacoes_jogos.items():
        if termo in texto:
            agora = time_module.time()
            if agora - ultimo_reagir >= COOLDOWN:
                try:
                    await message.add_reaction(emoji)
                    ultimo_reagir = agora
                except discord.HTTPException:
                    pass
            break

    # ============================
    #  RESPOSTA QUANDO MENCIONADO
    # ============================
    if bot.user in message.mentions:
        reacao = random.choice(BOT_REACTION)
        await message.channel.send(reacao)
        

    # ============================
    #  IGNORAR CARGO ESPECÍFICO
    # ============================
    if message.guild and hasattr(message.author, "roles"):
        if any(r.id == CARGO_IGNORADO for r in message.author.roles):
            return

    # ============================
    #  CONTAGEM DE MENSAGENS SEMANAIS
    # ============================
    user_id = message.author.id
    nome = str(message.author)
    hoje = datetime.now(timezone.utc).date()
    semana_atual = hoje.isocalendar()[1]

    conexao = conectar_vips()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        INSERT INTO atividade (user_id, nome_discord, mensagens, semana)
        VALUES (%s, %s, 1, %s)
        ON DUPLICATE KEY UPDATE 
            mensagens = mensagens + 1,
            nome_discord = %s,
            semana = %s
    """, (user_id, nome, semana_atual, nome, semana_atual))

    conexao.commit()
    cursor.close()
    conexao.close()

    await bot.process_commands(message)

    try:
        if message.channel.id == ID_CANAL_TICKET:
            if 'TICKET_EMBED_MESSAGE_ID' in globals():
                if (globals().get('TICKET_EMBED_MESSAGE_ID') is not None) and (message.id != globals().get('TICKET_EMBED_MESSAGE_ID')) and (not message.author.bot):
                    try:
                        await message.delete()
                    except:
                        pass
    except:
        pass

@bot.event
async def on_voice_state_update(member, before, after):
    if member and member.id == BOT_MUSICA_PROIBIDO:
        if after and after.channel:
            canal_id = after.channel.id
            if canal_id not in CANAIS_MUSICAS_LIBERADO:
                try:
                    canais_permitidos = [bot.get_channel(cid) for cid in CANAIS_MUSICAS_LIBERADO]
                    destino = next((c for c in canais_permitidos if c and c.guild.id == member.guild.id), None)
                    if destino:
                        await member.move_to(destino, reason="Mover bot de música para canal permitido")
                        try:
                            await after.channel.send(f"{member.mention} foi movido para {destino.mention}.")
                        except:
                            pass
                    else:
                        await member.edit(mute=True, deafen=True, reason="Bot de música restrito a canais permitidos")
                        try:
                            await after.channel.send(f"{member.mention} está silenciado fora dos canais permitidos.")
                        except:
                            pass
                except Exception as e:
                    logging.error(f"Falha ao aplicar restrição ao bot de música: {e}")



# ======================================
#  FUNÇÃO PARA ENVIAR TOP ATIVOS SEMANAL
# ======================================
async def enviar_top_ativos_semanal_once(semana_atual, canal):
    conexao = conectar_vips()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT nome_discord, mensagens
        FROM atividade
        WHERE semana = %s
        ORDER BY mensagens DESC
        LIMIT 5
    """, (semana_atual,))
    
    resultados = cursor.fetchall()
    cursor.close()
    conexao.close()

    if resultados:
        embed = discord.Embed(
            title="<:Jinx_Cool:1406660820602978374> Top 5 Usuários Mais Ativos da Semana",
            color=0xFFD700
        )

        for i, user in enumerate(resultados, start=1):
            embed.add_field(
                name=f"{i}º - {user['nome_discord']}",
                value=f"Mensagens: {user['mensagens']}",
                inline=False
            )

        await canal.send(embed=embed)


jogando = {}
ultimo_envio = {}  

@bot.event
async def on_presence_update(before, after):
    user = after
    guild = after.guild

    jogo_anterior = next((a.name for a in before.activities if a.type == discord.ActivityType.playing), None)
    jogo_atual = next((a.name for a in after.activities if a.type == discord.ActivityType.playing), None)

    # Se o jogo não mudou, sai
    if jogo_anterior == jogo_atual:
        return

    # Remove o usuário do jogo anterior
    if jogo_anterior and jogo_anterior in jogando and user.id in jogando[jogo_anterior]:
        jogando[jogo_anterior].remove(user.id)
        if not jogando[jogo_anterior]:
            del jogando[jogo_anterior]

    # Adiciona o usuário ao novo jogo, se estiver jogando e em call
    if jogo_atual and after.voice is not None:
        if jogo_atual not in jogando:
            jogando[jogo_atual] = []
        if user.id not in jogando[jogo_atual]:
            jogando[jogo_atual].append(user.id)

        # Verifica cooldown (10 minutos)
        agora = datetime.utcnow()
        if jogo_atual in ultimo_envio:
            tempo_desde_ultimo = agora - ultimo_envio[jogo_atual]
            if tempo_desde_ultimo < timedelta(minutes=10):
                return  # Ainda dentro do cooldown, não envia

        # Envia mensagem apenas se houver 3 jogadores
        if len(jogando[jogo_atual]) == 3:
            channel = bot.get_channel(1380564680552091789)
            mentions = " ".join(f"<@{uid}>" for uid in jogando[jogo_atual])
            await channel.send(
                f"<a:5ad2b0ea20074b8c80a3fa600b4e8ec4:1410657064430075975> "
                f"Os jogadores {mentions} estão jogando **{jogo_atual}** na call! Jogue você também!"
            )
            ultimo_envio[jogo_atual] = agora

 




@commands.has_permissions(administrator=True)
@bot.command()
async def resetar_mensagens (ctx):
    if ctx.author.id != ADM_BRABO:
        return await ctx.send("❌ Você não tem permissão para usar este comando.")
    
    conn = conectar_vips()
    cursor = conn.cursor()

    cursor.execute("TRUNCATE TABLE atividade")
    conn.commit()
    cursor.close()
    conn.close()
    await ctx.send("✅ Mensagens de atividade foram resetadas.")
    logging.info("Comando resetar_mensagens executado por %s", ctx.author)
    

async def remover_mute_apos_3h(member):
    await asyncio.sleep(10800)
    mute_role = member.guild.get_role(ID_CARGO_MUTE)
    await member.remove_roles(mute_role, reason="Mute finalizado automaticamente")
ID_DO_SERVIDOR = 1380564679084081175

@tasks.loop(hours=24)
async def limpar_avisados():
    conn = conectar_vips()
    c = conn.cursor()

    c.execute("""
        SELECT user_id FROM avisados
        WHERE data_aviso < DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)

    rows = c.fetchall()

    guild = bot.get_guild(ID_DO_SERVIDOR)
    cargo_avisado = guild.get_role(CARGO_AVISADO)

    for (user_id,) in rows:
        membro = guild.get_member(user_id)
        if membro:
            await membro.remove_roles(cargo_avisado, reason="Aviso expirado")

        c.execute("DELETE FROM avisados WHERE user_id = %s", (user_id,))
        conn.commit()


@bot.command()
@commands.has_permissions(administrator=True)
async def vip_list(ctx):
    try:
        conn = conectar_vips()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome_discord, data_inicio, data_fim FROM vips")
        vips = cursor.fetchall()
        cursor.close()
        conn.close()

        if not vips:
            await ctx.send("❌ Nenhum VIP registrado ainda.")
            return

        embed = discord.Embed(
            title="<:discotoolsxyzicon_6:1444750406763679764> Lista de VIPs Ativos",
            color=discord.Color.blue()
        )
        from datetime import datetime, timezone

        agora = datetime.now(timezone.utc)
        itens = []
        for id_vip, nome_discord, data_inicio, data_fim in vips:
            # Normaliza para UTC se vier naive
            if data_inicio.tzinfo is None:
                data_inicio = data_inicio.replace(tzinfo=timezone.utc)
            if data_fim.tzinfo is None:
                data_fim = data_fim.replace(tzinfo=timezone.utc)

            restante = data_fim - agora
            ativo = restante.total_seconds() > 0
            dias = max(0, restante.days)
            horas = max(0, int((restante.total_seconds() % 86400) // 3600))
            itens.append((ativo, data_fim, nome_discord, data_inicio, dias, horas))

        # Ordena ativos por menor tempo restante; expirados por data_fim
        itens.sort(key=lambda x: (not x[0], x[1]))

        for ativo, _, nome_discord, data_inicio, dias, horas in itens:
            status = "Ativo" if ativo else "Expirado"
            valor = (
                f"Início: `{data_inicio.strftime('%d/%m/%Y')}`\n"
                + (f"Restam: **{dias}d {horas}h**" if ativo else "Status: **Expirado**")
            )
            embed.add_field(name=f"{nome_discord} — {status}", value=valor, inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send("❌ Erro ao acessar o banco de dados.")
        logging.error(f"Erro vip_list: {e}")

 
        #----------------------------Anime--------------------------

animes = ["<:GRIFFITH:1408187671179821128>","<a:Goku:1408188460442849340>","<:itachi74:1408188776211025990>","<:Narutin:1408189027437379655>","<:ichigo_hollificado:1408189507702100150>","<:sukuna:1408189731916878035>","<a:Saitama:1408190053846356038>","<a:eren_titan_laugh:1408190415814922400>","<:ken99:1408190793457598544>","<a:Deku_Sword:1408190983971147929>","<a:Astademon:1408191298141294754>","<:Tanjiro_Angry:1408191588739317952>","<:aim26:1408191800266457411>"]

CANAL_ID = 1380564680552091789






filas = {}
timers_desconectar = {}


# Função para tocar a próxima música na fila
TEMP_DIR = "musicas_temp"
os.makedirs(TEMP_DIR, exist_ok=True)

async def tocar_proxima(ctx, voz):
    guild_id = ctx.guild.id
    if filas.get(guild_id):
        url = filas[guild_id].pop(0)

        # Baixa áudio temporariamente
        ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': f'{TEMP_DIR}/%(title)s.%(ext)s',
    'noplaylist': True,
    'extractor_args': {'youtube': {'player_client': ['android']}}
}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                arquivo = ydl.prepare_filename(info)
        except Exception as e:
            await ctx.send(f"❌ Não consegui tocar essa música: {e}")
            return

        def depois_de_tocar(error):
            try:
                if os.path.exists(arquivo):
                    os.remove(arquivo)
            except Exception as e:
                logging.error(f"Erro ao remover arquivo: {e}")
            # Toca a próxima música
            asyncio.run_coroutine_threadsafe(tocar_proxima(ctx, voz), bot.loop)

        voz.play(FFmpegPCMAudio(arquivo), after=depois_de_tocar)
        asyncio.run_coroutine_threadsafe(
            ctx.send(f"Tocando agora: {info['title']} <a:69059milkguitar:1417173552138031144>"),
            bot.loop
        )

    else:
        # Timer de desconexão
        async def desconectar_apos_espera():
            try:
                await asyncio.sleep(60)
                if voz.is_connected() and not voz.is_playing():
                    await voz.disconnect()
                    await ctx.send("<a:489897catfistbump:1414720257720848534> Esperei 1 minuto e nada de música, então fui!")
            except Exception as e:
                logging.error(f"Erro no timer de desconexão: {e}")

        timers_desconectar[ctx.guild.id] = bot.loop.create_task(desconectar_apos_espera())

#COMANDO TICKET
CARGO_AVISADO = 1445063169973424239
ID_CANAL_TICKET = 1386766363749781504
TICKET_EMBED_MESSAGE_ID = None
@bot.command()
@commands.has_permissions(administrator=True)
async def ticket_mensagem(ctx):
    if ctx.channel.id != ID_CANAL_TICKET:
        return await ctx.send("❌ Use este comando no canal de tickets.")
    embed = discord.Embed(
        title="🎫 Abra seu Ticket",
        description=(
            "Use o comando **!ticket** neste canal e siga as instruções na DM.\n\n"
            "Opções disponíveis:\n"
            "1️⃣ Ajuda do servidor\n"
            "2️⃣ Recuperar cargo perdido\n"
            "3️⃣ Denúncia"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Use o comando !ticket para abrir um ticket.")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1380564680552091789/1445202774756298752/JINXED_7.png?ex=692f7d78&is=692e2bf8&hm=23728dc10a7f583a4a4210f09c6cf5ec4555ee640fedd190de239bb5639b06f8&")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749579605119148/discotools-xyz-icon.png?ex=692fd1a5&is=692e8025&hm=c5bc7e74adbb2ea7dfa4f3340d48d94cc51818dcfb936f9ebb56aaaccd44bb8f&")
    try:
        msg = await ctx.send(embed=embed)
        global TICKET_EMBED_MESSAGE_ID
        TICKET_EMBED_MESSAGE_ID = msg.id
        await ctx.message.delete()
    except Exception as e:
        logging.error(f"Falha ao enviar ticket_mensagem: {e}")
        return await ctx.send("❌ Não foi possível enviar a mensagem de ticket.")

    return

@bot.command()
async def ticket (ctx):
    if ctx.channel.id != ID_CANAL_TICKET:
        return await ctx.send("❌ Este comando só pode ser usado no canal de tickets.")
    logging.info("Comando ticket executado por %s", ctx.author)
    if ctx.channel.id == ID_CANAL_TICKET:
        try:
            await ctx.message.delete()
        except:
            pass

    user = ctx.author
    try:
        dm = await user.create_dm()
        await dm.send(
            "Olá! Vi que você solicitou o seu ticket.\n\n"
            "O que você deseja?\n"
            "Digite o número da opção:\n"
            "1️⃣ Ajuda do servidor\n"
            "2️⃣ Recuperar cargo perdido\n"
            "3️⃣ Denúncia"
        )
    except:
        return await ctx.send("❌ Não consegui enviar DM. Ative sua DM para continuar.")

    def check (m):
        return m.author.id == user.id and isinstance (m.channel, discord.DMChannel)
    try:
        msg = await bot.wait_for("message", check=check, timeout=120)
        opcao = msg.content.strip()
        if opcao not in {"1", "2", "3"}:
            await dm.send("⚠️ Opção inválida. Use 1, 2 ou 3.")
            return
    except asyncio.TimeoutError:
        return await ctx.send("❌ Você demorou muito para responder.")
    logging.info("Opção escolhida por %s: %s", ctx.author, opcao)

    conn = conectar_vips()
    c = conn.cursor()
    sql = "INSERT INTO tickets (user_id, nome_discord, tipo) VALUES (%s, %s, %s)"
    c.execute(sql, (user.id, f"{ctx.author.name}#{ctx.author.discriminator}", int(opcao)))
    conn.commit()
    ticket_id = c.lastrowid
    
    if opcao == "1":
        await dm.send("Seu pedido de ajuda foi registrado! Em breve um staff irá te atender.")
        try:
            admins = [428006047630884864, 614476239683584004]
            for admin_id in admins:
                admin = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
                if admin:
                    await admin.send(
                        "📩 Novo ticket de ajuda\n\n"
                        f"🧑 Solicitante: <@{user.id}> ({ctx.author.name}#{ctx.author.discriminator})\n"
                        f"🆔 Ticket: #{ticket_id}\n"
                        "✅ Verifique no painel/banco e atenda quando possível."
                    )
            logging.info("Notificação de ticket de ajuda enviada aos admins: %s", admins)
        except Exception as e:
            logging.error("Falha ao notificar admins sobre ticket de ajuda: %s", e)
    elif opcao == "2":
        await dm.send("Seu pedido de recuperação de cargo foi registrado! Em breve um staff irá te atender.")
        try:
            admins = [428006047630884864, 614476239683584004, 1102837164863148062]
            for admin_id in admins:
                admin = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
                if admin:
                    await admin.send(
                        "📩 Novo ticket de ajuda\n\n"
                        f"🧑 Solicitante: <@{user.id}> ({ctx.author.name}#{ctx.author.discriminator}) pediu ajuda com cargo\n"
                        f"🆔 Ticket: #{ticket_id}\n"
                        "✅ Verifique no painel/banco e atenda quando possível."
                    )

                    logging.info("Notificação de ticket de recuperação de cargo enviada aos admins: %s", admins)
        except Exception as e:
            logging.error("Falha ao notificar admins sobre ticket de recuperação de cargo: %s", e)
    elif opcao == "3":
        await dm.send(
            "Qual o tipo de denúncia?\n"
            "1️⃣ Abuso de moderação\n"
            "2️⃣ Perturbação / Cyberbullying"
        )
        msg2 = await bot.wait_for("message", check=check)
        tipo_denuncia = msg2.content.strip()
    
    if opcao == "3" and tipo_denuncia == "1":
        await dm.send("Envie o ID exato do moderador que abusou da moderação:")

        msg3 = await bot.wait_for("message", check=check)
        id_moderador = msg3.content.strip()
        guild = ctx.guild
        membro = guild.get_member(int(id_moderador))

        if not membro:
            return await dm.send("<:3894307:1443956354698969149> ID do moderador inválido.")
        if user.id == membro.id:
            await dm.send("❌ Você não pode denunciar a si mesmo.")
            c.close(); conn.close(); return
        if not (membro.guild_permissions.kick_members or membro.guild_permissions.ban_members or membro.guild_permissions.manage_messages or membro.guild_permissions.administrator):
            await dm.send("⚠️ O ID informado não pertence a um moderador.")
            c.close(); conn.close(); return

        # salvar denúncia antes de qualquer lógica (atomicidade)
        c.execute(
            "SELECT 1 FROM denuncias WHERE denunciante_id=%s AND denunciado_id=%s AND tipo_denuncia=1 LIMIT 1",
            (user.id, membro.id)
        )
        if c.fetchone():
            await dm.send("⚠️ Denúncia já registrada anteriormente para este moderador.")
            c.close(); conn.close(); return
        c.execute(
            "INSERT INTO denuncias (ticket_id, denunciante_id, denunciado_id, tipo_denuncia) VALUES (%s, %s, %s, 1)",
            (ticket_id, user.id, membro.id)
        )
        conn.commit()

        cargo_avisado = guild.get_role(CARGO_AVISADO)
        if cargo_avisado:
            await membro.add_roles(cargo_avisado, reason="Denunciado por abuso de moderação")
            logging.info("Cargo avisado adicionado a %s", membro)

        try:
            dm_denunciado = await membro.create_dm()
            await dm_denunciado.send(
                "⚠️ Você recebeu uma denúncia de perturbação. "
                "Estamos monitorando seu comportamento durante 30 dias."
            )
        except:
            pass
        sql = "INSERT INTO avisados (user_id, denunciante_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE denunciante_id=VALUES(denunciante_id)"
        c.execute(sql, (membro.id, user.id))
        conn.commit()

        # evita duplicidade de alerta ativo
        c.execute(
            "SELECT 1 FROM moderador_alertas WHERE denunciante_id=%s AND moderador_id=%s LIMIT 1",
            (ctx.author.id, int(id_moderador))
        )
        if not c.fetchone():
            sql = "INSERT INTO moderador_alertas (denunciante_id, moderador_id) VALUES (%s, %s)"
            c.execute(sql, (ctx.author.id, int(id_moderador)))
        conn.commit()

        c.execute(
            "INSERT INTO denuncias (ticket_id, denunciante_id, denunciado_id, tipo_denuncia) VALUES (%s, %s, %s, 1)",
            (ticket_id, user.id, int(id_moderador))
        )
        conn.commit()

        sql = """
            SELECT COUNT(DISTINCT denunciante_id)
            FROM moderador_alertas
            WHERE moderador_id = %s
            """
        c.execute(sql, (int(id_moderador),))
        qtd = c.fetchone()[0]
        if qtd >= 3:
            alertar = [428006047630884864, 614476239683584004]
            for admin_id in alertar:
                admin = bot.get_user(admin_id)
                if admin:
                    await admin.send(
                        "⚠️ Alerta de possível abuso de moderação\n\n"
                        f"O moderador <@{id_moderador}> recebeu denúncias de 3 usuários diferentes.\n"
                        "Verifique o caso no painel / banco de dados."
                    )
                    logging.info("Alerta enviado para %s sobre %s denúncias de abuso de moderação", admin, qtd)



        
        await dm.send("Sua denúncia foi enviada. A equipe será notificada.")
    elif opcao == "3" and tipo_denuncia == "2":
        await dm.send("Envie os IDs das pessoas que te perturbam (separados por espaço):")

        msg3 = await bot.wait_for("message", check=check)
        ids = msg3.content.strip().split()

        for denunciado_id in ids:
            sql = "INSERT INTO denuncias (ticket_id, denunciante_id, denunciado_id, tipo_denuncia) VALUES (%s, %s, %s, 2)"
            c.execute(sql, (ticket_id, user.id, int(denunciado_id)))
        
        conn.commit()

    c.close()
    conn.close()


    







@bot.command()
async def tocar(ctx, url):
    # Verificação de permissões
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    cargo_booster = discord.utils.get(ctx.guild.roles, name="Jinxed Booster")
    if not (ctx.author.guild_permissions.administrator or 
            (cargo_vip in ctx.author.roles) or 
            (cargo_booster in ctx.author.roles)):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    # Verifica se o usuário está em um canal de voz
    if ctx.author.voice is None:
        await ctx.send("Você precisa estar em um canal de voz!")
        return

    canal = ctx.author.voice.channel
    voz = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # Conecta ou move para o canal de voz
    if voz is None:
        voz = await canal.connect()
    elif voz.channel != canal:
        await voz.move_to(canal)

    # Cancela timer de desconexão se houver
    if ctx.guild.id in timers_desconectar:
        task = timers_desconectar.pop(ctx.guild.id)
        if not task.done():
            task.cancel()

    # Cria fila se não existir
    if ctx.guild.id not in filas:
        filas[ctx.guild.id] = []

    # Adiciona música à fila ou toca imediatamente
    if voz.is_playing():
        filas[ctx.guild.id].append(url)
        await ctx.send("<a:53941musicalastronaut:1417173804861489192> Música adicionada à fila!")
    else:
        filas[ctx.guild.id].append(url)
        await tocar_proxima(ctx, voz)

    

@bot.command()
async def pular(ctx):
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    cargo_booster = discord.utils.get(ctx.guild.roles, name="Jinxed Booster")
    if not (ctx.author.guild_permissions.administrator or 
            (cargo_vip in ctx.author.roles) or 
            (cargo_booster in ctx.author.roles)):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return
    if ctx.author.voice is None:
        await ctx.send("Você precisa estar em um canal de voz!")
        return
    voz = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voz and voz.is_playing():
        voz.stop()
        await ctx.send("⏭ Música pulada! <a:270795discodance:1419694558945476760>")
    else:
        await ctx.send("<:__:1410352761148674129> Nenhuma música tocando.")

@bot.command()
async def tocar_playlist(ctx, url):
    # Verifica permissões/cargos
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    cargo_booster = discord.utils.get(ctx.guild.roles, name="Jinxed Booster")
    if not (ctx.author.guild_permissions.administrator or 
            (cargo_vip in ctx.author.roles) or 
            (cargo_booster in ctx.author.roles)):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    # Verifica se está em um canal de voz
    if ctx.author.voice is None:
        await ctx.send("Você precisa estar em um canal de voz!")
        return

    canal = ctx.author.voice.channel
    voz = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voz is None:
        voz = await canal.connect()
    elif voz.channel != canal:
        await voz.move_to(canal)

    # Cancela timer de desconexão se houver
    if ctx.guild.id in timers_desconectar:
        timers_desconectar[ctx.guild.id].cancel()

    # Cria fila se não existir
    if ctx.guild.id not in filas:
        filas[ctx.guild.id] = []

    # Extrai vídeos da playlist usando yt_dlp
    ydl_opts = {"quiet": True, "extract_flat": True, "dump_single_json": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        videos = info.get("entries", [info])  # Se for só um vídeo, devolve ele mesmo

    for video in videos:
        if not video.get("id"):
            continue
    video_url = f"https://www.youtube.com/watch?v={video['id']}"
    filas[ctx.guild.id].append(video_url)

    await ctx.send(f"<a:53941musicalastronaut:1417173804861489192> *{len(videos)} músicas adicionadas à fila*!")

    # Se não estiver tocando, começa a tocar a primeira música
    if not voz.is_playing():
        await tocar_proxima(ctx, voz)

@bot.command()
async def parar(ctx):
    cargo_vip = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
    cargo_booster = discord.utils.get(ctx.guild.roles, name="Jinxed Booster")
    if not (ctx.author.guild_permissions.administrator or 
            (cargo_vip in ctx.author.roles) or 
            (cargo_booster in ctx.author.roles)):
        await ctx.send("<:JinxKissu:1408843869784772749> Você não tem permissão para usar este comando.")
        return
    if ctx.author.voice is None:
        await ctx.send("Você precisa estar em um canal de voz!")
        return
    voz = discord.utils.get(bot.voice_clients,guild=ctx.guild)
    if voz:
        voz.stop()
        await voz.disconnect()
        await ctx.send("<:JinxKissu:1408843869784772749> Música parada e bot desconectado.")

    else:
        await ctx.send("Tô em nenhum canal de voz não fi")

#-------------------cargo jogo------------

Envio_mensagem = 1380564680552091789
ROLE_MINECRAFT = 1422954037174603796
ROLE_BRAWHALLA = 1425160627487375533
ROLE_ROBLOX    = 1422954452846907446
ROLE_VALORANT  = 1422954672754397316
ROLE_LOL       = 1422978913373651094

class RoleView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Minecraft", style=discord.ButtonStyle.green, custom_id="minecraft")
    async def minecraft_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_MINECRAFT)   
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Minecraft**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Roblox", style=discord.ButtonStyle.red, custom_id="roblox")
    async def roblox_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_ROBLOX)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Roblox**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Valorant", style=discord.ButtonStyle.blurple, custom_id="valorant")
    async def valorant_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_VALORANT)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Valorant**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="LoL", style=discord.ButtonStyle.gray, custom_id="lol")
    async def lol_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_LOL)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **LoL**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Brawlhalla", style=discord.ButtonStyle.green, custom_id="brawlhalla")
    async def brawlhalla_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_BRAWHALLA)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Brawlhalla**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)


@tasks.loop(hours=4)
async def enviar_mensagem():
    canal = bot.get_channel(Envio_mensagem)
    if canal:
        embed = discord.Embed(
            title="🎮 **Escolha seu cargo de jogador!**",
            description=(
                "Quer receber avisos só sobre o seu jogo favorito? 🕹️\n\n"
                "Clique no botão do jogo que você mais joga e receba o cargo correspondente. "
                "Assim, quando alguém quiser jogar, pode te mencionar diretamente sem incomodar todo mundo! ✨\n\n"
                "Escolha sabiamente e divirta-se com a sua galera de jogo!"
            ),
            color=discord.Color.from_rgb(255, 100, 50)
        )
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/704107435295637605/1422978121874800690/Gemini_Generated_Image_iwkdiciwkdiciwkd.png?ex=68dea325&is=68dd51a5&hm=939267e30f3431ea3e2537c23cae7a7473bce8f07b340d7aad6c3f5d37eb8d56&"
        )

        # Usando a RoleView com os métodos de clique
        view = RoleView()

        await canal.send(embed=embed, view=view)





   
    


@tasks.loop(hours=4)
async def enviar_mensagem():
    canal = bot.get_channel(Envio_mensagem)
    if canal:
        embed = discord.Embed(
            title="🎮 **Escolha seu cargo de jogador!**",
            description=(
        "Quer receber avisos só sobre o seu jogo favorito? 🕹️\n\n"
        "Clique no botão do jogo que você mais joga e receba o cargo correspondente. "
        "Assim, quando alguém quiser jogar, pode te mencionar diretamente sem incomodar todo mundo! ✨\n\n"
        "Escolha sabiamente e divirta-se com a sua galera de jogo!"
        ),
            color=discord.Color.from_rgb(255, 100, 50)
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/704107435295637605/1422978121874800690/Gemini_Generated_Image_iwkdiciwkdiciwkd.png?ex=68dea325&is=68dd51a5&hm=939267e30f3431ea3e2537c23cae7a7473bce8f07b340d7aad6c3f5d37eb8d56&")

        # Usando a RoleView com os métodos de clique
        view = RoleView()

        await canal.send(embed=embed, view=view)





#--------------------FUTEBOL PALPITE---------------------



EMOJI_TIMES = {
    "sport": "<:Sport:1425992405227671593>",
    "juventude": "<:Juventude:1425992333207539732>",
    "fortaleza": "<:Fortaleza:1425992225128583218>",
    "vitoria": "<:Vitri:1425992077702860905>",
    "santos": "<:Santos:1425991974179045468>",
    "internacional": "<:Internacional:1425991752468267158>",
    "galo": "<:Galo:1425991683690074212>",
    "gremio": "<:Gremio:1425991602438148187>",
    "corinthians": "<:Corinthians:1425991139517010031>",
    "vasco": "<:Vascodagama:1425991055941046373>",
    "ceara": "<:Cear:1425990930254790718>",
    "bragantino": "<:Bragantino:1425990800885678160>",
    "sao_paulo": "<:SoPaulo:1425990707373674587>",
    "fluminense": "<:Fluminense:1425990639128150106>",
    "bahia": "<:Bahia:1425990545314021427>",
    "botafogo": "<:Botafogo:1425990460589080617>",
    "mirassol": "<:Mirassol:1425990400178393098>",
    "cruzeiro": "<:Cruzeiro:1425990118816354405>",
    "flamengo": "<:Flamengo:1425990044623044659>",
    "palmeiras": "<:Palmeiras:1425989650513662044>",
    "brasil":"<:imagem_20251111_091505344:1437777668320788501>",
    "argentina":"<:imagem_20251111_091525637:1437777753205243936>",
    "frança":"<:imagem_20251111_091547369:1437777844058194001>",
    "alemanha":"<:imagem_20251111_091612275:1437777948907405332>",
    "italia":"<:imagem_20251111_091635544:1437778046680699010>",
    "inglaterra":"<:imagem_20251111_091700042:1437778149155803328>",
    "espanha":"<:imagem_20251111_091727942:1437778266118422568>",
    "portugal":"<:imagem_20251111_091755098:1437778380324864103>",
    "holanda":"<:imagem_20251111_091822476:1437778495018106880>",
    "uruguai":"<:imagem_20251111_091923082removeb:1437778793711534110>",
    "belgica":"<:imagem_20251111_091958114:1437778895888846888>",
    "croacia":"<:imagem_20251111_092025445:1437779010628222998>",
    "mexico":"<:imagem_20251111_092057355:1437779144917127259>",
    "japao":"<:imagem_20251111_092122937:1437779251729272903>",
    "eua":"<:imagem_20251111_092151751:1437779372940464138>",
    "senegal":"<:imagem_20251111_092227325:1437779522157281290>",
    "tunisia":"<:imagem_20251111_092254095:1437779634191208518>",
    "lanus":"<:Lanus:1441436509281718383>",
    "atletico paranaense":"<:atlpr:1443398482516775055>",
    "Coritiba" : "<:Coritibaa:1443398813820784660>",
    "Remo" : "<:Remo:1443399201655492708>"



}




ROLE_IDS_TIMES = {
    "fluminense": 1442482502311739442,
    "vasco": 1442482275546697860,
    "gremio": 1442482642942689323,
    "fortaleza": 1442482777894293624,
    "galo": 1443224658710364190,
    "internacional": 1443226517219049512,
    "cruzeiro": 1443226573116538950,
    "flamengo": 1443226719572988077,
    "palmeiras": 1443227045332123648,
    "bahia": 1443227115561685033,
    "sao paulo": 1443227353412014081,
    "corinthians": 1443227525458165903,
    "santos": 1443227595935187025,
    "botafogo": 1443759934054469703,
    "vitoria": 1444483144270086267
}





acompanhando = False
ADM_BRABO = 428006047630884864

async def fazer_request(status="live"):
    params = {"live": "all"} if status == "live" else {"league": 71, "season": 2025, "status": "FT"}
    async with aiohttp.ClientSession() as session:
        async with session.get(URL, headers=HEADERS, params=params) as r:
            return await r.json()
            

API_TOKEN = os.getenv("API_KEY")
URL = "https://v3.football.api-sports.io/fixtures"
HEADERS = {"x-apisports-key": API_TOKEN}

# Guarda o placar anterior pra comparar
placares = {}

async def jogos_ao_vivo():
    data = await fazer_request(status="live")
    return bool(data.get("response"))





#   Ligar o loop e agendar
tz_br = pytz.timezone("America/Sao_Paulo")


@commands.has_permissions(administrator=True)
@bot.command()
async def apistart(ctx, horario: str = None):
    if ctx.author.id != ADM_BRABO:
        return await ctx.send("Só amorreba the gostoso pode usar este comando! <:Galo:1425991683690074212>")

    global acompanhando, placares

    # -----------------------------------------------------
    # MODO 1 — SEM PARÂMETRO (INÍCIO MANUAL)
    # -----------------------------------------------------
    if horario is None:
        acompanhando = True
        placares.clear()

        if not verificar_gols.is_running():
            verificar_gols.start()

        logging.info("Monitoramento iniciado MANUALMENTE.")
        return await ctx.send("🔵 **Monitoramento iniciado manualmente! Jogos ao vivo em andamento!**")

    # -----------------------------------------------------
    # MODO 2 — COM PARÂMETRO (AGENDADO)
    # -----------------------------------------------------
    agora = datetime.now(tz_br)
    try:
        if ":" in horario:
            h, m = horario.split(":", 1)
            hour = int(h)
            minute = int(m)
        else:
            hour = int(horario)
            minute = 0
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")
    except Exception:
        return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")
    horario_agendado = agora.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Se o horário já passou → agenda para o próximo dia
    if horario_agendado <= agora:
        horario_agendado += timedelta(days=1)

    await ctx.send(f"🟡 **Monitoramento será iniciado às {horario_agendado.strftime('%H:%M')} (horário de Brasília).**")
    logging.info(f"Monitoramento AGENDADO para {horario_agendado.strftime('%H:%M:%S')}")

    async def iniciar_no_horario():
        await discord.utils.sleep_until(horario_agendado)

        global acompanhando, placares
        acompanhando = True
        placares.clear()

        if not verificar_gols.is_running():
            verificar_gols.start()

        logging.info("Monitoramento iniciado AUTOMATICAMENTE no horário agendado.")
        await ctx.send(f"🟢 **Monitoramento iniciado automaticamente às {horario_agendado.strftime('%H:%M')}!**")

    bot.loop.create_task(iniciar_no_horario())

        

          
@commands.has_permissions(administrator=True)
@bot.command()
async def apistop(ctx, horario: str = None):
    if ctx.author.id != ADM_BRABO:
        return await ctx.send("Só amorreba the gostoso pode usar este comando! <:Galo:1425991683690074212>")

    global acompanhando

    # -----------------------------------------------------
    # MODO 1 — SEM PARÂMETRO (PARADA MANUAL)
    # -----------------------------------------------------
    if horario is None:
        acompanhando = False

        logging.info("Monitoramento PARADO manualmente.")
        return await ctx.send("🔴 **Monitoramento pausado manualmente! Nenhum request será feito.**")

    # -----------------------------------------------------
    # MODO 2 — PARADA AGENDADA
    # -----------------------------------------------------
    agora = datetime.now(tz_br)
    try:
        if ":" in horario:
            h, m = horario.split(":", 1)
            hour = int(h)
            minute = int(m)
        else:
            hour = int(horario)
            minute = 0
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")
    except Exception:
        return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")
    horario_agendado = agora.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if horario_agendado <= agora:
        horario_agendado += timedelta(days=1)

    await ctx.send(f"🟡 **Monitoramento será pausado às {horario_agendado.strftime('%H:%M')} (horário de Brasília).**")
    logging.info(f"Pausa AGENDADA para {horario_agendado.strftime('%H:%M:%S')}")

    async def parar_no_horario():
        await discord.utils.sleep_until(horario_agendado)
        global acompanhando
        acompanhando = False
        logging.info("Monitoramento pausado AUTOMATICAMENTE no horário agendado.")
        await ctx.send("🔴 **Monitoramento pausado automaticamente. Nenhum request será feito.**")

    bot.loop.create_task(parar_no_horario())

    





@bot.command()
async def meuspontos(ctx):
    pontos = pegar_pontos(ctx.author.id)
    await ctx.send(f"💳 {ctx.author.mention}, você tem **{pontos} pontos**!")
    logging.info(f"Usuário {ctx.author.name} ({ctx.author.id}) solicitou os pontos.")



CANAL_JOGOS_ID = 1380564680552091789

CANAL_APOSTAS_ID = 1442495893365330138 
# ---------- CONFIG ----------

URL = "https://v3.football.api-sports.io/fixtures"
HEADERS = {"x-apisports-key": API_TOKEN}
CANAL_JOGOS_ID = 1380564680552091789

EMOJI_EMPATE = "⚪"  # seu emoji de empate
# Use seus EMOJI_TIMES e MAPEAMENTO_TIMES já definidos anteriormente

# ---------- DB helper (usa sua função conectar_futebol) ----------
def garantir_tabelas():
    con = conectar_futebol()
    cur = con.cursor()

    # Tabela jogos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jogos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            fixture_id BIGINT NOT NULL UNIQUE,
            message_id BIGINT,
            home VARCHAR(100),
            away VARCHAR(100),
            bet_deadline DATETIME,
            betting_open TINYINT DEFAULT 0,
            finalizado TINYINT DEFAULT 0,
            processado TINYINT DEFAULT 0,
            canal_id BIGINT,
            data DATE,
            horario TIME,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabela apostas (corrigida: inclui modo_clown)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            fixture_id BIGINT NOT NULL,
            palpite VARCHAR(20) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            modo_clown TINYINT(1) DEFAULT 0,
            UNIQUE KEY uniq_aposta (user_id, fixture_id)
        )
    """)

    try:
        cur.execute("ALTER TABLE jogos ADD COLUMN processado TINYINT DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE apostas ADD UNIQUE KEY uniq_aposta (user_id, fixture_id)")
    except Exception:
        pass

    # Tabela pontuacoes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pontuacoes (
            nome_discord VARCHAR(50) NOT NULL,
            user_id BIGINT PRIMARY KEY,
            pontos INT NOT NULL DEFAULT 0
        )
    """)

    try:
        cur.execute("ALTER TABLE pontuacoes ADD COLUMN nome_discord VARCHAR(50) NOT NULL")
    except Exception:
        pass

    con.commit()
    con.close()

def adicionar_pontos_db(user_id: int, pontos: int, nome_discord: str = None):
    con = conectar_futebol()
    cur = con.cursor()
    try:
        if nome_discord is None:
            u = bot.get_user(int(user_id))
            nome_discord = f"{u.name}#{u.discriminator}" if u else str(user_id)
        cur.execute(
            """
            INSERT INTO pontuacoes (user_id, nome_discord, pontos)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE pontos = pontos + VALUES(pontos), nome_discord = VALUES(nome_discord)
            """,
            (user_id, nome_discord, pontos)
        )
        con.commit()
        logging.info(f"✅ Pontos adicionados: user_id={user_id}, pontos={pontos}")
    except Exception as e:
        logging.error(f"❌ Erro ao adicionar pontos: {e}")
    finally:
        cur.close()
        con.close()

def registrar_aposta_db(user_id: int, fixture_id: int, palpite: str) -> bool:
    """
    Retorna True se aposta registrada; False se o usuário já apostou nesse fixture.
    Vai também consumir um uso de clown_bet (se existir) e salvar modo_clown na aposta.
    """
    con = conectar_futebol()
    cur = con.cursor()

    # 1) verifica duplicata
    cur.execute("SELECT id FROM apostas WHERE user_id = %s AND fixture_id = %s", (user_id, fixture_id))
    if cur.fetchone():
        con.close()
        return False

    # 2) checa se usuário tem clown ativo (tabela clown_bet)
    modo_clown = 0
    try:
        cur.execute("SELECT ativo FROM clown_bet WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row and row[0] == 1:
            modo_clown = 1
            # consumir o uso (defina a lógica que preferir: desativar, decrementar ou remover)
            # Exemplo: desativar (set ativo = 0)
            cur.execute("UPDATE clown_bet SET ativo = 0 WHERE user_id = %s", (user_id,))
    except Exception:
        # se a tabela clown_bet não existir por algum motivo, seguimos sem modo_clown
        modo_clown = 0

    # 3) inserir aposta com modo_clown
    cur.execute(
        "INSERT INTO apostas (user_id, fixture_id, palpite, modo_clown) VALUES (%s, %s, %s, %s)",
        (user_id, fixture_id, palpite, modo_clown)
    )

    con.commit()
    con.close()
    return True

def pegar_apostas_fixture(fixture_id: int):
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute("SELECT user_id, palpite, modo_clown FROM apostas WHERE fixture_id = %s", (fixture_id,))
    rows = cur.fetchall()
    con.close()
    return rows

def marcar_jogo_como_open(fixture_id: int, message_id: int, home: str, away: str,
                          deadline_utc: datetime, canal_id: int, data_jogo: str, horario_jogo: str):
    con = conectar_futebol()
    cur = con.cursor()
    
    # Insert ou update completo
    cur.execute("""
        INSERT INTO jogos (fixture_id, message_id, home, away, bet_deadline, betting_open,
                           finalizado, canal_id, data, horario)
        VALUES (%s, %s, %s, %s, %s, 1, 0, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            message_id=%s,
            home=%s,
            away=%s,
            bet_deadline=%s,
            betting_open=1,
            finalizado=0,
            canal_id=%s,
            data=%s,
            horario=%s
    """, (
        fixture_id, message_id, home, away, deadline_utc, canal_id, data_jogo, horario_jogo,
        message_id, home, away, deadline_utc, canal_id, data_jogo, horario_jogo
    ))
    
    con.commit()
    con.close()

def marcar_jogo_finalizado(fixture_id: int):
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute("UPDATE jogos SET finalizado=1, betting_open=0 WHERE fixture_id = %s", (fixture_id,))
    con.commit()
    con.close()

def buscar_jogo_por_fixture(fixture_id: int):
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute("SELECT id, message_id, bet_deadline, betting_open, home, away FROM jogos WHERE fixture_id = %s", (fixture_id,))
    row = cur.fetchone()
    con.close()
    return row  # None ou (id, message_id, bet_deadline, betting_open, home, away)

# ---------- inicializa tabelas
garantir_tabelas()

# ---------- Manipulação de reações (usa on_raw_reaction_add para pegar reações em mensagens antigas)

MAPEAMENTO_TIMES = {
        "atlético mineiro": "galo",
        "atletico-mg": "galo",
        "atlético-mg":"galo",
        "galo": "galo",
        "são paulo": "sao paulo",
        "sao paulo fc": "sao paulo",
        "sao paulo": "sao paulo",
        "flamengo rj": "flamengo",
        "flamengo": "flamengo",
        "fluminense rj": "fluminense",
        "fluminense": "fluminense",
        "corinthians sp": "corinthians",
        "corinthians": "corinthians",
        "palmeiras sp": "palmeiras",
        "palmeiras": "palmeiras",
        "palemeiras": "palmeiras",
        "internacional rs": "internacional",
        "internacional": "internacional",
        "grêmio": "gremio",
        "gremio rs": "gremio",
        "gremio": "gremio",
        "bahia ba": "bahia",
        "bahia": "bahia",
        "botafogo rj": "botafogo",
        "botafogo": "botafogo",
        "cruzeiro mg": "cruzeiro",
        "cruzeiro": "cruzeiro",
        "vasco da gama": "vasco",
        "vasco": "vasco",
        "ceará": "ceara",
        "rb bragantino": "bragantino",
        "mirassol sp": "mirassol",
        "juventude rs": "juventude",
        "vitoria ba": "vitoria",
        "vitoria": "vitoria",
        "vitória": "vitoria",
        "esporte clube vitoria": "vitoria",
        "ec vitoria": "vitoria",
        "sport recife": "sport",
        "lanús": "lanus",
        "fortaleza ec" :"fortaleza",
        "fortaleza" :"fortaleza",
        "atlético paranaense": "atletico paranaense",
        "atletico pr": "atletico paranaense",
        "athletico pr": "atletico paranaense",
        "athletico paranaense": "atletico paranaense",
        "coritiba": "coritiba",
        "remo": "remo"

        
    }


PALAVRAS_GOL = {
    "galo":        "🐓 GOOOOOOOOOOL É DO GALO DOIDO!!! 🔥",
    "flamengo":    "🦅 GOOOOOOOL DO MENGÃO",
    "palmeiras":   "🐷 GOOOOOOOOOL DO VERDÃO",
    "corinthians": "🦅 GOOOOOOOL DO TIMÃO!",
    "cruzeiro":    "🦊 GOOOOOOOOOL DO CRUZEIRÃO CABULOSO!!!",
    "sao paulo":   "👑 GOOOOOL DO TRICOLOR!",
    "fortaleza":   "🦁 GOOOOOOOOL DO LEÃO DO PICI!!!",
    "vitoria":     "🦁 GOOOOOOOOOL DO LEÃO DA BARRA!!!",
    "sport":       "🦁 GOOOOOOOOOL DO LEÃO DA ILHA!!!",
    "mirassol":    "🦁 GOOOOOOOOOL DO LEÃO DE MIRASSOL!!!",
    "bahia":       "🔵⚪🔴 GOOOOOOOL DO BAHÊA, ESQUADRÃO!!!",
    "gremio":      "🤺 GOOOOOOOL DO IMORTAL TRICOLOR!!!",
    "juventude":   "🟢⚪ GOOOOOOOL DO JU!!!",
    "botafogo":    "⭐ GOOOOOOOOOL DO GLORIOSO!!!",
    "vasco":       "⚓ GOOOOOOOOL DO GIGANTE DA COLINA!!!",
    "bragantino":  "🐂 GOOOOOOOL DO MASSA BRUTA!!!",
    "ceara":       "🦅 GOOOOOOOL DO VOZÃO!!!",
    "atletico paranaense": "🌪️ GOOOOOOOL DO FURACÃO!!!",
    "fluminense":  "🍃❤️💚 GOOOOOOOL DO FLUZÃO",
    "internacional": "🎩 GOOOOOOOL DO COLORADO!!!",
    "coritiba":    "🍀 GOOOOOOOL DO COXA!!!",
    "remo":        "🦁 GOOOOOOOL DO LEÃO AZUL!!!",
    "lanus":       "🟤 GOOOOOOOL DO GRANATE!!!",
    "santos":      "🐬 GOOOOOOOOOL DO PEIXÃO!!!",
    "chapecoense": "💚⚪ GOOOOOOOL DA CHAPE!!!"
}



LIGAS_PERMITIDAS = [71, 73, 11, 13]

# ---------- Integração com verificar_gols 
@tasks.loop(minutes=5)
async def verificar_gols():
    global acompanhando, placares
    if not acompanhando:
        return

    # --------------------------------------------------------------------
    # 1) Requisição de jogos ao vivo
    # --------------------------------------------------------------------
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL, headers=HEADERS, params={"live": "all"}) as response:
                data_vivo = await response.json()
        logging.info("✅ Request de jogos ao vivo concluída com sucesso!")
    except Exception as e:
        logging.error(f"❌ Erro ao buscar dados da API (ao vivo): {e}")
        data_vivo = {"response": []}

    # --------------------------------------------------------------------
    # 2) Requisição de jogos finalizados (FT) — TODAS AS LIGAS PERMITIDAS
    # --------------------------------------------------------------------
    data_ft = {"response": []}

    try:
        async with aiohttp.ClientSession() as session:
            for liga in LIGAS_PERMITIDAS:
                async with session.get(
                    URL,
                    headers=HEADERS,
                    params={"league": liga, "season": 2025, "status": "FT"}
                ) as response:
                    ft_liga = await response.json()

                if "response" in ft_liga and ft_liga["response"]:
                    data_ft["response"].extend(ft_liga["response"])

        logging.info("✅ Request de jogos finalizados (todas ligas) concluída!")
    except Exception as e:
        logging.error(f"❌ Erro ao buscar dados FT de ligas permitidas: {e}")

    # --------------------------------------------------------------------
    # 3) Canal de jogos
    # --------------------------------------------------------------------
    canal = bot.get_channel(CANAL_JOGOS_ID)
    if not canal:
        logging.error("❌ Canal de jogos não encontrado.")
        return

    # --------------------------------------------------------------------
    # 4) Combina jogos
    # --------------------------------------------------------------------
    jogos = []

    if "response" in data_vivo and data_vivo["response"]:
        jogos.extend(data_vivo["response"])

    if "response" in data_ft and data_ft["response"]:
        jogos.extend(data_ft["response"])

    if not jogos:
        placares.clear()
        return

    tracked_ids = set()
    try:
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute("SELECT fixture_id FROM jogos WHERE finalizado=0")
        rows = cur.fetchall()
        tracked_ids = {r[0] for r in rows} if rows else set()
        con.close()
    except Exception as e:
        logging.error(f"Erro ao buscar jogos rastreados: {e}")

    # --------------------------------------------------------------------
    # 5) Loop pelos jogos
    # --------------------------------------------------------------------
    for partida in jogos:
        fixture_id = partida["fixture"]["id"]
        if partida["league"]["id"] not in LIGAS_PERMITIDAS and fixture_id not in tracked_ids:
            continue

        fixture_id = partida["fixture"]["id"]
        casa = partida["teams"]["home"]["name"]
        fora = partida["teams"]["away"]["name"]

        gols_casa = partida["goals"]["home"] or 0
        gols_fora = partida["goals"]["away"] or 0
        status = partida["fixture"]["status"]["short"].lower()

        anterior = placares.get(fixture_id, {"home": 0, "away": 0, "status": ""})

        nome_casa = MAPEAMENTO_TIMES.get(casa.lower(), casa.lower()).replace(" ", "_")
        nome_fora = MAPEAMENTO_TIMES.get(fora.lower(), fora.lower()).replace(" ", "_")
        emoji_casa = EMOJI_TIMES.get(nome_casa, "⚽")
        emoji_fora = EMOJI_TIMES.get(nome_fora, "⚽")

        utc_time = datetime.fromisoformat(partida['fixture']['date'].replace("Z", "+00:00"))
        br_time = utc_time.astimezone(pytz.timezone("America/Sao_Paulo"))
        horario_br = br_time.strftime("%H:%M")

        # --------------------------------------------------------------------
        # 5.1) ABRIR APOSTAS (1H)
        # --------------------------------------------------------------------
        canal_apostas = bot.get_channel(CANAL_APOSTAS_ID)
        if not canal_apostas:
            logging.error("❌ Canal de apostas não encontrado.")
            continue
        if status == "1h" and anterior["status"] != "1h":
            deadline_utc = datetime.utcnow() + timedelta(minutes=10)
            try:
                cargo_futebol = "<@&1437851100878344232>" 
                embed = discord.Embed(
                title="🏆 Apostas Abertas Agora!",
                description=(
                    f"⏰ Horário: {horario_br} (BR)\n\n"
                    f"📢 {cargo_futebol} reaja para apostar:"
                ),
                color=discord.Color.blue()
            )
                
                embed.add_field(name=f"{emoji_casa} {casa}", value="Casa", inline=True)
                embed.add_field(name=f"{emoji_fora} {fora}", value="Visitante", inline=True)
                embed.add_field(name=f"{EMOJI_EMPATE} Empate", value="Empate", inline=True)
                embed.set_footer(text="Apostas abertas por 10 minutos!")

                if partida["league"]["id"] == 13:
                    await canal_apostas.send(
                        "🏆 **APOSTAS ABERTAS PARA A LIBERTADORES!**\n"
                        "https://tenor.com/view/libertadores-copa-libertadores-conmebol-libertadores-a-gl%C3%B3ria-eterna-gif-26983587"
                    )
                mensagem = await canal_apostas.send(
                    content=cargo_futebol,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )
                
                await mensagem.add_reaction(emoji_casa)
                logging.info(f"✅ Reação {emoji_casa} adicionada à mensagem {mensagem.id}")
                await mensagem.add_reaction(emoji_fora)
                logging.info(f"✅ Reação {emoji_fora} adicionada à mensagem {mensagem.id}")
                await mensagem.add_reaction(EMOJI_EMPATE)
                logging.info(f"✅ Reação {EMOJI_EMPATE} adicionada à mensagem {mensagem.id}")

                marcar_jogo_como_open(
                    fixture_id=fixture_id,
                    message_id=mensagem.id,
                    home=casa,
                    away=fora,
                    deadline_utc=deadline_utc,
                    canal_id=CANAL_JOGOS_ID,
                    data_jogo=br_time.date().isoformat(),
                    horario_jogo=br_time.time().strftime("%H:%M:%S")
                )
            except Exception as e:
                logging.error(f"❌ Erro ao abrir apostas: {e}")

        # --------------------------------------------------------------------
        # 5.2) NOTIFICAÇÃO DE GOLS
        # --------------------------------------------------------------------
        try:
            gols_anteriores_casa = anterior["home"]
            gols_anteriores_fora = anterior["away"]

            if gols_casa > gols_anteriores_casa:
                key_home = MAPEAMENTO_TIMES.get(casa.lower(), casa.lower())
                frase_home = PALAVRAS_GOL.get(key_home, f"⚽ GOOOOOOOL DO {casa.upper()}!")
                embed = discord.Embed(
                    title=frase_home,
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Placar",
                    value=f"{emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
                    inline=False
                )
                role_home_name = key_home
                role_home = discord.utils.get(canal.guild.roles, name=role_home_name)
                mention_home = role_home.mention if role_home else f"@{role_home_name}"
                await canal.send(content=f"{mention_home} {frase_home}", embed=embed)

            if gols_fora > gols_anteriores_fora:
                key_away = MAPEAMENTO_TIMES.get(fora.lower(), fora.lower())
                frase_away = PALAVRAS_GOL.get(key_away, f"⚽ GOOOOOOOL DO {fora.upper()}!")
                embed = discord.Embed(
                    title=frase_away,
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Placar",
                    value=f"{emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
                    inline=False
                )
                role_away_name = key_away
                role_away = discord.utils.get(canal.guild.roles, name=role_away_name)
                mention_away = role_away.mention if role_away else f"@{role_away_name}"
                await canal.send(content=f"{mention_away} {frase_away}", embed=embed)

        except Exception as e:
            logging.error(f"❌ Erro ao enviar notificação de gol: {e}")

        # --------------------------------------------------------------------
        # 5.3) PROCESSAR FIM DE JOGO + APOSTAS
        # --------------------------------------------------------------------
        try:
            if status in ("ft", "aet", "pen"):

                # 🔎 Checar se já foi processado
                conn = conectar_futebol()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT processado FROM jogos WHERE fixture_id = %s", (fixture_id,))
                row = cursor.fetchone()

                if row and row["processado"] == 1:
                    logging.warning(f"⚠️ Jogo {fixture_id} já foi processado anteriormente. Pulando.")
                    cursor.close()
                    conn.close()
                    placares[fixture_id] = {
                        "home": gols_casa,
                        "away": gols_fora,
                        "status": status
                    }
                    continue

                # Determinar vencedor
                if gols_casa > gols_fora:
                    resultado_final = "home"
                elif gols_fora > gols_casa:
                    resultado_final = "away"
                else:
                    resultado_final = "draw"

                # Buscar apostas
                cursor.execute("SELECT user_id, palpite FROM apostas WHERE fixture_id = %s", (fixture_id,))
                apostas = cursor.fetchall()

                # Contagem por palpite para bônus de minoria
                contagem = {"home": 0, "away": 0, "draw": 0}
                for a in apostas:
                    p = a["palpite"]
                    if p in contagem:
                        contagem[p] += 1
                votos_vencedor = contagem.get(resultado_final, 0)
                votos_max = max(contagem.values()) if contagem else 0
                bonus_minoria = votos_vencedor > 0 and votos_vencedor < votos_max

                mensagens_pv = []
                for aposta in apostas:
                    user_id = aposta["user_id"]
                    palpite = aposta["palpite"]
                    acertou = (palpite == resultado_final)
                    pontos_base = 30 if (acertou and bonus_minoria) else 15
                    pontos = pontos_base if acertou else -7

                    usuario_dm = bot.get_user(int(user_id))
                    nome_discord = f"{usuario_dm.name}#{usuario_dm.discriminator}" if usuario_dm else str(user_id)
                    cursor.execute(
                        """
                        INSERT INTO pontuacoes (user_id, nome_discord, pontos)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE pontos = pontos + VALUES(pontos), nome_discord = VALUES(nome_discord)
                        """,
                        (user_id, nome_discord, pontos)
                    )

                    if acertou:
                        mensagens_pv.append(
                            (user_id, f"<:JinxKissu:1408843869784772749> Você **acertou** o resultado de **{casa} x {fora}**!\n➡️ **+{pontos} pontos**" + (" (bônus de minoria)" if bonus_minoria else ""))
                        )
                    else:
                        mensagens_pv.append(
                            (user_id, f"❌ Você **errou** o resultado de **{casa} x {fora}**.\n➡️ **-7 pontos**")
                        )

                # 🔥 Marca como processado
                cursor.execute("UPDATE jogos SET processado = 1, finalizado = 1 WHERE fixture_id = %s", (fixture_id,))
                conn.commit()
                cursor.close()
                conn.close()

                logging.info(f"✔️ Pontuação processada e jogo {fixture_id} marcado como processado.")

                # Embed final
                embed_final = discord.Embed(
                    title=f"🏁 Fim de jogo — {casa} x {fora}",
                    description=f"Placar final: {emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
                    color=discord.Color.orange()
                )
                embed_final.set_footer(text="Obrigado por participar das apostas!")
                await canal.send(embed=embed_final)

                # Enviar DMs
                for user_id, msg in mensagens_pv:
                    usuario = bot.get_user(int(user_id))
                    if usuario:
                        try:
                            await usuario.send(msg)
                        except:
                            pass

        except Exception as e:
            logging.error(f"❌ Erro ao processar apostas do fim de jogo: {e}")

        # --------------------------------------------------------------------
        # 5.4) Atualizar placares
        # --------------------------------------------------------------------
        placares[fixture_id] = {
            "home": gols_casa,
            "away": gols_fora,
            "status": status
        }


PRECOS = {
    "jinxed_vip": 1000,
    "ticket_reaposta": 200,
    "som_entrada": 300,
    "cor_personalizada": 250,
    "badge_perfil": 500,
    "limite_apostas_extra": 350,
    "caixa_misteriosa": 50,
    "caixinha": 50,
    "segunda_chance": 30,
    "clown_bet": 20
}
#LOJA DE PONTOS----------------------------------


def atualizar_pontos(user_id: int, valor: int, nome_discord: str = None):
    conn = conectar_futebol()
    cursor = conn.cursor()
    if nome_discord is None:
        u = bot.get_user(int(user_id))
        nome_discord = f"{u.name}#{u.discriminator}" if u else str(user_id)
    cursor.execute(
        "INSERT INTO pontuacoes (user_id, nome_discord, pontos) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE pontos = pontos + VALUES(pontos), nome_discord = VALUES(nome_discord)",
        (user_id, nome_discord, valor)
    )
    conn.commit()
    conn.close()


@bot.command()
async def comprar_item(ctx, item_nome: str):
    user_id = ctx.author.id
    item = item_nome.lower()

    if item not in PRECOS:
        await ctx.send("❌ Item não encontrado na loja!")
        return

    preco = PRECOS[item]

    try:
        # Abrir conexão
        conn = conectar_futebol()
        cursor = conn.cursor()

        # Buscar pontos do usuário na tabela correta
        cursor.execute("SELECT pontos FROM pontuacoes WHERE user_id = %s", (user_id,))
        resultado = cursor.fetchone()
        pontos = resultado[0] if resultado else 0

        if pontos < preco:
            await ctx.send(f"<:Jinxsip1:1390638945565671495> Você precisa de {preco} pontos para comprar este item. Você tem {pontos} pontos.")
            return

        # Descontar pontos
        atualizar_pontos(user_id, -preco)

        # ===========================
        # ITEM VIP
        # ===========================
        if item == "jinxed_vip":
            cargo = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
            if cargo:
                data_compra = datetime.utcnow()
                data_expira = data_compra + timedelta(days=15)
                cursor.execute(
                    "INSERT INTO loja_vip (user_id, cargo_id, data_compra, data_expira, ativo) VALUES (%s, %s, %s, %s, 1)",
                    (user_id, cargo.id, data_compra, data_expira)
                )
                await ctx.author.add_roles(cargo)
                await ctx.send(f"✅ Parabéns! Você comprou o cargo **Jinxed Vip** por 15 dias!")
            else:
                await ctx.send("⚠️ Cargo 'Jinxed Vip' não encontrado no servidor.")

        # ===========================
        # ITEM SEGUNDA CHANCE
        # ===========================
        elif item == "segunda_chance":
            cursor.execute(
                "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
                (user_id, item, preco, datetime.utcnow())
            )
            await ctx.send("🎯 Você comprou **Segunda Chance**! Ela será usada automaticamente na sua próxima aposta perdida.")

        # ===========================
        # ITEM CAIXINHA DE SURPRESA
        # ===========================
        elif item == "caixinha":
            cursor.execute(
                "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'caixinha' AND DATE(data_compra) = UTC_DATE()",
                (user_id,)
            )
            limite_hoje = cursor.fetchone()[0]
            if limite_hoje >= 3:
                atualizar_pontos(user_id, preco)
                await ctx.send("⏳ Você já usou a **Caixinha** 3 vezes hoje. Tente novamente amanhã.")
                return

            pontos_sorteados = random.randint(10, 100)
            atualizar_pontos(user_id, pontos_sorteados)
            cursor.execute(
                "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
                (user_id, item, preco, datetime.utcnow())
            )
            await ctx.send(f"🎁 Você abriu a **Caixinha de Surpresa** e ganhou **{pontos_sorteados} pontos**!")

        # ===========================
        # ITEM CLOWN BET
        # ===========================
        elif item == "clown_bet":
            cursor.execute(
                "INSERT INTO clown_bet (user_id, ativo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE ativo = 1",
                (user_id,)
            )
            await ctx.send("🤡 Você ativou a **Clown Bet**! Próxima aposta: 6x se acertar, 4x se errar.")

        # Commit e fechar
        conn.commit()

    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro ao comprar o item: {e}")

    finally:
        cursor.close()
        conn.close()


@tasks.loop(minutes=30)
async def verificar_vips_expirados():
    conn = conectar_futebol()
    cursor = conn.cursor()
    agora = datetime.utcnow()

    cursor.execute(
        "SELECT user_id, cargo_id FROM loja_vip WHERE ativo = 1 AND data_expira <= %s",
        (agora,)
    )
    resultados = cursor.fetchall()

    for user_id, cargo_id in resultados:
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            cargo = discord.utils.get(guild.roles, id=cargo_id)
            if member and cargo:
                try:
                    await member.remove_roles(cargo)
                    await member.send(f"⏰ Seu VIP **{cargo.name}** expirou e foi removido.")
                except Exception:
                    pass

        cursor.execute(
            "UPDATE loja_vip SET ativo = 0 WHERE user_id = %s AND cargo_id = %s",
            (user_id, cargo_id)
        )

    conn.commit()
    conn.close()

CANAL_PERMITIDO_ID = 1380564680774385724

@bot.command()
async def loja(ctx):
    if ctx.channel.id != CANAL_PERMITIDO_ID:
        return await ctx.send(f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.")  
    embed = discord.Embed(
        title="🛒 Loja de Pontos",
        description="Use seus pontos para comprar benefícios!",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🎭 Modo Clown — 20 pontos",
        value="• Multiplica pontos por 6 se acertar\n• Mas perde 4x se errar\n• Uso único\n• Use **clown_bet**  ",
        inline=False
    )

    embed.add_field(
        name="🎁 Caixa Surpresa — 50 pontos",
        value="• Ganha pontos aleatórios de 10 a 100\n• Pode vir até negativo 👀\n• Use **caixinha** ",
        inline=False
    )


    embed.add_field(
        name="<:discotoolsxyzicon_6:1444750406763679764> Jinxed VIP — 1000 pontos",
        value="• Garante 15 dias do cargo VIP\n• Use **jinxed_vip**",
        inline=False
    )

    embed.add_field(
        name="⏪ Segunda Chance — 30 pontos",
        value="• Recupera a última aposta perdida\n• Uso único\n• Use **segunda_chance**",
        inline=False
    )

    embed.set_footer(text="Use: !comprar <item>")
    await ctx.send(embed=embed)



@bot.command()
async def comprar(ctx, item_nome: str):
    user_id = ctx.author.id
    item = item_nome.lower()

    # Verifica se o comando foi usado no canal permitido
    if ctx.channel.id != CANAL_PERMITIDO_ID:
        return await ctx.send(f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.")

    if item not in PRECOS:
        return await ctx.send("❌ Item não encontrado na loja! Use `!loja` para ver os itens.")

    preco = PRECOS[item]

    # Verifica saldo
    pontos = pegar_pontos(user_id)
    if pontos < preco:
        return await ctx.send(f"<:Jinxsip1:1390638945565671495> Você precisa de {preco} pontos para comprar este item. Você tem {pontos} pontos.")

    # Desconta pontos
    adicionar_pontos_db(user_id, -preco)

    # Entregar itens
    if item == "jinxed_vip":
        cargo = discord.utils.get(ctx.guild.roles, name="Jinxed Vip")
        if cargo:
            data_compra = datetime.utcnow()
            data_expira = data_compra + timedelta(days=15)
            con = conectar_futebol()
            cur = con.cursor()
            cur.execute(
                "INSERT INTO loja_vip (user_id, cargo_id, data_compra, data_expira, ativo) VALUES (%s, %s, %s, %s, 1)",
                (user_id, cargo.id, data_compra, data_expira)
            )
            con.commit()
            con.close()
            await ctx.author.add_roles(cargo)
            await ctx.send(f"<:discotoolsxyzicon_6:1444750406763679764> Parabéns! Você comprou o cargo **Jinxed Vip** por 15 dias!")
            logging.info(f"{ctx.author.name} comprou o cargo Jinxed Vip por 15 dias.")
        else:
            await ctx.send("⚠️ Cargo 'Jinxed Vip' não encontrado no servidor.")

    elif item == "segunda_chance":
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send("🎯 Você comprou **Segunda Chance**! Pode recuperar pontos na próxima aposta perdida.")

    elif item == "caixinha":
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'caixinha' AND DATE(data_compra) = UTC_DATE()",
            (user_id,)
        )
        limite_hoje = cur.fetchone()[0]
        if limite_hoje >= 3:
            adicionar_pontos_db(user_id, preco)
            con.close()
            await ctx.send("⏳ Você já usou a **Caixinha** 3 vezes hoje. Tente novamente amanhã.")
            return

        pontos_sorteados = random.randint(10, 100)
        adicionar_pontos_db(user_id, pontos_sorteados)
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send(f"🎁 Você abriu a **Caixinha de Surpresa** e ganhou **{pontos_sorteados} pontos!**")

    elif item == "clown_bet":
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO clown_bet (user_id, ativo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE ativo = 1",
            (user_id,)
        )
        con.commit()
        con.close()
        await ctx.send("🤡 Você ativou a **Clown Bet**! Próxima aposta: 6x se acertar, 4x se errar.")

def processar_aposta(user_id, fixture_id, resultado, pontos_base):
    conn = conectar_futebol()
    cursor = conn.cursor()

    # 1️⃣ Verificar aposta do usuário
    cursor.execute(
        "SELECT palpite, modo_clown FROM apostas WHERE user_id = %s AND fixture_id = %s",
        (user_id, fixture_id)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return  # Sem aposta feita

    aposta_usuario, modo_clown = row

    multiplicador_vitoria = 1
    multiplicador_derrota = 1
    if modo_clown == 1:
        multiplicador_vitoria = 6
        multiplicador_derrota = 4
        cursor.execute("UPDATE apostas SET modo_clown = 0 WHERE user_id = %s AND fixture_id = %s",
                       (user_id, fixture_id))
        logging.info(f"Usuário {user_id} usou Clown Bet!")

    # 3️⃣ Calcular pontos ganhos ou perdidos
    if aposta_usuario == resultado:
        pontos_final = pontos_base * multiplicador_vitoria
        adicionar_pontos_db(user_id, pontos_final)
        logging.info(f"Usuário {user_id} acertou! Ganhou {pontos_final} pontos.")
    else:
        # 4️⃣ Verificar Segunda Chance
        cursor.execute(
            "SELECT id FROM loja_pontos WHERE user_id = %s AND item = 'segunda_chance' AND ativo = 1",
            (user_id,)
        )
        row_chance = cursor.fetchone()
        if row_chance:
            # Consumir Segunda Chance
            cursor.execute("UPDATE loja_pontos SET ativo = 0 WHERE id = %s", (row_chance[0],))
            adicionar_pontos_db(user_id, pontos_base)  # devolve os pontos
            logging.info(f"Usuário {user_id} perdeu, mas usou Segunda Chance! Pontos devolvidos: {pontos_base}")
        else:
            pontos_final = -pontos_base * multiplicador_derrota
            adicionar_pontos_db(user_id, pontos_final)
            logging.info(f"Usuário {user_id} perdeu! Perdeu {abs(pontos_final)} pontos.")

    conn.commit()
    conn.close()


@bot.command()
@commands.has_permissions(administrator=True)
async def terminar_jogo(ctx, fixture_id: int = None):
    logging.info(f"Administrador {ctx.author} solicitou o término de jogo(s) com fixture_id {fixture_id}.")
    try:
        conn = conectar_futebol()
        cursor = conn.cursor(dictionary=True)

        alvos = []
        if fixture_id is None:
            cursor.execute("SELECT fixture_id FROM jogos WHERE finalizado = 0")
            alvos = [r["fixture_id"] for r in cursor.fetchall()] if cursor.rowcount else []
            if not alvos:
                await ctx.send("⚠️ Nenhum jogo pendente encontrado. Use `!terminar_jogo <fixture_id>`.")
                conn.close()
                return
        else:
            alvos = [fixture_id]

        processados = 0
        for fx in alvos:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL, headers=HEADERS, params={"id": fx}) as response:
                    data = await response.json()

            if not data.get("response"):
                await ctx.send(f"❌ Jogo {fx} não encontrado na API.")
                continue

            partida = data["response"][0]
            casa = partida["teams"]["home"]["name"]
            fora = partida["teams"]["away"]["name"]
            gols_casa = partida["goals"]["home"] or 0
            gols_fora = partida["goals"]["away"] or 0
            status = partida["fixture"]["status"]["short"].lower()

            if status not in ("ft", "aet", "pen"):
                await ctx.send(f"⚠️ Jogo {fx} ainda não finalizou (status: {status}).")
                continue

            if gols_casa > gols_fora:
                resultado_final = "home"
            elif gols_fora > gols_casa:
                resultado_final = "away"
            else:
                resultado_final = "draw"

            cursor.execute("SELECT processado FROM jogos WHERE fixture_id = %s", (fx,))
            row = cursor.fetchone()
            if row and row.get("processado") == 1:
                await ctx.send(f"⚠️ Jogo {fx} já foi processado.")
                continue

            cursor.execute("SELECT user_id, palpite FROM apostas WHERE fixture_id = %s", (fx,))
            apostas = cursor.fetchall()

            contagem = {"home": 0, "away": 0, "draw": 0}
            for a in apostas:
                p = a["palpite"]
                if p in contagem:
                    contagem[p] += 1
            votos_vencedor = contagem.get(resultado_final, 0)
            votos_max = max(contagem.values()) if contagem else 0
            bonus_minoria = votos_vencedor > 0 and votos_vencedor < votos_max

            mensagens_pv = []
            for aposta in apostas:
                user_id = aposta["user_id"]
                palpite = aposta["palpite"]
                acertou = (palpite == resultado_final)
                pontos_base = 30 if (acertou and bonus_minoria) else 15
                pontos = pontos_base if acertou else -7
                usuario_dm = bot.get_user(int(user_id))
                nome_discord = f"{usuario_dm.name}#{usuario_dm.discriminator}" if usuario_dm else str(user_id)
                cursor.execute(
                """
                INSERT INTO pontuacoes (user_id, nome_discord, pontos)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE pontos = pontos + VALUES(pontos), nome_discord = VALUES(nome_discord)
                """,
                (user_id, nome_discord, pontos)
            )
                if acertou:
                    mensagens_pv.append(
                        (
                            user_id,
                            f"<a:270795discodance:1419694558945476760> **APOSTA CERTA!**\n"
                            f"✨ Você garantiu **+{pontos} pontos**" + (" (bônus de minoria)" if bonus_minoria else "") + "!\n\n"
                            f"🏟️ **Partida:** `{casa} x {fora}`\n\n"
                            f"<:apchikabounce:1408193721907941426> Confira seus pontos com **!meuspontos**\n"
                            f"📘 Veja mais comandos em **!info**"
                        )
                    )
                    
                else:
                    mensagens_pv.append(
                        (
                            user_id,
                            f"😬 **Que pena... você errou a aposta!**\n"
                            f"Você perdeu **-7 pontos**.\n\n"
                            f"🏟️ **Partida:** `{casa} x {fora}`\n\n"
                            f"ℹ️ Veja seus pontos com **!meuspontos**\n"
                            f"📘 Mais informações: **!info**"
                        )
                        
                    )

            cursor.execute("UPDATE jogos SET processado = 1, finalizado = 1 WHERE fixture_id = %s", (fx,))
            conn.commit()

            nome_casa = MAPEAMENTO_TIMES.get(casa.lower(), casa.lower()).replace(" ", "_")
            nome_fora = MAPEAMENTO_TIMES.get(fora.lower(), fora.lower()).replace(" ", "_")
            emoji_casa = EMOJI_TIMES.get(nome_casa, "⚽")
            emoji_fora = EMOJI_TIMES.get(nome_fora, "⚽")

            embed_final = discord.Embed(
                title=f"🏁 Fim de jogo — {casa} x {fora}",
                description=f"Placar final: {emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
                color=discord.Color.orange()
            )
            embed_final.set_footer(text="Obrigado por participar das apostas!")

            canal = bot.get_channel(CANAL_JOGOS_ID)
            if canal:
                await canal.send(embed=embed_final)

            for user_id, msg in mensagens_pv:
                usuario = bot.get_user(int(user_id))
                if usuario:
                    try:
                        await usuario.send(msg)
                    except:
                        pass

            processados += 1

        cursor.close()
        conn.close()

        if processados == 0:
            await ctx.send("⚠️ Nenhum jogo foi processado.")
        elif processados == 1:
            await ctx.send("✅ 1 jogo finalizado manualmente. Pontuações aplicadas.")
            logging.info("1 jogo finalizado manualmente. Pontuações aplicadas.")
        else:
            await ctx.send(f"✅ {processados} jogos finalizados manualmente. Pontuações aplicadas.")
            logging.info(f"{processados} jogos finalizados manualmente. Pontuações aplicadas.")

    except Exception as e:
        await ctx.send(f"❌ Erro ao finalizar jogos: {e}")
        logging.error(f"Erro ao finalizar jogos: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def fixture_id(ctx):
    logging.info(f"Administrador {ctx.author} solicitou o painel de comandos administrativos.")
    try:
        conn = conectar_futebol()
        cursor = conn.cursor()

        cursor.execute("SELECT fixture_id, home, away, data, horario FROM jogos WHERE finalizado = 0")
        logging.info("Executando consulta para buscar jogos pendentes.")
        jogos = cursor.fetchall()
        cursor.close()
        conn.close()

        if not jogos:
            await ctx.send("⚠️ Nenhum jogo pendente encontrado.")
            return

        mensagem = "🏟️ **Jogos Pendentes:**\n"
        for jogo in jogos:
            fixture_id, home, away, data_jogo, horario_jogo = jogo
            mensagem += f"- ID: `{fixture_id}` | {home} x {away} | Data: {data_jogo} | Horário: {horario_jogo}\n"

        await ctx.send(mensagem)
        logging.info(f"Enviado para {ctx.author}: {mensagem}")
    except Exception as e:
        await ctx.send(f"❌ Erro ao buscar jogos pendentes: {e}")
        logging.error(f"Erro ao buscar jogos pendentes: {e}")

ID_AMORREBA = 428006047630884864

@commands.has_permissions(administrator= True)
@bot.command()
async def resetar_jogo(ctx):
    if ctx.author.id != ID_AMORREBA:
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        logging.info(f"Alguém ({ctx.author}) tentou usar o comando resetar_jogo sem permissão.")
        return
    try:
        conn = conectar_futebol()
        cursor = conn.cursor()

        cursor.execute("TRUNCATE TABLE jogos")
        conn.commit()
        cursor.close()
        conn.close()
        await ctx.send("🧼 Todos os jogos foram resetados com sucesso! Tabela limpa e preparada para novos eventos.")
        logging.info("Todos os jogos foram resetados com sucesso! Tabela limpa e preparada para novos eventos.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao resetar jogos: {e}")
        logging.error(f"Erro ao resetar jogos: {e}")

@bot.command()
async def info(ctx):
    embed = discord.Embed(
        title="📜 Lista de Comandos",
        description="Aqui estão os comandos disponíveis no bot:",
        color=discord.Color.blue()
    )

    # Comandos de música
    embed.add_field(
        name="🎵 Música",
        value=(
            "`!tocar <link>` - Toca a música do link informado.\n"
            "`!pular` - Pula a música atual.\n"
            "`!parar` - Para a música que está tocando."
        ),
        inline=False
    )

    # Comandos de apostas/loja
    embed.add_field(
        name="🎲 Apostas, Pontos e Loja",
        value=(
            "`!comprar_item <nome>` - Compra um item da loja usando seus pontos.\n"
            "`!meuspontos` - Mostra quantos pontos você tem.\n"
            "`!loja` - Indica a loja para compra."
        ),
        inline=False
    )

    # Comandos de Time
    embed.add_field(
        name="⚽ Times de Futebol",
        value=(
            "`!time <nome>` - Seleciona o time e recebe o cargo correspondente.\n"
            "`!lista_times` - Mostra todos os times disponíveis para escolha.\n"
            "`!torcedores` - Mostra os torcedores do time informado."
            

        ),
        inline=False
    )

    embed.add_field(
        name="🎰 Melhores apostadores",
        value=(
            "`!top_apostas` - Mostra os 5 melhores apostadores do servidor."
            
        ),
        inline=False
    )

    await ctx.send(embed=embed)
    logging.info(f"Usuário {ctx.author} solicitou a lista de comandos.")

#LISTAR OS 5 MAIORES COM PONTUACOES DE APOSTAS
@bot.command()
async def top_apostas(ctx):
    conn = conectar_futebol()
    cursor = conn.cursor()
    cursor.execute("SELECT nome_discord, pontos FROM pontuacoes ORDER BY pontos DESC LIMIT 5")
    top = cursor.fetchall()
    cursor.close()
    conn.close()

    if not top:
        return await ctx.send("⚠️ Nenhum usuário possui pontos.")

    # Formata a mensagem
    mensagem = "🏆 **Top 5 Usuários com Mais Pontos:**\n"
    for pos, (nome, pontos) in enumerate(top, start=1):
        mensagem += f"{pos}. **{nome}** - {pontos} pontos\n"

    await ctx.send(mensagem)
    logging.info(f"Usuário {ctx.author} solicitou ver os 5 melhores apostadores.")


CANAL_COMANDOS = 1380564680774385724

@bot.command()
async def time(ctx, *, nome_time: str):
    if ctx.channel.id != CANAL_COMANDOS:
        return await ctx.send("<:480700twinshout:1443957065230844066> Este comando pode ser usado apenas no canal <#1380564680774385724>.")
    logging.info(f"Alguém ({ctx.author}) tentou usar o comando time em um canal diferente ({ctx.channel.id}).")
    if nome_time is None:
        return await ctx.send("<:Jinx_Watching:1390380695712694282> Desculpa, mas você precisa informar o nome do time")
    

    nome = nome_time.lower().strip()
    if nome not in MAPEAMENTO_TIMES:
        return await ctx.send("<:3894307:1443956354698969149> Desculpa, mas eu não reconheço esse time")

    time_normalizado = MAPEAMENTO_TIMES[nome]

    # Nome do cargo bonito (primeira letra maiúscula)
    cargo_nome = time_normalizado.title()

    #------Banco------
    conn = conectar_futebol()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO times_usuarios (user_id, time_normalizado)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE time_normalizado = VALUES(time_normalizado)
    """, (ctx.author.id, time_normalizado))
    conn.commit()
    cursor.close()
    conn.close()

    role_id = ROLE_IDS_TIMES.get(time_normalizado)
    cargo = None
    if role_id:
        cargo = discord.utils.get(ctx.guild.roles, id=role_id)
    if not cargo:
        cargo = discord.utils.get(ctx.guild.roles, name=cargo_nome)
    if not cargo:
        cargo = await ctx.guild.create_role(name=cargo_nome)

    await ctx.author.add_roles(cargo)
    
    logging.info(f"Usuário {ctx.author} se registrou como torcedor do time {cargo_nome} (ID: {cargo.id}).")


    await ctx.send(f"<a:995589misathumb:1443956356846719119> {ctx.author.mention}, agora você está registrado como torcedor do **{cargo_nome}**!")



@bot.command()
async def lista_times(ctx):
    def emoji_do_time(nome: str) -> str:
        base = nome.strip().lower()
        e = EMOJI_TIMES.get(base) or EMOJI_TIMES.get(base.replace(" ", "_"))
        if e:
            return e
        for k, v in EMOJI_TIMES.items():
            if k.replace("_", " ").lower() == base:
                return v
        return "❓"

    times = sorted(ROLE_IDS_TIMES.keys())
    linhas = [f"{emoji_do_time(t)} | {t.title()}" for t in times]
    embed = discord.Embed(title="📋 Times Disponíveis", description="\n".join(linhas), color=discord.Color.blue())
    await ctx.send(embed=embed)
    logging.info(f"Usuário {ctx.author} solicitou a lista de times.")

#Mostrar os torcedores do servidor
@bot.command()
async def torcedores(ctx):
    try:
        conn = conectar_futebol()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, time_normalizado FROM times_usuarios")
        rows = cursor.fetchall()
        if not rows:
            return await ctx.send("Nenhum torcedor registrado no servidor.")
        
        torcedores = {}

        for user_id, time_normalizado in rows:
            if time_normalizado not in torcedores:
                torcedores[time_normalizado] = []
            torcedores[time_normalizado].append(user_id)
        embed = discord.Embed(
            title="🏟️ Torcedores por Time",
            color=discord.Color.blue()
        )
        DISPLAY_NOMES = {
            "galo": "Atlético-MG",
            "sao paulo": "São Paulo",
            "gremio": "Grêmio",
            "ceara": "Ceará",
            "vitoria": "Vitória",
            "atletico paranaense": "Athletico-PR",
            "lanus": "Lanús",
        }
        itens = []
        for time, usuarios in torcedores.items():
            base = time.strip().lower()
            display = DISPLAY_NOMES.get(base, time.title())
            emoji = EMOJI_TIMES.get(base) or EMOJI_TIMES.get(base.replace(" ", "_")) or "⚽"
            mencoes = "\n".join(f"<@{uid}>" for uid in usuarios)
            itens.append((display, emoji, mencoes))
        itens.sort(key=lambda x: x[0])
        for display, emoji, mencoes in itens:
            embed.add_field(name=f"{emoji} | {display}", value=mencoes, inline=False)
        await ctx.send(embed=embed)
        logging.info(f"Usuário {ctx.author} solicitou a lista de torcedores.")

        cursor.close()
        conn.close()
    except Exception as e:
        logging.info(f"Ocorreu um erro ao listar os torcedores: {e}")
        await ctx.send(f"Ocorreu um erro ao listar os torcedores: {e}")



# ----- CÓDIGO PARA VER TODOS OS COMANDOS ADMIN -----
@bot.command() 
@commands.has_permissions(administrator=True)
async def admin(ctx):
    embed = discord.Embed(
        title="🛠️ Painel de Comandos Administrativos",
        description="Aqui estão todos os comandos disponíveis para administradores:",
        color=discord.Color.red()
    )

    embed.add_field(
        name="🔧 Administração Geral",
        value=(
            "**!top_apostas** — mostra top jogadores nas apostas\n"
            "**!resetar_jogo** — limpa as apostas de um jogo\n"
            "**!fixture_id** — busca informações de uma partida\n"
            "**!terminar_jogo** — finaliza e processa resultados\n"
        ),
        inline=False
    )

    embed.add_field(
        name="<:discotoolsxyzicon_6:1444750406763679764> Sistema VIP",
        value=(
            "**!dar_vip** — concede VIP ao usuário\n"
            "**!remover_vip** — remove VIP do usuário\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🛰️ API",
        value=(
            "**!apistart** — inicia a sincronização com a API\n"
            "**!apistop** — para a sincronização\n"
        ),
        inline=False
    )

    embed.add_field(
        name="📨 Utilidades",
        value="**!enviar_mensagem** — envia uma mensagem para um canal",
        inline=False
    )

    embed.set_footer(text="Use com responsabilidade. 😉")
    logging.info(f"Administrador {ctx.author} solicitou o painel de comandos administrativos.")

    await ctx.send(embed=embed)




bot.run(TOKEN)
async def enviar_alerta(moderador_id: int, total: int):
    try:
        admins = [428006047630884864, 614476239683584004]
        for admin_id in admins:
            admin = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
            if admin:
                await admin.send(
                    "⚠️ Alerta de possível abuso de moderação\n\n"
                    f"O moderador <@{moderador_id}> recebeu denúncias de {total} usuários diferentes.\n"
                    "Verifique o caso no painel / banco de dados."
                )
        conn = conectar_vips()
        c = conn.cursor()
        c.execute("DELETE FROM moderador_alertas WHERE moderador_id = %s", (moderador_id,))
        conn.commit()
        c.close()
        conn.close()
        logging.info(f"Contador de denúncias zerado para moderador {moderador_id}")
    except Exception as e:
        logging.error(f"Erro ao enviar alerta/zerar contador: {e}")
