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
# 1. CONFIGURAÇÃO VISUAL - TEMA CYBER SECURITY
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite | AI System", 
    page_icon="🛡️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PROFISSIONAL (TECH & SECURE) ---
def local_css():
    st.markdown("""
    <style>
        /* IMPORTANDO FONTE TECH */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');

        /* --- VARIÁVEIS DE COR (PALETA CYBER) --- */
        :root {
            --bg-dark: #0F172A;        /* Fundo Principal (Deep Navy) */
            --bg-card: rgba(30, 41, 59, 0.7); /* Fundo Vidro (Slate 800) */
            --text-main: #E2E8F0;      /* Texto Claro (Slate 200) */
            --accent-primary: #38BDF8; /* Azul Neon (Sky 400) */
            --accent-glow: rgba(56, 189, 248, 0.4);
            --gradient-btn: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
            --border-glass: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* --- GERAL --- */
        .stApp {
            background-color: var(--bg-dark);
            background-image: radial-gradient(circle at 10% 20%, rgba(56, 189, 248, 0.05) 0%, transparent 20%),
                              radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 20%);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
        }

        h1, h2, h3, h4, h5 {
            color: #FFFFFF !important;
            font-family: 'Inter', sans-serif;
            letter-spacing: -0.5px;
        }

        /* TÍTULOS COM GRADIENTE (EFEITO TECH) */
        .tech-header {
            background: linear-gradient(90deg, #FFFFFF 0%, #38BDF8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background-color: #020617; /* Quase preto */
            border-right: 1px solid #1E293B;
            box-shadow: 5px 0 15px rgba(0,0,0,0.3);
        }

        /* --- BOTÕES MODERNOS --- */
        .stButton>button {
            background: var(--gradient-btn);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            width: 100%;
            text-transform: uppercase;
            font-size: 0.85rem;
        }
        
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 15px var(--accent-glow);
            border: 1px solid #7DD3FC;
        }

        /* --- INPUTS & CAMPOS --- */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
            background-color: #1E293B !important;
            color: #F8FAFC !important;
            border: 1px solid #334155 !important;
            border-radius: 6px;
            transition: border-color 0.3s;
        }
        
        .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
            border-color: var(--accent-primary) !important;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
        }

        /* --- CARDS & CONTAINERS (GLASSMORPHISM) --- */
        div[data-testid="metric-container"] {
            background: var(--bg-card);
            backdrop-filter: blur(10px);
            border: var(--border-glass);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        div[data-testid="metric-container"]:hover {
             border-color: var(--accent-primary);
        }

        /* Estiliza os Expanders e Containers Gerais */
        div[data-testid="stExpander"], div[data-testid="stContainer"] {
            border: var(--border-glass);
            border-radius: 10px;
            background-color: rgba(30, 41, 59, 0.3);
        }

        /* --- SCROLLBAR --- */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0F172A; 
        }
        ::-webkit-scrollbar-thumb {
            background: #334155; 
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #475569; 
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
                <h1 style='font-size: 3rem; margin-bottom: 0;'>🛡️</h1>
                <h1 class='tech-header' style='font-size: 2.5rem;'>LEGALHUB <span style='font-weight: 300; color: #94a3b8;'>ELITE</span></h1>
                <p style='color: #64748b; font-size: 0.9rem; letter-spacing: 1px;'>SECURE LEGAL INTELLIGENCE SYSTEM</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.write("")
        
        with st.container(border=True):
            st.markdown("#### Identificação")
            username = st.text_input("ID Usuário")
            password = st.text_input("Chave de Acesso", type="password")
            
            st.write("")
            if st.button("🔓 INICIAR SESSÃO SEGURA", use_container_width=True):
                users = run_query("SELECT * FROM usuarios WHERE username = ? AND senha = ?", (username, password), return_data=True)
                if not users.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = username
                    st.session_state.escritorio_atual = users.iloc[0]['escritorio']
                    st.rerun()
                else: st.error("Acesso Negado. Credenciais Inválidas.")
            
            st.markdown("<div style='text-align:center; margin-top:10px; color: #475569; font-size: 0.8rem;'>v5.5 Secure Build</div>", unsafe_allow_html=True)

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
    api_key = st.sidebar.text_input("🔑 API Key:", type="password")

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

with st.sidebar:
    st.markdown("<h2 class='tech-header'>🛡️ LEGALHUB</h2>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.8rem; color:#94a3b8; margin-bottom: 20px;'>{st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    
    # Lista de Opções
    opcoes_menu = ["📊 Dashboard", "✍️ Redator Jurídico", "🧮 Calculadoras & Perícia", "🏛️ Estratégia de Audiência", "📂 Gestão de Casos", "🚦 Monitor de Prazos", "🔧 Ferramentas Extras"]
    
    idx_menu = 0
    if st.session_state.navegacao_override:
        try: idx_menu = opcoes_menu.index(st.session_state.navegacao_override)
        except: idx_menu = 0
        st.session_state.navegacao_override = None
    
    menu_opcao = st.radio("SISTEMA:", opcoes_menu, index=idx_menu)
    
    st.markdown("---")
    
    # Display de Créditos Moderno
    st.markdown("#### SALDO DE CRÉDITOS")
    col_cred1, col_cred2 = st.columns([1, 3])
    with col_cred1: st.markdown("<h3 style='color:#38BDF8;'>💎</h3>", unsafe_allow_html=True)
    with col_cred2: 
        st.markdown(f"<h3 style='margin:0; color:#38BDF8;'>{creditos_atuais}</h3>", unsafe_allow_html=True)
        st.progress(min(creditos_atuais/50, 1.0))
    
    st.write("")
    if st.button("🔒 LOGOUT"):
        st.session_state.logado = False
        st.rerun()

    # --- ÁREA DE ADMINISTRAÇÃO ---
    if st.session_state.usuario_atual == 'admin':
        st.markdown("---")
        with st.expander("🛠️ PAINEL ADMIN"):
            st.markdown("##### ➕ Novo Usuário")
            novo_user = st.text_input("Login")
            novo_pass = st.text_input("Senha", type="password")
            novo_banca = st.text_input("Escritório")
            if st.button("Criar Acesso"):
                run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50))
                st.success("Usuário criado!")
            
            st.divider()
            st.markdown("##### 💰 Recarga")
            df_users = run_query("SELECT username FROM usuarios", return_data=True)
            if not df_users.empty:
                user_recarga = st.selectbox("Usuário:", df_users['username'])
                qtd_recarga = st.number_input("Qtd:", min_value=1, value=50, step=10)
                if st.button("Confirmar Recarga"):
                    run_query("UPDATE usuarios SET creditos = creditos + ? WHERE username = ?", (qtd_recarga, user_recarga))
                    st.toast(f"✅ Recarga efetuada para {user_recarga}!")
                    time.sleep(1)
                    st.rerun()

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>Painel de Controle <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| {st.session_state.usuario_atual}</span></h2>", unsafe_allow_html=True)
    
    # Métricas Superiores
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    
    c1.metric("📄 Documentos Gerados", docs_feitos, delta="+2 esse mês")
    c2.metric("💎 Créditos Disponíveis", creditos_atuais)
    c3.metric("📅 Prazos Ativos", "0", delta="Regular", delta_color="off")
    
    st.write("")
    
    # Gráfico e Dicas
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.markdown("##### 📈 Análise de Produtividade")
        with st.container(border=True):
            df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
            if not df_areas.empty:
                # Cores Tech para o gráfico
                colors_tech = ['#38BDF8', '#0EA5E9', '#0284C7', '#6366F1', '#8B5CF6']
                fig = px.pie(df_areas, values='qtd', names='area', hole=0.6, color_discrete_sequence=colors_tech)
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#cbd5e1", showlegend=True, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Sem dados para análise visual.")
    
    with col_info:
        st.markdown("##### 💡 Status do Sistema")
        with st.container(border=True):
            st.success("Servidor IA: Online")
            st.info("Banco de Dados: Seguro")
            st.warning("Atualização: v5.5 Estável")
            st.markdown("---")
            st.caption("Dica: Use a 'Jurisprudência Inteligente' para aumentar a precisão das peças.")

    # CARDS DE FUNCIONALIDADES
    st.write("")
    st.subheader("🛠️ Acesso Rápido")
    
    # CSS específico para botões invisíveis cobrindo cards (hack visual)
    
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        with st.container(border=True):
            st.markdown("#### ✍️ Redator IA")
            st.caption("Geração de peças processuais.")
            if st.button("Abrir Redator", key="btn_redator"):
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r1c2:
        with st.container(border=True):
            st.markdown("#### 🧮 Perícia")
            st.caption("Cálculos complexos automatizados.")
            if st.button("Abrir Perícia", key="btn_pericia"):
                st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"
                st.rerun()

    with r1c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ Audiência")
            st.caption("Simulação e estratégia de defesa.")
            if st.button("Abrir Audiência", key="btn_aud"):
                st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"
                st.rerun()

    st.write("")
    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        with st.container(border=True):
            st.markdown("#### ⚖️ Jurisprudência")
            st.caption("Busca em tribunais superiores.")
            if st.button("Pesquisar", key="btn_juris"):
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r2c2:
        with st.container(border=True):
            st.markdown("#### 📄 Chat PDF")
            st.caption("Interrogatório de documentos.")
            if st.button("Analisar PDF", key="btn_pdf"):
                st.session_state.navegacao_override = "🔧 Ferramentas Extras"
                st.rerun()

    with r2c3:
        with st.container(border=True):
            st.markdown("#### 📅 Prazos")
            st.caption("Monitoramento de intimações.")
            if st.button("Ver Monitor", key="btn_prazo"):
                st.session_state.navegacao_override = "🚦 Monitor de Prazos"
                st.rerun()

# 2. REDATOR
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ Redator Inteligente</h2>", unsafe_allow_html=True)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    col_config, col_input = st.columns([1, 2])
    
    with col_config:
        with st.container(border=True):
            st.markdown("##### ⚙️ Parâmetros")
            tipo = st.selectbox("Tipo de Peça", ["Inicial", "Contestação", "Recurso Inominado", "Apelação", "Contrato", "Parecer"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
            web = st.checkbox("Incluir Jurisprudência Web", value=True)
            
            st.markdown("##### 👤 Cliente")
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
        st.markdown("##### 📝 Fatos e Dados do Caso")
        fatos = st.text_area("Descreva os detalhes aqui...", height=350, value=st.session_state.fatos_recuperados, placeholder="Cole os fatos, datas e valores relevantes...")
    
    st.write("")
    if st.button("✨ EXECUTAR GERAÇÃO (1 CRÉDITO)", use_container_width=True):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner("Processando dados com IA..."):
                jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisp: {jur}. Formal e Técnico."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    
                    st.markdown("### 📄 Resultado:")
                    with st.container(border=True):
                        st.markdown(res)
                    
                    st.download_button("📥 Baixar Documento (.docx)", gerar_word(res), "Minuta_LegalHub.docx", use_container_width=True)
                    st.success(f"Documento salvo em: {cli_final}")
                    time.sleep(2)
                    st.rerun()
                except Exception as e: st.error(f"Erro no processamento: {str(e)}")
        else: st.error("Verifique créditos e preenchimento dos campos.")

# 3. CALCULADORA
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='tech-header'>🧮 Laboratório de Perícia</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            tipo_calc = st.selectbox("Selecione o Cálculo:", ["Aluguel", "Divórcio", "FGTS", "INSS", "PASEP", "Pensão", "RMC/RCC", "Superendividamento", "Criminal (Dosimetria)", "Trabalhista"])
            dt_base = st.date_input("Data Base do Cálculo")
        with c2:
            upload = st.file_uploader("Anexar Documento Base (PDF)", type="pdf")
        
        dados = st.text_area("Insira os valores e parâmetros manuais:")
        
        if st.button("🧮 PROCESSAR CÁLCULO"):
            if dados or upload:
                with st.spinner("Realizando cálculos..."):
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
    st.markdown("<h2 class='tech-header'>🏛️ Simulador de Audiência</h2>", unsafe_allow_html=True)
    
    col_setup, col_doc = st.columns([1, 1])
    with col_setup:
        area = st.selectbox("Área do Direito", ["Trabalhista", "Cível", "Criminal"])
        papel = st.selectbox("Você representa:", ["Autor/Reclamante", "Réu/Reclamada"])
    with col_doc:
        upload = st.file_uploader("Processo/Inicial (PDF)", type="pdf")
    
    obs = st.text_area("Pontos sensíveis do caso:")
    
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
    st.markdown("<h2 class='tech-header'>📂 Cofre Digital de Processos</h2>", unsafe_allow_html=True)
    
    if "pasta_aberta" not in st.session_state: st.session_state.pasta_aberta = None
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)

    if not df_docs.empty:
        if st.session_state.pasta_aberta is None:
            st.info("Selecione o dossiê do cliente para acessar os arquivos.")
            clientes_unicos = df_docs['cliente'].unique()
            cols = st.columns(4) 
            for i, cliente in enumerate(clientes_unicos):
                with cols[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"#### 📁")
                        st.markdown(f"**{cliente}**")
                        qtd = len(df_docs[df_docs['cliente'] == cliente])
                        st.caption(f"{qtd} arquivos")
                        if st.button(f"Abrir Pasta", key=f"btn_{i}"):
                            st.session_state.pasta_aberta = cliente
                            st.rerun()

        else:
            col_back, col_title = st.columns([1, 10])
            with col_back:
                if st.button("⬅"):
                    st.session_state.pasta_aberta = None
                    st.rerun()
            with col_title:
                st.markdown(f"### 📂 Cliente: {st.session_state.pasta_aberta}")

            with st.expander("➕ Adicionar Novo Item ao Dossiê", expanded=False):
                c_add1, c_add2 = st.columns(2)
                novo_tipo = c_add1.text_input("Nome do Documento:")
                nova_area = c_add2.selectbox("Categoria:", ["Documentos Pessoais", "Provas", "Andamento", "Anotações", "Financeiro"])
                
                tab_up, tab_txt = st.tabs(["📤 Upload", "✍️ Nota Rápida"])
                conteudo_novo = ""
                with tab_up: arquivo_novo = st.file_uploader("Arquivo PDF", key="novo_up")
                with tab_txt: texto_novo = st.text_area("Texto:", key="nova_nota")

                if st.button("💾 Salvar"):
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
    st.markdown("<h2 class='tech-header'>🚦 Radar de Prazos</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("##### Configuração IMAP")
        c_email1, c_email2, c_email3 = st.columns(3)
        email_leitura = c_email1.text_input("Email", placeholder="adv@jus.com")
        senha_leitura = c_email2.text_input("Senha App", type="password")
        servidor_imap = c_email3.text_input("Host", value="imap.gmail.com")

        if st.button("🔄 ESCANEAR CAIXA DE ENTRADA"):
            if email_leitura and senha_leitura:
                with st.spinner("Varrendo metadados de e-mails..."):
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
    st.markdown("<h2 class='tech-header'>🔧 Toolkit Avançado</h2>", unsafe_allow_html=True)
    
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
st.markdown("<center style='color: #64748b; font-size: 0.8rem;'>🔒 LegalHub Enterprise v5.5 | Encrypted Session | 2025</center>", unsafe_allow_html=True)
