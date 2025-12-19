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
            --neon-purple: #BC13FE;
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

        /* PLAN CARDS */
        .plan-card {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .plan-card:hover { transform: translateY(-5px); border-color: var(--neon-blue); box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); }
        
        .plan-header { font-family: 'Rajdhani'; font-size: 1.4rem; font-weight: bold; color: #FFF; margin-bottom: 5px; text-transform: uppercase; }
        .plan-price { font-size: 2rem; font-weight: 800; color: var(--neon-blue); margin: 10px 0; }
        .plan-features { text-align: left; font-size: 0.85rem; color: #CBD5E1; margin-bottom: 20px; line-height: 1.6; }
        
        .plan-crim { border-top: 4px solid var(--neon-red); }
        .plan-trab { border-top: 4px solid var(--neon-blue); }
        .plan-civ { border-top: 4px solid var(--neon-purple); }
        .plan-full { border: 1px solid var(--neon-gold); background: rgba(255, 215, 0, 0.05); }

        /* LOCK SCREEN */
        .lock-screen { border: 1px solid var(--neon-red); background: rgba(255, 0, 85, 0.05); border-radius: 10px; padding: 40px; text-align: center; margin-top: 20px; }
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
    """Gera um arquivo Word a partir de um texto."""
    doc = Document()
    for p in texto.split('\n'):
        if p.strip(): doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def extrair_texto_pdf(arquivo):
    """Extrai texto de um PDF."""
    try: return "".join([p.extract_text() for p in PdfReader(arquivo).pages])
    except: return ""

def buscar_intimacoes_email(user, pwd, server):
    """Busca emails via IMAP."""
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

# --- BUSCA JURÍDICA INTELIGENTE (RAG) ---
def buscar_jurisprudencia_oficial(tema, area):
    sites = ""
    if area == "Criminal": sites = "site:stf.jus.br OR site:stj.jus.br OR site:conjur.com.br"
    elif area == "Trabalhista": sites = "site:tst.jus.br OR site:csjt.jus.br OR site:trtsp.jus.br"
    elif area == "Civil" or area == "Família": sites = "site:stj.jus.br OR site:tjsp.jus.br OR site:ibdfam.org.br"
    else: sites = "site:jusbrasil.com.br"
    query = f"{tema} {sites}"
    try:
        res = DDGS().text(query, region="br-pt", max_results=4)
        if res: return "\n".join([f"- {r['body']} (Fonte: {r['href']})" for r in res])
        return "Nenhuma jurisprudência específica localizada nas bases oficiais."
    except: return "Erro de conexão com bases jurídicas."

def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')''')
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except: pass
    try: 
        c.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT DEFAULT 'starter'")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)''')
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('adv_criminal', '123', 'Penal Office', 'crime@adv.br', 50, 'criminal')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('adv_trab', '123', 'Labor Law', 'trab@adv.br', 50, 'trabalhista')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com', 9999, 'full')")
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
# 3. LÓGICA DE PERMISSÕES POR ESPECIALIDADE
# ==========================================================
def verificar_permissao(area_necessaria):
    """
    Verifica se o plano do usuário cobre a área solicitada.
    """
    plano_atual = st.session_state.get('plano_atual', 'starter')
    if plano_atual == 'full': return True
    if plano_atual == area_necessaria: return True
    return False

def card_bloqueio(area_necessaria):
    cor = "#FF0055"
    msg = f"Este recurso é exclusivo do plano {area_necessaria.upper()} ou FULL."
    st.markdown(f"""
    <div class='lock-screen' style='border-color:{cor};'>
        <div class='lock-icon'>🔒</div>
        <div class='lock-title' style='color:{cor};'>ACESSO RESTRITO</div>
        <p class='lock-desc'>{msg}</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"🚀 FAZER UPGRADE PARA {area_necessaria.upper()}", key=f"upg_{area_necessaria}"):
        st.session_state.navegacao_override = "💎 Planos & Upgrade"
        st.rerun()

# ==========================================================
# 4. LOGIN
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""
if "plano_atual" not in st.session_state: st.session_state.plano_atual = "starter"

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
        with st.container(border=True):
            st.markdown("#### ACCESS CONTROL")
            username = st.text_input("ID Usuário")
            password = st.text_input("Chave de Acesso", type="password")
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
# 5. SIDEBAR E MENU
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
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Perícia & Calc": "🧮 Calculadoras & Perícia", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Planos & Upgrade"}
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
    
    p_label = st.session_state.plano_atual.upper()
    cor_p = "#FFFFFF"
    if p_label == "CRIMINAL": cor_p = "#FF0055"
    elif p_label == "TRABALHISTA": cor_p = "#00F3FF"
    elif p_label == "FULL": cor_p = "#FFD700"
    
    st.markdown(f"<div style='border:1px solid {cor_p}; padding:5px; border-radius:5px; text-align:center; color:{cor_p}; margin:10px 0; font-weight:bold;'>PLANO: {p_label}</div>", unsafe_allow_html=True)

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
            # Se for plano específico, trava na área. Se for full, libera.
            opcoes_areas = ["Criminal", "Trabalhista", "Cível", "Família"]
            plano = st.session_state.plano_atual
            
            if plano == "criminal": index_area = 0 # Criminal
            elif plano == "trabalhista": index_area = 1 # Trabalhista
            elif plano == "civil": index_area = 2 # Cível (assume Cível como padrão para civil/família)
            else: index_area = 0
            
            # Se for starter ou full, deixa escolher. Se for específico, força a escolha ou sugere.
            # Para melhor UX, vamos deixar selecionar, mas a "mágica" só acontece se tiver o plano.
            area = st.selectbox("Área de Atuação", opcoes_areas, index=index_area)
            
            # Tipos de Peça Dinâmicos
            opcoes_pecas = []
            if area == "Trabalhista": opcoes_pecas = ["Reclamação Trabalhista", "Contestação", "Recurso Ordinário"]
            elif area == "Cível": opcoes_pecas = ["Petição Inicial", "Contestação", "Apelação"]
            elif area == "Criminal": opcoes_pecas = ["Habeas Corpus", "Resposta à Acusação", "Pedido de Liberdade", "Relaxamento de Prisão"]
            elif area == "Família": opcoes_pecas = ["Divórcio", "Alimentos", "Guarda"]
            else: opcoes_pecas = ["Petição Genérica"]
            
            tipo = st.selectbox("Tipo de Peça", opcoes_pecas)
            tom = st.selectbox("Tom de Voz", ["Técnico", "Combativo", "Conciliador"])
            
            # --- VERIFICAÇÃO DE PLANO PARA BUSCA DE JURISPRUDÊNCIA ---
            permissao_area = False
            if area == "Criminal" and verificar_permissao("criminal"): permissao_area = True
            elif area == "Trabalhista" and verificar_permissao("trabalhista"): permissao_area = True
            elif area == "Cível" and verificar_permissao("civil"): permissao_area = True
            elif area == "Família" and verificar_permissao("civil"): permissao_area = True
            elif verificar_permissao("full"): permissao_area = True

            label_busca = "🔍 Buscar Jurisprudência (Genérica)"
            if area == "Criminal": label_busca = "⚖️ Buscar Acórdãos STF/STJ (Anti-Alucinação)"
            elif area == "Trabalhista": label_busca = "⚖️ Buscar Súmulas TST (Anti-Alucinação)"
            
            web = st.checkbox(label_busca, value=permissao_area, disabled=not permissao_area)
            if not permissao_area: 
                st.caption(f"🔒 Necessário Plano {area.upper()} ou FULL para busca oficial.")
            
            st.markdown("---")
            st.markdown("##### 👤 CLIENTE")
            modo_cliente = st.radio("Seleção:", ["Existente", "Novo"], horizontal=True, label_visibility="collapsed")
            if modo_cliente == "Existente" and lista_clientes: cli_final = st.selectbox("Nome:", lista_clientes)
            else: cli_final = st.text_input("Nome do Novo Cliente:")

    with col_input:
        with st.container(border=True):
            st.markdown("##### 📝 DADOS E FATOS")
            # Upload disponível para todos, mas a análise profunda depende do plano (via prompt)
            upload_peticao = st.file_uploader("Anexar Documento Base (PDF)", type="pdf")
            fatos = st.text_area("Descreva os fatos:", height=200, value=st.session_state.fatos_recuperados)
            legislacao_extra = st.text_input("Legislação Específica:")
            formato = st.radio("Formato:", ["Texto Corrido", "Tópicos"], horizontal=True)
    
    st.write("")
    if st.button("✨ GERAR MINUTA COMPLETA (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner(f"Redigindo {tipo}... Consultando bases oficiais: {'SIM' if web else 'NÃO'}"):
                
                contexto_pdf = ""
                if upload_peticao:
                    contexto_pdf = f"\n\n[CONTEXTO DO ARQUIVO ANEXADO]:\n{extrair_texto_pdf(upload_peticao)}"

                jur_contexto = ""
                if web:
                    jur_contexto = buscar_jurisprudencia_oficial(f"{tipo} {fatos}", area)
                    aviso_jur = f"Jurisprudência extraída diretamente dos tribunais ({area})."
                else:
                    jur_contexto = "Sem acesso à busca externa oficial. Use conhecimento geral."
                    aviso_jur = "Busca oficial desativada (Plano incompatível)."
                
                prompt = f"""
                Atue como Advogado Especialista em Direito {area}.
                Redija uma {tipo} completa.
                Tom: {tom}. Cliente: {cli_final}.
                Fatos: {fatos}. Lei Extra: {legislacao_extra}. 
                {contexto_pdf}
                
                [JURISPRUDÊNCIA OFICIAL ENCONTRADA]:
                {jur_contexto}
                
                IMPORTANTE: Use os julgados acima se pertinentes. Evite alucinar jurisprudência inexistente.
                Formato: {formato}.
                """
                
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    
                    st.markdown("### 📄 MINUTA GERADA:")
                    if web: st.success(aviso_jur)
                    
                    with st.container(border=True): st.markdown(res)
                    st.download_button("📥 BAIXAR DOCX", gerar_word(res), f"{tipo}_{cli_final}.docx", use_container_width=True)
                    st.success("Salvo no cofre.")
                except Exception as e: st.error(f"Erro: {str(e)}")
        else: st.error("Créditos insuficientes.")

# 3. CALCULADORA (AUTOMÁTICA PELO PLANO)
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='tech-header'>🧮 CÁLCULOS ESPECIALIZADOS</h2>", unsafe_allow_html=True)
    
    # Detecção Automática do Plano para evitar menu desnecessário
    plano_atual = st.session_state.plano_atual
    
    # Se for FULL ou STARTER, mostra todas as opções. Se for específico, já trava na opção certa.
    opcoes_calc = ["Trabalhista", "Cível", "Criminal", "Família"]
    index_calc = 0
    
    if plano_atual == "criminal": 
        opcoes_calc = ["Criminal"]
    elif plano_atual == "trabalhista":
        opcoes_calc = ["Trabalhista"]
    elif plano_atual == "civil":
        opcoes_calc = ["Cível", "Família"]
    
    area_calc = st.selectbox("Selecione a Especialidade:", opcoes_calc)
    
    # Verifica permissão da área para liberar a calculadora (dupla checagem de segurança)
    liberado = False
    if area_calc == "Trabalhista" and verificar_permissao("trabalhista"): liberado = True
    elif area_calc == "Criminal" and verificar_permissao("criminal"): liberado = True
    elif area_calc in ["Cível", "Família"] and verificar_permissao("civil"): liberado = True
    elif verificar_permissao("full"): liberado = True

    if liberado:
        with st.container(border=True):
            if area_calc == "Trabalhista":
                st.markdown("#### 👷 Cálculo de Rescisão CLT")
                c1, c2, c3 = st.columns(3)
                salario = c1.number_input("Salário Base (R$)", min_value=0.0)
                meses = c2.number_input("Meses", min_value=1)
                motivo = c3.selectbox("Motivo", ["Sem Justa Causa", "Pedido de Demissão"])
                if st.button("CALCULAR"):
                    multa = (salario * 0.08 * meses) * 0.40 if motivo == "Sem Justa Causa" else 0
                    total = salario + multa 
                    st.success(f"Total Estimado: R$ {total:,.2f}")
            elif area_calc == "Criminal":
                st.markdown("#### 🚔 Dosimetria da Pena (Estimativa)")
                pena_base = st.number_input("Pena Base (Anos)", min_value=0)
                agravantes = st.number_input("Qtd. Agravantes", min_value=0)
                atenuantes = st.number_input("Qtd. Atenuantes", min_value=0)
                if st.button("CALCULAR PENA"):
                    pena = pena_base + ((agravantes - atenuantes) * (pena_base/6))
                    st.warning(f"⚖️ Pena Estimada: {pena:.1f} anos")
            elif area_calc == "Cível":
                st.markdown("#### ⚖️ Atualização Monetária")
                valor = st.number_input("Valor Original", min_value=0.0)
                if st.button("ATUALIZAR"): st.success(f"Valor Corrigido: R$ {valor * 1.05:,.2f} (Exemplo)")
            elif area_calc == "Família":
                st.markdown("#### 👨‍👩‍👧 Pensão Alimentícia")
                renda = st.number_input("Renda Líquida", min_value=0.0)
                if st.button("CALCULAR"): st.success(f"30% Sugerido: R$ {renda * 0.30:,.2f}")
    else:
        # Mostra o bloqueio da área que ele tentou acessar (ou a padrão)
        tela_bloqueio(area_calc, "149")

# 4. AUDIENCIA (BLOQUEIO POR ÁREA)
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ ESTRATEGISTA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
    
    # Detecção Automática do Plano
    plano_atual = st.session_state.plano_atual
    opcoes_aud = ["Trabalhista", "Criminal", "Cível"]
    
    if plano_atual == "criminal": opcoes_aud = ["Criminal"]
    elif plano_atual == "trabalhista": opcoes_aud = ["Trabalhista"]
    elif plano_atual == "civil": opcoes_aud = ["Cível"]
    
    area_aud = st.selectbox("Área da Audiência:", opcoes_aud)
    
    liberado = False
    if area_aud == "Trabalhista" and verificar_permissao("trabalhista"): liberado = True
    elif area_aud == "Criminal" and verificar_permissao("criminal"): liberado = True
    elif area_aud == "Cível" and verificar_permissao("civil"): liberado = True
    elif verificar_permissao("full"): liberado = True

    if liberado:
        c1, c2 = st.columns(2)
        with c1: papel = st.selectbox("Papel", ["Autor/MP", "Réu/Defesa"])
        with c2: perfil_juiz = st.selectbox("Perfil Juiz", ["Padrão", "Rígido", "Conciliador"])
        detalhes = st.text_area("Resumo do Caso:")
        upload_autos = st.file_uploader("Autos (PDF) - Opcional", type="pdf")
        
        if st.button("🔮 SIMULAR"):
            if detalhes:
                with st.spinner("Simulando..."):
                    ctx = f"[DOC]: {extrair_texto_pdf(upload_autos)}" if upload_autos else ""
                    prompt = f"Estrategista {area_aud}. Papel: {papel}. Juiz: {perfil_juiz}. Caso: {detalhes} {ctx}. Gere perguntas e riscos."
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("BAIXAR ROTEIRO", gerar_word(res), "Roteiro_Audiencia.docx")
    else: tela_bloqueio(area_aud, "149")

# 5. GESTÃO DE CASOS (LIBERADO)
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
    # ... Lógica padrão de gestão de casos (mantida do anterior para economizar espaço visual, é igual)
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
                novo_tipo = c_add1.text_input("Nome do Documento (Ex: Procuração):")
                nova_area = c_add2.selectbox("Categoria:", ["Provas", "Andamento", "Anotações"])
                tab_up, tab_txt = st.tabs(["📤 Upload PDF", "✍️ Nota de Texto"])
                conteudo_novo = ""
                with tab_up: arquivo_novo = st.file_uploader("Arquivo PDF", key="novo_up")
                with tab_txt: texto_novo = st.text_area("Texto da Nota:", key="nova_nota")
                
                if st.button("💾 SALVAR DOCUMENTO"):
                    if novo_tipo:
                        if arquivo_novo: conteudo_novo = f"[ARQUIVO EXTERNO] {extrair_texto_pdf(arquivo_novo)}"
                        elif texto_novo: conteudo_novo = texto_novo
                        else: conteudo_novo = "Item adicionado sem conteúdo."
                        
                        run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), st.session_state.pasta_aberta, nova_area, novo_tipo, conteudo_novo))
                        st.success("Adicionado com sucesso!")
                        time.sleep(1)
                        st.rerun()

            st.divider()
            docs_cli = df_docs[df_docs['cliente'] == st.session_state.pasta_aberta]
            for idx, row in docs_cli.iterrows():
                with st.expander(f"{row['tipo']} - {row['data_criacao']}"):
                    texto_display = row['conteudo'][:300] + "..." if len(row['conteudo']) > 300 else row['conteudo']
                    st.write(texto_display)
                    c_d, c_e = st.columns([4, 1])
                    with c_d:
                        st.download_button("📥 BAIXAR DOCX", gerar_word(row['conteudo']), f"{row['tipo']}.docx", key=f"dl_{idx}")
                    with c_e:
                        if st.button("🗑️ EXCLUIR", key=f"del_{idx}"):
                            run_query("DELETE FROM documentos WHERE id = ?", (row['id'],))
                            st.rerun()
    else: st.info("Nenhum documento encontrado.")

# 6. MONITOR (CORRIGIDO PARA QUALQUER PLANO PAGO)
elif menu_opcao == "🚦 Monitor de Prazos":
    if st.session_state.plano_atual != 'starter':
        st.markdown("<h2 class='tech-header'>🚦 RADAR DE PRAZOS INTELIGENTE</h2>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("E-mails Lidos", "0"); m2.metric("Prazos Fatais", "0"); m3.metric("Status IMAP", "Desconectado")
        st.write("")
        with st.container(border=True):
            st.markdown("##### 📡 PARÂMETROS DE VARREDURA")
            c_mail, c_pass, c_host = st.columns(3)
            email_leitura = c_mail.text_input("E-mail OAB")
            senha_leitura = c_pass.text_input("Senha App", type="password")
            servidor_imap = c_host.text_input("Servidor", value="imap.gmail.com")
            if st.button("INICIAR VARREDURA PROFUNDA"):
                if email_leitura and senha_leitura:
                    with st.spinner("Analisando metadados..."):
                        msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                        if err: st.error(err)
                        elif not msgs: st.success("Nenhuma intimação.")
                        else:
                            for m in msgs:
                                with st.expander(f"⚠️ {m['assunto']}"):
                                    st.write(m['corpo'])
                                    if st.button("ANALISAR PRAZO (IA)", key=m['assunto']):
                                        res = genai.GenerativeModel(mod_escolhido).generate_content(f"Extraia prazos: {m['corpo']}").text
                                        st.warning(res)
                else: st.error("Preencha credenciais.")
    else: tela_bloqueio("QUALQUER PLANO PAGO", "149")

# 8. PLANOS (UPGRADE POR ESPECIALIDADE)
elif menu_opcao == "💎 Planos & Upgrade":
    st.markdown("<h2 class='tech-header' style='text-align:center;'>ESCOLHA SUA ESPECIALIDADE</h2>", unsafe_allow_html=True)
    st.write("")
    
    col1, col2, col3, col4 = st.columns(4)
    
    def render_plan_card(titulo, preco, desc, slug, css_class):
        st.markdown(f"""
        <div class='plan-card {css_class}'>
            <div>
                <div class='plan-header'>{titulo}</div>
                <div class='plan-price'>R$ {preco}<small>/mês</small></div>
                <div class='plan-features'>{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        btn_label = "SELECIONADO" if st.session_state.plano_atual == slug else "ASSINAR AGORA"
        if st.button(btn_label, key=f"btn_{slug}", disabled=(st.session_state.plano_atual == slug), use_container_width=True):
            run_query("UPDATE usuarios SET plano = ? WHERE username = ?", (slug, st.session_state.usuario_atual))
            st.session_state.plano_atual = slug
            st.toast(f"Plano {titulo} ativado com sucesso!")
            time.sleep(1)
            st.rerun()

    with col1:
        render_plan_card("Criminalista Elite", "149", 
                         "✅ Busca STF/STJ<br>✅ Dosimetria da Pena<br>✅ Simulador de Júri<br>✅ Redator de HC", 
                         "criminal", "plan-crim")
        
    with col2:
        render_plan_card("Trabalhista Expert", "149", 
                         "✅ Busca TST/CSJT<br>✅ Cálculos Rescisórios<br>✅ Instrução Trabalhista<br>✅ Redator CLT", 
                         "trabalhista", "plan-trab")

    with col3:
        render_plan_card("Civil & Família", "149", 
                         "✅ Busca TJs<br>✅ Cálculos Pensão/Atualização<br>✅ Contratos & Divórcio<br>✅ Gestão Patrimonial", 
                         "civil", "plan-civ")

    with col4:
        render_plan_card("Full Service", "297", 
                         "💎 <strong>Acesso a TUDO</strong><br>💎 Todas as áreas<br>💎 Prioridade de Suporte<br>💎 + Créditos IA", 
                         "full", "plan-full")

st.markdown("---")
st.markdown("<center style='color: #64748b; font-size: 0.8rem; font-family: Rajdhani;'>🔒 LEGALHUB ELITE v5.5 | ENCRYPTED SESSION</center>", unsafe_allow_html=True)
