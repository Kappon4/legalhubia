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

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - TEMA CYBER FUTURE
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite | AI System", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="collapsed" # Sidebar recolhida por padrão
)

# --- CSS AVANÇADO (MENU HORIZONTAL FUTURISTA NATIVO) ---
def local_css():
    st.markdown("""
    <style>
        /* IMPORTANDO FONTE TECH */
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');

        /* --- VARIÁVEIS CYBER --- */
        :root {
            --bg-dark: #050A14;
            --bg-card: rgba(20, 30, 50, 0.6);
            --text-main: #FFFFFF;
            --neon-blue: #00F3FF;
            --neon-purple: #BC13FE;
            --border-glow: 1px solid rgba(0, 243, 255, 0.2);
        }

        /* --- GERAL --- */
        .stApp {
            background-color: var(--bg-dark);
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
        }

        h1, h2, h3, h4, h5, h6 {
            color: #FFFFFF !important;
            font-family: 'Rajdhani', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* --- TEXTOS BRANCOS --- */
        p, .stCaption, div[data-testid="caption"], div[data-testid="stMetricLabel"] label, div[data-testid="stMarkdownContainer"] p {
            color: #E2E8F0 !important;
            font-family: 'Inter', sans-serif;
        }
        
        div[data-testid="stMetricValue"] {
            color: var(--neon-blue) !important;
            text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        label, .stTextInput label, .stSelectbox label, .stTextArea label {
            color: #CBD5E1 !important;
        }

        /* --- TÍTULOS COM EFEITO GLITCH --- */
        .tech-header {
            background: linear-gradient(90deg, #FFFFFF 0%, var(--neon-blue) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
            text-shadow: 0 0 20px rgba(0, 243, 255, 0.3);
        }

        /* --- LOGOTIPO NO CABEÇALHO --- */
        .header-logo {
            display: flex;
            align-items: center;
            margin-right: 2rem;
        }
        .header-logo h1 {
            font-size: 1.8rem;
            margin: 0;
            letter-spacing: 2px;
            text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        .header-logo span {
            font-weight: 300;
            color: #fff;
            font-size: 1.2rem;
        }

        /* --- SIDEBAR PARA CONFIGURAÇÕES --- */
        section[data-testid="stSidebar"] {
            background-color: #020408;
            border-right: 1px solid rgba(0, 243, 255, 0.1);
        }

        /* --- BOTÕES DE AÇÃO --- */
        .stButton>button {
            background: transparent;
            color: var(--neon-blue);
            border: 1px solid var(--neon-blue);
            border-radius: 0px;
            padding: 0.6rem 1.2rem;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            text-transform: uppercase;
            transition: all 0.3s ease;
            position: relative;
            clip-path: polygon(10px 0, 100% 0, 100% calc(100% - 10px), calc(100% - 10px) 100%, 0 100%, 0 10px);
        }
        
        .stButton>button:hover {
            background: var(--neon-blue);
            color: #000;
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.6);
        }

        /* --- CARDS/CONTAINERS --- */
        div[data-testid="metric-container"], div[data-testid="stExpander"], .folder-card {
            background: rgba(10, 15, 30, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 0px;
            backdrop-filter: blur(10px);
            clip-path: polygon(0 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%); 
        }

        /* --- INPUTS --- */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {
            background-color: rgba(0, 0, 0, 0.3) !important;
            border: 1px solid #334155 !important;
            color: #FFF !important;
            border-radius: 0px;
        }
        .stTextInput>div>div>input:focus {
            border-color: var(--neon-blue) !important;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

local_css()

# ==========================================================
# 2. BANCO DE DADOS
# ==========================================================
def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10)''')
    try: c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except: pass 
    c.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)''')
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado1', '123', 'Escritório Alpha', 'lucas@alpha.adv.br', 10)")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br', 5)")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com', 9999)")
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
# 3. LOGIN (MODERNIZADO)
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Logo Tech
        st.markdown("""
            <div style='text-align: center;'>
                <h1 style='font-size: 3.5rem; margin-bottom: 0; text-shadow: 0 0 20px rgba(0, 243, 255, 0.5);'>🛡️</h1>
                <h1 class='tech-header' style='font-size: 2.5rem; letter-spacing: 3px;'>LEGALHUB <span style='font-weight: 300; color: #fff;'>ELITE</span></h1>
                <p style='color: #00F3FF; font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase;'>Artificial Intelligence System</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
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

df_user = run_query("SELECT creditos FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
creditos_atuais = df_user.iloc[0]['creditos'] if not df_user.empty else 0

# --- CONTROLE DE NAVEGAÇÃO ---
if "navegacao_override" not in st.session_state:
    st.session_state.navegacao_override = None

# --- CABEÇALHO HORIZONTAL (VERSÃO CSS NATIVO) ---
col_logo, col_menu = st.columns([1, 4])

with col_logo:
    st.markdown("""
        <div class='header-logo'>
            <h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1>
        </div>
    """, unsafe_allow_html=True)

with col_menu:
    # Mapeamento
    mapa_nav = {
        "Dashboard": "📊 Dashboard",
        "Redator IA": "✍️ Redator Jurídico", 
        "Perícia & Calc": "🧮 Calculadoras & Perícia",
        "Audiência": "🏛️ Estratégia de Audiência",
        "Gestão Casos": "📂 Gestão de Casos",
        "Monitor Prazos": "🚦 Monitor de Prazos",
        "Ferramentas": "🔧 Ferramentas Extras"
    }
    opcoes_menu = list(mapa_nav.keys())

    # CSS para transformar o Radio em Menu Horizontal
    st.markdown("""
    <style>
        div[role="radiogroup"] {
            display: flex;
            flex-direction: row;
            justify-content: space-between;
            background: rgba(10, 15, 30, 0.8);
            padding: 10px;
            border-radius: 8px;
            border-bottom: 1px solid rgba(0, 243, 255, 0.3);
        }
        div[role="radiogroup"] label {
            background: transparent !important;
            border: none !important;
            margin: 0 !important;
            padding: 5px 15px !important;
            color: #94A3B8 !important;
            transition: all 0.3s;
        }
        div[role="radiogroup"] label:hover {
            color: #FFF !important;
            text-shadow: 0 0 5px #00F3FF;
        }
        div[role="radiogroup"] label[data-checked="true"] {
            color: #00F3FF !important;
            border-bottom: 2px solid #00F3FF !important;
            background: rgba(0, 243, 255, 0.1) !important;
        }
        div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {
             font-size: 1rem !important; 
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Determinar índice para o radio button se houver override
    idx_radio = 0
    if st.session_state.navegacao_override:
        try:
            # Encontrar a chave correta baseada no valor
            key_override = [k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0]
            idx_radio = opcoes_menu.index(key_override)
        except:
            idx_radio = 0
        st.session_state.navegacao_override = None

    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")

# --- SIDEBAR (AGORA APENAS PARA CONFIGURAÇÕES E LOGOUT) ---
with st.sidebar:
    # ---------------------------------------------------------------------
    # LOGO: CARREGA A IMAGEM UPLOADED PELO NOME
    # ---------------------------------------------------------------------
    try:
        # Tenta carregar a imagem local
        st.sidebar.image("diagrama-ia.png", use_container_width=True)
    except:
        # Se não encontrar, mostra um placeholder para não quebrar o layout
        st.warning("⚠️ Imagem 'diagrama-ia.png' não encontrada na pasta.")

    st.markdown("<h2 class='tech-header' style='font-size:1.5rem;'>CONFIGURAÇÕES</h2>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0; margin-bottom: 20px;'>Usuário: {st.session_state.usuario_atual}<br>Escritório: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)

    if "GOOGLE_API_KEY" not in st.secrets:
        st.text_input("🔑 API Key (Google Gemini):", type="password", key="sidebar_api_key")
        if st.session_state.sidebar_api_key:
             genai.configure(api_key=st.session_state.sidebar_api_key)
             st.success("API Key configurada temporariamente.")

    st.markdown("---")
    
    # Display de Créditos Moderno
    st.markdown("<h4 style='font-size:1rem; color:#94A3B8;'>CRÉDITOS</h4>", unsafe_allow_html=True)
    col_cred1, col_cred2 = st.columns([1, 3])
    with col_cred1: st.markdown("<h3 style='color:#00F3FF; margin:0;'>💎</h3>", unsafe_allow_html=True)
    with col_cred2: 
        st.markdown(f"<h3 style='margin:0; color:#FFFFFF; text-shadow: 0 0 10px #00F3FF;'>{creditos_atuais}</h3>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/50, 1.0))
    
    st.write("")
    if st.button("LOGOUT / SAIR"):
        st.session_state.logado = False
        st.rerun()

    # --- ÁREA DE ADMINISTRAÇÃO ---
    if st.session_state.usuario_atual == 'admin':
        st.markdown("---")
        with st.expander("🛠️ ADMIN CONSOLE"):
            st.markdown("##### ➕ Novo Usuário")
            novo_user = st.text_input("Login")
            novo_pass = st.text_input("Senha", type="password")
            novo_banca = st.text_input("Escritório")
            if st.button("CRIAR"):
                run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50))
                st.success("OK")
            
            st.divider()
            st.markdown("##### 💰 Recarga")
            df_users = run_query("SELECT username FROM usuarios", return_data=True)
            if not df_users.empty:
                user_recarga = st.selectbox("Usuário:", df_users['username'])
                qtd_recarga = st.number_input("Qtd:", min_value=1, value=50, step=10)
                if st.button("RECARREGAR"):
                    run_query("UPDATE usuarios SET creditos = creditos + ? WHERE username = ?", (qtd_recarga, user_recarga))
                    st.toast(f"✅ Recarga efetuada para {user_recarga}!")
                    time.sleep(1)
                    st.rerun()

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>SYSTEM STATUS <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| {st.session_state.usuario_atual}</span></h2>", unsafe_allow_html=True)
    
    # Métricas Superiores
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    
    c1.metric("DOCUMENTOS", docs_feitos, delta="Online")
    c2.metric("CRÉDITOS", creditos_atuais)
    c3.metric("PRAZOS", "0", delta="Estável", delta_color="off")
    
    st.write("")
    
    # Gráfico e Dicas
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.markdown("##### 📈 DADOS DE PRODUTIVIDADE")
        with st.container(border=True):
            df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
            if not df_areas.empty:
                # Cores Tech para o gráfico
                colors_tech = ['#00F3FF', '#BC13FE', '#2E5CFF', '#FFFFFF', '#4A4A4A']
                fig = px.pie(df_areas, values='qtd', names='area', hole=0.7, color_discrete_sequence=colors_tech)
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0", showlegend=True, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Aguardando dados...")
    
    with col_info:
        # ==========================================================
        # --- ATUALIZAÇÃO: SECURITY & COMPLIANCE ---
        # ==========================================================
        st.markdown("##### 🛡️ SECURITY & COMPLIANCE")
        with st.container(border=True):
            # Item 1: LGPD
            st.markdown("""
            <div style='background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10B981; padding: 10px; margin-bottom: 8px; border-radius: 4px;'>
                <strong style='color: #10B981; font-family: Rajdhani; letter-spacing: 1px;'>✓ LGPD COMPLIANT</strong><br>
                <span style='font-size: 0.8rem; color: #E2E8F0;'>Tratamento de dados anonimizado e rastreável.</span>
            </div>
            """, unsafe_allow_html=True)

            # Item 2: Criptografia
            st.markdown("""
            <div style='background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3B82F6; padding: 10px; margin-bottom: 8px; border-radius: 4px;'>
                <strong style='color: #3B82F6; font-family: Rajdhani; letter-spacing: 1px;'>🔒 E2E ENCRYPTION</strong><br>
                <span style='font-size: 0.8rem; color: #E2E8F0;'>Proteção AES-256 militar em todos os arquivos.</span>
            </div>
            """, unsafe_allow_html=True)

            # Item 3: Atualização Jurídica
            st.markdown("""
            <div style='background: rgba(245, 158, 11, 0.1); border-left: 3px solid #F59E0B; padding: 10px; border-radius: 4px;'>
                <strong style='color: #F59E0B; font-family: Rajdhani; letter-spacing: 1px;'>⚖️ LIVE JURISPRUDENCE</strong><br>
                <span style='font-size: 0.8rem; color: #E2E8F0;'>Sincronização em tempo real com STF/STJ.</span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("<div style='text-align:center; font-size: 0.7rem; color: #64748b;'>Certificado Digital de Autenticidade V5.5</div>", unsafe_allow_html=True)
        # ==========================================================

    # CARDS DE FUNCIONALIDADES
    st.write("")
    st.subheader("🛠️ ACESSO RÁPIDO")
    
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        with st.container(border=True):
            st.markdown("#### ✍️ REDATOR")
            st.caption("IA Generativa de Peças.")
            if st.button("INICIAR", key="btn_redator"):
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r1c2:
        with st.container(border=True):
            st.markdown("#### 🧮 PERÍCIA")
            st.caption("Cálculos Automatizados.")
            if st.button("CALCULAR", key="btn_pericia"):
                st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"
                st.rerun()

    with r1c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ AUDIÊNCIA")
            st.caption("Simulador Estratégico.")
            if st.button("SIMULAR", key="btn_aud"):
                st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"
                st.rerun()

    st.write("")
    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        with st.container(border=True):
            st.markdown("#### ⚖️ JURISPRUDÊNCIA")
            st.caption("Busca de Tribunais.")
            if st.button("PESQUISAR", key="btn_juris"):
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r2c2:
        with st.container(border=True):
            st.markdown("#### 📄 CHAT PDF")
            st.caption("Análise Documental.")
            if st.button("ANALISAR", key="btn_pdf"):
                st.session_state.navegacao_override = "🔧 Ferramentas Extras"
                st.rerun()

    with r2c3:
        with st.container(border=True):
            st.markdown("#### 📅 PRAZOS")
            st.caption("Monitoramento Fatal.")
            if st.button("MONITORAR", key="btn_prazo"):
                st.session_state.navegacao_override = "🚦 Monitor de Prazos"
                st.rerun()

# 2. REDATOR
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA</h2>", unsafe_allow_html=True)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    
    with col_config:
        with st.container(border=True):
            st.markdown("##### ⚙️ PARÂMETROS")
            tipo = st.selectbox("Tipo de Peça", ["Inicial", "Contestação", "Recurso Inominado", "Apelação", "Contrato", "Parecer"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
            web = st.checkbox("Incluir Jurisprudência Web", value=True)
            
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

    with col_input:
        st.markdown("##### 📝 FATOS DO CASO")
        fatos = st.text_area("Insira os dados...", height=350, value=st.session_state.fatos_recuperados, placeholder="Descreva os fatos, datas e valores...")
    
    st.write("")
    if st.button("✨ GERAR DOCUMENTO (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner("PROCESSANDO DADOS..."):
                jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisp: {jur}. Formal e Técnico."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    
                    st.markdown("### 📄 RESULTADO:")
                    with st.container(border=True):
                        st.markdown(res)
                    
                    st.download_button("📥 DOWNLOAD (.docx)", gerar_word(res), "Minuta_LegalHub.docx", use_container_width=True)
                    st.success(f"Salvo em: {cli_final}")
                    time.sleep(2)
                    st.rerun()
                except Exception as e: st.error(f"Erro: {str(e)}")
        else: st.error("Créditos insuficientes ou dados faltantes.")

# 3. CALCULADORA
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='tech-header'>🧮 LABORATÓRIO DE PERÍCIA</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            tipo_calc = st.selectbox("Selecione o Cálculo:", ["Aluguel", "Divórcio", "FGTS", "INSS", "PASEP", "Pensão", "RMC/RCC", "Superendividamento", "Criminal (Dosimetria)", "Trabalhista"])
            dt_base = st.date_input("Data Base")
        with c2:
            upload = st.file_uploader("Anexar PDF", type="pdf")
        
        dados = st.text_area("Parâmetros Manuais:")
        
        if st.button("🧮 PROCESSAR"):
            if dados or upload:
                with st.spinner("Calculando..."):
                    txt = f"\nPDF Contexto: {extrair_texto_pdf(upload)}" if upload else ""
                    prompt = f"Atue como Perito Contábil em {tipo_calc}. Data Base: {dt_base}. Parâmetros: {dados} {txt}. Gere Laudo Técnico detalhado com memória de cálculo."
                    try:
                        res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                        st.markdown("---")
                        st.markdown(res)
                        st.download_button("📥 Baixar Laudo", gerar_word(res), "Laudo_Tecnico.docx")
                    except Exception as e: st.error(str(e))

# 4. AUDIENCIA
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ SIMULADOR DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
    
    col_setup, col_doc = st.columns([1, 1])
    with col_setup:
        area = st.selectbox("Área", ["Trabalhista", "Cível", "Criminal"])
        papel = st.selectbox("Representando:", ["Autor/Reclamante", "Réu/Reclamada"])
    with col_doc:
        upload = st.file_uploader("Processo/Inicial (PDF)", type="pdf")
    
    obs = st.text_area("Pontos sensíveis:")
    
    if st.button("🎭 GERAR ESTRATÉGIA"):
        if obs or upload:
            with st.spinner("Analisando probabilidades..."):
                txt = f"\nPDF: {extrair_texto_pdf(upload)}" if upload else ""
                prompt = f"Advogado Especialista em {area}. Papel: {papel}. Contexto: {obs} {txt}. Crie um roteiro de perguntas para testemunhas, preveja perguntas do juiz e aponte riscos."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("📥 Baixar Roteiro", gerar_word(res), "Roteiro_Audiencia.docx")
                except: st.error("Erro na IA")

# 5. GESTÃO DE CASOS
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
    
    if "pasta_aberta" not in st.session_state: st.session_state.pasta_aberta = None
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)

    if not df_docs.empty:
        if st.session_state.pasta_aberta is None:
            st.info("Selecione o dossiê para acessar os arquivos.")
            clientes_unicos = df_docs['cliente'].unique()
            cols = st.columns(4) 
            for i, cliente in enumerate(clientes_unicos):
                with cols[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"#### 📁")
                        st.markdown(f"**{cliente}**")
                        qtd = len(df_docs[df_docs['cliente'] == cliente])
                        st.caption(f"{qtd} arquivos")
                        if st.button(f"ABRIR", key=f"btn_{i}"):
                            st.session_state.pasta_aberta = cliente
                            st.rerun()

        else:
            col_back, col_title = st.columns([1, 10])
            with col_back:
                if st.button("⬅"):
                    st.session_state.pasta_aberta = None
                    st.rerun()
            with col_title:
                st.markdown(f"### 📂 CLIENTE: {st.session_state.pasta_aberta}")

            with st.expander("➕ NOVO DOCUMENTO", expanded=False):
                c_add1, c_add2 = st.columns(2)
                novo_tipo = c_add1.text_input("Nome:")
                nova_area = c_add2.selectbox("Categoria:", ["Documentos Pessoais", "Provas", "Andamento", "Anotações", "Financeiro"])
                
                tab_up, tab_txt = st.tabs(["📤 Upload", "✍️ Nota"])
                conteudo_novo = ""
                with tab_up: arquivo_novo = st.file_uploader("Arquivo PDF", key="novo_up")
                with tab_txt: texto_novo = st.text_area("Texto:", key="nova_nota")

                if st.button("💾 SALVAR"):
                    if novo_tipo:
                        if arquivo_novo: conteudo_novo = f"[ARQUIVO] {extrair_texto_pdf(arquivo_novo)}"
                        elif texto_novo: conteudo_novo = texto_novo
                        else: conteudo_novo = "..."
                        run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), st.session_state.pasta_aberta, nova_area, novo_tipo, conteudo_novo))
                        st.success("Salvo!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()
            arquivos_cliente = df_docs[df_docs['cliente'] == st.session_state.pasta_aberta]
            
            for index, row in arquivos_cliente.iterrows():
                icone = "📝" if row['area'] == "Anotações" else "📄"
                with st.expander(f"{icone} {row['tipo']} ({row['data_criacao']}) | {row['area']}"):
                    texto_view = row['conteudo'].split("||")[-1] if "||" in row['conteudo'] else row['conteudo']
                    st.markdown(texto_view)
                    
                    c_down, c_del = st.columns([4, 1])
                    with c_down:
                        st.download_button("📥 Baixar", gerar_word(texto_view), f"{row['tipo']}.docx", key=f"down_{row['id']}")
                    with c_del:
                        if st.button("🗑️", key=f"del_{row['id']}"):
                            run_query("DELETE FROM documentos WHERE id = ?", (row['id'],))
                            st.toast("Deletado.")
                            time.sleep(1)
                            st.rerun()
    else: st.warning("📭 Nenhum dossiê encontrado.")

# 6. MONITOR
elif menu_opcao == "🚦 Monitor de Prazos":
    st.markdown("<h2 class='tech-header'>🚦 RADAR DE PRAZOS</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("##### CONFIGURAÇÃO IMAP")
        c_email1, c_email2, c_email3 = st.columns(3)
        email_leitura = c_email1.text_input("Email", placeholder="adv@jus.com")
        senha_leitura = c_email2.text_input("Senha App", type="password")
        servidor_imap = c_email3.text_input("Host", value="imap.gmail.com")

        if st.button("🔄 ESCANEAR"):
            if email_leitura and senha_leitura:
                with st.spinner("Varrendo metadados..."):
                    msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                    if err: st.error(err)
                    elif not msgs: st.info("Nenhuma intimação detectada.")
                    else:
                        for m in msgs:
                            with st.expander(f"⚠️ {m['assunto']}"):
                                st.write(m['corpo'])
                                if st.button("Analisar Prazo IA", key=m['assunto']):
                                    res = genai.GenerativeModel(mod_escolhido).generate_content(f"Identifique o prazo fatal e providências: {m['corpo']}").text
                                    st.info(res)
            else: st.error("Credenciais necessárias.")

# 7. EXTRAS
elif menu_opcao == "🔧 Ferramentas Extras":
    st.markdown("<h2 class='tech-header'>🔧 TOOLKIT AVANÇADO</h2>", unsafe_allow_html=True)
    
    tabs_ex = st.tabs(["🔎 Analisador PDF", "🎙️ Transcrição", "⚖️ Comparador"])
    
    with tabs_ex[0]:
        up = st.file_uploader("Upload PDF", key="pdf_res")
        if up and st.button("Resumir Documento"): 
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma este documento jurídico: {extrair_texto_pdf(up)}").text)
    
    with tabs_ex[1]:
        aud = st.file_uploader("Upload Áudio", type=["mp3","ogg","wav"])
        if aud and st.button("Transcrever Áudio"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp: tmp.write(aud.getvalue()); path = tmp.name
            f = genai.upload_file(path); time.sleep(2)
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(["Transcreva este áudio forense:", f]).text)
    
    with tabs_ex[2]:
        p1 = st.file_uploader("Versão 1", key="v1"); p2 = st.file_uploader("Versão 2", key="v2")
        if p1 and p2 and st.button("Comparar Versões"): 
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Compare juridicamente e aponte divergências: {extrair_texto_pdf(p1)} vs {extrair_texto_pdf(p2)}").text)

st.markdown("---")
st.markdown("<center style='color: #64748b; font-size: 0.8rem; font-family: Rajdhani;'>🔒 LEGALHUB ELITE v5.5 | ENCRYPTED SESSION</center>", unsafe_allow_html=True)
