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
import plotly.express as px # --- NOVA IMPORTAÇÃO PARA O GRÁFICO ---

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - TEMA DARK & GOLD
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZADO (DARK MODE + ORO) ---
def local_css():
    st.markdown("""
    <style>
        /* --- FUNDO GERAL (DEGRADE PRETO) --- */
        .stApp {
            background: linear-gradient(135deg, #000000 0%, #1c1c1c 100%);
            color: #FFFFFF;
        }

        /* --- LOGO E TÍTULOS --- */
        h1, h2, h3 {
            color: #FFFFFF !important;
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 600;
        }
        
        /* Destaque em Amarelo para textos específicos */
        .highlight-gold {
            color: #FFD700 !important;
        }

        /* --- BOTÕES (AMARELO OURO COM TEXTO PRETO) --- */
        .stButton>button {
            background-color: #FFD700; /* Ouro */
            color: #000000; /* Texto Preto */
            border-radius: 8px;
            border: none;
            padding: 0.6rem 1.2rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(255, 215, 0, 0.2);
        }
        .stButton>button:hover {
            background-color: #E5C100;
            color: #000000;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.5); /* Brilho ao passar o mouse */
            transform: scale(1.02);
        }

        /* --- CAMPOS DE TEXTO (INPUTS) ESCUROS --- */
        .stTextInput>div>div>input, 
        .stTextArea>div>div>textarea, 
        .stSelectbox>div>div>div {
            background-color: #2d2d2d !important;
            color: #FFFFFF !important;
            border: 1px solid #444 !important;
            border-radius: 8px;
        }
        /* Cor do placeholder e label */
        .stTextInput label, .stTextArea label, .stSelectbox label {
            color: #FFD700 !important; /* Labels em Dourado */
        }

        /* --- BARRA LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: #0a0a0a; /* Preto quase absoluto */
            border-right: 1px solid #333;
        }
        
        /* --- CARDS E MÉTRICAS --- */
        div[data-testid="metric-container"] {
            background-color: #1a1a1a;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        label[data-testid="stMetricLabel"] {
            color: #AAAAAA !important;
        }
        div[data-testid="stMetricValue"] {
            color: #FFD700 !important; /* Valor da métrica em ouro */
        }

        /* --- HEADER DA TABELA --- */
        thead tr th {
            background-color: #FFD700 !important;
            color: #000000 !important;
        }

        /* Esconder menu padrão */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Scrollbar personalizada */
        ::-webkit-scrollbar {
            width: 10px;
            background: #000;
        }
        ::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 5px;
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# ==========================================================
# 2. BANCO DE DADOS (BACK-END)
# ==========================================================
def init_db():
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10)''')
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
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
# 3. SISTEMA DE LOGIN (INTERFACE DARK)
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # Logo Amarela
        st.markdown("<h1 style='text-align: center; color: #FFD700 !important;'>⚖️ LegalHub <span style='font-size: 20px; color: #fff;'>Enterprise</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Sistema de Inteligência Jurídica</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.info("Acesso: 'advogado1' / '123' (Admin: 'admin')")
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            
            if st.button("🔒 ACESSAR SISTEMA", use_container_width=True):
                users = run_query("SELECT * FROM usuarios WHERE username = ? AND senha = ?", (username, password), return_data=True)
                if not users.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = username
                    st.session_state.escritorio_atual = users.iloc[0]['escritorio']
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

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
# 5. APLICAÇÃO PRINCIPAL
# ==========================================================

# --- CONFIG API ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.sidebar.text_input("🔑 API Key (Google):", type="password")

if api_key:
    genai.configure(api_key=api_key)
    try:
        mods = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        mod_escolhido = "models/gemini-1.5-flash" if "models/gemini-1.5-flash" in mods else mods[0]
    except: mod_escolhido = "models/gemini-1.5-flash"

# --- DADOS USUÁRIO ---
df_user = run_query("SELECT creditos FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
creditos_atuais = df_user.iloc[0]['creditos'] if not df_user.empty else 0

# --- SIDEBAR DARK ---
with st.sidebar:
    st.markdown("<h1 style='color: #FFD700 !important;'>⚖️ LegalHub</h1>", unsafe_allow_html=True)
    st.caption(f"Licenciado para: {st.session_state.escritorio_atual}")
    st.divider()
    
    menu_opcao = st.radio(
        "MENU PRINCIPAL:",
        ["📊 Dashboard", "✍️ Redator Jurídico", "🧮 Calculadoras & Perícia", "🏛️ Estratégia de Audiência", "📂 Gestão de Casos", "🚦 Monitor de Prazos", "🔧 Ferramentas Extras"]
    )
    
    st.divider()
    
    col_cred1, col_cred2 = st.columns([1, 3])
    with col_cred1: st.write("💎")
    with col_cred2: 
        st.markdown(f"<span style='color:#FFD700; font-weight:bold'>{creditos_atuais} Créditos</span>", unsafe_allow_html=True)
        st.progress(min(creditos_atuais/50, 1.0))
    
    with st.expander("📧 Configurar E-mail"):
        email_leitura = st.text_input("E-mail:")
        senha_leitura = st.text_input("Senha App:", type="password")
        servidor_imap = st.text_input("IMAP:", value="imap.gmail.com")

    if st.button("SAIR"):
        st.session_state.logado = False
        st.rerun()

    if st.session_state.usuario_atual == 'admin':
        st.divider()
        st.subheader("👑 Painel Admin")
        novo_user = st.text_input("Login Novo")
        novo_pass = st.text_input("Senha Nova", type="password")
        novo_banca = st.text_input("Escritório")
        if st.button("CRIAR CONTA"):
            run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50))
            st.success("Criado!")

# ==========================================================
# TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='highlight-gold'>Bem-vindo, Dr(a). {st.session_state.usuario_atual}</h2>", unsafe_allow_html=True)
    st.write("Visão geral estratégica do escritório.")
    
    # Métricas Superiores
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    
    c1.metric("Documentos Gerados", docs_feitos, "+1 hoje")
    c2.metric("Créditos Restantes", creditos_atuais)
    c3.metric("Prazos Ativos", "0", "Em dia")
    
    st.markdown("---")
    
    # --- NOVO: GRÁFICO DE PIZZA/ROSCA (ÁREAS DE ATUAÇÃO) ---
    st.subheader("📈 Performance por Área")
    
    col_chart, col_info = st.columns([2, 1])
    
    with col_chart:
        # Busca dados agrupados por área
        df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
        
        if not df_areas.empty:
            # Cria o gráfico de rosca (Donut Chart) com tema Dourado
            fig = px.pie(
                df_areas, 
                values='qtd', 
                names='area', 
                hole=0.4, # Faz o buraco da rosca
                color_discrete_sequence=['#FFD700', '#FFA500', '#DAA520', '#B8860B', '#F0E68C'] # Tons de Dourado
            )
            # Configurações para Dark Mode (Fundo transparente e texto branco)
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ainda não há dados suficientes para gerar o gráfico. Crie documentos na aba Redator!")

    with col_info:
        st.markdown("### 🚀 Acesso Rápido")
        st.info(" Precisa de uma Inicial? Vá em **Redator**.")
        st.success(" Tem audiência amanhã? Vá em **Estratégia**.")
        st.warning(" Dúvida no cálculo? Vá em **Calculadoras**.")

    # --- VITRINE DE FUNCIONALIDADES ---
    st.markdown("---")
    st.markdown("### 🛠️ O Que Você Pode Fazer Aqui:")
    
    row1_c1, row1_c2, row1_c3 = st.columns(3)
    with row1_c1:
        with st.container(border=True):
            st.markdown("#### ✍️ Redator IA")
            st.write("Crie petições, contratos e recursos em segundos. A IA pesquisa jurisprudência e formata o texto para você.")
    with row1_c2:
        with st.container(border=True):
            st.markdown("#### 🧮 Calculadora Jurídica")
            st.write("Realize perícias contábeis completas (Trabalhista, Cível, Criminal) apenas anexando o contrato em PDF.")
    with row1_c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ Estratégia de Audiência")
            st.write("Prepare-se para audiências. A IA lê o processo e gera roteiros de perguntas para testemunhas e análise de risco.")

    row2_c1, row2_c2, row2_c3 = st.columns(3)
    with row2_c1:
        with st.container(border=True):
            st.markdown("#### 📂 Gestão de Casos (GED)")
            st.write("Seus arquivos gerados ficam salvos automaticamente na nuvem segura do seu escritório.")
    with row2_c2:
        with st.container(border=True):
            st.markdown("#### 🚦 Monitor de Prazos")
            st.write("Conecte seu e-mail da OAB. O sistema busca intimações e calcula a data fatal automaticamente.")
    with row2_c3:
        with st.container(border=True):
            st.markdown("#### 🔧 Ferramentas Extras")
            st.write("Utilitários essenciais: Transcrição de áudio do WhatsApp, Resumo de PDF e Comparador de Versões.")

# 2. REDATOR
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='highlight-gold'>✍️ Redator de Peças com IA</h2>", unsafe_allow_html=True)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("### Configuração")
        tipo = st.selectbox("Tipo de Peça", ["Inicial", "Contestação", "Recurso Inominado", "Apelação", "Contrato", "Parecer"])
        area = st.selectbox("Área", ["Cível", "Trabalhista", "Penal", "Família", "Tributário"])
        web = st.checkbox("Busca Jurisprudência?", value=True)
        cli = st.text_input("Cliente", value=st.session_state.cliente_recuperado)
    
    with c2:
        st.markdown("### Fatos e Dados")
        fatos = st.text_area("Descreva o caso:", height=300, value=st.session_state.fatos_recuperados, placeholder="Cole o resumo aqui...")
    
    if st.button("✨ GERAR MINUTA (1 CRÉDITO)"):
        if creditos_atuais > 0 and fatos:
            with st.spinner("IA Trabalhando..."):
                jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}. Estruture formalmente."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    if cli:
                        run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli, area, tipo, fatos + "||" + res[:500]))
                    st.markdown("### 📄 Resultado")
                    st.markdown(res)
                    st.download_button("📥 Baixar Word", gerar_word(res), f"Minuta_{tipo}.docx")
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
        elif creditos_atuais <= 0: st.error("Sem créditos.")
        else: st.warning("Preencha os fatos.")

# 3. CALCULADORAS
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='highlight-gold'>🧮 Central de Cálculos e Perícia</h2>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        opcoes_calc = ["Aluguel", "Divórcio", "FGTS", "INSS", "PASEP", "Pensão", "RMC/RCC", "Superendividamento", "Criminal (Dosimetria)", "Revisional", "Trabalhista"]
        tipo_calc = st.selectbox("Tipo de Cálculo:", opcoes_calc)
        dt_base = st.date_input("Data Base")
    with c2:
        upload_calc = st.file_uploader("📂 Anexar Contrato (PDF)", type="pdf")
    
    dados_input = st.text_area("Observações Manuais:", height=150)
    
    if st.button("🧮 CALCULAR AGORA"):
        if dados_input or upload_calc:
            with st.spinner("Processando..."):
                txt_pdf = f"\nPDF: {extrair_texto_pdf(upload_calc)}" if upload_calc else ""
                prompt = f"""Atue como Perito em {tipo_calc}. Data Base: {dt_base}. 
                DADOS: "{dados_input}" {txt_pdf}. 
                Gere LAUDO TÉCNICO com memória de cálculo."""
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown("### 📊 Laudo Gerado")
                    st.markdown(res)
                    st.download_button("📥 Baixar Laudo", gerar_word(res), "Laudo.docx")
                except Exception as e: st.error(str(e))

# 4. ESTRATÉGIA DE AUDIÊNCIA
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.markdown("<h2 class='highlight-gold'>🏛️ Preparador de Audiência</h2>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: area_aud = st.selectbox("Área", ["Trabalhista", "Cível", "Criminal", "Família"])
    with c2: tipo_aud = st.selectbox("Tipo", ["Instrução", "Conciliação", "UNA", "Inicial"])
    with c3: papel = st.selectbox("Papel", ["Autor", "Réu"])
    
    upload_aud = st.file_uploader("Anexar Processo (PDF)", type="pdf")
    obs_aud = st.text_area("Notas Estratégicas:", placeholder="Ex: A testemunha mente sobre...")
    
    if st.button("🎭 GERAR ROTEIRO ESTRATÉGICO"):
        if upload_aud or obs_aud:
            with st.spinner("Criando estratégia..."):
                txt = f"\nPDF: {extrair_texto_pdf(upload_aud)}" if upload_aud else ""
                prompt = f"""Advogado Senior {area_aud}. Audiência {tipo_aud}. Papel: {papel}. 
                Dados: {obs_aud} {txt}. 
                Gere: 1. PERGUNTAS (Para mim e para o outro). 2. RISCOS. 3. ESTRATÉGIA DE ACORDO."""
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("📥 Baixar Roteiro", gerar_word(res), "Roteiro.docx")
                except Exception as e: st.error(str(e))

# 5. GESTÃO DE CASOS
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='highlight-gold'>📂 Arquivo Digital</h2>", unsafe_allow_html=True)
    if st.button("Atualizar"): st.rerun()
    
    df = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    if not df.empty:
        st.dataframe(df[['id', 'data_criacao', 'cliente', 'area', 'tipo']], use_container_width=True)
        c1, c2 = st.columns([1, 3])
        with c1: doc_id = st.selectbox("ID:", df['id'].tolist())
        with c2:
            if st.button("📂 ABRIR DOCUMENTO"):
                row = df[df['id'] == doc_id].iloc[0]
                st.session_state.cliente_recuperado = row['cliente']
                st.session_state.fatos_recuperados = row['conteudo'].split("||")[0]
                st.success("Carregado no Redator!")
    else: st.info("Nenhum caso salvo.")

# 6. MONITOR
elif menu_opcao == "🚦 Monitor de Prazos":
    st.markdown("<h2 class='highlight-gold'>🚦 Monitor de Intimações</h2>", unsafe_allow_html=True)
    if st.button("🔄 BUSCAR NOVOS E-MAILS"):
        if email_leitura and senha_leitura:
            with st.spinner("Lendo e-mails..."):
                msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                if err: st.error(err)
                elif not msgs: st.info("Nenhuma intimação nova.")
                else:
                    for m in msgs:
                        with st.expander(f"📧 {m['assunto']}"):
                            st.write(m['corpo'])
                            if st.button("Analisar Prazo", key=m['assunto']):
                                res = genai.GenerativeModel(mod_escolhido).generate_content(f"Analise prazo: {m['corpo']}").text
                                st.write(res)
        else: st.error("Configure o e-mail na barra lateral.")

# 7. EXTRAS
elif menu_opcao == "🔧 Ferramentas Extras":
    st.markdown("<h2 class='highlight-gold'>🔧 Utilitários</h2>", unsafe_allow_html=True)
    tabs_ex = st.tabs(["PDF Resumo", "Áudio Transcrição", "Comparador"])
    
    with tabs_ex[0]:
        up = st.file_uploader("PDF", key="pdf_res")
        if up and st.button("Resumir PDF"): 
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)}").text)
            
    with tabs_ex[1]:
        aud = st.file_uploader("Áudio", type=["mp3","ogg","wav"])
        if aud and st.button("Transcrever"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(aud.getvalue())
                path = tmp.name
            f = genai.upload_file(path)
            time.sleep(2)
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(["Transcreva", f]).text)
            
    with tabs_ex[2]:
        p1 = st.file_uploader("Versão 1", key="v1")
        p2 = st.file_uploader("Versão 2", key="v2")
        if p1 and p2 and st.button("Comparar"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Diferenças: {extrair_texto_pdf(p1)} E {extrair_texto_pdf(p2)}").text)

st.markdown("---")
st.markdown("<center style='color: #555;'>🔒 LegalHub Enterprise v3.6 | Dark Mode Edition</center>", unsafe_allow_html=True)
