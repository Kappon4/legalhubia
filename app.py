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
    page_title="LegalHub Elite v7.6", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# 🛑 DATABASE CONFIGURATION (SUPABASE/POSTGRES)
# ==========================================================
try:
    # Tenta pegar dos secrets (Nuvem)
    DB_URI = st.secrets["DB_URI"]
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
    USAR_SQLITE_BACKUP = False
except:
    # Fallback local (Seu PC)
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

# --- CÁLCULO TRABALHISTA (ROBUSTO) ---
def calcular_rescisao_completa(admissao, demissao, salario_base, motivo, saldo_fgts, ferias_vencidas, aviso_tipo, grau_insalubridade, tem_periculosidade, sal_minimo=1412.00):
    formato_data = "%Y-%m-%d"
    d1 = datetime.strptime(str(admissao), formato_data)
    d2 = datetime.strptime(str(demissao), formato_data)
    
    verbas = {}
    
    val_insalubridade = 0.0
    if grau_insalubridade == "Mínimo (10%)": val_insalubridade = sal_minimo * 0.10
    elif grau_insalubridade == "Médio (20%)": val_insalubridade = sal_minimo * 0.20
    elif grau_insalubridade == "Máximo (40%)": val_insalubridade = sal_minimo * 0.40
    
    val_periculosidade = 0.0
    if tem_periculosidade:
        val_periculosidade = salario_base * 0.30
        val_insalubridade = 0 
    
    remuneracao = salario_base + val_insalubridade + val_periculosidade
    
    if val_insalubridade > 0: verbas[f"Adicional Insalubridade"] = val_insalubridade
    if val_periculosidade > 0: verbas[f"Adicional Periculosidade"] = val_periculosidade
    
    meses_trabalhados = (d2.year - d1.year) * 12 + d2.month - d1.month
    anos_completo = meses_trabalhados // 12
    dias_no_mes = d2.day
    
    saldo_salario = (remuneracao / 30) * dias_no_mes
    verbas["Saldo de Salário"] = saldo_salario
    
    dias_aviso = 30 + (3 * anos_completo)
    if dias_aviso > 90: dias_aviso = 90
    
    if motivo == "Demissão sem Justa Causa":
        if aviso_tipo == "Indenizado":
            valor_aviso = (remuneracao / 30) * dias_aviso
            verbas[f"Aviso Prévio Indenizado ({dias_aviso} dias)"] = valor_aviso
            d2 = d2 + timedelta(days=dias_aviso)
    elif motivo == "Pedido de Demissão" and aviso_tipo == "Não Trabalhado":
        verbas["Desconto Aviso Prévio"] = -remuneracao
        
    meses_ano_atual = d2.month
    if d2.day < 15: meses_ano_atual -= 1 
    if meses_ano_atual == 0: meses_ano_atual = 12 
    
    if motivo != "Justa Causa":
        decimo = (remuneracao / 12) * meses_ano_atual
        verbas[f"13º Salário Proporcional ({meses_ano_atual}/12)"] = decimo
        
    if motivo != "Justa Causa":
        if ferias_vencidas:
            verbas["Férias Vencidas + 1/3"] = remuneracao + (remuneracao/3)
        val_ferias_prop = (remuneracao / 12) * meses_ano_atual
        verbas[f"Férias Proporcionais ({meses_ano_atual}/12) + 1/3"] = val_ferias_prop + (val_ferias_prop/3)

    if motivo == "Demissão sem Justa Causa" or motivo == "Rescisão Indireta":
        verbas["Multa 40% FGTS"] = saldo_fgts * 0.4
    elif motivo == "Acordo (Comum)":
        verbas["Multa 20% FGTS"] = saldo_fgts * 0.2

    return verbas

# --- ROBUST AI FUNCTION ---
def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ Error: API Key not configured."
    genai.configure(api_key=chave)
    modelos = ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    erro_final = ""
    for modelo in modelos:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            erro_final = str(e)
            continue 
    return f"❌ Falha na IA: {erro_final}"

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
        return "Nenhuma jurisprudência encontrada."
    except: return "Erro de conexão."

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
# 4. LOGIN & SETUP (CORRIGIDO PARA POSTGRESQL)
# ==========================================================
try:
    if USAR_SQLITE_BACKUP:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    else:
        # Postgres Nuvem
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    
    # SETUP DO ADMIN COM ON CONFLICT CORRETO
    q_admin = "INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING"
    run_query(q_admin, ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full'))

except Exception as e:
    print(f"Setup Error: {e}")

if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        img_base64 = get_base64_of_bin_file("diagrama-ia.png")
        if img_base64: st.markdown(f"""<div style="text-align: center;"><img src="data:image/png;base64,{img_base64}" class="floating-logo" style="width: 250px;"></div>""", unsafe_allow_html=True)
        else: st.markdown("<h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)
        
        st.markdown("""<div style='text-align: center;'><h1 class='tech-header' style='font-size: 2.5rem; letter-spacing: 3px;'>LEGALHUB <span style='font-weight: 300; color: #fff;'>ELITE</span></h1><p style='color: #00F3FF; font-size: 0.8rem; letter-spacing: 2px;'>Artificial Intelligence System</p></div>""", unsafe_allow_html=True)

        if USAR_SQLITE_BACKUP:
            st.warning("⚠️ MODO OFFLINE (SQLITE). Configure a senha no DB_URI para salvar na nuvem.")
        else:
            st.success("☁️ BANCO DE DADOS NUVEM CONECTADO (SEGURO)")
            
        with st.container(border=True):
            user_input = st.text_input("Usuário")
            pwd_input = st.text_input("Senha", type="password")
            
            c_entrar, c_reset = st.columns(2)
            
            if c_entrar.button("🔓 INICIAR SESSÃO", use_container_width=True):
                res = run_query("SELECT * FROM usuarios WHERE username = %s AND senha = %s", (user_input, pwd_input), return_data=True)
                if res is not None and not res.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = user_input
                    st.session_state.escritorio_atual = res.iloc[0]['escritorio']
                    st.session_state.plano_atual = res.iloc[0]['plano']
                    st.rerun()
                else:
                    st.error("Acesso Negado. Usuário não encontrado.")
            
            # Botão de Emergência para recriar o Admin se ele sumiu
            if c_reset.button("🆘 Resetar Admin", use_container_width=True):
                try:
                    # Força a atualização da senha do admin
                    run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO UPDATE SET senha = 'admin'", ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full'))
                    st.success("Admin restaurado! Use: admin / admin")
                except Exception as e:
                    st.error(f"Erro ao restaurar: {e}")

            st.markdown("<div style='text-align:center; margin-top:10px; color: #475569; font-size: 0.7rem; font-family: Rajdhani;'>SYSTEM V7.6 // SECURE</div>", unsafe_allow_html=True)
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
else: creditos_atuais = 0

col_logo, col_menu = st.columns([1, 4])
with col_logo: st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)
with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Contratos": "📜 Contratos", "Calculos": "🧮 Cálculos Jurídicos", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Planos & Upgrade"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.get("navegacao_override"):
        try: idx_radio = opcoes_menu.index([k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0])
        except: pass
        st.session_state.navegacao_override = None
    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")
with st.sidebar:
    st.markdown(f"<div style='font-size:0.8rem;'>User: {st.session_state.usuario_atual}<br>Banca: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/100, 1.0))
    if st.button("LOGOUT"): st.session_state.logado = False; st.rerun()

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    docs = run_query("SELECT count(*) FROM documentos WHERE escritorio = %s", (st.session_state.escritorio_atual,), return_data=True)
    qtd_docs = docs.iloc[0][0] if docs is not None else 0
    c1.metric("DOCS GERADOS", qtd_docs)
    c2.metric("SALDO CRÉDITOS", creditos_atuais)
    c3.metric("STATUS DB", "Online" if not USAR_SQLITE_BACKUP else "Local")

    st.subheader("🛠️ CENTRAL DE COMANDO")
    r1, r2, r3 = st.columns(3)
    with r1:
        if st.button("✍️ REDATOR IA", use_container_width=True): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r2:
        if st.button("🧮 CÁLCULOS", use_container_width=True): st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"; st.rerun()
    with r3:
        if st.button("🏛️ AUDIÊNCIA", use_container_width=True): st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"; st.rerun()

elif menu_opcao == "📜 Contratos":
    st.header("📜 Gerador de Contratos & Procurações")
    tab_cont, tab_proc = st.tabs(["📝 Contrato de Honorários", "⚖️ Procuração Ad Judicia"])
    
    with tab_cont:
        c1, c2 = st.columns(2)
        contratante = c1.text_input("Nome do Cliente (Contratante)")
        cpf_cnpj = c2.text_input("CPF/CNPJ")
        objeto = st.text_area("Objeto do Contrato")
        cc1, cc2, cc3 = st.columns(3)
        valor = cc1.number_input("Valor (R$)", step=100.0)
        exito = cc2.number_input("Taxa Êxito (%)", 30)
        forma = cc3.selectbox("Pagamento", ["À Vista", "Parcelado", "Ao final"])
        
        if st.button("GERAR CONTRATO"):
            with st.spinner("Redigindo..."):
                prompt = f"Contrato honorários. Cliente: {contratante}, CPF {cpf_cnpj}. Valor R$ {valor}. Exito {exito}%. Objeto: {objeto}. Contratado: {st.session_state.escritorio_atual}."
                res = tentar_gerar_conteudo(prompt, api_key)
                if "❌" not in res:
                    st.download_button("Baixar Contrato", gerar_word(res), f"Contrato_{contratante}.docx")
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)", (st.session_state.escritorio_atual, str(date.today()), contratante, "Contratos", "Contrato Honorários", res))
                else: st.error(res)

    with tab_proc:
        outorgante = st.text_input("Outorgante")
        dados = st.text_input("Dados Completos")
        if st.button("GERAR PROCURAÇÃO"):
            res = tentar_gerar_conteudo(f"Procuração Ad Judicia. Outorgante: {outorgante}, {dados}. Outorgado: {st.session_state.escritorio_atual}", api_key)
            st.download_button("Baixar Procuração", gerar_word(res), "Procuracao.docx")

elif menu_opcao == "✍️ Redator Jurídico":
    st.header("✍️ Redator Jurídico")
    c1, c2 = st.columns([1, 2])
    with c1:
        tipo = st.selectbox("Peça", ["Petição Inicial", "Contestação", "Recurso", "Habeas Corpus"])
        cli = st.text_input("Cliente")
    with c2: fatos = st.text_area("Fatos", height=150)
    
    if st.button("GERAR MINUTA"):
        if fatos and cli:
            with st.spinner("Escrevendo..."):
                prompt = f"Advogado. Redija {tipo}. Cliente: {cli}. Fatos: {fatos}."
                res = tentar_gerar_conteudo(prompt, api_key)
                st.markdown(res)
                if "❌" not in res:
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)", (st.session_state.escritorio_atual, str(date.today()), cli, "Geral", tipo, res))

# =========================================================
# 🧮 CÁLCULOS JURÍDICOS (CENTRALIZADO & ATUALIZADO)
# =========================================================
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Central Unificada de Cálculos")
    
    # SELETOR DE ÁREA PRINCIPAL
    area_calc = st.selectbox("Selecione a Área do Direito:", 
                             ["Trabalhista (CLT)", "Cível & Processual", "Família & Sucessões", "Tributária", "Previdenciária", "Criminal"])
    st.divider()

    # --- 1. TRABALHISTA ---
    if area_calc == "Trabalhista (CLT)":
        st.subheader("🛠️ Rescisão Trabalhista Completa")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            dt_adm = c1.date_input("Admissão", date(2022, 1, 1))
            dt_dem = c2.date_input("Demissão", date.today())
            motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo"])
            
            c4, c5, c6 = st.columns(3)
            salario = c4.number_input("Salário Base", value=2500.0)
            fgts = c5.number_input("Saldo FGTS", value=0.0)
            aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado", "Não Trabalhado"])
            
            c7, c8, c9 = st.columns(3)
            insal = c7.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
            peric = c8.checkbox("Periculosidade (30%)")
            ferias = c9.checkbox("Férias Vencidas?")
            
            if st.button("CALCULAR RESCISÃO"):
                if dt_dem > dt_adm:
                    verbas = calcular_rescisao_completa(dt_adm, dt_dem, salario, motivo, fgts, ferias, aviso, insal, peric)
                    total = sum(verbas.values())
                    st.markdown(f"### Total Estimado: R$ {total:,.2f}")
                    st.dataframe(pd.DataFrame(list(verbas.items()), columns=["Verba", "Valor"]), use_container_width=True)
                    
                    # Parecer IA
                    with st.spinner("Gerando Parecer..."):
                        p_laudo = f"Parecer contábil trabalhista rescisão. Admissão {dt_adm}, Demissão {dt_dem}. Verbas: {verbas}. Explique resumidamente."
                        laudo = tentar_gerar_conteudo(p_laudo, api_key)
                        with st.expander("📄 Ver Parecer Técnico"):
                            st.markdown(laudo)
                            st.download_button("Baixar Laudo", gerar_word(laudo), "Parecer_Trabalhista.docx")

    # --- 2. CÍVEL & PROCESSUAL (ATUALIZADO) ---
    elif area_calc == "Cível & Processual":
        tab_liq, tab_causa, tab_rev = st.tabs(["Liquidação de Sentença", "Valor da Causa (Art 292 CPC)", "Revisão Bancária"])
        
        # 1. Liquidação Detalhada
        with tab_liq:
            st.markdown("#### 💸 Liquidação de Sentença Completa")
            st.info("Atualização Monetária, Juros, Multa (Art. 523) e Honorários.")
            
            with st.container(border=True):
                cl1, cl2 = st.columns(2)
                valor_cond = cl1.number_input("Valor da Condenação", 0.0, step=100.0)
                data_inicio = cl2.date_input("Data Inicial (Citação/Vencimento)", value=date(2022,1,1))
                
                cl3, cl4 = st.columns(2)
                indice = cl3.number_input("Índice Acumulado (Tabela TJ)", value=1.050, format="%.4f")
                juros_tipo = cl4.selectbox("Juros de Mora", ["1% ao Mês (Simples)", "Selic (Composta)", "Sem Juros"])
                
                cl5, cl6 = st.columns(2)
                multa_art523 = cl5.checkbox("Multa 10% (Art. 523 CPC - Não pagou em 15 dias)")
                hon_exec = cl6.checkbox("Honorários Execução (10%)")
                
                if st.button("CALCULAR LIQUIDAÇÃO"):
                    hj = date.today()
                    meses = (hj.year - data_inicio.year) * 12 + hj.month - data_inicio.month
                    if meses < 0: meses = 0
                    
                    val_atualizado = valor_cond * indice
                    
                    val_juros = 0.0
                    if juros_tipo == "1% ao Mês (Simples)":
                        val_juros = val_atualizado * (0.01 * meses)
                    elif juros_tipo == "Selic (Composta)":
                        val_juros = val_atualizado * 0.40 # Estimativa
                    
                    subtotal = val_atualizado + val_juros
                    
                    # Multas incidem sobre o subtotal
                    v_multa = subtotal * 0.10 if multa_art523 else 0.0
                    v_hon = subtotal * 0.10 if hon_exec else 0.0
                    
                    final = subtotal + v_multa + v_hon
                    
                    st.success(f"💰 Total da Execução: R$ {final:,.2f}")
                    st.table(pd.DataFrame({
                        "Descrição": ["Principal Corrigido", f"Juros ({meses} meses)", "Multa Art. 523", "Honorários Exec."],
                        "Valor": [val_atualizado, val_juros, v_multa, v_hon]
                    }))

        # 2. Valor da Causa (Art 292 CPC)
        with tab_causa:
            st.markdown("#### ⚖️ Cálculo do Valor da Causa (CPC/2015)")
            tipo_acao = st.radio("Tipo de Ação", ["Alimentos (Art. 292, III)", "Cobrança (Art. 292, I)", "Indenização (Art. 292, V)"], horizontal=True)
            
            valor_final = 0.0
            if tipo_acao == "Alimentos (Art. 292, III)":
                mensal = st.number_input("Valor da Prestação Mensal")
                valor_final = mensal * 12
                st.info("Regra: Soma de 12 prestações mensais.")
            
            elif tipo_acao == "Cobrança (Art. 292, I)":
                princ = st.number_input("Dívida Principal")
                jur = st.number_input("Juros Vencidos")
                mul = st.number_input("Multas Contratuais")
                valor_final = princ + jur + mul
                st.info("Regra: Principal + Juros + Multas vencidas até a propositura.")
                
            elif tipo_acao == "Indenização (Art. 292, V)":
                moral = st.number_input("Danos Morais Pretendidos")
                material = st.number_input("Danos Materiais Estimados")
                valor_final = moral + material
                st.info("Regra: Soma de todos os pedidos indenizatórios.")
            
            if st.button("DEFINIR VALOR DA CAUSA"):
                st.success(f"Valor da Causa: R$ {valor_final:,.2f}")

        # 3. Revisão Bancária
        with tab_rev:
            st.markdown("#### 🏦 Revisão de Contratos (Juros Abusivos)")
            emp = st.number_input("Valor Financiado (R$)")
            taxa = st.number_input("Taxa de Juros Mensal (%)", value=2.0)
            meses = st.number_input("Prazo (Meses)", value=48)
            
            if st.button("SIMULAR ABUSIVIDADE"):
                i = taxa / 100
                # Price (Composto)
                parc_price = emp * (i * (1+i)**meses) / ((1+i)**meses - 1)
                total_price = parc_price * meses
                
                # Gauss (Simples - Tese)
                juros_tot_gauss = emp * i * meses
                total_gauss = emp + juros_tot_gauss
                parc_gauss = total_gauss / meses
                
                diff = total_price - total_gauss
                
                c_res1, c_res2 = st.columns(2)
                c_res1.metric("Parcela Banco (Price)", f"R$ {parc_price:,.2f}")
                c_res2.metric("Parcela Justa (Gauss)", f"R$ {parc_gauss:,.2f}")
                st.warning(f"📉 Diferença Total (Juros Abusivos): R$ {diff:,.2f}")

    # --- 3. FAMÍLIA & SUCESSÕES ---
    elif area_calc == "Família & Sucessões":
        st.subheader("👨‍👩‍👧‍👦 Família & Sucessões")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.markdown("**Divórcio & Inventário (Partilha)**")
            pat = st.number_input("Patrimônio Total")
            meeeiro = st.checkbox("Existe Meeiro (Cônjuge)?", value=True)
            herd = st.number_input("Número de Herdeiros", 1, 10, 2)
            
            if st.button("SIMULAR PARTILHA"):
                parte_meeiro = pat * 0.5 if meeeiro else 0.0
                saldo = pat - parte_meeiro
                quinhao = saldo / herd
                st.success(f"Quinhão por Herdeiro: R$ {quinhao:,.2f}")
                if meeeiro: st.info(f"Parte do Meeiro: R$ {parte_meeiro:,.2f}")

        with col_f2:
            st.markdown("**Pensão Alimentícia**")
            renda = st.number_input("Renda Líquida Alimentante")
            f = st.slider("Filhos", 1, 5, 1)
            if st.button("CALCULAR PENSÃO"):
                perc = 0.30 if f == 1 else 0.30 + (f-1)*0.05
                st.info(f"Sugerido ({int(perc*100)}%): R$ {renda * perc:.2f}")

    # --- 4. TRIBUTÁRIA (NOVO) ---
    elif area_calc == "Tributária":
        st.subheader("🏛️ Cálculos Tributários")
        st.info("Atualização de Débitos Fiscais (Selic/Multa)")
        
        with st.container(border=True):
            principal = st.number_input("Valor do Tributo Original (R$)", 0.0)
            multa_pct = st.number_input("Multa de Mora (%)", value=20.0)
            selic_acum = st.number_input("Selic Acumulada (%)", value=15.0)
            
            if st.button("ATUALIZAR DÉBITO FISCAL"):
                val_multa = principal * (multa_pct/100)
                val_juros = principal * (selic_acum/100)
                total_trib = principal + val_multa + val_juros
                
                st.metric("Total a Pagar", f"R$ {total_trib:,.2f}")
                st.write(f"Principal: R$ {principal:.2f} | Multa: R$ {val_multa:.2f} | Juros: R$ {val_juros:.2f}")

    # --- 5. PREVIDENCIÁRIA (NOVO) ---
    elif area_calc == "Previdenciária":
        st.subheader("👴 Previdenciário")
        st.info("Calculadora Simples de Tempo de Contribuição")
        
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Início Contribuição", date(2000, 1, 1))
        fim = c2.date_input("Fim Contribuição", date.today())
        
        if st.button("CALCULAR TEMPO"):
            dias = (fim - inicio).days
            anos = dias // 365
            meses = (dias % 365) // 30
            st.success(f"Tempo Estimado: {anos} anos e {meses} meses.")

    # --- 6. CRIMINAL (NOVO) ---
    elif area_calc == "Criminal":
        st.subheader("⚖️ Dosimetria da Pena (Estimativa)")
        pena_min = st.number_input("Pena Mínima (Anos)", value=5)
        pena_max = st.number_input("Pena Máxima (Anos)", value=15)
        circunstancias = st.slider("Circunstâncias Judiciais Desfavoráveis (0 a 8)", 0, 8, 0)
        
        if st.button("CALCULAR PENA BASE"):
            intervalo = pena_max - pena_min
            aumento = (intervalo / 8) * circunstancias
            pena_base = pena_min + aumento
            st.error(f"Pena Base Sugerida: {pena_base:.1f} anos")

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
                        run_query("DELETE FROM documentos WHERE id = %s" if not USAR_SQLITE_BACKUP else "DELETE FROM documentos WHERE id = ?", (row['id'],))
                        st.rerun()
    else: st.info("Nenhum documento encontrado.")

# --- MENUS SIMPLES (MANTIDOS) ---
elif menu_opcao == "🚦 Monitor de Prazos":
    st.markdown("## 🚦 RADAR")
    st.info("Monitor ativo.")

elif menu_opcao == "💎 Planos & Upgrade":
    st.markdown("## PLANOS")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.info("Criminal")
    with c2: st.info("Trabalhista")
    with c3: st.info("Cível")
    with c4: st.warning("Full Service")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v7.6 | POSTGRESQL SECURE</center>", unsafe_allow_html=True)
