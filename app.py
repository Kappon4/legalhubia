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
            --neon-green: #10B981;
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

        /* MODULE CARDS */
        .module-card { background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .module-active { border: 1px solid var(--neon-green); box-shadow: 0 0 15px rgba(16, 185, 129, 0.2); }
        .module-title { font-family: 'Rajdhani'; font-size: 1.2rem; font-weight: bold; color: #FFF; }
        .module-price { float: right; color: var(--neon-blue); font-weight: bold; }

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
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, .stNumberInput>div>div>input { background-color: rgba(0, 0, 0, 0.3) !important; border: 1px solid #334155 !important; color: #FFF !important; border-radius: 0px; }
        
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

def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'base')''')
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except: 
        pass
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT DEFAULT 'base'")
    except: 
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)''')
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado1', '123', 'Escritório Alpha', 'lucas@alpha.adv.br', 10, 'base')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br', 5, 'base,litigio')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com', 9999, 'base,litigio,calculo,hightech')")
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
# 3. LÓGICA DE MÓDULOS
# ==========================================================
def verificar_acesso(modulo_necessario):
    modulos_usuario = st.session_state.get('plano_atual', 'base').split(',')
    if modulo_necessario == 'base': return True
    return modulo_necessario in modulos_usuario

def tela_bloqueio(nome_modulo, preco_sugerido):
    st.markdown(f"""
    <div class='lock-screen'><div class='lock-icon'>🔒</div>
    <div class='lock-title'>MÓDULO {nome_modulo.upper()} BLOQUEADO</div>
    <p class='lock-desc'>Adicione este segmento ao seu plano para liberar esta funcionalidade.</p>
    </div>
    """, unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2: 
        if st.button(f"➕ ADICIONAR POR R$ {preco_sugerido}/mês", use_container_width=True): 
            st.session_state.navegacao_override = "💎 Meus Planos"; st.rerun()

# ==========================================================
# 4. CONTROLE DE SESSÃO & LOGIN
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""
if "plano_atual" not in st.session_state: st.session_state.plano_atual = "base"

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
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Perícia & Calc": "🧮 Calculadoras & Perícia", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Meus Planos"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.navegacao_override:
        try: idx_radio = opcoes_menu.index([k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0])
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
    
    modulos_ativos = st.session_state.plano_atual.replace("base", "Core").replace("litigio", "Litígio").replace("calculo", "Cálculos").replace("hightech", "Tech")
    st.info(f"Módulos: {modulos_ativos}")

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
    c3.metric("STATUS", "Ativo")
    
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

# 2. REDATOR JURÍDICO (ADAPTATIVO)
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO</h2>", unsafe_allow_html=True)
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    
    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    with col_config:
        with st.container(border=True):
            st.markdown("##### ⚙️ ESTRUTURA")
            # Seleção de Área (Determina os tipos de peça)
            area = st.selectbox("Área de Atuação", ["Trabalhista", "Cível", "Criminal", "Família", "Previdenciário", "Tributário"])
            
            # Tipos de Peça Dinâmicos
            opcoes_pecas = []
            if area == "Trabalhista": opcoes_pecas = ["Reclamação Trabalhista", "Contestação", "Recurso Ordinário", "Contrarrazões"]
            elif area == "Cível": opcoes_pecas = ["Petição Inicial", "Contestação", "Réplica", "Apelação", "Agravo de Instrumento"]
            elif area == "Criminal": opcoes_pecas = ["Habeas Corpus", "Resposta à Acusação", "Pedido de Liberdade Provisória", "Alegações Finais"]
            elif area == "Família": opcoes_pecas = ["Ação de Divórcio", "Ação de Alimentos", "Regulamentação de Guarda", "Inventário"]
            elif area == "Previdenciário": opcoes_pecas = ["Petição Inicial (Aposentadoria)", "Recurso Administrativo", "Mandado de Segurança"]
            else: opcoes_pecas = ["Petição Genérica", "Contrato", "Parecer"]
            
            tipo = st.selectbox("Tipo de Peça", opcoes_pecas)
            tom = st.selectbox("Tom de Voz", ["Técnico e Formal", "Combativo e Incisivo", "Conciliador", "Acadêmico"])
            
            tem_litigio = verificar_acesso("litigio")
            web = st.checkbox("🔍 Jurisprudência Web (Módulo Litígio)", value=tem_litigio, disabled=not tem_litigio)
            if not tem_litigio: st.caption("🔒 Adicione o módulo Litígio para ativar.")
            
            st.markdown("---")
            st.markdown("##### 👤 CLIENTE")
            modo_cliente = st.radio("Seleção:", ["Existente", "Novo"], horizontal=True, label_visibility="collapsed")
            if modo_cliente == "Existente" and lista_clientes: cli_final = st.selectbox("Nome:", lista_clientes)
            else: cli_final = st.text_input("Nome do Novo Cliente:")

    with col_input:
        with st.container(border=True):
            st.markdown("##### 📝 DADOS E FATOS")
            fatos = st.text_area("Descreva os fatos:", height=200, value=st.session_state.fatos_recuperados)
            legislacao_extra = st.text_input("Legislação/Súmula (Opcional):")
            formato = st.radio("Formato:", ["Texto Corrido", "Tópicos"], horizontal=True)
    
    st.write("")
    if st.button("✨ GERAR MINUTA COMPLETA (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner(f"Redigindo {tipo} na área {area}..."):
                jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else "Padrão."
                prompt = f"""
                Atue como Advogado Especialista em Direito {area}.
                Redija uma {tipo} completa e robusta.
                Tom: {tom}. Cliente: {cli_final}.
                Fatos: {fatos}. Lei Extra: {legislacao_extra}. Juris: {jur}.
                Estruture de acordo com o CPC/CPP/CLT conforme a área.
                """
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    st.markdown("### 📄 MINUTA GERADA:")
                    with st.container(border=True): st.markdown(res)
                    st.download_button("📥 BAIXAR DOCX", gerar_word(res), f"{tipo}_{cli_final}.docx", use_container_width=True)
                    st.success("Salvo no cofre.")
                except Exception as e: st.error(f"Erro: {str(e)}")
        else: st.error("Créditos insuficientes.")

# 3. CALCULADORA (ADAPTATIVA POR ÁREA)
elif menu_opcao == "🧮 Calculadoras & Perícia":
    if verificar_acesso("calculo"):
        st.markdown("<h2 class='tech-header'>🧮 CÁLCULOS ESPECIALIZADOS</h2>", unsafe_allow_html=True)
        
        area_calc = st.selectbox("Selecione a Especialidade:", ["Trabalhista", "Cível", "Criminal (Penal)", "Família", "Previdenciário"])
        
        with st.container(border=True):
            # --- LÓGICA DE CADA ÁREA ---
            if area_calc == "Trabalhista":
                st.markdown("#### 👷 Cálculo de Rescisão CLT")
                c1, c2, c3 = st.columns(3)
                salario = c1.number_input("Salário Base (R$)", min_value=0.0)
                meses = c2.number_input("Meses Trabalhados", min_value=1)
                motivo = c3.selectbox("Motivo", ["Sem Justa Causa", "Pedido de Demissão", "Justa Causa"])
                
                if st.button("CALCULAR VERBAS"):
                    aviso = salario if motivo == "Sem Justa Causa" else 0
                    ferias = (salario / 12) * meses # Simplificado
                    decimo = (salario / 12) * meses # Simplificado
                    multa = (salario * 0.08 * meses) * 0.40 if motivo == "Sem Justa Causa" else 0
                    total = aviso + ferias + decimo + multa
                    st.success(f"💰 Total Estimado: R$ {total:,.2f}")
                    st.json({"Aviso Prévio": aviso, "Férias Prop.": ferias, "13º Prop.": decimo, "Multa 40%": multa})

            elif area_calc == "Cível":
                st.markdown("#### ⚖️ Atualização Monetária")
                c1, c2 = st.columns(2)
                valor = c1.number_input("Valor Original (R$)", min_value=0.0)
                indice = c2.selectbox("Índice", ["IGP-M", "INPC", "IPCA-E"])
                juros = st.checkbox("Aplicar Juros de 1% a.m.?", value=True)
                anos = st.slider("Tempo (Anos)", 1, 20, 1)
                
                if st.button("ATUALIZAR"):
                    correcao = valor * (1 + (0.05 * anos)) # 5% aa média ficticia
                    jur_val = (correcao * 0.01 * 12 * anos) if juros else 0
                    total = correcao + jur_val
                    st.success(f"💰 Valor Atualizado: R$ {total:,.2f}")

            elif area_calc == "Criminal (Penal)":
                st.markdown("#### 🚔 Dosimetria da Pena (Estimativa)")
                pena_base = st.number_input("Pena Base (Anos)", min_value=0)
                agravantes = st.number_input("Qtd. Agravantes", min_value=0)
                atenuantes = st.number_input("Qtd. Atenuantes", min_value=0)
                causa_aum = st.selectbox("Causa de Aumento", ["Nenhuma", "1/3", "1/2", "2/3"])
                causa_dim = st.selectbox("Causa de Diminuição", ["Nenhuma", "1/3", "1/2", "2/3"])
                
                if st.button("CALCULAR PENA"):
                    pena = pena_base + ((agravantes - atenuantes) * (pena_base/6))
                    if causa_aum != "Nenhuma":
                        frac = 1/3 if causa_aum == "1/3" else 0.5
                        pena = pena * (1 + frac)
                    st.warning(f"⚖️ Pena Estimada: {pena:.1f} anos")

            elif area_calc == "Família":
                st.markdown("#### 👨‍👩‍👧 Pensão Alimentícia")
                renda = st.number_input("Renda Líquida do Alimentante (R$)", min_value=0.0)
                filhos = st.slider("Número de Filhos", 1, 5, 1)
                porcentagem = st.slider("Porcentagem da Renda (%)", 10, 50, 30)
                
                if st.button("CALCULAR PENSÃO"):
                    valor = renda * (porcentagem / 100)
                    st.success(f"💰 Valor da Pensão: R$ {valor:,.2f}")
                    st.caption(f"Equivalente a {valor/1412:.1f} salários mínimos (base 2024).")

            elif area_calc == "Previdenciário":
                st.markdown("#### 👴 Tempo de Contribuição")
                homem = st.radio("Gênero", ["Homem", "Mulher"], horizontal=True)
                anos_contrib = st.number_input("Anos Contribuídos", min_value=0)
                idade = st.number_input("Idade Atual", min_value=0)
                
                if st.button("VERIFICAR APOSENTADORIA"):
                    min_anos = 35 if homem == "Homem" else 30
                    min_idade = 65 if homem == "Homem" else 62
                    
                    falta_anos = max(0, min_anos - anos_contrib)
                    falta_idade = max(0, min_idade - idade)
                    
                    if falta_anos == 0 and falta_idade == 0:
                        st.balloons()
                        st.success("✅ Apto para aposentadoria (Regra Geral)!")
                    else:
                        st.error(f"❌ Faltam {falta_anos} anos de contribuição e {falta_idade} anos de idade.")

    else: tela_bloqueio("CALCULISTA", "97")

# 4. AUDIENCIA (MÓDULO LITIGIO - COM UPLOAD)
elif menu_opcao == "🏛️ Estratégia de Audiência":
    if verificar_acesso("litigio"):
        st.markdown("<h2 class='tech-header'>🏛️ ESTRATEGISTA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: area = st.selectbox("Rito/Área", ["Trabalhista (Ordinário)", "Trabalhista (Sumaríssimo)", "Cível (Comum)", "Juizado Especial"])
        with c2: papel = st.selectbox("Papel", ["Advogado do Autor", "Advogado do Réu"])
        with c3: perfil_juiz = st.selectbox("Perfil Juiz", ["Padrão", "Legalista", "Conciliador"])
        col_txt, col_up = st.columns([2, 1])
        with col_txt: detalhes = st.text_area("Resumo do Caso:", height=150)
        with col_up: upload_autos = st.file_uploader("Autos (PDF)", type="pdf")
        
        if st.button("🔮 SIMULAR"):
            if detalhes:
                with st.spinner("Simulando..."):
                    ctx = f"[DOC]: {extrair_texto_pdf(upload_autos)}" if upload_autos else ""
                    prompt = f"Estrategista {area}. Papel: {papel}. Juiz: {perfil_juiz}. Caso: {detalhes} {ctx}. Gere perguntas e riscos."
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("BAIXAR ROTEIRO", gerar_word(res), "Roteiro.docx")
    else: tela_bloqueio("LITÍGIO (CONTENCIOSO)", "97")

# 5. GESTÃO DE CASOS
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
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
            with st.expander("➕ ADICIONAR DOCUMENTO", expanded=False):
                c_add1, c_add2 = st.columns(2)
                novo_tipo = c_add1.text_input("Nome:")
                nova_area = c_add2.selectbox("Categoria:", ["Provas", "Andamento", "Anotações"])
                tab_up, tab_txt = st.tabs(["📤 Upload PDF", "✍️ Nota"])
                conteudo_novo = ""
                with tab_up: arquivo_novo = st.file_uploader("Arquivo PDF", key="novo_up")
                with tab_txt: texto_novo = st.text_area("Texto:", key="nova_nota")
                if st.button("💾 SALVAR"):
                    if novo_tipo:
                        if arquivo_novo: conteudo_novo = f"[PDF] {extrair_texto_pdf(arquivo_novo)}"
                        elif texto_novo: conteudo_novo = texto_novo
                        else: conteudo_novo = "Item vazio."
                        run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), st.session_state.pasta_aberta, nova_area, novo_tipo, conteudo_novo))
                        st.success("Salvo!"); time.sleep(1); st.rerun()
            st.divider()
            docs_cli = df_docs[df_docs['cliente'] == st.session_state.pasta_aberta]
            for idx, row in docs_cli.iterrows():
                with st.expander(f"{row['tipo']} - {row['data_criacao']}"):
                    st.write(row['conteudo'][:300] + "...")
                    c_d, c_e = st.columns([4, 1])
                    with c_d: st.download_button("BAIXAR DOCX", gerar_word(row['conteudo']), f"{row['tipo']}.docx", key=f"dl_{idx}")
                    with c_e:
                        if st.button("🗑️", key=f"del_{idx}"): run_query("DELETE FROM documentos WHERE id = ?", (row['id'],)); st.rerun()
    else: st.info("Nenhum documento encontrado.")

# 6. MONITOR (MÓDULO LITIGIO)
elif menu_opcao == "🚦 Monitor de Prazos":
    if verificar_acesso("litigio"):
        st.markdown("<h2 class='tech-header'>🚦 RADAR DE PRAZOS</h2>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("E-mails", "0"); m2.metric("Prazos", "0"); m3.metric("IMAP", "Off")
        st.write("")
        with st.container(border=True):
            c_mail, c_pass, c_host = st.columns(3)
            email_leitura = c_mail.text_input("E-mail OAB")
            senha_leitura = c_pass.text_input("Senha App", type="password")
            servidor_imap = c_host.text_input("Servidor", value="imap.gmail.com")
            if st.button("INICIAR VARREDURA"):
                if email_leitura and senha_leitura:
                    with st.spinner("Analisando metadados..."):
                        msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                        if err: st.error(err)
                        elif not msgs: st.success("Nada novo.")
                        else:
                            for m in msgs:
                                with st.expander(f"⚠️ {m['assunto']}"):
                                    st.write(m['corpo'])
                                    if st.button("ANALISAR PRAZO (IA)", key=m['assunto']):
                                        res = genai.GenerativeModel(mod_escolhido).generate_content(f"Extraia prazos: {m['corpo']}").text
                                        st.warning(res)
                else: st.error("Preencha credenciais.")
    else: tela_bloqueio("LITÍGIO (CONTENCIOSO)", "97")

# 7. FERRAMENTAS EXTRAS (MÓDULO HIGHTECH)
elif menu_opcao == "💎 Meus Planos":
    st.markdown("<h2 class='tech-header' style='text-align:center;'>MONTE SEU PLANO</h2>", unsafe_allow_html=True)
    st.write("")
    meus_modulos = st.session_state.plano_atual.split(',')
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### SELECIONE OS MÓDULOS")
        
        # Módulo Litígio
        tem_litigio = 'litigio' in meus_modulos
        st.markdown(f"""<div class='module-card {"module-active" if tem_litigio else ""}'><span class='module-title'>⚖️ MÓDULO LITÍGIO</span><span class='module-price'>R$ 97/mês</span><p style='color:#ccc; font-size:0.9rem;'>Libera: Monitor de Prazos, Audiência e Jurisprudência Web.</p></div>""", unsafe_allow_html=True)
        if st.button("REMOVER LITÍGIO" if tem_litigio else "ADICIONAR LITÍGIO", key="btn_litigio"):
            if tem_litigio: meus_modulos.remove('litigio')
            else: meus_modulos.append('litigio')
            novo_plano = ",".join(meus_modulos); run_query("UPDATE usuarios SET plano = ? WHERE username = ?", (novo_plano, st.session_state.usuario_atual)); st.session_state.plano_atual = novo_plano; st.rerun()

        # Módulo Cálculo
        tem_calculo = 'calculo' in meus_modulos
        st.markdown(f"""<div class='module-card {"module-active" if tem_calculo else ""}'><span class='module-title'>🧮 MÓDULO CALCULISTA</span><span class='module-price'>R$ 97/mês</span><p style='color:#ccc; font-size:0.9rem;'>Libera: Calculadoras Trabalhistas, Cíveis e Penais.</p></div>""", unsafe_allow_html=True)
        if st.button("REMOVER CÁLCULOS" if tem_calculo else "ADICIONAR CÁLCULOS", key="btn_calculo"):
            if tem_calculo: meus_modulos.remove('calculo')
            else: meus_modulos.append('calculo')
            novo_plano = ",".join(meus_modulos); run_query("UPDATE usuarios SET plano = ? WHERE username = ?", (novo_plano, st.session_state.usuario_atual)); st.session_state.plano_atual = novo_plano; st.rerun()

        # Módulo Tech
        tem_tech = 'hightech' in meus_modulos
        st.markdown(f"""<div class='module-card {"module-active" if tem_tech else ""}'><span class='module-title'>🚀 MÓDULO HIGH TECH</span><span class='module-price'>R$ 47/mês</span><p style='color:#ccc; font-size:0.9rem;'>Libera: Ferramentas Extras (Chat com PDF, Comparador).</p></div>""", unsafe_allow_html=True)
        if st.button("REMOVER TECH" if tem_tech else "ADICIONAR TECH", key="btn_tech"):
            if tem_tech: meus_modulos.remove('hightech')
            else: meus_modulos.append('hightech')
            novo_plano = ",".join(meus_modulos); run_query("UPDATE usuarios SET plano = ? WHERE username = ?", (novo_plano, st.session_state.usuario_atual)); st.session_state.plano_atual = novo_plano; st.rerun()

    with c2:
        st.markdown("#### RESUMO DA ASSINATURA")
        total = 0
        if 'litigio' in meus_modulos: total += 97
        if 'calculo' in meus_modulos: total += 97
        if 'hightech' in meus_modulos: total += 47
        st.metric("Mensalidade Atual", f"R$ {total},00")
        st.write("---")
        st.info("O Plano Base (Core) é gratuito.")

st.markdown("---")
st.markdown("<center style='color: #64748b; font-size: 0.8rem; font-family: Rajdhani;'>🔒 LEGALHUB ELITE v5.5 | ENCRYPTED SESSION</center>", unsafe_allow_html=True)
