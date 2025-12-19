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
        p, .stCaption, label { color: #E2E8F0 !important; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetricValue"] { color: var(--neon-blue) !important; text-shadow: 0 0 10px rgba(0, 243, 255, 0.5); }
        .tech-header { background: linear-gradient(90deg, #FFFFFF 0%, var(--neon-blue) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 700; }

        /* CARDS DE PREÇO */
        .price-card { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.3s ease; }
        .price-card:hover { transform: translateY(-5px); border-color: var(--neon-blue); box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); }
        .price-title { font-family: 'Rajdhani'; font-size: 1.5rem; font-weight: bold; color: #FFF; margin-bottom: 10px; }
        .price-amount { font-size: 2.5rem; font-weight: 800; color: var(--neon-blue); margin: 15px 0; }
        .elite-card { border: 1px solid var(--neon-gold); background: rgba(255, 215, 0, 0.05); }
        .elite-card .price-amount { color: var(--neon-gold); text-shadow: 0 0 10px rgba(255,215,0,0.5); }

        /* TELA DE BLOQUEIO */
        .lock-screen {
            border: 1px solid var(--neon-red);
            background: rgba(255, 0, 85, 0.05);
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            margin-top: 50px;
        }
        .lock-icon { font-size: 3rem; margin-bottom: 10px; }
        .lock-title { color: var(--neon-red) !important; font-family: 'Rajdhani'; font-size: 2rem; font-weight: bold; }
        .lock-desc { color: #E2E8F0; margin-bottom: 20px; }

        /* OUTROS ELEMENTOS */
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
    except FileNotFoundError:
        return None

def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    # Tabela Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'Starter')''')
    
    # Migrações seguras
    try: c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except: pass
    try: c.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT DEFAULT 'Starter'")
    except: pass
    
    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)''')
    
    # Usuários Padrão
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
        else:
            conn.commit()
            conn.close()
            return True
    except Exception:
        conn.close()
        return None

init_db()

# ==========================================================
# 3. LÓGICA DE ACESSO E PLANOS
# ==========================================================
NIVEIS_PLANO = {"Starter": 1, "Pro": 2, "Elite": 3}

def verificar_acesso(plano_minimo):
    plano_usuario = st.session_state.get('plano_atual', 'Starter')
    nivel_usuario = NIVEIS_PLANO.get(plano_usuario, 1)
    nivel_necessario = NIVEIS_PLANO.get(plano_minimo, 1)
    return nivel_usuario >= nivel_necessario

def tela_bloqueio(plano_necessario):
    st.markdown(f"""
    <div class='lock-screen'>
        <div class='lock-icon'>🔒</div>
        <div class='lock-title'>ACCESS DENIED</div>
        <p class='lock-desc'>Esta ferramenta é exclusiva para membros <strong>{plano_necessario.upper()}</strong> ou superior.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_b1, col_b2, col_b3 = st.columns([1,2,1])
    with col_b2:
        if st.button(f"🚀 FAZER UPGRADE PARA {plano_necessario.upper()}", use_container_width=True):
            st.session_state.navegacao_override = "💎 Planos Premium"
            st.rerun()

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
        if img_base64:
            st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo"></div>""", unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)

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

# --- NAVEGAÇÃO ---
if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)

with col_menu:
    mapa_nav = {
        "Dashboard": "📊 Dashboard",
        "Redator IA": "✍️ Redator Jurídico", 
        "Perícia & Calc": "🧮 Calculadoras & Perícia",
        "Audiência": "🏛️ Estratégia de Audiência",
        "Gestão Casos": "📂 Gestão de Casos",
        "Monitor Prazos": "🚦 Monitor de Prazos",
        "Assinatura": "💎 Planos Premium"
    }
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
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0;'>User: {st.session_state.usuario_atual}</div>", unsafe_allow_html=True)
    
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
    if st.button("LOGOUT"):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

    if st.session_state.usuario_atual == 'admin':
        with st.expander("🛠️ ADMIN"):
            if st.button("Add 50 Créditos"): run_query("UPDATE usuarios SET creditos = creditos + 50 WHERE username = ?", (st.session_state.usuario_atual,)); st.rerun()

# ==========================================================
# LÓGICA DAS TELAS (COM LIMITAÇÃO DE PLANOS)
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
            st.markdown("#### ✍️ REDATOR")
            if st.button("ABRIR", key="d_redator"): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r1c2:
        with st.container(border=True):
            st.markdown("#### 🧮 PERÍCIA")
            if st.button("ABRIR", key="d_pericia"): st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"; st.rerun()
    with r1c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ AUDIÊNCIA")
            if st.button("ABRIR", key="d_aud"): st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"; st.rerun()

    st.write("")
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.markdown("##### 📈 DADOS DE PRODUTIVIDADE")
        with st.container(border=True):
            df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
            if not df_areas.empty:
                colors_tech = ['#00F3FF', '#BC13FE', '#2E5CFF', '#FFFFFF', '#4A4A4A']
                fig = px.pie(df_areas, values='qtd', names='area', hole=0.7, color_discrete_sequence=colors_tech)
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0", showlegend=True, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Aguardando dados...")
    
    with col_info:
        st.markdown("##### 🛡️ SECURITY & COMPLIANCE")
        with st.container(border=True):
            st.markdown("""
            <div style='background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10B981; padding: 10px; margin-bottom: 8px; border-radius: 4px;'>
                <strong style='color: #10B981; font-family: Rajdhani;'>✓ LGPD COMPLIANT</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Dados anonimizados.</span>
            </div>
            <div style='background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3B82F6; padding: 10px; margin-bottom: 8px; border-radius: 4px;'>
                <strong style='color: #3B82F6; font-family: Rajdhani;'>🔒 E2E ENCRYPTION</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Criptografia Militar.</span>
            </div>
            <div style='background: rgba(245, 158, 11, 0.1); border-left: 3px solid #F59E0B; padding: 10px; border-radius: 4px;'>
                <strong style='color: #F59E0B; font-family: Rajdhani;'>⚖️ LIVE JURISPRUDENCE</strong><br><span style='font-size: 0.8rem; color: #E2E8F0;'>Sincronia STF/STJ.</span>
            </div>
            """, unsafe_allow_html=True)

# 2. REDATOR (LIBERADO PARA TODOS)
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA</h2>", unsafe_allow_html=True)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    # Busca clientes existentes
    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    with col_config:
        st.markdown("##### ⚙️ PARÂMETROS")
        tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Contrato", "Parecer"])
        area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família"])
        
        # Limitação: Apenas PRO/Elite podem usar Jurisprudência Automática
        web_disabled = not verificar_acesso("Pro")
        web = st.checkbox("Jurisprudência Web (PRO)", value=not web_disabled, disabled=web_disabled)
        if web_disabled: st.caption("🔒 Upgrade para PRO para liberar.")
        
        # --- SELETOR DE CLIENTE (RESTAURADO) ---
        st.markdown("##### 👤 CLIENTE")
        modo_cliente = st.radio("Seleção:", ["Existente", "Novo"], horizontal=True, label_visibility="collapsed")
        
        cli_final = ""
        if modo_cliente == "Existente":
            if lista_clientes:
                idx = 0
                if st.session_state.cliente_recuperado in lista_clientes:
                    idx = lista_clientes.index(st.session_state.cliente_recuperado)
                cli_final = st.selectbox("Nome:", lista_clientes, index=idx)
            else:
                st.warning("Sem registros.")
                cli_final = st.text_input("Nome do Novo Cliente:")
        else:
            cli_final = st.text_input("Nome do Novo Cliente:")
        # ----------------------------------------

    with col_input:
        fatos = st.text_area("Fatos do Caso", height=300)
    
    if st.button("GERAR PEÇA (1 CRÉDITO)"):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner("Gerando..."):
                time.sleep(2) # Simulação
                prompt = f"Peça: {tipo}. Área: {area}. Fatos: {fatos}. Jurisp: {web}"
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    st.markdown(res)
                    buf = BytesIO(); Document().save(buf); buf.seek(0)
                    st.download_button("BAIXAR DOCX", buf, "minuta.docx")
                    st.rerun()
                except: st.error("Erro na IA ou API Key.")
        else: st.error("Sem créditos ou dados.")

# 3. CALCULADORA (APENAS PRO+)
elif menu_opcao == "🧮 Calculadoras & Perícia":
    if verificar_acesso("Pro"):
        st.markdown("<h2 class='tech-header'>🧮 LABORATÓRIO DE PERÍCIA</h2>", unsafe_allow_html=True)
        tipo_calc = st.selectbox("Cálculo", ["Trabalhista", "Cível", "Revisional"])
        dados = st.text_area("Dados Financeiros")
        if st.button("CALCULAR"):
            st.info("Funcionalidade de cálculo ativa.")
    else:
        tela_bloqueio("Pro")

# 4. AUDIENCIA (APENAS ELITE)
elif menu_opcao == "🏛️ Estratégia de Audiência":
    if verificar_acesso("Elite"):
        st.markdown("<h2 class='tech-header'>🏛️ SIMULADOR DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
        obs = st.text_area("Caso")
        if st.button("SIMULAR"):
            st.info("Simulação de audiência ativa.")
    else:
        tela_bloqueio("Elite")

# 5. GESTÃO DE CASOS (LIBERADO PARA TODOS)
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    if not df_docs.empty:
        for index, row in df_docs.iterrows():
            with st.expander(f"{row['tipo']} - {row['cliente']}"):
                st.write(row['conteudo'][:100] + "...")
    else: st.info("Nenhum caso arquivado.")

# 6. MONITOR (APENAS ELITE)
elif menu_opcao == "🚦 Monitor de Prazos":
    if verificar_acesso("Elite"):
        st.markdown("<h2 class='tech-header'>🚦 RADAR DE PRAZOS</h2>", unsafe_allow_html=True)
        st.text_input("Email Monitorado")
        if st.button("ESCANEAR"):
            st.info("Scanner ativo (Simulação).")
    else:
        tela_bloqueio("Elite")

# 7. FERRAMENTAS EXTRAS (APENAS PRO+)
elif menu_opcao == "🔧 Ferramentas Extras":
    if verificar_acesso("Pro"):
        st.markdown("<h2 class='tech-header'>🔧 TOOLKIT AVANÇADO</h2>", unsafe_allow_html=True)
        st.selectbox("Ferramenta", ["Chat PDF", "Comparador", "Transcrição"])
    else:
        tela_bloqueio("Pro")

# 8. PLANOS (VENDA)
elif menu_opcao == "💎 Planos Premium":
    st.markdown("<h2 class='tech-header' style='text-align:center;'>UPGRADE YOUR SYSTEM</h2>", unsafe_allow_html=True)
    st.write("")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""<div class='price-card'><div class='price-title'>STARTER</div><div class='price-amount'>GRÁTIS</div>
        <div class='price-features'>✅ Redator Básico<br>✅ Gestão de Casos<br>❌ Sem Perícia<br>❌ Sem Audiência</div></div>""", unsafe_allow_html=True)
        if st.button("PLANO ATUAL" if st.session_state.plano_atual == "Starter" else "DOWNGRADE", key="p1"):
            run_query("UPDATE usuarios SET plano = 'Starter' WHERE username = ?", (st.session_state.usuario_atual,))
            st.rerun()

    with c2:
        st.markdown("""<div class='price-card'><div class='price-title' style='color:#00F3FF'>PRO</div><div class='price-amount'>R$ 97</div>
        <div class='price-features'>✅ Tudo do Starter<br>✅ <strong>Perícia & Cálculos</strong><br>✅ Ferramentas Extras<br>✅ Jurisprudência IA</div></div>""", unsafe_allow_html=True)
        if st.button("ATIVO" if st.session_state.plano_atual == "Pro" else "ASSINAR PRO", key="p2"):
            with st.spinner("Processando..."):
                time.sleep(1)
                run_query("UPDATE usuarios SET plano = 'Pro', creditos = creditos + 50 WHERE username = ?", (st.session_state.usuario_atual,))
                st.rerun()

    with c3:
        st.markdown("""<div class='price-card elite-card'><div class='price-title' style='color:#FFD700'>ELITE</div><div class='price-amount'>R$ 297</div>
        <div class='price-features'>💎 <strong>Tudo Liberado</strong><br>💎 Simulador Audiência<br>💎 Monitor de Prazos<br>💎 Suporte Prioritário</div></div>""", unsafe_allow_html=True)
        if st.button("ATIVO" if st.session_state.plano_atual == "Elite" else "ASSINAR ELITE", key="p3"):
            with st.spinner("Validando Elite..."):
                time.sleep(1)
                run_query("UPDATE usuarios SET plano = 'Elite', creditos = creditos + 200 WHERE username = ?", (st.session_state.usuario_atual,))
                st.rerun()

st.markdown("---")
st.markdown("<center style='color: #64748b; font-size: 0.8rem; font-family: Rajdhani;'>🔒 LEGALHUB ELITE v5.5 | ENCRYPTED SESSION</center>", unsafe_allow_html=True)
