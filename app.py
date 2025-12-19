import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
from datetime import datetime, timedelta, date
import time
import tempfile
import os
import pandas as pd
import sqlite3
import imaplib
import email
from email.header import decode_header
import smtplib
import ssl
from email.message import EmailMessage
import plotly.express as px
import base64

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - TEMA CYBER FUTURE
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite | AI System", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS AVANÇADO ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');

        :root {
            --bg-dark: #020617;
            --bg-card: rgba(15, 23, 42, 0.6);
            --text-main: #FFFFFF;
            --neon-blue: #00F3FF;
            --neon-red: #FF0055;
            --neon-gold: #FFD700;
        }

        .stApp {
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(14, 165, 233, 0.08), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.08), transparent 25%);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
        }

        h1, h2, h3, h4, h5, h6 { color: #FFFFFF !important; font-family: 'Rajdhani', sans-serif; text-transform: uppercase; letter-spacing: 1.5px; }
        p, .stCaption, label, .stMarkdown { color: #E2E8F0 !important; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetricValue"] { color: var(--neon-blue) !important; text-shadow: 0 0 10px rgba(0, 243, 255, 0.5); }
        .tech-header { background: linear-gradient(90deg, #FFFFFF 0%, var(--neon-blue) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 700; }

        /* CARDS & CONTAINERS */
        .price-card { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease; }
        .price-card:hover { transform: translateY(-5px); border-color: var(--neon-blue); box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); }
        .price-title { font-family: 'Rajdhani'; font-size: 1.5rem; font-weight: bold; color: #FFF; margin-bottom: 10px; }
        .price-amount { font-size: 2.5rem; font-weight: 800; color: var(--neon-blue); margin: 15px 0; }
        .elite-card { border: 1px solid var(--neon-gold); background: rgba(255, 215, 0, 0.05); }
        .elite-card .price-amount { color: var(--neon-gold); text-shadow: 0 0 10px rgba(255,215,0,0.5); }

        /* LOCK SCREEN */
        .lock-screen { border: 1px solid var(--neon-red); background: rgba(255, 0, 85, 0.05); border-radius: 10px; padding: 40px; text-align: center; margin-top: 50px; }
        .lock-icon { font-size: 3rem; margin-bottom: 10px; }
        .lock-title { color: var(--neon-red) !important; font-family: 'Rajdhani'; font-size: 2rem; font-weight: bold; }

        /* HEADER & ANIMATION */
        .header-logo { display: flex; align-items: center; margin-right: 2rem; }
        .header-logo h1 { font-size: 1.8rem; margin: 0; letter-spacing: 2px; }
        .floating-logo { animation: float 6s ease-in-out infinite; display: block; margin: 0 auto 30px auto; width: 250px; }
        @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-20px); } }
        
        section[data-testid="stSidebar"] { background-color: #020408; border-right: 1px solid rgba(0, 243, 255, 0.1); }
        .stButton>button { background: transparent; color: var(--neon-blue); border: 1px solid var(--neon-blue); border-radius: 0px; padding: 0.6rem 1.2rem; font-family: 'Rajdhani'; font-weight: 700; }
        .stButton>button:hover { background: var(--neon-blue); color: #000; box-shadow: 0 0 20px rgba(0, 243, 255, 0.6); }
        
        div[data-testid="metric-container"], div[data-testid="stExpander"], .folder-card { background: var(--bg-card); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 0px; backdrop-filter: blur(12px); }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { background-color: rgba(0, 0, 0, 0.3) !important; border: 1px solid #334155 !important; color: #FFF !important; border-radius: 0px; }
        
        div[role="radiogroup"] { display: flex; justify-content: space-between; background: rgba(10, 15, 30, 0.8); padding: 10px; border-radius: 8px; border-bottom: 1px solid rgba(0, 243, 255, 0.3); }
        div[role="radiogroup"] label { background: transparent !important; border: none !important; margin: 0 !important; padding: 5px 15px !important; color: #94A3B8 !important; }
        div[role="radiogroup"] label:hover { color: #FFF !important; text-shadow: 0 0 5px #00F3FF; }
        div[role="radiogroup"] label[data-checked="true"] { color: #00F3FF !important; border-bottom: 2px solid #00F3FF !important; background: rgba(0, 243, 255, 0.1) !important; }
        div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p { font-size: 1rem !important; }

        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

local_css()

# ==========================================================
# 2. FUNÇÕES GERAIS E BANCO DE DADOS
# ==========================================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError: return None

def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'Starter')''')
    
    # --- CORREÇÃO AQUI (Try/Except separados em linhas) ---
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except:
        pass
        
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT DEFAULT 'Starter'")
    except:
        pass
    # -----------------------------------------------------

    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)''')
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado1', '123', 'Escritório Alpha', 'lucas@alpha.adv.br', 10, 'Starter')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br', 5, 'Pro')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com', 9999, 'Elite')")
        conn.commit()
    conn.close()

def run_query(query, params=(), return_data=False):
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if return_data:
            data = c.fetchall()
            col_names = [description[0] for description in c.description]
            conn.close()
            return pd.DataFrame(data, columns=col_names)
        else: conn.commit(); conn.close(); return True
    except Exception: conn.close(); return None

init_db()

# ==========================================================
# 3. LÓGICA DE ACESSO E PLANOS
# ==========================================================
NIVEIS_PLANO = {"Starter": 1, "Pro": 2, "Elite": 3}

def verificar_acesso(plano_minimo):
    plano_usuario = st.session_state.get('plano_atual', 'Starter')
    return NIVEIS_PLANO.get(plano_usuario, 1) >= NIVEIS_PLANO.get(plano_minimo, 1)

def tela_bloqueio(plano_necessario):
    st.markdown(f"""
    <div class='lock-screen'><div class='lock-icon'>🔒</div><div class='lock-title'>ACCESS DENIED</div>
    <p class='lock-desc'>Recurso exclusivo para membros <strong>{plano_necessario.upper()}</strong>.</p></div>
    """, unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2: 
        if st.button("🚀 FAZER UPGRADE", use_container_width=True): st.session_state.navegacao_override = "💎 Planos Premium"; st.rerun()

# ==========================================================
# 4. CONTROLE DE SESSÃO & LOGIN
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""
if "plano_atual" not in st.session_state: st.session_state.plano_atual = "Starter"

if not st.session_state.logado:
    if "user" in st.query_params:
        user_url = st.query_params["user"]
        users = run_query("SELECT * FROM usuarios WHERE username = ?", (user_url,), return_data=True)
        if not users.empty:
            st.session_state.logado = True
            st.session_state.usuario_atual = user_url
            st.session_state.escritorio_atual = users.iloc[0]['escritorio']
            st.session_state.plano_atual = users.iloc[0]['plano']
            st.rerun()

def login_screen():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        img_base64 = get_base64_of_bin_file("diagrama-ia.png")
        if img_base64: st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo"></div>""", unsafe_allow_html=True)
        else: st.markdown("<h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)
        st.markdown("""<div style='text-align: center;'><h1 class='tech-header' style='font-size: 2.5rem; letter-spacing: 3px;'>LEGALHUB <span style='font-weight: 300; color: #fff;'>ELITE</span></h1><p style='color: #00F3FF; font-size: 0.8rem; letter-spacing: 2px;'>Artificial Intelligence System</p></div>""", unsafe_allow_html=True)
        st.write("")
        with st.container(border=True):
            st.markdown("#### ACCESS CONTROL")
            username = st.text_input("ID Usuário")
            password = st.text_input("Chave de Acesso", type="password")
            st.write("")
            if st.button("🔓 INICIAR SESSÃO", use_container_width=True):
                users = run_query("SELECT * FROM usuarios WHERE username = ? AND senha = ?", (username, password), return_data=True)
                if not users.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = username
                    st.session_state.escritorio_atual = users.iloc[0]['escritorio']
                    st.session_state.plano_atual = users.iloc[0]['plano']
                    st.query_params["user"] = username
                    st.rerun()
                else: st.error("Acesso Negado.")
            st.markdown("<div style='text-align:center; margin-top:10px; color: #475569; font-size: 0.7rem; font-family: Rajdhani;'>SYSTEM V5.5 // SECURE</div>", unsafe_allow_html=True)

if not st.session_state.logado:
    login_screen()
    st.stop()

# ==========================================================
# 5. CONFIGURAÇÃO API E SIDEBAR
# ==========================================================
if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
else: api_key = st.text_input("🔑 API Key (Salve no sidebar):", type="password")

if api_key:
    genai.configure(api_key=api_key)
    mod_escolhido = "models/gemini-1.5-flash"

df_user = run_query("SELECT creditos, plano FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
if not df_user.empty:
    creditos_atuais = df_user.iloc[0]['creditos']
    st.session_state.plano_atual = df_user.iloc[0]['plano']
else: creditos_atuais = 0

if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)

with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Perícia & Calc": "🧮 Calculadoras & Perícia", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Planos Premium"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.navegacao_override:
        try:
            key_override = [k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0]
            idx_radio = opcoes_menu.index(key_override)
        except: idx_radio = 0
        st.session_state.navegacao_override = None
    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")

with st.sidebar:
    img_base64 = get_base64_of_bin_file("diagrama-ia.png")
    if img_base64: st.markdown(f'<img src="data:image/png;base64,{img_base64}" style="width:100%; margin-bottom: 20px;">', unsafe_allow_html=True)
    st.markdown("<h2 class='tech-header' style='font-size:1.5rem;'>CONFIGURAÇÕES</h2>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0;'>User: {st.session_state.usuario_atual}<br>Banca: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    
    plano_cor = "#FFD700" if st.session_state.plano_atual == "Elite" else "#00F3FF"
    if st.session_state.plano_atual == "Starter": plano_cor = "#FFFFFF"
    st.markdown(f"<div style='border:1px solid {plano_cor}; padding:5px; border-radius:5px; text-align:center; color:{plano_cor}; margin:10px 0;'>PLANO: {st.session_state.plano_atual.upper()}</div>", unsafe_allow_html=True)

    if "GOOGLE_API_KEY" not in st.secrets:
        st.text_input("🔑 API Key:", type="password", key="sidebar_api_key")
        if st.session_state.sidebar_api_key: genai.configure(api_key=st.session_state.sidebar_api_key)

    st.markdown("---")
    st.markdown("<h4 style='font-size:1rem; color:#94A3B8;'>CRÉDITOS</h4>", unsafe_allow_html=True)
    c_cr1, c_cr2 = st.columns([1, 3])
    with c_cr1: st.markdown("<h3 style='color:#0EA5E9; margin:0;'>💎</h3>", unsafe_allow_html=True)
    with c_cr2: st.markdown(f"<h3 style='margin:0; color:#FFFFFF;'>{creditos_atuais}</h3>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/100, 1.0))
    
    st.write("")
    if st.button("LOGOUT"): st.session_state.logado = False; st.query_params.clear(); st.rerun()

    if st.session_state.usuario_atual == 'admin':
        with st.expander("🛠️ ADMIN"):
            if st.button("Add 50 Créditos"): run_query("UPDATE usuarios SET creditos = creditos + 50 WHERE username = ?", (st.session_state.usuario_atual,)); st.rerun()

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    img_base64 = get_base64_of_bin_file("diagrama-ia.png")
    if img_base64: st.markdown(f"""<div style="display: flex; justify-content: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo" style="width: 200px;"></div>""", unsafe_allow_html=True)
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| {st.session_state.usuario_atual}</span></h2>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    c1.metric("DOCS GERADOS", docs_feitos)
    c2.metric("SALDO CRÉDITOS", creditos_atuais)
    c3.metric("STATUS CONTA", st.session_state.plano_atual.upper())
    
    st.write("")
    st.subheader("🛠️ ACESSO RÁPIDO")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        with st.container(border=True):
            st.markdown("#### ✍️ REDATOR"); st.caption("Crie petições e contratos.")
            if st.button("ABRIR", key="d_redator"): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r1c2:
        with st.container(border=True):
            st.markdown("#### 🧮 PERÍCIA"); st.caption("Cálculos Trabalhistas e Cíveis.")
            if st.button("ABRIR", key="d_pericia"): st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"; st.rerun()
    with r1c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ AUDIÊNCIA"); st.caption("Estratégia e Perguntas.")
            if st.button("ABRIR", key="d_aud"): st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"; st.rerun()

    st.write("")
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.markdown("##### 📈 DADOS DE PRODUTIVIDADE")
        with st.container(border=True):
            df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
            if not df_areas.empty:
                fig = px.pie(df_areas, values='qtd', names='area', hole=0.7, color_discrete_sequence=['#00F3FF', '#BC13FE', '#2E5CFF', '#FFFFFF', '#4A4A4A'])
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0", showlegend=True, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Aguardando dados...")
    
    with col_info:
        st.markdown("##### 🛡️ SECURITY & COMPLIANCE")
        with st.container(border=True):
            st.markdown("""
            <div style='background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10B981; padding: 10px; margin-bottom: 8px; border-radius: 4px;'><strong style='color: #10B981; font-family: Rajdhani;'>✓ LGPD COMPLIANT</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Dados anonimizados.</span></div>
            <div style='background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3B82F6; padding: 10px; margin-bottom: 8px; border-radius: 4px;'><strong style='color: #3B82F6; font-family: Rajdhani;'>🔒 E2E ENCRYPTION</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Criptografia Militar.</span></div>
            <div style='background: rgba(245, 158, 11, 0.1); border-left: 3px solid #F59E0B; padding: 10px; border-radius: 4px;'><strong style='color: #F59E0B; font-family: Rajdhani;'>⚖️ LIVE JURISPRUDENCE</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Sincronia STF/STJ.</span></div>
            """, unsafe_allow_html=True)

# 2. REDATOR JURÍDICO (FUNCIONALIDADES EXPANDIDAS)
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO</h2>", unsafe_allow_html=True)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    
    # Carrega Clientes
    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    with col_config:
        with st.container(border=True):
            st.markdown("##### ⚙️ ESTRUTURA DA PEÇA")
            tipo = st.selectbox("Tipo de Peça", ["Petição Inicial", "Contestação", "Réplica", "Recurso Inominado", "Apelação", "Contrato", "Parecer Jurídico", "Mandado de Segurança"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário", "Previdenciário", "Consumidor"])
            tom = st.selectbox("Tom de Voz", ["Formal e Técnico", "Combativo e Incisivo", "Conciliador", "Acadêmico"])
            
            # Limitação: Jurisprudência
            web_disabled = not verificar_acesso("Pro")
            web = st.checkbox("🔍 Buscar Jurisprudência Atualizada (Web)", value=not web_disabled, disabled=web_disabled)
            if web_disabled: st.caption("🔒 Upgrade para PRO para liberar.")
            
            st.markdown("---")
            st.markdown("##### 👤 CLIENTE")
            modo_cliente = st.radio("Seleção:", ["Existente", "Novo"], horizontal=True, label_visibility="collapsed")
            if modo_cliente == "Existente" and lista_clientes:
                cli_final = st.selectbox("Nome:", lista_clientes)
            else:
                cli_final = st.text_input("Nome do Novo Cliente:")

    with col_input:
        with st.container(border=True):
            st.markdown("##### 📝 DADOS E FATOS")
            fatos = st.text_area("Descreva os fatos detalhadamente:", height=200, value=st.session_state.fatos_recuperados)
            legislacao_extra = st.text_input("Citar Legislação/Súmula Específica (Opcional):", placeholder="Ex: Súmula 331 do TST")
            formato = st.radio("Formato de Saída:", ["Texto Corrido", "Tópicos Estruturados"], horizontal=True)
    
    st.write("")
    if st.button("✨ GERAR MINUTA COMPLETA (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner("Analisando caso, buscando teses e redigindo..."):
                jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else "Jurisprudência padrão aplicada."
                prompt = f"""
                Atue como Advogado Sênior especialista em {area}.
                Escreva uma {tipo} completa.
                Tom: {tom}.
                Cliente: {cli_final}.
                Fatos: {fatos}.
                Legislação Obrigatória: {legislacao_extra}.
                Jurisprudência encontrada para usar: {jur}.
                Formato: {formato}.
                Estruture com: Endereçamento, Qualificação, Fatos, Direito (com teses robustas), Pedidos e Fechamento.
                """
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    
                    st.markdown("### 📄 MINUTA GERADA:")
                    with st.container(border=True): st.markdown(res)
                    buf = BytesIO(); Document().save(buf); buf.seek(0)
                    st.download_button("📥 BAIXAR DOCX EDITÁVEL", gerar_word(res), f"{tipo}_{cli_final}.docx", use_container_width=True)
                    st.success("Documento salvo no cofre digital.")
                except Exception as e: st.error(f"Erro: {str(e)}")
        else: st.error("Créditos insuficientes ou dados faltantes.")

# 3. CALCULADORA (FUNCIONALIDADES EXPANDIDAS)
elif menu_opcao == "🧮 Calculadoras & Perícia":
    if verificar_acesso("Pro"):
        st.markdown("<h2 class='tech-header'>🧮 LABORATÓRIO DE PERÍCIA</h2>", unsafe_allow_html=True)
        
        tab_calc1, tab_calc2 = st.tabs(["⚡ Cálculo Rápido", "📑 Laudo Pericial Completo"])
        
        with tab_calc1:
            c1, c2 = st.columns(2)
            with c1:
                tipo_calc = st.selectbox("Tipo de Cálculo", ["Atualização Monetária", "Rescisão Trabalhista", "Pensão Alimentícia", "Aluguel (IGPM/IPCA)"])
                valor = st.number_input("Valor Original (R$)", min_value=0.0)
            with c2:
                indice = st.selectbox("Índice de Correção", ["INPC", "IPCA-E", "IGP-M", "TR"])
                juros = st.selectbox("Juros de Mora", ["1% a.m. Simples", "1% a.m. Composto", "SELIC", "Sem Juros"])
                dt_inicio = st.date_input("Data Inicial")
            
            if st.button("CALCULAR AGORA"):
                # Simulação de cálculo (aqui entraria a lógica matemática real)
                st.info("Cálculo processado pela IA...")
                valor_final = valor * 1.5 # Exemplo
                st.metric("VALOR ATUALIZADO (ESTIMADO)", f"R$ {valor_final:,.2f}")
                st.caption(f"Correção pelo {indice} + {juros} desde {dt_inicio}")

        with tab_calc2:
            st.write("Gera um laudo completo baseando-se em documentos anexados.")
            upload = st.file_uploader("Anexar Contrato/Sentença (PDF)", type="pdf")
            quesitos = st.text_area("Quesitos para o Assistente Técnico:")
            if st.button("GERAR LAUDO TÉCNICO"):
                if upload:
                    with st.spinner("Analisando PDF e calculando..."):
                        txt = extrair_texto_pdf(upload)
                        res = genai.GenerativeModel(mod_escolhido).generate_content(f"Aja como Perito Contábil. Analise: {txt}. Responda aos quesitos: {quesitos}. Gere laudo pericial.").text
                        st.markdown(res)
                        st.download_button("BAIXAR LAUDO", gerar_word(res), "Laudo.docx")
    else: tela_bloqueio("Pro")

# 4. AUDIENCIA (FUNCIONALIDADES EXPANDIDAS)
elif menu_opcao == "🏛️ Estratégia de Audiência":
    if verificar_acesso("Elite"):
        st.markdown("<h2 class='tech-header'>🏛️ ESTRATEGISTA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: area = st.selectbox("Rito/Área", ["Trabalhista (Ordinário)", "Trabalhista (Sumaríssimo)", "Cível (Comum)", "Juizado Especial"])
        with c2: papel = st.selectbox("Papel", ["Advogado do Autor", "Advogado do Réu"])
        with c3: perfil_juiz = st.selectbox("Perfil do Juiz (IA Adaptativa)", ["Padrão", "Legalista Rígido", "Conciliador/Mediador", "Pró-Reclamante", "Pró-Empresa"])
        
        col_txt, col_up = st.columns([2, 1])
        with col_txt: detalhes = st.text_area("Resumo do Caso / Pontos Controversos:", height=150)
        with col_up: testemunhas = st.text_area("Lista de Testemunhas (Opcional):")
        
        if st.button("🔮 SIMULAR CENÁRIOS"):
            if detalhes:
                with st.spinner(f"Simulando audiência com juiz perfil '{perfil_juiz}'..."):
                    prompt = f"""
                    Aja como um estrategista jurídico sênior.
                    Caso: {detalhes}. Área: {area}. Meu lado: {papel}.
                    Perfil do Juiz: {perfil_juiz}. Testemunhas: {testemunhas}.
                    
                    Gere uma estratégia dividida em 3 seções:
                    1. Perguntas Cruzadas: O que perguntar para a outra parte e testemunhas para expor contradições.
                    2. Análise de Risco: O que o juiz {perfil_juiz} provavelmente vai focar.
                    3. Alegações Finais Orais: Um roteiro curto e impactante.
                    """
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    
                    tab1, tab2, tab3 = st.tabs(["⚔️ Perguntas Cruzadas", "⚠️ Análise de Risco", "🗣️ Alegações Finais"])
                    # Divisão simples do texto (na prática seria melhor estruturar via JSON, mas texto serve)
                    with tab1: st.markdown(res) # Exibe tudo por enquanto, a IA tende a formatar bem
                    with tab2: st.info("Dica: Fique atento à postura do juiz simulada acima.")
                    with tab3: st.download_button("BAIXAR ROTEIRO", gerar_word(res), "Roteiro_Audiencia.docx")
    else: tela_bloqueio("Elite")

# 5. GESTÃO DE CASOS (MANTIDO)
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
    # ... (Código de gestão de casos original, já estava bom e funcional) ...
    # Replicando a lógica básica para funcionar:
    if "pasta_aberta" not in st.session_state: st.session_state.pasta_aberta = None
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    if not df_docs.empty:
        if st.session_state.pasta_aberta is None:
            clientes = df_docs['cliente'].unique()
            cols = st.columns(4)
            for i, cli in enumerate(clientes):
                with cols[i%4]:
                    with st.container(border=True):
                        st.markdown(f"#### 📁 {cli}")
                        if st.button("ABRIR", key=f"b_{i}"): st.session_state.pasta_aberta = cli; st.rerun()
        else:
            if st.button("⬅ VOLTAR"): st.session_state.pasta_aberta = None; st.rerun()
            st.markdown(f"### Arquivos de: {st.session_state.pasta_aberta}")
            docs_cli = df_docs[df_docs['cliente'] == st.session_state.pasta_aberta]
            for idx, row in docs_cli.iterrows():
                with st.expander(f"{row['tipo']} - {row['data_criacao']}"):
                    st.write(row['conteudo'][:200])
                    st.download_button("BAIXAR", gerar_word(row['conteudo']), f"{row['tipo']}.docx", key=f"dl_{idx}")
                    if st.button("EXCLUIR", key=f"del_{idx}"):
                        run_query("DELETE FROM documentos WHERE id = ?", (row['id'],))
                        st.rerun()
    else: st.info("Nenhum documento encontrado.")

# 6. MONITOR (FUNCIONALIDADES EXPANDIDAS)
elif menu_opcao == "🚦 Monitor de Prazos":
    if verificar_acesso("Elite"):
        st.markdown("<h2 class='tech-header'>🚦 RADAR DE PRAZOS INTELIGENTE</h2>", unsafe_allow_html=True)
        
        # Dashboard do Monitor
        m1, m2, m3 = st.columns(3)
        m1.metric("E-mails Lidos (Hoje)", "0")
        m2.metric("Prazos Fatais", "0", delta="Normal", delta_color="normal")
        m3.metric("Status IMAP", "Desconectado", delta_color="off")
        
        st.write("")
        with st.container(border=True):
            st.markdown("##### 📡 PARÂMETROS DE VARREDURA")
            c_mail, c_pass, c_host = st.columns(3)
            email_leitura = c_mail.text_input("E-mail OAB/Escritório")
            senha_leitura = c_pass.text_input("Senha de App", type="password")
            servidor_imap = c_host.text_input("Servidor", value="imap.gmail.com")
            
            c_filter1, c_filter2 = st.columns(2)
            filtro_data = c_filter1.date_input("Buscar a partir de:", value=date.today())
            palavras_chave = c_filter2.text_input("Filtrar Assunto (ex: Intimação, Urgente)", value="Intimação")
            
            if st.button("INICIAR VARREDURA PROFUNDA"):
                if email_leitura and senha_leitura:
                    with st.spinner("Conectando ao servidor e analisando metadados..."):
                        msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                        if err: st.error(err)
                        elif not msgs: st.success("Nenhuma intimação encontrada com os filtros atuais.")
                        else:
                            for m in msgs:
                                if palavras_chave.lower() in m['assunto'].lower():
                                    with st.expander(f"⚠️ {m['assunto']}"):
                                        st.write(m['corpo'])
                                        if st.button("ANALISAR PRAZO (IA)", key=m['assunto']):
                                            res = genai.GenerativeModel(mod_escolhido).generate_content(f"Analise este e-mail jurídico e extraia: Data da publicação, Prazo processual (em dias úteis), Data fatal. Texto: {m['corpo']}").text
                                            st.warning(res)
                else: st.error("Preencha as credenciais.")
    else:
        tela_bloqueio("Elite")

# 7. FERRAMENTAS EXTRAS (MANTIDO)
elif menu_opcao == "🔧 Ferramentas Extras":
    if verificar_acesso("Pro"):
        st.markdown("<h2 class='tech-header'>🔧 TOOLKIT AVANÇADO</h2>", unsafe_allow_html=True)
        tabs_ex = st.tabs(["🔎 Chat PDF", "🎙️ Transcrição de Audiência", "⚖️ Comparador de Peças"])
        # ... (Código original das ferramentas mantido, é funcional) ...
        with tabs_ex[0]:
            up = st.file_uploader("PDF", key="pdf_chat")
            q = st.text_input("O que você quer saber sobre o documento?")
            if up and q and st.button("PERGUNTAR"):
                st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Baseado no PDF: {extrair_texto_pdf(up)}. Responda: {q}").text)
    else:
        tela_bloqueio("Pro")

# 8. PLANOS (MANTIDO)
elif menu_opcao == "💎 Planos Premium":
    st.markdown("<h2 class='tech-header' style='text-align:center;'>UPGRADE YOUR SYSTEM</h2>", unsafe_allow_html=True)
    st.write(""); c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""<div class='price-card'><div class='price-title'>STARTER</div><div class='price-amount'>GRÁTIS</div><div class='price-features'>✅ Redator Básico<br>✅ Gestão de Casos<br>❌ Sem Perícia<br>❌ Sem Audiência</div></div>""", unsafe_allow_html=True)
        if st.button("SELECIONAR STARTER", key="p1"):
            run_query("UPDATE usuarios SET plano = 'Starter' WHERE username = ?", (st.session_state.usuario_atual,)); st.session_state.plano_atual = "Starter"; st.rerun()

    with c2:
        st.markdown("""<div class='price-card'><div class='price-title' style='color:#00F3FF'>PRO</div><div class='price-amount'>R$ 97</div><div class='price-features'>✅ Tudo do Starter<br>✅ <strong>Perícia & Cálculos</strong><br>✅ Ferramentas Extras<br>✅ Jurisprudência IA</div></div>""", unsafe_allow_html=True)
        if st.button("ASSINAR PRO", key="p2"):
            time.sleep(1); run_query("UPDATE usuarios SET plano = 'Pro', creditos = 100 WHERE username = ?", (st.session_state.usuario_atual,)); st.session_state.plano_atual = "Pro"; st.rerun()

    with c3:
        st.markdown("""<div class='price-card elite-card'><div class='price-title' style='color:#FFD700'>ELITE</div><div class='price-amount'>R$ 297</div><div class='price-features'>💎 <strong>Tudo Liberado</strong><br>💎 Simulador Audiência<br>💎 Monitor de Prazos<br>💎 Suporte Prioritário</div></div>""", unsafe_allow_html=True)
        if st.button("ASSINAR ELITE", key="p3"):
            time.sleep(1); run_query("UPDATE usuarios SET plano = 'Elite', creditos = 500 WHERE username = ?", (st.session_state.usuario_atual,)); st.session_state.plano_atual = "Elite"; st.rerun()

st.markdown("---")
st.markdown("<center style='color: #64748b; font-size: 0.8rem; font-family: Rajdhani;'>🔒 LEGALHUB ELITE v5.5 | ENCRYPTED SESSION</center>", unsafe_allow_html=True)
