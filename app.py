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
import requests # Importante para a solução nuclear

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument, PermissionDenied

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - TEMA CYBER FUTURE
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite | AI System", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

# --- FUNÇÃO DE IA BLINDADA (RESOLUÇÃO DO ERRO 404) ---
def tentar_gerar_conteudo(prompt, api_key_val):
    if not api_key_val:
        return "⚠️ Erro: API Key não configurada. Insira na barra lateral."
    
    # --- ESTRATÉGIA 1: DETECÇÃO AUTOMÁTICA VIA SDK ---
    try:
        genai.configure(api_key=api_key_val)
        modelo_encontrado = None
        
        # Pergunta para a API quais modelos estão disponíveis para esta chave
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # Prioriza modelos mais capazes se disponíveis
                if 'gemini-1.5' in m.name:
                    modelo_encontrado = m.name
                    break
                elif 'gemini-pro' in m.name:
                    modelo_encontrado = m.name
        
        if modelo_encontrado:
            model = genai.GenerativeModel(modelo_encontrado)
            response = model.generate_content(prompt)
            return response.text
            
    except Exception as e_sdk:
        print(f"Falha no SDK: {e_sdk}")
        # Se o SDK falhar, passamos para a Estratégia 2 silenciosamente

    # --- ESTRATÉGIA 2: REQUISIÇÃO HTTP DIRETA (NUCLEAR) ---
    # Isso ignora a biblioteca instalada e fala direto com o servidor do Google
    try:
        # Tenta endpoint do Gemini 1.5 Flash (mais rápido e barato/gratis)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key_val}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # Se falhar, tenta o Gemini Pro (Legacy)
            url_backup = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key_val}"
            response_backup = requests.post(url_backup, headers=headers, json=data)
            
            if response_backup.status_code == 200:
                return response_backup.json()['candidates'][0]['content']['parts'][0]['text']
            
            return f"❌ Erro Crítico de API (HTTP {response.status_code}): {response.text}"

    except Exception as e_req:
        return f"❌ Falha Total (SDK e HTTP falharam). Verifique sua Internet e sua API Key. Erro: {str(e_req)}"

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
                    found.append({"assunto": subj, "corpo": str(msg)[:2000]})
        return found, None
    except Exception as e: return [], str(e)

def verificar_permissao(area_necessaria):
    plano_atual = st.session_state.get('plano_atual', 'starter')
    if plano_atual == 'full': return True
    if plano_atual == area_necessaria: return True
    if area_necessaria == 'bancario' and plano_atual == 'civil': return True
    return False

def tela_bloqueio(area_necessaria, preco):
    cor = "#FF0055"
    msg = f"Este recurso é exclusivo do plano {area_necessaria.upper()} ou FULL."
    st.markdown(f"""
    <div class='lock-screen' style='border-color:{cor};'>
        <div class='lock-icon'>🔒</div>
        <div class='lock-title' style='color:{cor};'>ACESSO RESTRITO</div>
        <p class='lock-desc'>{msg}</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"🚀 FAZER UPGRADE", key=f"upg_{area_necessaria}"):
        st.session_state.navegacao_override = "💎 Planos & Upgrade"
        st.rerun()

def buscar_jurisprudencia_oficial(tema, area):
    sites = ""
    if area == "Criminal": sites = "site:stf.jus.br OR site:stj.jus.br OR site:conjur.com.br"
    elif area == "Trabalhista": sites = "site:tst.jus.br OR site:csjt.jus.br OR site:trtsp.jus.br"
    elif area == "Civil" or area == "Família" or area == "Bancário": sites = "site:stj.jus.br OR site:tjsp.jus.br OR site:ibdfam.org.br"
    else: sites = "site:jusbrasil.com.br"
    query = f"{tema} {sites}"
    try:
        res = DDGS().text(query, region="br-pt", max_results=4)
        if res: return "\n".join([f"- {r['body']} (Fonte: {r['href']})" for r in res])
        return "Nenhuma jurisprudência específica localizada."
    except: return "Erro de conexão com bases jurídicas."

# --- CSS AVANÇADO COM BACKGROUND ---
def local_css():
    bg_image_b64 = get_base64_of_bin_file("unnamed.jpg")
    bg_css = ""
    if bg_image_b64:
        bg_css = f"""
        .stApp::before {{
            content: "";
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 60%;
            height: 60%;
            background-image: url("data:image/jpeg;base64,{bg_image_b64}");
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            opacity: 0.08;
            z-index: 0;
            pointer-events: none;
            animation: float-logo 15s ease-in-out infinite;
        }}
        @keyframes float-logo {{
            0%, 100% {{ transform: translate(-50%, -50%) translateY(0px); }}
            50% {{ transform: translate(-50%, -50%) translateY(-20px); }}
        }}
        """

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');

        :root {{
            --bg-dark: #020617;
            --bg-card: rgba(15, 23, 42, 0.6);
            --text-main: #FFFFFF;
            --neon-blue: #00F3FF;
            --neon-red: #FF0055;
            --neon-gold: #FFD700;
            --neon-green: #10B981;
            --neon-purple: #BC13FE;
        }}

        .stApp {{
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(14, 165, 233, 0.08), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.08), transparent 25%);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
        }}

        {bg_css}

        h1, h2, h3, h4, h5, h6 {{ color: #FFFFFF !important; font-family: 'Rajdhani', sans-serif; text-transform: uppercase; letter-spacing: 1.5px; z-index: 1; position: relative; }}
        p, .stCaption, label, .stMarkdown {{ color: #E2E8F0 !important; font-family: 'Inter', sans-serif; z-index: 1; position: relative; }}
        div[data-testid="stMetricValue"] {{ color: var(--neon-blue) !important; text-shadow: 0 0 10px rgba(0, 243, 255, 0.5); }}
        .tech-header {{ background: linear-gradient(90deg, #FFFFFF 0%, var(--neon-blue) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 700; }}

        .plan-card {{
            background: rgba(15, 23, 42, 0.85);
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
            z-index: 1;
        }}
        .plan-card:hover {{ transform: translateY(-5px); border-color: var(--neon-blue); box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); }}
        
        .plan-header {{ font-family: 'Rajdhani'; font-size: 1.4rem; font-weight: bold; color: #FFF; margin-bottom: 5px; text-transform: uppercase; }}
        .plan-price {{ font-size: 2rem; font-weight: 800; color: var(--neon-blue); margin: 10px 0; }}
        .plan-features {{ text-align: left; font-size: 0.85rem; color: #CBD5E1; margin-bottom: 20px; line-height: 1.6; }}
        
        .plan-crim {{ border-top: 4px solid var(--neon-red); }}
        .plan-trab {{ border-top: 4px solid var(--neon-blue); }}
        .plan-civ {{ border-top: 4px solid var(--neon-purple); }}
        .plan-full {{ border: 1px solid var(--neon-gold); background: rgba(255, 215, 0, 0.05); }}

        .lock-screen {{ border: 1px solid var(--neon-red); background: rgba(255, 0, 85, 0.05); border-radius: 10px; padding: 40px; text-align: center; margin-top: 20px; z-index: 1; position: relative; }}
        .lock-icon {{ font-size: 3rem; margin-bottom: 10px; }}
        .lock-title {{ color: var(--neon-red) !important; font-family: 'Rajdhani'; font-size: 2rem; font-weight: bold; }}

        .header-logo {{ display: flex; align-items: center; margin-right: 2rem; }}
        .header-logo h1 {{ font-size: 1.8rem; margin: 0; letter-spacing: 2px; }}
        .floating-logo {{ animation: float 6s ease-in-out infinite; display: block; margin: 0 auto 30px auto; width: 250px; z-index: 1; position: relative; }}
        @keyframes float {{ 0%, 100% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-20px); }} }}
        
        section[data-testid="stSidebar"] {{ background-color: #020408; border-right: 1px solid rgba(0, 243, 255, 0.1); z-index: 2; }}
        .stButton>button {{ background: transparent; color: var(--neon-blue); border: 1px solid var(--neon-blue); border-radius: 0px; padding: 0.6rem 1.2rem; font-family: 'Rajdhani'; font-weight: 700; }}
        .stButton>button:hover {{ background: var(--neon-blue); color: #000; box-shadow: 0 0 20px rgba(0, 243, 255, 0.6); }}
        
        div[data-testid="metric-container"], div[data-testid="stExpander"], .folder-card {{ background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 0px; backdrop-filter: blur(12px); z-index: 1; }}
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, .stNumberInput>div>div>input {{ background-color: rgba(0, 0, 0, 0.3) !important; border: 1px solid #334155 !important; color: #FFF !important; border-radius: 0px; }}
        
        #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

local_css()

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

# (A configuração da API agora é feita dentro da função tentar_gerar_conteudo)

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
    
    # Label do Plano
    p_label = st.session_state.plano_atual.upper()
    cor_p = "#FFFFFF"
    if p_label == "CRIMINAL": cor_p = "#FF0055"
    elif p_label == "TRABALHISTA": cor_p = "#00F3FF"
    elif p_label == "FULL": cor_p = "#FFD700"
    
    st.markdown(f"<div style='border:1px solid {cor_p}; padding:5px; border-radius:5px; text-align:center; color:{cor_p}; margin:10px 0; font-weight:bold;'>PLANO: {p_label}</div>", unsafe_allow_html=True)

    if "GOOGLE_API_KEY" not in st.secrets:
        st.text_input("🔑 API Key:", type="password", key="sidebar_api_key")

    # --- NOVO DIAGNÓSTICO DE MODELOS ---
    with st.expander("🛠️ SYSTEM CHECK"):
        if st.button("Verificar Modelos"):
            try:
                genai.configure(api_key=api_key if api_key else st.session_state.get('sidebar_api_key'))
                modelos = [m.name for m in genai.list_models()]
                st.write(modelos)
            except Exception as e:
                st.error(f"Erro: {e}")
    # -----------------------------------

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
    st.subheader("🛠️ CENTRAL DE COMANDO")
    
    row1_c1, row1_c2, row1_c3 = st.columns(3)
    
    with row1_c1:
        with st.container(border=True):
            st.markdown("#### ✍️ REDATOR IA")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Crie petições robustas, contratos e pareceres com inteligência artificial e busca de jurisprudência oficial.</div>", unsafe_allow_html=True)
            if st.button("ABRIR REDATOR", key="d_redator", use_container_width=True): 
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with row1_c2:
        with st.container(border=True):
            st.markdown("#### 🧮 PERÍCIA & CÁLCULOS")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Calculadoras especializadas (Trabalhista, Cível, Penal) e gerador de laudos técnicos instantâneos.</div>", unsafe_allow_html=True)
            if st.button("ABRIR CÁLCULOS", key="d_pericia", use_container_width=True): 
                st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"
                st.rerun()

    with row1_c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ AUDIÊNCIA STRATEGY")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Simule audiências, gere perguntas cruzadas para testemunhas e antecipe a estratégia da parte contrária.</div>", unsafe_allow_html=True)
            if st.button("ABRIR SIMULADOR", key="d_aud", use_container_width=True): 
                st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"
                st.rerun()

    st.write("") 

    row2_c1, row2_c2, row2_c3 = st.columns(3)

    with row2_c1:
        with st.container(border=True):
            st.markdown("#### 📂 COFRE DIGITAL")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Gestão segura de documentos. Armazene provas, histórico de clientes e peças geradas em nuvem criptografada.</div>", unsafe_allow_html=True)
            if st.button("ACESSAR COFRE", key="d_gestao", use_container_width=True):
                st.session_state.navegacao_override = "📂 Gestão de Casos"
                st.rerun()

    with row2_c2:
        with st.container(border=True):
            st.markdown("#### 🚦 MONITOR DE PRAZOS")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Rastreamento inteligente de intimações via e-mail para garantir que nenhum prazo fatal seja perdido.</div>", unsafe_allow_html=True)
            if st.button("VER PRAZOS", key="d_monitor", use_container_width=True):
                st.session_state.navegacao_override = "🚦 Monitor de Prazos"
                st.rerun()

    with row2_c3:
        with st.container(border=True):
            st.markdown("#### 💎 PLANOS & ESPECIALIZAÇÃO")
            st.markdown("<div style='height: 60px; font-size: 0.85rem; color: #cbd5e1;'>Gerencie sua assinatura, troque sua especialidade (Criminal, Cível, etc) e adquira mais créditos de IA.</div>", unsafe_allow_html=True)
            if st.button("GERENCIAR PLANO", key="d_planos", use_container_width=True):
                st.session_state.navegacao_override = "💎 Planos & Upgrade"
                st.rerun()

    st.write("")
    st.divider()
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
            # --- DETECÇÃO AUTOMÁTICA DE ÁREA PELO PLANO ---
            plano = st.session_state.plano_atual
            opcoes_areas = ["Criminal", "Trabalhista", "Cível", "Família"]
            index_area = 0
            
            if plano == "criminal": index_area = 0 
            elif plano == "trabalhista": index_area = 1 
            elif plano == "civil": index_area = 2 
            
            area = st.selectbox("Área de Atuação", opcoes_areas, index=index_area)
            
            # Tipos de Peça Dinâmicos
            opcoes_pecas = []
            if area == "Trabalhista": opcoes_pecas = ["Reclamação Trabalhista", "Contestação", "Recurso Ordinário"]
            elif area == "Cível": opcoes_pecas = ["Petição Inicial", "Contestação", "Apelação", "Notificação Extrajudicial"]
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
            upload_peticao = st.file_uploader("Anexar Documento Base (PDF)", type="pdf")
            fatos = st.text_area("Descreva os fatos:", height=200, value=st.session_state.fatos_recuperados)
            legislacao_extra = st.text_input("Legislação Específica:")
            formato = st.radio("Formato:", ["Texto Corrido", "Tópicos"], horizontal=True)
    
    st.write("")
    if st.button("✨ GERAR MINUTA COMPLETA (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner(f"Redigindo {tipo}... Consultando bases oficiais..."):
                
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
                
                # --- CHAMADA DA NOVA FUNÇÃO ROBUSTA ---
                api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                res = tentar_gerar_conteudo(prompt, api_key_to_use)
                
                if "❌" not in res:
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    st.markdown("### 📄 MINUTA GERADA:")
                    if web: st.success(aviso_jur)
                    with st.container(border=True): st.markdown(res)
                    st.download_button("📥 BAIXAR DOCX", gerar_word(res), f"{tipo}_{cli_final}.docx", use_container_width=True)
                    st.success("Salvo no cofre.")
                else:
                    st.error(res)
        else: st.error("Créditos insuficientes.")

# 3. CALCULADORA (APRIMORADA PARA CÍVEL, FAMÍLIA, TRABALHISTA E BANCÁRIO)
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='tech-header'>🧮 CÁLCULOS ESPECIALIZADOS</h2>", unsafe_allow_html=True)
    
    # Detecção Automática do Plano
    plano_atual = st.session_state.plano_atual
    
    opcoes_calc = ["Trabalhista", "Cível", "Criminal", "Família", "Bancário"]
    index_calc = 0
    if plano_atual == "criminal": opcoes_calc = ["Criminal"]
    elif plano_atual == "trabalhista": opcoes_calc = ["Trabalhista"]
    elif plano_atual == "civil": opcoes_calc = ["Cível", "Família", "Bancário"]
    
    area_calc = st.selectbox("Selecione a Especialidade:", opcoes_calc)
    
    # Verifica permissão da área
    liberado = False
    if area_calc == "Trabalhista" and verificar_permissao("trabalhista"): liberado = True
    elif area_calc == "Criminal" and verificar_permissao("criminal"): liberado = True
    elif area_calc in ["Cível", "Família", "Bancário"] and verificar_permissao("civil"): liberado = True
    elif verificar_permissao("full"): liberado = True

    if liberado:
        with st.container(border=True):
            
            # --- CÍVEL (NOVO E APROFUNDADO) ---
            if area_calc == "Cível":
                tab_debito, tab_aluguel, tab_rescisao, tab_bancario, tab_veiculo, tab_not = st.tabs([
                    "💸 Atualização Débitos", "🏠 Reajuste Aluguel", "🚫 Rescisão Aluguel", 
                    "🏦 Juros Bancários", "🚘 Financ. Veículos", "📢 Notificação Extrajud."
                ])
                
                with tab_debito:
                    st.markdown("#### Correção Monetária e Juros")
                    c1, c2, c3 = st.columns(3)
                    valor = c1.number_input("Valor Original (R$)", min_value=0.0, value=1000.0, key="c_valor")
                    dt_inicio = c2.date_input("Data Inicial", value=date(2023, 1, 1), key="c_dt_ini")
                    dt_final = c3.date_input("Data Final", value=date.today(), key="c_dt_fim")
                    
                    c4, c5, c6 = st.columns(3)
                    indice = c4.selectbox("Índice de Correção", ["Tabela Prática TJ", "IGP-M", "INPC", "IPCA-E", "CDI"], key="c_ind")
                    juros_tipo = c5.selectbox("Juros de Mora", ["1% a.m. Simples", "1% a.m. Composto", "Sem Juros"], key="c_jur")
                    multa = c6.checkbox("Multa de 10% (Art. 523 CPC)", key="c_mul")
                    honra = st.number_input("Honorários Advocatícios (%)", min_value=0, max_value=30, value=10, key="c_hon")
                    
                    if st.button("CALCULAR ATUALIZAÇÃO", key="btn_c_atu"):
                        # Simulação matemática (Fins demonstrativos)
                        meses = (dt_final.year - dt_inicio.year) * 12 + dt_final.month - dt_inicio.month
                        fator_correcao = 1.05 + (meses * 0.005) # Simulação 0.5% ao mês de inflação
                        val_corrigido = valor * fator_correcao
                        
                        val_juros = 0
                        if "1%" in juros_tipo:
                            val_juros = val_corrigido * (0.01 * meses)
                        
                        subtotal = val_corrigido + val_juros
                        val_multa = subtotal * 0.10 if multa else 0
                        val_honra = (subtotal + val_multa) * (honra / 100)
                        total_final = subtotal + val_multa + val_honra
                        
                        st.divider()
                        col_res1, col_res2 = st.columns(2)
                        col_res1.metric("Valor Corrigido", f"R$ {val_corrigido:,.2f}")
                        col_res1.metric("Juros de Mora", f"R$ {val_juros:,.2f}")
                        col_res2.metric("Multa + Honorários", f"R$ {val_multa + val_honra:,.2f}")
                        col_res2.metric("TOTAL FINAL", f"R$ {total_final:,.2f}", delta="Atualizado")
                
                with tab_aluguel:
                    st.markdown("#### Reajuste Anual de Contrato")
                    val_aluguel = st.number_input("Valor Atual do Aluguel", min_value=0.0, key="alu_val")
                    idx_aluguel = st.selectbox("Índice do Contrato", ["IGP-M (FGV)", "IPCA (IBGE)", "IVAR"], key="alu_idx")
                    if st.button("CALCULAR NOVO ALUGUEL", key="btn_alu"):
                        # Simulação
                        fator = 1.045 if idx_aluguel == "IPCA (IBGE)" else 1.005 # IGPM baixo na simulação
                        novo_valor = val_aluguel * fator
                        st.success(f"Novo Aluguel Sugerido: R$ {novo_valor:,.2f} (Baseado no acumulado de 12 meses)")
                
                with tab_rescisao:
                    st.markdown("#### Cálculo de Multa por Rescisão Antecipada")
                    val_aluguel_res = st.number_input("Valor do Aluguel", key="res_val")
                    multa_padrao = st.number_input("Multa prevista (em aluguéis)", value=3, key="res_mul")
                    data_inicio = st.date_input("Início do Contrato", key="res_dt_ini")
                    data_fim = st.date_input("Fim do Contrato (Prazo Original)", key="res_dt_fim")
                    data_saida = st.date_input("Data de Entrega das Chaves", key="res_dt_sai")

                    if st.button("CALCULAR MULTA", key="btn_res"):
                        total_dias = (data_fim - data_inicio).days
                        dias_cumpridos = (data_saida - data_inicio).days
                        dias_restantes = total_dias - dias_cumpridos

                        if dias_restantes <= 0:
                            st.success("Sem multa! O contrato foi cumprido integralmente.")
                        else:
                            valor_multa_total = val_aluguel_res * multa_padrao
                            multa_proporcional = (valor_multa_total / total_dias) * dias_restantes
                            st.error(f"Multa Devida: R$ {multa_proporcional:.2f}")

                with tab_bancario:
                    st.markdown("#### 🏦 Revisional Bancária (Empréstimos)")
                    c1, c2 = st.columns(2)
                    valor_emprestimo = c1.number_input("Valor Liberado (R$)", value=10000.0, key="ban_val")
                    num_parcelas = c2.number_input("Nº Parcelas", value=24, key="ban_par")
                    
                    c3, c4 = st.columns(2)
                    tx_banco = c3.number_input("Taxa Contrato (% a.m.)", value=4.5, key="ban_tx")
                    tx_media = c4.number_input("Taxa Média BACEN (% a.m.)", value=1.9, help="Consulte a série histórica do BACEN.", key="ban_bac")

                    if st.button("CALCULAR REVISIONAL (BANCO)", key="btn_ban"):
                        def pmt(p, i, n):
                            i = i / 100
                            if i == 0: return p/n
                            return p * (i * (1 + i)**n) / ((1 + i)**n - 1)

                        parc_real = pmt(valor_emprestimo, tx_banco, num_parcelas)
                        parc_justa = pmt(valor_emprestimo, tx_media, num_parcelas)
                        
                        total_real = parc_real * num_parcelas
                        total_justo = parc_justa * num_parcelas
                        diferenca = total_real - total_justo

                        c_res1, c_res2 = st.columns(2)
                        c_res1.metric("Parcela Cobrada", f"R$ {parc_real:,.2f}")
                        c_res2.metric("Parcela Justa (Média)", f"R$ {parc_justa:,.2f}")
                        
                        if tx_banco > (tx_media * 1.5):
                            st.error(f"⚠️ Taxa abusiva! {tx_banco/tx_media:.1f}x acima da média. Indício forte para ação revisional.")
                            st.metric("Valor a Recuperar (Estimado)", f"R$ {diferenca:,.2f}")
                        else:
                            st.warning("Taxa acima da média, mas dentro da margem de tolerância jurisprudencial.")

                with tab_veiculo:
                    st.markdown("#### 🚘 Revisional de Financiamento de Veículo")
                    c1, c2 = st.columns(2)
                    val_veiculo = c1.number_input("Valor do Veículo (FIPE/Nota)", value=60000.0, key="vei_val")
                    entrada = c2.number_input("Valor da Entrada", value=10000.0, key="vei_ent")
                    
                    c3, c4 = st.columns(2)
                    tarifas = c3.number_input("Tarifas (TAC, Registro, Avaliação)", value=2500.0, key="vei_tar")
                    seguro = c4.number_input("Seguro Prestamista (Venda Casada?)", value=1500.0, key="vei_seg")
                    
                    st.divider()
                    c5, c6 = st.columns(2)
                    tx_vei_con = c5.number_input("Taxa Contrato (% a.m.)", value=2.9, key="vei_tx")
                    tx_vei_bacen = c6.number_input("Taxa Média BACEN - Veículos", value=1.4, key="vei_bac")
                    n_parc_vei = st.number_input("Nº Parcelas", value=48, key="vei_par")

                    if st.button("CALCULAR REVISIONAL (VEÍCULO)", key="btn_vei"):
                        valor_financiado = val_veiculo - entrada + tarifas + seguro
                        
                        def pmt(p, i, n):
                            i = i / 100
                            if i == 0: return p/n
                            return p * (i * (1 + i)**n) / ((1 + i)**n - 1)

                        parc_atual = pmt(valor_financiado, tx_vei_con, n_parc_vei)
                        # Cálculo sem as tarifas abusivas e com taxa justa
                        valor_justo_finan = val_veiculo - entrada 
                        parc_justa = pmt(valor_justo_finan, tx_vei_bacen, n_parc_vei)
                        
                        diff_mensal = parc_atual - parc_justa
                        diff_total = diff_mensal * n_parc_vei

                        st.info(f"Valor Financiado Real (com taxas): R$ {valor_financiado:,.2f}")
                        
                        col1, col2 = st.columns(2)
                        col1.metric("Parcela Atual", f"R$ {parc_atual:,.2f}")
                        col2.metric("Parcela Justa (S/ Taxas + Juros Médios)", f"R$ {parc_justa:,.2f}")
                        
                        st.success(f"💰 Potencial de Economia: R$ {diff_total:,.2f}")
                        st.caption("Considerando a exclusão de tarifas acessórias e aplicação da taxa média de mercado.")

                # --- NOVA ABA DE NOTIFICAÇÃO (RÁPIDA) ---
                with tab_not:
                    st.markdown("#### Gerador Rápido de Notificação Extrajudicial")
                    c1, c2 = st.columns(2)
                    notificante = c1.text_input("Nome do Notificante (Cliente)")
                    notificado = c2.text_input("Nome do Notificado (Devedor/Parte)")
                    endereco = st.text_input("Endereço do Imóvel/Objeto (Opcional)")
                    motivo = st.text_area("Motivo (Ex: Cobrança aluguel, Desocupação, Vício Oculto)")
                    prazo = st.number_input("Prazo (dias)", value=5)
                    
                    if st.button("GERAR NOTIFICAÇÃO RÁPIDA", key="btn_not"):
                        if notificante and notificado and motivo:
                            prompt = f"""
                            Redija uma Notificação Extrajudicial formal.
                            Notificante: {notificante}. Notificado: {notificado}.
                            Endereço: {endereco}. Motivo: {motivo}.
                            Prazo para cumprimento: {prazo} dias.
                            Tom: Jurídico, formal e imperativo.
                            """
                            api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                            res = tentar_gerar_conteudo(prompt, api_key_to_use)
                            
                            if "❌" not in res:
                                st.markdown("### 📢 Minuta da Notificação")
                                st.markdown(res)
                                st.download_button("📥 Baixar Notificação (.docx)", gerar_word(res), "Notificacao_Extrajudicial.docx")
                            else: st.error(res)
                        else: st.error("Preencha os campos obrigatórios.")

            # --- FAMÍLIA (NOVO E APROFUNDADO) ---
            elif area_calc == "Família":
                tab_pensao, tab_partilha = st.tabs(["👶 Pensão Alimentícia Completa", "💍 Partilha de Bens & Inventário"])
                
                with tab_pensao:
                    st.markdown("#### Simulador de Pensão")
                    base_calc = st.radio("Base de Cálculo", ["Salário Mínimo (2025: R$ 1.509)", "Renda Líquida do Alimentante"], horizontal=True, key="fam_base")
                    
                    if "Mínimo" in base_calc:
                        percentual = st.slider("Percentual do S.M. (%)", 10, 100, 30, key="fam_perc_sm")
                        valor_base = 1509.00
                    else:
                        valor_base = st.number_input("Renda Líquida (R$)", value=3000.0, key="fam_renda")
                        percentual = st.slider("Percentual da Renda (%)", 10, 50, 30, key="fam_perc_renda")
                    
                    incluir_13 = st.checkbox("Incidir sobre 13º e Férias?", value=True, key="fam_13")
                    filhos = st.number_input("Quantidade de Filhos", 1, 5, 1, key="fam_filhos")
                    
                    if st.button("CALCULAR PENSÃO", key="btn_fam_pen"):
                        mensal = valor_base * (percentual / 100)
                        total_anual = mensal * 12
                        if incluir_13: total_anual += mensal + (mensal/3) 
                        
                        st.metric("Valor Mensal por Filho", f"R$ {mensal/filhos:,.2f}")
                        st.metric("Valor Mensal Total", f"R$ {mensal:,.2f}")
                        st.caption(f"Custo Anual Estimado: R$ {total_anual:,.2f}")

                with tab_partilha:
                    st.markdown("#### Simulador de Partilha de Bens (Divórcio)")
                    regime = st.selectbox("Regime de Bens", ["Comunhão Parcial", "Comunhão Universal", "Separação Total"], key="fam_reg")
                    
                    c_bens1, c_bens2 = st.columns(2)
                    imoveis = c_bens1.number_input("Valor Imóveis", min_value=0.0, key="fam_imo")
                    veiculos = c_bens2.number_input("Valor Veículos", min_value=0.0, key="fam_vei")
                    invest = c_bens1.number_input("Investimentos/Saldo", min_value=0.0, key="fam_inv")
                    dividas = c_bens2.number_input("Dívidas do Casal", min_value=0.0, key="fam_div")
                    
                    bem_particular = 0.0
                    if regime == "Comunhão Parcial":
                        bem_particular = st.number_input("Bens Particulares (Adquiridos antes/Herança)", min_value=0.0, key="fam_part")
                    
                    if st.button("SIMULAR PARTILHA", key="btn_fam_par"):
                        total_patrimonio = imoveis + veiculos + invest
                        patrimonio_comum = total_patrimonio - bem_particular
                        saldo_partilhavel = patrimonio_comum - dividas
                        
                        meacao = saldo_partilhavel / 2 if regime != "Separação Total" else 0
                        
                        if regime == "Separação Total":
                            st.info("Neste regime, não há comunhão de bens (salvo pacto em contrário). Cada um fica com o que está em seu nome.")
                        else:
                            st.success(f"💰 Patrimônio Total: R$ {total_patrimonio:,.2f}")
                            st.warning(f"📉 Dívidas: R$ {dividas:,.2f}")
                            st.metric("Meação (Para cada cônjuge)", f"R$ {meacao:,.2f}")
                            if bem_particular > 0:
                                st.caption(f"Obs: R$ {bem_particular:,.2f} foram excluídos da partilha por serem bens particulares.")

            # --- TRABALHISTA (MANTIDO) ---
            elif area_calc == "Trabalhista":
                # NOVAS ABAS DE CÁLCULO TRABALHISTA
                tab_resc, tab_he, tab_adic = st.tabs(["📄 Rescisão Completa", "⏰ Horas Extras & Reflexos", "⚠️ Adicionais (Insal./Peric.)"])

                with tab_resc:
                    st.markdown("#### Cálculo de Rescisão de Contrato (CLT)")
                    c1, c2 = st.columns(2)
                    salario_base = c1.number_input("Último Salário (R$)", min_value=0.0, key="trab_sal")
                    dt_admissao = c1.date_input("Data Admissão", value=date(2022, 1, 10), key="trab_adm")
                    dt_demissao = c2.date_input("Data Demissão", value=date.today(), key="trab_dem")
                    motivo_resc = c2.selectbox("Motivo", ["Dispensa Sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo (Culpa Recíproca)"], key="trab_mot")
                    
                    aviso_previo = st.radio("Aviso Prévio", ["Indenizado", "Trabalhado", "Não Cumprido"], horizontal=True, key="trab_avi")
                    ferias_vencidas = st.checkbox("Possui Férias Vencidas?", value=False, key="trab_fer")

                    if st.button("CALCULAR RESCISÃO", key="btn_trab"):
                        # Lógica de Tempo de Casa
                        anos_casa = (dt_demissao.year - dt_admissao.year)
                        if dt_demissao.month < dt_admissao.month: anos_casa -= 1
                        
                        # Aviso Prévio Proporcional (Lei 12.506)
                        dias_aviso = 30
                        if anos_casa >= 1: dias_aviso += min(3 * anos_casa, 60) # Max 90 dias total

                        val_aviso = 0
                        if motivo_resc == "Dispensa Sem Justa Causa":
                            if aviso_previo == "Indenizado": val_aviso = (salario_base / 30) * dias_aviso
                            
                        # Proporcionais (Simplificado para demonstração)
                        meses_trab_ano = dt_demissao.month
                        decimo_prop = (salario_base / 12) * meses_trab_ano
                        ferias_prop = (salario_base / 12) * meses_trab_ano + ((salario_base/12 * meses_trab_ano)/3)
                        
                        val_ferias_venc = 0
                        if ferias_vencidas: val_ferias_venc = salario_base + (salario_base/3)

                        saldo_salario = (salario_base/30) * dt_demissao.day

                        multa_40 = 0
                        if motivo_resc == "Dispensa Sem Justa Causa":
                            # Estimativa FGTS (8% mensal)
                            total_fgts_estimado = salario_base * 0.08 * (anos_casa * 12 + meses_trab_ano)
                            multa_40 = total_fgts_estimado * 0.40

                        total_bruto = saldo_salario + val_aviso + decimo_prop + ferias_prop + val_ferias_venc + multa_40

                        st.divider()
                        col_res1, col_res2, col_res3 = st.columns(3)
                        col_res1.metric("Saldo de Salário", f"R$ {saldo_salario:,.2f}")
                        col_res1.metric("Aviso Prévio", f"R$ {val_aviso:,.2f}")
                        col_res2.metric("13º Proporcional", f"R$ {decimo_prop:,.2f}")
                        col_res2.metric("Férias (+1/3)", f"R$ {ferias_prop + val_ferias_venc:,.2f}")
                        col_res3.metric("Multa 40% FGTS", f"R$ {multa_40:,.2f}")
                        col_res3.metric("TOTAL ESTIMADO", f"R$ {total_bruto:,.2f}", delta="Bruto")

                with tab_he:
                    st.markdown("#### Cálculo de Horas Extras com Reflexos")
                    c_he1, c_he2 = st.columns(2)
                    salario_hora = c_he1.number_input("Salário Mensal", min_value=0.0, value=2500.0, key="he_sal")
                    divisor = c_he1.number_input("Divisor (Mensalista)", value=220, key="he_div")
                    qtd_horas = c_he2.number_input("Média de Horas Extras/Mês", value=10, key="he_qtd")
                    adicional = c_he2.selectbox("Adicional", ["50%", "60%", "100%"], key="he_add")
                    
                    if st.button("CALCULAR H.E.", key="btn_he"):
                        valor_hora = salario_hora / divisor
                        perc = 1.5 if adicional == "50%" else (1.6 if adicional == "60%" else 2.0)
                        valor_he_mensal = valor_hora * perc * qtd_horas
                        
                        # Reflexo DSR (Estimativa 1/6)
                        reflexo_dsr = valor_he_mensal / 6 
                        # Reflexo FGTS (8%)
                        reflexo_fgts = (valor_he_mensal + reflexo_dsr) * 0.08
                        
                        total_he = valor_he_mensal + reflexo_dsr + reflexo_fgts
                        
                        st.success(f"Valor Mensal das H.E.: R$ {valor_he_mensal:,.2f}")
                        st.info(f"Reflexo DSR: R$ {reflexo_dsr:,.2f} | Reflexo FGTS: R$ {reflexo_fgts:,.2f}")
                        st.metric("Total Mensal Integrado", f"R$ {total_he:,.2f}")

                with tab_adic:
                    st.markdown("#### Adicionais de Insalubridade e Periculosidade")
                    tipo_add = st.radio("Tipo", ["Insalubridade", "Periculosidade"], horizontal=True, key="add_tipo")
                    salario_base_add = st.number_input("Salário Base para Cálculo", value=2500.0, key="add_sal")
                    salario_minimo = 1509.00 # Base 2025 aprox
                    
                    grau = "N/A"
                    if tipo_add == "Insalubridade":
                        grau = st.selectbox("Grau", ["Mínimo (10%)", "Médio (20%)", "Máximo (40%)"], key="add_grau")
                        base_calc_insal = st.radio("Base de Cálculo Insalubridade", ["Salário Mínimo", "Salário Base"], horizontal=True, key="add_base")
                    else:
                        st.write("Periculosidade é fixada em 30% sobre o Salário Base.")

                    if st.button("CALCULAR ADICIONAL", key="btn_add"):
                        valor_add = 0
                        if tipo_add == "Periculosidade":
                            valor_add = salario_base_add * 0.30
                        else:
                            base = salario_minimo if base_calc_insal == "Salário Mínimo" else salario_base_add
                            perc_insal = 0.10 if "Mínimo" in grau else (0.20 if "Médio" in grau else 0.40)
                            valor_add = base * perc_insal
                        
                        st.metric(f"Valor do Adicional ({tipo_add})", f"R$ {valor_add:,.2f}")
                        st.caption("Lembre-se de pedir reflexos em 13º, Férias e FGTS na petição!")

            # --- CRIMINAL (MANTIDO) ---
            elif area_calc == "Criminal":
                st.markdown("#### 🚔 Dosimetria da Pena (Estimativa)")
                pena_base = st.number_input("Pena Base (Anos)", min_value=0, key="crim_pen")
                agravantes = st.number_input("Qtd. Agravantes", min_value=0, key="crim_agra")
                atenuantes = st.number_input("Qtd. Atenuantes", min_value=0, key="crim_ate")
                if st.button("CALCULAR PENA", key="btn_crim"):
                    pena = pena_base + ((agravantes - atenuantes) * (pena_base/6))
                    st.warning(f"⚖️ Pena Estimada: {pena:.1f} anos")
            
            # --- BANCÁRIO (AGORA DENTRO DE CÍVEL, MAS MANTIDO PARA COMPATIBILIDADE SELECIONADA DIRETAMENTE) ---
            elif area_calc == "Bancário":
                st.info("Acesse a aba 'Cível' para a calculadora bancária completa.")
            
    else:
        # Mostra o bloqueio da área que ele tentou acessar
        tela_bloqueio(area_calc, "149")

# 4. AUDIENCIA (BLOQUEIO POR ÁREA)
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ ESTRATEGISTA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
    
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
        # Lógica de papéis dinâmica
        opcoes_papel = ["Advogado do Autor", "Advogado do Réu"] # Padrão Cível
        if area_aud == "Trabalhista":
            opcoes_papel = ["Advogado do Reclamante", "Advogado da Reclamada"]
        elif area_aud == "Criminal":
            opcoes_papel = ["Defesa", "Acusação/MP"]
            
        with c1: papel = st.selectbox("Papel", opcoes_papel)
        with c2: perfil_juiz = st.selectbox("Perfil Juiz", ["Padrão", "Rígido", "Conciliador"])
        detalhes = st.text_area("Resumo do Caso:")
        upload_autos = st.file_uploader("Autos (PDF) - Opcional", type="pdf")
        
        if st.button("🔮 SIMULAR"):
            if detalhes:
                with st.spinner("Simulando..."):
                    ctx = f"[DOC]: {extrair_texto_pdf(upload_autos)}" if upload_autos else ""
                    prompt = f"Estrategista {area_aud}. Papel: {papel}. Juiz: {perfil_juiz}. Caso: {detalhes} {ctx}. Gere perguntas e riscos."
                    # CHAMADA DA NOVA FUNÇÃO INTELIGENTE
                    api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                    res = tentar_gerar_conteudo(prompt, api_key_to_use)
                    if "❌" in res: st.error(res)
                    else:
                        st.markdown(res)
                        st.download_button("BAIXAR ROTEIRO", gerar_word(res), "Roteiro_Audiencia.docx")
    else: tela_bloqueio(area_aud, "149")

# 5. GESTÃO DE CASOS (LIBERADO)
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

# 6. MONITOR (LIBERADO PARA PLANOS PAGOS)
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
                                        api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                                        res = tentar_gerar_conteudo(f"Extraia prazos: {m['corpo']}", api_key_to_use)
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
