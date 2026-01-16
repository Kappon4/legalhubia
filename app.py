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
import imaplib
import email
from email.header import decode_header
import smtplib
import ssl
from email.message import EmailMessage
import plotly.express as px
import base64
import requests
import sys
import subprocess

# --- PROFESSIONAL DATABASE LIBRARY ---
try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

# --- IMPORT ERROR HANDLING ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument, PermissionDenied

# ==========================================================
# 1. VISUAL CONFIGURATION - CYBER FUTURE THEME
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite | AI System", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# 🛑 DATABASE CONFIGURATION (SUPABASE/POSTGRES)
# ==========================================================
try:
    # Tenta pegar as senhas configuradas no site do Streamlit (Nuvem)
    DB_URI = st.secrets["DB_URI"]
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
    USAR_SQLITE_BACKUP = False
except:
    # Fallback local (Seu PC)
    # Senha corrigida (apenas um @)
    DB_URI = "postgresql://postgres:0OquFTc7ovRHTBGM@db.qhcjfmzkwczjupkfpmdk.supabase.co:5432/postgres"
    API_KEY_FIXA = "AIzaSyA5lMfeDUE71k6BOOxYRZDtOolPZaqCurA"
    USAR_SQLITE_BACKUP = False

def get_db_connection():
    """Manages database connection robustly."""
    if USAR_SQLITE_BACKUP:
        import sqlite3
        return sqlite3.connect('legalhub.db')
    else:
        return psycopg2.connect(DB_URI)

def run_query(query, params=(), return_data=False):
    """Executes queries adapting syntax between SQLite (?) and Postgres (%s)."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Syntax adaptation (SQLite uses ? / Postgres uses %s)
        if not USAR_SQLITE_BACKUP:
            query = query.replace('?', '%s')
            
        c.execute(query, params)
        
        if return_data:
            data = c.fetchall()
            if c.description:
                col_names = [desc[0] for desc in c.description]
                conn.close()
                return pd.DataFrame(data, columns=col_names)
            else:
                conn.close()
                return pd.DataFrame()
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        if conn: conn.close()
        return None

# ==========================================================
# 2. GENERAL FUNCTIONS
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

# --- NOVA FUNÇÃO DE CÁLCULO TRABALHISTA (CLT) ---
def calcular_rescisao_completa(admissao, demissao, salario, motivo, saldo_fgts, ferias_vencidas, aviso_tipo):
    # Converte para objetos de data
    formato_data = "%Y-%m-%d"
    d1 = datetime.strptime(str(admissao), formato_data)
    d2 = datetime.strptime(str(demissao), formato_data)
    
    # Cálculo do tempo de serviço
    meses_trabalhados = (d2.year - d1.year) * 12 + d2.month - d1.month
    anos_completo = meses_trabalhados // 12
    dias_no_mes = d2.day
    
    verbas = {}
    
    # 1. Saldo de Salário
    saldo_salario = (salario / 30) * dias_no_mes
    verbas["Saldo de Salário"] = saldo_salario
    
    # 2. Aviso Prévio (Lei 12.506/2011 - 3 dias por ano)
    dias_aviso = 30 + (3 * anos_completo)
    if dias_aviso > 90: dias_aviso = 90
    
    if motivo == "Demissão sem Justa Causa":
        if aviso_tipo == "Indenizado":
            valor_aviso = (salario / 30) * dias_aviso
            verbas[f"Aviso Prévio Indenizado ({dias_aviso} dias)"] = valor_aviso
            # Projeta data para 13o e Férias
            d2 = d2 + timedelta(days=dias_aviso)
    elif motivo == "Pedido de Demissão" and aviso_tipo == "Não Trabalhado":
        verbas["Desconto Aviso Prévio"] = -salario
        
    # Recalcula meses proporcionais com a projeção
    meses_ano_atual = d2.month
    if d2.day < 15: meses_ano_atual -= 1 # Fração inferior a 15 dias não conta
    if meses_ano_atual == 0: meses_ano_atual = 12 # Ajuste virada de ano
    
    # 3. 13º Salário Proporcional
    if motivo != "Justa Causa":
        decimo = (salario / 12) * meses_ano_atual
        verbas[f"13º Salário Proporcional ({meses_ano_atual}/12)"] = decimo
        
    # 4. Férias
    if motivo != "Justa Causa":
        # Vencidas
        if ferias_vencidas:
            verbas["Férias Vencidas + 1/3"] = salario + (salario/3)
        
        # Proporcionais
        val_ferias_prop = (salario / 12) * meses_ano_atual
        verbas[f"Férias Proporcionais ({meses_ano_atual}/12) + 1/3"] = val_ferias_prop + (val_ferias_prop/3)

    # 5. Multa FGTS
    if motivo == "Demissão sem Justa Causa" or motivo == "Rescisão Indireta":
        verbas["Multa 40% FGTS"] = saldo_fgts * 0.4
    elif motivo == "Acordo (Comum)":
        verbas["Multa 20% FGTS"] = saldo_fgts * 0.2

    return verbas

# --- ROBUST AI FUNCTION ---
def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    
    if not chave:
        return "⚠️ Error: API Key not configured. Insert in sidebar."
    
    genai.configure(api_key=chave)
    
    modelos_para_tentar = ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    
    erro_final = ""
    
    for modelo in modelos_para_tentar:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            erro_final = str(e)
            continue 

    return f"❌ Falha na IA. Verifique sua chave API. Erro: {erro_final}"

def buscar_intimacoes_email(user, pwd, server):
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, pwd)
        mail.select("inbox")
        status, msgs = mail.search(None, '(UNSEEN)')
        if not msgs[0]: return [], "Nothing new."
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
    st.markdown(f"""
    <div class='lock-screen' style='border-color:{cor};'>
        <div class='lock-icon'>🔒</div>
        <div class='lock-title' style='color:{cor};'>ACESSO RESTRITO</div>
        <p class='lock-desc'>Recurso exclusivo do plano {area_necessaria.upper()} ou FULL.</p>
    </div>
    """, unsafe_allow_html=True)

def buscar_jurisprudencia_oficial(tema, area):
    sites = ""
    if area == "Criminal": sites = "site:stf.jus.br OR site:stj.jus.br OR site:conjur.com.br"
    elif area == "Trabalhista": sites = "site:tst.jus.br OR site:csjt.jus.br OR site:trtsp.jus.br"
    elif area == "Civil" or area == "Família" or area == "Bancário": sites = "site:stj.jus.br OR site:tjsp.jus.br OR site:ibdfam.org.br"
    else: sites = "site:jusbrasil.com.br"
    query = f"{tema} {sites}"
    try:
        res = DDGS().text(query, region="br-pt", max_results=4)
        if res: return "\n".join([f"- {r['body']} (Source: {r['href']})" for r in res])
        return "Nenhuma jurisprudência encontrada nas bases oficiais."
    except: return "Erro de conexão com bases jurídicas."

# --- CSS ---
def local_css():
    bg_image_b64 = get_base64_of_bin_file("unnamed.jpg")
    bg_css = f"""
    .stApp::before {{
        content: ""; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        width: 60%; height: 60%; background-image: url("data:image/jpeg;base64,{bg_image_b64}");
        background-size: contain; background-repeat: no-repeat; background-position: center;
        opacity: 0.08; z-index: 0; pointer-events: none; animation: float-logo 15s ease-in-out infinite;
    }}
    @keyframes float-logo {{ 0%, 100% {{ transform: translate(-50%, -50%) translateY(0px); }} 50% {{ transform: translate(-50%, -50%) translateY(-20px); }} }}
    """ if bg_image_b64 else ""
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');
        :root {{ --bg-dark: #020617; --neon-blue: #00F3FF; --neon-red: #FF0055; --text-main: #FFFFFF; --bg-card: rgba(15, 23, 42, 0.6); }}
        .stApp {{ background-color: var(--bg-dark); color: var(--text-main); font-family: 'Inter'; }}
        {bg_css}
        h1, h2, h3, h4, h5, h6 {{ font-family: 'Rajdhani'; color: #FFF !important; text-transform: uppercase; letter-spacing: 1.5px; z-index: 1; position: relative; }}
        .tech-header {{ background: linear-gradient(90deg, #FFF, var(--neon-blue)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 700; }}
        .plan-card {{ background: rgba(15,23,42,0.85); border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; text-align: center; }}
        .lock-screen {{ border: 1px solid var(--neon-red); background: rgba(255, 0, 85, 0.05); border-radius: 10px; padding: 40px; text-align: center; margin-top: 20px; }}
        .lock-title {{ color: var(--neon-red) !important; font-family: 'Rajdhani'; font-size: 2rem; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)
local_css()

# ==========================================================
# 4. LOGIN
# ==========================================================
# Garante tabelas criadas
try:
    if USAR_SQLITE_BACKUP:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    else:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    
    run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full'))
except: pass

if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""
if "plano_atual" not in st.session_state: st.session_state.plano_atual = "starter"

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        img_base64 = get_base64_of_bin_file("diagrama-ia.png")
        if img_base64: st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo" style="width: 250px;"></div>""", unsafe_allow_html=True)
        else: st.markdown("<h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)
        
        st.markdown("""<div style='text-align: center;'><h1 class='tech-header' style='font-size: 2.5rem; letter-spacing: 3px;'>LEGALHUB <span style='font-weight: 300; color: #fff;'>ELITE</span></h1><p style='color: #00F3FF; font-size: 0.8rem; letter-spacing: 2px;'>Artificial Intelligence System</p></div>""", unsafe_allow_html=True)

        if USAR_SQLITE_BACKUP:
            st.warning("⚠️ MODO SQLITE (VOLÁTIL). Configure a senha no DB_URI para salvar na nuvem.")
        else:
            st.success("☁️ BANCO DE DADOS NUVEM CONECTADO (SEGURO)")
            
        with st.container(border=True):
            username = st.text_input("ID Usuário")
            password = st.text_input("Chave de Acesso", type="password")
            if st.button("🔓 INICIAR SESSÃO", use_container_width=True):
                users = run_query("SELECT * FROM usuarios WHERE username = %s AND senha = %s", (username, password), return_data=True)
                if users is not None and not users.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = username
                    st.session_state.escritorio_atual = users.iloc[0]['escritorio']
                    st.session_state.plano_atual = users.iloc[0]['plano']
                    st.rerun()
                else: st.error("Acesso Negado.")
            st.markdown("<div style='text-align:center; margin-top:10px; color: #475569; font-size: 0.7rem; font-family: Rajdhani;'>SYSTEM V7.0 // SECURE</div>", unsafe_allow_html=True)
    st.stop()

# ==========================================================
# 5. SIDEBAR
# ==========================================================
if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
else: api_key = st.text_input("🔑 API Key:", type="password", key="sidebar_api_key")

df_user = run_query("SELECT creditos, plano FROM usuarios WHERE username = %s", (st.session_state.usuario_atual,), return_data=True)
if df_user is not None and not df_user.empty:
    creditos_atuais = df_user.iloc[0]['creditos']
    st.session_state.plano_atual = df_user.iloc[0]['plano']
else:
    creditos_atuais = 0

if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)
with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Contratos": "📜 Contratos", "Perícia & Calc": "🧮 Calculadoras & Perícia", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Planos & Upgrade"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.navegacao_override:
        try: idx_radio = opcoes_menu.index([k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0])
        except: pass
        st.session_state.navegacao_override = None
    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")
with st.sidebar:
    st.markdown("<h2 class='tech-header' style='font-size:1.5rem;'>CONFIGURAÇÕES</h2>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#E2E8F0;'>User: {st.session_state.usuario_atual}<br>Banca: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    
    p_label = st.session_state.plano_atual.upper()
    cor_p = "#FFFFFF"
    if p_label == "CRIMINAL": cor_p = "#FF0055"
    elif p_label == "TRABALHISTA": cor_p = "#00F3FF"
    elif p_label == "FULL": cor_p = "#FFD700"
    
    st.markdown(f"<div style='border:1px solid {cor_p}; padding:5px; border-radius:5px; text-align:center; color:{cor_p}; margin:10px 0; font-weight:bold;'>PLANO: {p_label}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<h4 style='font-size:1rem; color:#94A3B8;'>CRÉDITOS</h4>", unsafe_allow_html=True)
    c_cr1, c_cr2 = st.columns([1, 3])
    with c_cr1: st.markdown("<h3 style='color:#0EA5E9; margin:0;'>💎</h3>", unsafe_allow_html=True)
    with c_cr2: st.markdown(f"<h3 style='margin:0; color:#FFFFFF;'>{creditos_atuais}</h3>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/100, 1.0))

    if st.button("LOGOUT"): st.session_state.logado = False; st.rerun()

    if st.session_state.usuario_atual == 'admin':
        with st.expander("🛠️ ADMIN"):
            if st.button("Add 50 Créditos"): run_query("UPDATE usuarios SET creditos = creditos + 50 WHERE username = %s", (st.session_state.usuario_atual,)); st.rerun()

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| {st.session_state.usuario_atual.upper()}</span></h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    docs = run_query("SELECT count(*) FROM documentos WHERE escritorio = %s", (st.session_state.escritorio_atual,), return_data=True)
    qtd_docs = docs.iloc[0][0] if docs is not None and not docs.empty else 0
    c1.metric("DOCS GERADOS", qtd_docs)
    c2.metric("SALDO CRÉDITOS", creditos_atuais)
    c3.metric("STATUS DB", "Online ✅" if not USAR_SQLITE_BACKUP else "Local (Risco) ⚠️")

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

elif menu_opcao == "📜 Contratos":
    st.header("📜 Gerador de Contratos & Procurações")
    st.info("Nova funcionalidade ativa! Gere contratos blindados e procurações instantâneas.")
    
    tab_cont, tab_proc = st.tabs(["📝 Contrato de Honorários", "⚖️ Procuração Ad Judicia"])
    
    with tab_cont:
        c1, c2 = st.columns(2)
        contratado = st.session_state.escritorio_atual
        contratante = c1.text_input("Nome do Cliente (Contratante)")
        cpf_cnpj = c2.text_input("CPF/CNPJ do Cliente")
        
        objeto = st.text_area("Objeto do Contrato (Descreva o serviço)", placeholder="Ex: Defesa na ação de cobrança nº X, ou Assessoria jurídica mensal...")
        
        cc1, cc2, cc3 = st.columns(3)
        valor = cc1.number_input("Valor dos Honorários (R$)", min_value=0.0, step=100.0)
        exito = cc2.number_input("Taxa de Êxito (%)", min_value=0, max_value=50, value=30)
        forma_pag = cc3.selectbox("Forma de Pagamento", ["À Vista", "Entrada + Parcelas", "Ao final do processo", "Mensal (Partido)"])
        
        foro = st.text_input("Foro de Eleição (Cidade/Estado)", value="Sorocaba/SP")
        
        if st.button("GERAR CONTRATO"):
            if contratante and objeto:
                with st.spinner("Redigindo cláusulas de proteção..."):
                    prompt_contrato = f"""
                    Atue como Advogado Sênior Especialista em Gestão Legal.
                    Redija um CONTRATO DE HONORÁRIOS ADVOCATÍCIOS completo e blindado.
                    PARTES:
                    - CONTRATADO: {contratado} (Advogados).
                    - CONTRATANTE: {contratante}, CPF/CNPJ: {cpf_cnpj}.
                    OBJETO: {objeto}.
                    HONORÁRIOS:
                    - Valor Fixo: R$ {valor}.
                    - Condição de Pagamento: {forma_pag}.
                    - Honorários de Êxito (Ad Exitum): {exito}% sobre o proveito econômico.
                    CLÁUSULAS OBRIGATÓRIAS:
                    1. Inadimplência (multa de 10%, juros de 1% a.m. e correção monetária).
                    2. Rescisão antecipada (pagamento proporcional).
                    3. Honorários de Sucumbência pertencem exclusivamente ao advogado.
                    4. Despesas processuais por conta do cliente.
                    5. Foro: {foro}.
                    Estilo: Formal, jurídico, direto e seguro.
                    """
                    api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                    res = tentar_gerar_conteudo(prompt_contrato, api_key_to_use)
                    if "❌" not in res:
                        st.markdown("### 📄 Minuta do Contrato")
                        with st.container(border=True):
                            st.markdown(res)
                        
                        # Salvar
                        q = "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)" if not USAR_SQLITE_BACKUP else "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)"
                        run_query(q, (st.session_state.escritorio_atual, str(date.today()), contratante, "Contratos", "Contrato Honorários", res))
                        
                        st.download_button("📥 Baixar Contrato (.docx)", gerar_word(res), f"Contrato_{contratante}.docx")
                    else: st.error(res)
            else: st.warning("Preencha o nome do cliente e o objeto.")

    with tab_proc:
        c1, c2 = st.columns(2)
        outorgante = c1.text_input("Outorgante (Cliente)", key="proc_cli")
        nac_estado_civil = c2.text_input("Nacionalidade e Estado Civil", placeholder="Brasileiro, casado...")
        profissao = c1.text_input("Profissão")
        rg_cpf = c2.text_input("RG e CPF")
        endereco = st.text_input("Endereço Completo")
        
        poderes = st.radio("Poderes", ["Gerais para o Foro (Padrão)", "Especiais (Confessar, transigir, receber valores)"], index=1)
        
        if st.button("GERAR PROCURAÇÃO"):
            prompt_proc = f"""
            Redija uma PROCURAÇÃO AD JUDICIA ET EXTRA.
            Outorgante: {outorgante}, {nac_estado_civil}, {profissao}, portador do RG/CPF {rg_cpf}, residente em {endereco}.
            Outorgado: {st.session_state.escritorio_atual}.
            Poderes: {poderes}. Incluir poderes específicos para atuar no PJe, e-SAJ e demais sistemas eletrônicos.
            Data: {date.today().strftime('%d/%m/%Y')}.
            Local: {foro.split('/')[0] if 'foro' in locals() else 'Local'}.
            """
            
            api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
            res_proc = tentar_gerar_conteudo(prompt_proc, api_key_to_use)
            
            if "❌" not in res_proc:
                st.markdown(res_proc)
                st.download_button("Baixar Procuração", gerar_word(res_proc), f"Procuracao_{outorgante}.docx")
            else: st.error(res_proc)

elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO</h2>", unsafe_allow_html=True)
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    
    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = %s", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if df_clientes is not None and not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    with col_config:
        with st.container(border=True):
            st.markdown("##### ⚙️ ESTRUTURA")
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
            if not permissao_area: st.caption(f"🔒 Necessário Plano {area.upper()} ou FULL para busca oficial.")
            
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
                ctx_pdf = f"[DOC]: {extrair_texto_pdf(upload_peticao)}" if upload_peticao else ""
                jur = buscar_jurisprudencia_oficial(f"{tipo} {fatos}", area) if web else "Busca desativada."
                prompt = f"Advogado {area}. Redigir {tipo}. Cliente: {cli_final}. Fatos: {fatos}. Lei: {legislacao_extra}. {ctx_pdf}. Jurisprudencia: {jur}. Formato: {formato}."
                
                api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                res = tentar_gerar_conteudo(prompt, api_key_to_use)
                
                if "❌" not in res:
                    q = "UPDATE usuarios SET creditos = creditos - 1 WHERE username = %s" if not USAR_SQLITE_BACKUP else "UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?"
                    run_query(q, (st.session_state.usuario_atual,))
                    
                    q2 = "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)" if not USAR_SQLITE_BACKUP else "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)"
                    run_query(q2, (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    st.markdown("### 📄 MINUTA GERADA:")
                    if web: st.success("Jurisprudência incluída.")
                    with st.container(border=True): st.markdown(res)
                    st.download_button("📥 BAIXAR DOCX", gerar_word(res), f"{tipo}.docx")
                else: st.error(res)
        else: st.error("Créditos insuficientes ou dados incompletos.")

# --- NOVA ABA SUBSTITUÍDA: CÁLCULADORA ROBUSTA ---
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.header("🧮 Central de Cálculos & Perícia")
    
    # Seletor de Tipo de Calculadora
    tipo_calc = st.selectbox("Selecione a Calculadora:", ["Trabalhista (Rescisão CLT)", "Cível (Atualização)", "Família (Pensão)"])
    st.markdown("---")

    # === CALCULADORA TRABALHISTA ROBUSTA ===
    if tipo_calc == "Trabalhista (Rescisão CLT)":
        st.info("Cálculo completo de Verbas Rescisórias (Lei 12.506/2011).")
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            dt_adm = c1.date_input("Data de Admissão", date(2022, 1, 1))
            dt_dem = c2.date_input("Data de Demissão", date.today())
            motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo (Comum)"])
            
            c4, c5, c6 = st.columns(3)
            salario = c4.number_input("Salário Base (R$)", min_value=0.0, value=2500.0)
            saldo_fgts = c5.number_input("Saldo FGTS (p/ Multa)", min_value=0.0)
            aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado", "Não Trabalhado"])
            
            ferias_venc = st.checkbox("Possui Férias Vencidas (1 ano completo sem tirar)?")
            
            if st.button("CALCULAR RESCISÃO", use_container_width=True):
                if dt_dem > dt_adm:
                    # Chama a função que criamos no Passo 1
                    verbas = calcular_rescisao_completa(dt_adm, dt_dem, salario, motivo, saldo_fgts, ferias_venc, aviso)
                    
                    # Exibe Resultado
                    total = sum(verbas.values())
                    st.subheader(f"💰 Total Estimado: R$ {total:,.2f}")
                    
                    df_res = pd.DataFrame(list(verbas.items()), columns=["Verba", "Valor (R$)"])
                    st.dataframe(df_res, use_container_width=True)
                    
                    # Gera Parecer com IA
                    with st.spinner("Gerando Laudo Técnico..."):
                        prompt_laudo = f"""
                        Atue como Contador Perito Trabalhista.
                        Gere um PARECER TÉCNICO formal explicando este cálculo de rescisão.
                        Dados: Admissão {dt_adm}, Demissão {dt_dem}, Motivo: {motivo}.
                        Verbas: {verbas}. Total: {total}.
                        Explique o aviso prévio proporcional e a multa do FGTS se houver.
                        """
                        # Tenta pegar a chave API (seja do secrets ou input manual)
                        api_key_to_use = api_key if api_key else st.session_state.get('sidebar_api_key')
                        if not api_key_to_use and 'API_KEY_FIXA' in globals(): api_key_to_use = API_KEY_FIXA
                        
                        parecer = tentar_gerar_conteudo(prompt_laudo, api_key_to_use)
                        
                        with st.expander("📄 Ver Parecer Técnico", expanded=True):
                            st.markdown(parecer)
                            st.download_button("Baixar Laudo (.docx)", gerar_word(parecer), "Laudo_Rescisao.docx")
                else:
                    st.error("A Data de Demissão deve ser posterior à Admissão.")

    # === CALCULADORA CÍVEL ===
    elif tipo_calc == "Cível (Atualização)":
        valor = st.number_input("Valor da Causa")
        if st.button("Atualizar"):
            st.success(f"Valor com Juros (1% a.m) e Correção: R$ {valor * 1.05:.2f} (Estimativa)")

    # === CALCULADORA FAMÍLIA ===
    elif tipo_calc == "Família (Pensão)":
        renda = st.number_input("Renda Líquida do Alimentante")
        filhos = st.slider("Número de Filhos", 1, 5, 1)
        if st.button("Calcular"):
            perc = 0.3 if filhos == 1 else 0.3 + (filhos * 0.05) # Lógica simples
            st.info(f"Pensão Sugerida ({int(perc*100)}%): R$ {renda * perc:.2f}")

elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL</h2>", unsafe_allow_html=True)
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = %s ORDER BY id DESC", (st.session_state.escritorio_atual,), return_data=True) if not USAR_SQLITE_BACKUP else run_query("SELECT * FROM documentos WHERE escritorio = ? ORDER BY id DESC", (st.session_state.escritorio_atual,), return_data=True)
    
    if df_docs is not None and not df_docs.empty:
        for i, row in df_docs.iterrows():
            with st.expander(f"{row['tipo']} - {row['cliente']} ({row['data_criacao']})"):
                st.write(row['conteudo'][:500] + "...")
                c1, c2 = st.columns([1, 5])
                with c1: st.download_button("📥 Baixar", gerar_word(row['conteudo']), "Doc.docx", key=f"d{i}")
                with c2: 
                    if st.button("🗑️ Apagar", key=f"del_{row['id']}"):
                        q = "DELETE FROM documentos WHERE id = %s" if not USAR_SQLITE_BACKUP else "DELETE FROM documentos WHERE id = ?"
                        run_query(q, (row['id'],))
                        st.rerun()
    else: st.info("Nenhum documento encontrado.")

# Other menus (Monitor, Plans) kept simple
elif menu_opcao == "🚦 Monitor de Prazos":
    if st.session_state.plano_atual != 'starter':
        st.markdown("## 🚦 RADAR")
        st.info("Monitor ativo.")
    else: tela_bloqueio("PAGO", "149")

elif menu_opcao == "💎 Planos & Upgrade":
    st.markdown("## PLANOS")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.info("Criminal")
    with c2: st.info("Trabalhista")
    with c3: st.info("Cível")
    with c4: st.warning("Full Service")

st.markdown("---")

st.markdown("<center>🔒 LEGALHUB ELITE v7.0 | POSTGRESQL SECURE</center>", unsafe_allow_html=True)
