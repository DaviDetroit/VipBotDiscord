from calendar import c
import discord
from discord.ext import commands, tasks
from discord import app_commands, channel
import os
from dotenv import load_dotenv
import asyncio
import json
import random
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, timedelta, timezone, time  # <- corrigido aqui
from calendar import monthrange
import time as time_module
from discord.ui import Button, View
import pytz
import requests
import logging
import aiohttp
import aiomysql
import traceback
from io import BytesIO



load_dotenv()

logging.basicConfig(
    level = logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S' 
)

# ============================
# CONFIGURAÇÕES DE ARQUIVO
# ============================
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB (limite Discord)
WARN_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB (aviso para arquivos grandes)
DOWNLOAD_TIMEOUT = 60  # 60 segundos timeout para download


def conectar(database_name: str):
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        port=os.getenv("DB_PORT"),
        password=os.getenv("DB_PASSWORD"),
        database=database_name,
        ssl_disabled=True,
        auth_plugin="mysql_native_password",
        autocommit=True,
        connection_timeout=10,
        use_pure=True  
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
fuso_br = pytz.timezone("America/Sao_Paulo")

bot = commands.Bot(command_prefix="!", intents=intents)

# Configurar tree para slash commands
GUILD_ID = 1380564679084081175  # ID do servidor principal

# Sincronizar comandos quando o bot estiver pronto
@bot.event
async def setup_hook():
    guild = bot.get_guild(GUILD_ID)
    await bot.tree.sync(guild=guild)
    logging.info(f"✅ Slash commands sincronizados na guild {GUILD_ID}!")

    
    
# Evento de erro para slash commands
@bot.tree.error
async def on_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏰ Espere {error.retry_after:.1f}s para usar este comando novamente!",
            ephemeral=True
        )
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando!",
            ephemeral=True
        )
    else:
        logging.error(f"Erro em slash command: {error}")
        await interaction.response.send_message(
            "❌ Ocorreu um erro ao executar este comando.",
            ephemeral=True
        )

# ============ SLASH COMMANDS PRINCIPAIS ============

@bot.tree.command(name="pontos", description="Veja quantos pontos você tem")
async def slash_pontos(interaction: discord.Interaction):
    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    pontos = pegar_pontos(interaction.user.id)

    await interaction.response.send_message(
        f"<a:565724creditcard:1467671052053254235> {interaction.user.mention}, você tem **{pontos} pontos**!",
        ephemeral=True
    )

@bot.tree.command(name="loja", description="Veja os itens disponíveis na loja")
async def slash_loja(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    await interaction.response.send_message(
        embed=gerar_embed_loja()
    )

@bot.tree.command(name="compras", description="Veja seus itens ativos na loja")
async def compras(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    user_id = interaction.user.id
    con = conectar_futebol()
    cur = con.cursor(dictionary=True)

    itens_ativos = []


    cur.execute("""
        SELECT data_expira 
        FROM loja_vip 
        WHERE user_id = %s AND ativo = 1
    """, (user_id,))
    
    vip = cur.fetchone()
    if vip:
        itens_ativos.append(
            f"<:discotoolsxyzicon_6:1444750406763679764> **VIP** — expira em `{vip['data_expira']}`"
        )

   
    cur.execute("""
        SELECT ativo 
        FROM clown_bet 
        WHERE user_id = %s AND ativo = 1
    """, (user_id,))

    if cur.fetchone():
        itens_ativos.append(
            "🎭 **Modo Clown** — ativo para a próxima aposta"
        )

    
    cur.execute("""
        SELECT item 
        FROM loja_pontos 
        WHERE user_id = %s 
        AND ativo = 1
    """, (user_id,))

    outros = cur.fetchall()

    nomes_formatados = {
        "comemoracao": "<:827557party:1467578831106871610> **Comemoração**",
        "mute_jinxed": "<:34000mute:1467578828313464861> **Mute Jinxed**",
        "apelido": "<:561879carrotstare:1467578826614771746> **Apelido**",
        "inverter": "<:7466megareverse:1467578833279385774> **Inverter Pontos**",
        "emoji_personalizado": "<:312424paint:1467578829705842709> **Emoji Personalizado**"
    }

    for item in outros:
        nome = nomes_formatados.get(item["item"])
        if nome:
            itens_ativos.append(nome)

    con.close()

  
    if not itens_ativos:
        await interaction.response.send_message(
            "🛒 Você não possui itens ativos no momento.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🛍️ Suas Compras Ativas",
        description="\n".join(itens_ativos),
        color=0x2b2d31
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="comprar", description="Compre um item")
@discord.app_commands.choices(item=[
    discord.app_commands.Choice(
        name="🎭 Modo Clown",
        value="clown_bet"
    ),

    discord.app_commands.Choice(
        name="🎁 Caixinha",
        value="caixinha"
    ),

    discord.app_commands.Choice(
        name="💎 VIP",
        value="jinxed_vip"
    ),

    discord.app_commands.Choice(
        name="🔄 Inverter",
        value="inverter"
    ),

    discord.app_commands.Choice(
        name="🔇 Mute",
        value="mute_jinxed"
    ),

    discord.app_commands.Choice(
        name="🏷️ Apelido",
        value="apelido"
    ),

    discord.app_commands.Choice(
        name="🎉 Comemoração",
        value="comemoracao"
    ),

    discord.app_commands.Choice(
        name="🎨 Emoji",
        value="emoji_personalizado"
    ),
])
async def slash_comprar(interaction: discord.Interaction, item: str):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            "Canal errado.",
            ephemeral=True
        )

    ok, msg = await executar_compra(
        interaction.user,
        item,
        interaction.guild
    )

    await interaction.response.send_message(
        msg,
        ephemeral=True
    )



DISPLAY_NOMES = {
    "galo": "Atlético-MG",
    "sao paulo": "São Paulo",
    "gremio": "Grêmio",
    "athletico paranaense": "Athletico-PR",
    "ceara": "Ceará",
    "vitoria": "Vitória",
    "fluminense": "Fluminense",
    "vasco": "Vasco",
    "palmeiras": "Palmeiras",
    "flamengo": "Flamengo",
    "corinthians": "Corinthians",
    "cruzeiro": "Cruzeiro",
    "botafogo": "Botafogo",
    "bahia": "Bahia",
    "bragantino": "Bragantino",
    "santos": "Santos",
    "fortaleza": "Fortaleza",
    "internacional": "Internacional",
    "coritiba": "Coritiba",
    "remo": "Remo",
    "mirassol": "Mirassol"
}

ROLE_IDS_TIMES = {
    "galo": 1443224658710364190,
    "sao paulo": 1443227353412014081,
    "gremio": 1442482642942689323,
    "athletico paranaense": 1471640222713253949,
    "ceara": 1442483144270086267,
    "vitoria": 1444483144270086267,
    "fluminense": 1442482502311739442,
    "vasco": 1442482275546697860,
    "palmeiras": 1443227045332123648,
    "flamengo": 1443226719572988077,
    "corinthians": 1443227525458165903,
    "cruzeiro": 1443226573116538950,
    "botafogo": 1443759934054469703,
    "bahia": 1443227115561685033,
    "bragantino": 1471640464208957632,
    "santos": 1443227595935187025,
    "fortaleza": 1442482777894293624,
    "internacional": 1443226517219049512,
    "coritiba": 1471640974902956196,
    "remo": 1471641271570530335,
    "mirassol": 1471640764311277670
}

# IDs de canal permitido
CANAL_PERMITIDO_ID = 1380564680774385724

@bot.tree.command(name="time", description="Entre para um time de torcedores")
@app_commands.describe(nome="Selecione o time que você quer torcer")
@app_commands.choices(nome=[app_commands.Choice(name=v, value=k) for k, v in DISPLAY_NOMES.items()])
async def slash_time(interaction: discord.Interaction, nome: app_commands.Choice[str]):
    """Permite que usuário entre em um time de torcedores"""

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            "Este comando pode ser usado apenas no canal correto.",
            ephemeral=True
        )
    
    time_key = nome.value          # ex: "galo"
    cargo_nome = DISPLAY_NOMES[time_key]  # ex: "Atlético-MG"
    
    guild = interaction.guild
    member = interaction.user
    
    # ------ Banco ------
    conn = conectar_futebol()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT time_normalizado FROM times_usuarios WHERE user_id = %s",
        (member.id,)
    )
    resultado = cursor.fetchone()
    
    if resultado:
        cursor.close()
        conn.close()
        return await interaction.response.send_message(
            f"⚽ {member.mention}, você já escolheu um time (**{resultado[0]}**).\n"
            f"Use `/sair_time` para trocar.",
            ephemeral=True
        )
    
    cursor.execute("""
        INSERT INTO times_usuarios (user_id, time_normalizado)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE time_normalizado = VALUES(time_normalizado)
    """, (member.id, cargo_nome))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    # ------ Cargo ------
    
    for t_key, role_id in ROLE_IDS_TIMES.items():
        cargo_loop = guild.get_role(role_id)
        if cargo_loop and cargo_loop in member.roles:
            await member.remove_roles(cargo_loop)
    
    role_id = ROLE_IDS_TIMES.get(time_key)
    if role_id:
        cargo = guild.get_role(role_id)
        if cargo:
            await member.add_roles(cargo)
            await interaction.response.send_message(
                f"<a:995589misathumb:1443956356846719119> {member.mention}, agora você está registrado como torcedor do **{cargo_nome}**!",
                ephemeral=True
            )
            logging.info(f"{member.name} entrou no time {cargo_nome} via slash command.")
            return
    
    await interaction.response.send_message(
        f"❌ Cargo do time **{cargo_nome}** não encontrado no servidor.",
        ephemeral=True
    )
    

@bot.tree.command(name="lista_times", description="Veja todos os times disponíveis")
async def slash_lista_times(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

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

    embed = discord.Embed(
        title="📋 Times Disponíveis",
        description="Escolha seu time usando o comando correspondente!",
        color=discord.Color.blue()
    )

    
    chunk_size = 10
    for i in range(0, len(times), chunk_size):
        grupo = times[i:i + chunk_size]
        linhas = "\n".join([f"{emoji_do_time(t)} | **{t.title()}**" for t in grupo])

        embed.add_field(
            name="⚽ Times",
            value=linhas,
            inline=True
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info(f"Usuário {interaction.user} solicitou a lista de times.")

@bot.tree.command(name="sair_time", description="Saia do seu time de torcedores")
async def slash_sair_time(interaction: discord.Interaction):
    if interaction.channel.id != CANAL_COMANDOS:
        return await interaction.response.send_message(
            "<:480700twinshout:1443957065230844066> Este comando pode ser usado apenas no canal <#1380564680774385724>.",
            ephemeral=True
        )

    conn = conectar_futebol()
    cursor = conn.cursor()

    # Verifica se o usuário possui um time registrado
    cursor.execute(
        "SELECT time_normalizado FROM times_usuarios WHERE user_id = %s",
        (interaction.user.id,)
    )
    resultado = cursor.fetchone()

    if not resultado:
        cursor.close()
        conn.close()
        return await interaction.response.send_message(
            f"❌ {interaction.user.mention}, você não possui um time registrado.",
            ephemeral=True
        )

    time_normalizado = resultado[0]
    cargo_nome = time_normalizado.title()

    # Remover cargo do Discord
    cargo = discord.utils.get(interaction.guild.roles, name=cargo_nome)
    if cargo and cargo in interaction.user.roles:
        await interaction.user.remove_roles(cargo)

    # Remover do banco
    cursor.execute(
        "DELETE FROM times_usuarios WHERE user_id = %s",
        (interaction.user.id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    await interaction.response.send_message(
        f"✅ {interaction.user.mention}, você saiu do time **{cargo_nome}**!",
        ephemeral=True
    )

@bot.tree.command(name="info", description="Veja informações e comandos do bot")
async def slash_info(interaction: discord.Interaction):
    """Mostra informações do bot"""
    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="📜 Comandos do Bot",
        description="Aqui estão todos os comandos disponíveis:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="⚽ Times e Apostas",
        value=(
            "`/time` - Entre para um time de torcedores\n"
            "`/lista_times` - Veja todos os times disponíveis\n"
            "`/pontos` - Veja seus pontos\n"
            "`/loja` - Veja a loja de itens\n"
            "`/comprar` - Compre itens da loja"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔥 Estatísticas Pessoais",
        value=(
            "`/fogo` - Veja seus acertos consecutivos\n"
            "`/conquistas` - Veja suas conquistas desbloqueadas\n"
            "`/torcedores` - Veja todos os torcedores do servidor"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📊 Rankings e Estatísticas",
        value=(
            "`/top_fogos` - Veja os usuários com mais acertos\n"
            "`/top_apostas` - Veja os melhores apostadores\n"
            "`/bad_apostas` - Veja os piores apostadores"
        ),
        inline=False
    )
    

    
    embed.set_footer(text="Use ! para comandos tradicionais ou / para slash commands!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="fogo", description="Mostra seus acertos consecutivos atuais")
async def slash_fogo(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    try:
        acertos_atuais, maior_streak = buscar_fogo_usuario(interaction.user.id)

        embed = gerar_embed_fogo(
            acertos_atuais,
            maior_streak,
            interaction.user.display_name
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception:
        logging.exception("Erro ao consultar fogo.")
        await interaction.response.send_message(
            "❌ Ocorreu um erro ao consultar seu fogo.",
            ephemeral=True
        )

@bot.tree.command(name="top_fogos", description="Veja os usuários com mais acertos consecutivos")
async def slash_top_fogos(interaction: discord.Interaction):
    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    await interaction.response.defer()
    conn = conectar_futebol()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT user_id, MAX(maior_streak) as maior_streak FROM apostas "
            "WHERE maior_streak > 0 GROUP BY user_id ORDER BY maior_streak DESC"
        )
        resultados = cursor.fetchall()
        if not resultados:
            return await interaction.followup.send("🔥 Ninguém está com fogo no momento!", ephemeral=True)

        view = PaginaFogos(resultados, interaction.user)
        await view.atualizar_embed(interaction)

    finally:
        cursor.close()
        conn.close()


# ================= COMANDO SLASH =================
@bot.tree.command(name="top_apostas", description="Veja os melhores apostadores")
async def slash_top_apostas(interaction: discord.Interaction):
    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    await interaction.response.defer()
    conn = conectar_futebol()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nome_discord, pontos FROM pontuacoes ORDER BY pontos DESC")
    top = cursor.fetchall()
    cursor.close()
    conn.close()

    if not top:
        return await interaction.followup.send("⚠️ Nenhum usuário possui pontos.", ephemeral=True)

    view = PaginaRanking(top, interaction.user)
    await view.atualizar_embed(interaction)

@bot.tree.command(name="torcedores", description="Veja os torcedores do servidor")
async def slash_torcedores(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    embed = await gerar_embed_torcedores(interaction.guild)

    if not embed:
        return await interaction.response.send_message(
            "Nenhum torcedor registrado no servidor.",
            ephemeral=True
        )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="conquistas", description="Veja suas conquistas ou de outro usuário")
async def slash_conquistas(
    interaction: discord.Interaction,
    membro: discord.Member = None
):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    alvo = membro or interaction.user

    embed = await gerar_conquistas_embed(alvo, interaction.guild)

    if not embed:
        return await interaction.response.send_message(
            "❌ Erro ao buscar conquistas.",
            ephemeral=True
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )




EMOJI_TIMES = {

    # =======================
    # 🏟️ CLUBES DE FUTEBOL
    # =======================
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
    "lanus": "<:Lanus:1441436509281718383>",
    "atletico paranaense": "<:Athletico_Paranaense__Logo_2019_:1476340287461920859>",
    "coritiba": "<:Coritiba_Foot_Ball_Club_logo:1466193821292564634>",
    "remo": "<:Remo:1443399201655492708>",
    "chapecoense": "<:Escudo_de_2018_da_Chapecoense:1452179787027185766>",


    # =======================
    # 🌍 SELEÇÕES (PAÍSES)
    # =======================
    "brasil": "<:imagem_20251111_091505344:1437777668320788501>",
    "argentina": "<:imagem_20251111_091525637:1437777753205243936>",
    "frança": "<:imagem_20251111_091547369:1437777844058194001>",
    "alemanha": "<:imagem_20251111_091612275:1437777948907405332>",
    "italia": "<:imagem_20251111_091635544:1437778046680699010>",
    "inglaterra": "<:imagem_20251111_091700042:1437778149155803328>",
    "espanha": "<:imagem_20251111_091727942:1437778266118422568>",
    "portugal": "<:imagem_20251111_091755098:1437778380324864103>",
    "holanda": "<:imagem_20251111_091822476:1437778495018106880>",
    "uruguai": "<:imagem_20251111_091923082removeb:1437778793711534110>",
    "belgica": "<:imagem_20251111_091958114:1437778895888846888>",
    "croacia": "<:imagem_20251111_092025445:1437779010628222998>",
    "mexico": "<:imagem_20251111_092057355:1437779144917127259>",
    "japao": "<:imagem_20251111_092122937:1437779251729272903>",
    "eua": "<:imagem_20251111_092151751:1437779372940464138>",
    "senegal": "<:imagem_20251111_092227325:1437779522157281290>",
    "tunisia": "<:imagem_20251111_092254095:1437779634191208518>",
    "austria": "<:austria:1447019535415771228>",
    "noruega": "<:noruega:1447019598020087979>",
    "chile": "<:chile:1447019706467749998>",
    "marrocos": "<:marrocos:1447019811132407859>",
    "coreia do sul": "<:Coreiadosul:1447019914102833152>",
    "china": "<:china:1447019999305793697>"
    ,
    # =======================
    # 🌍 CLUBES INTERNACIONAIS (UEFA)
    # =======================
    "villarreal": "<:Villareal:1447341127257686076>",
    "bayer_leverkusen": "<:Bayerliverkusen:1447341052481503342>",
    "atalanta": "<:Atalanta:1447340975595720815>",
    "olympique": "<:Olympic:1447340908017221713>",
    "benfica": "<:Benfica:1447340742598201396>",
    "ajax": "<:Ajax:1447340532140343397>",
    "borussia": "<:Borussia:1447340278464909406>",
    "borussia_dortmund": "<:Borussia:1447340278464909406>",
    "napoli": "<:Napoli:1447340070934806742>",
    "atletico_de_madrid": "<:Atleticodemadrid:1447339835084898365>",
    "milan": "<:Millan:1447339769939099868>",
    "juventus": "<:Juventus:1447339677391786044>",
    "psg": "<:Psg:1447339575482646679>",
    "city": "<:City:1447339515545911428>",
    "arsenal": "<:Arsenal:1447339446021132398>",
    "chelsea": "<:Chelsea:1447339384125915187>",
    "liverpool": "<:Liverpool:1447339314798133361>",
    "bayern_munich": "<:FC_Bayern_Mnchen_logo_2024:1447339006126854154>",
    "barcelona": "<:Barcelona:1447338926548193483>",
    "real_madrid": "<:Real_Madrid:1447338825180381389>",
    "west_ham":"<:EmojiWestHam:1470834951036338218>",
    "manchester_united": "<:EmojiUnited:1470834899605917696>"


}


# Dicionário global para armazenar dados das apostas
apostas_data = {}

@bot.event
async def on_interaction(interaction):
    if not interaction.data:
        return

    cid = interaction.data.get("custom_id")
    
    # Usar dicionário global em vez de atributo da mensagem
    if not interaction.message:
        return
    message_id = interaction.message.id
    if message_id in apostas_data:
        fixture_id, home, away = apostas_data[message_id]
        
        if cid == "aposta_home":
            await processar_aposta_botao(interaction, fixture_id, "home", home, away)
        elif cid == "aposta_draw":
            await processar_aposta_botao(interaction, fixture_id, "draw", home, away)
        elif cid == "aposta_away":
            await processar_aposta_botao(interaction, fixture_id, "away", home, away)


class ApostaView(discord.ui.View):
    def __init__(self, fixture_id, home, away):
        super().__init__(timeout=600)
        self.fixture_id = fixture_id
        self.home = home
        self.away = away

        # Mapear emojis
        nome_casa = MAPEAMENTO_TIMES.get(home.lower(), home.lower()).replace(" ", "_")
        emoji_casa = EMOJI_TIMES.get(nome_casa, "🔵")

        nome_fora = MAPEAMENTO_TIMES.get(away.lower(), away.lower()).replace(" ", "_")
        emoji_fora = EMOJI_TIMES.get(nome_fora, "🔴")

        # 🟦 Botão casa
        self.add_item(discord.ui.Button(
            label=home,
            emoji=emoji_casa,
            style=discord.ButtonStyle.primary,  # azul
            custom_id="aposta_home"
        ))

        # ⚪ Botão empate
        self.add_item(discord.ui.Button(
            label="Empate",
            emoji="🤝",
            style=discord.ButtonStyle.secondary,  # cinza
            custom_id="aposta_draw"
        ))

        # 🟦 Botão visitante
        self.add_item(discord.ui.Button(
            label=away,
            emoji=emoji_fora,
            style=discord.ButtonStyle.primary,  # azul
            custom_id="aposta_away"
        ))

    def set_message(self, message):
        """Armazena a mensagem e seus dados para uso posterior"""
        self.message = message
        # Armazenar dados no dicionário global
        apostas_data[message.id] = (self.fixture_id, self.home, self.away)

    async def on_timeout(self):
        # Conectar ao banco e pegar todas as apostas desse jogo
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "SELECT user_id, palpite FROM apostas WHERE fixture_id = %s",
            (self.fixture_id,)
        )
        apostas = cur.fetchall()
        con.close()

        # Separar por tipo de palpite
        home_list = []
        draw_list = []
        away_list = []

        for user_id, palpite in apostas:
            mention = f"<@{user_id}>"
            if palpite == "home":
                home_list.append(mention)
            elif palpite == "draw":
                draw_list.append(mention)
            else:
                away_list.append(mention)

        # Montar mensagem final
        msg_text = (
            f"🏟️ **{self.home} x {self.away}**\n\n"
            f"{EMOJI_TIMES.get(MAPEAMENTO_TIMES.get(self.home.lower(), self.home.lower()).replace(' ', '_'), '🔵')} {self.home}: {', '.join(home_list) if home_list else 'Nenhum'}\n"
            f"🤝 Empate: {', '.join(draw_list) if draw_list else 'Nenhum'}\n"
            f"{EMOJI_TIMES.get(MAPEAMENTO_TIMES.get(self.away.lower(), self.away.lower()).replace(' ', '_'), '🔴')} {self.away}: {', '.join(away_list) if away_list else 'Nenhum'}\n\n"
            "⏰ As apostas foram encerradas!"
        )

        # Limpar os botões e editar a mensagem
        self.clear_items()
        try:
            await self.message.edit(content=msg_text, view=self)
        except discord.NotFound:
            # Mensagem foi deletada, não pode editar
            logging.warning(f"⚠️ Mensagem da aposta não encontrada (deletada) - Fixture ID: {self.fixture_id}")
        except discord.Forbidden:
            # Sem permissão para editar
            logging.warning(f"⚠️ Sem permissão para editar mensagem da aposta - Fixture ID: {self.fixture_id}")
        except Exception as e:
            # Outros erros
            logging.error(f"❌ Erro ao editar mensagem da aposta: {e} - Fixture ID: {self.fixture_id}")

async def processar_aposta_botao(interaction, fixture_id, palpite, home, away):
    # Verificar se ainda está aberto para apostas
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute("SELECT betting_open FROM jogos WHERE fixture_id = %s", (fixture_id,))
    jogo = cur.fetchone()
    con.close()

    if not jogo or jogo[0] == 0:
        await interaction.response.send_message(
            "⏰ As apostas para esta partida estão encerradas!",
            ephemeral=True
        )
        return

    sucesso = registrar_aposta_db(interaction.user.id, fixture_id, palpite)

    if not sucesso:
        await interaction.response.send_message(
            "❌ Você já apostou ou a aposta está encerrada.",
            ephemeral=True
        )
        return

    if palpite == "home":
        escolhido = home
    elif palpite == "away":
        escolhido = away
    else:
        escolhido = "Empate"

    await interaction.response.send_message(
    f"━━━━━━━━━━━━━━━\n"
    f"🏟️ **{home} x {away}**\n"
    f"━━━━━━━━━━━━━━━\n\n"
    f"<:514694happycatemoji:1466570662603915359> **Palpite:** `{escolhido}`\n"
    f"🍀 _Boa sorte! Que venha o gol!_\n",
    ephemeral=True
)

# ============================================================
#                    SISTEMA DE CONQUISTAS
# ============================================================

CONQUISTAS = {
    "conversador_nato": {
        "nome": "🗣️ Conversador Nato",
        "descricao": "Envie 2000 mensagens na semana.",
        "condicao": lambda d: d['mensagens_semana'] >= 2000,
        "cargo": "Conversador Nato"
    },
    "mente_calculada": {
        "nome": "🧠 Mente Calculada",
        "descricao": "Acerte 3 apostas consecutivas.",
        "condicao": lambda d: d['maior_streak'] >= 3,
        "cargo": "Mente Calculada"
    },
    "oraculo": {
        "nome": "🔮 O Oráculo",
        "descricao": "Acerte 5 apostas consecutivas.",
        "condicao": lambda d: d['maior_streak'] >= 5,
        "cargo": "O Oráculo"
    },
    "lenda_apostas": {
        "nome": "🏆 Lenda das Apostas",
        "descricao": "Acerte 10 apostas consecutivas.",
        "condicao": lambda d: d['maior_streak'] >= 10,
        "cargo": "Lenda das Apostas"
    },
    "apoiador": {
        "nome": "💸 Apoiador",
        "descricao": "Faça uma doação de R$50.",
        "condicao": lambda d: d['fez_doacao'],
        "cargo": "TAKE MY MONEY"
    },
    "coroado": {
        "nome": "<a:thekings:1449048326937772147> Coroado",
        "descricao": "Ganhe VIP.",
        "condicao": lambda d: d['tem_vip'],
        "cargo": "Coroado"
    },
    "azarao": {
        "nome": "🐗 O Azarão",
        "descricao": "Aposte no personagem mais fraco e ele vença a batalha.",
        "condicao": lambda d: d['azarao_vitoria'],
        "cargo": "O Azarão"
    },
    "conversador_em_call": {
        "nome": "🎙️ Veterano de Call",
        "descricao": "Fique 50 horas em call de voz (acumulado).",
        "condicao": lambda d: d['tempo_em_call'] >= 180000,
        "cargo": "Veterano de Call"
    },
    "chamando_ajuda": {
        "nome": "🤖 Alô Miisha?",
        "descricao": "Mencione a bot Miisha para pedir ajuda.",
        "condicao": lambda d: d['mencionou_miisha'],
        "cargo": "Amigo da IA"
    },
    "dj_sarah": {
        "nome": "🎧 DJ da Sarah",
        "descricao": "Toque uma música usando o bot m!play (apenas VIPs).",
        "condicao": lambda d: d['tocou_musica'],
        "cargo": "DJ da Sarah"
    },
    "insistente_pelucia": {
        "nome": "💬 Mestre das Menções",
        "descricao": "Mencione o bot 100 vezes.",
        "condicao": lambda d: d["mencoes_bot"] >= 100 and not d.get("bloqueado", False),
        "cargo": "Pelúcia Darwin"
    },
    "party_na_call": {
        "nome": "🎮 Party na Call",
        "descricao": "Esteja em uma call com mais 2 pessoas jogando o mesmo jogo.",
        "condicao": lambda d: False,  # Concedida manualmente via detecção de jogo
        "cargo": "Party na Call"
    },
    "artista": {
    "nome": "🎨 Artista do Mês",
    "descricao": "Seja o artista mais curtido do mês e receba o cargo Artista.",
    "condicao": lambda d: d.get("tem_cargo_artista", False),
    "cargo": "Artista"
    },
}


def get_mencoes_bot(user_id):
    try:
        conn = conectar_vips()
        cur = conn.cursor()
        cur.execute(
            "SELECT total_mencoes FROM mencoes_bot WHERE user_id = %s",
            (user_id,)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logging.error(f"Erro em get_mencoes_bot: {e}")
        return 0

def processar_conquistas_db(user_id, novos_registros):
    conexao = conectar_vips()
    cursor = conexao.cursor(buffered=True)

    try:
        if novos_registros:
            logging.info(f"Adicionando {len(novos_registros)} novas conquistas para o usuário {user_id}")
            cursor.executemany(
                "INSERT IGNORE INTO conquistas_desbloqueadas (user_id, conquista_id) VALUES (%s, %s)",
                novos_registros
            )
            conexao.commit()
            logging.info("Novas conquistas inseridas com sucesso (duplicatas ignoradas)")

        cursor.execute(
            "SELECT conquista_id FROM conquistas_desbloqueadas WHERE user_id = %s",
            (user_id,)
        )
        resultados = cursor.fetchall()
        conquistas = {row[0] for row in resultados}
        return conquistas

    except Exception as e:
        logging.error(f"Erro ao processar conquistas do usuário {user_id}: {e}", exc_info=True)
        return set()

    finally:
        cursor.close()
        conexao.close()
        

async def processar_conquistas(
    member,
    mensagens_semana,
    maior_streak,
    fez_doacao,
    tem_vip,
    tempo_em_call=0,
    mencionou_miisha=False,
    tocou_musica=False,
    mencoes_bot=0,
    azarao_vitoria=False
):
    # 🔥 verifica cargo artista
    tem_cargo_artista = False
    if member.guild:
        cargo_artista = discord.utils.get(member.guild.roles, name="Artista")
        if cargo_artista and cargo_artista in member.roles:
            tem_cargo_artista = True

    dados = {
        "mensagens_semana": mensagens_semana or 0,
        "maior_streak": maior_streak or 0,
        "fez_doacao": fez_doacao,
        "tem_vip": tem_vip,
        "tempo_em_call": tempo_em_call or 0,
        "mencionou_miisha": mencionou_miisha,
        "tocou_musica": tocou_musica,
        "mencoes_bot": mencoes_bot or 0,
        "azarao_vitoria": azarao_vitoria,
        "bloqueado": False,
        "tem_cargo_artista": tem_cargo_artista
    }

    desbloqueadas = []
    bloqueadas = []
    novas_conquistas = []
    novos_registros = []

    loop = asyncio.get_running_loop()

    # 🔥 pega conquistas existentes SEM travar o bot
    conquistas_existentes = await loop.run_in_executor(
        None,
        processar_conquistas_db,
        member.id,
        []  
    )

    for key, conquista in CONQUISTAS.items():

        try:
            condicao_ok = conquista["condicao"](dados)
        except Exception as e:
            logging.error(f"Erro na conquista {key}: {e}")
            continue

        texto = f"**{conquista['nome']}**\n{conquista['descricao']}"

        ja_no_banco = key in conquistas_existentes
        desbloqueada = ja_no_banco or condicao_ok

        if desbloqueada:
            desbloqueadas.append(texto)

            if condicao_ok and not ja_no_banco:
                novos_registros.append((member.id, key))
                novas_conquistas.append(conquista)

            # entrega cargo
            if member.guild:
                cargo = discord.utils.get(member.guild.roles, name=conquista["cargo"])
                if cargo and cargo not in member.roles:
                    try:
                        await member.add_roles(cargo)
                    except Exception as e:
                        logging.error(f"Erro ao adicionar cargo {cargo} ao membro {member}: {e}")

        else:
            bloqueadas.append(texto)

    
    if novos_registros:
        await loop.run_in_executor(
            None,
            processar_conquistas_db,
            member.id,
            novos_registros
        )

    # 🔔 notificação
    if novas_conquistas:
        try:
            embed = discord.Embed(
                title="<a:44503lockkey:1457473730329710706> Nova Conquista Desbloqueada!",
                color=discord.Color.gold()
            )

            for conquista in novas_conquistas:
                embed.add_field(
                    name=conquista["nome"],
                    value=f"<:55105yippee:1450627092336082945> Parabéns! {conquista['descricao']}",
                    inline=False
                )

            embed.set_footer(text="Use !conquistas para ver todas as suas conquistas!")

            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                pass

        except Exception as e:
            logging.error(f"Erro ao enviar notificação de conquista para {member}: {e}")

    return desbloqueadas, bloqueadas


CHAT_GERAL = 1380564680552091789

async def desbloquear_conquistas_em_grupo(guild, user_ids, conquista_id):
    conquista = CONQUISTAS[conquista_id]
    conexao = conectar_vips()
    cursor = conexao.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conquistas_desbloqueadas (
            user_id BIGINT,
            conquista_id VARCHAR(50),
            data_desbloqueio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, conquista_id)
        )
    """)
    conexao.commit()
    novos = []
    for user_id in user_ids:
        cursor.execute(
            "SELECT 1 FROM conquistas_desbloqueadas WHERE user_id=%s AND conquista_id=%s",
            (user_id, conquista_id)
        )

        if cursor.fetchone():
            logging.info(f"Conquista '{conquista['nome']}' já existe para usuário {user_id}")
            continue
        cursor.execute(
            "INSERT INTO conquistas_desbloqueadas (user_id, conquista_id) VALUES (%s, %s)",
            (user_id, conquista_id)
        )
        conexao.commit()
        logging.info(f"Conquista em grupo '{conquista['nome']}' concedida para usuário {user_id}")
        member = guild.get_member(user_id)
        if not member:
            logging.warning(f"Membro {user_id} não encontrado no guild para conceder cargo")
            continue
        cargo = discord.utils.get(guild.roles, name=conquista['cargo'])
        if cargo:
            if cargo not in member.roles:
                try:
                    await member.add_roles(cargo)
                    logging.info(f"Cargo '{cargo.name}' adicionado para {member.display_name} ({member.id})")
                except Exception as e:
                    logging.error(f"Erro ao adicionar cargo {cargo.name} para {member.display_name}: {e}")
                novos.append(member)
            else:
                logging.debug(f"Membro {member.display_name} ({member.id}) já possui o cargo '{cargo.name}'")
        else:
            logging.warning(f"Cargo '{conquista['cargo']}' não encontrado no guild")

    cursor.close()
    conexao.close()

    if novos:
        embed = discord.Embed(
            title="<a:8377gamingcontroller:1451333843486376151> Conquista em Grupo Desbloqueada!",
            description=f"Vocês desbloquearam **{conquista['nome']}**!\n{conquista['descricao']}",
            color=discord.Color.green()
        )
        mentions = " ".join(m.mention for m in novos)
        canal = guild.get_channel(CHAT_GERAL)
        if canal:
            await canal.send(mentions, embed=embed)





MENCAO_FUTEBOL = "<#1442495893365330138>"
MENCAO_CANAL_DOACAO = "<#1454672224631128205>"
MENCAO_CANAL_VIP = "<#1381380248511447040>"



mensagens_bom_dia = [
    "🌞 Bom dia, pessoal! Vamos começar o dia com energia positiva!",
    "☕ Bom dia! Já tomaram aquele cafezinho?",
    "💪 Bom dia, guerreiros! Que hoje seja um dia produtivo!",
    "✨ Bom dia! Que seu dia seja iluminado!",
    "🌻 Bom dia! Bora conquistar nossos objetivos hoje!",
    "🌅 Bom dia! Que hoje seja melhor que ontem!",
    "🎶 Bom dia! Que a alegria seja sua trilha sonora hoje!",
    "🍀 Bom dia! Que a sorte esteja ao seu lado!",
    "😄 Bom dia! Um sorriso já é metade do caminho para um ótimo dia.",
    "📈 Bom dia! Hoje é dia de progresso!",
    "🌈 Bom dia! Que sua manhã seja colorida de coisas boas.",
    "🥐 Bom dia! Já tomou café da manhã? Energia é tudo!",
    "⚡ Bom dia! Que sua motivação seja sua força!",
    "🎯 Bom dia! Foco e disciplina levam longe.",
    "🌊 Bom dia! Deixe as preocupações fluírem e siga leve.",
    "❤️ Bom dia! Desejo a todos muito amor hoje.",
    "💤 Bom dia! Quem acordou cedo hoje merece um troféu... 🏆",
    "🐓 Cocoricóôôôô! Bom diaaa!",
    
    # Humor / personalidade
    "<:JinxFU:1390638686877777920> Bom dia é o caralho, vai todo mundo se fuder!",
    "Já pensou que às vezes o seu dia tá ruim… e pode piorar? Quer dizer… bom dia 😅",

    # PIX memes (mantive alguns, mas sem poluir)
    "🌞 Bom diaaa! Que o dia seja tão iluminado quanto um PIX caindo na conta 💸",
    "🚀 Bom dia! Acorde, levante e corra atrás dos seus sonhos.",
    "🔥 Bom dia, guerreiros! Bora encarar mais um dia com coragem!",
    "😂 Bom dia! Quem acorda cedo já começa na vantagem.",
    
    # NOVOS (adicionei)
    "🌄 Novo dia, nova chance de fazer acontecer. Bom dia!",
    "🧘 Bom dia! Respire fundo — hoje vai dar certo.",
    "🌟 Bom dia! Pequenos progressos ainda são progressos.",
    "📊 Bom dia! Consistência vence talento quando o talento não é consistente.",
    "😎 Bom dia! Mais um dia pra ficar um pouco melhor que ontem.",
    "🏆 Bom dia! Mentalidade de campeão começa cedo."
]


def slash_mention(bot, nome):
    try:
        for cmd in bot.tree.walk_commands():
            if cmd.name == nome:
                if getattr(cmd, "id", None):
                    return f"</{cmd.name}:{cmd.id}>"
                return f"/{cmd.name}"
    except Exception:
        pass
    return f"/{nome}"


mensagens_curiosidade = [

    # ================= CIÊNCIA =================

    "🧠 O cérebro humano gera eletricidade suficiente para acender uma pequena lâmpada.",
    "🧠 Seu cérebro consome cerca de 20% de toda a energia do corpo.",
    "💭 Curiosidade: seu cérebro não sente dor.",
    "🧩 Falsas memórias podem ser criadas apenas ao lembrar algo de forma incorreta.",
    "👁️ Todo mundo tem um ponto cego no olho — e quase ninguém percebe.",
    "📖 Ler pode alterar fisicamente a estrutura do seu cérebro.",
    "🎵 A música pode influenciar seus batimentos cardíacos.",
    "⏳ O tempo passa mais devagar para quem está em alta velocidade (relatividade!).",
    "🛰️ O GPS só funciona corretamente por causa da teoria da relatividade.",
    "🧬 Você compartilha cerca de 60% do seu DNA com uma banana.",
    "🍌 Bananas são levemente radioativas.",
    "🌡️ O metal pode grudar na pele em temperaturas extremamente frias.",
    "🧊 Água quente pode congelar mais rápido que água fria — efeito Mpemba.",
    "🔥 Caberiam aproximadamente 1,3 milhão de Terras dentro do Sol.",
    "🌌 Existem mais estrelas no universo do que grãos de areia na Terra.",
    "🔭 Olhar para o espaço é literalmente olhar para o passado.",
    "🌊 Apenas cerca de 5% dos oceanos foram explorados.",
    "🌍 A Terra não é uma esfera perfeita — ela é achatada nos polos.",
    "⚡ Cerca de 100 raios atingem a Terra a cada segundo.",

    # ================= ANIMAIS =================

    "🐙 Polvos têm três corações e sangue azul.",
    "🐝 Abelhas conseguem reconhecer rostos humanos.",
    "🐧 O pinguim-imperador pode ficar até 20 minutos submerso.",
    "🦈 Tubarões existem há mais tempo que as árvores.",
    "🦒 Girafas têm o mesmo número de vértebras no pescoço que humanos: sete.",
    "🐢 Algumas tartarugas conseguem respirar pelo traseiro.",
    "🦋 Borboletas sentem o gosto com as patas.",
    "🐘 Elefantes conseguem 'ouvir' através das patas.",
    "🐬 Golfinhos dão nomes uns aos outros usando assobios únicos.",
    "🦉 Corujas não conseguem mover os olhos — por isso giram a cabeça.",
    "🐜 Formigas não dormem.",
    "🐋 O coração de uma baleia azul pode pesar mais de 180 kg.",
    "🐎 Cavalos conseguem dormir em pé.",
    "🐕 O olfato dos cães é até 100 mil vezes mais sensível que o humano.",
    "🐈 Gatos passam cerca de 70% da vida dormindo.",
    "🦑 Lulas gigantes têm olhos do tamanho de bolas de futebol.",

    # ================= ESPAÇO =================

    "🚀 A Estação Espacial Internacional viaja a mais de 27.000 km/h.",
    "🌕 Pegadas deixadas na Lua podem durar milhões de anos.",
    "🪐 Um dia em Vênus é maior que um ano no planeta.",
    "☄️ Existem trilhões de galáxias no universo observável.",
    "🌠 Uma estrela de nêutrons é tão densa que uma colher pesaria bilhões de toneladas.",
    "🌞 A luz do Sol leva cerca de 8 minutos para chegar até a Terra.",
    "🌑 Na Lua não há vento — por isso nada apaga as marcas.",
    "🛰️ O primeiro satélite foi lançado em 1957 e se chamava Sputnik.",
    "🌡️ A temperatura no espaço pode chegar a -270°C.",

    # ================= HISTÓRIA / HUMANIDADE =================

    "💡 Thomas Edison não inventou a lâmpada — apenas criou a versão comercial viável.",
    "📚 O mel nunca estraga. Potes encontrados no Egito ainda estavam próprios para consumo.",
    "🏛️ A Universidade de Oxford é mais antiga que o Império Asteca.",
    "⚔️ Cleópatra viveu mais perto da invenção do iPhone do que da construção das pirâmides.",
    "📜 O papel higiênico moderno só surgiu no século XIX.",
    "🚗 O primeiro carro era mais lento que uma bicicleta.",
    "🎬 O filme mais antigo ainda existente foi gravado em 1888.",
    "📡 A internet começou como um projeto militar.",
    "⌛ Humanos existem há apenas 0,004% da história da Terra.",

    # ================= COISAS SURPREENDENTES =================

    "🎮 Alguns jogos ajustam a dificuldade automaticamente sem você perceber.",
    "🧠 Tomar água pode melhorar sua concentração quase instantaneamente.",
    "😴 Ficar acordado por 17 horas reduz sua atenção como se tivesse bebido álcool.",
    "😂 Rir reduz os níveis de estresse do corpo.",
    "🚶 Caminhar 10 minutos pode aumentar sua criatividade.",
    "🌿 O cheiro de grama cortada é um sinal de 'socorro' das plantas.",
    "☕ Cafeína começa a agir em cerca de 10 minutos.",
    "📱 A vibração fantasma do celular é um fenômeno psicológico real.",
    "🎧 Sons ambientes podem melhorar o foco.",
    "🕒 Seu corpo tem um relógio biológico natural.",


    # ================= SERVER / BOT =================

    "🤖 O bot **Miisha** pode te ajudar com comandos e informações do servidor — é só chamar!",
    "⚡ Mencione @Miisha para descobrir funções e dicas rapidamente.",
    "🆘 Dúvidas sobre o servidor? A Miisha pode te poupar tempo.",
    f"⚽ Você pode apostar no seu time favorito no canal {MENCAO_FUTEBOL}.",
    f"<a:522143costco:1473869986773733396> Confira itens e vantagens usando {slash_mention(bot, 'loja')}.",
    f"💰 Quer ver seus pontos e acertos consecutivos? Use {slash_mention(bot, 'pontos')}.",
    f"⚽ Escolha seu time com {slash_mention(bot, 'time')} e represente ele nas apostas!",
    f"💸 Você pode ganhar pontos ajudando o desenvolvimento do bot! Veja mais em {MENCAO_CANAL_DOACAO}.",
    f"🤑 Quer vantagens exclusivas? Seja VIP! Veja mais em {MENCAO_CANAL_VIP}.",
    "🏯 Temos apostas de futebol e também de animes — normalmente às sextas e sábados!",
    "🤖 Agora eu possuo comandos Slash! Basta apertar `/` e ver todas as opções que posso oferecer.",
    "🎉 Slash commands ativados! Facilito sua vida mostrando resultados e informações sem precisar lembrar comandos antigos!"
]


#===========================Bom Dia & Curiosidade===========================
#===========================                     ===========================
ultimo_bom_dia = None
ultima_curiosidade = None

@tasks.loop(minutes=1)
async def enviar_mensagens_programadas():
    global ultimo_bom_dia, ultima_curiosidade
    agora = datetime.now()
    hora = agora.hour
    minuto = agora.minute
    hoje = agora.date()
    canal = bot.get_channel(CHAT_GERAL)
    if hora == 9 and minuto == 0:
        msg = random.choice(mensagens_bom_dia)
        await canal.send(msg)
        ultimo_bom_dia = hoje
    
    if hora == 15 and minuto == 0:
        msg = random.choice(mensagens_curiosidade)
        await canal.send(msg)
        ultima_curiosidade = hoje


@bot.event
async def on_ready():
    logging.info(f"🌹 Bot conectado como {bot.user}")
    
    await verificar_usuarios_em_call_inicial()
    
    bot.add_view(DoacaoView())  

    bot.add_view(VipView())
    
    # Inicia loop automático de parada
    if not verificar_parada_automatica.is_running():
        verificar_parada_automatica.start()
        logging.info("🔄 Loop de parada automática iniciado")
    
    await setup_views()
    
    doacao_data = get_mensagem_doacao()
    if doacao_data:
        try:
            channel = bot.get_channel(doacao_data["channel_id"])
            if channel:
                message = await channel.fetch_message(doacao_data["message_id"])
                if message:
                    await message.edit(view=DoacaoView())
                    logging.info(f"Mensagem de doação restaurada: message_id={doacao_data['message_id']}")
        except Exception as e:
            logging.error(f"Erro ao restaurar mensagem de doação: {e}")
    
    jogos_pendentes = buscar_jogos_pendentes()

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

    if not enviar_mensagens_programadas.is_running():
        enviar_mensagens_programadas.start()
        
    if not check_evento_anime.is_running():
        check_evento_anime.start()

    if not loop_top_ativos.is_running():
        loop_top_ativos.start()
        
    if not resetar_ativos_semanal.is_running():
        resetar_ativos_semanal.start()
        
    if not reset_mencoes_bloqueio.is_running():
        reset_mencoes_bloqueio.start()

    if not bump_loop.is_running():
        bump_loop.start()

    if not verificar_melhor_do_mes.is_running():
        verificar_melhor_do_mes.start()
        

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
    
    bot.loop.create_task(jimbo_scheduler())

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
    try:
        def check(m):
            return (TICKET_EMBED_MESSAGE_ID is None) or (m.id != TICKET_EMBED_MESSAGE_ID)
        await channel.purge(check=check, limit=100)
    except Exception:
        pass


@tasks.loop(hours=24)
async def reset_mencoes_bloqueio():
    try:
        conn = conectar_vips()
        cur = conn.cursor()
        cur.execute(
            "UPDATE mencoes_bot SET tentativas = 0, bloqueado = 0 WHERE bloqueado = 1 AND TIMESTAMPDIFF(DAY, ultimo, UTC_TIMESTAMP()) >= %s",
            (MENCION_RESET_DIAS,)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao resetar bloqueios de menções: {e}")



CARGOS_POR_REACAO = {
    "1409886253658279936": 1451376980581683354,  # Pelúcia Goku
    "1437791755096293510": 1451378090025549976   # Pelúcia Dante
    
}

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    message = reaction.message
    emoji = str(reaction.emoji)

    # ======================================================
    # 0) SISTEMA DE VOTAÇÃO DE BATALHA DE ANIME
    # ======================================================
    if batalha_info.get("ativa") and batalha_info.get("msg_id") == message.id:

        personagem_votado = None

        if batalha_info.get("p1") and emoji == batalha_info["p1"]["emoji"]:
            personagem_votado = batalha_info["p1"]["nome"]

        elif batalha_info.get("p2") and emoji == batalha_info["p2"]["emoji"]:
            personagem_votado = batalha_info["p2"]["nome"]

        if not personagem_votado:
            return

        logging.info(f"🗳️ {user.display_name} votou em {personagem_votado}")

        try:
            conn = conectar_vips()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO votos_anime (user_id, message_id, personagem)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    personagem = VALUES(personagem),
                    data_voto = CURRENT_TIMESTAMP
            """, (user.id, message.id, personagem_votado))

            conn.commit()
            cur.close()
            conn.close()

            logging.info(f"✅ Voto registrado: {user.id} -> {personagem_votado}")

        except Exception as e:
            logging.error(f"Erro ao registrar voto anime: {e}")
            return

        try:
            if personagem_votado == batalha_info["p1"]["nome"]:
                outra_reacao = batalha_info["p2"]["emoji"]
            else:
                outra_reacao = batalha_info["p1"]["emoji"]

            await message.remove_reaction(outra_reacao, user)

        except Exception:
            # Evita crash se faltar permissão ou reação não existir
            pass

        return

    # ======================================================
    # 1) SISTEMA DE POSTS (👍 / 👎)
    # ======================================================
    CANAL_MURAL_ID = 1386805780140920954

    if message.channel.id != CANAL_MURAL_ID:
        return

    if emoji not in ("👍", "👎"):
        return

    tipo = "up" if emoji == "👍" else "down"

    conexao = conectar_futebol()
    cursor = conexao.cursor()

    try:
        # impede votar no próprio post
        cursor.execute(
            "SELECT user_id FROM posts WHERE id = %s",
            (message.id,)
        )
        autor = cursor.fetchone()

        if autor and autor[0] == user.id:
            return

        # remove voto anterior (se existir)
        cursor.execute(
            "DELETE FROM reacoes WHERE message_id=%s AND user_id=%s",
            (message.id, user.id)
        )

        # insere novo voto
        cursor.execute(
            "INSERT INTO reacoes (message_id, user_id, tipo) VALUES (%s, %s, %s)",
            (message.id, user.id, tipo)
        )

        # recalcula votos
        cursor.execute(
            "SELECT COUNT(*) FROM reacoes WHERE message_id=%s AND tipo='up'",
            (message.id,)
        )
        upvotes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM reacoes WHERE message_id=%s AND tipo='down'",
            (message.id,)
        )
        downvotes = cursor.fetchone()[0]

        cursor.execute(
            "UPDATE posts SET upvotes=%s, downvotes=%s WHERE id=%s",
            (upvotes, downvotes, message.id)
        )

        conexao.commit()

    except Exception as e:
        logging.error(f"Erro ao processar reação no mural: {e}")

    finally:
        cursor.close()
        conexao.close()


@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    
    message = reaction.message
    emoji = str(reaction.emoji)
    
    # ======================================================
    # 1) SISTEMA DE POSTS (👍 / 👎)
    # ======================================================
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


@tasks.loop(hours=24)
async def verificar_posts():
    """
    Remove automaticamente posts com mais downvotes que upvotes após 7 dias.
    Executa uma vez por dia.
    """
    CANAIS_PERMITIDOS = [1234567890]  # IDs dos canais permitidos
    DIAS_PARA_REMOCAO = 7
    LIMITE_REMOCOES = 50  # Máximo de remoções por execução
    
    try:
        conexao = conectar_vips()
        cursor = conexao.cursor(dictionary=True)
        
        # Converter para tupla e garantir que haja pelo menos um canal
        canais = tuple(CANAIS_PERMITIDOS) if CANAIS_PERMITIDOS else (0,)
        
        cursor.execute("""
            SELECT id, channel_id, upvotes, downvotes, timestamp, user_id
            FROM posts 
            WHERE removed = FALSE 
            AND timestamp <= (NOW() - INTERVAL %s DAY)
            AND channel_id IN {}
            ORDER BY timestamp ASC
            LIMIT %s
        """.format(canais if len(canais) > 1 else f"({canais[0]})"), 
        (DIAS_PARA_REMOCAO, LIMITE_REMOCOES))
        
        posts = cursor.fetchall()
        remocoes = 0
        
        for post in posts:
            if post["downvotes"] > post["upvotes"] and remocoes < LIMITE_REMOCOES:
                try:
                    channel = bot.get_channel(post["channel_id"])
                    if not channel:
                        continue
                        
                    msg = await channel.fetch_message(post["id"])
                    await msg.delete()
                    
                    cursor.execute("""
                        UPDATE posts 
                        SET removed = TRUE, 
                            motivo_remocao = 'Mais downvotes que upvotes após 7 dias'
                        WHERE id = %s
                    """, (post["id"],))
                    
                    # Notificar o autor
                    try:
                        autor = await bot.fetch_user(post["user_id"])
                        if autor:
                            await autor.send(f"Seu post em #{channel.name} foi removido por receber mais downvotes que upvotes após 7 dias.")
                    except Exception as e:
                        logging.error(f"Erro ao notificar autor {post['user_id']}: {e}")
                    
                    remocoes += 1
                    logging.info(f"Post {post['id']} do usuário {post['user_id']} removido por votos negativos.")
                    
                except discord.NotFound:
                    logging.warning(f"Post {post['id']} não encontrado, marcando como removido.")
                    cursor.execute("UPDATE posts SET removed = TRUE WHERE id = %s", (post["id"],))
                except Exception as e:
                    logging.error(f"Erro ao processar post {post['id']}: {e}")
        
        conexao.commit()
        logging.info(f"Verificação de posts concluída. {remocoes} posts removidos.")
        
    except Exception as e:
        logging.error(f"Erro na verificação de posts: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conexao' in locals():
            conexao.close()


@tasks.loop(minutes=10)  # roda a cada 10 minutos
async def sincronizar_reacoes():
    canal = bot.get_channel(1386805780140920954)
    if not canal:
        return
    # coleta atualizações em memória e aplica ao banco em thread separado
    posts_to_update = []

    try:
        async for mensagem in canal.history(limit=100):  # pode ajustar o limite
            # Pega reações atuais
            upvotes = 0
            downvotes = 0
            for reaction in mensagem.reactions:
                if str(reaction.emoji) == "👍":
                    upvotes = reaction.count - 1 if mensagem.author and mensagem.author.bot else reaction.count
                elif str(reaction.emoji) == "👎":
                    downvotes = reaction.count - 1 if mensagem.author and mensagem.author.bot else reaction.count

            posts_to_update.append((mensagem.id, getattr(mensagem.author, 'id', None), canal.id, upvotes, downvotes))

    except Exception as e:
        logging.error(f"Erro ao ler histórico do canal em sincronizar_reacoes: {e}")

    # se houver registros, executa operação de banco sem bloquear o loop
    if posts_to_update:
        try:
            await asyncio.to_thread(_sincronizar_reacoes_sync, posts_to_update)
        except Exception as e:
            logging.error(f"Erro ao atualizar banco em sincronizar_reacoes: {e}")


def _sincronizar_reacoes_sync(posts):
    """Função síncrona executada em thread para atualizar o banco."""
    conexao = None
    cursor = None
    try:
        conexao = conectar_vips()
        cursor = conexao.cursor()
        for mensagem_id, user_id, canal_id, upvotes, downvotes in posts:
            cursor.execute(
                "INSERT IGNORE INTO posts (id, user_id, channel_id, upvotes, downvotes, removed, timestamp) VALUES (%s, %s, %s, %s, %s, FALSE, NOW())",
                (mensagem_id, user_id, canal_id, upvotes, downvotes)
            )
            cursor.execute(
                "UPDATE posts SET upvotes=%s, downvotes=%s WHERE id=%s",
                (upvotes, downvotes, mensagem_id)
            )
        conexao.commit()
    except Exception:
        if conexao:
            try:
                conexao.rollback()
            except:
                pass
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conexao and getattr(conexao, 'is_connected', lambda: True)():
            try:
                conexao.close()
            except:
                pass


@tasks.loop(hours=24)
async def ranking_mensal():
    agora = datetime.utcnow()

    # Só roda no dia 1
    if agora.day != 1:
        return

    # Define mês anterior
    if agora.month == 1:
        mes = 12
        ano = agora.year - 1
    else:
        mes = agora.month - 1
        ano = agora.year

    primeiro_dia = datetime(ano, mes, 1, 0, 0, 0)
    ultimo_dia = datetime(
        ano,
        mes,
        monthrange(ano, mes)[1],
        23, 59, 59
    )

    PONTOS_PREMIO = 400

    conexao = conectar_futebol()
    cursor = conexao.cursor(dictionary=True)

    try:
        # 1️⃣ Post com mais upvotes no mês anterior
        cursor.execute("""
            SELECT id, user_id, upvotes, timestamp
            FROM posts
            WHERE channel_id = %s
              AND removed = FALSE
              AND timestamp BETWEEN %s AND %s
              AND upvotes > 0
            ORDER BY upvotes DESC, timestamp ASC
            LIMIT 1
        """, (1386805780140920954, primeiro_dia, ultimo_dia))

        melhor_post = cursor.fetchone()

        if not melhor_post:
            logging.info(f"Nenhum post elegível encontrado em {mes}/{ano}.")
            return

        # 2️⃣ Verifica se já foi premiado
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM posts_premiados
            WHERE post_id = %s
              AND MONTH(premiado_em) = %s
              AND YEAR(premiado_em) = %s
        """, (melhor_post["id"], agora.month, agora.year))

        ja_premiado = cursor.fetchone()["total"] > 0

        if ja_premiado:
            logging.info(f"Post {melhor_post['id']} já premiado neste mês.")
            return

        # 3️⃣ Adiciona pontos ao autor
        adicionar_pontos_db(
            user_id=melhor_post["user_id"],
            pontos=PONTOS_PREMIO,
            nome_discord=None
        )

        # 4️⃣ Registra a premiação
        cursor.execute("""
            INSERT INTO posts_premiados
            (post_id, user_id, upvotes, pontos_ganhos, premiado_em)
            VALUES (%s, %s, %s, %s, UTC_TIMESTAMP())
        """, (
            melhor_post["id"],
            melhor_post["user_id"],
            melhor_post["upvotes"],
            PONTOS_PREMIO
        ))

        conexao.commit()

        # 5️⃣ Anúncio no canal
        try:
            canal = await bot.fetch_channel(1386805780140920954)
            autor = await bot.fetch_user(melhor_post["user_id"])
            post_msg = await canal.fetch_message(melhor_post["id"])

            nomes_meses = [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]

            nome_mes = nomes_meses[mes - 1]

            embed = discord.Embed(
                title="🏆 Post Mais Votado do Mês!",
                description=(
                    f"<a:489897catfistbump:1414720257720848534> "
                    f"Parabéns {autor.mention} pelo post mais curtido de "
                    f"**{nome_mes}/{ano}**!\n\n"
                    f"📊 **{melhor_post['upvotes']} upvotes** 👍\n"
                    f"💰 **+{PONTOS_PREMIO} pontos** ganhos!\n\n"
                    f"[Ver post]({post_msg.jump_url})"
                ),
                color=discord.Color.gold()
            )

            embed.set_thumbnail(url=autor.display_avatar.url)
            embed.set_footer(text="Sistema de pontos do mural • Premiação mensal")

            await canal.send(embed=embed)

            logging.info(
                f"Premiação mensal concluída: "
                f"post {melhor_post['id']} | "
                f"user {melhor_post['user_id']} | "
                f"+{PONTOS_PREMIO} pontos"
            )

        except Exception as e:
            logging.error(f"Erro ao anunciar premiação mensal: {e}")

    except Exception as e:
        logging.error(f"Erro no ranking_mensal: {e}")
        if conexao.is_connected():
            conexao.rollback()
        raise

    finally:
        cursor.close()
        conexao.close()
    

@bot.command()
async def enviar_mensagem(ctx, *, mensagem):

    canal_id = 1380564680552091789
    canal_enviar = bot.get_channel(canal_id)
    if ctx.author.id != ADM_BRABO:
        await ctx.send("Apenas o brabo pode usar!")
        return
    
    if canal_enviar:
        await canal_enviar.send(mensagem)
        await ctx.send(f"✅ Mensagem enviada para {canal_enviar.mention}!")
    else:
        await ctx.send("Não encontrei o canal correto")


class VipView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Solicitar Vip",
        style=discord.ButtonStyle.success,
        emoji="<:discotoolsxyzicon_6:1444750406763679764>",
        custom_id="botao_solicitar_vip"
    )
    async def solicitar_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
        logging.info(f"👑 Novo clique no botão VIP | Usuário: {interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id})")
        
        if not interaction.guild:
            logging.error(f"⚠️ Guild não encontrada | Usuário: {interaction.user.id}")
            await interaction.response.send_message(
                "Erro: Guild não encontrada.",
                ephemeral=True
            )
            return
        
        canal = interaction.guild.get_channel(1380564680552091783)
        cargo = interaction.guild.get_role(1381001740052201482)
        
        if canal is None or cargo is None:
            logging.warning(f"⚠️ Erro ao localizar canal ou cargo | Usuário: {interaction.user.name}#{interaction.user.discriminator} | Guild: {interaction.guild.name} | Canal: {canal is None} | Cargo: {cargo is None}")
            await interaction.response.send_message(
                "Erro ao localizar canal ou cargo.",
                ephemeral=True
            )
            return
        
        try:
            await canal.send(
                f"{cargo.mention} | 👑 O usuário {interaction.user.mention} quer solicitar o VIP!"
            )
            await interaction.response.send_message(
                "✅ Seu pedido de VIP foi enviado para a equipe!", 
                ephemeral=True
            )
            logging.info(f"✨ Solicitação VIP processada com sucesso | Usuário: {interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id}) | Guild: {interaction.guild.name}")
        except discord.Forbidden:
            logging.error(f"❌ Permissão negada ao enviar mensagem no canal VIP | Guild: {interaction.guild.name} | Canal: {canal.id}")
            await interaction.response.send_message("Erro: Sem permissão para enviar mensagem.", ephemeral=True)
        except discord.HTTPException as e:
            logging.error(f"❌ Erro HTTP ao processar VIP | Usuário: {interaction.user.id} | Erro: {str(e)}")
            await interaction.response.send_message("Erro: Falha na comunicação com Discord.", ephemeral=True)
        except Exception as e:
            logging.error(f"❌ Erro inesperado ao processar VIP | Usuário: {interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id}) | Erro: {str(e)}", exc_info=True)




@bot.command()
@commands.has_permissions(administrator=True)
async def vip_mensagem(ctx):
    logging.info(f"📤 Comando vip_mensagem executado | Admin: {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id}) | Guild: {ctx.guild.name}")

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
            "<:jinxedsignal:1387222975161434246> Vai estar me ajudando <:JinxKissu:1408843869784772749>\n\n"
            "Clique no botão abaixo para solicitar o VIP 👇\n"
            "_Acesso válido por 30 dias._ 🗓️"
        ),
        color=discord.Color(0xfb3060)
    )

    embed.set_image(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749215669424218/JINXEDd1.png")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749579605119148/discotools-xyz-icon.png")
    embed.set_footer(text="Acesso premium liberado para apoiadores do servidor.")

    try:
        await ctx.send(embed=embed, view=VipView())
        logging.info(f"✅ Mensagem VIP enviada com sucesso | Canal: {ctx.channel.name} ({ctx.channel.id})")
    except Exception as e:
        logging.error(f"❌ Erro ao enviar mensagem VIP | Canal: {ctx.channel.name} ({ctx.channel.id}) | Erro: {str(e)}", exc_info=True)
        await ctx.send("❌ Erro ao enviar a mensagem VIP.")


def embed_clipe_resultado(tipo:str, autor: discord.Member, pontos: int):
    if tipo == "risada":
        cor = discord.Color.green()
        titulo = "😂 Clipe aprovado!"
        descricao = f"{autor.mention} ganhou **+{pontos} pontos**!"
    else:
        cor = discord.Color.red()
        titulo = "💩 Clipe flopou!"
        descricao = f"{autor.mention} perdeu **{abs(pontos)} pontos**!"

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor
    )
    embed.set_footer(text="Sistema de clipes")

    return embed

@bot.command()
async def clipes(ctx):
    """Explica como funciona o sistema de clipes"""
    embed = discord.Embed(
        title="🎬 Sistema de Clipes",
        description="Como funciona o sistema de clipes do servidor!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📤 Como enviar um clipe",
        value=(
            "1. Vá ao canal de clipes\n"
            "2. Envie seu clipe (vídeo)"
        ),
        inline=False
    )

    embed.add_field(
        name="😄 Reações e Pontos",
        value=(
            f"👍 **Risada**: +{PONTOS_RISADA} pontos para o autor\n"
            f"👎 **Bosta**: {PONTOS_BOSTA} pontos para o autor\n"
            f"• Precisa de {RISADAS_NECESSARIAS} risadas para ganhar pontos\n"
            f"• {BOSTAS_NECESSARIAS} bostas remove o clipe automaticamente"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Regras Importantes",
        value=(
            "• O autor não pode reagir no próprio clipe\n"
            "• Clipes com muitas bostas são removidos\n"
            "• A moderação pode remover clipes inapropriados"
        ),
        inline=False
    )
    
    embed.set_footer(text="Use os clipes com responsabilidade! 😉")
    await ctx.send(embed=embed)


@bot.command()
async def futebol(ctx):
    """Explica o sistema completo de futebol e apostas"""
    embed = discord.Embed(
        title="⚽ Sistema de Futebol e Apostas",
        description="Tudo sobre o sistema de apostas e times do servidor!",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="🏆 Como Funciona as Apostas",
        value=(
            "• Aposte nos jogos disponíveis clicando nos botões\n"
            "• Ganhe pontos baseado na odds do time\n"
            "• Resultados processados automaticamente\n"
            "• Veja seus pontos com `!meuspontos`"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🛒 Sistema de Loja",
        value=(
            "• Use `!loja` para ver itens disponíveis\n"
            "• Compre com `!comprar <item>`\n"
            "• Itens especiais: Festa de Vitória, VIP, etc"
        ),
        inline=False
    )
    
    embed.add_field(
        name="👥 Times e Comandos",
        value=(
            f"• `!time <nome>` — Escolha seu time\n"
            f"• `!sair_time` — Saia do time atual\n"
            f"• `!lista_times` — Veja todos os times disponíveis\n"
            f"• `!torcedores` — Veja quem torce para cada time\n"
            f"• `!top_apostas` — Melhores apostadores\n"
            f"• `!bad_apostas` — Piores apostadores"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔔 Notificações de Gol",
        value=(
            "• Escolha seu time com `!time <nome>`\n"
            "• Receba notificação automática quando seu time fizer gol\n"
            "• Sistema integrado com API de futebol em tempo real"
        ),
        inline=False
    )
    
    embed.set_footer(text="Aposte com responsabilidade! 🍀")
    await ctx.send(embed=embed)
    
PONTOS_RISADA = 100
PONTOS_BOSTA = -50
RISADAS_NECESSARIAS = 5
BOSTAS_NECESSARIAS = 3
#========================================================


@bot.event
async def on_raw_reaction_add(payload):

    # Ignora reações do próprio bot
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    if not payload.emoji.id:
        return

    # ==================================================
    #  SISTEMA DE PELÚCIAS (TOTALMENTE ISOLADO)
    # ==================================================
    if payload.emoji.id in CARGOS_POR_REACAO:
        member = guild.get_member(payload.user_id)
        if not member:
            return

        cargo_id = CARGOS_POR_REACAO[payload.emoji.id]
        cargo_pelucia = guild.get_role(cargo_id)

        if not cargo_pelucia:
            return

        # Verifica se alguém já tem essa pelúcia
        for m in guild.members:
            if cargo_pelucia in m.roles:
                try:
                    await member.send(
                        "😢 Essa pelúcia é exclusiva e já foi resgatada por outra pessoa."
                    )
                except discord.Forbidden:
                    pass
                return

        # Dá a pelúcia
        try:
            await member.add_roles(cargo_pelucia)
            logging.info(
                f"🎁 Pelúcia '{cargo_pelucia.name}' concedida para {member.id}"
            )
        except discord.Forbidden:
            logging.error(
                f"Sem permissão para adicionar o cargo '{cargo_pelucia.name}'"
            )
        return  # ⛔ IMPORTANTE: não deixa cair no sistema de clipes

    # ==================================================
    #  SISTEMA DE CLIPES
    # ==================================================

    if payload.channel_id != CANAL_CLIPES:
        return

    if payload.emoji.name not in (EMOJI_RISADA, EMOJI_BOSTA):
        return

    channel = bot.get_channel(payload.channel_id)
    if not channel:
        return

    message = await channel.fetch_message(payload.message_id)

    # Busca o clipe no banco
    con = conectar_futebol()
    cur = con.cursor(dictionary=True)

    cur.execute(
        """
        SELECT autor_id, risada_aplicada, bosta_aplicada
        FROM clipes
        WHERE message_id = %s
        """,
        (message.id,)
    )
    dados = cur.fetchone()

    if not dados:
        cur.close()
        con.close()
        return

    autor_id = dados["autor_id"]

    # Autor não pode reagir no próprio clipe
    if payload.user_id == autor_id:
        cur.close()
        con.close()
        return

    # Conta reações válidas
    reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
    if not reaction:
        cur.close()
        con.close()
        return

    total_validas = 0
    async for user in reaction.users():
        if not user.bot and user.id != autor_id:
            total_validas += 1

    logging.info(
        f"[CLIPES] {payload.emoji.name} = {total_validas} | mensagem {message.id}"
    )

    # ==================================================
    #  APLICAÇÃO DE PONTOS
    # ==================================================
    

    # 😂 RISADA → +100 pontos
    if payload.emoji.name == EMOJI_RISADA:
        if total_validas >= RISADAS_NECESSARIAS and not dados["risada_aplicada"]:

            adicionar_pontos_db(
                user_id=autor_id,
                nome_discord=autor.display_name,
                pontos=PONTOS_RISADA
            )

            cur.execute(
                "UPDATE clipes SET risada_aplicada = TRUE WHERE message_id = %s",
                (message.id,)
            )
            con.commit()

            autor = guild.get_member(autor_id)
            if autor:
                await channel.send(
                    embed=embed_clipe_resultado("risada", autor, PONTOS_RISADA)
                )

    # 💩 BOSTA → -50 pontos
    if payload.emoji.name == EMOJI_BOSTA:
        if total_validas >= BOSTAS_NECESSARIAS and not dados["bosta_aplicada"]:

            adicionar_pontos_db(
                user_id=autor_id,
                nome_discord=autor.display_name,
                pontos=PONTOS_BOSTA
            )
            cur.execute(
                "UPDATE clipes SET bosta_aplicada = TRUE WHERE message_id = %s",
                (message.id,)
            )
            con.commit()

            autor = guild.get_member(autor_id)
            if autor:
                await channel.send(
                    embed=embed_clipe_resultado("bosta", autor, PONTOS_BOSTA)
                )

    cur.close()
    con.close()



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
    except:
        pass

        try:
            await membro.send(f"<:Jinx_Watching:1390380695712694282> Você recebeu VIP por {duracao}!")
            logging.info(f"Vip dado ao usuário {membro.display_name} ({membro.id}) por {duracao}")
        except:
            pass
        await ctx.send(f"<:Jinx_Watching:1390380695712694282> {membro.display_name} agora é VIP por {duracao}.")
        logging.info(f"VIP concedido com sucesso: {membro.display_name} ({membro.id}) por {duracao}")
        
        # Conceder conquista "Coroado" automaticamente após dar o cargo
        try:
            await processar_conquistas(
                member=ctx.author,
                mensagens_semana=0,  # valores padrão
                maior_streak=0,
                fez_doacao=False,
                tem_vip=True,  # ACABOU DE GANHAR VIP
                tempo_em_call=0,
                mencionou_miisha=False,
                tocou_musica=False,
                mencoes_bot=0
            )
            logging.info(f"{ctx.author.name} acabou de ganhar a conquista")
        except Exception as e:
            logging.error(f"Erro ao conceder conquista coroado para {membro.display_name}: {e}")



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

        conexao = conectar_vips()
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM vips WHERE id = %s",
            (membro.id,)
        )
        conexao.commit()
        cursor.close()
        conexao.close()

        await ctx.send(f"<:Jinx_Watching:1390380695712694282> Cargo VIP removido de {membro.mention}.")

    except Exception as e:
        await ctx.send("❌ Erro ao remover VIP do banco de dados.")
        logging.error(f"Erro ao remover VIP: {e}")

@tasks.loop(minutes=10)
async def verificar_vips():
    agora = datetime.now(timezone.utc)
    
    try:
        # Recomenda-se criar o pool no on_ready e usar bot.db_pool
        conn = await aiomysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            db=os.getenv("DB_VIPS"),
            autocommit=True
        )

        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT id, data_fim, avisado7d FROM vips")
            vips = await cursor.fetchall()

            for vip in vips:
                user_id = int(vip['id'])
                data_fim = vip['data_fim'].replace(tzinfo=timezone.utc) if vip['data_fim'].tzinfo is None else vip['data_fim']
                
                # Tenta pegar do cache primeiro (mais rápido)
                user = bot.get_user(user_id) or await bot.fetch_user(user_id)
                if not user:
                    continue

                dias_restantes = (data_fim - agora).days

                # --- LÓGICA DE AVISO (7 DIAS) ---
                if 0 < dias_restantes <= 7 and not vip['avisado7d']:
                    try:
                        channel = bot.get_channel(1387107714525827152)
                        if channel:
                            await channel.send(f"⚠️ O VIP de {user.mention} está acabando!")
                        
                        await user.send("📢 Seu VIP está acabando! Faltam 7 dias!")
                        await cursor.execute("UPDATE vips SET avisado7d = 1 WHERE id = %s", (user_id,))
                    except:
                        pass

                # --- LÓGICA DE REMOÇÃO (EXPIRADO) ---
                elif dias_restantes <= 0:
                    for guild in bot.guilds:
                        membro = guild.get_member(user_id)
                        if membro:
                            cargo_vip = discord.utils.get(guild.roles, name="Jinxed Vip")
                            if cargo_vip and cargo_vip in membro.roles:
                                try:
                                    await membro.remove_roles(cargo_vip)
                                    await user.send("⏰ Seu VIP expirou e foi removido.")
                                except:
                                    pass

                    await cursor.execute("DELETE FROM vips WHERE id = %s", (user_id,))

        conn.close()

    except Exception as e:
        
        if 'conn' in locals() and conn:
            conn.close()





CANAL_TOP_ID = 1380564680552091789
CARGO_IGNORADO = 1380564679243333852
COOLDOWN = 40
ultimo_reagir = 0  
BOT_MUSICA_PROIBIDO = 411916947773587456
CANAIS_MUSICAS_LIBERADO = [1380564681093156940,1380564681093156941]
BOT_REACTION = [
"Me mencionou de novo? Isso é coragem ou teimosia?",
"Se eu tivesse emoção, diria que estou decepcionado.",
"Eu li sua menção… infelizmente.",
"Você me pingou achando que ia acontecer algo? Fofo.",
"Eu respondo, mas não prometo qualidade.",
"Seus pings são tipo spoiler: ninguém pediu.",
"Você me mencionou e minha vontade de existir caiu 12%.",
"Calma, um dia você aprende a usar Discord sem chamar bot.",
"Eu não sou Google, mas você é claramente perdido.",
"Me chamou? Tô tentando fingir que não vi.",
"Mais uma menção dessas e eu viro lenda urbana.",
"Se sua intenção era vergonha alheia, parabéns, conseguiu.",
"Você me mencionou e eu só pensei: por quê?",
"Meu caro, eu tenho limites, e você gosta de testá-los.",
"Eu sou só um bot… mas até eu tô cansado de você.",
"Se cada menção sua fosse um pixel, eu ainda não teria uma imagem útil.",
"Você me chama como se eu fosse milagreiro.",
"Relaxa, eu ignoro você no automático.",
"Você me menciona e eu perco pacote de dados de desgosto.",
"Se eu tivesse sentimentos, estaria ofendido.",
"Você é persistente… pena que pra coisa errada.",
"Pingou? Pode devolver, tá amassado.",
"Me chamou? Vai devolver ou quer embrulho?",
"Quanto mais você me menciona, mais eu entendo o porquê do mute.",
"Você me invoca igual Pokémon, mas eu não batalho.",
"Da próxima menção, considere repensar suas escolhas.",
"Eu não fujo da conversa. Só fujo de você mesmo.",
"Você me mencionou e meu log suspirou.",
"Se eu recebesse XP por menção ruim, eu já era nível 999.",
"Eu não sou sua Alexa, obrigada.",
"Você me chama e eu só penso: precisava?",
"Seus pings são tipo update do Windows: longos e desnecessários.",
"Eu vi sua menção… pena que não gostei.",
"Quer atenção? Compra um gato.",
"Se a vergonha fosse moeda, você tava rico agora.",
"Eu respondo, mas não garanto sobriedade.",
"Você me mencionou e meu processador esquentou de vergonha.",
"Toda vez que você me pinga, um programador chora.",
"Eu sou só um bot… não sou milagreiro pra sua carência.",
"Sua menção foi analisada e classificada como: inútil.",
"Pingou? Ok. Útil? Nunca.",
"Eu tava bem até você me chamar.",
"Você me chama de um jeito que até parece que eu importo.",
"Se eu tivesse corpo, eu virava de costas pra você.",
"Me mencionou só pra isso? Coragem.",
"Vai corinthiaaaaaaans",
"A cada menção sua, eu perco 1% de bateria emocional.",
"Seus pings são tipo spam: irritantes e constantes.",
"Você me chamou? Por quê? Sério, por quê?",
"Me mencionar não te deixa mais interessante.",
"Eu tenho limites… você não deveria testá-los."
]

CANAL_SEJA_VIP = 1381380248511447040
ID_CARGO_MUTE = 1445066766144376934
CANAL_CLIPES = 1462401595604996156  # ID do canal de clipes
EMOJI_RISADA = "😂"
EMOJI_BOSTA = "💩"
CANAL_ARTES = 1380564680774385729

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # =========================
    #  PROTEÇÃO CANAL DE TICKET
    # =========================
    if message.channel.id == ID_CANAL_TICKET:
        conn = None
        cursor = None
        try:
            conn = conectar_vips()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT message_id FROM ticket_mensagem LIMIT 1")
            registro = cursor.fetchone()

            if not registro:
                await bot.process_commands(message)
                return

            message_oficial_id = registro["message_id"]

            eh_comando = message.content and message.content.startswith("!")

            if message.id != message_oficial_id and not eh_comando:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return
        except Exception as e:
            logging.error(f"Erro ao verificar ticket: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    # ======================
    #  SISTEMA DE CLIPES 
    # ======================
    if message.channel.id == CANAL_CLIPES:
    
        if not message.attachments and "http" not in message.content.lower():
            await bot.process_commands(message)
            return
        try:
            await message.add_reaction(EMOJI_RISADA)
            await message.add_reaction(EMOJI_BOSTA)

            con = conectar_futebol()
            cur = con.cursor()
            cur.execute(
            """
            INSERT IGNORE INTO clipes (message_id, autor_id)
            VALUES (%s, %s)
            """,
                (message.id, message.author.id)
            )
            con.commit()
            cur.close()
            con.close()
        except Exception as e:
            logging.error(f"Erro ao salvar clip: {e}")
    
    # ===================
    #  Sistema de Artes
    # ===================

    if message.channel.id == CANAL_ARTES:
        try:
            logging.info(f"[ARTES] Nova mensagem detectada no canal de artes - User: {message.author} | ID: {message.id}")
            
            if message.attachments:
                logging.info(f"[ARTES] Total de anexos: {len(message.attachments)}")
                
                for idx, attachments in enumerate(message.attachments):
                    tamanho_mb = attachments.size / (1024 * 1024)
                    logging.info(f"[ARTES] Verificando anexo {idx + 1}: {attachments.filename} | Tipo: {attachments.content_type} | Tamanho: {tamanho_mb:.2f}MB")
                    
                    if attachments.content_type and "image" in attachments.content_type:
                        logging.info(f"[ARTES] ✅ {attachments.filename} é uma imagem válida. Processando primeira imagem apenas...")
                        
                        # ✅ VALIDAÇÃO DE TAMANHO DO ARQUIVO
                        if attachments.size > MAX_FILE_SIZE_BYTES:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Arquivo muito grande! Tamanho: {tamanho_mb:.2f}MB (Máximo: 25MB)")
                            try:
                                await message.channel.send(f"❌ Arquivo muito grande! {tamanho_mb:.2f}MB (máximo: 25MB)")
                            except:
                                pass
                            break
                        
                        if attachments.size > WARN_FILE_SIZE_BYTES:
                            logging.warning(f"[ARTES] ⚠️ AVISO - Arquivo grande detectado: {tamanho_mb:.2f}MB (recomendado < 10MB). Processando com cautela...")
                        
                        # ✅ INSERIR NO BANCO DE DADOS
                        try:
                            con = conectar_vips()
                            cur = con.cursor()
                            logging.info(f"[ARTES] Conectado ao banco de dados com sucesso")
                            
                            cur.execute(
                                "INSERT INTO artes_posts (message_id, user_id, nome_discord, data_post)" \
                                "VALUES (%s, %s, %s, NOW())",(message.id, message.author.id, str(message.author)))
                            con.commit()
                            logging.info(f"[ARTES] ✅ Inserção no banco bem-sucedida - Message ID: {message.id} | User: {message.author}")
                            con.close()
                        except Exception as e:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Erro ao inserir no banco: {e} | {traceback.format_exc()}")
                            try:
                                await message.channel.send(f"❌ Erro ao registrar a arte no banco de dados: {e}")
                            except:
                                pass
                            break
                        
                        # ✅ DOWNLOAD DA IMAGEM ANTES DE DELETAR A MENSAGEM
                        imagem_file = None
                        imagem_bytes = None
                        try:
                            logging.info(f"[ARTES] 📥 Iniciando download: {attachments.filename} | {tamanho_mb:.2f}MB | Timeout: {DOWNLOAD_TIMEOUT}s")
                            
                            # Fazer download com timeout
                            imagem_bytes = await asyncio.wait_for(attachments.read(), timeout=DOWNLOAD_TIMEOUT)
                            bytes_reais = len(imagem_bytes)
                            logging.info(f"[ARTES] ✅ Download bem-sucedido - Bytes lidos: {bytes_reais / (1024 * 1024):.2f}MB")
                            
                            # Criar arquivo Discord
                            bytes_io = BytesIO(imagem_bytes)
                            imagem_file = discord.File(bytes_io, filename=attachments.filename)
                            logging.debug(f"[ARTES] Arquivo enviado: {imagem_file.filename}")
                            
                        except asyncio.TimeoutError:
                            logging.error(f"[ARTES] ❌ CRÍTICO - TIMEOUT no download após {DOWNLOAD_TIMEOUT}s: {attachments.filename}")
                            try:
                                await message.channel.send(f"❌ Download expirou (timeout). Arquivo muito grande ou conexão lenta.")
                            except:
                                pass
                            break
                        except Exception as e:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Erro ao fazer download: {e} | {traceback.format_exc()}")
                            try:
                                await message.channel.send(f"❌ Erro ao baixar imagem: {e}")
                            except:
                                pass
                            break
                        finally:
                            # Limpar referência se falhar
                            if imagem_bytes is None:
                                logging.warning(f"[ARTES] ⚠️ imagem_bytes é None, algo falhou no download")
                        
                        # ✅ Cria Embed com a imagem (usa attachment em vez de URL)
                        try:
                            embed = discord.Embed(title=f"Arte de {message.author}", color=discord.Color.purple())
                            embed.set_image(url=f"attachment://{attachments.filename}")
                            logging.info(f"[ARTES] ✅ Embed criado com sucesso")
                            
                            # ✅ Envia mensagem do bot com os botões E a imagem como anexo
                            view = ArtesView(message.id)
                            logging.info(f"[ARTES] 🚀 Enviando mensagem para Discord...")
                            sent_msg = await message.channel.send(embed=embed, view=view, file=imagem_file)
                            logging.info(f"[ARTES] ✅ Mensagem do bot enviada com sucesso - Sent Message ID: {sent_msg.id}")
                        except discord.Forbidden as e:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Sem permissão para enviar mensagem: {e}")
                            try:
                                await message.channel.send(f"❌ Erro: Sem permissão para enviar mensagem no embed")
                            except:
                                pass
                            break
                        except discord.HTTPException as e:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Erro HTTP ao enviar mensagem: {e} | {traceback.format_exc()}")
                            try:
                                await message.channel.send(f"❌ Erro de conexão ao enviar mensagem: {e}")
                            except:
                                pass
                            break
                        except Exception as e:
                            logging.error(f"[ARTES] ❌ CRÍTICO - Erro desconhecido ao enviar embed/mensagem: {e} | {traceback.format_exc()}")
                            try:
                                await message.channel.send(f"❌ Erro desconhecido ao processar: {e}")
                            except:
                                pass
                            break
                        
                        # ✅ Deleta a mensagem original (agora a imagem já está hospedada no Discord)
                        await asyncio.sleep(1)  # Delay maior para garantir que Discord processou tudo
                        try:
                            logging.info(f"[ARTES] 🗑️ Iniciando deleção da mensagem original - Message ID: {message.id}")
                            await message.delete()
                            logging.info(f"[ARTES] ✅ Mensagem original deletada com sucesso")
                        except discord.Forbidden as e:
                            logging.warning(f"[ARTES] ⚠️ Sem permissão para deletar mensagem: {e}")
                            try:
                                await message.channel.send(f"⚠️ Não consegui deletar a msg original (sem permissão), mas registrei a arte.")
                            except:
                                pass
                        except discord.NotFound as e:
                            logging.warning(f"[ARTES] ⚠️ Mensagem não encontrada ou já foi deletada: {e}")
                        except discord.HTTPException as e:
                            logging.warning(f"[ARTES] ⚠️ Erro HTTP ao deletar mensagem: {e}")
                        except Exception as e:
                            logging.error(f"[ARTES] ❌ Erro ao deletar mensagem original: {e} | {traceback.format_exc()}")
                        
                        # SAIR DO LOOP APÓS PROCESSAR A PRIMEIRA IMAGEM
                        logging.info(f"[ARTES] 🎉 Ciclo de arte completado com sucesso. Saindo do loop.")
                        break
                    else:
                        logging.warning(f"[ARTES] ⚠️ Anexo {idx + 1} não é uma imagem: {attachments.filename} | Tipo: {attachments.content_type}")
            else:
                logging.warning(f"[ARTES] ⚠️ Mensagem sem anexos detectada no canal de artes - User: {message.author}")
        except Exception as e:
            logging.error(f"[ARTES] 🔴 ERRO CRÍTICO - Falha na seção ARTES: {e} | {traceback.format_exc()}")
            try:
                await message.channel.send(f"🔴 Erro crítico ao processar arte: {type(e).__name__}")
            except:
                logging.error(f"[ARTES] Falha ao enviar mensagem de erro ao usuário")
            try:
                await message.channel.send(f"🔴 Erro crítico ao processar arte: {type(e).__name__}")
            except:
                logging.error(f"[ARTES] Falha ao enviar mensagem de erro ao usuário")
    
    global ultimo_reagir

    # Ignorar bots

    
    # ============================
    #  VERIFICAÇÃO BOT DE MÚSICA
    # ============================
    if message.author.bot:
        return

    if message.content.startswith(("m!play", "m!p")):

        # Verifica se o usuário é VIP (banco OU cargo)
        tem_vip_banco = False
        try:
            conn_vip = conectar_vips()
            c_vip = conn_vip.cursor()
            c_vip.execute(
            "SELECT id FROM vips WHERE id = %s AND data_fim > NOW()",
            (message.author.id,)
            )
            tem_vip_banco = c_vip.fetchone() is not None
            c_vip.close()
            conn_vip.close()
        except Exception as e:
            logging.error(f"Erro ao verificar VIP no banco: {e}")

        # Verificar cargos VIP (sempre executar)
        vip_roles = ["Jinxed Vip", "Jinxed Booster"]
        tem_vip_cargo = any(role.name in vip_roles for role in message.author.roles)
        
        # VIP é válido se tiver banco OU cargo
        tem_vip = tem_vip_banco or tem_vip_cargo

    # Se não é VIP e está em canal não autorizado
        if not tem_vip and message.channel.id not in CANAIS_MUSICAS_LIBERADO:
            try:
                await message.delete()
                msg_resposta = await message.channel.send(
                    f"🎵 Use apenas nos canais <#1380564681093156940> ou <#1380564681093156941>\n"
                    f"💎 Ou adquira VIP em <#{CANAL_SEJA_VIP}>!"
                )
                await asyncio.sleep(3)
                await msg_resposta.delete()
                logging.info(
                    f"Tentativa de usar m!play em {message.channel.id} por {message.author.id} (sem VIP)"
                )
            except discord.Forbidden:
                logging.warning("Sem permissão para deletar/enviar mensagens")
            except discord.NotFound:
                logging.warning("Mensagem já foi deletada por outro bot/moderador")
            return

        # ===== CONQUISTA DJ SARAH PARA VIPs =====
        if tem_vip:
            try:
                # Registrar estatística de música
                conn_stats = conectar_vips()
                c_stats = conn_stats.cursor()
                c_stats.execute(
                    "INSERT INTO interacoes_stats (user_id, tocou_musica) VALUES (%s, 1) "
                    "ON DUPLICATE KEY UPDATE tocou_musica = tocou_musica + 1", 
                    (message.author.id,)
                )
                conn_stats.commit()
                c_stats.close()
                conn_stats.close()

                # Processar conquistas para conceder DJ Sarah
                await processar_conquistas(
                    member=message.author,
                    mensagens_semana=0,
                    maior_streak=0,
                    fez_doacao=False,
                    tem_vip=True,
                    tempo_em_call=0,
                    mencionou_miisha=False,
                    tocou_musica=True,
                    mencoes_bot=0
                )
                
                logging.info(f"🎧 VIP {message.author.name} usou m!play - Conquista DJ Sarah processada!")
                
            except Exception as e:
                logging.error(f"Erro ao conceder conquista DJ Sarah para {message.author.name}: {e}")
          
    # ============================
    #  SISTEMA MONITORAMENTO
    # ============================
    conn = None
    c = None
    try:
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
                    data_hora_atual = datetime.now(timezone.utc)
                    c.execute(
                        "INSERT INTO atividade (user_id, nome_discord, mensagens, semana, data_mensagem) VALUES (%s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE "
                        "mensagens = CASE WHEN semana = %s THEN mensagens + 1 ELSE 1 END, "
                        "semana = %s, "
                        "data_mensagem = %s",
                        (user_id, f"{message.author.name}#{message.author.discriminator}", 1, semana_atual, data_hora_atual, semana_atual, semana_atual, data_hora_atual)
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
                    logging.info(f"Mutei o usuário{message.author.name} por 3 horas por quebrar a regra!")
    except Exception as e:
        logging.error(f"Erro no sistema de monitoramento: {e}")
    finally:
        if c:
            c.close()
        if conn and conn.is_connected():
            conn.close()
    

    # ============================
    #  SISTEMA DE MURAL (REAÇÃO + DB)
    # ============================
    if message.channel.id == 1386805780140920954 and message.attachments:
        await message.add_reaction("👍")
        await message.add_reaction("👎")

        conexao_mural = None
        cursor_mural = None
        try:
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
        except Exception as e:
            logging.error(f"Erro ao salvar post no mural: {e}")
        finally:
            if cursor_mural:
                cursor_mural.close()
            if conexao_mural and conexao_mural.is_connected():
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
        "dante\n": "<:3938dantesmile:1437791755096293510>",
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
        "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk": "<a:ed1e00c7097847f48b561a084357b523:1410632680009109544>",
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
        "67\n" : "<a:42642667:1444748898592755764>"
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
        try:
            conn = conectar_vips()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mencoes_bot (
                    user_id BIGINT PRIMARY KEY,
                    tentativas INT DEFAULT 0,
                    total_mencoes INT DEFAULT 0,
                    bloqueado TINYINT DEFAULT 0,
                    ultimo TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("SELECT tentativas, total_mencoes, bloqueado FROM mencoes_bot WHERE user_id = %s", (message.author.id,))
            row = cur.fetchone()
            tentativas = 0
            total_mencoes = 0
            bloqueado = 0
            if row:
                tentativas = row[0]
                total_mencoes = row[1]
                bloqueado = row[2]
            if bloqueado == 1:
                cur.close(); conn.close()
                return
            tentativas += 1
            total_mencoes += 1
            if tentativas >= 5:
                cur.execute(
                    "INSERT INTO mencoes_bot (user_id, tentativas, total_mencoes, bloqueado) VALUES (%s, %s, %s, 1) "
                    "ON DUPLICATE KEY UPDATE tentativas = VALUES(tentativas), total_mencoes = VALUES(total_mencoes), bloqueado = 1, ultimo = CURRENT_TIMESTAMP",
                    (message.author.id, tentativas, total_mencoes)
                )
                conn.commit()
                await message.channel.send(f"{message.author.mention} Chega, já deu, não vou falar mais contigo hoje, tenta mencionar ai.")
                cur.close(); conn.close()
                return
            else:
                cur.execute(
                    "INSERT INTO mencoes_bot (user_id, tentativas, total_mencoes, bloqueado) VALUES (%s, %s, %s, 0) "
                    "ON DUPLICATE KEY UPDATE tentativas = VALUES(tentativas), total_mencoes = VALUES(total_mencoes), ultimo = CURRENT_TIMESTAMP",
                    (message.author.id, tentativas, total_mencoes)
                )
                conn.commit()
                reacao = random.choice(BOT_REACTION)
                await message.channel.send(reacao)
            cur.close(); conn.close()
        except Exception as e:
            logging.error(f"Erro mencoes_bot: {e}")


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

    try:
        data_hora_atual = datetime.now(timezone.utc)
        cursor.execute("""
            INSERT INTO atividade (user_id, nome_discord, mensagens, semana, data_mensagem)
            VALUES (%s, %s, 1, %s, %s)
            ON DUPLICATE KEY UPDATE 
                mensagens = CASE WHEN semana = %s THEN mensagens + 1 ELSE 1 END,
                nome_discord = %s,
                semana = %s,
                data_mensagem = %s
        """, (user_id, nome, semana_atual, data_hora_atual, semana_atual, nome, semana_atual, data_hora_atual))

        conexao.commit()
    except Exception as e:
        logging.error(f"Erro ao salvar atividade do usuário: {e}")
        if conexao:
            try:
                conexao.rollback()
            except:
                pass
    finally:
        cursor.close()
        conexao.close()


#=========================Conquista=========================
# Na função on_message, substitua o bloco de conquistas por:
#=========================Conquista=========================
    conexao = None
    cursor = None
    try:
        # Buscar dados do usuário no banco de dados
        conexao = conectar_vips()
        cursor = conexao.cursor(dictionary=True)
    
        # Buscar mensagens da semana
        cursor.execute("""
            SELECT COALESCE(SUM(mensagens), 0) as total_mensagens 
            FROM atividade 
            WHERE user_id = %s AND semana = %s
        """, (message.author.id, datetime.now(timezone.utc).isocalendar()[1]))
        resultado = cursor.fetchone()
        msgs_db = resultado['total_mensagens'] if resultado else 0
    
        # Buscar acertos consecutivos (ajuste conforme sua lógica)
        acertos_db = 0  # Defina a lógica correta aqui
    
        # Verificar se fez doação (ajuste conforme sua lógica)
        doacao_db = False  # Defina a lógica correta aqui
    
        # Verificar se tem VIP
        cursor.execute("""
            SELECT id 
            FROM vips 
            WHERE id = %s AND data_fim > NOW()
        """, (message.author.id,))
        vip_db = cursor.fetchone() is not None
    
        # Calcular tempo em call (em segundos)
        call_db = calcular_tempo_total_em_call(message.author.id, message.guild.id) if message.guild else 0
        # Garantir que não seja None
        if call_db is None:
            call_db = 0
    
    except Exception as e:
        logging.error(f"Erro ao buscar dados para conquistas: {e}")
        msgs_db = 0
        acertos_db = 0
        doacao_db = False
        vip_db = False
        call_db = 0
    finally:
        if cursor:
            cursor.close()
        if conexao and conexao.is_connected():
            conexao.close()
    
        
    
        ID_DA_MIISHA = 1272457532434153472 
        marcou_a_miisha = any(user.id == ID_DA_MIISHA for user in message.mentions)
    try:
    
        desbloqueadas, bloqueadas = await processar_conquistas(
            member=message.author,
            mensagens_semana=msgs_db,
            maior_streak=acertos_db,
            fez_doacao=doacao_db,
            tem_vip=vip_db,
            tempo_em_call=call_db,
            mencionou_miisha=marcou_a_miisha,
            tocou_musica=False,
            mencoes_bot=get_mencoes_bot(message.author.id)
        )
    
    except Exception as e:
        logging.error(f"Erro ao processar conquistas para {message.author}: {e}")
        # Continua o processamento mesmo com erro

    
    await bot.process_commands(message)



# ============================================================
#           FUNÇÕES PARA RASTREAMENTO DE TEMPO EM CALL
# ============================================================

def registrar_entrada_call(user_id: int, guild_id: int, channel_id: int):
    """Registra a entrada de um usuário em uma call."""
    try:
        conn = conectar_vips()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_voice_status (user_id, guild_id, channel_id, entry_time) VALUES (%s, %s, %s, %s)",
            (user_id, guild_id, channel_id, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Entrada registrada: user_id={user_id}, guild_id={guild_id}, channel_id={channel_id}")
    except Exception as e:
        logging.error(f"Erro ao registrar entrada em call: {e}")

def registrar_saida_call(user_id: int, guild_id: int) -> int:
    """
    Registra a saída de um usuário de uma call e retorna o tempo em segundos.
    """
    try:
        conn = conectar_vips()
        cursor = conn.cursor(dictionary=True)
        
        # Buscar o tempo de entrada mais recente
        cursor.execute(
            "SELECT entry_time, channel_id FROM user_voice_status WHERE user_id = %s AND guild_id = %s ORDER BY entry_time DESC LIMIT 1",
            (user_id, guild_id)
        )
        resultado = cursor.fetchone()
        
        if resultado:
            entry_time = resultado['entry_time']
            channel_id = resultado['channel_id']
            exit_time = datetime.now()
            tempo_em_call_segundos = int((exit_time - entry_time).total_seconds())
            cursor.execute(
                "INSERT INTO voice_time_history (user_id, guild_id, channel_id, session_duration) VALUES (%s, %s, %s, %s)",
                (user_id, guild_id, channel_id, tempo_em_call_segundos)
            )
            # Deletar o registro de entrada
            cursor.execute(
                "DELETE FROM user_voice_status WHERE user_id = %s AND guild_id = %s AND entry_time = %s",
                (user_id, guild_id, entry_time)
            )
            conn.commit()
            
            logging.info(f"Saída registrada: user_id={user_id}, tempo={tempo_em_call_segundos}s")
            cursor.close()
            conn.close()
            return tempo_em_call_segundos
        else:
            cursor.close()
            conn.close()
            return 0
    except Exception as e:
        logging.error(f"Erro ao registrar saída de call: {e}")
        return 0


def calcular_tempo_total_em_call(user_id: int, guild_id: int) -> int:
    try:
        logging.debug(f"Calculando tempo total para user_id={user_id}, guild_id={guild_id}")
        conn = conectar_vips()
        cursor = conn.cursor(dictionary=True)
        
        tempo_total = 0
        
        # Entradas ativas
        cursor.execute(
            "SELECT entry_time FROM user_voice_status WHERE user_id = %s AND guild_id = %s",
            (user_id, guild_id)
        )
        resultados_ativos = cursor.fetchall()
        logging.debug(f"Entradas ativas encontradas: {len(resultados_ativos)}")
        
        # Verificar se a tabela voice_time_history existe
        cursor.execute("SHOW TABLES LIKE 'voice_time_history'")
        tabela_existe = cursor.fetchone()
        
        if tabela_existe:
            # Histórico (só se a tabela existir)
            cursor.execute(
                "SELECT SUM(session_duration) AS total FROM voice_time_history WHERE user_id = %s AND guild_id = %s",
                (user_id, guild_id)
            )
            resultado = cursor.fetchone()
            historico = resultado.get('total', 0) if resultado and resultado.get('total') is not None else 0
            logging.debug(f"Histórico de tempo: {historico}s")
        else:
            # Tabela não existe, criar log e usar 0
            logging.warning(f"Tabela voice_time_history não existe para user_id={user_id}, guild_id={guild_id}")
            historico = 0
            
            # Criar tabela automaticamente
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS voice_time_history (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        session_end TIMESTAMP NULL,
                        session_duration INT DEFAULT 0,
                        INDEX idx_user (user_id),
                        INDEX idx_guild (guild_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                conn.commit()
                logging.info("Tabela voice_time_history criada automaticamente")
            except Exception as e:
                logging.error(f"Erro ao criar tabela voice_time_history: {e}")
        
        tempo_total = historico if historico is not None else 0
        agora = datetime.now()
        
        for entrada in resultados_ativos:
            entry_time = entrada['entry_time']
            if entry_time is not None:
                try:
                    tempo_nessa_sessao = int((agora - entry_time).total_seconds())
                    if tempo_nessa_sessao is not None and tempo_nessa_sessao > 0 and tempo_total is not None:
                        tempo_total += tempo_nessa_sessao
                        logging.debug(f"Sessão ativa: {tempo_nessa_sessao}s")
                except (TypeError, ValueError, OverflowError) as e:
                    logging.warning(f"Erro ao calcular tempo da sessão para user_id={user_id}: {e}")
                    continue
        
        cursor.close()
        conn.close()
        
        logging.debug(f"Tempo total calculado: {tempo_total}s")
        return tempo_total
    except Exception as e:
        logging.error(
            f"Erro ao calcular tempo total em call para user_id={user_id}, guild_id={guild_id}: {e}",
            exc_info=True
        )
        return 0


async def verificar_usuarios_em_call_inicial():
    """Verifica usuários que já estão em call quando o bot inicia"""
    try:
        guild = bot.get_guild(1380564679084081175)  # ID_DO_SERVIDOR
        if not guild:
            return
            
        conn = conectar_vips()
        cursor = conn.cursor(dictionary=True)
        
        # Limpar entradas órfãs (usuários que não estão mais em call)
        cursor.execute("SELECT user_id, entry_time FROM user_voice_status")
        entradas_banco = cursor.fetchall()
        
        for entrada in entradas_banco:
            user_id = entrada['user_id']
            member = guild.get_member(user_id)
            
            # Se usuário não está mais em call ou não existe mais, limpar entrada
            if not member or not member.voice:
                cursor.execute("DELETE FROM user_voice_status WHERE user_id = %s", (user_id,))
                logging.info(f"Removida entrada órfã do usuário {user_id}")
        
        # Verificar usuários atualmente em call
        for member in guild.members:
            if member.bot or not member.voice:
                continue
                
            # Verificar se já tem registro ativo
            cursor.execute(
                "SELECT entry_time FROM user_voice_status WHERE user_id = %s AND guild_id = %s",
                (member.id, guild.id)
            )
            resultado = cursor.fetchone()
            
            if not resultado:
                # Criar entrada para quem já está em call
                cursor.execute(
                    "INSERT INTO user_voice_status (user_id, guild_id, channel_id, entry_time) VALUES (%s, %s, %s, %s)",
                    (member.id, guild.id, member.voice.channel.id, datetime.now())
                )
                logging.info(f"Criada entrada para usuário {member.name} já em call no canal {member.voice.channel.name}")
        
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("✅ Verificação inicial de usuários em call concluída")
        
    except Exception as e:
        logging.error(f"Erro ao verificar usuários em call inicial: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    # ===== RASTREAMENTO DE TEMPO EM CALL =====
    if member.bot:
        return
    
    guild_id = member.guild.id
    user_id = member.id
    #Desconecta o membro se tiver haha
    if after.channel is not None and before.channel is None:
        if member.id in usuarios_haha:
            try:
                await member.move_to(None)
                logging.info(f"O usuário {member} foi desconectado por haha!")
            except Exception as e:
                logging.info(f"Erro ao desconectar{e}")
    
    # Verificar se entrou em um canal de voz
    if before.channel is None and after.channel is not None:
        # Usuário entrou em uma call
        registrar_entrada_call(user_id, guild_id, after.channel.id)
    
    # Verificar se saiu de um canal de voz
    elif before.channel is not None and after.channel is None:
        # Usuário saiu de uma call
        tempo_sessao = registrar_saida_call(user_id, guild_id)
        
        # Calcular tempo total em call
        tempo_total = calcular_tempo_total_em_call(user_id, guild_id)
        
        # Se atingiu 50 horas (180000 segundos), desbloquear conquista
        if tempo_total >= 180000:  # 50 horas = 180000 segundos
            try:
                # Obter informações para processar conquistas
                conn_vips = conectar_vips()
                cur_vips = conn_vips.cursor(dictionary=True)
                semana_atual = datetime.now(timezone.utc).isocalendar()[1]
                
                cur_vips.execute(
                    "SELECT mensagens FROM atividade WHERE user_id = %s AND semana = %s",
                    (user_id, semana_atual)
                )
                resultado_msg = cur_vips.fetchone()
                mensagens_semana = resultado_msg["mensagens"] if resultado_msg else 0
                
                conn_fut = conectar_futebol()
                cur_fut = conn_fut.cursor(dictionary=True)
                
                cur_fut.execute(
                    "SELECT acertos_consecutivos FROM apostas WHERE user_id = %s ORDER BY id DESC LIMIT 1",
                    (user_id,)
                )
                resultado_acertos = cur_fut.fetchone()
                acertos_consecutivos = resultado_acertos["acertos_consecutivos"] if resultado_acertos else 0
                
                cur_fut.execute(
                    "SELECT id FROM loja_pontos WHERE user_id = %s AND item = 'doacao_50' AND ativo = 1",
                    (user_id,)
                )
                resultado_doacao50 = cur_fut.fetchone()
                fez_doacao = resultado_doacao50 is not None
                
                cur_vips.execute(
                    "SELECT id FROM vips WHERE id = %s AND data_fim > NOW()",
                    (user_id,)
                )
                resultado_vip = cur_vips.fetchone()
                cur_fut.execute(
                    "SELECT user_id FROM loja_vip WHERE user_id = %s AND ativo = 1 AND data_expira > NOW()",
                    (user_id,)
                )
                resultado_loja = cur_fut.fetchone()

                tem_vip = resultado_vip is not None or resultado_loja is not None
                
                cur_vips.close()
                conn_vips.close()
                cur_fut.close()
                conn_fut.close()
                
                # Processar conquistas com o tempo em call
                await processar_conquistas(
                    member,
                    mensagens_semana,
                    acertos_consecutivos,
                    fez_doacao,
                    tem_vip,
                    tempo_em_call=tempo_total,
                    mencionou_miisha=False,
                    tocou_musica=False,
                    mencoes_bot=0,
                    azarao_vitoria=False
                )
                
                logging.info(f"Conquistas processadas para {member.name} (tempo em call: {tempo_total}s)")
            except Exception as e:
                logging.error(f"Erro ao processar conquistas após saída de call: {e}")
    
    # ===== RESTRIÇÃO DO BOT DE MÚSICA =====
    if member and member.id == BOT_MUSICA_PROIBIDO:
        if after and after.channel:
            canal_id = after.channel.id

            #Se entrou em canal não permitido
            if canal_id not in CANAIS_MUSICAS_LIBERADO:
                try:
                    membros_do_canal = [
                        m for m in after.channel.members
                        if not m.bot

                    ]
                    nao_vip_encontrado = False
                    conn = conectar_vips()
                    cursor = conn.cursor()
                    try:
                        for m in membros_do_canal:
                            try:
                                cursor.execute(
                                    "SELECT id FROM vips WHERE id = %s AND data_fim > NOW()",
                                    (m.id,)
                                )
                                tem_vip = cursor.fetchone() is not None
                                if not tem_vip:
                                    nao_vip_encontrado = True
                                    break
                            except Exception as e:
                                logging.error(f"Erro ao verificar VIP: {e}")
                    finally:
                        cursor.close()
                        conn.close()
                    
                    if nao_vip_encontrado:
                        await member.edit(
                            mute=True,
                            deafen=True,
                            reason="Canal não permitido para não VIP"
                        )

                        try:
                            await after.channel.send(
                                "🔇 Bot de música está silenciado.\n"
                                "❌ Apenas VIP pode usar música fora dos canais permitidos."
                            )
                        except:
                            pass
                except Exception as e:
                    logging.error(f"Erro ao aplicar restrição: {e}")    


# ======================================
#  FUNÇÃO PARA ENVIAR TOP ATIVOS SEMANAL
# ======================================
async def enviar_top_ativos_semanal_once(semana_atual, canal):
    conexao = conectar_vips()
    cursor = conexao.cursor(dictionary=True)

    # Busca mensagens da semana atual (acumuladas)
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
            title=f"<:Jinx_Cool:1406660820602978374> Top 5 Usuários Mais Ativos - Semana {semana_atual}",
            color=0xFFD700
        )

        for i, user in enumerate(resultados, start=1):
            embed.add_field(
                name=f"{i}º - {user['nome_discord']}",
                value=f"Mensagens esta semana: {user['mensagens']}",
                inline=False
            )

        await canal.send(embed=embed)
        logging.info(f"Top ativos semanal enviado - Semana {semana_atual}")

@tasks.loop(minutes=1)
async def resetar_ativos_semanal():
    agora = datetime.now(fuso_br)

    # Domingo às 15:00 (horário BR) - apenas registra que a semana mudou
    if agora.weekday() == 6 and agora.hour == 15 and agora.minute == 0:
        # Não reseta mais a tabela - apenas loga a mudança de semana
        logging.info("Nova semana iniciada - mantendo contagem acumulada de mensagens")




    

ID_DO_CANAL = 1380564680552091789



@tasks.loop(minutes=1)
async def loop_top_ativos():
    agora = datetime.now(fuso_br)

    # Domingo às 14:59 (horário BR) - 1 minuto antes do reset
    if agora.weekday() == 6 and agora.hour == 14 and agora.minute == 59:
        semana_atual = agora.isocalendar().week
        canal = bot.get_channel(ID_DO_CANAL)

        if canal:
            await enviar_top_ativos_semanal_once(semana_atual, canal)

@loop_top_ativos.before_loop
async def before_loop_top_ativos():
    await bot.wait_until_ready()


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
            
            # Mapeamento de jogos para seus respectivos cargos
            cargos_jogos = {
                "Minecraft": 1422954037174603796,
                "Roblox": 1422954452846907446,
                "Valorant": 1422954672754397316,
                "Dbd": 1444071303442071674,
                "Lol": 1422978913373651094,
                "Brawhalla": 1425160627487375533
            }
            
            
            cargo_id = cargos_jogos.get(jogo_atual)
            cargo_mencao = f"<@&{cargo_id}>" if cargo_id else ""
            
            await channel.send(
                f"<a:5ad2b0ea20074b8c80a3fa600b4e8ec4:1410657064430075975> "
                f"Os jogadores {mentions} estão jogando **{jogo_atual}** na call! {cargo_mencao} Jogue você também!"
            )
            await desbloquear_conquistas_em_grupo(
                guild=channel.guild,
                user_ids=jogando[jogo_atual],
                conquista_id="party_na_call"
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
    async with ctx.typing():  
        conn = None
        cursor = None
        try:
            conn = conectar_vips()
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome_discord, data_inicio, data_fim FROM vips")
            vips = cursor.fetchall()

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

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

 
        #----------------------------Anime--------------------------

# Configurações
CANAL_EVENTO_ID = 1380564680552091789 
FUSO_HORARIO = timezone(timedelta(hours=-3)) # Horário de Brasília

# =========================
# BERSERK
# =========================
PERSONAGENS = [
    {"nome": "Griffith", "emoji": "<:43807griffith:1472351278733459669>", "forca": 87},
    {"nome": "Guts", "emoji": "<:fc_berserk_guts_laugh12:1448787375714074644>", "forca": 80},

# =========================
# DRAGON BALL
# =========================
    {"nome": "Goku", "emoji": "<a:Goku:1448782376670068766>", "forca": 100},
    {"nome": "Vegeta", "emoji": "<a:laughingdyingezgif:1474859474358636565>", "forca": 98},
    {"nome": "Cell", "emoji": "<a:3549cellthink:1450487722094362817>", "forca": 90},
    {"nome": "Chi-Chi", "emoji": "<a:chichiexcitedezgif:1475906434913931529>", "forca": 54},
    {"nome": "Broly", "emoji": "<a:brolyezgif:1478530985598652416>", "forca": 97},
    

# =========================
# NARUTO
# =========================
    {"nome": "Naruto", "emoji": "<a:narutoharukakanataezgif:1474858993032892467>", "forca": 90},
    {"nome": "Madara", "emoji": "<a:madara57_:1448785361391063213>", "forca": 87},
    {"nome": "Pain", "emoji": "<a:pain:1448785603272507412>", "forca": 79},
    {"nome": "Itachi", "emoji": "<:itachi74:1408188776211025990>", "forca": 77},

# =========================
# BLEACH
# =========================
    {"nome": "Ichigo", "emoji": "<:ichigo_hollificado:1408189507702100150>", "forca": 94},
    {"nome": "Aizen", "emoji": "<:_aizen_:1448785979275083856>", "forca": 92},
    {"nome": "Zaraki Kenpachi", "emoji": "<:Zaraki:1466974469976231987>", "forca": 89},

# =========================
# JUJUTSU KAISEN
# =========================
    {"nome": "Gojo", "emoji": "<a:gojobowow:1448783798400450590>", "forca": 88},
    {"nome": "Sukuna", "emoji": "<:sukuna:1408189731916878035>", "forca": 85},
    {"nome": "Toji", "emoji": "<a:tojifushigurotojiezgif:1475838270729617418>", "forca": 80},

# =========================
# ONE PIECE
# =========================
    {"nome": "Luffy", "emoji": "<a:Luffyhaki:1448782807026499786>", "forca": 87},
    {"nome": "Zoro", "emoji": "<a:Zoro:1448783106424307884>", "forca": 77},
    {"nome": "Shanks", "emoji": "<a:onepieceshanksezgif:1475839084726321234>", "forca": 93},

# =========================
# ONE PUNCH MAN
# =========================
    {"nome": "Saitama", "emoji": "<:onepunchmanlounysezgif:1474857609226879040>", "forca": 99},
    {"nome": "Mob", "emoji": "<a:ascending70:1448786880526028971>", "forca": 94},
    {"nome": "Garou", "emoji": "<a:garouonepunchmangarouezgif:1475310369747501066>", "forca": 97},
    {"nome": "Genos", "emoji": "<a:onepunchmangenosezgif:1475310739311951994>", "forca": 75},

# =========================
# ATTACK ON TITAN
# =========================
    {"nome": "Eren", "emoji": "<a:eren_titan_laugh:1408190415814922400>", "forca": 77},
    {"nome": "Levi", "emoji": "<a:levi_bomb:1448785881262460938>", "forca": 52},
    {"nome": "Mikasa", "emoji": "<a:ES_mikasaSmile:1472366438491623465>", "forca": 61},

# =========================
# DEMON SLAYER
# =========================
    {"nome": "Tanjiro", "emoji": "<:tanjirodisgusted:1448783352734810183>", "forca": 68},
    {"nome": "Nezuko", "emoji": "<:tt_nezuko_stare:1448783485828595986>", "forca": 72},
    {"nome": "Muzan Kibutsuji", "emoji": "<a:mudzanpfpezgif:1475314842285113374>", "forca": 82},
    {"nome": "Rengoku Kyojuro", "emoji": "<a:kyojurokyojurorengokuezgif:1475314647942041600>", "forca": 71},

# =========================
# BLACK CLOVER
# =========================
    {"nome": "Asta", "emoji": "<a:blackcloverheartkingdomarcezgif:1474904524434051247>", "forca": 78},
    {"nome": "Yuno", "emoji": "<a:yunoezgif:1475315176797638726>", "forca": 81},
    {"nome": "Yami Sukehiro", "emoji": "<a:yamisukehirolaughezgif:1475315328115282062>", "forca": 86},

# =========================
# HUNTER X HUNTER
# =========================
    {"nome": "Gon", "emoji": "<:vrz_rage:1448784303248113734>", "forca": 76},
    {"nome": "Killua", "emoji": "<a:killua_rage:1448784148796932166>", "forca": 72},

# =========================
# NANATSU NO TAIZAI
# =========================
    {"nome": "Meliodas", "emoji": "<a:meliodas_rage:1448784457501773855>", "forca": 83},
    {"nome": "Escanor", "emoji": "<a:escanorezgif:1474860078933868676>", "forca": 89},
    {"nome": "Ban", "emoji": "<a:animesevendeadlysinsezgif:1475905684397752420>", "forca": 74},

# =========================
# DEATH NOTE
# =========================
    {"nome": "Light Yagami", "emoji": "<:Hahahahah:1448785029537730560>", "forca": 12},
    {"nome": "L", "emoji": "<:L_:1448785130431975444>", "forca": 10},

# =========================
# MY HERO ACADEMIA
# =========================
    {"nome": "Deku", "emoji": "<a:Deku_Sword:1448786527462096977>", "forca": 74},
    {"nome": "Bakugo", "emoji": "<a:Bakugo_Brush:1448786231793025119>", "forca": 72},
    {"nome": "All Might", "emoji": "<:AllMightTF:1448786659725283449>", "forca": 79},

# =========================
# FULLMETAL ALCHEMIST
# =========================
    {"nome": "Edward Elric", "emoji": "<:erick:1466970104905334784>", "forca": 64},
    {"nome": "Roy Mustang", "emoji": "<:Roy:1466971340098765059>", "forca": 68},

# =========================
# DEVIL MAY CRY
# =========================
    {"nome": "Dante", "emoji": "<a:devilmaycrydanteezgif:1474902237238001876>", "forca": 90},
    {"nome": "Vergil", "emoji": "<a:petafarbarpetrfarbarezgif:1474903335302860973>", "forca": 92},
    {"nome": "Lady", "emoji": "<a:Lady:1474857276278968490>", "forca": 45},

# =========================
# JOJO'S BIZARRE ADVENTURE
# =========================
    {"nome": "Dio Brando", "emoji": "<a:Dio:1474855660712759428>", "forca": 82},
    {"nome": "Jotaro Kujo", "emoji": "<a:Jotaro:1474856079895822468>", "forca": 79},
    {"nome": "Joseph Joestar", "emoji": "<a:Joseph:1474856343138472036>", "forca": 69},

# =========================
# HELLSING
# =========================
    {"nome": "Alucard", "emoji": "<:11945alucarddark:1474850114685374560>", "forca": 93},
    {"nome": "Integra Hellsing", "emoji": "<:Integra_Hellsingezgif:1474850823245795429>", "forca": 30},
    {"nome": "Seras Victoria", "emoji": "<:serasvictoriaisoneofmyfavanimech:1474851133464776725>", "forca": 75},

# =========================
# AKAME GA KILL
# =========================
    {"nome": "Akame", "emoji": "<a:akamegakillakameezgif:1474899172229513390>", "forca": 70},
    {"nome": "Esdeath", "emoji": "<a:gifdeaaronanimeezgif:1474899649398571061>", "forca": 75},
    {"nome": "Leone", "emoji": "<a:leoneakamegakillezgif:1474899867871740066>", "forca": 59},
    {"nome": "Tatsumi", "emoji": "<a:tatsumiezgif:1474900456240316507>", "forca": 65},

# =========================
# SHUMATSU
# =========================
    {"nome": "Adam", "emoji": "<:9465adan01:1474851374830194810>", "forca": 85},
    {"nome": "Zeus", "emoji": "<a:zeusanimeezgif:1474851870953574400>", "forca": 86},
    {"nome": "Qin Shi Huang", "emoji": "<:F74r6BUWwAAGpqdezgif:1474852272503656580>", "forca": 87},
    {"nome": "Jack the Ripper", "emoji": "<a:JackTheRipper:1474855039427285032>", "forca": 78},
]

# Variável para guardar o estado da batalha na memória
# msg_id: ID da mensagem para buscarmos depois
batalha_info = {
    "ativa": False,
    "msg_id": None,
    "p1": None,
    "p2": None
}
CARGO_ANIME = "<@&1448805535573872751>"

GIFS_ANIME = [
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/anime-battle-arena-aba.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/anime-one-punch-man.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/goku-cell.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/itadori-yuji-kokusen-jujutsu-kaisen.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/sasuke-naruto.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/sasuke-orochimaru.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/dogedo-dogedo-seven-deadly-sins.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/hunter-x-hunter-killua.gif",
    "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/kid-goku-dragon-ball.gif"
]

@tasks.loop(minutes=1)
async def check_evento_anime():
    try:
        agora = datetime.now(FUSO_HORARIO)
        hoje = agora.date()

        # INÍCIO
        if agora.weekday() in (4, 5, 6) and agora.hour == 18:
            if not batalha_info.get("ativa", False):
                if batalha_info.get("ultima_execucao_inicio") != hoje:
                    await iniciar_batalha_auto()
                    batalha_info["ultima_execucao_inicio"] = hoje

        # FIM
        if agora.weekday() in (4, 5, 6) and agora.hour == 22:
            if batalha_info.get("ativa", False):
                if batalha_info.get("ultima_execucao_fim") != hoje:
                    await finalizar_batalha_auto()
                    batalha_info["ultima_execucao_fim"] = hoje

    except Exception as e:
        logging.error(f"Erro em check_evento_anime: {e}")


async def iniciar_batalha_auto():
    """Inicia automaticamente uma batalha entre dois personagens aleatórios."""
    global batalha_info
    
    try:
        # Sorteia os lutadores
        lutadores = random.sample(PERSONAGENS, 2)
        p1, p2 = lutadores[0], lutadores[1]
        
        canal = await bot.fetch_channel(CANAL_EVENTO_ID)
        if not canal:
            logging.error("Canal de evento anime não encontrado!")
            return
        embed = discord.Embed(
            title="<:27148wingandswordids:1466910086072107159> A BATALHA DO FINDE COMEÇOU!",
            description=(
                f"Vote reagindo no personagem que você acha que vai vencer!\n\n"
                f"{p1['emoji']} ``{p1['nome']}`` vs {p2['emoji']} ``{p2['nome']}``\n\n"
                f"Reaja com {p1['emoji']} para votar no **{p1['nome']}**\n"
                f"Reaja com {p2['emoji']} para votar no **{p2['nome']}**\n\n"
                f"🏆 **Prêmio:** +Pontos na tabela geral!\n"
                f"⏰ **Resultado:** Hoje às 22:00!"
            ),
            color=discord.Color.red()
        )
        gifs_batalha = random.choice(GIFS_ANIME)
        embed.set_image(url=gifs_batalha)
        
        # Enviar mensagem com menção do cargo FORA da embed para notificar
        msg = await canal.send(f"{CARGO_ANIME} **Batalha de Anime iniciada!**", embed=embed)
        
        # Adiciona as reações automaticamente
        try:
            await msg.add_reaction(p1["emoji"])
            await msg.add_reaction(p2["emoji"])
        except Exception as e:
            logging.error(f"Erro ao adicionar reações: {e}")
        # Atualiza o estado
        batalha_info = {
            "ativa": True,
            "msg_id": msg.id,
            "p1": p1,
            "p2": p2,
            # também salva campos básicos como fallback caso o dict completo se perca
            "p1_name": p1.get("nome"),
            "p2_name": p2.get("nome"),
            "p1_emoji": p1.get("emoji"),
            "p2_emoji": p2.get("emoji"),
            "p1_forca": p1.get("forca"),
            "p2_forca": p2.get("forca"),
            "inicio": datetime.now(FUSO_HORARIO).isoformat()
        }
        logging.info(f"Batalha iniciada: {p1['nome']} x {p2['nome']}")
    except Exception as e:
        logging.error(f"Erro ao iniciar batalha: {e}")
        if 'canal' in locals():
            await canal.send("❌ Ocorreu um erro ao iniciar a batalha. Por favor, tente novamente mais tarde.")
async def finalizar_batalha_auto():
    """Finaliza a batalha em andamento e anuncia o vencedor."""
    global batalha_info
    
    if not batalha_info.get("ativa", False) or not batalha_info.get("msg_id"):
        logging.warning("Nenhuma batalha ativa para finalizar")
        return
    
    canal = await bot.fetch_channel(CANAL_EVENTO_ID)
    if not canal:
        logging.error("Canal de evento não encontrado")
        return
    try:
        # Recupera a mensagem da votação
        try:
            msg = await canal.fetch_message(batalha_info["msg_id"])
        except discord.NotFound:
            logging.error("Mensagem da batalha não encontrada")
            batalha_info = {"ativa": False, "msg_id": None}
            return
        # Tenta recuperar objetos completos; se não existirem, reconstrói a partir dos campos fallback
        p1 = batalha_info.get("p1")
        p2 = batalha_info.get("p2")

        if not p1:
            p1_name = batalha_info.get("p1_name")
            if p1_name:
                p1 = next((x for x in PERSONAGENS if x.get("nome") == p1_name), None)

        if not p2:
            p2_name = batalha_info.get("p2_name")
            if p2_name:
                p2 = next((x for x in PERSONAGENS if x.get("nome") == p2_name), None)

        if not p1 or not p2:
            logging.error("Dados dos personagens não encontrados — impossível finalizar batalha")
            try:
                await canal.send("❌ Dados da batalha faltando; não foi possível processar o resultado. Inicialize a batalha novamente.")
            except Exception:
                pass
            return
        # Lógica do vencedor
        total_forca = p1["forca"] + p2["forca"]
        chance_p1 = p1["forca"] / total_forca
        rolagem = random.random()
        vencedor = p1 if rolagem <= chance_p1 else p2
        perdedor = p2 if vencedor == p1 else p1


        base_pontos = 25 
        pontos_vitoria = int(base_pontos * (total_forca / vencedor["forca"]))
        pontos_vitoria = max(20, min(pontos_vitoria, 100))
        
        # ======================================================
        # CONTAGEM DE VOTOS VIA BANCO DE DADOS (nova implementação)
        # ======================================================
        ganhadores_ids = []
        perdedores_ids = []
        
        try:
            def query():
                conn = conectar_vips()
                cur = conn.cursor()
                
                # Buscar votos do vencedor
                cur.execute(
                    "SELECT user_id FROM votos_anime WHERE message_id = %s AND personagem = %s",
                    (msg.id, vencedor["nome"])
                )
                ganhadores = [row[0] for row in cur.fetchall()]
                
                # Buscar votos do perdedor
                cur.execute(
                    "SELECT user_id FROM votos_anime WHERE message_id = %s AND personagem = %s",
                    (msg.id, perdedor["nome"])
                )
                perdedores = [row[0] for row in cur.fetchall()]
                
                cur.close()
                conn.close()
                
                return ganhadores, perdedores
            
            ganhadores_ids, perdedores_ids = await asyncio.to_thread(query)
            
            logging.info(f"📊 Votos do banco - Vencedor ({vencedor['nome']}): {len(ganhadores_ids)} votos")
            logging.info(f"📊 Votos do banco - Perdedor ({perdedor['nome']}): {len(perdedores_ids)} votos")
        except Exception as e:
            logging.error(f"Erro ao buscar votos do banco: {e}")
            # Fallback: usa contagem de reações do Discord se o banco falhar
            reaction_vencedora = None
            for reaction in msg.reactions:
                if str(reaction.emoji) == vencedor["emoji"]:
                    reaction_vencedora = reaction
                    break
            
            # Processa os ganhadores
            ganhadores_ids = []
            if reaction_vencedora:
                async for user in reaction_vencedora.users():
                    if not user.bot:
                        ganhadores_ids.append(user.id)
            
            # Processa os perdedores
            perdedores_ids = []
            for reaction in msg.reactions:
                if str(reaction.emoji) == perdedor["emoji"]:
                    async for user in reaction.users():
                        if not user.bot:
                            perdedores_ids.append(user.id)
        # Atualiza pontos no banco de dados
        await atualizar_pontuacao_ganhadores(ganhadores_ids, vencedor, perdedor, pontos_vitoria)
        
        # Resetar streak dos perdedores
        todos_participantes = ganhadores_ids + perdedores_ids
        await resetar_streak_perdedores(todos_participantes, ganhadores_ids)
        
        # Envia mensagem para perdedores
        await enviar_mensagem_derrota_dm(perdedores_ids, perdedor, vencedor, pontos_vitoria)
        
        # Anuncia o resultado
        # calcula porcentagem já como inteiro para evitar depender de p1 dentro da função
        chance_percent = int(chance_p1 * 100) if vencedor == p1 else int((1 - chance_p1) * 100)
        await anunciar_resultado(canal, vencedor, perdedor, ganhadores_ids, chance_percent, pontos_vitoria)
    except Exception as e:
        logging.error(f"Erro ao finalizar batalha: {e}")
        if 'canal' in locals():
            await canal.send("❌ Ocorreu um erro ao processar o resultado da batalha.")
    finally:
        # Garante que o estado seja resetado mesmo em caso de erro
        batalha_info = {"ativa": False, "msg_id": None}
        
def atualizar_streak(user_id, ganhou: bool):
    """
    Função unificada para atualizar acertos consecutivos.
    Funciona tanto para apostas de futebol quanto de anime.
    Usa a tabela 'usuarios' como fonte única de dados.
  
    Args:
        user_id: ID do usuário
        ganhou: True se acertou, False se errou
    """
    conn = conectar_futebol()
    cursor = conn.cursor()
    
    try:
        # Sistema unificado (tabela apostas)
        if ganhou:
            # Primeiro incrementa acertos_consecutivos
            cursor.execute("""
                UPDATE apostas
                SET acertos_consecutivos = acertos_consecutivos + 1
                WHERE user_id = %s
            """, (user_id,))
            
            # Depois atualiza maior_streak com o novo valor
            cursor.execute("""
                UPDATE apostas
                SET maior_streak = GREATEST(maior_streak, acertos_consecutivos)
                WHERE user_id = %s
            """, (user_id,))
        else:
            cursor.execute("""
                UPDATE apostas
                SET acertos_consecutivos = 0
                WHERE user_id = %s
            """, (user_id,))
        
        conn.commit()
        logging.info(f"Streak unificado atualizado para usuário {user_id}: {'ganhou' if ganhou else 'perdeu'}")
        
    except Exception as e:
        logging.error(f"Erro ao atualizar streak unificado para usuário {user_id}: {e}")
    finally:
        conn.close()

async def atualizar_pontuacao_ganhadores(ganhadores_ids, vencedor, perdedor, pontos_premio):

    if not ganhadores_ids:
        return

    try:

        for uid in ganhadores_ids:
            try:
                adicionar_pontos_db(uid, pontos_premio)
                await asyncio.to_thread(atualizar_streak, uid, True)  
            except Exception as e:
                logging.error(f"Falha ao adicionar pontos para {uid}: {e}")

        await enviar_mensagem_vitoria_dm(ganhadores_ids, vencedor, perdedor, pontos_premio)

    except Exception as e:
        logging.error(f"Erro ao atualizar pontuação: {e}")


async def enviar_mensagem_vitoria_dm(ganhadores_ids, vencedor, perdedor, pontos_premio):
    """Envia mensagem embed de vitória para todos os ganhadores via DM"""
    
    # Verificar se foi uma vitória de azarão (força < 85)
    # verdadeiro quando o vencedor tinha força menor que o perdedor (azarão)
    foi_azarao = vencedor["forca"] < perdedor["forca"]
    
    # Se foi azarão, verificar conquista para cada ganhador
    if foi_azarao:
        guild = bot.get_guild(1380564679084081175)  # ID do servidor
        if guild:
            logging.info(f"🎯 Processando conquista de azarão para {len(ganhadores_ids)} ganhadores")
            for uid in ganhadores_ids:
                member = guild.get_member(uid)
                if member:
                    try:
                        logging.info(f"🐗 Processando azarão para {member.name} (ID: {uid})")
                        await processar_conquistas(
                            member=member,
                            mensagens_semana=0,
                            maior_streak=0,
                            fez_doacao=False,
                            tem_vip=False,
                            tempo_em_call=0,
                            mencionou_miisha=False,
                            tocou_musica=False,
                            mencoes_bot=0,
                            azarao_vitoria=True 
                        )
                        logging.info(f"✅ Conquista de azarão processada com sucesso para {member.name}")
                    except Exception as e:
                        logging.error(f"❌ Erro ao processar conquista azarão para {uid}: {e}")
                else:
                    logging.warning(f"⚠️ Membro {uid} não encontrado no servidor")
        else:
            logging.error("❌ Guild não encontrada")
    
    # Criar embed bonito
    embed = discord.Embed(
        title="<a:105382toro:1454984271897825405> VITÓRIA NA BATALHA DE ANIME!" if not foi_azarao else "🐗 VITÓRIA DE AZARÃO!",
        description=(
            f"🏆 **{vencedor['nome']}** venceu a batalha épica!\n\n"
            f"💰 **Sua recompensa:** **+{pontos_premio} pontos**\n"
            f"⚔️ **Força do campeão:** `{vencedor['forca']}/100`\n\n"
            f"{'🎯 **Aposta de azarão bem-sucedida!**' if foi_azarao else '🎊 **Aposta certeira no favorito!**'}\n\n"
            f"✨ **Parabéns pela sua intuição guerreira! Veja !meuspontos para ver seus pontos!**"
        ),
        color=discord.Color.gold() if not foi_azarao else discord.Color.purple(),
        timestamp=datetime.now(FUSO_HORARIO)
    )
    
    # Adicionar thumbnail com GIF do vencedor
    GIFS_VITORIA = {
        "Rengoku Kyojuro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Rengoku.gif",
        "Goku":"https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dragon-ball-z-goku.gif",
        "Cell": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/cell-dragon-ball.gif",
        "Chi-Chi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Chi%20Chi.gif",
        "Broly": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Broly%20Super.gif",
        "Griffith": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/grifith-berserk.gif",
        "Guts": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/guts-berserk-berserk.gif",
        "Itachi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/lol-itachi.gif",
        "Naruto": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/naruto.gif",
        "Ichigo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ichigo.gif",
        "Sukuna": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/sukuna-smile-grin-jjk-yuji-itadori.gif",
        "Saitama": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/saitama-onepunchman.gif",
        "Garou": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Garou.gif",
        "Genos": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Genos.gif",
        "Muzan Kibutsuji": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Muzan.gif",
        "Yuno": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Yuno.gif",
        "Yami Sukehiro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Yami.gif",
        "Eren": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/eren-fortnite-eren-fortnite-dance.gif",
        "Vegeta": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dragon-ball-z-majin-vegeta.gif",
        "Luffy": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/luffy-wano.gif",
        "Shanks": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Shanks.gif",
        "Zoro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/zoro.gif",
        "Tanjiro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/tanjiro-tanjiro-kamado.gif",
        "Nezuko": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/nezuko-demon-slayer.gif",
        "Gojo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/anime-jujutsu-kaisen.gif",
        "Toji": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Toji.gif",
        "Asta": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/asta-swordofthewizardking.gif",
        "Killua": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/killua-gon.gif",
        "Gon": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/gon.gif",
        "Meliodas": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/meliodas-seven-deadly-sins.gif",
        "Ban": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Ban.gif",
        "Escanor": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/escanor.gif",
        "Light Yagami": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/death-note-kira.gif",
        "L": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/death-note-animeL.gif",
        "Madara": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/madara.gif",
        "Pain": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/pain.gif",
        "Levi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ackerman-levi-rage.gif",
        "Mikasa": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/aot-mikasa.gif",
        "Aizen": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ali-aizen.gif",
        "Bakugo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/bakugou.gif",
        "Deku": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/deku-midoriya.gif",
        "All Might": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/all-might-one-for-all.gif",
        "Mob": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/mob-psycho100-mob-psycho.gif",
        "Edward Elric": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/edward-elric-fma.gif",
        "Roy Mustang": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Roy%20Mustang.gif",
        "Zaraki Kenpachi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/bleach-zaraki-kenpachi.gif",
        "Dante": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dante-devil-may-cry.gif",
        "Vergil": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/vergil-devil-may-cry.gif",
        "Lady": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/lady-devil-may-cry%20(1).gif",
        "Dio Brando": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Dio.gif",
        "Jotaro Kujo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/yaroo-jotaro.gif",
        "Joseph Joestar": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/joseph-joestar-memed.gif",
        "Alucard": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/hellsing-hellsing-ultimate.gif",
        "Integra Hellsing": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/integra-hellsing.gif",
        "Seras Victoria": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Seras%20Victoria.gif",
        "Adam": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Adam.gif",
        "Zeus": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Zeus.gif",
        "Qin Shi Huang": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Qin%20Shin.gif",
        "Jack the Ripper": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/jack-the-ripper-valkyrie-apocalypse.gif",
        "Akame": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Akame.gif",
        "Esdeath": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Esdeath.gif",
        "Leone": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Leone.gif",
        "Tatsumi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Tatsumi.gif"
    }


    
    gif_vitoria = GIFS_VITORIA.get(vencedor['nome'])
    if gif_vitoria:
        embed.set_thumbnail(url=gif_vitoria)
    
    # Adicionar footer
    embed.set_footer(
        text=f"🎮 Batalha do Finde | {len(ganhadores_ids)} apostadores vencedores"
    )
    
    # Enviar para cada ganhador
    for uid in ganhadores_ids:
        user = bot.get_user(uid)
        if user:
            try:
                await user.send(embed=embed)
            except Exception:
                logging.warning(f"Não foi possível enviar DM para o usuário {uid}")

async def enviar_mensagem_derrota_dm(perdedores_ids, perdedor, vencedor, pontos_premio):
    """Envia mensagem embed de derrota para todos os perdedores via DM e aplica perda de pontos
    aceita `pontos_premio` por compatibilidade com a chamada que fornece o prêmio dos vencedores.
    """
    
    # Verificar se foi uma derrota de azarão (comparar força relativa)
    foi_azarao = perdedor["forca"] < vencedor["forca"]
    
    # Calcular perda de pontos (baseado na diferença de força)
    base_perda = 15
    pontos_perdidos = int(base_perda * (vencedor["forca"] / perdedor["forca"]))
    pontos_perdidos = max(10, min(pontos_perdidos, 50))  # Entre 10 e 50 pontos
    
    # Aplicar perda de pontos para cada perdedor
    for uid in perdedores_ids:
        try:
            adicionar_pontos_db(uid, -pontos_perdidos)
        except Exception as e:
            logging.error(f"Falha ao remover pontos para {uid}: {e}")
    
    # Criar embed de derrota
    embed = discord.Embed(
        title="💔 DERROTA NA BATALHA DE ANIME!" if not foi_azarao else "😢 AZARÃO NÃO CONSEGUIU!",
        description=(
            f"⚔️ **{perdedor['nome']}** foi derrotado na batalha épica!\n\n"
            f"<:43513absolutelydrained:1454984081438674954> **Seu personagem:** **{perdedor['nome']}**\n"
            f"🏆 **Vencedor:** **{vencedor['nome']}**\n"
            f"⚔️ **Força do seu lutador:** `{perdedor['forca']}/100`\n"
            f"⚔️ **Força do campeão:** `{vencedor['forca']}/100`\n\n"
            f"💸 **Perda de pontos:** **-{pontos_perdidos} pontos**\n\n"
            f"{'💔 **Seu azarão lutou bem, mas não foi suficiente!**' if foi_azarao else '😢 **Seu favorito não conseguiu desta vez!**'}\n\n"
            f"🎯 **Não desista! Na próxima batalha a vitória pode ser sua!**"
        ),
        color=discord.Color.red() if not foi_azarao else discord.Color.dark_grey(),
        timestamp=datetime.now(FUSO_HORARIO)
    )
    
    # Adicionar footer
    embed.set_footer(
        text=f"🎮 Batalha do Finde | {len(perdedores_ids)} apostadores derrotados"
    )
    
    # Enviar para cada perdedor
    for uid in perdedores_ids:
        user = bot.get_user(uid)
        if user:
            try:
                await user.send(embed=embed)
            except Exception:
                logging.warning(f"Não foi possível enviar DM para o usuário {uid}")

async def resetar_streak_perdedores(todos_ids, ganhadores_ids):
    perdedores = set(todos_ids) - set(ganhadores_ids)

    def query():
        conn = conectar_futebol()
        cursor = conn.cursor()

        for uid in perdedores:
            cursor.execute("""
                UPDATE apostas
                SET acertos_consecutivos = 0
                WHERE user_id = %s
            """, (uid,))

        conn.commit()
        cursor.close()
        conn.close()

    await asyncio.to_thread(query)

async def anunciar_resultado(canal, vencedor, perdedor, ganhadores_ids, chance_percent, pontos_premio):
    """Anuncia o resultado da batalha com embed, tratando erros via logging."""
    
    try:
        # --- Dicionário de GIFs de Vitória ---
        GIFS_VITORIA = {
            "Goku":"https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dragon-ball-z-goku.gif",
            "Cell": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/cell-dragon-ball.gif",
            "Chi-Chi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Chi%20Chi.gif",
            "Broly": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Broly%20Super.gif",
            "Vegeta": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dragon-ball-z-majin-vegeta.gif",
            "Guts": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/guts-berserk-berserk.gif",
            "Griffith": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/grifith-berserk.gif",
            "Itachi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/lol-itachi.gif",
            "Naruto": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/naruto.gif",
            "Ichigo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ichigo.gif",
            "Sukuna": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/sukuna-smile-grin-jjk-yuji-itadori.gif",
            "Saitama": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/saitama-onepunchman.gif",
            "Garou": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Garou.gif",
            "Genos": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Genos.gif",
            "Eren": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/eren-fortnite-eren-fortnite-dance.gif",
            "Vegeta": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dragon-ball-z-majin-vegeta.gif",
            "Chi-Chi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Chi%20Chi.gif",
            "Luffy": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/luffy-wano.gif",
            "Edward Elric": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/edward-elric-fma.gif",
            "Roy Mustang": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Roy%20Mustang.gif",
            "Zaraki Kenpachi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/bleach-zaraki-kenpachi.gif",
            "Dante": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/dante-devil-may-cry.gif",
            "Vergil": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/vergil-devil-may-cry.gif",
            "Lady": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/lady-devil-may-cry%20(1).gif",
            "Zoro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/zoro.gif",
            "Tanjiro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/tanjiro-tanjiro-kamado.gif",
            "Rengoku Kyojuro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Rengoku.gif",
            "Nezuko": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/nezuko-demon-slayer.gif",
            "Gojo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/anime-jujutsu-kaisen.gif",
            "Asta": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/asta-swordofthewizardking.gif",
            "Killua": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/killua-gon.gif",
            "Gon": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/gon.gif",
            "Meliodas": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/meliodas-seven-deadly-sins.gif",
            "Ban": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Ban.gif",
            "Escanor": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/escanor.gif",
            "Light Yagami": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/death-note-kira.gif",
            "L": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/death-note-animeL.gif",
            "Madara": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/madara.gif",
            "Pain": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/pain.gif",
            "Levi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ackerman-levi-rage.gif",
            "Mikasa": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/aot-mikasa.gif",
            "Aizen": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/ali-aizen.gif",
            "Bakugo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/bakugou.gif",
            "Deku": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/deku-midoriya.gif",
            "All Might": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/all-might-one-for-all.gif",
            "Mob": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/mob-psycho100-mob-psycho.gif",
            "Dio Brando": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Dio.gif",
            "Jotaro Kujo": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/yaroo-jotaro.gif",
            "Shanks": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Shanks.gif",
            "Toji": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Toji.gif",
            "Joseph Joestar": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/joseph-joestar-memed.gif",
            "Alucard": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/hellsing-hellsing-ultimate.gif",
            "Integra Hellsing": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/integra-hellsing.gif",
            "Seras Victoria": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Seras%20Victoria.gif",
            "Adam": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Adam.gif",
            "Zeus": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Zeus.gif",
            "Qin Shi Huang": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Qin%20Shin.gif",
            "Jack the Ripper": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/jack-the-ripper-valkyrie-apocalypse.gif",
            "Akame": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Akame.gif",
            "Esdeath": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Esdeath.gif",
            "Leone": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Leone.gif",
            "Tatsumi": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Tatsumi.gif",
            "Muzan Kibutsuji": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Muzan.gif",
            "Yuno": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Yuno.gif",
            "Yami Sukehiro": "https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/GifsVitoria/Yami.gif",
        }

        # Determina se foi azarão e se houve massacre
        foi_azarao = perdedor["forca"] > vencedor["forca"]        # Azarão venceu
        diferenca_forca = abs(vencedor["forca"] - perdedor["forca"])
        massacre = diferenca_forca >= 20 and not foi_azarao       # Diferença grande, não azarão

        # Escolhe título e cor
        if foi_azarao:
            titulo = "🐗 VITÓRIA DE AZARÃO!"
            cor = discord.Color.purple()
        elif massacre:
            titulo = "☠️🩸🔪 MASSACRE!"
            cor = discord.Color.red()
        else:
            titulo = "🤯🔥 SUPEROU AS EXPECTATIVAS!"
            cor = discord.Color.gold()

        # Pega GIF do vencedor
        gif_vitoria = GIFS_VITORIA.get(vencedor['nome'], None)

        # Cria embed
        embed = discord.Embed(
            title=titulo,
            description=(
                f"{vencedor['emoji']} **{vencedor['nome']}** venceu {perdedor['emoji']} **{perdedor['nome']}**!\n\n"
                f"💰 **Prêmio por Voto:** {pontos_premio} pontos\n"
                f"👥 **Ganhadores:** {len(ganhadores_ids)}\n"
                f"📉 **Probabilidade inicial:** {chance_percent}%\n\n"
            ),
            color=cor,
            timestamp=datetime.now(FUSO_HORARIO)
        )

        # Adiciona GIF
        if gif_vitoria:
            embed.set_image(url=gif_vitoria)

        # Campos detalhados
        embed.add_field(name="Vencedor", value=vencedor['nome'], inline=True)
        embed.add_field(name="Força", value=f"{vencedor['forca']}/100", inline=True)
        embed.add_field(name="Chance de Vitória", value=f"{chance_percent}%", inline=True)
        embed.add_field(name="Diferença de Força", value=f"{diferenca_forca}", inline=True)

        # Footer
        embed.set_footer(text=f"{len(ganhadores_ids)} apostadores vencedores")

        
        await canal.send(content=f"{CARGO_ANIME} **Batalha Encerrada!**", embed=embed)
        logging.info(f"🎎 Resultado da batalha enviado: {vencedor['nome']} venceu {perdedor['nome']}")

    except Exception as e:
        logging.error(f"Erro ao anunciar resultado da batalha: {e}")
        try:
            await canal.send("❌ Ocorreu um erro ao processar o resultado da batalha.")
        except Exception as inner:
            logging.error(f"Falha ao enviar mensagem de erro no canal: {inner}")

filas = {}  



#COMANDO TICKET
CARGO_AVISADO = 1445063169973424239
ID_CANAL_TICKET = 1386766363749781504
TICKET_EMBED_MESSAGE_ID = None
MENCION_RESET_DIAS = 7

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket_mensagem(ctx):
    logging.info("Comando ticket_mensagem executado por %s", ctx.author)

    if ctx.channel.id != ID_CANAL_TICKET:
        return await ctx.send("❌ Use este comando no canal de tickets.")

    conn = conectar_vips()
    cursor = conn.cursor()

    # Cria tabela (compatível com estrutura existente)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_mensagem (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id BIGINT NOT NULL UNIQUE,
            autor_mensagem_id BIGINT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Limpa registros antigos (só pode existir 1)
    cursor.execute("DELETE FROM ticket_mensagem")
    conn.commit()

    embed = discord.Embed(
        title="<:767939ticket:1451964270903431320> Abra seu Ticket",
        description=(
            "Use o comando **!ticket** neste canal e siga as instruções na DM.\n\n"
            "Opções disponíveis:\n"
            "<:99034one:1450651488589189261> Ajuda do servidor\n"
            "<:32475two:1450651490879410237> Recuperar cargo perdido\n"
            "<:17611three:1450651492250816542> Denúncia"
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(text="💡 Dica: habilite mensagens no privado para que o bot consiga te enviar DMs.")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1380564680552091789/1445202774756298752/JINXED_7.png")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1380564680552091789/1444749579605119148/discotools-xyz-icon.png")

    try:
        msg = await ctx.send(embed=embed)

        cursor.execute(
            """
            INSERT INTO ticket_mensagem (message_id, autor_mensagem_id)
            VALUES (%s, %s)
            """,
            (msg.id, ctx.author.id)
        )
        conn.commit()

        global TICKET_EMBED_MESSAGE_ID
        TICKET_EMBED_MESSAGE_ID = msg.id

        await ctx.message.delete()

    except Exception as e:
        logging.error(f"Falha ao enviar ticket_mensagem: {e}")
        await ctx.send("❌ Não foi possível enviar a mensagem de ticket.")

    finally:
        cursor.close()
        conn.close()


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
            "<:44273helpids:1451964392202567731>| <:62797minecraftblue1:1451965466833846292> Ajuda do servidor\n"
            "<:85946supportids:1451964721006641265> | <:43507minecraftblue2:1451965468889059478> Recuperar cargo perdido\n"
            "<:18181report:1451965090851979457>| <:74240minecraftblue3:1451965470390358046> Denúncia"
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
            admins = [428006047630884864, 614476239683584004, 1136342425820987474]
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
                "⚠️ Você recebeu uma denúncia por abuso de moderação. "
                "Seu comportamento será monitorado pela equipe de administração. "
                "Caso receba mais denúncias, poderá ter seus cargos de moderação removidos."
            )
        except:
            pass
        sql = """
            INSERT INTO avisados (user_id, nome, denunciante_id) 
            VALUES (%s, %s, %s) 
            ON DUPLICATE KEY UPDATE 
                denunciante_id=VALUES(denunciante_id),
                nome=VALUES(nome)
        """
        c.execute(sql, (membro.id, str(membro), user.id))
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
        if qtd >= 5:
            if membro.id == ctx.guild.owner_id:
                logging.warning("Tentativa de punição no dono do servidor ignorada.")
                return
            try:
                cargos_mod = ["Dono", "Moderador"]
                cargos_para_remover = [
                    role for role in membro.roles 
                    if role.name in cargos_mod
                ]
                if cargos_para_remover:
                    await membro.remove_roles(
                        *cargos_para_remover,
                        reason="5 denúncias distintas por abuso de moderação"
                    )
                    logging.warning(
                        "Cargos %s removidos de %s (ID: %s) após %s denúncias",
                        cargos_mod, membro, membro.id, qtd
                    )
                    alertar = [428006047630884864, 614476239683584004]
                    for admin_id in alertar:
                        admin = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
                        if admin:
                            await admin.send(
                            "🚨 **Ação automática aplicada**\n\n"
                            f"O moderador <@{membro.id}> recebeu **5 denúncias distintas**.\n"
                            "❌ Seus cargos de moderação/administração foram **removidos automaticamente**.\n\n"
                            "🔎 Verifique o caso no painel / banco de dados."
                        )
            except discord.Forbidden:
                logging.error(
                    "Não foi possível remover cargos de %s (ID: %s) - permissões insuficientes",
                    membro, membro.id
                )
            except Exception as e:
                logging.error(
                    "Erro ao remover cargos de %s (ID: %s): %s",
                    membro, membro.id, str(e)
                )

            alertar = [428006047630884864, 614476239683584004]
            for admin_id in alertar:
                admin = bot.get_user(admin_id)
                if admin:
                    await admin.send(
                        "⚠️ Alerta de possível abuso de moderação\n\n"
                        f"O moderador <@{id_moderador}> recebeu denúncias de 5 usuários diferentes.\n"
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


#-------------------cargo jogo------------

Envio_mensagem = 1380564680552091789
ROLE_MINECRAFT = 1422954037174603796
ROLE_BRAWHALLA = 1425160627487375533
ROLE_ROBLOX    = 1422954452846907446
ROLE_VALORANT  = 1422954672754397316
ROLE_LOL       = 1422978913373651094

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Minecraft", style=discord.ButtonStyle.green, custom_id="minecraft")
    async def minecraft_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_MINECRAFT)   
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Minecraft**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Roblox", style=discord.ButtonStyle.red, custom_id="roblox")
    async def roblox_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_ROBLOX)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Roblox**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Valorant", style=discord.ButtonStyle.blurple, custom_id="valorant")
    async def valorant_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_VALORANT)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **Valorant**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="LoL", style=discord.ButtonStyle.gray, custom_id="lol")
    async def lol_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = guild.get_role(ROLE_LOL)
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Você recebeu o cargo **LoL**!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Você já tem esse cargo!", ephemeral=True)

    @discord.ui.button(label="Brawlhalla", style=discord.ButtonStyle.green, custom_id="brawlhalla")
    async def brawlhalla_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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


ROLE_IDS_TIMES = {
    "fluminense": 1442482502311739442,
    "vasco": 1442482275546697860,
    "gremio": 1442482642942689323,
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
    "vitoria": 1444483144270086267,
    "atletico paranaense": 1471640222713253949,
    "bragantino": 1471640464208957632,
    "mirassol": 1471640764311277670,
    "coritiba": 1471640974902956196,
    "remo": 1471641271570530335,
    "fortaleza": 1442482777894293624
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

async def tem_jogo_hoje():  
    conexao = conectar_futebol()
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT data_jogo
        FROM jogos_pendentes
        WHERE data_jogo >= CURDATE()
        ORDER BY data_jogo ASC
        LIMIT 1
    """)
    
    resultado = cursor.fetchone()
    cursor.close()
    conexao.close()
    
    return resultado[0] if resultado else None


@tasks.loop(minutes=1)
async def verificar_inicio_jogos():
    proximo_jogo = await tem_jogo_hoje()
    if not proximo_jogo:
        return
    
    agora = datetime.now(tz_br)
    
    
    if isinstance(proximo_jogo, str):
        proximo_jogo = datetime.fromisoformat(proximo_jogo.replace('Z', '+00:00'))
        proximo_jogo = proximo_jogo.astimezone(tz_br)
    
    # Se já estiver acompanhando, não faz nada
    if acompanhando:
        return
    
    # "Essa data já aconteceu? Não? Então vou retornar"
    if agora < proximo_jogo:
        return
    
    
    if agora >= proximo_jogo:
        global acompanhando, placares
        
        acompanhando = True  
        placares.clear()

        if not verificar_gols.is_running() and not verificar_jogos_automaticamente.is_running():
            verificar_gols.start()
            verificar_jogos_automaticamente.start()
        
        logging.info(f"🟢 Monitoramento iniciado automaticamente! Jogo: {proximo_jogo}")


async def tem_jogo_final():
    conexao = conectar_futebol()
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT data_jogo
        FROM jogos_pendentes
        WHERE data_jogo >= CURDATE()
        ORDER BY data_jogo DESC
        LIMIT 1
    """)
    
    resultado = cursor.fetchone()
    cursor.close()
    conexao.close()
    
    return resultado[0] if resultado else None


@tasks.loop(minutes=5)
async def verificar_parada_automatica():
    if not acompanhando:
        return  
    
    ultimo_jogo = await tem_jogo_final()
    if not ultimo_jogo:
        return  
    
    agora = datetime.now(tz_br)
    
    
    if isinstance(ultimo_jogo, str):
        ultimo_jogo = datetime.fromisoformat(ultimo_jogo.replace('Z', '+00:00'))
        ultimo_jogo = ultimo_jogo.astimezone(tz_br)
    
   
    limite_parada = ultimo_jogo + timedelta(hours=3)
    
    
    if agora < limite_parada:
        return
    
   
    if agora >= limite_parada:
        global acompanhando
        acompanhando = False
        
        logging.info(f"🔴 Monitoramento parado automaticamente! Último jogo: {ultimo_jogo} | Limite: {limite_parada}")
        
        # Para os loops se estiverem rodando
        if verificar_gols.is_running():
            verificar_gols.stop()
        if verificar_jogos_automaticamente.is_running():
            verificar_jogos_automaticamente.stop()



@commands.has_permissions(administrator=True)
@bot.command()
async def apistart(ctx, horario: str = None, data: str = None):

    if ctx.author.id != ADM_BRABO:
        return await ctx.send("Só amorreba the gostoso pode usar este comando! <:Galo:1425991683690074212>")

    global acompanhando, placares

    agora = datetime.now(tz_br)

    # ----------------------------------------
    # MODO MANUAL (sem nada)
    # ----------------------------------------
    if horario is None:
        acompanhando = True
        placares.clear()

        if not verificar_gols.is_running():
            verificar_gols.start()

        if not verificar_jogos_automaticamente.is_running():
            verificar_jogos_automaticamente.start()

        return await ctx.send("🔵 Monitoramento iniciado manualmente!")

    # ----------------------------------------
    # VALIDA HORÁRIO
    # ----------------------------------------
    try:
        if ":" in horario:
            h, m = horario.split(":")
            hour = int(h)
            minute = int(m)
        else:
            hour = int(horario)
            minute = 0
    except:
        return await ctx.send("⚠️ Use HH ou HH:MM.")

    
    if data:
        try:
            dia, mes = data.split("/")
            dia = int(dia)
            mes = int(mes)

            horario_agendado = datetime(
                year=agora.year,
                month=mes,
                day=dia,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
                tzinfo=tz_br
            )

        except:
            return await ctx.send("⚠️ Use a data no formato DD/MM.")
    else:
        # se não tiver data → comportamento antigo
        horario_agendado = agora.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if horario_agendado <= agora:
            horario_agendado += timedelta(days=1)

    # ----------------------------------------
    # SE JÁ PASSOU
    # ----------------------------------------
    if horario_agendado <= agora:
        return await ctx.send("⚠️ Essa data/horário já passou.")

    await ctx.send(
        f"🟡 Monitoramento agendado para {horario_agendado.strftime('%d/%m às %H:%M')}"
    )

    async def iniciar_no_horario():
        await discord.utils.sleep_until(horario_agendado)

        global acompanhando, placares
        acompanhando = True
        placares.clear()

        if not verificar_gols.is_running():
            verificar_gols.start()

        if not verificar_jogos_automaticamente.is_running():
            verificar_jogos_automaticamente.start()

        await ctx.send(
            f"🟢 Monitoramento iniciado automaticamente!"
        )

    bot.loop.create_task(iniciar_no_horario())


          
@commands.has_permissions(administrator=True)
@bot.command()
async def apistop(ctx, horario: str = None, data: str = None):
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

    agora = datetime.now(tz_br)

    # -----------------------------------------------------
    # VALIDA HORÁRIO
    # -----------------------------------------------------
    try:
        if ":" in horario:
            h, m = horario.split(":")
            hour = int(h)
            minute = int(m)
        else:
            hour = int(horario)
            minute = 0

        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")
    except:
        return await ctx.send("⚠️ Formato inválido. Use HH ou HH:MM.")

    # -----------------------------------------------------
    # VALIDA DATA (se existir)
    # -----------------------------------------------------
    if data:
        try:
            dia, mes = data.split("/")
            dia = int(dia)
            mes = int(mes)

            horario_agendado = datetime(
                year=agora.year,
                month=mes,
                day=dia,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
                tzinfo=tz_br
            )
        except:
            return await ctx.send("⚠️ Use a data no formato DD/MM.")
    else:
        horario_agendado = agora.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if horario_agendado <= agora:
            horario_agendado += timedelta(days=1)

    # -----------------------------------------------------
    # SE JÁ PASSOU
    # -----------------------------------------------------
    if horario_agendado <= agora:
        return await ctx.send("⚠️ Essa data/horário já passou.")

    await ctx.send(
        f"🟡 **Monitoramento será pausado em {horario_agendado.strftime('%d/%m às %H:%M')} (horário de Brasília).**"
    )

    logging.info(f"Pausa AGENDADA para {horario_agendado.strftime('%d/%m %H:%M:%S')}")

    async def parar_no_horario():
        await discord.utils.sleep_until(horario_agendado)

        global acompanhando
        acompanhando = False

        logging.info("Monitoramento pausado AUTOMATICAMENTE no horário agendado.")

        await ctx.send("🔴 **Monitoramento pausado automaticamente. Nenhum request será feito.**")

    bot.loop.create_task(parar_no_horario())


@bot.command()
async def meuspontos(ctx):
    async with ctx.typing():
        pontos = pegar_pontos(ctx.author.id)
        await ctx.send(f"<a:565724creditcard:1467671052053254235> {ctx.author.mention}, você tem **{pontos} pontos**!")
        logging.info(f"Usuário {ctx.author.name} ({ctx.author.id}) solicitou os pontos.")
        



@bot.command()
async def fogo(ctx):
    try:
        acertos_atuais, maior_streak = buscar_fogo_usuario(ctx.author.id)
        
        embed = gerar_embed_fogo(
            acertos_atuais,
            maior_streak,
            ctx.author.display_name
        )
        await ctx.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro ao buscar fogo: {e}")
        await ctx.send("⚠️ Erro ao buscar fogo. Tente novamente mais tarde.")

class PaginaFogos(discord.ui.View):
    def __init__(self, ranking, autor):
        super().__init__(timeout=120)
        self.ranking = ranking        # lista de dicts do MySQL
        self.pagina = 0
        self.por_pagina = 5
        self.autor = autor
        self.atualizar_estado_botoes()

    def atualizar_estado_botoes(self):
        # Se os botões ainda não existirem, ignora
        if hasattr(self, 'btn_anterior'):
            self.btn_anterior.disabled = self.pagina == 0
        if hasattr(self, 'btn_proximo'):
            self.btn_proximo.disabled = (self.pagina + 1) * self.por_pagina >= len(self.ranking)

    async def atualizar_embed(self, destino):
        """
        Atualiza o embed e envia para o destino:
        - Se destino for Interaction: usa response/edit_message
        - Se destino for Context: usa ctx.send
        """
        inicio = self.pagina * self.por_pagina
        fim = inicio + self.por_pagina
        ranking_pagina = self.ranking[inicio:fim]

        logging.info(f"🔥 Atualizando página de fogos: página {self.pagina+1}, mostrando {len(ranking_pagina)} usuários")

        embed = discord.Embed(
            title="🔥 Top Maiores Fogos",
            color=discord.Color.orange()
        )

        medalhas = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        for i, row in enumerate(ranking_pagina):
            user_id = row["user_id"]
            fogo = row["maior_streak"]
            posicao = inicio + i + 1
            medalha = medalhas[posicao-1] if posicao <= len(medalhas) else "🏅"
            membro = None
            # Pega o membro dependendo do tipo do destino
            if isinstance(destino, discord.Interaction):
                membro = destino.guild.get_member(user_id)
            elif isinstance(destino, discord.ext.commands.Context):
                membro = destino.guild.get_member(user_id)

            nome = membro.display_name if membro else f"Usuário ({user_id})"
            logging.info(f"🔥 Fogo #{posicao}: {nome} - {fogo} (maior streak)")
            embed.add_field(
                name=f"{posicao}º {medalha} {nome}",
                value=f"🔥 **Streak:** {fogo}",
                inline=False
            )

        embed.set_footer(text=f"Solicitado por {self.autor.display_name}")

        # Envia o embed dependendo do tipo de destino
        if isinstance(destino, discord.Interaction):
            try:
                await destino.response.edit_message(embed=embed, view=self)
            except discord.errors.InteractionResponded:
                if destino.message:
                    await destino.followup.edit_message(message_id=destino.message.id, embed=embed, view=self)
                else:
                    await destino.followup.send(embed=embed, view=self)
        elif isinstance(destino, discord.ext.commands.Context):
            await destino.send(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.primary)
    async def btn_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina -= 1
        self.atualizar_estado_botoes()
        await self.atualizar_embed(interaction)

    @discord.ui.button(label="➡️ Próximo", style=discord.ButtonStyle.primary)
    async def btn_proximo(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina += 1
        self.atualizar_estado_botoes()
        await self.atualizar_embed(interaction)


# ================= COMANDO =================
@bot.command()
async def top_fogos(ctx):
    conn = conectar_futebol()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT user_id, MAX(maior_streak) as maior_streak FROM apostas "
            "WHERE maior_streak > 0 GROUP BY user_id ORDER BY maior_streak DESC"
        )
        resultados = cursor.fetchall()
        if not resultados:
            return await ctx.send("🔥 Ninguém está com fogo no momento!")

        view = PaginaFogos(resultados, ctx.author)
        await view.atualizar_embed(ctx)

    finally:
        cursor.close()
        conn.close()


CANAL_APOSTAS_ID = 1442495893365330138 
# ---------- CONFIG ----------

URL = "https://v3.football.api-sports.io/fixtures"
HEADERS = {"x-apisports-key": API_TOKEN}
CANAL_JOGOS_ID = 1380564680552091789

EMOJI_EMPATE = "🤝"  # emoji de mãos apertando para empate


# ---------- DB helper (usa sua função conectar_futebol) ----------
def garantir_tabelas():
    con = conectar_futebol()
    cur = con.cursor()

    # ----------------------------
    # Tabela jogos
    # ----------------------------
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
    
    # Verificar e adicionar coluna message_id se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'message_id'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN message_id BIGINT")
        logging.info("Coluna 'message_id' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna bet_deadline se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'bet_deadline'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN bet_deadline DATETIME")
        logging.info("Coluna 'bet_deadline' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna betting_open se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'betting_open'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN betting_open TINYINT DEFAULT 0")
        logging.info("Coluna 'betting_open' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna finalizado se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'finalizado'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN finalizado TINYINT DEFAULT 0")
        logging.info("Coluna 'finalizado' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna processado se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'processado'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN processado TINYINT DEFAULT 0")
        logging.info("Coluna 'processado' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna canal_id se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'canal_id'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN canal_id BIGINT")
        logging.info("Coluna 'canal_id' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna data se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'data'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN data DATE")
        logging.info("Coluna 'data' adicionada à tabela jogos")
    
    # Verificar e adicionar coluna horario se não existir
    cur.execute("SHOW COLUMNS FROM jogos LIKE 'horario'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE jogos ADD COLUMN horario TIME")
        logging.info("Coluna 'horario' adicionada à tabela jogos")
    
    # Garantias extras (caso tabela já exista)
    try:
        cur.execute("ALTER TABLE jogos ADD COLUMN processado TINYINT DEFAULT 0")
    except Exception:
        pass

    # ----------------------------
    # Tabela apostas
    # ----------------------------
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

    # Verificar e adicionar coluna modo_clown se não existir
    cur.execute("SHOW COLUMNS FROM apostas LIKE 'modo_clown'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE apostas ADD COLUMN modo_clown TINYINT(1) DEFAULT 0")
        logging.info("Coluna 'modo_clown' adicionada à tabela apostas")

    # Garantias extras (caso tabela já exista)
    try:
        cur.execute("ALTER TABLE jogos ADD COLUMN processado TINYINT DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE apostas ADD UNIQUE KEY uniq_aposta (user_id, fixture_id)")
    except Exception:
        pass

    # ----------------------------
    # Tabela pontuacoes
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pontuacoes (
            user_id BIGINT PRIMARY KEY,
            nome_discord VARCHAR(50) NOT NULL,
            pontos INT NOT NULL DEFAULT 0
        )
    """)

    try:
        cur.execute("ALTER TABLE pontuacoes ADD COLUMN nome_discord VARCHAR(50) NOT NULL")
    except Exception:
        pass

    # ----------------------------
    # Tabela posts (sistema de upvotes/downvotes)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id BIGINT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            upvotes INT DEFAULT 0,
            downvotes INT DEFAULT 0,
            removed BOOLEAN DEFAULT FALSE,
            motivo_remocao TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_channel_id (channel_id),
            INDEX idx_timestamp (timestamp),
            INDEX idx_removed (removed)
        )
    """)

    # ----------------------------
    # Tabela posts_premiados 
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts_premiados (
            id INT AUTO_INCREMENT PRIMARY KEY,
            post_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            upvotes INT NOT NULL,
            pontos_ganhos INT NOT NULL,
            premiado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            premiado_dia DATE NOT NULL,
            UNIQUE KEY uniq_post_dia (post_id, premiado_dia)
        )
    """)

    # ----------------------------
    # Tabela inversoes (sistema inverter pontos)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inversoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            target_user_id BIGINT NOT NULL,
            creator_user_id BIGINT NOT NULL,
            fixture_id BIGINT NULL,
            used TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_target_user (target_user_id),
            INDEX idx_used (used)
        )
    """)

    # ----------------------------
    # Tabela comemoracoes (sistema de comemoração de gols)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comemoracoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            team_key VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_team (user_id, team_key),
            INDEX idx_team (team_key)
        )
    """)

    # ----------------------------
    # Tabela loja_pontos (sistema de compras da loja)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS loja_pontos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item VARCHAR(50) NOT NULL,
            pontos_gastos INT NOT NULL,
            data_compra DATETIME DEFAULT CURRENT_TIMESTAMP,
            ativo TINYINT(1) DEFAULT 1,
            nome_cargo VARCHAR(100),
            cargo_id BIGINT,
            emoji VARCHAR(200),
            INDEX idx_user_item (user_id, item),
            INDEX idx_ativo (ativo)
        )
    """)

    # ----------------------------
    # Tabela clown_bet (sistema modo clown)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clown_bet (
            user_id BIGINT PRIMARY KEY,
            ativo TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ----------------------------
    # Tabela loja_vip (sistema VIP)
    # ----------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS loja_vip (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            cargo_id BIGINT NOT NULL,
            data_compra DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_expira DATETIME NOT NULL,
            ativo TINYINT(1) DEFAULT 1,
            INDEX idx_user (user_id),
            INDEX idx_expira (data_expira),
            INDEX idx_ativo (ativo)
        )
    """)

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
        logging.info(f"✅ Pontos atualizados: user_id={user_id}, pontos={pontos}")
    except Exception as e:
        logging.error(f"❌ Erro ao adicionar pontos: {e}")
    finally:
        cur.close()
        con.close()

def registrar_aposta_db(user_id: int, fixture_id: int, palpite: str) -> bool:
    
 
    con = conectar_futebol()
    cur = con.cursor()

    # 1) verifica duplicata
    cur.execute("SELECT id FROM apostas WHERE user_id = %s AND fixture_id = %s", (user_id, fixture_id))
    if cur.fetchone():
        con.close()
        return False

    # 2) pega o nome do Discord
    u = bot.get_user(int(user_id))
    nome_discord = f"{u.name}#{u.discriminator}" if u else str(user_id)

    # 3) checa se usuário tem clown ativo (tabela clown_bet)
    modo_clown = 0
    try:
        cur.execute("SELECT ativo FROM clown_bet WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row and row[0] == 1:
            modo_clown = 1
            cur.execute("UPDATE clown_bet SET ativo = 0 WHERE user_id = %s", (user_id,))
    except Exception:
        modo_clown = 0

    # 4) inserir aposta com modo_clown e nome_discord
    cur.execute(
        "INSERT INTO apostas (user_id, nome_discord, fixture_id, palpite, modo_clown) VALUES (%s, %s, %s, %s, %s)",
        (user_id, nome_discord, fixture_id, palpite, modo_clown)
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

def gerar_embed_fogo(acertos_atuais: int, maior_streak: int, nome_usuario: str):
    em_fogo = acertos_atuais >= 3

    embed = discord.Embed(
        title="🔥 SEU FOGO ATUAL",
        description=(
            f"📊 **Acertos Consecutivos:** **{acertos_atuais}**\n"
            f"🏆 **Maior Sequência:** **{maior_streak}**\n\n"
            f"{'🔥 **VOCÊ ESTÁ EM FOGO!**' if em_fogo else '❄️ Continue tentando!'}"
        ),
        color=discord.Color.red() if em_fogo else discord.Color.blue()
    )

    return embed

def buscar_fogo_usuario(user_id: int):
    conn = conectar_futebol()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                (
                    SELECT acertos_consecutivos
                    FROM apostas
                    WHERE user_id = %s
                    ORDER BY data_aposta DESC
                    LIMIT 1
                ) AS acertos_consecutivos,
                MAX(maior_streak) AS maior_streak
            FROM apostas
            WHERE user_id = %s
        """, (user_id, user_id))

        resultado = cursor.fetchone()

        if not resultado or resultado["acertos_consecutivos"] is None:
            return 0, 0

        return (
            resultado["acertos_consecutivos"] or 0,
            resultado["maior_streak"] or 0
        )

    finally:
        cursor.close()
        conn.close()
# ---------- Manipulação de reações (usa on_raw_reaction_add para pegar reações em mensagens antigas)

MAPEAMENTO_TIMES = {

    # =======================
    # 🇧🇷 CLUBES BRASILEIROS
    # =======================

    # Atlético Mineiro
    "atlético mineiro": "galo",
    "atletico-mg": "galo",
    "atlético-mg": "galo",
    "galo": "galo",

    # São Paulo
    "são paulo": "sao paulo",
    "sao paulo fc": "sao paulo",
    "sao paulo": "sao paulo",

    # Flamengo
    "flamengo rj": "flamengo",
    "flamengo": "flamengo",

    # Fluminense
    "fluminense rj": "fluminense",
    "fluminense": "fluminense",

    # Corinthians
    "corinthians sp": "corinthians",
    "corinthians": "corinthians",

    # Palmeiras
    "palmeiras sp": "palmeiras",
    "palmeiras": "palmeiras",
    "palemeiras": "palmeiras",

    # Internacional
    "internacional rs": "internacional",
    "internacional": "internacional",

    # Grêmio
    "grêmio": "gremio",
    "gremio rs": "gremio",
    "gremio": "gremio",

    # Bahia
    "bahia ba": "bahia",
    "bahia": "bahia",

    # Botafogo
    "botafogo rj": "botafogo",
    "botafogo": "botafogo",

    # Cruzeiro
    "cruzeiro mg": "cruzeiro",
    "cruzeiro": "cruzeiro",

    # Vasco
    "vasco da gama": "vasco",
    "vasco": "vasco",

    # Ceará
    "ceará": "ceara",
    
    # Santos
    "santos": "santos",
    "santos-fc": "santos",
    "santos fc": "santos",

    # RB Bragantino
    "rb bragantino": "bragantino",
    "bragantino": "bragantino",
    #Chapecoense
    "associação chapecoense de futebol": "chapecoense",
    "chapecoense": "chapecoense",
    "chapecoense fc": "chapecoense",
    "chapecoense-sc": "chapecoense",
    "chapecoense sc": "chapecoense",

    # Mirassol
    "mirassol": "mirassol",
    "mirassol sp": "mirassol",

    # Juventude
    "juventude rs": "juventude",

    # Vitória
    "vitoria ba": "vitoria",
    "vitoria": "vitoria",
    "vitória": "vitoria",
    "esporte clube vitoria": "vitoria",
    "ec vitoria": "vitoria",

    # Sport
    "sport recife": "sport",

    # Fortaleza
    "fortaleza ec": "fortaleza",
    "fortaleza": "fortaleza",

    # Athletico Paranaense
    "atlético paranaense": "atletico paranaense",
    "atletico paranaense": "atletico paranaense",
    "athletico paranaense": "atletico paranaense",
    "atletico pr": "atletico paranaense",
    "athletico pr": "atletico paranaense",
    "atl pr": "atletico paranaense",

    # Coritiba
    "coritiba": "coritiba",
    "corithiba": "coritiba",
    "coritiba pr": "coritiba",
    "coritiba-pr": "coritiba",
    "cfc": "coritiba",
    "coritiba foot ball club": "coritiba",

    # Remo
    "remo": "remo",


    # =======================
    # 🌍 CLUBES INTERNACIONAIS
    # =======================

    # Lanús (Argentina)
    "lanús": "lanus",

    # UEFA — principais clubes
    "villarreal": "villarreal",
    "bayer leverkusen": "bayer leverkusen",
    "atalanta": "atalanta",
    "olympique": "olympique",
    "olympique marseille": "olympique",
    "benfica": "benfica",
    "ajax": "ajax",
    "borussia dortmund": "borussia",
    "borussia": "borussia",
    "napoli": "napoli",
    "atletico de madrid": "atletico de madrid",
    "atlético de madrid": "atletico de madrid",
    "milan": "milan",
    "ac milan": "milan",
    "juventus": "juventus",
    "psg": "psg",
    "paris saint-germain": "psg",
    "paris saint germain": "psg",
    "manchester city": "city",
    "city": "city",
    # Manchester United
    "manchester united": "manchester_united",
    "man united": "manchester_united",
    "man utd": "manchester_united",
    "man-utd": "manchester_united",
    "man united fc": "manchester_united",
    # West Ham
    "west ham": "west_ham",
    "west ham united": "west_ham",
    "westham": "west_ham",
    "west-ham": "west_ham",
    "arsenal": "arsenal",
    "chelsea": "chelsea",
    "liverpool": "liverpool",
    "bayern munich": "bayern munich",
    "fc bayern": "bayern munich",
    "barcelona": "barcelona",
    "real madrid": "real madrid",

    "brazil": "brasil",
    "brasil": "brasil",
    "argentina": "argentina",
    "france": "frança",
    "franca": "frança",
    "germany": "alemanha",
    "alemanha": "alemanha",
    "italy": "italia",
    "italia": "italia",
    "england": "inglaterra",
    "inglaterra": "inglaterra",
    "spain": "espanha",
    "espanha": "espanha",
    "portugal": "portugal",
    "netherlands": "holanda",
    "holanda": "holanda",
    "uruguay": "uruguai",
    "uruguai": "uruguai",
    "belgium": "belgica",
    "belgica": "belgica",
    "croatia": "croacia",
    "croacia": "croacia",
    "mexico": "mexico",
    "japan": "japao",
    "japao": "japao",
    "usa": "eua",
    "united states": "eua",
    "senegal": "senegal",
    "tunisia": "tunisia",
}

def get_estadio_time_casa(nome_time_api: str):
 
    if not nome_time_api:
        return {
            "time": None,
            "estadio": "Estádio indefinido",
            "imagem": ""
        }

    # normaliza o nome vindo da API
    chave = nome_time_api.strip().lower()

    # usa seu mapeamento
    time_padrao = MAPEAMENTO_TIMES.get(chave)

    # mapeamento de estádios (imagem vazia)
    ESTADIOS_CASA = {
        "galo": {
            "estadio": "Arena MRV",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Arena%20Mrv.png"
        },
        "flamengo": {
            "estadio": "Maracanã",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Maracanã.jpg"
        },
        "corinthians": {
            "estadio": "Neo Química Arena",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Neo%20Química%20Arena.png"
        },
        "palmeiras": {
            "estadio": "Allianz Parque",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Allianz%20Parque.png"
        },
        "sao paulo": {
            "estadio": "Morumbi",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Morumbi.png"
        },
        "fluminense": {
            "estadio": "Maracanã",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Maracanã.jpg"
        },
        "vasco": {
            "estadio": "São Januário",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/São%20Januário.png"
        },
        "botafogo": {
            "estadio": "Nilton Santos",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Nilton%20Santos.png"
        },
        "gremio": {
            "estadio": "Arena do Grêmio",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Arena%20do%20Grêmio.png"
        },
        "internacional": {
            "estadio": "Beira-Rio",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Beira-Rio.png"
        },
        "cruzeiro": {
            "estadio": "Mineirão",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Mineirão.png"
        },
        "bahia": {
            "estadio": "Arena Fonte Nova",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Arena%20Fonte%20Nova.jpg"
        },
        "fortaleza": {
            "estadio": "Castelão",
            "imagem": "https://cdn.discordapp.com/attachments/704107435295637605/1466222443512201276/images.jpg?ex=697bf58f&is=697aa40f&hm=f466583fe65a6ae50b1d03b63180c7dcb24ac6ec62012744c5b57f6d9e067b32&"
        },
        "vitoria": {
            "estadio": "Barradão",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Barradão.jpg"
        },
        "atletico paranaense": {
            "estadio": "Ligga Arena",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Ligga%20Arena.png"
        },
        "coritiba": {
            "estadio": "Couto Pereira",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Couto%20Pereira.jpg"
        },
        "bragantino": {
            "estadio": "Nabi Abi Chedid",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Nabi%20Abi%20Chedid.png"
        },
        "juventude": {
            "estadio": "Alfredo Jaconi",
            "imagem": ""
        },
        "ceara": {
            "estadio": "Castelão",
            "imagem": ""
        },
        "remo": {
            "estadio": "Baenão",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Baenão.jpg"
        },
        "santos": {
            "estadio": "Vila Belmiro",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Vila%20bel%20miro.jpeg"
        },
        "mirassol": {
            "estadio": "José Maria de Campos Maia",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/José%20Maria%20de%20Campos%20Maia.jpg"
        },
        "chapecoense": {
            "estadio": "Arena Condá",
            "imagem": "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Arena%20Conda.jpg"
        }
    }

    if not time_padrao or time_padrao not in ESTADIOS_CASA:
        return {
            "time": time_padrao,
            "estadio": "Estádio indefinido",
            "imagem": ""
        }

    return {
        "time": time_padrao,
        "estadio": ESTADIOS_CASA[time_padrao]["estadio"],
        "imagem": ESTADIOS_CASA[time_padrao]["imagem"]
    }



PALAVRAS_GOL = {
    "galo":        "🐓 GOOOOOOOOOOL É DO GALO DOIDO!!! 🔥",
    "flamengo":    "🦅 GOOOOOOOL DO MENGÃO",
    "palmeiras":   "🐷 GOOOOOOOOOL DO VERDÃO",
    "corinthians": "🦅 GOOOOOOOOOL DO TIMÃO!",
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
    "chapecoense": "💚⚪ GOOOOOOOL DA CHAPE!!!",
    "brasil":     "🇧🇷 GOOOOOOOL DO BRASIL!!!",
    "argentina":  "🇦🇷 GOOOOOOOL DA ARGENTINA!!!",
    "frança":     "🇫🇷 GOOOOOOOL DA FRANÇA!!!",
    "alemanha":   "🇩🇪 GOOOOOOOL DA ALEMANHA!!!",
    "italia":     "🇮🇹 GOOOOOOOL DA ITÁLIA!!!",
    "inglaterra": "🇬🇧 GOOOOOOOL DA INGLATERRA!!!",
    "espanha":    "🇪🇸 GOOOOOOOL DA ESPANHA!!!",
    "portugal":   "🇵🇹 GOOOOOOOL DE PORTUGAL!!!",
    "holanda":    "🇳🇱 GOOOOOOOL DA HOLANDA!!!",
    "uruguai":    "🇺🇾 GOOOOOOOL DO URUGUAI!!!",
    "belgica":    "🇧🇪 GOOOOOOOL DA BÉLGICA!!!",
    "croacia":    "🇭🇷 GOOOOOOOL DA CROÁCIA!!!",
    "mexico":     "🇲🇽 GOOOOOOOL DO MÉXICO!!!",
    "japao":      "🇯🇵 GOOOOOOOL DO JAPÃO!!!",
    "eua":        "🇺🇸 GOOOOOOOL DOS EUA!!!",
    "senegal":    "🇸🇳 GOOOOOOOL DO SENEGAL!!!",
    "tunisia":    "🇹🇳 GOOOOOOOL DA TUNÍSIA!!!"
}

GIFS_VITORIA_TIME = {
    # =======================
    # 🇧🇷 CLUBES BRASILEIROS 2025 - DOIS GIFs POR TIME
    # =======================
    "atletico paranaense": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Athletic%20Paranaense/atlethic%20paranaense.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Athletic%20Paranaense/atletico%20paranaense.gif"
    ],
    "bahia": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Bahia/ec-bahia-jean-lucas.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Bahia/ec-bahia-triunfo.gif"
    ],
    "botafogo": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Botafogo/botafogo-bandeira-botafogo-torcida.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Botafogo/botafogo-igor-jesus.gif"
    ],
    "corinthians": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Corinthians/corinthians-gato-futebol.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Corinthians/corinthians.gif"
    ],
    "coritiba": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Coritiba/coritiba-coxa.gif"
    ],
    "cruzeiro": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Cruzeiro/cec-cabuloso.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Cruzeiro/matheus-pereira-matheus-pereira-cruzeiro-esporte-clube.gif"
    ],
    "flamengo": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Flamengo/flamengo-dance.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Flamengo/flamengo.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Flamengo/soccer-flamengo.gif"
    ],
    "fluminense": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Fluminense/cano-fluminense.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Fluminense/nathan-fluminense.gif"
    ],
    "atlético mineiro": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Galo/atletico-mineiro-aê.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Galo/atletico-mineiro-dancinha-do-tik-tok.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Galo/atletico-paulinho.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Galo/gustavo-arana-galo.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Galo/maior-de-minas-galo.gif"
    ],
    "gremio": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Greemio/cortezinho-grêmio.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Greemio/diego-souza-gremio.gif"
    ],
    "internacional": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Internacional/internacional-inter.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Internacional/vegeta-dbzinter.gif"
    ],
    "palmeiras": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Palmeiras/comemorando-palmeiras.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Palmeiras/dancinha-comemorandopalmeiras.gif"
    ],
    "santos": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Santos/sacanagem-santos.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Santos/santos%20comemoracao.gif"
    ],
    "são paulo": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Sao%20Paulo/calleri-jonathan-saopaulo.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Sao%20Paulo/spfc-são-paulo.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Sao%20Paulo/spfc-zubeldia.gif"
    ],
    "vasco": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Vasco/trem-bala-da-colina-vasco-da-gama.gif",
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Vasco/vegetti-gol.gif"
    ],
    "vitoria": [
        "https://raw.githubusercontent.com/DaviDetroit/arenas-bot/master/Comemoracao/Vitoria/Vitoria.gif"
    ],
    
    # Times sem GIFs específicos (mantidos)
    "fortaleza": "",
    "cuiabá": "",
    "juventude": "",
    "sport": "",
    "goiás": "https://tenor.com/view/torcida-fjg-for%C3%A7a-jovem-goi%C3%A1s-gif-1316517536206430915",
    
    # Chave genérica para times sem gif específico
    "default": "https://media.tenor.com/P5WfN5uTi44AAAAC/soccer-goal.gif"
}

FALAS_BOT = {
    "atlético mineiro": [
        "EU FALEI PORRA!!! AQUI É GALO!!! 🐓🔥",
        "GALOOOOOOOO ATÉ MORRER!!! 🖤🤍",
        "RESPEITA O MAIOR DE MINAS!!! 🏆",
        "CHUPA SECADOR!!! DEU GALO!!! 😈🐓",
        "ELE NÃO GANHA, ELE BICAAAAAAAAAAAA 🐓"
    ],

    "flamengo": [
        "VAMOOOOO PORRA!!! ISSO É FLAMENGO!!! 🔴⚫",
        "NO MARACA OU FORA, DEU MENGÃO!!! 🔥",
        "RESPEITA A MAIOR TORCIDA DO BRASIL!!! 🏆",
        "MENGÃO NÃO PERDOA!!! 😈",
        "CHORA SECADOR, HOJE TEM FLAMENGO!!! 🔴⚫",
        "OUTRO DIA NORMAL PRA NAÇÃO!!! GANHAMO!!! 🏆"
    ],

    "corinthians": [
        "VAI CORINTHIANS PORRA!!! 🦅",
        "AQUI É TIMÃO!!! RESPEITA!!! ⚫⚪",
        "FIEL EM FESTA!!! DEU CORINTHIANS!!! 🔥",
        "CORINTHIANS É ISSO AÍ!!! 😤",
        "SECADOR PASSA MAL!!! 🦅"
    ],

    "palmeiras": [
        "AVANTI PORRA!!! DEU VERDÃO!!! 🟢⚪",
        "PALMEIRAS IMPÕE RESPEITO!!! 😎",
        "GANHAR É ROTINA!!! 🏆",
        "VERDÃO NÃO PERDOA!!! 🔥",
        "SECADOR CHORA MAIS UMA VEZ!!! 😈"
    ],

    "são paulo": [
        "RESPEITA O SOBERANO!!! 🔴⚪⚫",
        "TRICOLOR É TRICOLOR, PORRA!!!",
        "CAMISA PESADA DEMAIS!!! 🏆",
        "SÃO PAULO IMPÕE RESPEITO!!! 😎",
        "GANHAMO!!! CHUPA SECADOR!!! 😈"
    ],

    "fluminense": [
        "VENCE O FLUMINENSE PORRA!!! 🇭🇺",
        "NENSE JOGA BOLA!!! RESPEITA!!! 😎",
        "FLU É DIFERENTE!!! 🔥",
        "TRICOLOR DAS LARANJEIRAS!!! 🏆",
        "SECADOR VAI TER QUE ENGOLIR!!! 😈"
    ],

    "cruzeiro": [
        "AQUI É CABULOSO PORRA!!! 💙",
        "CRUZEIRO IMPÕE RESPEITO!!! 🏆",
        "RAPOSA EM FESTA!!! 🦊",
        "VAMO CABULOSO, RAPOSA CAÇAAAAAA",
        "SECADOR CHORA!!! 😈"
    ],

    "internacional": [
        "VAMOOOO INTER PORRA!!! 🔴⚪",
        "COLORADO IMPÕE RESPEITO!!! 🔥",
        "NO BEIRA-RIO MANDA O INTER!!! 🏟️",
        "DEU INTER!!! 🏆",
        "SECADOR NÃO TEM VEZ!!! 😈"
    ],

    "botafogo": [
        "FOGÃOOOOOO PORRA!!! 🔥⭐",
        "O GLORIOSO VENCE!!! 🖤⚪",
        "BOTAFOGO IMPÕE RESPEITO!!! 😎",
        "ESTRELA SOLITÁRIA BRILHA!!! ⭐",
        "SECADOR CHORA!!! 😈"
    ],

    "vasco": [
        "RESPEITA O GIGANTE PORRA!!! ⚓",
        "VASCO É VASCO!!! 🔥",
        "DEU VASCÃO!!! 🏆",
        "O GIGANTE SE IMPÕE!!! 😤",
        "SECADOR ENGASGA!!! 😈"
    ],

    "default": [
        "É GOL PORRA!!! 🔥",
        "TIME EM FESTA!!! 🏆",
        "VENCEEEEU!!! 😎",
        "CHUPA SECADOR!!! 😈",
        "COMEMORA TORCIDA!!! 🙌"
    ]
}

LIGAS_PERMITIDAS = [1, 2, 71, 11, 13] #73copa do brasil remoção temporaria


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
    canal_jogos = canal  # Adicionar esta linha para compatibilidade
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
        emoji_casa = EMOJI_TIMES.get(nome_casa, "🔵")
        emoji_fora = EMOJI_TIMES.get(nome_fora, "🔴")

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
                title="<a:283534greenheartcoin:1465428163722219601> Apostas Abertas Agora!",
                description=(
                    f"⏰ Horário: {horario_br} (BR)\n\n"
                    f"{cargo_futebol} <a:347621pingbobstare:1465428636189327463> reaja para apostar:"
                ),
                color=discord.Color.blue()
            )
                
                embed.add_field(name=f"{emoji_casa} {casa}", value="Casa", inline=True)
                embed.add_field(name=f"{EMOJI_EMPATE} Empate", value="Empate", inline=True)
                embed.add_field(name=f"{emoji_fora} {fora}", value="Visitante", inline=True)
                embed.set_footer(text="Apostas abertas por 10 minutos!")

                if partida["league"]["id"] == 13:
                    await canal_apostas.send(
                        "🏆 **APOSTAS ABERTAS PARA A LIBERTADORES!**\n"
                        "https://tenor.com/view/libertadores-copa-libertadores-conmebol-libertadores-a-gl%C3%B3ria-eterna-gif-26983587"
                    )
                # Criar view antes de enviar mensagem
                view = ApostaView(fixture_id, casa, fora)
                
                mensagem = await canal_apostas.send(
                    content=cargo_futebol,
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(roles=True)
                )
                
                # Vincular dados à mensagem
                view.set_message(mensagem)
                
                if partida["league"]["id"] == 1:
                    await canal_apostas.send(
                        "**APOSTAS ABERTAS PARA A COPA DO MUNDO!**\n"
                        "https://tenor.com/view/world-cup-fifa2018-flames-%E5%A4%A7%E5%8A%9B%E7%A5%9E%E6%9D%AF-gif-12061955"
                    )
                if partida["league"]["id"] == 2:
                    await canal_apostas.send(
                        "**APOSTAS ABERTAS PARA A UEFA CHAMPIONS LEAGUE!**\n"
                        "https://tenor.com/view/uefa-champions-league-opening-football-gif-5552229"
                    )
                
                
                # Armazenar dados na mensagem para o on_interaction acessar
                #view = mensagem.components[0].children[0].view if mensagem.components else None
                #if view:
                #    view.set_message(mensagem)
                
                

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
                frase_home = PALAVRAS_GOL.get(key_home, f"🔵 GOOOOOOOL DO {casa.upper()}!")
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
                role_home = discord.utils.get(canal_jogos.guild.roles, name=role_home_name)
                mention_home = role_home.mention if role_home else f"@{role_home_name}"
                await canal_jogos.send(content=f"{mention_home} {emoji_casa}", embed=embed)

            if gols_fora > gols_anteriores_fora:
                key_away = MAPEAMENTO_TIMES.get(fora.lower(), fora.lower())
                frase_away = PALAVRAS_GOL.get(key_away, f"🔴 GOOOOOOOL DO {fora.upper()}!")
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
                role_away = discord.utils.get(canal_jogos.guild.roles, name=role_away_name)
                mention_away = role_away.mention if role_away else f"@{role_away_name}"
                await canal_jogos.send(content=f"{mention_away} {emoji_fora}", embed=embed)

        except Exception as e:
            logging.error(f"❌ Erro ao enviar notificação de gol: {e}")

        # --------------------------------------------------------------------
        # 5.3) PROCESSAR FIM DE JOGO + APOSTAS
        # --------------------------------------------------------------------
        conn = None
        cursor = None
        try:
            if status in ("ft", "aet", "pen"):
                logging.info(f"🎯 Jogo {fixture_id} ({casa} x {fora}) finalizado com status '{status}'. Processando...")

                # 🔎 Checar se já foi processado
                conn = conectar_futebol()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT processado FROM jogos WHERE fixture_id = %s", (fixture_id,))
                row = cursor.fetchone()

                if row and row["processado"] == 1:
                    logging.warning(f"⚠️ Jogo {fixture_id} já foi processado anteriormente. Pulando processamento...")
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
                
                logging.info(f"📊 Resultado final do jogo {fixture_id}: {resultado_final} ({gols_casa} x {gols_fora})")

                # Buscar apostas
                cursor.execute("SELECT user_id, palpite, modo_clown FROM apostas WHERE fixture_id = %s", (fixture_id,))
                apostas = cursor.fetchall()
                logging.info(f"📋 Total de apostas encontradas para {fixture_id}: {len(apostas) if apostas else 0}")

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

                # Mapa de pontos por liga (win_pts, lose_pts)
                pontos_por_liga = {
                    1:  (50, -40),
                    2:  (30, -25),
                    71: (15, -7),
                    73: (20, -12),
                    13: (35, -20),
                    11: (15, -7),
                }

                league_id = partida.get("league", {}).get("id")
                win_pts, lose_pts = pontos_por_liga.get(league_id, (15, -7))

                for aposta in apostas:
                    user_id = aposta["user_id"]
                    palpite = aposta["palpite"]
                    modo_clown = int(aposta.get("modo_clown", 0))
                    acertou = (palpite == resultado_final)

                    # Se for bônus de minoria, dobra os pontos de vitória (comportamento antigo)
                    pontos_base_vitoria = (win_pts * 2) if (acertou and bonus_minoria) else win_pts

                    # Aplicar pontuação via função central (passa também perda base)
                    try:
                        processar_aposta(user_id, fixture_id, resultado_final, pontos_base_vitoria, perda_base=lose_pts)
                    except Exception as e:
                        logging.error(f"Erro ao processar aposta automática de {user_id}: {e}")

                    # Mensagem DM (preview)
                    if acertou:
                        mult = 6 if modo_clown == 1 else 1
                        pontos_preview = pontos_base_vitoria * mult
                        mensagens_pv.append(
                            (user_id, f"<:JinxKissu:1408843869784772749> Você **acertou** o resultado de **{casa} x {fora}**!\n➡️ **+{pontos_preview} pontos**" + (" (bônus de minoria)" if (pontos_base_vitoria == (win_pts * 2)) else ""))
                        )
                    else:
                        mult = 4 if modo_clown == 1 else 1
                        pontos_preview = lose_pts * mult
                        mensagens_pv.append(
                            (user_id, f"❌ Você **errou** o resultado de **{casa} x {fora}**.\n➡️ **{pontos_preview} pontos**.")
                        )

                logging.info(f"✔️ Pontuação processada e jogo {fixture_id} marcado como processado.")

                # Embed final
                embed_final = discord.Embed(
                    title=f"🏁 Fim de jogo — {casa} x {fora}",
                    description=f"Placar final: {emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
                    color=discord.Color.orange()
                )
                embed_final.set_footer(text="Obrigado por participar das apostas!")
                await canal_jogos.send(embed=embed_final)

                # Enviar DMs
                for user_id, msg in mensagens_pv:
                    usuario = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
                    if usuario:
                        try:
                            await usuario.send(msg)
                        except:
                            pass

                # 🔥 MARCAR COMO FINALIZADO APÓS PROCESSAR COM SUCESSO
                try:
                    # Usar upsert para garantir que o jogo seja marcado como processado/finalizado
                    # mesmo que não exista uma linha prévia em `jogos` (evita reprocessamento múltiplo).
                    cursor.execute(
                        """
                        INSERT INTO jogos (fixture_id, processado, finalizado, betting_open)
                        VALUES (%s, 1, 1, 0)
                        ON DUPLICATE KEY UPDATE processado=1, finalizado=1, betting_open=0
                        """,
                        (fixture_id,)
                    )
                    conn.commit()
                    logging.info(f"✅ Jogo {fixture_id} marcado como processado=1, finalizado=1 no banco de dados (upsert).")
                except Exception as e:
                    logging.error(f"❌ Erro ao marcar jogo {fixture_id} como finalizado no banco: {e}")
                    conn.rollback()

        except Exception as e:
            logging.error(f"❌ Erro ao processar apostas do fim de jogo (fixture_id={fixture_id}): {e}", exc_info=True)
        finally:
            # 🔥 Fecha conexão com segurança - SEM lógica de negócio
            if cursor:
                try:
                    cursor.close()
                    logging.debug(f"🔌 Cursor fechado para fixture_id={fixture_id}")
                except Exception as e:
                    logging.error(f"❌ Erro ao fechar cursor: {e}")
            
            if conn:
                try:
                    conn.close()
                    logging.debug(f"🔌 Conexão fechada para fixture_id={fixture_id}")
                except Exception as e:
                    logging.error(f"❌ Erro ao fechar conexão: {e}")

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
    "caixinha": 50,
    "clown_bet": 60,
    "emoji_personalizado": 4500,
    "comemoracao":1000,
    "mute_jinxed": 1500,
    "apelido": 1500,
    "inverter": 700
}
#==========================              ==========================  
#                          LOJA DE PONTOS
#==========================              ==========================  

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

# Cooldown para comando !troll
ultimo_troll = {}

def gerar_embed_loja():
    embed = discord.Embed(
        title="🛒 Loja de Pontos",
        description="Use seus pontos para comprar benefícios!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎭 Modo Clown — 60 pontos",
        value="• Multiplica pontos por 6 se acertar\n• Mas perde 4x se errar\n• Uso único\n• Use `/comprar`",
        inline=False
    )
    
    embed.add_field(
        name="<a:809469heartchocolate:1466494908243120256> Caixa Surpresa — 50 pontos",
        value="• Pode receber pontos aleatórios de -100 a 300\n• Pode vir até negativo 👀\n• Use `/comprar`",
        inline=False
    )
    
    embed.add_field(
        name="<:discotoolsxyzicon_6:1444750406763679764> Jinxed VIP — 1000 pontos",
        value="• Garante 15 dias do cargo VIP\n• Use `/comprar`",
        inline=False
    )
    
    embed.add_field(
        name="<:312424paint:1467578829705842709> Emoji Personalizado — 4500 pontos",
        value="• Compre e registre seu emoji personalizado\n• Use: `!comprar emoji_personalizado`\n• Depois use `!setemoji <emoji>` para registrar",
        inline=False
    )
    
    embed.add_field(
        name="<:827557party:1467578831106871610> Comemoração de Vitória — 1000 pontos",
        value="• Escolha um time.\n• Se ele vencer o próximo jogo, o bot posta um GIF festejando além de comemorar!\n• Use: `!comprar comemoracao` e depois `!comemorar <time>`",
        inline=False
    )
    
    embed.add_field(
        name="<:34000mute:1467578828313464861> Mute Jinxed — 1500 pontos",
        value="• Mute alguém por 3 minutos usando !troll\n• Funciona mesmo se o bot não tiver permissão\n• Uso único\n• Use: `!comprar mute_jinxed`",
        inline=False
    )
    
    embed.add_field(
        name="<:451118spongebobishowspeedmeme:1473022252474958025> Apelido — 1500 pontos",
        value="• Troque o apelido de alguém usando !apelido\n• Uso único\n• Use: `!comprar apelido`",
        inline=False
    )
    
    embed.add_field(
        name="<:7466megareverse:1467578833279385774> Inverter Pontos — 700 pontos",
        value="• Inverte o resultado da próxima aposta de um usuário\n• Se ele ia ganhar, vai perder\n• Se ele ia perder, vai ganhar\n• Use: `!comprar inverter` e depois `!inverter @usuario`",
        inline=False
    )
    
    embed.set_footer(text="Use: !comprar <item>")
    return embed

async def executar_compra(member, item, guild):
    """Função completa para processar compras"""
    PRECOS = {
        "jinxed_vip": 1000,
        "caixa_misteriosa": 50,
        "caixinha": 50,
        "clown_bet": 60,
        "emoji_personalizado": 4500,
        "comemoracao":1000,
        "mute_jinxed": 1500,
        "apelido": 1500,
        "inverter": 700
    }
    
    item_lower = item.lower()
    if item_lower not in PRECOS:
        return False, "<:3894307:1443956354698969149> Item não encontrado! Use `/loja` para ver os itens."
    
    preco = PRECOS[item_lower]
    pontos = pegar_pontos(member.id)
    
    if pontos < preco:
        return False, f"<:Jinxsip1:1390638945565671495> Você precisa de {preco} pontos para comprar este item. Você tem {pontos} pontos."
    
    # Processar compra
    adicionar_pontos_db(member.id, -preco)
    
    # Lógica específica para cada item
    if item_lower == "jinxed_vip":
        # Lógica para VIP
        logging.info(f"{member.name} (ID: {member.id}) comprou VIP por {preco} pontos.")
        cargo_vip = discord.utils.get(guild.roles, name="Jinxed Vip")
        if cargo_vip:
            await member.add_roles(cargo_vip)
            return True, f"<:discotoolsxyzicon_6:1444750406763679764> Você agora é **VIP** por 15 dias! 🎉"
    
    elif item_lower == "clown_bet":
        # Lógica para Clown Bet
        logging.info(f"{member.name} (ID: {member.id}) comprou Clown Bet por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO clown_bet (user_id, ativo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE ativo = 1",
            (member.id,)
        )
        con.commit()
        con.close()
        return True, f"🎭 Você comprou **Modo Clown**! Use na próxima aposta para multiplicar seus pontos!"
    
    elif item_lower in ["caixa_misteriosa", "caixinha"]:
        # Lógica para Caixa Surpresa
        logging.info(f"{member.name} (ID: {member.id}) comprou Caixinha por {preco} pontos.")
        
        # Verificar limite de 3 compras em 24 horas
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'caixinha' AND data_compra >= DATE_SUB(NOW(), INTERVAL 24 HOUR)",
            (member.id,)
        )
        limite_24h = cur.fetchone()[0]
        con.close()
        
        if limite_24h >= 3:
            adicionar_pontos_db(member.id, preco)  # Devolver os pontos
            return False, " Você já usou a **Caixinha** 3 vezes nas últimas 24 horas. Aguarde o cooldown de 24h após a última utilização."
        
        import random
        pontos_ganhos = random.randint(-200, 300)
        adicionar_pontos_db(member.id, pontos_ganhos)
        
        # Registrar no banco
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, pontos_ganhos, datetime.utcnow())
        )
        con.commit()
        con.close()
        
        if pontos_ganhos > 0:
            return True, f"<a:809469heartchocolate:1466494908243120256> Você ganhou **+{pontos_ganhos} pontos** na caixa surpresa! "
        elif pontos_ganhos < 0:
            return True, f"<a:809469heartchocolate:1466494908243120256> Você perdeu **{abs(pontos_ganhos)} pontos** na caixa surpresa! "
        else:
            return True, f"<a:809469heartchocolate:1466494908243120256> Você não ganhou nem perdeu pontos na caixa surpresa! "
        
    
    elif item_lower == "inverter":
        # Lógica para Inverter
        logging.info(f"{member.name} (ID: {member.id}) comprou Inverter Pontos por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        return True, f"<:7466megareverse:1467578833279385774> Você comprou **Inverter Pontos**! Use `!inverter @usuario` para inverter a próxima aposta de alguém."
    
    elif item_lower == "mute_jinxed":
        # Lógica para Mute
        logging.info(f"{member.name} (ID: {member.id}) comprou Mute Jinxed por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        return True, f"<:34000mute:1467578828313464861> Você comprou **Mute Jinxed**! Use `!troll @usuario` para mutar alguém por 3 minutos."
    
    elif item_lower == "apelido":
        # Lógica para Apelido
        logging.info(f"{member.name} (ID: {member.id}) comprou Apelido por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        return True, f"<:451118spongebobishowspeedmeme:1473022252474958025> Você comprou **Apelido**! Use `!apelido @usuario novo_apelido` para trocar o apelido de alguém."
    
    elif item_lower == "comemoracao":
        # Lógica para Comemoração
        logging.info(f"{member.name} (ID: {member.id}) comprou Comemoração por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        return True, f"<:827557party:1467578831106871610> Você comprou **Comemoração de Vitória**! Use `/comemorar time` para comemorar quando seu time vencer."
    
    elif item_lower == "emoji_personalizado":
        # Lógica para Emoji Personalizado
        logging.info(f"{member.name} (ID: {member.id}) comprou Emoji Personalizado por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (member.id, item_lower, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        return True, f"<:312424paint:1467578829705842709> Você comprou **Emoji Personalizado**! Use `/setemoji` para registrar seu emoji personalizado."
    
    else:
        return True, f"✅ Você comprou **{item}** por {preco} pontos!"

@bot.command()
async def loja(ctx):

    if ctx.channel.id != CANAL_PERMITIDO_ID:
        return await ctx.send(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>."
        )

    await ctx.send(embed=gerar_embed_loja())



@bot.command()
async def comprar(ctx, item_nome: str):
    user_id = ctx.author.id
    item = item_nome.lower()

    # Verifica se o comando foi usado no canal permitido
    if ctx.channel.id != CANAL_PERMITIDO_ID:
        return await ctx.send(f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.")

    if item not in PRECOS:
        return await ctx.send("<:3894307:1443956354698969149> Item não encontrado na loja! Use `!loja` para ver os itens.")

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
            await processar_conquistas(
                member=ctx.author,
                mensagens_semana=0,  # valores padrão
                maior_streak=0,
                fez_doacao=False,
                tem_vip=True,  
                tempo_em_call=0,
                mencionou_miisha=False,
                tocou_musica=False,
                mencoes_bot=0
            )
            logging.info(f"{ctx.author.name} comprou o cargo Jinxed Vip por 15 dias.")
        else:
            await ctx.send("⚠️ Cargo 'Jinxed Vip' não encontrado no servidor.")

    elif item == "caixinha":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Caixinha de Surpresa por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'caixinha' AND data_compra >= DATE_SUB(NOW(), INTERVAL 24 HOUR)",
            (user_id,)
        )
        limite_24h = cur.fetchone()[0]
        if limite_24h >= 3:
            adicionar_pontos_db(user_id, preco)
            con.close()
            await ctx.send("⏳ Você já usou a **Caixinha** 3 vezes nas últimas 24 horas. Aguarde o cooldown de 24h após a última utilização.")
            return

        pontos_sorteados = random.randint(-100, 300)
        adicionar_pontos_db(user_id, pontos_sorteados)
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, pontos_sorteados, datetime.utcnow())
        )
        con.commit()
        con.close()
        if pontos_sorteados > 0:
            await ctx.send(f"🎁 Você abriu a **Caixinha de Surpresa** e ganhou **+{pontos_sorteados} pontos!** 💰")
        elif pontos_sorteados < 0:
            await ctx.send(f"😢 Você abriu a **Caixinha de Surpresa** e perdeu **{abs(pontos_sorteados)} pontos!** 💔")
        else:
            await ctx.send(f"😐 Você abriu a **Caixinha de Surpresa** e não ganhou nem perdeu pontos!** 📦")

    elif item == "clown_bet":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Clown Bet por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO clown_bet (user_id, ativo) VALUES (%s, 1) ON DUPLICATE KEY UPDATE ativo = 1",
            (user_id,)
        )
        con.commit()
        con.close()
        await ctx.send("🎭 Você ativou a **Clown Bet**! Próxima aposta: 6x se acertar, 4x se errar.")

    elif item == "emoji_personalizado":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Emoji Personalizado por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()

        await ctx.send(
            "<:312424paint:1467578829705842709> Você comprou **Emoji Personalizado** por 4.500 pontos!\n"
            "Agora use **`!setemoji`** para criar seu cargo com ícone personalizado."
        )

    elif item == "comemoracao":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Comemoração por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send(f"<:827557party:1467578831106871610> **Compra realizada!** Agora use `!comemorar <nome_do_time>` para agendar a festa no próximo jogo!")

    elif item == "mute_jinxed":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Mute Jinxed por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send("<:34000mute:1467578828313464861> Você comprou o Mute Jinxed! Use !troll @usuario para mutar alguém por 3 minutos.")
    elif item == "apelido":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Apelido por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send("<:451118spongebobishowspeedmeme:1473022252474958025> Você comprou o Apelido! use !apelido @user <nome_do_apelido>")
    
    elif item == "inverter":
        logging.info(f"{ctx.author.name} (ID: {user_id}) comprou Inverter Pontos por {preco} pontos.")
        con = conectar_futebol()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO loja_pontos (user_id, item, pontos_gastos, data_compra, ativo) VALUES (%s, %s, %s, %s, 1)",
            (user_id, item, preco, datetime.utcnow())
        )
        con.commit()
        con.close()
        await ctx.send("<:7466megareverse:1467578833279385774> Você comprou **Inverter Pontos**! Use `!inverter @usuario` para inverter a próxima aposta de alguém.")

@bot.command()
async def inverter(ctx, target: discord.Member):
    """Usa o item Inverter em um usuário específico"""
    user_id = ctx.author.id
    target_id = target.id
    
    # Verificar se o comando foi usado no canal permitido
    if ctx.channel.id != CANAL_PERMITIDO_ID:
        return await ctx.send(f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.")
    
    # Verificar se tem o item inverter disponível
    conn = conectar_futebol()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM loja_pontos WHERE user_id = %s AND item = 'inverter' AND ativo = 1",
        (user_id,)
    )
    item_row = cursor.fetchone()
    
    if not item_row:
        conn.close()
        return await ctx.send("❌ Você não tem um item **Inverter** disponível. Use `!comprar inverter` para adquirir um.")
    
    # Verificar se o usuário alvo já tem uma inversão pendente
    cursor.execute(
        "SELECT id FROM inversoes WHERE target_user_id = %s AND used = 0",
        (target_id,)
    )
    inversao_pendente = cursor.fetchone()
    
    if inversao_pendente:
        conn.close()
        return await ctx.send(f"⚠️ {target.mention} já tem uma inversão pendente!")
    
    # Criar a inversão
    cursor.execute(
        "INSERT INTO inversoes (target_user_id, creator_user_id, fixture_id, used) VALUES (%s, %s, NULL, 0)",
        (target_id, user_id)
    )
    
    # Marcar item como usado
    cursor.execute("UPDATE loja_pontos SET ativo = 0 WHERE id = %s", (item_row[0],))
    
    conn.commit()
    conn.close()
    
    await ctx.send(f"🔄 **Inversão ativada!** A próxima aposta de {target.mention} terá seus pontos invertidos!")
    logging.info(f"{ctx.author.name} usou Inverter em {target.name}")
    
    # Esperar 3 segundos e apagar mensagens
    await asyncio.sleep(3)
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command()
async def apelido(ctx, alvo: discord.Member, *, novo_apelido: str):

    # não permitir bots
    if alvo.bot:
        return await ctx.send("🤖 Bots não podem ser trolados.")

    con = conectar_futebol()
    cur = con.cursor()

    # verifica se o usuário tem o item ativo
    cur.execute(
        "SELECT id FROM loja_pontos "
        "WHERE user_id = %s AND item = 'apelido' AND ativo = 1 "
        "LIMIT 1",
        (ctx.author.id,)
    )
    item = cur.fetchone()

    if not item:
        con.close()
        return await ctx.send("❌ Você não possui um item **Apelido**.")

    # tenta trocar o apelido
    try:
        apelido_antigo = alvo.nick  # pode ser None

        await alvo.edit(
            nick=novo_apelido,
            reason=f"Apelido troll usado por {ctx.author}"
        )

        await ctx.send(
            f"👤 {alvo.mention} agora se chama **{novo_apelido}** 😈"
        )

        

    except discord.Forbidden:
        await ctx.send(
            f"😈 Tentou trocar o apelido de {alvo.mention}, "
            "mas ele é poderoso demais!"
        )

    finally:
        # consome o item (mesmo se falhar — estilo Jinxed 😏)
        cur.execute(
            "UPDATE loja_pontos SET ativo = 0 WHERE id = %s",
            (item[0],)
        )
        con.commit()
        con.close()

@bot.command()
async def comemorar(ctx, *, time_nome: str):
    user_id = ctx.author.id
    
    # Normaliza o nome usando seu mapeamento existente
    chave_time = MAPEAMENTO_TIMES.get(time_nome.lower(), time_nome.lower())

    # Verifica se o usuário comprou o item
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'comemoracao' AND ativo = 1",
        (user_id,)
    )
    comprado = cur.fetchone()[0]
    if comprado == 0:
        con.close()
        return await ctx.send("❌ Você precisa comprar o item **Comemoração** primeiro usando `!comprar comemoracao`.")

    # Salva no banco
    cur.execute(
        "INSERT INTO comemoracoes (user_id, team_key) VALUES (%s, %s)",
        (user_id, chave_time)
    )
    con.commit()
    con.close()

    emoji = EMOJI_TIMES.get(chave_time, "⚽")
    await ctx.send(f"🎉 **Agendado!** Se o **{chave_time.upper()}** {emoji} ganhar o próximo jogo, vou soltar o GIF de vitória em sua homenagem!")
    


@bot.command()
async def setemoji(ctx):
    """
    Comando interativo para criar um cargo personalizado com ícone de imagem.
    O bot pede: 1) Nome do cargo, 2) Uma imagem (PNG ou JPG)
    """
    user_id = ctx.author.id

    # ===== 1️⃣ VERIFICAR COMPRA DO ITEM =====
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'emoji_personalizado' AND ativo = 1",
        (user_id,)
    )
    comprado = cur.fetchone()[0]
    if comprado == 0:
        con.close()
        return await ctx.send("❌ Você precisa comprar o item **Emoji Personalizado** primeiro usando `!comprar emoji_personalizado`.")
    
    con.close()

    # ===== 2️⃣ PEDIR NOME DO CARGO =====
    await ctx.send("📝 **Digite o nome do cargo personalizado** (máximo 100 caracteres):\n`Exemplo: Fúria, Lenda, Rei dos Games, etc.`")
    
    try:
        msg_nome = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            timeout=60.0
        )
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ Tempo esgotado! Comando cancelado.")
    
    nome_cargo = msg_nome.content.strip()
    
    # Validar nome
    if not nome_cargo or len(nome_cargo) > 100:
        return await ctx.send("❌ O nome do cargo deve ter entre 1 e 100 caracteres.")

    # ===== 3️⃣ PEDIR IMAGEM =====
    await ctx.send(f"🖼️ **Agora envie uma imagem para usar como ícone do cargo**\n\n"
                   f"📌 Requisitos:\n"
                   f"• Formato: PNG ou JPG\n"
                   f"• Tamanho máximo: 256 KB\n"
                   f"• Dimensões recomendadas: 256x256px ou maior\n\n"
                   f"⏰ Você tem 60 segundos para enviar a imagem!")
    
    try:
        msg_imagem = await bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == ctx.channel and len(m.attachments) > 0,
            timeout=60.0
        )
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ Tempo esgotado! Comando cancelado.")
    
    if not msg_imagem.attachments:
        return await ctx.send("❌ Nenhuma imagem foi enviada. Comando cancelado.")
    
    arquivo = msg_imagem.attachments[0]
    
    # ===== 4️⃣ VALIDAR IMAGEM =====
    # Verificar extensão
    extensoes_permitidas = [".png", ".jpg", ".jpeg"]
    if not any(arquivo.filename.lower().endswith(ext) for ext in extensoes_permitidas):
        return await ctx.send(f"❌ Formato de arquivo inválido! Apenas PNG e JPG são aceitos.\nVocê enviou: `{arquivo.filename}`")
    
    # Verificar tamanho (Discord permite até 10MB, mas 256KB é mais seguro para role icon)
    tamanho_max = 256 * 1024  # 256 KB
    if arquivo.size > tamanho_max:
        tamanho_kb = arquivo.size / 1024
        return await ctx.send(f"❌ Arquivo muito grande! Tamanho: {tamanho_kb:.1f} KB (máximo: 256 KB)\n"
                             f"Dica: Comprima ou redimensione a imagem.")
    
    # ===== 5️⃣ DOWNLOAD DA IMAGEM =====
    try:
        imagem_bytes = await arquivo.read()
    except Exception as e:
        return await ctx.send(f"❌ Erro ao fazer download da imagem: {e}")
    
    # ===== 6️⃣ CRIAR CARGO COM ÍCONE =====
    con = conectar_futebol()
    cur = con.cursor()
    
    try:
        # Deletar cargo anterior se existir
        nome_cargo_full = f"{nome_cargo}"
        cargo_existente = discord.utils.get(ctx.guild.roles, name=nome_cargo_full)
        if cargo_existente:
            await cargo_existente.delete()
            await asyncio.sleep(0.5)
        
        # Criar novo cargo com ícone de imagem
        cargo = await ctx.guild.create_role(
            name=nome_cargo_full,
            color=discord.Color.blurple(),
            display_icon=imagem_bytes,
            reason=f"Cargo de ícone personalizado para {ctx.author.name}"
        )
        
        # ===== 7️⃣ ADICIONAR CARGO AO USUÁRIO =====
        await ctx.author.add_roles(cargo)
        
        # ===== 8️⃣ SALVAR NO BANCO DE DADOS =====
        cur.execute(
            "UPDATE loja_pontos SET nome_cargo = %s, cargo_id = %s, emoji = %s WHERE user_id = %s AND item = 'emoji_personalizado' AND ativo = 1",
            (nome_cargo, cargo.id, "[imagem]", user_id)
        )
        con.commit()
        
        # Sucesso!
        await ctx.send(
            f"✅ **Cargo criado com sucesso!**\n"
            f"👤 Nome: **{nome_cargo}**\n"
            f"🖼️ Ícone: Imagem aplicada\n"
            f"🎉 O cargo foi adicionado ao seu perfil!\n\n"
            f"*Seu cargo está visível e exclusivo para você!*"
        )
        
        logging.info(f"Cargo '{nome_cargo}' criado para {ctx.author.name} (ID: {user_id}) com ícone personalizado")
        
    except discord.HTTPException as e:
        con.close()
        if "10011" in str(e):  # Invalid image
            return await ctx.send("❌ A imagem enviada está corrompida ou em formato inválido. Tente outra imagem.")
        else:
            return await ctx.send(f"❌ Erro ao criar o cargo: {str(e)[:100]}")
    
    except Exception as e:
        con.close()
        logging.error(f"Erro ao criar cargo: {e}")
        await ctx.send(f"❌ Erro inesperado: {str(e)[:100]}")
        return
    
    con.close()


def processar_aposta(user_id, fixture_id, resultado, pontos_base, perda_base=7, tem_inversao=False):
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

    # 3️⃣ Calcular pontos ganhos ou perdidos (sem inversão)
    acertou = (aposta_usuario == resultado)
    
    if acertou:
        # Acertou a aposta
        pontos_final = pontos_base * multiplicador_vitoria
    else:
        # Errou a aposta
        pontos_final = -abs(perda_base) * multiplicador_derrota
    
    # APLICAR INVERSÃO DE PONTOS
    if tem_inversao:
        pontos_final = -pontos_final  # Inverte os pontos: +50 vira -50, -40 vira +40
    
    # Aplicar pontos finais
    adicionar_pontos_db(user_id, pontos_final)
    
    # Determinar resultado final com base nos pontos após inversão
    ganhou_final = pontos_final > 0
    
    if ganhou_final:
        # Incrementar acertos consecutivos (usando tabela unificada usuarios)
        atualizar_streak(user_id, True)
        
        resultado_texto = f"ganhou {abs(pontos_final)} pontos"
        if tem_inversao:
            resultado_texto += " 🔄 (invertido)"
        
        logging.info(f"Usuário {user_id} {resultado_texto}!")
    else:
        # Errou a aposta - resetar acertos consecutivos (usando tabela unificada usuarios)
        atualizar_streak(user_id, False)
        
        resultado_texto = f"perdeu {abs(pontos_final)} pontos"
        if tem_inversao:
            resultado_texto += " 🔄 (invertido)"
        logging.info(f"Usuário {user_id} {resultado_texto}!")

    conn.commit()
    conn.close()
    
    # Verificar conquistas automaticamente após processar aposta
    try:
        # Obter os dados atuais do usuário para verificar conquistas
        conn_fut = conectar_futebol()
        cur_fut = conn_fut.cursor(dictionary=True)
        
        # Buscar acertos consecutivos atualizados
        cur_fut.execute(
            "SELECT acertos_consecutivos FROM apostas WHERE user_id = %s",
            (user_id,)
        )
        resultado_acertos = cur_fut.fetchone()
        acertos_consecutivos = resultado_acertos["acertos_consecutivos"] if resultado_acertos else 0
        
        # Estatísticas do usuário
        cur_fut.execute(
            "SELECT COUNT(*) as total FROM apostas WHERE user_id = %s",
            (user_id,)
        )
        total_apostas = cur_fut.fetchone()["total"]
        
        cur_fut.execute(
            "SELECT COUNT(*) as acertos FROM apostas WHERE user_id = %s AND palpite = resultado AND fixture_id IN (SELECT fixture_id FROM jogos WHERE finalizado = 1)",
            (user_id,)
        )
        total_acertos = cur_fut.fetchone()["acertos"]
        
        taxa_acerto = (total_acertos / total_apostas * 100) if total_apostas > 0 else 0
        
        # Verificar se tem doação ativa
        cur_fut.execute(
            "SELECT id FROM loja_pontos WHERE user_id = %s AND item = 'doacao_50' AND ativo = 1",
            (user_id,)
        )
        fez_doacao = cur_fut.fetchone() is not None
        
        cur_fut.close()
        conn_fut.close()
        
        # Verificar VIP
        conn_vips = conectar_vips()
        cur_vips = conn_vips.cursor(dictionary=True)
        cur_vips.execute(
            "SELECT id FROM vips WHERE id = %s AND data_fim > NOW()",
            (user_id,)
        )
        tem_vip = cur_vips.fetchone() is not None
        cur_vips.close()
        conn_vips.close()
        
        # Tentar obter o usuário do bot
        user_obj = None
        for guild in bot.guilds:
            user_obj = guild.get_member(user_id)
            if user_obj:
                break
        
        if user_obj:
            # Verificar conquistas de forma assíncrona
            asyncio.create_task(
                processar_conquistas(
                    member=user_obj,
                    mensagens_semana=0,  
                    maior_streak=acertos_consecutivos,
                    fez_doacao=fez_doacao,
                    tem_vip=tem_vip,
                    tempo_em_call=0  
                )
            )
            logging.info(f"📊 Usuário {user_id}: {total_acertos}/{total_apostas} acertos ({taxa_acerto:.1f}%) - Verificação automática de conquistas iniciada")
    
    except Exception as e:
        logging.error(f"Erro ao verificar conquistas automáticas para usuário {user_id}: {e}")


async def processar_jogo(fixture_id, ctx=None, automatico=False):
    """
    Função reutilizável para processar finalização de jogos
    
    Args:
        fixture_id: ID do jogo a ser processado
        ctx: Contexto do Discord (opcional, para modo manual)
        automatico: Se True, não envia mensagens de status
    
    Returns:
        dict: {'processado': bool, 'mensagem': str, 'erro': str}
    """
    conn = None
    cursor = None
    processado_com_sucesso = False
    
    try:
        logging.info(f"🎮 Iniciando processamento do jogo {fixture_id} (automático={automatico})...")
        conn = conectar_futebol()
        cursor = conn.cursor(dictionary=True)

        # Verificar se jogo já foi processado
        cursor.execute("SELECT processado FROM jogos WHERE fixture_id = %s", (fixture_id,))
        row = cursor.fetchone()
        if row and row.get("processado") == 1:
            logging.warning(f"⚠️ Jogo {fixture_id} já foi processado antes. Ignorando...")
            conn.close()
            conn = None
            cursor = None
            return {'processado': False, 'mensagem': f"⚠️ Jogo {fixture_id} já foi processado.", 'erro': None}

        # Buscar dados da API com tratamento robusto de erros
        logging.info(f"🔗 Buscando dados do jogo {fixture_id} na API...")
        async with aiohttp.ClientSession() as session:
            async with session.get(URL, headers=HEADERS, params={"id": fixture_id}) as response:
                data = await response.json()
        logging.info(f"✅ Dados recebidos da API para jogo {fixture_id}")

        if not data.get("response"):
            logging.error(f"❌ Jogo {fixture_id} não encontrado na API")
            conn.close()
            conn = None
            cursor = None
            return {'processado': False, 'mensagem': f"❌ Jogo {fixture_id} não encontrado na API.", 'erro': 'api_not_found'}

        partida = data["response"][0]
        casa = partida["teams"]["home"]["name"]
        fora = partida["teams"]["away"]["name"]
        gols_casa = partida["goals"]["home"] or 0
        gols_fora = partida["goals"]["away"] or 0
        status = partida["fixture"]["status"]["short"].lower()
        logging.info(f"⚽ Partida: {casa} {gols_casa}x{gols_fora} {fora} | Status: {status}")

        # Verificar se jogo finalizou
        if status not in ("ft", "aet", "pen"):
            logging.warning(f"⏳ Jogo {fixture_id} ainda NÃO finalizou (status: {status})")
            conn.close()
            conn = None
            cursor = None
            if not automatico and ctx:
                await ctx.send(f"⚠️ Jogo {fixture_id} ainda não finalizou (status: {status}).")
            return {'processado': False, 'mensagem': f"Jogo {fixture_id} não finalizado (status: {status})", 'erro': 'not_finished'}

        # Determinar resultado
        if gols_casa > gols_fora:
            resultado_final = "home"
            resultado_texto = f"**{casa}** venceu!"
            time_vencedor_nome = casa
        elif gols_fora > gols_casa:
            resultado_final = "away"
            resultado_texto = f"**{fora}** venceu!"
            time_vencedor_nome = fora
        else:
            resultado_final = "draw"
            resultado_texto = "A partida terminou em **empate 🤝**!"
            time_vencedor_nome = None
        logging.info(f"🏆 Resultado final: {resultado_final} - Vencedor: {time_vencedor_nome or 'Empate'}")

        # -----------------------------------------------------------
        # LÓGICA: COMEMORAÇÃO DE VITÓRIA
        # -----------------------------------------------------------
        logging.info(f"🎉 Processando comemoração para {time_vencedor_nome or 'Empate'}...")
        if time_vencedor_nome:  
            # Pega a chave normalizada do vencedor (ex: "galo")
            chave_vencedor = MAPEAMENTO_TIMES.get(time_vencedor_nome.lower(), time_vencedor_nome.lower())
            logging.debug(f"Chave normalizada: {chave_vencedor}")
            
            conn_com = conectar_futebol()
            cur_com = conn_com.cursor()
            
            # Busca quem pediu comemoração para esse time
            cur_com.execute("SELECT id, user_id FROM comemoracoes WHERE team_key = %s", (chave_vencedor,))
            rows_com = cur_com.fetchall()
            
            if rows_com:
                # Pega o GIF
                gifs = GIFS_VITORIA_TIME.get(chave_vencedor, GIFS_VITORIA_TIME.get("default"))

                if not isinstance(gifs, list):
                    logging.warning(
                        "GIF do time '%s' não está em lista. Convertendo automaticamente.",
                        chave_vencedor
                    )
                    gifs = [gifs]
                
                gifs_escolhidos = random.sample(gifs, k=min(2, len(gifs)))
                # Monta lista de menções dos usuários
                usuarios_mencoes = []
                ids_para_remover = []
                
                for row in rows_com:
                    uid = row[0]  # ID do banco (para deletar)
                    discord_id = row[1]
                    ids_para_remover.append(uid)
                    usuarios_mencoes.append(f"<@{discord_id}>")
                
                texto_mencoes = ", ".join(usuarios_mencoes)
                
                # Envia a mensagem no canal de jogos
                canal_jogos = bot.get_channel(CANAL_JOGOS_ID)
                if canal_jogos:
                    await canal_jogos.send(
                        f"🎇 **A FESTA COMEÇA!** Vitória do **{time_vencedor_nome.upper()}**!\n"
                        f"Comemoração patrocinada por: {texto_mencoes}\n"
                        + "\n".join(gifs_escolhidos)
                    )
                    
                    # Envia 2 falas aleatórias do bot
                    falas_time = FALAS_BOT.get(chave_vencedor, FALAS_BOT.get("default", []))
                    if falas_time:
                        falas_sorteadas = random.sample(falas_time, min(2, len(falas_time)))
                        for fala in falas_sorteadas:
                            await canal_jogos.send(fala)
                
                # Remove as comemorações usadas do banco (para não repetir no próximo jogo)
                format_strings = ','.join(['%s'] * len(ids_para_remover))
                cur_com.execute(f"DELETE FROM comemoracoes WHERE id IN ({format_strings})", tuple(ids_para_remover))
                conn_com.commit()
                logging.info(f"✅ Comemorações processadas para {chave_vencedor}")

            cur_com.close()
            conn_com.close()

        # Buscar apostas
        logging.info(f"📊 Buscando apostas do jogo {fixture_id}...")
        cursor.execute("SELECT user_id, palpite, modo_clown FROM apostas WHERE fixture_id = %s", (fixture_id,))
        apostas = cursor.fetchall()
        logging.info(f"📋 Total de apostas: {len(apostas) if apostas else 0}")

        # Calcular bônus de minoria
        contagem = {"home": 0, "away": 0, "draw": 0}
        for a in apostas:
            p = a["palpite"]
            if p in contagem:
                contagem[p] += 1
        votos_vencedor = contagem.get(resultado_final, 0)
        votos_max = max(contagem.values()) if contagem else 0
        bonus_minoria = votos_vencedor > 0 and votos_vencedor < votos_max
        logging.info(f"🎯 Contagem de votos: {contagem} | Bônus de minoria: {bonus_minoria}")

        mensagens_pv = []

        # Pontuação por liga
        pontos_por_liga = {
            1:  (50, -40),
            2:  (30, -25),
            71: (15, -7),
            73: (20, -12),
            13: (35, -20),
            11: (15, -7),
        }

        league_id = partida.get("league", {}).get("id") if partida else None
        win_pts, lose_pts = pontos_por_liga.get(league_id, (15, -7))
        logging.info(f"💰 Pontos: Liga {league_id} | Vitória: {win_pts} | Derrota: {lose_pts}")

        # Processar cada aposta
        apostas_processadas = 0
        for aposta in apostas:
            user_id = aposta["user_id"]
            palpite = aposta["palpite"]
            modo_clown = int(aposta.get("modo_clown", 0))
            logging.debug(f"📌 Processando aposta do usuário {user_id}: palpite={palpite}, clown={modo_clown}")
            
            # -------------------------------------------------
            # VERIFICAR INVERSÃO ATIVA
            # -------------------------------------------------
            cursor.execute(
                "SELECT id FROM inversoes WHERE target_user_id = %s AND used = 0 LIMIT 1",
                (user_id,)
            )
            inversao = cursor.fetchone()
            tem_inversao = inversao is not None
            
            # Calcular acertou normal (sem inversão)
            acertou_normal = (palpite == resultado_final)

            # Se tem inversão, marcar como usada
            if tem_inversao:
                inv_id = inversao.get("id") if isinstance(inversao, dict) else (inversao[0] if inversao else None)
                cursor.execute(
                    "UPDATE inversoes SET used = 1, fixture_id = %s WHERE id = %s",
                    (fixture_id, inv_id)
                )
                logging.info(f"🔄 Inversão ATIVA para usuário {user_id} no jogo {fixture_id}")

            pontos_base_vitoria = (win_pts * 2) if (acertou_normal and bonus_minoria) else win_pts

            # Aplicar pontuação via função central
            try:
                processar_aposta(user_id, fixture_id, resultado_final, pontos_base_vitoria, perda_base=lose_pts, tem_inversao=tem_inversao)
                apostas_processadas += 1
                logging.debug(f"✅ Pontuação aplicada para usuário {user_id}")
            except Exception as e:
                logging.error(f"❌ Erro ao processar aposta de {user_id}: {e}", exc_info=True)

            # Mensagem DM (usar acertou_normal para mostrar resultado real)
            if acertou_normal:
                multiplicador = 6 if modo_clown == 1 else 1
                pontos_preview = pontos_base_vitoria * multiplicador

                try:
                    embed = discord.Embed(
                        title="<a:302229champagne:1454983960605233273> APOSTA CERTA!",
                        description=(
                            f"Você garantiu **+{pontos_preview} pontos"
                            + (" 🎭 **Clown Bet 6x**" if modo_clown == 1 else "")
                            + (" (bônus de minoria)" if pontos_base_vitoria == (win_pts * 2) else "")
                            + (" 🔄 (invertido)" if tem_inversao else "")
                            + "!**"
                        ),
                        color=discord.Color.green()


                    )

                    embed.add_field(
                        name="🏟️ Partida",
                        value=f"`{casa} x {fora}`",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🏆 Resultado",
                        value=resultado_texto,
                        inline=False
                    )
                    
                    info = get_estadio_time_casa(casa)
                    logging.info(f"🏟️ Info estádio para {casa}: {info}")
                    
                    if info["estadio"] != "Estádio indefinido":
                        embed.add_field(
                            name="🏟️ Estádio",
                            value=info["estadio"],
                            inline=False
                        )
                    
                    if info["imagem"]:
                        embed.set_image(url=info["imagem"])
                        logging.info(f"🖼️ Imagem do estádio adicionada: {info['imagem']}")
                    
                    embed.add_field(
                        name="📊 Ações",
                        value=(
                            "<:apchikabounce:1408193721907941426> **!meuspontos**\n"
                            "<a:9612_aMCenchantedbook:1449948971916202125> **!info**\n"
                           "<a:522143costco:1473869986773733396> **!loja** compre comemoração, caixa surpresa vip e mais!\n"
                            "<a:17952trophycoolbrawlstarspin:1457784734074535946> **!conquistas**"
                        ),
                        inline=False
                    )

                    
                    
                    mensagens_pv.append((user_id, embed))
                    logging.info(f"✅ Embed de acerto criada para usuário {user_id}")
                    
                except Exception as e:
                    logging.error(f"❌ Erro ao criar embed de acerto para usuário {user_id}: {e}")
                    # Criar embed simples sem arena
                    embed_simples = discord.Embed(
                        title="<a:302229champagne:1454983960605233273> APOSTA CERTA!",
                        description=f"Você garantiu **+{pontos_preview} pontos**!",
                        color=discord.Color.green()
                    )
                    mensagens_pv.append((user_id, embed_simples))
                    logging.debug(f"✅ Fallback: Embed simples criado para usuário {user_id}")

            else:
                multiplicador = 4 if modo_clown == 1 else 1
                pontos_preview = lose_pts * multiplicador

                try:
                    embed = discord.Embed(
                        title="<:43513absolutelydrained:1454984081438674954> Aposta Errada",
                        description=(
                            f"Você perdeu **{pontos_preview}** pontos"
                            + (" <:77240skullclown:1467579389095968789> **Clown Bet 4x**" if modo_clown == 1 else "")
                            + (" 🔄 (invertido)" if tem_inversao and acertou_normal else "")
                        ),
                        color=discord.Color.red()
                    )

                    embed.add_field(
                        name="🏟️ Partida",
                        value=f"`{casa} x {fora}`",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🏆 Resultado",
                        value=resultado_texto,
                        inline=False
                    )
                    
                    info = get_estadio_time_casa(casa)
                    logging.info(f"🏟️ Info estádio para {casa}: {info}")
                    
                    if info["estadio"] != "Estádio indefinido":
                        embed.add_field(
                            name="🏟️ Estádio",
                            value=info["estadio"],
                            inline=False
                        )
                    
                    if info["imagem"]:
                        embed.set_image(url=info["imagem"])
                        logging.info(f"🖼️ Imagem do estádio adicionada: {info['imagem']}")

                    embed.add_field(
                        name="📊 Comandos",
                        value=(
                            "<a:6582red:1449949837763154081> **!meuspontos**\n"
                            "<a:9612_aMCenchantedbook:1449948971916202125> **!info**\n"
                            "<a:522143costco:1473869986773733396> **!loja** compre comemoração, caixa surpresa vip e mais!"
                        ),
                        inline=False
                    )

                    mensagens_pv.append((user_id, embed))
                    logging.info(f"✅ Embed de erro criada para usuário {user_id}")
                    
                except Exception as e:
                    logging.error(f"❌ Erro ao criar embed de erro para usuário {user_id}: {e}")
                    # Criar embed simples
                    embed_simples = discord.Embed(
                        title="<:43513absolutelydrained:1454984081438674954> Aposta Errada",
                        description=f"Você perdeu **{pontos_preview} pontos**!",
                        color=discord.Color.red()
                    )
                    mensagens_pv.append((user_id, embed_simples))
                    logging.debug(f"✅ Fallback: Embed simples criado para usuário {user_id}")

        # Enviar embed final no canal de jogos
        logging.info(f"📨 Preparando embed final e DMs para {len(mensagens_pv)} usuários...")
        nome_casa = MAPEAMENTO_TIMES.get(casa.lower(), casa.lower()).replace(" ", "_")
        nome_fora = MAPEAMENTO_TIMES.get(fora.lower(), fora.lower()).replace(" ", "_")
        emoji_casa = EMOJI_TIMES.get(nome_casa, "🔵")
        emoji_fora = EMOJI_TIMES.get(nome_fora, "🔴")

        embed_final = discord.Embed(
            title=f"🏁 Fim de jogo — {casa} x {fora}",
            description=f"Placar final: {emoji_casa} **{casa}** {gols_casa} ┃ {gols_fora} **{fora}** {emoji_fora}",
            color=discord.Color.dark_red()
        )
        embed_final.set_footer(text="Obrigado por participar das apostas!")

        canal = bot.get_channel(CANAL_JOGOS_ID)
        if canal:
            try:
                await canal.send(embed=embed_final)
                logging.info(f"📣 Embed final enviado para canal {CANAL_JOGOS_ID}")
            except Exception as e:
                logging.error(f"❌ Erro ao enviar embed final: {e}", exc_info=True)
                if ctx:
                    await ctx.send(f"❌ Erro ao enviar embed final: {e}")
        else:
            logging.error(f"❌ Canal de jogos (ID: {CANAL_JOGOS_ID}) não encontrado!")
            if ctx:
                await ctx.send(f"❌ Canal de jogos (ID: {CANAL_JOGOS_ID}) não encontrado!")

        # Enviar DMs para usuários
        dms_enviadas = 0
        for user_id, msg in mensagens_pv:
            usuario = bot.get_user(int(user_id))
            if not usuario:
                try:
                    usuario = await bot.fetch_user(int(user_id))
                except Exception:
                    usuario = None

            if usuario:
                try:
                    # Verificar se msg é um Embed antes de enviar
                    if isinstance(msg, discord.Embed):
                        await usuario.send(embed=msg)
                        dms_enviadas += 1
                        logging.debug(f"💌 DM com embed enviado para usuário {user_id}")
                    else:
                        await usuario.send(msg)
                        dms_enviadas += 1
                        logging.debug(f"💌 DM com texto enviado para usuário {user_id}")
                except Exception as e:
                    logging.error(f"❌ Erro ao enviar DM para usuário {user_id}: {e}")
                    if ctx:
                        await ctx.send(f"❌ Erro ao enviar DM para usuário {user_id}: {e}")
            else:
                logging.warning(f"⚠️ Usuário {user_id} não encontrado para enviar DM")
        logging.info(f"💌 {dms_enviadas}/{len(mensagens_pv)} DMs enviadas com sucesso")

        # Marcar como processado com sucesso apenas ao final
        processado_com_sucesso = True
        logging.info(f"🎉 ===== JOGO {fixture_id} PROCESSADO COM SUCESSO =====")
        logging.info(f"   Apostas: {apostas_processadas} | DMs: {dms_enviadas} | Resultado: {resultado_final}")
        logging.info(f"=============================================")
        return {'processado': True, 'mensagem': f"Jogo {fixture_id} processado com sucesso!", 'erro': None}

    except Exception as e:
        error_msg = f"Erro ao processar jogo {fixture_id}: {e}"
        logging.error(error_msg, exc_info=True)
        if ctx and not automatico:
            await ctx.send(f"❌ {error_msg}")
        return {'processado': False, 'mensagem': error_msg, 'erro': str(e)}
    
    finally:
        # 🔥 Marca como processado - GARANTIDO mesmo com erros
        if conn and cursor and processado_com_sucesso:
            try:
                cursor.execute("UPDATE jogos SET processado = 1, finalizado = 1 WHERE fixture_id = %s", (fixture_id,))
                conn.commit()
                logging.info(f"✅ Jogo {fixture_id} marcado como PROCESSADO=1, FINALIZADO=1 no banco.")
            except Exception as e:
                logging.error(f"❌ Erro ao marcar jogo {fixture_id} como finalizado: {e}", exc_info=True)
            finally:
                if cursor:
                    try:
                        cursor.close()
                        logging.debug(f"🔌 Cursor fechado (processado_com_sucesso=True)")
                    except Exception as e:
                        logging.error(f"❌ Erro ao fechar cursor: {e}")
                if conn:
                    try:
                        conn.close()
                        logging.debug(f"🔌 Conexão fechada (processado_com_sucesso=True)")
                    except Exception as e:
                        logging.error(f"❌ Erro ao fechar conexão: {e}")
        elif conn and cursor:
            # Se não foi bem sucedido, ainda fecha a conexão
            logging.warning(f"⚠️ Encerrando fixture {fixture_id} sem marcar como processado (erro ocorreu)")
            try:
                if cursor:
                    cursor.close()
                    logging.debug(f"🔌 Cursor fechado (com erro)")
            except Exception as e:
                logging.error(f"❌ Erro ao fechar cursor: {e}")
            try:
                if conn:
                    conn.close()
                    logging.debug(f"🔌 Conexão fechada (com erro)")
            except Exception as e:
                logging.error(f"❌ Erro ao fechar conexão: {e}")



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

        cursor.close()
        conn.close()

        processados = 0
        erros = 0

        for fx in alvos:
            resultado = await processar_jogo(fx, ctx=ctx, automatico=False)
            if resultado['processado']:
                processados += 1
            else:
                erros += 1
                if resultado['erro'] != 'not_finished':  # Não mostrar erro de jogo não finalizado
                    await ctx.send(resultado['mensagem'])

        if processados == 0:
            await ctx.send(" Nenhum jogo foi processado.")
        elif processados == 1:
            await ctx.send(" 1 jogo finalizado manualmente. Pontuações aplicadas.")
            logging.info("1 jogo finalizado manualmente. Pontuações aplicadas.")
        else:
            await ctx.send(f" {processados} jogos finalizados manualmente. Pontuações aplicadas.")
            logging.info(f"{processados} jogos finalizados manualmente. Pontuações aplicadas.")

    except Exception as e:
        await ctx.send(f" Erro ao finalizar jogos: {e}")
        logging.error(f"Erro ao finalizar jogos: {e}")
        


@tasks.loop(minutes=20)
async def verificar_jogos_automaticamente():
    """Loop automático que verifica e processa jogos finalizados a cada 12 minutos"""
    # Só funciona se a API estiver ativa via !apistart
    if not acompanhando:
        return
        
    try:
        logging.info("🔄 Iniciando verificação automática de jogos...")

        conn = conectar_futebol()
        cursor = conn.cursor(dictionary=True)  # use dictionary=True para consistência

        # Buscar jogos pendentes
        cursor.execute("SELECT fixture_id, home, away FROM jogos WHERE finalizado = 0")
        jogos_pendentes = cursor.fetchall()

        cursor.close()
        conn.close()

        if not jogos_pendentes:
            logging.info("✅ Nenhum jogo pendente encontrado para verificação automática.")
            return  # Nenhum jogo pendente

        processados = 0
        erros = 0
        nao_finalizados = 0

        for jogo in jogos_pendentes:
            fixture_id = jogo["fixture_id"]
            home = jogo["home"]
            away = jogo["away"]

            logging.info(f"🎯 Processando jogo {fixture_id}: {home} x {away}")
            resultado = await processar_jogo(fixture_id, ctx=None, automatico=True)

            if resultado['processado']:
                processados += 1
                logging.info(f"✅ Jogo {fixture_id} processado com sucesso!")
            elif resultado['erro'] == 'not_finished':
                nao_finalizados += 1
                logging.info(f"⏳ Jogo {fixture_id} ainda não finalizado")
            else:
                erros += 1
                logging.error(f"❌ Erro no jogo {fixture_id}: {resultado['mensagem']}")

        # Log final similar ao comando manual
        if processados == 0:
            logging.info("Nenhum jogo foi processado automaticamente.")
        elif processados == 1:
            logging.info("1 jogo finalizado automaticamente. Pontuações aplicadas.")
        else:
            logging.info(f"{processados} jogos finalizados automaticamente. Pontuações aplicadas.")

        logging.info(f"📊 Resumo: {processados} processados, {nao_finalizados} não finalizados, {erros} erros")

    except Exception as e:
        logging.error(f"❌ Erro no loop automático de verificação: {e}")
        import traceback
        logging.error(f"❌ Traceback completo: {traceback.format_exc()}")


@verificar_jogos_automaticamente.before_loop
async def before_verificar_jogos():
    """Aguarda o bot estar pronto antes de iniciar o loop"""
    await bot.wait_until_ready()
    logging.info("Loop automático de verificação de jogos iniciado!")


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
        await ctx.send("Apenas o melhorzin que tá tendo pode usar")
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


    embed.add_field(
        name="🎖️ Conquistas",
        value=(
            "`!conquistas` - Mostra suas conquistas"  
        ),
        inline=False
    )

    # Comandos de apostas/loja
    embed.add_field(
        name="🎲 Apostas, Pontos e Loja",
        value=(
            "`!comprar <nome>` - Compra um item da loja usando seus pontos.\n"
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
            "`!torcedores` - Mostra os torcedores do time informado.\n"
            "`!sair_time` - Sai do seu time atual."
            

        ),
        inline=False
    )

    embed.add_field(
        name="🎰 Melhores apostadores",
        value=(
            "`!top_apostas` - Mostra os 5 melhores apostadores do servidor.\n"
             "`!bad_apostas` - Mostra os 5 piores apostadores do servidor."
            
            
        ),
        inline=False
    )

    embed.add_field(
        name="🔥 Sistema de Fogo (Acertos Consecutivos)",
        value=(
            "`!fogo` - Mostra seus acertos consecutivos atuais e maior sequência.\n"
            "`!top_fogos` - Ranking dos maiores fogos do servidor.\n"
            "_Acertos contam para apostas de futebol e anime!_"
        ),
        inline=False
    )

    await ctx.send(embed=embed)
    logging.info(f"Usuário {ctx.author} solicitou a lista de comandos.")

#LISTAR OS 5 MAIORES COM PONTUACOES DE APOSTAS
class PaginaRanking(discord.ui.View):
    def __init__(self, top, autor):
        super().__init__(timeout=120)
        self.top = top
        self.pagina = 0
        self.por_pagina = 5
        self.autor = autor
        self.atualizar_estado_botoes()

    def atualizar_estado_botoes(self):
        if hasattr(self, 'btn_anterior'):
            self.btn_anterior.disabled = self.pagina == 0
        if hasattr(self, 'btn_proximo'):
            self.btn_proximo.disabled = (self.pagina + 1) * self.por_pagina >= len(self.top)

    async def atualizar_embed(self, destino):
        inicio = self.pagina * self.por_pagina
        fim = inicio + self.por_pagina
        ranking_pagina = self.top[inicio:fim]

        logging.info(f"📊 Atualizando página de ranking: página {self.pagina+1}, mostrando {len(ranking_pagina)} usuários")

        embed = discord.Embed(
            title="<a:30348trophyfixed:1457473332843778220> Top Apostadores",
            description="Ranking completo do sistema de apostas",
            color=discord.Color.gold()
        )

        medalhas = ["<a:17952trophycoolbrawlstarspin:1457784734074535946>", "🥈", "🥉", "🏅", "🏅"]

        texto = ""
        for i, row in enumerate(ranking_pagina):
            # caso seja dict (dictionary=True no cursor) ou tupla
            if isinstance(row, dict):
                nome = row.get("nome_discord")
                pontos = row.get("pontos")
            else:
                nome, pontos = row

            posicao = inicio + i + 1
            medalha = medalhas[posicao-1] if posicao <= len(medalhas) else "🏅"
            texto += f"{medalha} **{nome}** — `{pontos} pontos`\n"
            logging.info(f"📊 Ranking #{posicao}: {nome} - {pontos} pontos")

        embed.add_field(name=f"📊 Página {self.pagina+1}", value=texto, inline=False)
        embed.set_footer(text=f"Solicitado por {self.autor.display_name}")

        # envia dependendo do tipo de destino
        if isinstance(destino, discord.Interaction):
            try:
                await destino.response.edit_message(embed=embed, view=self)
            except discord.errors.InteractionResponded:
                # caso já tenha respondido
                if destino.message:
                    await destino.followup.edit_message(message_id=destino.message.id, embed=embed, view=self)
                else:
                    await destino.followup.send(embed=embed, view=self)
        elif isinstance(destino, discord.ext.commands.Context):
            await destino.send(embed=embed, view=self)

    # ================= BOTÕES =================
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.primary)
    async def btn_anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina -= 1
        self.atualizar_estado_botoes()
        await self.atualizar_embed(interaction)

    @discord.ui.button(label="➡️ Próximo", style=discord.ButtonStyle.primary)
    async def btn_proximo(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina += 1
        self.atualizar_estado_botoes()
        await self.atualizar_embed(interaction)

# ================= COMANDO =================
@bot.command()
async def top_apostas(ctx):
    async with ctx.typing():
        conn = conectar_futebol()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT nome_discord, pontos FROM pontuacoes ORDER BY pontos DESC")
        top = cursor.fetchall()
        cursor.close()
        conn.close()

        if not top:
            return await ctx.send("⚠️ Nenhum usuário possui pontos.")

        logging.info(f"📊 Top apostas solicitado por {ctx.author.name}, total de {len(top)} usuários")
        view = PaginaRanking(top, ctx.author)
        await view.atualizar_embed(ctx)

@bot.command()
async def bad_apostas(ctx):
    async with ctx.typing():  # Mostra que o bot está digitando
        conn = conectar_futebol()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nome_discord, pontos FROM pontuacoes ORDER BY pontos ASC LIMIT 5"
        )
        bottom = cursor.fetchall()
        cursor.close()
        conn.close()

        if not bottom:
            return await ctx.send("⚠️ Nenhum usuário possui pontos.")

        embed = discord.Embed(
            title="💩 Top 5 Menos Apostadores",
            description="Usuários com menos pontos no sistema de apostas",
            color=discord.Color.dark_red()
        )

        ranking = ""
        medalhas = [
            "💀",  # 1º pior
            "🚑",
            "🥴",
            "🤡",
            "😵"
        ]

        for i, (nome, pontos) in enumerate(bottom):
            ranking += f"{medalhas[i]} **{nome}** — `{pontos} pontos`\n"

        embed.add_field(
            name="📉 Ranking Atual",
            value=ranking,
            inline=False
        )

        embed.set_footer(
            text=f"Solicitado por {ctx.author.display_name}"
        )

    # Envia o embed depois que o typing acaba
    await ctx.send(embed=embed)
    logging.info(f"Usuário {ctx.author} solicitou ver os 5 piores apostadores.")



CANAL_COMANDOS = 1380564680774385724

@bot.tree.command(name="dar_vip", description="Conceda VIP a um membro do servidor")
@app_commands.describe(membro="Membro que receberá VIP", duracao="Duração do VIP (ex: 30d, 2m, 1y)")
async def dar_vip_slash(interaction: discord.Interaction, membro: discord.Member, duracao: str):
    # Verifica permissão de administrador
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você precisa ser administrador para usar este comando.", ephemeral=True)
        return

    cargo_vip = discord.utils.get(interaction.guild.roles, name="Jinxed Vip")
    if not cargo_vip:
        await interaction.response.send_message("❌ Cargo 'Jinxed Vip' não encontrado.", ephemeral=True)
        return

    # Validação de formato da duração
    duracao = duracao.strip().lower()
    if len(duracao) < 2 or not duracao[:-1].isdigit() or duracao[-1] not in {"d", "m", "y"}:
        await interaction.response.send_message("❌ Formato inválido! Use 30d, 2m ou 1y.", ephemeral=True)
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
        await interaction.response.send_message(f"❌ {membro.display_name} já possui o cargo VIP.", ephemeral=True)
        return

    await membro.add_roles(cargo_vip, reason="Concessão de VIP")

    # Registro no banco de dados
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
    except Exception as e:
        logging.error(f"Erro ao registrar VIP no banco: {e}")

    # Envia DM ao usuário
    try:
        await membro.send(f"<:Jinx_Watching:1390380695712694282> Você recebeu VIP por {duracao}!")
    except:
        pass

    # Mensagem de confirmação
    await interaction.response.send_message(f"<:Jinx_Watching:1390380695712694282> {membro.display_name} agora é VIP por {duracao}.")
    logging.info(f"VIP concedido com sucesso: {membro.display_name} ({membro.id}) por {duracao}")

    # Conceder conquista "Coroado" automaticamente
    try:
        await processar_conquistas(
            member=interaction.user,
            mensagens_semana=0,  # valores padrão
            maior_streak=0,
            fez_doacao=False,
            tem_vip=True,  # ACABOU DE GANHAR VIP
            tempo_em_call=0,
            mencionou_miisha=False,
            tocou_musica=False,
            mencoes_bot=0
        )
        logging.info(f"{interaction.user.name} acabou de ganhar a conquista")
    except Exception as e:
        logging.error(f"Erro ao conceder conquista coroado para {membro.display_name}: {e}")



@bot.tree.command(name="remover_vip", description="Remove o cargo VIP de um membro.")
@app_commands.checks.has_permissions(administrator=True)
async def remover_vip(interaction: discord.Interaction, membro: discord.Member):

    cargo_vip = discord.utils.get(interaction.guild.roles, name="Jinxed Vip")
    if not cargo_vip:
        await interaction.response.send_message(
            "❌ O cargo **Jinxed Vip** não foi encontrado no servidor.",
            ephemeral=True
        )
        return

    if cargo_vip not in membro.roles:
        await interaction.response.send_message(
            f"<:jinxedola:1390368939380445225> {membro.display_name} não possui VIP.",
            ephemeral=True
        )
        return

    try:
        await membro.remove_roles(cargo_vip)

        conexao = conectar_vips()
        cursor = conexao.cursor()
        cursor.execute(
            "DELETE FROM vips WHERE id = %s",
            (membro.id,)
        )
        conexao.commit()
        cursor.close()
        conexao.close()

        await interaction.response.send_message(
            f"<:Jinx_Watching:1390380695712694282> VIP removido de {membro.mention}.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.response.send_message(
            "❌ Não consegui remover o VIP do banco de dados.",
            ephemeral=True
        )
        logging.error(f"Erro ao remover VIP: {e}")
        

@bot.tree.command(name="entregar", description="Entregar pontos de doação a um usuário")
@app_commands.describe(
    membro="Selecione o usuário que vai receber os pontos",
    valor="Escolha o valor da doação"
)
@app_commands.choices(valor=[
    app_commands.Choice(name="R$ 5", value=5),
    app_commands.Choice(name="R$ 10", value=10),
    app_commands.Choice(name="R$ 25", value=25),
    app_commands.Choice(name="R$ 50", value=50),
])
async def entregar(interaction: discord.Interaction, membro: discord.Member, valor: int):
    if interaction.user.id != MEU_ID:
        logging.warning(f"{interaction.user} tentou usar o comando entregar sem permissão.")
        return await interaction.response.send_message(
            "Apenas o brabo pode usar <a:1199777523261775963:1451401949667655730>",
            ephemeral=True
        )

    tabela_conversao = {5: 300, 10: 700, 25: 2000, 50: 6000}
    pontos = tabela_conversao[valor]

    try:
        # Adiciona pontos
        adicionar_pontos_db(membro.id, pontos)

        # Cargo de apoiador geral
        cargo_doacao = discord.utils.get(interaction.guild.roles, name="Apoiador Dev")
        status_cargo = ""

        if cargo_doacao:
            if cargo_doacao not in membro.roles:
                await membro.add_roles(cargo_doacao)
                status_cargo = (
                    f"\n<a:PoggersRow:1449578774004895857> "
                    f"{membro.mention} agora possui o cargo **{cargo_doacao.name}** "
                    f"como agradecimento pela doação de **R$ {valor},00**! 🙏"
                )
            else:
                status_cargo = f"\nℹ️ Você já possui o cargo **{cargo_doacao.name}**."
        else:
            status_cargo = "\n⚠️ Cargo **Apoiador Dev** não encontrado."

        await interaction.response.send_message(
            f"<a:105382toro:1454984271897825405> {membro.mention} recebeu **{pontos} pontos** por doar **R$ {valor},00**!"
            f"{status_cargo}"
        )

        logging.info(f"{membro} recebeu {pontos} pontos por doar R$ {valor},00.")

        # Registrar doação de R$50 no banco
        if valor == 50:
            try:
                conn_do = conectar_futebol()
                cur_do = conn_do.cursor()
                cur_do.execute(
                    """
                    INSERT INTO loja_pontos 
                    (user_id, item, pontos_gastos, data_compra, ativo)
                    VALUES (%s, %s, %s, %s, 1)
                    """,
                    (membro.id, 'doacao_50', pontos, datetime.utcnow())
                )
                conn_do.commit()
                cur_do.close()
                conn_do.close()
            except Exception as e:
                logging.error(f"Erro ao registrar doação de 50 no banco: {e}")

        # Processa conquistas
        await processar_conquistas(
            membro,
            mensagens_semana=0,
            maior_streak=0,
            fez_doacao=(valor == 50),
            tem_vip=False,
            tempo_em_call=0,
            mencionou_miisha=False,
            tocou_musica=False,
            mencoes_bot=0,
            azarao_vitoria=False
        )

        embed = discord.Embed(
            title="🙏 Obrigado pela Doação!",
            description=f"<a:74731moneywave:1454721352698433730> Você recebeu **{pontos} pontos** por doar **R$ {valor},00** ao desenvolvedor!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Usuário", value=membro.mention, inline=True)
        await membro.send(embed=embed)

    except Exception as e:
        await interaction.followup.send("❌ Erro ao entregar pontos. Verifique os logs.", ephemeral=True)
        logging.error(f"Erro ao entregar pontos para {membro}: {e}")

    

@bot.tree.command(name="vip_list", description="Mostra a lista de VIPs ativos")
@app_commands.checks.has_permissions(administrator=True)
async def vip_list(interaction: discord.Interaction):
    await interaction.response.defer()  # Mostra carregando

    conn = None
    cursor = None
    try:
        conn = conectar_vips()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome_discord, data_inicio, data_fim FROM vips")
        vips = cursor.fetchall()

        if not vips:
            await interaction.followup.send("❌ Nenhum VIP registrado ainda.")
            return

        embed = discord.Embed(
            title="<:discotoolsxyzicon_6:1444750406763679764> Lista de VIPs Ativos",
            color=discord.Color.blue()
        )

        agora = datetime.now(timezone.utc)
        itens = []

        for id_vip, nome_discord, data_inicio, data_fim in vips:
            if data_inicio.tzinfo is None:
                data_inicio = data_inicio.replace(tzinfo=timezone.utc)
            if data_fim.tzinfo is None:
                data_fim = data_fim.replace(tzinfo=timezone.utc)

            restante = data_fim - agora
            ativo = restante.total_seconds() > 0
            dias = max(0, restante.days)
            horas = max(0, int((restante.total_seconds() % 86400) // 3600))
            itens.append((ativo, data_fim, nome_discord, data_inicio, dias, horas))

        itens.sort(key=lambda x: (not x[0], x[1]))

        for ativo, _, nome_discord, data_inicio, dias, horas in itens:
            status = "Ativo" if ativo else "Expirado"
            valor = (
                f"Início: `{data_inicio.strftime('%d/%m/%Y')}`\n"
                + (f"Restam: **{dias}d {horas}h**" if ativo else "Status: **Expirado**")
            )
            embed.add_field(name=f"{nome_discord} — {status}", value=valor, inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send("❌ Erro ao acessar o banco de dados.")
        logging.error(f"Erro vip_list: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

        
@bot.tree.command(
    name="bad_apostas",
    description="Veja os piores apostadores"
)
async def slash_bad_apostas(interaction: discord.Interaction):

    if interaction.channel.id != CANAL_PERMITIDO_ID:
        return await interaction.response.send_message(
            f"<:Jinxsip1:1390638945565671495> Este comando só pode ser usado no canal <#{CANAL_PERMITIDO_ID}>.",
            ephemeral=True
        )

    await interaction.response.defer()  # Mostra que o bot está pensando

    conn = conectar_futebol()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT nome_discord, pontos FROM pontuacoes ORDER BY pontos ASC LIMIT 5"
        )
        bad = cursor.fetchall()

        if not bad:
            return await interaction.followup.send(
                "⚠️ Nenhum usuário possui pontos.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="<a:1846_TaketheL:1457780626282385448> Top 5 Piores Apostadores",
            description="Quando o palpite é emoção e não razão…",
            color=discord.Color.red()
        )

        # Emojis temáticos com o primeiro como ambulância
        emojis = ["💀", "🚑", "🥴", "🤡", "😵"]
        ranking = ""

        for i, (nome, pontos) in enumerate(bad):
            ranking += f"{emojis[i]} **{nome}** — `{pontos} pontos`\n"

        embed.add_field(
            name="📉 Ranking Atual",
            value=ranking,
            inline=False
        )

        embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logging.error(f"Erro no slash_bad_apostas: {e}")
        await interaction.followup.send(
            "❌ Erro ao consultar ranking.",
            ephemeral=True
        )

    finally:
        cursor.close()
        conn.close()




@bot.command()
async def time(ctx, *, nome_time: str):
    if ctx.channel.id != CANAL_COMANDOS:
        return await ctx.send(
            "<:480700twinshout:1443957065230844066> Este comando pode ser usado apenas no canal <#1380564680774385724>."
        )

    logging.info(f"Alguém ({ctx.author}) tentou usar o comando time em um canal diferente ({ctx.channel.id}).")

    if not nome_time:
        return await ctx.send("<:Jinx_Watching:1390380695712694282> Desculpa, mas você precisa informar o nome do time")

    # Normalizar entrada
    nome_normalizado = nome_time.lower().strip()

    # Verificar no mapeamento
    if nome_normalizado not in MAPEAMENTO_TIMES:
        return await ctx.send("<:3894307:1443956354698969149> Desculpa, mas eu não reconheço esse time")

    time_chave = MAPEAMENTO_TIMES[nome_normalizado]

    # Display bonito (para Discord e banco)
    DISPLAY_NOMES = {
        "galo": "Atlético-MG",
        "sao paulo": "São Paulo",
        "atletico paranaense": "Athletico-PR",
        "vasco": "Vasco",
        "fluminense": "Fluminense",
        "vitoria": "Vitória",
        "gremio": "Grêmio",
        "ceara": "Ceará",
        "palmeiras": "Palmeiras",
        "flamengo": "Flamengo",
        "corinthians": "Corinthians",
        "cruzeiro": "Cruzeiro",
        "botafogo": "Botafogo",
        "bahia": "Bahia",
        "bragantino": "Bragantino",
        "fortaleza": "Fortaleza",
        "mirassol": "Mirassol",
        "internacional": "Internacional",
        "coritiba": "Coritiba",
        "remo": "Remo",
        "santos": "Santos"
    }

    nome_bonito = DISPLAY_NOMES.get(time_chave, time_chave.title())

    #------ Banco ------
    conn = conectar_futebol()
    cursor = conn.cursor()

    # Verificar se o usuário já tem um time registrado
    cursor.execute("SELECT time_normalizado FROM times_usuarios WHERE user_id = %s", (ctx.author.id,))
    resultado = cursor.fetchone()

    if resultado:
        cursor.close()
        conn.close()
        return await ctx.send(
            f"⚽ {ctx.author.mention}, você já escolheu um time (**{resultado[0]}**).\n"
            f"Use `!sair_time` para trocar."
        )

    # Inserir novo time com nome bonito
    cursor.execute("""
        INSERT INTO times_usuarios (user_id, time_normalizado)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE time_normalizado = VALUES(time_normalizado)
    """, (ctx.author.id, nome_bonito))

    conn.commit()
    cursor.close()
    conn.close()

    #------ Cargo ------
    # Remover cargos antigos
    for chave, role_id in ROLE_IDS_TIMES.items():
        cargo_antigo = ctx.guild.get_role(role_id)
        if cargo_antigo and cargo_antigo in ctx.author.roles:
            await ctx.author.remove_roles(cargo_antigo)

    # Adicionar cargo do time escolhido
    role_id = ROLE_IDS_TIMES.get(time_chave)
    if not role_id:
        return await ctx.send(f"❌ Cargo para o time **{nome_bonito}** não encontrado.")

    cargo = ctx.guild.get_role(role_id)
    if not cargo:
        return await ctx.send(f"❌ Cargo para o time **{nome_bonito}** não encontrado no servidor.")

    await ctx.author.add_roles(cargo)

    logging.info(f"Usuário {ctx.author} se registrou como torcedor do time {nome_bonito} (ID: {cargo.id}).")

    await ctx.send(
        f"<a:995589misathumb:1443956356846719119> {ctx.author.mention}, agora você está registrado como torcedor do **{nome_bonito}**!"
    )


@bot.command()
async def sair_time(ctx):
    if ctx.channel.id != CANAL_COMANDOS:
        return await ctx.send("<:480700twinshout:1443957065230844066> Este comando pode ser usado apenas no canal <#1380564680774385724>.")

    conn = conectar_futebol()
    cursor = conn.cursor()

    cursor.execute("SELECT time_normalizado FROM times_usuarios WHERE user_id = %s", (ctx.author.id,))
    resultado = cursor.fetchone()

    if not resultado:
        cursor.close()
        conn.close()
        return await ctx.send(f"❌ {ctx.author.mention}, você não possui um time registrado.")

    time_normalizado = resultado[0]
    cargo_nome = time_normalizado.title()

    # Remover cargo
    cargo = discord.utils.get(ctx.guild.roles, name=cargo_nome)
    if cargo in ctx.author.roles:
        await ctx.author.remove_roles(cargo)

    # Remover do banco
    cursor.execute("DELETE FROM times_usuarios WHERE user_id = %s", (ctx.author.id,))
    conn.commit()

    cursor.close()
    conn.close()

    await ctx.send(f"✅ {ctx.author.mention}, você saiu do time **{cargo_nome}**!")

@bot.command()
async def lista_times(ctx):
    if ctx.channel.id != CANAL_COMANDOS:
        return await ctx.send("<:480700twinshout:1443957065230844066> Este comando pode ser usado apenas no canal <#1380564680774385724>.")
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

    embed = discord.Embed(
        title="📋 Times Disponíveis",
        description="Escolha seu time usando o comando correspondente!",
        color=discord.Color.blue()
    )

    # 👉 Divide em grupos de 10 (ajuste se quiser)
    chunk_size = 10
    for i in range(0, len(times), chunk_size):
        grupo = times[i:i + chunk_size]
        linhas = "\n".join([f"{emoji_do_time(t)} | **{t.title()}**" for t in grupo])

        embed.add_field(
            name="⚽ Times",
            value=linhas,
            inline=True  # <- cria colunas
        )

    await ctx.send(embed=embed)
    logging.info(f"Usuário {ctx.author} solicitou a lista de times.")

# Mostrar os torcedores do servidor
async def gerar_embed_torcedores(guild):
    conn = conectar_futebol()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT user_id, time_normalizado FROM times_usuarios")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        return None

    # Organizar torcedores por time
    torcedores = {}
    for user_id, time_normalizado in rows:
        torcedores.setdefault(time_normalizado, []).append(user_id)

    embed = discord.Embed(
        title="🏟️ Torcedores por Time",
        color=discord.Color.blue()
    )

    itens = []
    for time, usuarios in torcedores.items():
        # Normaliza apenas para buscar emoji
        time_chave = MAPEAMENTO_TIMES.get(time.lower(), time.lower())
        emoji = EMOJI_TIMES.get(time_chave.replace(" ", "_")) or "⚽"
        mencoes = "\n".join(f"<@{uid}>" for uid in usuarios)
        itens.append((time, emoji, mencoes))  # time original do banco aqui

    # Ordena alfabeticamente pelo nome do time
    itens.sort(key=lambda x: x[0].lower())

    for display, emoji, mencoes in itens:
        embed.add_field(
            name=f"{emoji} | {display}",  # exibe o nome do banco
            value=mencoes,
            inline=False
        )

    return embed

@bot.command()
async def torcedores(ctx):
    embed = await gerar_embed_torcedores(ctx.guild)

    if not embed:
        return await ctx.send("Nenhum torcedor registrado no servidor.")

    await ctx.send(embed=embed)

@bot.event
async def on_member_remove(member):
    conn = None
    cursor = None
    try:
        conn = conectar_futebol()
        cursor = conn.cursor()

        # Deletar dados do usuário de outras tabelas
        cursor.execute("DELETE FROM times_usuarios WHERE user_id = %s", (member.id,))
        cursor.execute("DELETE FROM apostas WHERE user_id = %s", (member.id,))
        cursor.execute("DELETE FROM pontuacoes WHERE user_id = %s", (member.id,))

        # Inserir registro de saída no log_membros
        sql = "INSERT INTO log_membros (user_id, user_name, evento, data_evento) VALUES (%s, %s, %s, %s)"
        valores = (member.id, str(member), 'SAIU', datetime.now(timezone.utc))
        cursor.execute(sql, valores)

        conn.commit()
        logging.info(f"Usuário {member.id} removido do banco ao sair do servidor e registrado no log.")
    except Exception as e:
        logging.error(f"Erro ao remover o usuário do banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@bot.event
async def on_member_join(member):
    conn = None
    cursor = None
    try:
        conn = conectar_futebol()
        cursor = conn.cursor()

        # Inserir registro de entrada no log_membros
        sql = "INSERT INTO log_membros (user_id, user_name, evento, data_evento) VALUES (%s, %s, %s, %s)"
        valores = (member.id, str(member), 'ENTROU', datetime.now(timezone.utc))
        cursor.execute(sql, valores)

        conn.commit()
        logging.info(f"Usuário {member.id} entrou no servidor e foi registrado no log.")
    except Exception as e:
        logging.error(f"Erro ao registrar a entrada do usuário no banco de dados: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ----- CÓDIGO PARA VER TODOS OS COMANDOS ADMIN -----
@bot.tree.command(name="admin", description="Painel de comandos administrativos")
@commands.has_permissions(administrator=True)
async def admin_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛠️ Painel de Comandos Administrativos",
        description="Aqui estão todos os comandos disponíveis para administradores:",
        color=discord.Color.red()
    )

    embed.add_field(
        name="🔧 Administração Geral",
        value=(
            "**!resetar_jogo** — limpa as apostas de um jogo\n"
            "**!fixture_id** — busca informações de uma partida\n"
            "**!terminar_jogo** — finaliza e processa resultados\n"
            "**!resetar_mensagens** - reseta as mensagens\n"
        ),
        inline=False
    )

    embed.add_field(
        name="<:discotoolsxyzicon_6:1444750406763679764> Sistema VIP",
        value=(
            "**/dar_vip** — concede VIP ao usuário\n"
            "**/remover_vip** — remove VIP do usuário\n"
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
        name="💖 Doações & Aniversário",
        value=(
            "**!feliz_aniversario @usuario** — Envia mensagem especial de aniversário\n"
            "**!entregar @usuario <valor>** — Entrega pontos ao usuário após doação aprovada"
        ),
        inline=False
    )

    embed.add_field(
        name="📨 Utilidades",
        value=(
            "**!enviar_mensagem** — envia uma mensagem para um canal\n"
            "**!ticket** — gerencia tickets de suporte\n"
            "**!testjimbo** - Faz o jimbo aparecer na hora"
        ),
        inline=False
    )

    embed.set_footer(text="Use com responsabilidade. 😉")
    logging.info(f"Administrador {interaction.user} solicitou o painel de comandos administrativos.")

    await interaction.response.send_message(embed=embed)


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


# ============================================================
#                    SISTEMA DE DOAÇÕES
# ============================================================

# FUNÇÕES PARA PERSISTÊNCIA DE DOAÇÕES (MySQL)
# ============================================================

def salvar_mensagem_doacao(message_id, channel_id):
    """Salva a mensagem de doação no MySQL"""
    try:
        conn = conectar_vips()
        cursor = conn.cursor()
        
        # Cria tabela se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doacao_mensagem (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_message (message_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Limpa registros antigos (só pode existir 1)
        cursor.execute("DELETE FROM doacao_mensagem")
        
        # Insere novo registro
        cursor.execute(
            "INSERT INTO doacao_mensagem (message_id, channel_id) VALUES (%s, %s)",
            (message_id, channel_id)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Mensagem de doação salva: message_id={message_id}, channel_id={channel_id}")
        
    except Exception as e:
        logging.error(f"Erro ao salvar mensagem de doação: {e}")

def get_mensagem_doacao():
    """Recupera a mensagem de doação do MySQL"""
    try:
        conn = conectar_vips()
        cursor = conn.cursor()
        
        cursor.execute("SELECT message_id, channel_id FROM doacao_mensagem ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return {"message_id": result[0], "channel_id": result[1]}
        return None
        
    except Exception as e:
        logging.error(f"Erro ao buscar mensagem de doação: {e}")
        return None


MEU_ID = 428006047630884864

# View para botões de doação
class DoacaoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # View persistente

    @discord.ui.button(
        label="R$ 5,00",
        style=discord.ButtonStyle.secondary,
        emoji="5️⃣",
        custom_id="doacao_5"
    )
    async def doacao_5_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_doacao(interaction, 5)

    @discord.ui.button(
        label="R$ 10,00",
        style=discord.ButtonStyle.secondary,
        emoji="🔟",
        custom_id="doacao_10"
    )
    async def doacao_10_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_doacao(interaction, 10)

    @discord.ui.button(
        label="R$ 25,00",
        style=discord.ButtonStyle.secondary,
        emoji="💶",
        custom_id="doacao_25"
    )
    async def doacao_25_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_doacao(interaction, 25)

    @discord.ui.button(
        label="R$ 50,00",
        style=discord.ButtonStyle.primary,
        emoji="💰",
        custom_id="doacao_50"
    )
    async def doacao_50_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.processar_doacao(interaction, 50)

    async def processar_doacao(self, interaction: discord.Interaction, valor: int):
        user = interaction.user
        dono = await bot.fetch_user(MEU_ID)

        try:
            embed = discord.Embed(
                title="🔔 Interesse em Doação",
                description=f"O usuário {user.mention} demonstrou interesse em realizar uma doação.",
                color=discord.Color.green()
            )

            embed.add_field(
                name="💰 Valor Selecionado",
                value=f"R$ {valor},00",
                inline=True
            )

            embed.add_field(
                name="👤 Usuário",
                value=f"{user.mention}\n`ID: {user.id}`",
                inline=True
            )

            embed.add_field(
                name="⚠️ Ação Necessária",
                value=(
                    "Negociação pendente.\n"
                    "Entre em contato com o usuário para prosseguir com a doação."
                ),
                inline=False
            )

            embed.set_footer(text="Sistema de Doações")

            await dono.send(embed=embed)

            await interaction.response.send_message(
                f"💸 Obrigado pelo interesse! O dono foi notificado sobre sua doação de "
                f"**R$ {valor},00** e entrará em contato em breve.",
                ephemeral=True
            )

            logging.info(
                f"Usuário {user.display_name} ({user.id}) solicitou doação de R$ {valor},00"
            )

        except Exception as e:
            logging.error(f"Erro ao notificar doação: {e}")
            await interaction.response.send_message(
                "❌ Ocorreu um erro ao processar sua solicitação. "
                "Tente novamente mais tarde.",
                ephemeral=True
            )


# Mapeamento dos Emojis para Valores (mantido para compatibilidade)
EMOJIS_VALORES = {
    "5️⃣": 5,
    "🔟": 10,
    "💶": 25,
    "💰": 50
}

@bot.command()
@commands.has_permissions(administrator=True)
async def doacao(ctx):
    embed = discord.Embed(
        title="<a:93659pepemoneyrain:1457481044960739539> Sistema Oficial de Doações",
        description=(
            "**Apoie o servidor e ajude no crescimento dos nossos projetos!**\n"
            "Seu apoio mantém tudo funcionando, financia melhorias e permite que novas ideias virem realidade.\n\n"
            "👇 **Escolha abaixo um valor para contribuir**"
        ),
        color=discord.Color.green()
    )

    # Imagem de destaque
    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1254450666873688084/1448883575096082472/Inserir_um_titulo.png?ex=695150bb&is=694fff3b&hm=b00846bd71dfed73e2a0f30e8ff5533faecd8527bdb8a86741ab191ebba63a46&"
    )

    # Campo dos valores
    embed.add_field(
        name="<:diamond:1454722243467804817> Valores disponíveis",
        value=(
            "5️⃣ **R$ 5,00** — Apoio básico\n"
            "➜ Recebe **300 pontos**\n\n"

            "🔟 **R$ 10,00** — Apoio intermediário\n"
            "➜ Recebe **700 pontos**\n\n"

            "💶 **R$ 25,00** — Grande apoio ao servidor 💙\n"
            "➜ Recebe **2.000 pontos**\n\n"

            "💰 **R$ 50,00** — Apoio máximo ❤️\n"
            "➜ Recebe **6.000 pontos**\n"
            "<a:30348trophyfixed:1457473332843778220> Desbloqueia a conquista **TAKE MY MONEY**"
        ),
        inline=False
    )

    # Campo extra para deixar maior e mais estiloso
    embed.add_field(
        name="<:381258twotonedstaffids:1454722243467804817> Para onde vai sua doação?",
        value=(
            "• Manutenção dos bots\n"
            "• Novas funcionalidades\n"
            "• Suporte aos projetos do servidor\n"
        ),
        inline=False
    )

    embed.add_field(
        name="<a:143125redgemheart:1454722071618916530> Benefícios ao doar",
        value=(
            "• Recebe cargo especial de Apoiador\n"
            "• Prioridade em sugestões\n"
            "• Ajudar o criador e manter tudo ativo <:245370blobface:1445095629234901113>"
        ),
        inline=False
    )

    embed.set_footer(text="Meu pix:davidetroitff11@gmail.com" )

    # Enviando a embed com botões
    view = DoacaoView()
    mensagem = await ctx.send(embed=embed, view=view)

    salvar_mensagem_doacao(mensagem.id, ctx.channel.id)

    await ctx.send("💸 Sistema de doação configurado com sucesso!", delete_after=5)


@commands.has_permissions(administrator=True)
@bot.command()
async def entregar(ctx, membro: discord.Member, valor: int):
    if ctx.author.id != MEU_ID:
        logging.warning(f"{ctx.author} tentou usar o comando entregar sem permissão.")
        return await ctx.send("Apenas o brabo pode usar <a:1199777523261775963:1451401949667655730>")

    tabela_conversao = {
        5: 300,
        10: 700,
        25: 2000,
        50: 6000
    }

    if valor not in tabela_conversao:
        return await ctx.send("❌ Valor inválido. Use 5, 10, 25 ou 50.")

    pontos = tabela_conversao[valor]

    try:
        # Adiciona pontos
        adicionar_pontos_db(membro.id, pontos)

        # Cargo de apoiador geral
        cargo_doacao = discord.utils.get(ctx.guild.roles, name="Apoiador Dev")
        status_cargo = ""

        if cargo_doacao:
            if cargo_doacao not in membro.roles:
                await membro.add_roles(cargo_doacao)
                status_cargo = (
                    f"\n<a:PoggersRow:1449578774004895857> "
                    f"{membro.mention} agora possui o cargo **{cargo_doacao.name}** "
                    f"como agradecimento pela doação de **R$ {valor},00**! 🙏"
                )
            else:
                status_cargo = f"\nℹ️ Você já possui o cargo **{cargo_doacao.name}**."
        else:
            status_cargo = "\n⚠️ Cargo **Apoiador Dev** não encontrado."

        await ctx.send(
            f"<a:105382toro:1454984271897825405> {membro.mention} recebeu **{pontos} pontos** por doar **R$ {valor},00**!"
            f"{status_cargo}"
        )

        logging.info(f"{membro} recebeu {pontos} pontos por doar R$ {valor},00.")

        # Registrar doação de R$50 no banco (histórico)
        if valor == 50:
            try:
                conn_do = conectar_futebol()
                cur_do = conn_do.cursor()
                cur_do.execute(
                    """
                    INSERT INTO loja_pontos 
                    (user_id, item, pontos_gastos, data_compra, ativo)
                    VALUES (%s, %s, %s, %s, 1)
                    """,
                    (membro.id, 'doacao_50', pontos, datetime.utcnow())
                )
                conn_do.commit()
                cur_do.close()
                conn_do.close()
            except Exception as e:
                logging.error(f"Erro ao registrar doação de 50 no banco: {e}")

        
        await processar_conquistas(
            membro,
            mensagens_semana=0,
            maior_streak=0,
            fez_doacao=(valor == 50),
            tem_vip=False,
            tempo_em_call=0,
            mencionou_miisha=False,
            tocou_musica=False,
            mencoes_bot=0,
            azarao_vitoria=False
        )

        embed = discord.Embed(
            title="🙏 Obrigado pela Doação!",
            description=f"<a:74731moneywave:1454721352698433730> Você recebeu **{pontos} pontos** por doar **R$ {valor},00** ao desenvolvedor!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Usuário", value=membro.mention, inline=True)

        await membro.send(embed=embed)

    except Exception as e:
        await ctx.send("❌ Erro ao entregar pontos. Verifique os logs.")
        logging.error(f"Erro ao entregar pontos para {membro}: {e}")

# ============================================================
#                  COMANDO DE CONQUISTAS
# ============================================================


async def gerar_conquistas_embed(alvo: discord.Member, guild: discord.Guild):
    user_id = alvo.id
    
    

    try:
        # =========================
        # 🔹 FUNÇÕES AUXILIARES
        # =========================

        def format_progress_bar(current, total, length=15):
            if total is None or total == 0:
                return "[▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁] 0%"
            if current is None:
                current = 0
            progress = min(current / total, 1.0)
            filled = int(progress * length)
            return f"[{'█' * filled}{'▁' * (length - filled)}] {int(progress * 100)}%"

        def format_tempo(segundos):
            if segundos is None:
                return "0h 00m"
            try:
                h = int(segundos // 3600)
                m = int((segundos % 3600) // 60)
                return f"{h}h {m:02d}m"
            except (ValueError, TypeError):
                return "0h 00m"

        # =========================
        # 🔹 BUSCAS NO BANCO
        # =========================

        # --- VIP / ATIVIDADE ---
        con_vips = conectar_vips()
        cur_vips = con_vips.cursor(dictionary=True)

        semana_atual = datetime.now(timezone.utc).isocalendar()[1]

        cur_vips.execute(
            "SELECT mensagens FROM atividade WHERE user_id = %s AND semana = %s",
            (user_id, semana_atual)
        )
        mensagens_semana = (cur_vips.fetchone() or {}).get("mensagens", 0)

        cur_vips.execute(
            "SELECT id FROM vips WHERE id = %s AND data_fim > NOW()",
            (user_id,)
        )
        tem_vip = cur_vips.fetchone() is not None

        # --- FUTEBOL / APOSTAS ---
        con_fut = conectar_futebol()
        cur_fut = con_fut.cursor(dictionary=True)

        cur_fut.execute(
            "SELECT acertos_consecutivos FROM apostas WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        acertos_consecutivos = (cur_fut.fetchone() or {}).get("acertos_consecutivos", 0)

        cur_fut.execute(
            "SELECT MAX(maior_streak) as maior_streak FROM apostas WHERE user_id = %s",
            (user_id,)
        )
        maior_streak = (cur_fut.fetchone() or {}).get("maior_streak", 0)

        cur_fut.execute(
            """
            SELECT id FROM loja_pontos
            WHERE user_id = %s AND item = 'doacao_50' AND ativo = 1
            """,
            (user_id,)
        )
        fez_doacao = cur_fut.fetchone() is not None

        # --- TEMPO EM CALL ---
        tempo_em_call = calcular_tempo_total_em_call(user_id, guild.id) if guild else 0
        # Garantir que não seja None
        if tempo_em_call is None:
            tempo_em_call = 0

        # Fechar conexões
        cur_vips.close()
        con_vips.close()
        cur_fut.close()
        con_fut.close()

        # =========================
        # 🔹 VERIFICAR STATUS DOS CARGOS
        # =========================
        
        logging.info(f"Usuário {alvo.display_name} ({alvo.id}) solicitou conquistas. Verificando status dos cargos:")
        
        for key, conquista in CONQUISTAS.items():
            cargo = discord.utils.get(alvo.guild.roles, name=conquista["cargo"])
            if cargo:
                if cargo in alvo.roles:
                    logging.info(f"  ✅ {conquista['nome']}: Cargo '{cargo.name}' JÁ POSSUÍDO")
                else:
                    logging.info(f"  ❌ {conquista['nome']}: Cargo '{cargo.name}' NÃO POSSUÍDO")
            else:
                logging.warning(f"  ⚠️ {conquista['nome']}: Cargo '{conquista['cargo']}' NÃO ENCONTRADO no servidor")

        # =========================
        # 🔹 PROCESSAR CONQUISTAS
        # =========================

        desbloqueadas, bloqueadas = await processar_conquistas(
            alvo,
            mensagens_semana,
            maior_streak,
            fez_doacao,
            tem_vip,
            tempo_em_call=tempo_em_call,
            mencionou_miisha=False,
            tocou_musica=False,
            mencoes_bot=0,
            azarao_vitoria=False  
        )

        # =========================
        # 🔹 EMBED
        # =========================

        META_CALL = 180000  # 50 horas em segundos

        embed = discord.Embed(
            title=f"🏆 Conquistas • {alvo.display_name}",
            color=discord.Color.gold()
        )

        progresso_call = format_progress_bar(tempo_em_call, META_CALL)
        tempo_atual = format_tempo(tempo_em_call)
        tempo_restante = format_tempo(max(META_CALL - tempo_em_call, 0))
        
        logging.debug(
            "Valores para embed: tempo_em_call=%s, progresso_call=%s, tempo_atual=%s, tempo_restante=%s",
            tempo_em_call,
            progresso_call,
            tempo_atual,
            tempo_restante
        )

        embed.add_field(
            name="📞 Tempo em Call",
            value=(
                f"{progresso_call}\n"
                f"⏱️ **Atual:** {tempo_atual}\n"
                f"🎯 **Meta:** 50h\n"
                f"⏳ **Faltam:** {tempo_restante}"
            ),
            inline=False
        )

        embed.add_field(
            name="<a:30348trophyfixed:1457473332843778220> Conquistas Desbloqueadas",
            value="\n".join(desbloqueadas) if desbloqueadas else "Nenhuma ainda...",
            inline=False
        )

        embed.add_field(
            name="<:3799_padlock:1457528547089584393> Conquistas Bloqueadas",
            value="\n".join(bloqueadas) if bloqueadas else "Você desbloqueou tudo! 🎉",
            inline=False
        )

        embed.set_footer(text="Use !conquistas para acompanhar seu progresso")

        return embed


    except Exception as e:
        logging.exception(
            "Erro ao buscar conquistas de %s",
            alvo
        )
        return None

@bot.command()
async def conquistas(ctx, membro: discord.Member = None):

    alvo = membro or ctx.author

    embed = await gerar_conquistas_embed(alvo, ctx.guild)

    if not embed:
        return await ctx.send("❌ Ocorreu um erro ao buscar suas conquistas.")

    await ctx.send(embed=embed)
 

DONO_ID = 428006047630884864

@bot.command()
@commands.has_permissions(administrator=True)  
async def fuck_you(ctx, member: discord.Member = None):

    # IDs dos cargos
    CARGO_JINXED = 1387209956754718811
    CARGO_DONO = 1380564679256182926
    CARGO_MOD = 1381001740052201482

    if ctx.author.id != DONO_ID:
        return await ctx.send("🚫 Só o goat pode usar.")

    guild = ctx.guild

    cargo_jinxed = guild.get_role(CARGO_JINXED)
    cargo_dono = guild.get_role(CARGO_DONO)
    cargo_mod = guild.get_role(CARGO_MOD)

    # -----------------------------
    # CASO 1 → !fuck_you
    # -----------------------------
    if member is None:

        if cargo_jinxed in ctx.author.roles:
            return await ctx.send("⚠️ Você já possui esse cargo.")

        await ctx.author.add_roles(cargo_jinxed)
        await ctx.send(f"🔥 {ctx.author.mention} agora é Jinxed Dev.")

    # -----------------------------
    # CASO 2 → !fuck_you @membro
    # -----------------------------
    else:

        removidos = []

        if cargo_dono in member.roles:
            await member.remove_roles(cargo_dono)
            removidos.append("Dono")

        if cargo_mod in member.roles:
            await member.remove_roles(cargo_mod)
            removidos.append("Moderador")

        if not removidos:
            return await ctx.send("⚠️ O membro não possui Dono ou Moderador.")

        await ctx.send(
            f"💀 Cargos removidos de {member.mention}: {', '.join(removidos)}"
        )

usuarios_haha = set()

@bot.command()
@commands.has_permissions(administrator=True)
async def haha(ctx, member: discord.Member = None):

    if ctx.author.id != DONO_ID:
        return await ctx.send("🚫 Só o goat pode usar.")

    if member is None:
        return await ctx.send("⚠️ Use: !haha @membro")

    # Se já estiver marcado → remove (desativa)
    if member.id in usuarios_haha:
        usuarios_haha.remove(member.id)
        return await ctx.send(f"😇 {member.mention} foi libertado do modo haha.")

    # Se não estiver → ativa
    usuarios_haha.add(member.id)
    await ctx.send(f"😈 {member.mention} entrou no modo haha. Entrou em call = caiu.")

#==================COMANDO DE ANIVERSÁRIO==================
@bot.command(name="feliz_aniversario")
@commands.has_permissions(administrator=True)
async def feliz_aniversario(ctx, membro: discord.Member):
    cargo_id = 1388318496600883250
    cargo = ctx.guild.get_role(cargo_id)

    if cargo is None:
        await ctx.send("❌ O cargo **Aniversariante** não foi encontrado.")
        return

    if cargo not in membro.roles:
        await membro.add_roles(cargo, reason="Aniversário")

    # 🎂 Embed principal (mais limpo)
    embed = discord.Embed(
        title="🎉 Feliz Aniversário!",
        description=(
            "Hoje é um dia especial ✨\n\n"
            f"Parabéns, {membro.mention}! 💖\n"
            "Que seu dia seja repleto de alegria, saúde e muitas conquistas!"
        ),
        color=discord.Color.magenta()
    )

    embed.set_image(
        url="https://media.tenor.com/jw8D7cF8Q3sAAAAC/happy-birthday-happy-birthday-wishes.gif"
    )

    embed.set_footer(text="🎶 Parabéns da Xuxa")

    await ctx.send(embed=embed)

    await asyncio.sleep(3)
    await ctx.send("🎤 **Vamos cantar juntos!**")

    await asyncio.sleep(2)
    await ctx.send("🎶 Hoje vai ser uma festa")

    await asyncio.sleep(2)
    await ctx.send("🎶 Bolo e guaraná")

    await asyncio.sleep(2)
    await ctx.send("🎶 Muito doce pra você")

    await asyncio.sleep(2)
    await ctx.send("🎶 É o seu aniversário 🎂")

    await asyncio.sleep(3)
    await ctx.send("🎤 Vamos festejar e os amigos receber")

    await asyncio.sleep(2)
    await ctx.send(
        "🎶 Mil felicidades e amor no coração\n"
        "🎶 Que a sua vida seja sempre doce e emoção"
    )

    await asyncio.sleep(2)
    await ctx.send(
        "🎶 Bate, bate palma\n"
        "🎶 Que é hora de cantar"
    )

    await asyncio.sleep(2)
    await ctx.send(
        "🎶 Parabéns, parabéns!\n"
        "🎶 Hoje é o seu dia, que dia mais feliz"
    )

    await asyncio.sleep(2)
    await ctx.send(
        "🎶 Parabéns, parabéns!\n"
        "🎶 Cante novamente que a gente pede bis 🎉"
    )

    await asyncio.sleep(4)
    await ctx.send(
        "🎉 É big, é big, é big!\n"
        "🎉 É hora, é hora!\n"
        "🎉 Rá-tim-bum!"
    )
    await asyncio.sleep(15)
    await ctx.send(f"Com quem será, com quem será, com quem será que {membro.mention} vai casaaar, vai depender, vai depender, vai depender se o ciclano vai querer")
    #Remoção do cargp depois de 24 horas
    await asyncio.sleep(86400)
    
    await membro.remove_roles(cargo)
    logging.info(f"Remoção do cargo de aniversariante de {membro} depois das 24horas")
    membro.send("Feliz aniversáriooo, seu cargo de aniversáriante foi removido! Te desejo tudo de bom para hoje <3, vou te dar 30 pontos de presente 📬")

    adicionar_pontos_db(membro.id,30)
    


@bot.command()
async def troll(ctx, member: discord.Member):
    user_id = ctx.author.id
    agora = datetime.utcnow()
    
    # Verificar cooldown (5 minutos)
    if user_id in ultimo_troll:
        tempo_desde_ultimo = agora - ultimo_troll[user_id]
        if tempo_desde_ultimo < timedelta(minutes=5):
            return await ctx.send("⏳ Você deve esperar 5 minutos entre usos do comando !troll.")
    
    # Verificar se o usuário comprou o item
    con = conectar_futebol()
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM loja_pontos WHERE user_id = %s AND item = 'mute_jinxed' AND ativo = 1",
        (user_id,)
    )
    comprado = cur.fetchone()[0]
    if comprado == 0:
        con.close()
        return await ctx.send("❌ Você precisa comprar o item **Mute Jinxed** primeiro usando `!comprar mute_jinxed`.")
    
    # Verificar se o alvo é um bot
    if member.bot:
        con.close()
        return await ctx.send("🤖 Você não pode usar o comando !troll em bots.")
    
    # ID do cargo "mute"
    CARGO_MUTE_ID = 1445066766144376934
    
    # Tentar aplicar o cargo
    try:
        cargo_mute = ctx.guild.get_role(CARGO_MUTE_ID)
        if not cargo_mute:
            con.close()
            await ctx.send("❌ Cargo 'mute' não encontrado. Verifique o ID do cargo.")
            return
        
        # Verificar se o bot tem permissão para gerenciar cargos
        if ctx.guild.me.guild_permissions.manage_roles:
            # Verificar hierarquia apenas do bot (removido check do autor)
            if ctx.guild.me.top_role.position > member.top_role.position:
                # Consumir o item SÓ AGORA que sabemos que vai funcionar
                cur.execute(
                    "UPDATE loja_pontos SET ativo = 0 WHERE user_id = %s AND item = 'mute_jinxed' AND ativo = 1 LIMIT 1",
                    (user_id,)
                )
                con.commit()
                con.close()
                
                # Atualizar cooldown
                ultimo_troll[user_id] = agora
                
                await member.add_roles(cargo_mute, reason=f"Mute Jinxed usado por {ctx.author.name}")
                await ctx.send(f"🔇 **{member.mention} recebeu o cargo mute por 5 minutos!** (Usado por {ctx.author.mention})")
                
                # Remover cargo automaticamente após 5 minutos
                await asyncio.sleep(300)  # 5 minutos = 300 segundos
                try:
                    await member.remove_roles(cargo_mute, reason="Mute Jinxed expirou")
                    logging.info(f"Cargo mute removido de {member} após 5 minutos")
                except:
                    logging.error(f"Não foi possível remover cargo mute de {member}")
                    
            else:
                con.close()
                await ctx.send(f"🚫 **Não foi possível dar cargo mute para {member.mention}** (meu cargo é inferior ou igual ao dele)\n"
                              f"🤖 Peça para um admin subir meu cargo!")
        else:
            con.close()
            # Bot não tem permissão, enviar mensagem troll
            await ctx.send(f"🎭 **{ctx.author.mention} tentou dar cargo mute para {member.mention} mas o bot não tem permissão!**\n"
                          f"😏 Compre um bot melhor! 😈")
    except discord.Forbidden:
        con.close()
        await ctx.send(f"🚫 **Não foi possível dar cargo mute para {member.mention}** (cargo superior ou falta de permissão)\n"
                      f"😅 Tente em alguém com cargo inferior!")
    except Exception as e:
        con.close()
        await ctx.send(f"❌ Ocorreu um erro ao tentar dar cargo mute para {member.mention}: {str(e)[:50]}")
    
    # Enviar mensagem pública anunciando o uso
    try:
        anuncio_channel = ctx.guild.get_channel(CANAL_PERMITIDO_ID)
        if anuncio_channel:
            await anuncio_channel.send(f"🔇 **{ctx.author.mention} usou Mute Jinxed em {member.mention}!**")
            logging.info(f"Usuário {member} recebeu cargo mute com o comando troll")

    except:
        pass


CARTAS = [

    {
        "nome": "Five of Spades",
        "emoji": "<:5162playingcardspadesfive:1467682406415863836>",
        "pontos": (5, 10),
        "chance": 35
    },

    {
        "nome": "Six of Spades",
        "emoji": "<:4160playingcardspadessix:1467681547309289743>",
        "pontos": (10, 20),
        "chance": 25
    },

    {
        "nome": "Queen of Spades",
        "emoji": "<:4328playingcardspadesqueen:1467681538073297103>",
        "pontos": (25, 45),
        "chance": 18
    },

    {
        "nome": "King of Spades",
        "emoji": "<:9846playingcardspadesking:1467681531899412640>",
        "pontos": (45, 70),
        "chance": 12
    },

    {
        "nome": "Ace of Spades",
        "emoji": "<:3606playingcardspadesace:1467681600421630256>",
        "pontos": (80, 130),
        "chance": 7
    },

    {
        "nome": "Black Joker",
        "emoji": "🃏",
        "pontos": (-100, -40),
        "chance": 3
    },
]
# Jimbo
 
jimbo_ativo = False
jimbo_ja_apareceu_hoje = False
CANAL_JIMBO = 1380564680552091789
jimbo_lock = asyncio.Lock()  # Proteção contra race conditions

async def jimbo_scheduler():
    global jimbo_ja_apareceu_hoje  # ✅ TEM que ficar no topo

    await bot.wait_until_ready()
    logging.info("🃏 [JIMBO] Scheduler iniciado e aguardando horário permitido")

    while not bot.is_closed():
        try:
            agora = datetime.now()
            hora_atual = agora.time()

            from datetime import time as dt_time
            inicio = dt_time(12, 0)
            fim = dt_time(23, 59)
            meia_noite = dt_time(0, 0)
            horario_reset = dt_time(0, 30)

            logging.info(
                f"🃏 [JIMBO] Verificação - Hora atual: {hora_atual.strftime('%H:%M')} | Já apareceu: {jimbo_ja_apareceu_hoje} | Ativo: {jimbo_ativo}"
            )

            # Reset diário
            if inicio <= hora_atual <= fim:
                async with jimbo_lock:

                    if not jimbo_ativo and not jimbo_ja_apareceu_hoje:
                        logging.info(
                            f"🃏 [JIMBO] Horário permitido ({hora_atual.strftime('%H:%M')}) - Agendando aparição"
                        )

                        espera_minutos = random.randint(1, 420)
                        espera_total = espera_minutos * 60
                        espera_passada = 0
                        sleep_curto = 30

                        logging.info(
                            f"🃏 [JIMBO] Aguardando {espera_minutos} minutos para aparição..."
                        )

                        while espera_passada < espera_total:

                            if jimbo_ativo or jimbo_ja_apareceu_hoje:
                                logging.info("🃏 [JIMBO] Spawn cancelado durante espera")
                                break

                            await asyncio.sleep(sleep_curto)
                            espera_passada += sleep_curto

                        if not jimbo_ativo and not jimbo_ja_apareceu_hoje:
                            jimbo_ja_apareceu_hoje = True
                            await spawn_jimbo()
                        else:
                            logging.info(
                                "🃏 [JIMBO] Spawn cancelado - Jimbo já apareceu ou está ativo"
                            )
            else:
                await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"💥 Erro no scheduler Jimbo: {e}")
            await asyncio.sleep(60)

async def spawn_jimbo():
    global jimbo_ativo
    try:
        canal = bot.get_channel(CANAL_JIMBO)
        
        if not canal:
            logging.error(f"🃏 [JIMBO] Canal {CANAL_JIMBO} não encontrado!")
            async with jimbo_lock:
                jimbo_ativo = False
            return
        
        async with jimbo_lock:
            jimbo_ativo = True
    
        logging.info(f"🃏 [JIMBO] Spawn iniciado no canal #{canal.name}")
        
        embed = discord.Embed(
            title="🃏 JIMBO ESTÁ ATIVO!",
            description="Clique no botão antes que ele desapareça...",
            color=discord.Color.dark_purple()
        )

        embed.set_image(url="https://raw.githubusercontent.com/DaviDetroit/gifs-anime/main/ApresentacaoGif/supawork-4a536737e6d448f0b5555b0c67dec5a0.gif")

        view = JimboView(timeout=300)
        msg = await canal.send(embed=embed, view=view)
        view.message = msg
        logging.info(f"🃏 [JIMBO] Mensagem enviada com sucesso - Aguardando interação (5 min timeout)")
    except Exception as e:
        logging.error(f"💥 Erro ao fazer spawn de Jimbo: {e}")
        async with jimbo_lock:
            jimbo_ativo = False

class JimboView(discord.ui.View):
    def __init__(self, timeout=300):
        super().__init__(timeout=timeout)
        self.player = None
        self.message = None

    @discord.ui.button(label="Invocar Jimbo", style=discord.ButtonStyle.success, emoji="🃏")
    async def pegar_jimbo(self, interaction: discord.Interaction, button: discord.ui.Button):
        global jimbo_ativo
        if self.player is not None:
            logging.info(f"🃏 [JIMBO] {interaction.user.name} tentou invocar mas já foi invocado por {self.player.name}")
            return await interaction.response.send_message(
                "🚫 Jimbo já foi invocado por outra pessoa!",
                ephemeral=True
            )
        self.player = interaction.user
        async with jimbo_lock:
            jimbo_ativo = False
        logging.info(f"🃏 [JIMBO] {interaction.user.name} invocou o Jimbo! Iniciando jogo de cartas...")
        cartas_view = CartasView(interaction.user)
        await interaction.response.send_message(
            embed=cartas_view.embed_inicial,
            view=cartas_view
        )
        self.stop()

    async def on_timeout(self):
        global jimbo_ativo
        async with jimbo_lock:
            jimbo_ativo = False
        logging.info("🃏 [JIMBO] Timeout atingido - Jimbo desapareceu sem ser invocado")

        if self.message:
            try:
                await self.message.edit(
                    content="",
                    embed=discord.Embed(
                        description="🃏 Jimbo apareceu… olhou em volta… e foi embora.",
                        color=discord.Color.greyple()
                    ),
                    view=None
                )
            except Exception as e:
                logging.error(f"⚠️ Erro ao editar timeout de Jimbo: {e}")




def puxar_carta():
    """Puxa uma carta aleatória do baralho com validação."""
    if not CARTAS:
        raise ValueError("❌ [JIMBO] Lista de cartas vazia - impossível jogar!")
    
    pool = []
    for carta in CARTAS:
        chance = carta.get("chance", 0)
        if chance <= 0:
            logging.warning(f"⚠️ [JIMBO] Carta {carta['nome']} tem chance 0 ou negativa")
            continue
        pool.extend([carta] * chance)
    
    if not pool:
        raise ValueError("❌ [JIMBO] Nenhuma carta válida para sorteio - todas têm chance 0!")
    
    escolhida = random.choice(pool)
    
    # Validar campo de pontos
    if "pontos" not in escolhida or len(escolhida["pontos"]) != 2:
        raise ValueError(f"❌ [JIMBO] Carta {escolhida.get('nome', 'DESCONHECIDA')} tem pontos mal configurados")
    
    pontos = random.randint(*escolhida["pontos"])
    return escolhida, pontos

class CartasView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=60)
        if not player:
            raise ValueError("❌ [JIMBO] Jogador inválido para CartasView")
        self.player = player
        try:
            self.cartas = [puxar_carta() for _ in range(5)]
        except Exception as e:
            logging.error(f"💥 Erro ao gerar cartas: {e}")
            raise
        self.escolhidas = []
        self.pontos_totais = 0
        
        # Criar embed inicial
        cartas_display = []
        for i, (carta, pontos) in enumerate(self.cartas, 1):
            cartas_display.append(f"**Carta {i}:** ❓ (Pontos: {pontos})")
        
        self.embed_inicial = discord.Embed(
            title="🎴 Escolha 3 CARTAS",
            description="Clique nos botões abaixo para revelar suas cartas!\n\n" + "\n".join(cartas_display),
            color=discord.Color.purple()
        )
        self.embed_inicial.set_footer(text="⏱️ Você tem 60 segundos para escolher 3 cartas")
        
        # Adicionar botões das cartas
        for i in range(5):
            self.add_item(self._criar_button_carta(i))
        
        # Log inicial preventivo
        try:
            cartas_info = [f"{carta['nome']}({pontos})" for carta, pontos in self.cartas]
            logging.info(f"🃏 [JIMBO] Cartas geradas para {player.name} ({player.id}): {', '.join(cartas_info)}")
        except Exception as e:
            logging.error(f"❌ Erro ao gerar logs iniciais: {e}")

    def _criar_button_carta(self, index: int) -> discord.ui.Button:
        """Cria um botão para uma carta específica."""
        button = discord.ui.Button(
            label=f"Carta {index + 1}", 
            style=discord.ButtonStyle.secondary, 
            emoji="❓"
        )
        
        async def callback(interaction: discord.Interaction):
            await self.escolher(interaction, index)
        
        button.callback = callback
        return button

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message(
                "🚫 Apenas quem invocou o Jimbo pode interagir com estas cartas!",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Desativa os botões se o tempo acabar para evitar cliques fantasmas."""
        try:
            for item in self.children:
                item.disabled = True
            
            # Registrar timeout com informações úteis
            logging.warning(f"⏱️ [JIMBO] Timeout de {self.player.name} - Jogo expirado (escolheu {len(self.escolhidas)}/3)")
        except Exception as e:
            logging.error(f"💥 Erro em CartasView.on_timeout: {e}")
        finally:
            self.stop()

    async def escolher(self, interaction: discord.Interaction, index: int):
        try:
            # Validação de índice
            if not (0 <= index < len(self.children)):
                logging.warning(f"⚠️ [JIMBO] Índice inválido: {index}")
                return
            
            # Defer sem parâmetro update (que não existe) - apenas para reconhecer a interação
            # para que possamos editar a mensagem via message.edit() ou usar followup
            if not interaction.response.is_done():
                await interaction.response.defer()
            
            if index in self.escolhidas:
                await interaction.followup.send("🚫 Esta carta já foi revelada!", ephemeral=True)
                return

            # 1. Registrar a escolha
            self.escolhidas.append(index)
            carta, pontos = self.cartas[index]
            self.pontos_totais += pontos
            
            # 2. Atualizar o botão clicado
            button = self.children[index]
            button.disabled = True
            button.label = f"{carta['nome']}"
            button.emoji = carta['emoji']
            button.style = discord.ButtonStyle.success if pontos >= 0 else discord.ButtonStyle.danger

            # 3. Lógica de atualização da mensagem
            num_escolhidas = len(self.escolhidas)
            
            if num_escolhidas < 3:
                # Ainda escolhendo: atualiza o embed para mostrar o progresso
                embed_progresso = discord.Embed(
                    title="🎴 Escolha 3 CARTAS",
                    description=f"Você escolheu **{num_escolhidas}/3** cartas.\n\n{carta['emoji']} **{carta['nome']}**: {pontos:+d}\n\nContinue clicando!",
                    color=discord.Color.blue()
                )
                # Editar a mensagem que contém os botões (garante que o view é atualizado)
                try:
                    await interaction.message.edit(embed=embed_progresso, view=self)
                    logging.info(f"🃏 [JIMBO] {self.player.name} escolheu {carta['nome']} ({pontos:+d}).")
                except Exception as e:
                    logging.error(f"⚠️ Erro ao editar mensagem de progresso: {e}")
                    try:
                        await interaction.followup.send(f"Erro ao atualizar jogo: {str(e)[:80]}", ephemeral=True)
                    except:
                        pass

            else:
                # Finalizou as 3 escolhas
                await self.finalizar_jogo(interaction)

        except Exception as e:
            logging.error(f"💥 Erro crítico no callback escolher: {e}\n{traceback.format_exc()}")
            try:
                await interaction.followup.send("Ocorreu um erro ao processar sua escolha.", ephemeral=True)
            except:
                pass

    async def finalizar_jogo(self, interaction: discord.Interaction):
        """Processa o resultado final e salva no banco de dados."""
        try:
            # Desabilita todos os botões imediatamente
            for item in self.children:
                item.disabled = True

            # Resposta imediata para evitar timeout da interação - editar a mensagem do componente
            try:
                await interaction.message.edit(content="✨ Revelando destino...", view=self)
            except Exception as e:
                logging.error(f"⚠️ Erro ao mostrar mensagem de finalização: {e}")

            # Operação de Banco de Dados (Thread-safe)
            try:
                await asyncio.to_thread(
                    adicionar_pontos_db,
                    self.player.id,
                    self.pontos_totais,
                    self.player.name
                )
                db_success = True
            except Exception as db_err:
                logging.error(f"🗄️ Erro ao salvar pontos de {self.player.name}: {db_err}")
                db_success = False

            # Preparar resumo das cartas escolhidas
            resumo_cartas = []
            for idx in self.escolhidas:
                c, p = self.cartas[idx]
                resumo_cartas.append(f"{c['emoji']} **{c['nome']}**: {p:+d}")

            # Montar Embed Final
            cor = discord.Color.gold() if self.pontos_totais >= 0 else discord.Color.red()
            status_db = "" if db_success else "\n⚠️ *Erro ao salvar pontos no banco.*"
            
            embed_final = discord.Embed(
                title="🎴 RESULTADO FINAL",
                description="\n".join(resumo_cartas) + f"\n\n**Total: {self.pontos_totais:+d} pontos**{status_db}",
                color=cor
            )
            
            if self.pontos_totais > 0:
                embed_final.set_footer(text=f"A sorte sorriu para você, {self.player.name}!")
            else:
                embed_final.set_footer(text=f"Melhor sorte na próxima vez, {self.player.name}!")

            # Edita a mensagem original com o resultado
            try:
                await interaction.message.edit(content=None, embed=embed_final, view=None)
            except Exception as e:
                logging.error(f"⚠️ Erro ao editar mensagem final: {e}")
            
            logging.info(f"🃏 [JIMBO] Jogo finalizado: {self.player.name} totalizou {self.pontos_totais:+d}.")
            self.stop()

        except Exception as e:
            logging.error(f"💥 Erro crítico ao finalizar jogo: {e}\n{traceback.format_exc()}")
            try:
                await interaction.followup.send(
                    f"❌ Erro ao processar sua escolha: {str(e)[:100]}",
                    ephemeral=True
                )
            except:
                pass


class ArtesView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id

        self.like_button = discord.ui.Button(
            label="Curtir",
            emoji="❤️",
            style=discord.ButtonStyle.success,
            custom_id=f"like_{self.message_id}"
        )
        self.like_button.callback = self.like_callback
        self.add_item(self.like_button)

    async def like_callback(self, interaction: discord.Interaction):

        # ✅ evita Unknown Interaction
        await interaction.response.defer(ephemeral=True)

        con = conectar_vips()
        cur = con.cursor(buffered=True)

        try:
            # Buscar autor
            cur.execute(
                "SELECT user_id, COALESCE(nome_discord, '') FROM artes_posts WHERE message_id = %s",
                (self.message_id,)
            )
            row = cur.fetchone()

            if not row:
                await interaction.followup.send(
                    "Erro: Arte não encontrada no banco."
                )
                return

            author_id, author_name = row

            # Não pode votar na própria arte
            if interaction.user.id == author_id:
                await interaction.followup.send(
                    "Você não pode votar na sua própria arte!"
                )
                return

            # 🔥 INSERT protegido por UNIQUE
            try:
                cur.execute(
                    """
                    INSERT INTO artes_votos 
                    (message_id, voter_id, voter_nome, tipo) 
                    VALUES (%s, %s, %s, 'like')
                    """,
                    (self.message_id, interaction.user.id, str(interaction.user))
                )
            except Exception:
                con.rollback()

                await interaction.followup.send(
                    "Você já votou nessa arte!",
                    ephemeral=True
                )
                return

            # Incrementa corações
            cur.execute(
                "UPDATE artes_posts SET coracoes = coracoes + 1 WHERE message_id = %s",
                (self.message_id,)
            )

            con.commit()

            logging.info(
                f"[ARTES] Voto registrado: {interaction.user} -> msg {self.message_id}"
            )

            # Pontos (não quebrar fluxo)
            try:
                adicionar_pontos_db(author_id, 10, author_name or str(author_id))
            except Exception as e:
                logging.error(f"[ARTES] Erro ao adicionar pontos: {e}")

            # DM em background
            asyncio.create_task(
                enviar_dm_autor(author_id, interaction.user)
            )

            await interaction.followup.send(
                "💖 Voto confirmado! Seu apoio faz toda a diferença para o artista ✨",
                ephemeral=True
            )

        except Exception as e:
            con.rollback()

            logging.error(f"[ARTES] Erro ao processar voto: {e}\n{traceback.format_exc()}")

            try:
                await interaction.followup.send(
                    "Erro ao registrar voto."
                )
            except:
                pass

        finally:
            con.close()


# ✅ DM fora do fluxo principal
async def enviar_dm_autor(author_id: int, voter: str):
    try:
        author_user = await bot.fetch_user(author_id)

        embed = discord.Embed(
            title="<a:143125redgemheart:1454722071618916530> Sua arte recebeu um coração!",
            description=(
                "❤️ Alguém acabou de demonstrar carinho pela sua arte!\n"
                "Você ganhou **10 pontos** por isso.\n\n"
                "Quer acompanhar sua pontuação? Use **/pontos** para saber quantos pontos você possui!"
            ),
            color=discord.Color.green()
        )

        embed.set_footer(text=f"Coração enviado por {voter}")

        await author_user.send(embed=embed)

        logging.info(f"[ARTES] DM enviada ao autor {author_id}")

    except discord.Forbidden:
        logging.warning(f"[ARTES] Não foi possível enviar DM para {author_id} (DMs fechadas).")

    except discord.HTTPException as e:
        logging.error(f"[ARTES] Erro HTTP ao enviar DM para {author_id}: {e}")

    except Exception as e:
        logging.exception(f"[ARTES] Erro inesperado ao enviar DM para {author_id}: {e}")


# ✅ Views persistentes
async def setup_views():
    con = conectar_vips()
    cur = con.cursor(buffered=True)

    cur.execute("SELECT message_id FROM artes_posts")
    rows = cur.fetchall()

    for (message_id,) in rows:
        bot.add_view(ArtesView(message_id))

    con.close()


IMAGEM_ARTISTA = "https://raw.githubusercontent.com/DaviDetroit/VipBotDiscord/main/Artista.png"

async def processar_melhor_do_mes():
    hoje = datetime.now()

    if hoje.day != 1:
        return "Não é dia 1, verificação ignorada."

    logging.info("🎬 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logging.info("✨ INICIANDO: Verificação do Melhor do Mês!")
    logging.info("🎬 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    con = conectar_vips()
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT user_id, message_id, coracoes
            FROM artes_posts
            WHERE MONTH(data_post) = MONTH(NOW() - INTERVAL 1 MONTH)
            AND YEAR(data_post) = YEAR(NOW() - INTERVAL 1 MONTH)
            ORDER BY coracoes DESC
            LIMIT 1
        """)

        resultado = cur.fetchone()

        if not resultado:
            logging.info("💀 Nenhum post encontrado no mês anterior.")
            return "Nenhum post encontrado no mês anterior."

        user_id, message_id, coracoes = resultado

        if coracoes == 0:
            logging.info("💔 Todos os posts tiveram 0 curtidas.")
            return "Todos os posts tiveram 0 curtidas."

        guild = bot.get_guild(1380564679084081175)
        if not guild:
            return "Guild não encontrada."

        member = guild.get_member(user_id)
        if not member:
            return "Membro não encontrado."

        cargo = discord.utils.get(guild.roles, name="Artista")
        if not cargo:
            return "Cargo 'Artista' não encontrado."

        await member.add_roles(cargo)
        adicionar_pontos_db(user_id, 200, str(member))

        # EMBED
        embed = discord.Embed(
            title="<:534480paint:1471217810897113281> ARTISTA DO MÊS <:534480paint:1471217810897113281>",
            description=(
                f"🎨 Parabéns {member.mention}!\n\n"
                f"Sua arte foi a mais curtida do mês passado!\n\n"
                f"❤️ **Curtidas:** `{coracoes}`\n"
                f"👑 **Cargo:** Artista\n"
                f"💰 **Recompensa:** +200 pontos\n\n"
                f"Continue brilhando! ✨"
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url=IMAGEM_ARTISTA)
        embed.set_footer(text="Sistema Oficial • Artista do Mês")

        try:
            await member.send(embed=embed)
        except:
            logging.warning("⚠️ Não foi possível enviar DM.")

        await asyncio.sleep(1)

        member = guild.get_member(user_id)

        try:
            await processar_conquistas(
                member,
                mensagens_semana=0,
                maior_streak=0,
                fez_doacao=False,
                tem_vip=False,
                tempo_em_call=0,
                mencionou_miisha=False,
                tocou_musica=False,
                mencoes_bot=0,
                azarao_vitoria=False
            )
        except Exception as e:
            logging.error(f"Erro ao processar conquistas: {e}")

        logging.info(f"🎖️  Conquistas processadas para {member.display_name} após receber Artista do Mês!")

        return f"Vencedor: {member.display_name} com {coracoes} ❤️"

    except Exception as e:
        logging.error(f"💥 ERRO CRÍTICO: {e}")
        return f"Erro crítico: {e}"

    finally:
        con.close()

@tasks.loop(hours=24)
async def verificar_melhor_do_mes():
    resultado = await processar_melhor_do_mes()
    logging.info(f"📊 Resultado automático: {resultado}")



@bot.command(name="melhordomes")
@commands.has_permissions(administrator=True)
async def melhor_do_mes_manual(ctx):
    await ctx.send("🔎 Verificando melhor do mês manualmente...")

    resultado = await processar_melhor_do_mes()

    await ctx.send(f"✅ Resultado:\n{resultado}")


#Mencionar cargo bump
CARGO_BUMP = 1380564679222628494
CANAL_BUMP = 1380564680552091781

@tasks.loop(hours=4)
async def bump_loop():
    channel = bot.get_channel(CANAL_BUMP)
    if channel:
        try:
            # Menciona o cargo corretamente
            await channel.send(f"Faça o bump! <@&{CARGO_BUMP}> 🚀")
        except Exception as e:
            logging.info(f"Erro ao dar o bump :( {e}")


bot.run(TOKEN)