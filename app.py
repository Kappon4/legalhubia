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
    """Cria o banco e atualiza estrutura se necessário."""
    conn = sqlite3.connect('legalhub.db')
    c = conn.cursor()
    
    # Cria tabelas base
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            senha TEXT,
            escritorio TEXT,
            email_oab TEXT,
            creditos INTEGER DEFAULT 10
        )
    ''')
    
    # --- MIGRATION ---
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN creditos INTEGER DEFAULT 10")
    except:
        pass 
    # -----------------

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
    
    # Usuários Padrão
    c.execute('SELECT count(*) FROM usuarios')
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado1', '123', 'Escritório Alpha', 'lucas@alpha.adv.br', 10)")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('advogado2', '123', 'Escritório Beta', 'joao@beta.adv.br', 5)")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES ('admin', 'admin', 'LegalHub Master', 'suporte@legalhub.com', 9999)")
        conn.commit()
    
    conn.close()

def run_query(query, params=(), return_data=False):
    """Função para rodar SQL."""
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

# Inicializa/Atualiza DB
init_db()

# --- 3. SISTEMA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.title("⚖️ LegalHub Login")
        st.info("Teste: 'advogado1' (10 créditos) | 'advogado2' (5 créditos)")
        
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

# --- RECUPERAR CRÉDITOS DO USUÁRIO ATUAL ---
df_user = run_query("SELECT creditos FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
creditos_atuais = df_user.iloc[0]['creditos'] if not df_user.empty else 0

# --- BARRA LATERAL ---
st.sidebar.header(f"🏢 {st.session_state.escritorio_atual}")
st.sidebar.text(f"Usuário: {st.session_state.usuario_atual}")

# MOSTRADOR DE CRÉDITOS
if creditos_atuais > 0:
    st.sidebar.metric("Créditos de IA", creditos_atuais)
else:
    st.sidebar.error("⚠️ Créditos Esgotados")

if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.rerun()

st.sidebar.divider()

# --- PAINEL DE ADMINISTRAÇÃO ---
if st.session_state.usuario_atual == 'admin':
    with st.sidebar.expander("👑 Gestão de Escritórios"):
        tabs_admin = st.tabs(["Novo", "Recarregar"])
        
        with tabs_admin[0]: # Criar Novo
            st.markdown("**Novo Contrato**")
            novo_user = st.text_input("Login")
            novo_pass = st.text_input("Senha", type="password")
            novo_banca = st.text_input("Escritório")
            novo_email = st.text_input("E-mail")
            novo_credito = st.number_input("Créditos Iniciais", value=50)
            
            if st.button("💾 Criar"):
                try:
                    sql = "INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)"
                    run_query(sql, (novo_user, novo_pass, novo_banca, novo_email, novo_credito))
                    st.success("Criado!")
                except Exception as e: st.error(f"Erro: {e}")
        
        with tabs_admin[1]: # Recarregar Créditos
            st.markdown("**Adicionar Créditos**")
            all_users = run_query("SELECT username, creditos FROM usuarios", return_data=True)
            if not all_users.empty:
                user_recarga = st.selectbox("Selecione o Cliente:", all_users['username'])
                qtd_recarga = st.number_input("Adicionar quanto?", value=10)
                if st.button("💰 Adicionar"):
                    run_query("UPDATE usuarios SET creditos = creditos + ? WHERE username = ?", (qtd_recarga, user_recarga))
                    st.success("Recarregado!")
                    time.sleep(1)
                    st.rerun()
    st.sidebar.divider()

# Seleção de Chave API
uso_manual = st.sidebar.checkbox("Usar chave manual", value=False)
if uso_manual:
    api_key = st.sidebar.text_input("Sua API Key:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.sidebar.text_input("API Key:", type="password")

if api_key: st.sidebar.success("✅ IA Conectada")

# Configuração E-mail
st.sidebar.markdown("📧 **E-mail OAB**")
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
    tabs = st.tabs(["✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas", "🧮 Calculadora", "🏛️ Audiência", "🚦 Monitor"])

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
            
        if creditos_atuais > 0:
            if st.button("✨ Gerar (Custa 1 Crédito)"):
                if fatos:
                    with st.spinner("Gerando e descontando crédito..."):
                        jur = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                        prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisp: {jur}. Formal."
                        try:
                            res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                            run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                            if cli:
                                conteudo_salvar = fatos + "||" + res[:500]
                                sql = "INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)"
                                run_query(sql, (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli, area, tipo, conteudo_salvar))
                                st.success(f"Salvo! Créditos restantes: {creditos_atuais - 1}")
                            st.markdown(res)
                            st.download_button("Word", gerar_word(res), "minuta.docx")
                            time.sleep(2)
                            st.rerun()
                        except Exception as e: st.error(str(e))
        else:
            st.error("🚫 Créditos Esgotados.")
            st.button("✨ Gerar (Bloqueado)", disabled=True)

    # --- ABAS 2 a 5 ---
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
            st.info("Nenhum arquivo salvo ainda.")

    # --- ABA 7: CALCULADORA COM UPLOAD PDF (NOVA) ---
    with tabs[6]:
        st.header("🧮 Calculadoras Jurídicas & Perícias")
        st.markdown("Selecione o tipo de cálculo. Você pode anexar o contrato (PDF) para a IA extrair os dados automaticamente.")
        
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            opcoes_calc = [
                "Aluguel (Reajuste/Atraso)", "Divórcio (Partilha/Pensão)", 
                "FGTS (Correção/Revisão)", "INSS (Renda Mensal/Aposentadoria)", 
                "PASEP (Atualização)", "Pensão Alimentícia", 
                "RMC e RCC (Cartão Crédito)", "Superendividamento (Lei 14.181)", 
                "Criminal (Dosimetria)", "Revisional (Juros Bancários)", 
                "Trabalhista (Rescisão)"
            ]
            tipo_calc = st.selectbox("Tipo de Cálculo:", opcoes_calc)
            dt_base = st.date_input("Data Base", datetime.now())
        
        with col_calc2:
            # --- CAMPO DE UPLOAD ADICIONADO AQUI ---
            upload_calc = st.file_uploader("📂 Anexar Contrato/Documento (PDF)", type="pdf")
            if upload_calc: st.info("Arquivo anexado. A IA lerá o conteúdo.")
        
        dados_input = st.text_area(f"Observações / Dados Manuais:", height=150, placeholder="Ex: Valor da causa, datas, salários...")

        if st.button("🧮 Calcular / Gerar Laudo"):
            if dados_input or upload_calc:
                with st.spinner(f"Analisando documentos e calculando..."):
                    # Extrai texto do PDF se houver
                    texto_anexo = ""
                    if upload_calc:
                        texto_anexo = f"\n\n--- CONTEÚDO DO PDF ANEXADO ---\n{extrair_texto_pdf(upload_calc)}"
                    
                    prompt_calc = f"""
                    Atue como um Perito Judicial Contábil e Jurídico Especialista em {tipo_calc}.
                    Data Base: {dt_base.strftime('%d/%m/%Y')}.
                    
                    DADOS DO USUÁRIO: "{dados_input}"
                    {texto_anexo}

                    TAREFA: Realize o cálculo ou perícia solicitada com base nos dados acima.
                    Se for Revisional/RMC, identifique juros no texto do PDF.
                    Se for Criminal, use os fatos narrados.
                    
                    SAÍDA: Laudo Técnico com memória de cálculo.
                    """
                    try:
                        res_calc = genai.GenerativeModel(mod_escolhido).generate_content(prompt_calc).text
                        st.markdown(f"### 📊 Resultado: {tipo_calc}")
                        st.markdown(res_calc)
                        st.download_button("Baixar Laudo (DOCX)", gerar_word(res_calc), f"calculo.docx")
                    except Exception as e:
                        st.error(f"Erro: {e}")
            else:
                st.warning("Preencha os dados ou anexe um PDF.")

    with tabs[7]:
        st.header("Audiência")
        pap = st.selectbox("Papel", ["Autor", "Réu"])
        fat = st.text_area("Fatos")
        if st.button("Gerar"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Roteiro {pap}: {fat}").text)

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
