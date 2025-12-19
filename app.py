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
# 1. CONFIGURAÇÃO VISUAL - TEMA DARK & GOLD
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZADO ---
def local_css():
    st.markdown("""
    <style>
        /* --- GERAL --- */
        .stApp {
            background: linear-gradient(135deg, #000000 0%, #1c1c1c 100%);
            color: #FFFFFF;
        }
        h1, h2, h3, h4 {
            color: #FFFFFF !important;
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 600;
        }
        .highlight-gold { color: #FFD700 !important; }

        /* --- BOTÕES --- */
        .stButton>button {
            background-color: #FFD700;
            color: #000000;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: bold;
            transition: all 0.3s ease;
            width: 100%;
        }
        .stButton>button:hover {
            background-color: #E5C100;
            transform: scale(1.02);
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.4);
        }

        /* --- INPUTS --- */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {
            background-color: #2d2d2d !important;
            color: #FFFFFF !important;
            border: 1px solid #444 !important;
            border-radius: 8px;
        }
        
        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background-color: #0a0a0a;
            border-right: 1px solid #333;
        }

        /* --- CARDS DASHBOARD --- */
        div[data-testid="metric-container"] {
            background-color: #1a1a1a;
            border: 1px solid #333;
            border-radius: 10px;
        }
        
        /* Estiliza os containers (cards) */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            /* Tenta focar nos containers internos */
        }
        
        div[data-testid="stExpander"] {
            background-color: #2d2d2d;
            border: 1px solid #444;
            border-radius: 8px;
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
# 3. LOGIN
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #FFD700 !important;'>⚖️ LegalHub <span style='font-size: 20px; color: #fff;'>Enterprise</span></h1>", unsafe_allow_html=True)
        
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
                else: st.error("Credenciais inválidas.")

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

# --- CONTROLE DE NAVEGAÇÃO EXTRA (PARA OS CARDS) ---
# Usamos session_state para forçar a mudança de página caso venha dos cards
if "navegacao_override" not in st.session_state:
    st.session_state.navegacao_override = None

with st.sidebar:
    st.markdown("<h1 style='color: #FFD700 !important;'>⚖️ LegalHub</h1>", unsafe_allow_html=True)
    st.caption(f"Licenciado para: {st.session_state.escritorio_atual}")
    st.divider()
    
    # Lista de Opções
    opcoes_menu = ["📊 Dashboard", "✍️ Redator Jurídico", "🧮 Calculadoras & Perícia", "🏛️ Estratégia de Audiência", "📂 Gestão de Casos", "🚦 Monitor de Prazos", "🔧 Ferramentas Extras"]
    
    # Se houver um override (clique no card), define o index
    idx_menu = 0
    if st.session_state.navegacao_override:
        try:
            idx_menu = opcoes_menu.index(st.session_state.navegacao_override)
        except:
            idx_menu = 0
        st.session_state.navegacao_override = None # Limpa após usar
    
    menu_opcao = st.radio(
        "MENU PRINCIPAL:",
        opcoes_menu,
        index=idx_menu
    )
    
    st.divider()
    col_cred1, col_cred2 = st.columns([1, 3])
    with col_cred1: st.write("💎")
    with col_cred2: 
        st.markdown(f"<span style='color:#FFD700; font-weight:bold'>{creditos_atuais} Créditos</span>", unsafe_allow_html=True)
        st.progress(min(creditos_atuais/50, 1.0))
    
    if st.button("SAIR"):
        st.session_state.logado = False
        st.rerun()

    if st.session_state.usuario_atual == 'admin':
        st.divider()
        with st.expander("👑 Admin"):
            novo_user = st.text_input("Login")
            novo_pass = st.text_input("Senha", type="password")
            novo_banca = st.text_input("Escritório")
            if st.button("Criar"):
                run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50))
                st.success("Criado!")

# ==========================================================
# LÓGICA DAS TELAS
# ==========================================================

# 1. DASHBOARD
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='highlight-gold'>Bem-vindo, Dr(a). {st.session_state.usuario_atual}</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    c1.metric("Documentos", docs_feitos)
    c2.metric("Créditos", creditos_atuais)
    c3.metric("Prazos", "0")
    
    st.markdown("---")
    st.subheader("📈 Performance por Área")
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        df_areas = run_query("SELECT area, COUNT(*) as qtd FROM documentos WHERE escritorio = ? GROUP BY area", (st.session_state.escritorio_atual,), return_data=True)
        if not df_areas.empty:
            fig = px.pie(df_areas, values='qtd', names='area', hole=0.4, color_discrete_sequence=['#FFD700', '#FFA500', '#DAA520', '#B8860B', '#F0E68C'])
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Sem dados suficientes.")
    
    with col_info:
        st.info("💡 Dica: Use o Redator para gerar documentos e alimentar o gráfico.")

    # ==========================================================
    # --- INTEGRAÇÃO DOS 6 CARDS ---
    # ==========================================================
    st.markdown("---")
    st.markdown("### 🛠️ Funcionalidades Rápidas:")
    
    # LINHA 1
    r1c1, r1c2, r1c3 = st.columns(3)
    
    with r1c1:
        with st.container(border=True):
            st.markdown("#### ✍️ Redator IA")
            st.caption("Crie petições e contratos.")
            if st.button("Acessar Redator"):
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r1c2:
        with st.container(border=True):
            st.markdown("#### 🧮 Perícia")
            st.caption("Cálculos Trabalhistas e Cíveis.")
            if st.button("Acessar Perícia"):
                st.session_state.navegacao_override = "🧮 Calculadoras & Perícia"
                st.rerun()

    with r1c3:
        with st.container(border=True):
            st.markdown("#### 🏛️ Audiência")
            st.caption("Estratégia e Perguntas.")
            if st.button("Acessar Audiência"):
                st.session_state.navegacao_override = "🏛️ Estratégia de Audiência"
                st.rerun()

    st.write("") # Espaçamento
    
    # LINHA 2
    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        with st.container(border=True):
            st.markdown("#### ⚖️ Jurisprudência")
            st.caption("Pesquisa inteligente.")
            if st.button("Pesquisar"):
                # Manda para redator, onde tem busca
                st.session_state.navegacao_override = "✍️ Redator Jurídico"
                st.rerun()

    with r2c2:
        with st.container(border=True):
            st.markdown("#### 📄 Chat com PDF")
            st.caption("Resuma e converse com processos.")
            if st.button("Acessar Chat PDF"):
                st.session_state.navegacao_override = "🔧 Ferramentas Extras"
                st.rerun()

    with r2c3:
        with st.container(border=True):
            st.markdown("#### 📅 Prazos")
            st.caption("Calculadora e gestão de datas.")
            if st.button("Ver Prazos"):
                st.session_state.navegacao_override = "🚦 Monitor de Prazos"
                st.rerun()
    # ==========================================================

# 2. REDATOR (ATUALIZADO COM SELETOR DE CLIENTE)
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='highlight-gold'>✍️ Redator de Peças</h2>", unsafe_allow_html=True)
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    # Busca clientes existentes no banco para este escritório
    df_clientes = run_query("SELECT DISTINCT cliente FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    lista_clientes = df_clientes['cliente'].tolist() if not df_clientes.empty else []

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("### Configuração")
        tipo = st.selectbox("Tipo de Peça", ["Inicial", "Contestação", "Recurso Inominado", "Apelação", "Contrato", "Parecer"])
        area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
        web = st.checkbox("Jurisprudência?", value=True)
        
        # --- SELETOR DE CLIENTE INTELIGENTE ---
        st.markdown("### 👤 Cliente")
        modo_cliente = st.radio("Opção:", ["Selecionar Existente", "Novo Cadastro"], horizontal=True, label_visibility="collapsed")
        
        cli_final = ""
        if modo_cliente == "Selecionar Existente":
            if lista_clientes:
                # Se veio de um arquivo aberto, tenta selecionar ele
                idx = 0
                if st.session_state.cliente_recuperado in lista_clientes:
                    idx = lista_clientes.index(st.session_state.cliente_recuperado)
                cli_final = st.selectbox("Selecione:", lista_clientes, index=idx)
            else:
                st.warning("Nenhum cliente cadastrado.")
                cli_final = st.text_input("Nome do Novo Cliente:")
        else:
            cli_final = st.text_input("Nome do Novo Cliente:")
        # ----------------------------------------

    with c2:
        st.markdown("### Fatos e Dados")
        fatos = st.text_area("Descreva o caso:", height=300, value=st.session_state.fatos_recuperados)
    
    if st.button("✨ GERAR MINUTA (1 CRÉDITO)"):
        if creditos_atuais > 0 and fatos and cli_final:
            with st.spinner("Redigindo..."):
                jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisp: {jur}. Formal."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                    
                    # --- CORREÇÃO: Salva o texto COMPLETO (sem limite de 500) ---
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli_final, area, tipo, fatos + "||" + res))
                    
                    st.markdown(res)
                    st.download_button("Word", gerar_word(res), "Minuta.docx")
                    st.success(f"Salvo na pasta de: {cli_final}")
                    time.sleep(2)
                    st.rerun()
                except Exception as e: st.error(str(e))
        else: st.error("Verifique créditos e campos obrigatórios.")

# 3. CALCULADORA
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.markdown("<h2 class='highlight-gold'>🧮 Central de Perícia</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        opcoes_calc = ["Aluguel", "Divórcio", "FGTS", "INSS", "PASEP", "Pensão", "RMC/RCC", "Superendividamento", "Criminal (Dosimetria)", "Revisional", "Trabalhista"]
        tipo_calc = st.selectbox("Tipo de Cálculo:", opcoes_calc)
        dt_base = st.date_input("Data Base")
    with c2:
        upload = st.file_uploader("Contrato (PDF)", type="pdf")
    dados = st.text_area("Dados Manuais:")
    if st.button("🧮 Calcular"):
        if dados or upload:
            with st.spinner("Calculando..."):
                txt = f"\nPDF: {extrair_texto_pdf(upload)}" if upload else ""
                prompt = f"Perito {tipo_calc}. Data: {dt_base}. Dados: {dados} {txt}. Gere Laudo."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("Laudo", gerar_word(res), "Laudo.docx")
                except Exception as e: st.error(str(e))

# 4. AUDIENCIA
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.markdown("<h2 class='highlight-gold'>🏛️ Preparador de Audiência</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        area = st.selectbox("Área", ["Trabalhista", "Cível", "Criminal"])
        papel = st.selectbox("Papel", ["Autor", "Réu"])
    with c2:
        upload = st.file_uploader("Processo (PDF)", type="pdf")
    obs = st.text_area("Pontos Chave:")
    if st.button("🎭 Gerar Roteiro"):
        if obs or upload:
            with st.spinner("Criando estratégia..."):
                txt = f"\nPDF: {extrair_texto_pdf(upload)}" if upload else ""
                prompt = f"Advogado {area}. Papel: {papel}. Dados: {obs} {txt}. Roteiro de Perguntas e Riscos."
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("Roteiro", gerar_word(res), "Roteiro.docx")
                except: st.error("Erro na IA")

# ==========================================================
# 5. GESTÃO DE CASOS (COM BOTÃO DE EXCLUIR)
# ==========================================================
elif menu_opcao == "📂 Gestão de Casos":
    st.markdown("<h2 class='highlight-gold'>📂 Arquivo Digital</h2>", unsafe_allow_html=True)
    
    if "pasta_aberta" not in st.session_state: st.session_state.pasta_aberta = None
    df_docs = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)

    if not df_docs.empty:
        # VISÃO DE PASTAS
        if st.session_state.pasta_aberta is None:
            st.info("Selecione uma pasta para ver os arquivos.")
            clientes_unicos = df_docs['cliente'].unique()
            cols = st.columns(4) 
            for i, cliente in enumerate(clientes_unicos):
                with cols[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"### 📁")
                        st.markdown(f"**{cliente}**")
                        qtd = len(df_docs[df_docs['cliente'] == cliente])
                        st.caption(f"{qtd} itens")
                        if st.button(f"Abrir", key=f"btn_{i}"):
                            st.session_state.pasta_aberta = cliente
                            st.rerun()

        # DENTRO DA PASTA
        else:
            col_back, col_title = st.columns([1, 10])
            with col_back:
                if st.button("⬅ Voltar"):
                    st.session_state.pasta_aberta = None
                    st.rerun()
            with col_title:
                st.markdown(f"### 📂 Pasta: {st.session_state.pasta_aberta}")

            # ADD ITEM
            with st.expander("➕ Adicionar Novo Documento ou Nota", expanded=False):
                c_add1, c_add2 = st.columns(2)
                novo_tipo = c_add1.text_input("Nome do Item (Ex: RG, Procuração):")
                nova_area = c_add2.selectbox("Categoria:", ["Documentos Pessoais", "Provas", "Andamento", "Anotações", "Financeiro"])
                
                tab_up, tab_txt = st.tabs(["📤 Upload Arquivo", "✍️ Nota de Texto"])
                conteudo_novo = ""
                with tab_up: arquivo_novo = st.file_uploader("Arquivo (PDF)", key="novo_up")
                with tab_txt: texto_novo = st.text_area("Conteúdo da Nota:", key="nova_nota")

                if st.button("💾 Salvar na Pasta"):
                    if novo_tipo:
                        if arquivo_novo: conteudo_novo = f"[ARQUIVO EXTERNO] {extrair_texto_pdf(arquivo_novo)}"
                        elif texto_novo: conteudo_novo = texto_novo
                        else: conteudo_novo = "Item adicionado sem conteúdo."
                        run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), st.session_state.pasta_aberta, nova_area, novo_tipo, conteudo_novo))
                        st.success("Adicionado!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()
            arquivos_cliente = df_docs[df_docs['cliente'] == st.session_state.pasta_aberta]
            
            for index, row in arquivos_cliente.iterrows():
                icone = "📝" if row['area'] == "Anotações" else "📄"
                with st.expander(f"{icone} {row['tipo']} ({row['data_criacao']}) - {row['area']}"):
                    texto_view = row['conteudo'].split("||")[-1] if "||" in row['conteudo'] else row['conteudo']
                    st.markdown(texto_view)
                    
                    c_down, c_del = st.columns([4, 1])
                    with c_down:
                        st.download_button("📥 Baixar", gerar_word(texto_view), f"{row['tipo']}.docx", key=f"down_{row['id']}")
                    with c_del:
                        if st.button("🗑️ Excluir", key=f"del_{row['id']}"):
                            run_query("DELETE FROM documentos WHERE id = ?", (row['id'],))
                            st.toast("Item excluído!")
                            time.sleep(1)
                            st.rerun()
    else: st.warning("📭 Nenhum arquivo encontrado.")

# 6. MONITOR
elif menu_opcao == "🚦 Monitor de Prazos":
    st.markdown("<h2 class='highlight-gold'>🚦 Monitor de Intimações</h2>", unsafe_allow_html=True)
    
    # Simulação de inputs de email para evitar erro de variável não definida
    c_email1, c_email2, c_email3 = st.columns(3)
    email_leitura = c_email1.text_input("Email", placeholder="advogado@email.com")
    senha_leitura = c_email2.text_input("Senha de App", type="password")
    servidor_imap = c_email3.text_input("Servidor IMAP", value="imap.gmail.com")

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
        else: st.error("Preencha os dados de e-mail acima.")

# 7. EXTRAS
elif menu_opcao == "🔧 Ferramentas Extras":
    st.markdown("<h2 class='highlight-gold'>🔧 Utilitários</h2>", unsafe_allow_html=True)
    tabs_ex = st.tabs(["PDF", "Áudio", "Comparador"])
    with tabs_ex[0]:
        up = st.file_uploader("PDF", key="pdf_res")
        if up and st.button("Resumir"): st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)}").text)
    with tabs_ex[1]:
        aud = st.file_uploader("Áudio", type=["mp3","ogg","wav"])
        if aud and st.button("Transcrever"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp: tmp.write(aud.getvalue()); path = tmp.name
            f = genai.upload_file(path); time.sleep(2)
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(["Transcreva", f]).text)
    with tabs_ex[2]:
        p1 = st.file_uploader("V1", key="v1"); p2 = st.file_uploader("V2", key="v2")
        if p1 and p2 and st.button("Comparar"): st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Dif: {extrair_texto_pdf(p1)} vs {extrair_texto_pdf(p2)}").text)

st.markdown("---")
st.markdown("<center style='color: #555;'>🔒 LegalHub Enterprise v5.5 | Delete & Fix Edition</center>", unsafe_allow_html=True)
