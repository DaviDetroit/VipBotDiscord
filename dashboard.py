import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Dashboard Bot Discord", layout="wide")
st.title("📊 Dashboard Estatístico do Bot")

# =============================
# SELETOR DE BANCO
# =============================

bancos = {
    "⚽ Futebol": os.getenv("DB_FUTEBOL"),
    "👑 Vips": os.getenv("DB_VIPS")
}

nome_escolhido = st.selectbox(
    "📂 Escolha o Banco",
    list(bancos.keys())
)

DATABASE = bancos[nome_escolhido]

DB_FUTEBOL = os.getenv("DB_FUTEBOL")
DB_VIPS = os.getenv("DB_VIPS")

# =============================
# CONEXÃO MYSQL
# =============================

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

def consulta(sql, database_name: str | None = None):
    conn = conectar(database_name or DATABASE)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

# =====================================================
# ⚽ BANCO FUTEBOL
# =====================================================
if DATABASE == os.getenv("DB_FUTEBOL"):
    st.markdown("## 🏆 Ranking de Mitos (Maiores Streaks)")

    # SQL CORRIGIDO: Agrupa por usuário e pega o maior valor de cada um
    sql_streak = """
    SELECT nome_discord, MAX(maior_streak) AS recorde_streak 
    FROM apostas 
    GROUP BY nome_discord
    ORDER BY recorde_streak DESC 
    LIMIT 5;
    """

    df_streak = consulta(sql_streak)

    if not df_streak.empty:
        # Criando colunas para um visual de "Pódio" antes da lista
        col1, col2, col3 = st.columns([1, 2, 1])

        # CSS para deixar a tabela com cara de App de Apostas
        st.markdown("""
            <style>
            .leaderboard-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 20px;
                margin: 8px 0px;
                background: #262730;
                border-radius: 10px;
                border-left: 4px solid #00E676; /* Verde sucesso */
            }
            .user-id { font-weight: bold; color: #FAFAFA; }
            .streak-val { color: #00E676; font-family: 'Courier New', monospace; font-size: 20px; }
            </style>
        """, unsafe_allow_html=True)

        for i, row in df_streak.iterrows():
            # Ícone baseado na posição
            icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "👤"
            
            st.markdown(f"""
                <div class="leaderboard-row">
                    <span class="user-id">{icon} ID: {row['nome_discord']}</span>
                    <span class="streak-val">{row['recorde_streak']}🔥</span>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhum recorde encontrado.")

    # =============================
    # Distribuição de Torcedores
    # =============================

    st.header("⚽ Distribuição de Torcedores")

    sql_times = """
    SELECT time_normalizado, COUNT(*) as total
    FROM times_usuarios
    GROUP BY time_normalizado;
    """

    df_times = consulta(sql_times)

    if not df_times.empty:
        df_times = df_times.sort_values(by="total", ascending=False)

        total_torcedores = df_times["total"].sum()
        time_lider = df_times.iloc[0]["time_normalizado"]

        col1, col2 = st.columns(2)
        col1.metric("Total de Participantes", total_torcedores)
        col2.metric("Maior Torcida", time_lider)

        fig = px.pie(
            df_times,
            names="time_normalizado",
            values="total",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Pastel,
            template="plotly_white"
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            marker=dict(line=dict(color="#000000", width=1))
        )

        fig.update_layout(
            showlegend=False,
            margin=dict(t=30, b=0, l=0, r=0)
        )

        st.plotly_chart(fig, use_container_width=True)

    # =============================
    # Ranking Pontos
    # =============================

    st.header("💰 Ranking Geral de Pontos")

    sql_pontos = """
    SELECT nome_discord, pontos
    FROM pontuacoes
    ORDER BY pontos DESC
    LIMIT 10;
    """

    df_pontos = consulta(sql_pontos)

    if not df_pontos.empty:
        fig = px.bar(df_pontos,
                     x="nome_discord",
                     y="pontos",
                     title="Top 10 Pontuação",
                     text="pontos")

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Estatísticas Gerais")

        media = df_pontos["pontos"].mean()
        maximo = df_pontos["pontos"].max()
        minimo = df_pontos["pontos"].min()

        col1, col2, col3 = st.columns(3)

        col1.metric("Média Pontos (Top 10)", f"{media:.2f}")
        col2.metric("Maior Pontuação", maximo)
        col3.metric("Menor Pontuação (Top 10)", minimo)


# =====================================================
# 👑 BANCO VIPS
# =====================================================

elif DATABASE == os.getenv("DB_VIPS"):

    st.header("👑 VIPs Ordenados por Vencimento")

    sql_vips = """
    SELECT nome_discord, data_inicio, data_fim
    FROM vips
    ORDER BY data_fim ASC;
    """

    df_vips = consulta(sql_vips)

    if not df_vips.empty:
        st.dataframe(df_vips)

    # =============================
    # Conquistas
    # =============================

    st.header("🏅 Estatísticas de Conquistas")

    sql_total_users = """
    SELECT COUNT(DISTINCT user_id) as total_users
    FROM pontuacoes;
    """

    df_total = consulta(sql_total_users, DB_FUTEBOL)
    total_users = df_total["total_users"][0] if not df_total.empty else 0

    sql_conquistas = """
    SELECT conquista_id, COUNT(DISTINCT user_id) as total
    FROM conquistas_desbloqueadas
    GROUP BY conquista_id
    ORDER BY total DESC;
    """

    df_conquistas = consulta(sql_conquistas, DB_VIPS)

    if not df_conquistas.empty and total_users > 0:

        df_conquistas["percentual"] = (df_conquistas["total"] / total_users) * 100

        fig = px.bar(
            df_conquistas,
            x="conquista_id",
            y="percentual",
            title="📊 Percentual de Usuários por Conquista",
            text=df_conquistas["percentual"].round(2),
        )

        st.plotly_chart(fig, use_container_width=True)

        mais_comum = df_conquistas.iloc[0]
        mais_rara = df_conquistas.iloc[-1]

        col1, col2 = st.columns(2)

        col1.metric(
            "🥇 Conquista Mais Popular",
            mais_comum["conquista_id"],
            f'{mais_comum["percentual"]:.2f}% dos usuários'
        )

        col2.metric(
            "🧊 Conquista Mais Rara",
            mais_rara["conquista_id"],
            f'{mais_rara["percentual"]:.2f}% dos usuários'
        )

    # =============================
    # 📈 Ranking de Atividade
    # =============================

    st.header("💬 Ranking de Atividade Semanal")

    sql_atividade = """
    SELECT user_id, nome_discord, SUM(mensagens) as total_mensagens
    FROM atividade
    GROUP BY user_id, nome_discord
    ORDER BY total_mensagens DESC
    LIMIT 10;
    """

    df_atividade = consulta(sql_atividade, DB_VIPS)

    if not df_atividade.empty:
        fig = px.bar(
            df_atividade,
            x="total_mensagens",
            y="nome_discord",
            orientation="h",
            text="total_mensagens",
            title="Top 10 Usuários Mais Ativos na Semana",
            color="total_mensagens",
            color_continuous_scale="Blues"
        )

        fig.update_layout(
            yaxis=dict(autorange="reversed"),  # colocar o mais ativo em cima
            height=500,
            title_x=0.5,
            coloraxis_showscale=False
        )

        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma atividade registrada nesta semana.")