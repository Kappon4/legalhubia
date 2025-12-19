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

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL & CSS (FRONT-END PROFISSIONAL)
# ==========================================================
st.set_page_config(
    page_title="LegalHub Enterprise", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INJEÇÃO DE CSS PERSONALIZADO ---
def local_css():
    st.markdown("""
    <style>
        :root {
            --primary-color: #0e1117;
            --background-color: #ffffff;
            --secondary-background-color: #f0f2f6;
            --text-color: #262730;
            --font: "Source Sans Pro", sans-serif;
        }
        h1, h2, h3 {
            color: #1f2937;
            font-family: 'Helvetica', sans-serif;
        }
        .stButton>button {
            background-color: #2563eb;
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #1e40af;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {
            border-radius: 8px;
            border: 1px solid #d1d5db;
        }
        section[data-testid="stSidebar"] {
            background-color: #f8fafc;
            border-right: 1px solid #e5e7eb;
        }
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
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
# 3. SISTEMA DE LOGIN (INTERFACE LIMPA)
# ==========================================================
if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "escritorio_atual" not in st.session_state: st.session_state.escritorio_atual = ""

def login_screen():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>⚖️ LegalHub</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Sistema de Inteligência Jurídica Integrada</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.info("Acesso Demonstração: 'advogado1' / '123' (Admin: 'admin')")
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            
            if st.button("🔒 Acessar Sistema", use_container_width=True):
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
# 4. FUNÇÕES AUXILIARES E INTEGRAÇÕES
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
# 5. APLICAÇÃO PRINCIPAL (DASHBOARD & FERRAMENTAS)
# ==========================================================

# --- CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.sidebar.text_input("🔑 Google API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    try:
        mods = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        mod_escolhido = "models/gemini-1.5-flash" if "models/gemini-1.5-flash" in mods else mods[0]
    except: mod_escolhido = "models/gemini-1.5-flash"

# --- RECUPERAR DADOS DO USUÁRIO ---
df_user = run_query("SELECT creditos FROM usuarios WHERE username = ?", (st.session_state.usuario_atual,), return_data=True)
creditos_atuais = df_user.iloc[0]['creditos'] if not df_user.empty else 0

# --- SIDEBAR DE NAVEGAÇÃO ---
with st.sidebar:
    st.title("🏛️ LegalHub")
    st.caption(f"Licenciado para: {st.session_state.escritorio_atual}")
    st.divider()
    
    # Menu Principal
    menu_opcao = st.radio(
        "Navegação:",
        ["📊 Dashboard", "✍️ Redator Jurídico", "🧮 Calculadoras & Perícia", "🏛️ Estratégia de Audiência", "📂 Gestão de Casos", "🚦 Monitor de Prazos", "🔧 Ferramentas Extras"]
    )
    
    st.divider()
    
    # Mostrador de Créditos
    col_cred1, col_cred2 = st.columns([1, 3])
    with col_cred1: st.write("💎")
    with col_cred2: 
        if creditos_atuais > 0:
            st.write(f"**{creditos_atuais} Créditos**")
            st.progress(min(creditos_atuais/50, 1.0))
        else:
            st.error("Sem créditos")
    
    with st.expander("📧 Configurar E-mail OAB"):
        email_leitura = st.text_input("E-mail:")
        senha_leitura = st.text_input("Senha App:", type="password")
        servidor_imap = st.text_input("IMAP:", value="imap.gmail.com")

    if st.button("Sair (Logout)"):
        st.session_state.logado = False
        st.rerun()

    # --- PAINEL ADMIN ---
    if st.session_state.usuario_atual == 'admin':
        st.divider()
        st.subheader("👑 Admin")
        novo_user = st.text_input("Novo Login")
        novo_pass = st.text_input("Senha", type="password")
        novo_banca = st.text_input("Escritório")
        if st.button("Criar Conta"):
            run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos) VALUES (?, ?, ?, ?, ?)", (novo_user, novo_pass, novo_banca, "", 50))
            st.success("Criado!")

# ==========================================================
# LÓGICA DAS TELAS (FRONT-END DINÂMICO)
# ==========================================================

# 1. DASHBOARD (HOME)
if menu_opcao == "📊 Dashboard":
    st.title(f"Bem-vindo, Dr(a). {st.session_state.usuario_atual}")
    st.markdown("Visão geral do seu escritório hoje.")
    
    c1, c2, c3 = st.columns(3)
    docs_feitos = run_query("SELECT count(*) FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True).iloc[0][0]
    
    c1.metric("Documentos Gerados", docs_feitos, "+2 hoje")
    c2.metric("Créditos Disponíveis", creditos_atuais)
    c3.metric("Prazos Monitorados", "0", "Em dia")
    
    st.subheader("🚀 Acesso Rápido")
    col_a, col_b = st.columns(2)
    with col_a: st.info("💡 **Nova Peça?** Vá para o Redator Jurídico.")
    with col_b: st.success("📈 **Cálculo Trabalhista?** Use a Calculadora.")

# 2. REDATOR JURÍDICO
elif menu_opcao == "✍️ Redator Jurídico":
    st.title("✍️ Redator de Peças com IA")
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("### Configuração")
        tipo = st.selectbox("Tipo de Peça", ["Inicial", "Contestação", "Recurso Inominado", "Apelação", "Contrato", "Parecer"])
        area = st.selectbox("Área", ["Cível", "Trabalhista", "Penal", "Família", "Tributário"])
        web = st.checkbox("Pesquisar Jurisprudência Atualizada?", value=True)
        cli = st.text_input("Nome do Cliente", value=st.session_state.cliente_recuperado)
    
    with c2:
        st.markdown("### Fatos e Dados")
        fatos = st.text_area("Descreva o caso:", height=300, value=st.session_state.fatos_recuperados, placeholder="Cole aqui o resumo do caso...")
    
    col_btn, _ = st.columns([1, 4])
    with col_btn:
        if st.button("✨ Gerar Peça (1 Crédito)", use_container_width=True):
            if creditos_atuais > 0 and fatos:
                with st.spinner("A IA está redigindo sua peça..."):
                    jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                    prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}. Estruture formalmente."
                    try:
                        res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                        run_query("UPDATE usuarios SET creditos = creditos - 1 WHERE username = ?", (st.session_state.usuario_atual,))
                        if cli:
                            run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (?, ?, ?, ?, ?, ?)", 
                                     (st.session_state.escritorio_atual, datetime.now().strftime("%d/%m/%Y"), cli, area, tipo, fatos + "||" + res[:500]))
                        st.markdown("### 📄 Minuta Gerada")
                        st.markdown(res)
                        st.download_button("📥 Baixar Word (.docx)", gerar_word(res), f"Minuta_{tipo}.docx")
                        st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")
            elif creditos_atuais <= 0: st.error("Créditos insuficientes.")
            else: st.warning("Preencha os fatos.")

# 3. CALCULADORAS & PERÍCIA
elif menu_opcao == "🧮 Calculadoras & Perícia":
    st.title("🧮 Central de Cálculos e Perícia")
    st.markdown("A IA atua como seu assistente técnico pericial. Anexe documentos para maior precisão.")
    
    c1, c2 = st.columns([1, 1])
    with c1:
        opcoes_calc = [
            "Aluguel (Reajuste/Atraso)", "Divórcio (Partilha/Pensão)", 
            "FGTS (Correção/Revisão)", "INSS (Renda Mensal/Aposentadoria)", 
            "PASEP (Atualização)", "Pensão Alimentícia", 
            "RMC e RCC (Cartão Crédito)", "Superendividamento (Lei 14.181)", 
            "Criminal (Dosimetria)", "Revisional (Juros Bancários)", 
            "Trabalhista (Rescisão)"
        ]
        tipo_calc = st.selectbox("Selecione o Cálculo:", opcoes_calc)
        dt_base = st.date_input("Data Base")
    with c2:
        upload_calc = st.file_uploader("📂 Anexar Contrato/Sentença (PDF)", type="pdf")
    
    dados_input = st.text_area("Observações Manuais:", height=150, placeholder="Ex: Salário R$ 2.000, admissão 01/01/2020...")
    
    if st.button("🧮 Processar Cálculo"):
        if dados_input or upload_calc:
            with st.spinner("Analisando documentos..."):
                txt_pdf = f"\nPDF: {extrair_texto_pdf(upload_calc)}" if upload_calc else ""
                prompt = f"""
                Atue como um Perito Judicial Contábil e Jurídico Especialista em {tipo_calc}.
                Data Base: {dt_base.strftime('%d/%m/%Y')}.
                DADOS DO USUÁRIO: "{dados_input}"
                {txt_pdf}
                TAREFA: Realize o cálculo ou perícia solicitada com base nos dados acima.
                SAÍDA: Laudo Técnico com memória de cálculo.
                """
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown("### 📊 Laudo Preliminar")
                    st.markdown(res)
                    st.download_button("📥 Baixar Laudo", gerar_word(res), "Laudo_Calculo.docx")
                except Exception as e: st.error(str(e))

# 4. ESTRATÉGIA DE AUDIÊNCIA
elif menu_opcao == "🏛️ Estratégia de Audiência":
    st.title("🏛️ Preparador de Audiência")
    
    c1, c2, c3 = st.columns(3)
    with c1: area_aud = st.selectbox("Área", ["Trabalhista", "Cível", "Criminal", "Família"])
    with c2: tipo_aud = st.selectbox("Tipo", ["Instrução", "Conciliação", "UNA", "Inicial"])
    with c3: papel = st.selectbox("Papel", ["Autor/Reclamante", "Réu/Reclamado"])
    
    upload_aud = st.file_uploader("Anexar Processo (PDF) para Análise", type="pdf")
    obs_aud = st.text_area("Pontos de Atenção:", placeholder="Ex: A testemunha chave mente sobre...")
    
    if st.button("🎭 Gerar Roteiro Estratégico"):
        if upload_aud or obs_aud:
            with st.spinner("Criando estratégia..."):
                txt = f"\nPDF: {extrair_texto_pdf(upload_aud)}" if upload_aud else ""
                prompt = f"""
                Advogado Senior {area_aud}. Audiência {tipo_aud}. Papel: {papel}. 
                Dados: {obs_aud} {txt}. 
                Gere: 
                1. ROTEIRO DE PERGUNTAS (Para mim e para o outro)
                2. RISCOS 
                3. ESTRATÉGIA DE ACORDO.
                """
                try:
                    res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                    st.markdown(res)
                    st.download_button("📥 Baixar Roteiro", gerar_word(res), "Roteiro_Audiencia.docx")
                except Exception as e: st.error(str(e))

# 5. GESTÃO DE CASOS (GED)
elif menu_opcao == "📂 Gestão de Casos":
    st.title("📂 Arquivo Digital")
    if st.button("🔄 Atualizar Lista"): st.rerun()
    
    df = run_query("SELECT * FROM documentos WHERE escritorio = ?", (st.session_state.escritorio_atual,), return_data=True)
    if not df.empty:
        st.dataframe(df[['id', 'data_criacao', 'cliente', 'area', 'tipo']], use_container_width=True)
        c1, c2 = st.columns([1, 3])
        with c1:
            doc_id = st.selectbox("Selecionar ID:", df['id'].tolist())
        with c2:
            if st.button("📂 Abrir Documento"):
                row = df[df['id'] == doc_id].iloc[0]
                st.session_state.cliente_recuperado = row['cliente']
                st.session_state.fatos_recuperados = row['conteudo'].split("||")[0]
                st.success(f"Caso de {row['cliente']} carregado no Redator!")
                time.sleep(1)
    else:
        st.info("Nenhum caso salvo ainda.")

# 6. MONITOR
elif menu_opcao == "🚦 Monitor de Prazos":
    st.title("🚦 Monitor de Intimações (E-mail)")
    if st.button("🔄 Buscar no E-mail"):
        if email_leitura and senha_leitura:
            with st.spinner("Conectando ao OAB Mail..."):
                msgs, err = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                if err: st.error(err)
                elif not msgs: st.info("Nenhuma intimação nova.")
                else:
                    for m in msgs:
                        with st.expander(f"📧 {m['assunto']}"):
                            st.write(m['corpo'])
                            if st.button("Analisar Prazo", key=m['assunto']):
                                res = genai.GenerativeModel(mod_escolhido).generate_content(f"Analise prazo fatal: {m['corpo']}").text
                                st.write(res)
        else:
            st.error("Configure o e-mail na barra lateral.")

# 7. FERRAMENTAS EXTRAS (CORRIGIDO)
elif menu_opcao == "🔧 Ferramentas Extras":
    st.title("🔧 Utilitários")
    tabs_ex = st.tabs(["PDF Resumo", "Áudio Transcrição", "Comparador"])
    
    with tabs_ex[0]:
        up = st.file_uploader("PDF", key="pdf_res")
        if up and st.button("Resumir"): 
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)}").text)
            
    with tabs_ex[1]:
        aud = st.file_uploader("Áudio/WhatsApp", type=["mp3","ogg","wav"])
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
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Diferenças entre: {extrair_texto_pdf(p1)} E {extrair_texto_pdf(p2)}").text)

# RODAPÉ
st.markdown("---")
st.caption("🔒 LegalHub Enterprise v2.0 | Sistema Seguro de Inteligência Jurídica")
