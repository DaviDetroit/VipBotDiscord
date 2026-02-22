from _plotly_utils.colors.plotlyjs import Reds
import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go
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
        percentual_lider = (df_times.iloc[0]["total"] / total_torcedores) * 100

        # Cards métricos com design moderno
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 1.5rem; 
                            border-radius: 15px; 
                            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                            text-align: center;
                            margin: 0.5rem 0;
                            border: 1px solid rgba(255,255,255,0.1);'>
                    <div style='color: rgba(255,255,255,0.8); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;'>Total de Participantes</div>
                    <div style='color: white; font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0;'>{total_torcedores:,}</div>
                    <div style='color: rgba(255,255,255,0.7); font-size: 0.8rem;'>torcedores registrados</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                            padding: 1.5rem; 
                            border-radius: 15px; 
                            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                            text-align: center;
                            margin: 0.5rem 0;
                            border: 1px solid rgba(255,255,255,0.1);'>
                    <div style='color: rgba(255,255,255,0.8); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;'>Maior Torcida</div>
                    <div style='color: white; font-size: 2rem; font-weight: bold; margin: 0.5rem 0;'>{time_lider}</div>
                    <div style='color: rgba(255,255,255,0.7); font-size: 0.8rem;'>{df_times.iloc[0]["total"]} torcedores</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                            padding: 1.5rem; 
                            border-radius: 15px; 
                            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                            text-align: center;
                            margin: 0.5rem 0;
                            border: 1px solid rgba(255,255,255,0.1);'>
                    <div style='color: rgba(255,255,255,0.8); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;'>Domínio do Líder</div>
                    <div style='color: white; font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0;'>{percentual_lider:.1f}%</div>
                    <div style='color: rgba(255,255,255,0.7); font-size: 0.8rem;'>do total de torcedores</div>
                </div>
            """, unsafe_allow_html=True)

        # Container para o gráfico com título
        st.markdown("""
            <div style='margin-top: 2rem; margin-bottom: 1rem;'>
                <h3 style='color: white; text-align: center; font-size: 1.5rem; margin-bottom: 1rem;'>
                    📊 Distribuição Percentual por Time
                </h3>
            </div>
        """, unsafe_allow_html=True)

        # Dicionário de cores gradientes para cada time
        cores_gradientes = {
            'Atlético-MG': ['#E93A3A', '#FFFFFF'],  # Vermelho para Branco (Galo)
            'Athletico-PR': ['#C8102E', '#FF6B6B'],  # Vermelho escuro para vermelho claro
            'Bahia': ['#0033A0', '#4D7FFF'],  # Azul escuro para azul claro
            'Botafogo': ['#000000', '#4D4D4D'],  # Preto para cinza
            'Bragantino': ['#C40000', '#FF4D4D'],  # Vermelho para vermelho claro
            'Ceará': ['#000000', '#4D4D4D'],  # Preto para cinza
            'Corinthians': ['#000000', '#4D4D4D'],  # Preto para cinza
            'Cruzeiro': ['#0033A0', '#4D7FFF'],  # Azul escuro para azul claro
            'Flamengo': ['#CC0000', '#FF4D4D'],  # Vermelho para vermelho claro
            'Fluminense': ['#7A0026', '#C41E3A'],  # Vinho para vermelho
            'Fortaleza': ['#0033A0', '#4D7FFF'],  # Azul escuro para azul claro
            'Grêmio': ['#0A3A77', '#2A6FB0'],  # Azul marinho para azul médio
            'Internacional': ['#CC0000', '#FF4D4D'],  # Vermelho para vermelho claro
            'Juventude': ['#006437', '#00B050'],  # Verde escuro para verde
            'Palmeiras': ['#006437', '#00B050'],  # Verde escuro para verde
            'Santos': ['#000000', '#4D4D4D'],  # Preto para cinza
            'São Paulo': ['#FF0000', '#FF6B6B'],  # Vermelho para vermelho claro
            'Sport': ['#C8102E', '#FF6B6B'],  # Vermelho para vermelho claro
            'Vasco': ['#000000', '#4D4D4D'],  # Preto para cinza
            'Vitória': ['#C8102E', '#FF6B6B'],  # Vermelho para vermelho claro
        }
        
        fig = go.Figure()

        # Criar lista de cores baseada nos times
        colors = []
        for time in df_times['time_normalizado']:
            if time in cores_gradientes:
                # Para gradiente, usamos a primeira cor como base
                colors.append(cores_gradientes[time][0])
            else:
                colors.append('#4A90E2')

        # Criar gráfico com Plotly Express (mais simples e confiável)
        fig = px.pie(
            df_times,
            values='total',
            names='time_normalizado',
            hole=0.6,
            color_discrete_sequence=colors,
            template='plotly_white'
        )

        # Atualizar traços para melhor visualização
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            textfont=dict(size=14, color='white', family="Arial Black"),
            marker=dict(line=dict(color='white', width=3)),
            hovertemplate='<b>%{label}</b><br>Torcedores: %{value}<br>Percentual: %{percent}<extra></extra>'
        )

        # Atualizar layout
        fig.update_layout(
            showlegend=False,
            margin=dict(t=30, b=30, l=30, r=30),
            height=500,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Arial", size=12, color="#1f1f1f"),
            annotations=[
                dict(
                    text=f"Total<br>{total_torcedores}",
                    x=0.5, y=0.5,
                    font_size=20,
                    font_family="Arial Black",
                    showarrow=False
                )
            ]
        )

        # Container para o gráfico com sombra
        st.markdown("""
            <div style='background: white; padding: 1rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); margin: 1rem 0;'>
        """, unsafe_allow_html=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

        

        # Cards adicionais com cores gradientes dos times
        st.markdown("""
            <div style='margin-top: 2rem;'>
                <h3 style='color: white; text-align: center; font-size: 1.5rem; margin-bottom: 1rem;'>
                    🏟 Maiores Torcidas
                </h3>
            </div>
        """, unsafe_allow_html=True)

        # Mostrar cards para os top 3 times
        col1, col2, col3 = st.columns(3)
        
        top_3_times = df_times.head(3).reset_index(drop=True)
        
        for idx, col in enumerate([col1, col2, col3]):
            if idx < len(top_3_times):
                with col:
                    time = top_3_times.iloc[idx]['time_normalizado']
                    total = top_3_times.iloc[idx]['total']
                    percentual = (total / total_torcedores) * 100
                    
                    if time in cores_gradientes:
                        cor1, cor2 = cores_gradientes[time]
                        gradiente = f"linear-gradient(135deg, {cor1}, {cor2})"
                    else:
                        gradiente = "linear-gradient(135deg, #667eea, #764ba2)"
                    
                    medalha = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉"
                    
                    st.markdown(f"""
                        <div style='background: {gradiente}; 
                                    padding: 1.5rem; 
                                    border-radius: 15px; 
                                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                                    text-align: center;
                                    margin: 0.5rem 0;
                                    border: 2px solid white;'>
                            <div style='font-size: 3rem; margin-bottom: 0.5rem;'>{medalha}</div>
                            <div style='color: white; font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0;'>{time}</div>
                            <div style='color: white; font-size: 2rem; font-weight: bold;'>{total:,}</div>
                            <div style='color: rgba(255,255,255,0.8); font-size: 1rem;'>{percentual:.1f}% dos torcedores</div>
                        </div>
                    """, unsafe_allow_html=True)

    else:
        st.markdown("""
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        padding: 3rem; 
                        border-radius: 15px; 
                        text-align: center;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        margin: 2rem 0;'>
                <h2 style='color: white; margin-bottom: 1rem;'>😕 Nenhum dado encontrado</h2>
                <p style='color: rgba(255,255,255,0.9); font-size: 1.1rem;'>
                    Aguardando os primeiros torcedores se registrarem!
                </p>
            </div>
        """, unsafe_allow_html=True)

    # Rodapé
    st.markdown("""
        <div style='text-align: center; margin-top: 3rem; padding: 1rem; color: #6c757d; border-top: 1px solid #dee2e6;'>
            <p style='font-size: 0.9rem;'>
                ⚽ Dados atualizados em tempo real • Total de {total} torcedores distribuídos entre {times} times
            </p>
        </div>
    """.format(total=total_torcedores if not df_times.empty else 0, 
               times=len(df_times) if not df_times.empty else 0), unsafe_allow_html=True)

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
    # 🎨 Ranking de Artes por Corações
    # =============================
    st.header("🎨 Ranking de Artes - Mais Amados da Comunidade")
    sql_artes = """
        SELECT nome_discord, SUM(coracoes) AS total_coracao
        FROM artes_posts
        GROUP BY nome_discord
        ORDER BY total_coracao DESC;
        """
    
    df_artes = consulta(sql_artes, DB_VIPS)
    if not df_artes.empty:
        mais_amado = df_artes.iloc[0]

        # Card do Campeão (Agora em Lilás)

        st.markdown(f"""
            <div class="champion-card" style="
                background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
                padding: 30px;
                border-radius: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 10px 30px rgba(155,89,182,0.4);
                margin-bottom: 25px;
            ">
                <div class="crown-icon" style="font-size: 4em; margin-bottom: 10px;">🎨</div>
                <h1 style="margin: 10px 0; font-size: 2.5em; color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">
                    {mais_amado['nome_discord']}
                </h1>
                <div style="font-size: 1.3em; color: #f8f0ff; margin: 10px 0;">
                    💜 Artista Mais Amado da Comunidade 💜
                </div>
                <div style="
                    background: rgba(255,255,255,0.2);
                    padding: 15px 30px;
                    border-radius: 50px;
                    display: inline-block;
                    margin: 15px 0;
                    font-size: 1.8em;
                    font-weight: bold;
                ">
                    ❤️ {mais_amado['total_coracao']} corações
                </div>
                <div style="margin-top: 20px; font-size: 1.1em; color: #f8f0ff;">
                    👑 O artista mais querido da comunidade! 👑
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Ranking Completo (Agora em Tons Lilás)
        with st.expander("📊 Ver ranking completo detalhado"):
            for i, row in df_artes.iterrows():
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🎨"
                
                # Cores em degrade lilás para o top 3
                if i == 0:
                    bg_color = "linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%)"
                    border_color = "#9b59b6"
                elif i == 1:
                    bg_color = "linear-gradient(135deg, #b48ab4 0%, #9b59b6 100%)"
                    border_color = "#b48ab4"
                elif i == 2:
                    bg_color = "linear-gradient(135deg, #c39bd3 0%, #b48ab4 100%)"
                    border_color = "#c39bd3"
                else:
                    bg_color = "white"
                    border_color = "#9b59b6"
                
                text_color = "white" if i < 3 else "#000000"
                
                st.markdown(f"""
                <div style="
                    background: {bg_color};
                    padding: 12px;
                    border-radius: 10px;
                    margin: 5px 0;
                    border-left: 5px solid {border_color};
                    box-shadow: 0 2px 5px rgba(155,89,182,0.2);
                    color: {text_color};
                ">
                    <span style="font-size: 1.3em; margin-right: 10px;">{medal}</span>
                    <span style="font-weight: bold; font-size: 1.1em;">
                        {i+1}. {row['nome_discord']}
                    </span>
                    <span style="float: right; background: {'rgba(255,255,255,0.3)' if i < 3 else '#9b59b6'}; color: white; padding: 4px 12px; border-radius: 20px;">
                        ❤️ {row['total_coracao']}
                    </span>
                </div>
                """,unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            color: white;
            box-shadow: 0 10px 30px rgba(155,89,182,0.4);
        ">
            <div style="font-size: 4em; margin-bottom: 20px;">🎨</div>
            <h2 style="margin-bottom: 15px;">Nenhuma arte postada ainda!</h2>
            <p style="font-size: 1.1em; opacity: 0.9;">
                Poste sua arte e conquiste corações! 💜✨
            </p>
        </div>
        """, unsafe_allow_html=True)




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

    # =============================
    # 🎌 Ranking Anime (AGORA DENTRO DO BLOCO DB_VIPS)
    # =============================
    
    # Estilo personalizado com CSS
    st.markdown("""
    <style>
        .ranking-title {
            background: linear-gradient(90deg, #FF4B4B 0%, #FF8E8E 100%);
            padding: 20px;
            border-radius: 15px;
            color: white;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(255,75,75,0.3);
        }
        .ranking-title h2 {
            margin: 0;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .ranking-title p {
            margin: 10px 0 0 0;
            opacity: 0.95;
            font-size: 1.1em;
        }
        .champion-card {
            background: linear-gradient(135deg, #FFF9C4 0%, #FFE082 100%);
            padding: 25px;
            border-radius: 20px;
            border: 2px solid #FFD700;
            box-shadow: 0 10px 25px rgba(255,215,0,0.3);
            margin: 20px 0;
            text-align: center;
        }
        .crown-icon {
            font-size: 3em;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.2));
            animation: float 3s ease-in-out infinite;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        .votes-count {
            background: rgba(255,255,255,0.3);
            padding: 10px 20px;
            border-radius: 30px;
            font-weight: bold;
            backdrop-filter: blur(5px);
            display: inline-block;
            margin-top: 10px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.15);
        }
        .stat-value {
            font-size: 2.2em;
            font-weight: bold;
            color: #FF4B4B;
            line-height: 1.2;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Título estilizado
    st.markdown("""
    <div class="ranking-title">
        <h2>🏆 Ranking dos Personagens</h2>
        <p>✨ Descubra os favoritos da comunidade! ✨</p>
    </div>
    """, unsafe_allow_html=True)

    # Container principal com efeito de vidro
    with st.container():
        # Consulta SQL
        sql_anime = """
            SELECT personagem, COUNT(*) AS votos_personagem
            FROM votos_anime
            GROUP BY personagem
            ORDER BY votos_personagem DESC
            LIMIT 10;
            """
        df_anime = consulta(sql_anime, DB_VIPS)

        if not df_anime.empty:
            # Cards de estatísticas rápidas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{}</div>
                    <div class="stat-label">Total de Personagens</div>
                </div>
                """.format(len(df_anime)), unsafe_allow_html=True)
            
            with col2:
                total_votos = df_anime['votos_personagem'].sum()
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{}</div>
                    <div class="stat-label">Total de Votos</div>
                </div>
                """.format(total_votos), unsafe_allow_html=True)
            
            with col3:
                media_votos = int(df_anime['votos_personagem'].mean())
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">{}</div>
                    <div class="stat-label">Média de Votos</div>
                </div>
                """.format(media_votos), unsafe_allow_html=True)
            
            with col4:
                mais_votado = df_anime.iloc[0]
                st.markdown("""
                <div class="stat-card">
                    <div class="stat-value">🥇</div>
                    <div class="stat-label">Campeão</div>
                </div>
                """, unsafe_allow_html=True)

            # Gráfico melhorado
            fig = px.bar(
                df_anime,
                x="votos_personagem",
                y="personagem",
                orientation="h",
                text="votos_personagem",
                color="votos_personagem",
                color_continuous_scale=[
                    [0, '#FFE5E5'],
                    [0.3, '#FFB8B8'],
                    [0.6, '#FF8A8A'],
                    [0.8, '#FF5C5C'],
                    [1, '#FF2E2E']
                ],
                template="plotly_white"
            )
            
            fig.update_layout(
                height=500,
                title_x=0.5,
                xaxis_title="Número de Votos",
                yaxis_title="",
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Arial", size=12),
                margin=dict(l=10, r=10, t=30, b=10)
            )

            fig.update_traces(
                textposition='outside',
                textfont=dict(size=12, color='#FF4B4B'),
                marker=dict(line=dict(color='#FF4B4B', width=1)),
                hovertemplate='<b>%{y}</b><br>Votos: %{x}<extra></extra>'
            )

            st.plotly_chart(fig, use_container_width=True)

            # Card do campeão com animação
            st.markdown(f"""
            <div class="champion-card">
                <div class="crown-icon">👑</div>
                <h1 style="margin: 10px 0; font-size: 2.5em; color: #8B4513;">{mais_votado['personagem']}</h1>
                <div style="font-size: 1.3em; color: #666; margin: 10px 0;">
                    ⭐ Campeão Absoluto ⭐
                </div>
                <div class="votes-count">
                    🗳️ {mais_votado['votos_personagem']} votos
                </div>
                <div style="margin-top: 20px; font-size: 0.9em; color: #8B4513;">
                    🏆 O favorito da comunidade!
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Ranking em formato de lista (opcional)
            with st.expander("📊 Ver ranking completo detalhado"):
                for i, row in df_anime.iterrows():
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📌"
                    st.markdown(f"""
                    <div style="
                        background: {'#FFF9C4' if i < 3 else 'white'};
                        padding: 12px;
                        border-radius: 10px;
                        margin: 5px 0;
                        border-left: 5px solid {'#FFD700' if i == 0 else '#C0C0C0' if i == 1 else '#CD7F32' if i == 2 else '#FF4B4B'};
                        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                    ">
                        <span style="font-size: 1.3em; margin-right: 10px;">{medal}</span>
                        <span style="font-weight: bold; font-size: 1.1em;">{i+1}. {row['personagem']}</span>
                        <span style="float: right; background: #FF4B4B; color: white; padding: 4px 12px; border-radius: 20px;">
                            {row['votos_personagem']} votos
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

        else:
            # Mensagem de vazio mais atraente
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px;
                border-radius: 20px;
                text-align: center;
                color: white;
                box-shadow: 0 10px 30px rgba(102,126,234,0.4);
            ">
                <div style="font-size: 4em; margin-bottom: 20px;">🎭</div>
                <h2 style="margin-bottom: 15px;">Nenhum voto registrado ainda!</h2>
                <p style="font-size: 1.1em; opacity: 0.9;">Seja o primeiro a votar no seu personagem favorito! ✨</p>
            </div>
            """, unsafe_allow_html=True)
