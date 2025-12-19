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

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub SaaS", page_icon="⚖️", layout="wide")

# --- 2. BANCO DE DADOS (SQLITE) ---
def init_db():
    """Cria o banco de dados e as tabelas se não existirem."""
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    
    # Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            senha TEXT,
            escritorio TEXT,
            email_oab TEXT
        )
    ''')
    
    # Tabela de Documentos
    c.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escritorio TEXT,
            data_criacao TEXT,
            cliente TEXT,
            area TEXT,
            tipo TEXT,
            conteudo TEXT
        )
    ''')
    
    # --- DADOS INICIAIS ---
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        # Cria usuários de teste originais
        c.execute("INSERT INTO usuarios VALUES ('advogado1', '123', 'Escritório Alpha', 'lucas@alpha.adv.br')")
        c.execute("INSERT INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br')")
        # Cria o ADMIN (Necessário para cadastrar novos escritórios pelo site)
        c.execute("INSERT INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com')")
        conn.commit()
    
    conn.close()

def run_query(query, params=(), return_data=False):
    """Função auxiliar para rodar comandos no banco de dados com segurança."""
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

# Inicializa o banco ao abrir o app
init_db()

# --- 3. SISTEMA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.title("⚖️ LegalHub Login")
        st.info("Teste: 'advogado1' / '123' | Admin: 'admin' / 'admin'")
        
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.button("Entrar no Sistema"):
            users = run_query("SELECT * FROM usuarios WHERE username = ? AND senha = ?", (username, password), return_data=True)
            
            if not users.empty:
                st.session_state.logado = True
                st.session_state.usuario_atual = username
                st.session_state.escritorio_atual = users.iloc[0]['escritorio']
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

if not st.session_state.logado:
    login_screen()
    st.stop()

# ==========================================================
# ÁREA LOGADA
# ==========================================================

# 4. FUNÇÕES AUXILIARES
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

# --- BARRA LATERAL ---
st.sidebar.header(f"🏢 {st.session_state.escritorio_atual}")
st.sidebar.caption(f"Usuário: {st.session_state.usuario_atual}")

if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.session_state.usuario_atual = ""
    st.session_state.escritorio_atual = ""
    st.rerun()

st.sidebar.divider()

# --- [NOVO] PAINEL DE ADMINISTRAÇÃO (Integrado do seu código) ---
# Só aparece se o usuário for 'admin'
if st.session_state.usuario_atual == 'admin':
    with st.sidebar.expander("👑 Cadastrar Novo Escritório"):
        st.markdown("**Novo Contrato**")
        novo_user = st.text_input("Login (Novo Usuário)")
        novo_pass = st.text_input("Senha Provisória", type="password")
        novo_banca = st.text_input("Nome do Escritório")
        novo_email = st.text_input("E-mail OAB")
        
        if st.button("💾 Cadastrar Cliente"):
            if novo_user and novo_pass and novo_banca:
                try:
                    sql = "INSERT INTO usuarios (username, senha, escritorio, email_oab) VALUES (?, ?, ?, ?)"
                    res = run_query(sql, (novo_user, novo_pass, novo_banca, novo_email))
                    if res:
                        st.success(f"✅ Sucesso! Escritório '{novo_banca}' criado.")
                except sqlite3.IntegrityError:
                    st.error("Erro: Esse login já existe.")
                except Exception as e:
                    st.error(f"Erro: {e}")
            else:
                st.warning("Preencha todos os campos.")
    st.sidebar.divider()
# -------------------------------------------------------------

# Seleção de Chave API
uso_manual = st.sidebar.checkbox("Usar chave manual", value=False)
if uso_manual:
    api_key = st.sidebar.text_input("Sua API Key:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ IA Conectada")
else:
    api_key = st.sidebar.text_input("API Key:", type="password")

# Configuração E-mail
st.sidebar.markdown("📧 **E-mail OAB (Leitura)**")
email_leitura = st.sidebar.text_input("E-mail:")
senha_leitura = st.sidebar.text_input("Senha App:", type="password")
servidor_imap = st.sidebar.text_input("Servidor IMAP:", value="imap.gmail.com")

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

# 5. LÓGICA PRINCIPAL
if api_key:
    genai.configure(api_key=api_key)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    try:
        mods = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        mod_escolhido = st.sidebar.selectbox("Modelo:", mods) if mods else "models/gemini-1.5-flash"
    except: mod_escolhido = "models/gemini-1.5-flash"

    st.title("⚖️ LegalHub IA")
    tabs = st.tabs(["✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas (SaaS)", "📅 Calc", "🏛️ Audiência", "🚦 Monitor"])

    # --- ABA 1: REDATOR ---
    with tabs[0]:
        st.header("Gerador de Peças")
        if st.button("🔄 Limpar"):
            st.session_state.fatos_recuperados = ""
            st.session_state.cliente_recuperado = ""
            st.rerun()
        
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Penal", "Família"])
            web = st.checkbox("Web Search?", value=True)
        with c2:
            cli = st.text_input("Cliente:", value=st.session_state.cliente_recuperado)
            fatos = st.text_area("Fatos:", height=150, value=st.session_state.fatos_recuperados)
            
        if st.button("✨ Gerar"):
            if fatos:
                with st.spinner("Gerando..."):
                    jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                    prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisp: {jur}. Formal."
                    try:
                        res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                        st.markdown(res)
                        st.download_button("Word", gerar_word(res), "minuta.docx")
                        if cli:
                            conteudo_salvar = fatos + "||" + res[:500]
                            sql = "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)"
                            run_query(sql, (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli, area, tipo, conteudo_salvar))
                            st.success(f"Salvo no banco de dados do {st.session_state.escritorio_atual}!")
                    except Exception as e: st.error(str(e))

    # --- ABA 2 a 5 ---
    with tabs[1]:
        st.header("Ler PDF")
        up = st.file_uploader("PDF", type="pdf")
        if up and st.button("Resumir"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)[:30000]}").text)
    
    with tabs[2]:
        st.header("Transcrição")
        aud = st.file_uploader("Audio", type=["mp3","wav","ogg"])
        if aud and st.button("Transcrever"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(aud.getvalue())
                path = tmp.name
            try:
                f = genai.upload_file(path)
                time.sleep(2)
                st.write(genai.GenerativeModel(mod_escolhido).generate_content(["Transcreva", f]).text)
            finally: os.remove(path)

    with tabs[3]:
        st.header("Comparar")
        p1 = st.file_uploader("V1", key="v1")
        p2 = st.file_uploader("V2", key="v2")
        if p1 and p2 and st.button("Comp"):
             st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Diferenças: {extrair_texto_pdf(p1)[:10000]} vs {extrair_texto_pdf(p2)[:10000]}").text)

    with tabs[4]:
        st.header("Chat")
        if "hist" not in st.session_state: st.session_state.hist = []
        for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
        if p := st.chat_input("Msg"):
            st.chat_message("user").write(p)
            st.session_state.hist.append({"role":"user", "content":p})
            res = genai.GenerativeModel(mod_escolhido).generate_content(p).text
            st.chat_message("assistant").write(res)
            st.session_state.hist.append({"role":"assistant", "content":res})

    # --- ABA 6: PASTAS SAAS ---
    with tabs[5]:
        st.header(f"📂 Arquivos: {st.session_state.escritorio_atual}")
        if st.button("Atualizar Lista"): st.rerun()
        df = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
        if not df.empty:
            st.dataframe(df.drop(columns=['conteudo']), use_container_width=True)
            doc_id = st.selectbox("ID para abrir:", df['id'].tolist())
            if st.button("Abrir Documento"):
                row = df[df['id'] == doc_id].iloc[0]
                st.session_state.cliente_recuperado = row['cliente']
                st.session_state.fatos_recuperados = row['conteudo'].split("||")[0]
                st.success("Carregado no Redator!")
        else:
            st.info("Nenhum arquivo salvo neste escritório ainda.")

    # --- ABA 7 E 8 ---
    with tabs[6]:
        st.header("Calc Prazo")
        dt = st.date_input("Data")
        esf = st.selectbox("Esfera", ["Cível", "Penal", "Trab"])
        txt = st.text_area("Texto")
        if st.button("Calc"):
             st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Calc prazo {esf} {dt}: {txt}").text)

    with tabs[7]:
        st.header("Audiência")
        pap = st.selectbox("Papel", ["Autor", "Réu"])
        fat = st.text_area("Fatos")
        if st.button("Gerar"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Roteiro {pap}: {fat}").text)

    # --- ABA 9: MONITOR ---
    with tabs[8]:
        st.header("🚦 Monitor")
        if st.button("🔄 Ler E-mail OAB"):
            if not email_leitura or not senha_leitura:
                st.error("Configure E-mail na barra lateral")
            else:
                msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                if err: st.error(err)
                elif not msgs: st.warning("Nada novo.")
                else:
                    for i, m in enumerate(msgs):
                        st.subheader(m['assunto'])
                        st.write(m['corpo'][:500])
                        if st.button(f"Analisar {i}", key=f"an_{i}"):
                            res = genai.GenerativeModel(mod_escolhido).generate_content(f"Analise prazo: {m['corpo'][:3000]}").text
                            st.write(res)
                            if st.button(f"Salvar {i}", key=f"sv_{i}"):
                                sql = "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)"
                                run_query(sql, (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m"), "Auto-Email", "Monitor", "Prazo", res[:500]))
                                st.toast("Salvo!")

else: st.warning("Configure a API Key.")
