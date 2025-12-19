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

# --- CSS AVANÇADO (FUNDO SUAVE + CARDS DE PREÇO) ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');

        :root {
            --bg-dark: #020617;
            --bg-card: rgba(15, 23, 42, 0.6);
            --text-main: #FFFFFF;
            --neon-blue: #00F3FF;
            --neon-purple: #BC13FE;
            --neon-gold: #FFD700;
            --border-glow: 1px solid rgba(0, 243, 255, 0.2);
        }

        .stApp {
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(14, 165, 233, 0.08), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.08), transparent 25%);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
        }

        h1, h2, h3, h4, h5, h6 {
            color: #FFFFFF !important;
            font-family: 'Rajdhani', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }

        p, .stCaption, div[data-testid="caption"], div[data-testid="stMetricLabel"] label, div[data-testid="stMarkdownContainer"] p {
            color: #E2E8F0 !important;
            font-family: 'Inter', sans-serif;
        }
        
        div[data-testid="stMetricValue"] {
            color: var(--neon-blue) !important;
            text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        label { color: #CBD5E1 !important; }

        .tech-header {
            background: linear-gradient(90deg, #FFFFFF 0%, var(--neon-blue) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
            text-shadow: 0 0 20px rgba(0, 243, 255, 0.3);
        }

        /* --- CARDS DE PREÇO (NOVO) --- */
        .price-card {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .price-card:hover {
            transform: translateY(-5px);
            border-color: var(--neon-blue);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.2);
        }
        .price-title {
            font-family: 'Rajdhani';
            font-size: 1.5rem;
            font-weight: bold;
            color: #FFF;
            margin-bottom: 10px;
        }
        .price-amount {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--neon-blue);
            margin: 15px 0;
        }
        .price-features {
            text-align: left;
            font-size: 0.9rem;
            color: #CBD5E1;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        
        /* Destaque para o plano Elite */
        .elite-card {
            border: 1px solid var(--neon-gold);
            background: rgba(255, 215, 0, 0.05);
        }
        .elite-card .price-amount { color: var(--neon-gold); text-shadow: 0 0 10px rgba(255,215,0,0.5); }

        /* --- LOGOTIPO NO CABEÇALHO --- */
        .header-logo { display: flex; align-items: center; margin-right: 2rem; }
        .header-logo h1 { font-size: 1.8rem; margin: 0; letter-spacing: 2px; text-shadow: 0 0 10px rgba(0, 243, 255, 0.5); }
        .header-logo span { font-weight: 300; color: #fff; font-size: 1.2rem; }

        /* --- ANIMAÇÃO FLUTUANTE --- */
        @keyframes float {
            0%, 100% { transform: translateY(0px); filter: drop-shadow(0 5px 15px rgba(14, 165, 233, 0.2)); }
            50% { transform: translateY(-20px); filter: drop-shadow(0 25px 30px rgba(14, 165, 233, 0.5)); }
        }
        .floating-logo { animation: float 6s ease-in-out infinite; display: block; margin: 0 auto 30px auto; width: 250px; }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] { background-color: #020408; border-right: 1px solid rgba(0, 243, 255, 0.1); }

        /* --- BOTÕES --- */
        .stButton>button {
            background: transparent; color: var(--neon-blue); border: 1px solid var(--neon-blue); border-radius: 0px;
            padding: 0.6rem 1.2rem; font-family: 'Rajdhani', sans-serif; font-weight: 700; text-transform: uppercase;
            transition: all 0.3s ease; position: relative;
            clip-path: polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px);
        }
        .stButton>button:hover { background: var(--neon-blue); color: #000; box-shadow: 0 0 20px rgba(0, 243, 255, 0.6); }

        /* --- INPUTS --- */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: rgba(0, 0, 0, 0.3) !important; border: 1px solid #334155 !important; color: #FFF !important; border-radius: 0px; }
        .stTextInput>div>div>input:focus { border-color: var(--neon-blue) !important; box-shadow: 0 0 15px rgba(0, 243, 255, 0.1); }

        /* --- MENU HORIZONTAL --- */
        div[role="radiogroup"] { display: flex; justify-content: space-between; background: rgba(10, 15, 30, 0.8); padding: 10px; border-radius: 8px; border-bottom: 1px solid rgba(0, 243, 255, 0.3); }
        div[role="radiogroup"] label { background: transparent !important; border: none !important; margin: 0 !important; padding: 5px 15px !important; color: #94A3B8 !important; transition: all 0.3s; }
        div[role="radiogroup"] label:hover { color: #FFF !important; text-shadow: 0 0 5px #00F3FF; }
        div[role="radiogroup"] label[data-checked="true"] { color: #00F3FF !important; border-bottom: 2px solid #00F3FF !important; background: rgba(0, 243, 255, 0.1) !important; }
        div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p { font-size: 1rem !important; }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

local_css()

# ==========================================================
# 2. FUNÇÕES GERAIS (DB E IMAGEM)
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
    # Tabela Usuarios (Adicionado coluna 'plano')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'Starter')''')
    
    # Migrações para garantir que colunas existam se o banco já foi criado
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
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br', 5, 'Starter')")
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
    except Exception as e:
        conn.close()
        st.error(f"Erro no Banco de Dados: {e}")
        return None

init_db()

# ==========================================================
# 3. CONTROLE DE SESSÃO & LOGIN
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""
if "plano_atual" not in st.session_state: st.session_state.plano_atual = "Starter"

# Persistência F5 via URL
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

        st.markdown("""
            <div style='text-align: center;'>
                <h1 class='tech-header' style='font-size: 2.5rem; letter-spacing: 3px;'>LEGALHUB <span style='font-weight: 300; color: #fff;'>ELITE</span></h1>
                <p style='color: #00F3FF; font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase;'>Artificial Intelligence System</p>
            </div>
        """, unsafe_allow_html=True)
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
                    st.session_state.plano_atual = users.iloc[0]['plano'] # Carrega o plano
                    st.query_params["user"] = username
                    st.rerun()
                else: st.error("Acesso Negado.")
            st.markdown("<div style='text-align:center; margin-top:10px; color: #475569; font-size: 0.7rem; font-family: Rajdhani;'>SYSTEM V5.5 // SECURE</div>", unsafe_allow_html=True)

if not st.session_state.logado:
    login_screen()
    st.stop()

# ==========================================================
# 4. FUNÇÕES AUXILIARES
# ==========================================================
def buscar_jurisprudencia_real(tema):
    try:
        res = DDGS().text(f"{tema} (site:stf.jus.br OR site:stj.jus.br OR site:jusbrasil.com.br)", region="br-pt", max_results=4)
        return "\n".join([f"FONTE: {r['title']}\nLINK: {r['href']}\nRESUMO: {r['body']}\n" for r in res]) if res else "Nada encontrado."
    except: return "Erro na busca."

def gerar_word(texto):
    doc = Document()
    for p in texto.split('\n'):
        if p.strip(): doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def extrair_texto_pdf(arquivo):
    try: return "".join([p.extract_text() for p in PdfReader(arquivo).pages])
    except: return ""

def buscar_intimacoes_email(user, pwd, server):
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, pwd)
        mail.select("inbox")
        status, msgs = mail.search(None, '(UNSEEN)')
        if not msgs[0]: return [], "Nada novo."
        found = []
        for e_id in msgs[0].split()[-5:]:
            res, data = mail.fetch(e_id, "(RFC822)")
            for response in data:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subj = decode_header(msg["Subject"])[0][0]
                    if isinstance(subj, bytes): subj = subj.decode()
                    termos = ["intimação", "processo", "movimentação"]
                    if any(t in str(subj).lower() for t in termos):
                        found.append({"assunto": subj, "corpo": str(msg)[:2000]})
        return found, None
    except Exception as e: return [], str(e)

# ==========================================================
# 5. APP PRINCIPAL
# ==========================================================
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.text_input("🔑 API Key (Insira no painel lateral para salvar):", type="password")

if api_key:
    genai.configure(api_key=api_key)
    try:
        mods = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        mod_escolhido = "models/gemini-1.5-flash" if "models/gemini-1.5-flash" in mods else mods[0]
    except: mod_escolhido = "models/gemini-1.5-flash"

# Atualiza dados do usuário a cada reload
df_user = run_query("SELECT creditos, plano FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
if not df_user.empty:
    creditos_atuais = df_user.iloc[0]['creditos']
    st.session_state.plano_atual = df_user.iloc[0]['plano']
else:
    creditos_atuais = 0

# --- CONTROLE DE NAVEGAÇÃO ---
if "navegacao_override" not in st.session_state:
    st.session_state.navegacao_override = None

# --- CABEÇALHO HORIZONTAL ---
col_logo, col_menu = st.columns([1, 4])
with col_logo:
    st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)

with col_menu:
    mapa_nav = {
        "Dashboard": "📊 Dashboard",
        "Redator IA": "✍️ Redator Jurídico", 
        "Perícia & Calc": "🧮 Calculadoras & Perícia",
        "Audiência": "🏛️ Estratégia de Audiência",
        "Gestão Casos": "📂 Gestão de Casos",
        "Monitor Prazos": "🚦 Monitor de Prazos",
        "Assinatura": "💎 Planos Premium" # NOVO ITEM DE MENU
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

# --- SIDEBAR (PERFIL) ---
with st.sidebar:
    img_base64 = get_base64_of_bin_file("diagrama-ia.png")
    if img_base64:
        st.markdown(f'<img src="data:image/png;base64,{img_base64}" style="width:100%; margin-bottom: 20px;">', unsafe_allow_html=True)

    st.markdown("<h2 class='tech-header' style='font-size:1.5rem;'>CONFIGURAÇÕES</h2>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0;'>Usuário: {st.session_state.usuario_atual}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0; margin-bottom: 20px;'>Escritório: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    
    # Exibe o plano atual
    plano_cor = "#FFD700" if st.session_state.plano_atual == "Elite" else "#00F3FF"
    st.markdown(f"<div style='border:1px solid {plano_cor}; padding:5px; border-radius:5px; text-align:center; color:{plano_cor}; margin-bottom:15px;'>PLANO: {st.session_state.plano_atual.upper()}</div>", unsafe_allow_html=True)

    if "GOOGLE_API_KEY" not in st.secrets:
        st.text_input("🔑 API Key (Google Gemini):", type="password", key="sidebar_api_key")
        if st.session_state.sidebar_api_key:
             genai.configure(api_key=st.session_state.sidebar_api_key)
             st.success("API Key configurada.")

    st.markdown("---")
    st.markdown("<h4 style='font-size:1rem; color:#94A3B8;'>CRÉDITOS</h4>", unsafe_allow_html=True)
    c_cr1, c_cr2 = st.columns([1, 3])
    with c_cr1: st.markdown("<h3 style='color:#0EA5E9; margin:0;'>💎</h3>", unsafe_allow_html=True)
    with c_cr2: st.markdown(f"<h3 style='margin:0; color:#FFFFFF;'>{creditos_atuais}</h3>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/100, 1.0))
    
    st.write("")
    if st.button("LOGOUT / SAIR"):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

    if st.session_state.usuario_atual == 'admin':
        st.markdown("---")
        with st.expander("🛠️ ADMIN"):
            novo_user = st.text_input("User")
            novo_pass = st.text_input("Pass", type="password")
            novo_banca = st.text_input("Banca")
            if st.button("CRIAR"):
                run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (?, ?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50, "Starter"))
                st.success("OK")

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    img_base64 = get_base64_of_bin_file("diagrama-ia.png")
    if img_base64:
        st.markdown(f"""<div style="display: flex; justify-content: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo" style="width: 200px;"></div>""", unsafe_allow_html=True)

    st.
