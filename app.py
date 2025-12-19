import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date
import time
import tempfile
import os
import pandas as pd
import plotly.express as px
import imaplib
import email
from email.header import decode_header
import smtplib
import ssl
from email.message import EmailMessage

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument, PermissionDenied

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- FUNÇÃO DE LEITURA DE E-MAIL (IMAP GENÉRICO/OAB) ---
def buscar_intimacoes_email(email_user, senha_app, servidor_imap):
    """
    Conecta em qualquer servidor de e-mail (OAB, Gmail, Outlook) via IMAP.
    """
    try:
        mail = imaplib.IMAP4_SSL(servidor_imap)
        mail.login(email_user, senha_app)
        mail.select("inbox")

        # Busca e-mails NÃO LIDOS
        status, messages = mail.search(None, '(UNSEEN)')
        
        # Se não tiver e-mail, retorna vazio
        if not messages[0]:
            return [], "Nenhum e-mail não lido encontrado."

        email_ids = messages[0].split()
        intimacoes_encontradas = []

        # Pega apenas os últimos 5
        for e_id in email_ids[-5:]:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decodifica Assunto
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # FILTRO: Termos Jurídicos
                    termos_chave = ["intimação", "processo", "movimentação", "push", "tribunal", "pje", "esaj", "projudi", "nota de expediente"]
                    if any(termo in subject.lower() for termo in termos_chave):
                        
                        # Extrai Corpo
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload: body = payload.decode(errors="ignore")
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload: body = payload.decode(errors="ignore")
                        
                        if body:
                            intimacoes_encontradas.append({
                                "assunto": subject,
                                "corpo": body[:2000]
                            })
        
        mail.close()
        mail.logout()
        return intimacoes_encontradas, None

    except Exception as e:
        return [], str(e)

# --- 2. PAINEL LATERAL ---
st.sidebar.header("Painel de Controle")

# Diagnóstico
versao_lib = genai.__version__
st.sidebar.caption(f"Versão Lib: {versao_lib}")

# Chave API
uso_manual = st.sidebar.checkbox("Usar chave manual", value=False)
if uso_manual:
    api_key = st.sidebar.text_input("Nova API Key:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ Chave IA Conectada")
else:
    api_key = st.sidebar.text_input("API Key:", type="password")

st.sidebar.divider()

# --- CONFIGURAÇÃO DE E-MAIL (AGORA COM SUPORTE OAB) ---
st.sidebar.markdown("📧 **Ler E-mail OAB/Tribunal**")
email_leitura = st.sidebar.text_input("Seu E-mail (ex: nome@adv.oabsp.org.br):")
senha_leitura = st.sidebar.text_input("Senha (ou App Password):", type="password")

# Seletor inteligente de provedor
tipo_provedor = st.sidebar.selectbox("Provedor do E-mail:", ["Gmail / G-Suite", "Outlook / Office 365", "Outro / OAB (Personalizado)"])

servidor_imap = ""
if tipo_provedor == "Gmail / G-Suite":
    servidor_imap = "imap.gmail.com"
elif tipo_provedor == "Outlook / Office 365":
    servidor_imap = "outlook.office365.com"
else:
    # Opção para OABs que usam servidores específicos (Locaweb, UOL, etc)
    servidor_imap = st.sidebar.text_input("Servidor IMAP (Consulte sua TI):", value="imap.gmail.com", help="Ex: imap.uol.com.br, mail.oabsp.org.br")

if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.rerun()

# --- 🔐 LOGIN ---
def check_password():
    if "logado" not in st.session_state: st.session_state.logado = False
    if st.session_state.logado: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔒 LegalHub - Acesso")
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar"):
            if "SENHA_ACESSO" not in st.secrets or senha == st.secrets["SENHA_ACESSO"]:
                st.session_state.logado = True
                st.rerun()
            else: st.error("Senha incorreta.")
    return False

if not check_password(): st.stop()

st.title("⚖️ LegalHub IA (Gestão & Inteligência)")

# 3. FUNÇÕES AUXILIARES
def conectar_planilha():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Casos Juridicos - LegalHub").sheet1 
    except: return None

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

def criar_ics_calendario(processo, data_fatal, descricao):
    dt_inicio = data_fatal.strftime('%Y%m%d')
    dt_fim = (data_fatal + timedelta(days=1)).strftime('%Y%m%d')
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//LegalHub//Monitor//PT
BEGIN:VEVENT
SUMMARY:🚨 PRAZO: {processo}
DTSTART;VALUE=DATE:{dt_inicio}
DTEND;VALUE=DATE:{dt_fim}
DESCRIPTION:{descricao}
BEGIN:VALARM
TRIGGER:-P1D
ACTION:DISPLAY
DESCRIPTION:Lembrete Prazo
END:VALARM
END:VEVENT
END:VCALENDAR"""

# 4. LÓGICA
if api_key:
    genai.configure(api_key=api_key)
    
    # Memória
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    # Modelo
    st.sidebar.divider()
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        mod_escolhido = st.sidebar.selectbox("Modelo IA:", modelos) if modelos else "models/gemini-1.5-flash"
    except: mod_escolhido = "models/gemini-1.5-flash"

    # Abas
    tabs = st.tabs(["✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas", "📅 Calc", "🏛️ Audiência", "🚦 Monitor"])
    
    # --- REDATOR ---
    with tabs[0]:
        st.header("Gerador de Peças")
        if st.button("🔄 Novo"):
            st.session_state.fatos_recuperados = ""
            st.session_state.cliente_recuperado = ""
            st.rerun()
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família"])
            web = st.checkbox("Buscar Jurisprudência?", value=True)
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
                        st.download_button("Baixar Word", gerar_word(res), "minuta.docx")
                        if cli:
                            s = conectar_planilha()
                            if s: s.append_row([datetime.now().strftime("%d/%m"), cli, area, tipo, fatos + "||" + res[:500]])
                            st.success("Salvo!")
                    except Exception as e: st.error(f"Erro: {e}")

    # --- PDF ---
    with tabs[1]:
        st.header("Ler PDF")
        up = st.file_uploader("PDF", type="pdf")
        if up and st.button("Resumir"):
            with st.spinner("Lendo..."):
                st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)[:30000]}").text)

    # --- AUDIO ---
    with tabs[2]:
        st.header("Transcrição")
        aud = st.file_uploader("Áudio", type=["mp3", "wav", "m4a", "ogg"])
        if aud and st.button("Transcrever"):
            with st.spinner("Processando..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(aud.getvalue())
                    p = tmp.name
                try:
                    f = genai.upload_file(p)
                    time.sleep(2)
                    st.write(genai.GenerativeModel(mod_escolhido).generate_content(["Transcreva.", f]).text)
                finally: os.remove(p)

    # --- COMPARADOR ---
    with tabs[3]:
        st.header("Comparar")
        p1 = st.file_uploader("V1", type="pdf", key="v1")
        p2 = st.file_uploader("V2", type="pdf", key="v2")
        if p1 and p2 and st.button("Comparar"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Diferenças: {extrair_texto_pdf(p1)[:10000]} vs {extrair_texto_pdf(p2)[:10000]}").text)

    # --- CHAT ---
    with tabs[4]:
        st.header("Chat")
        if "hist" not in st.session_state: st.session_state.hist = []
        for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
        if p := st.chat_input("Dúvida?"):
            st.chat_message("user").write(p)
            st.session_state.hist.append({"role":"user", "content":p})
            res = genai.GenerativeModel(mod_escolhido).generate_content(p).text
            st.chat_message("assistant").write(res)
            st.session_state.hist.append({"role":"assistant", "content":res})

    # --- PASTAS ---
    with tabs[5]:
        st.header("Pastas (GED)")
        if st.button("Atualizar"): st.session_state.d = None
        s = conectar_planilha()
        if s:
            df = pd.DataFrame(s.get_all_records())
            if not df.empty and "Cliente" in df.columns:
                cli_sel = st.selectbox("Cliente:", ["Todos"] + list(df["Cliente"].unique()))
                df_show = df[df["Cliente"] == cli_sel] if cli_sel != "Todos" else df
                st.dataframe(df_show)
                if not df_show.empty:
                    idx = st.selectbox("ID Doc:", df_show.index)
                    if st.button("Abrir"):
                        row = df.loc[idx]
                        st.session_state.cliente_recuperado = row["Cliente"]
                        st.session_state.fatos_recuperados = str(row.iloc[-1]).split("||")[0]
                        st.success("Carregado no Redator!")

    # --- CALC ---
    with tabs[6]:
        st.header("Calc Prazo")
        dt = st.date_input("Data Pub")
        esf = st.selectbox("Esfera", ["Cível", "Penal", "Trabalhista"])
        txt = st.text_area("Texto")
        if st.button("Calcular"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Calc prazo {esf}, data {dt}: {txt}").text)

    # --- AUDIENCIA ---
    with tabs[7]:
        st.header("Audiência")
        pap = st.selectbox("Papel", ["Autor", "Réu"])
        fat = st.text_area("Fatos Caso")
        if st.button("Gerar"):
            st.write(genai.GenerativeModel(mod_escolhido).generate_content(f"Roteiro {pap}: {fat}").text)

    # --- MONITOR (COM SUPORTE OAB) ---
    with tabs[8]:
        st.header("🚦 Monitor de Prazos (Leitura de E-mail)")
        st.info(f"Conectando via servidor: {servidor_imap}")

        if st.button("🔄 Ler E-mail do Tribunal"):
            if not email_leitura or not senha_leitura:
                st.error("Preencha E-mail e Senha na barra lateral!")
            else:
                with st.spinner("Buscando intimações..."):
                    msgs, erro = buscar_intimacoes_email(email_leitura, senha_leitura, servidor_imap)
                    
                    if erro:
                        st.error(f"Erro de conexão: {erro}")
                        st.info("Verifique se o Servidor IMAP está correto na barra lateral.")
                    elif not msgs:
                        st.warning("Nenhum e-mail jurídico novo encontrado (não lido).")
                    else:
                        st.success(f"{len(msgs)} intimações encontradas!")
                        for i, m in enumerate(msgs):
                            st.divider()
                            st.subheader(f"📧 {m['assunto']}")
                            with st.expander("Ver texto"): st.write(m['corpo'])
                            
                            if st.button(f"Analisar {i+1}", key=f"a_{i}"):
                                prompt = f"Analise: Assunto: {m['assunto']}. Corpo: {m['corpo'][:3000]}. Saída: RESUMO | PRAZO | DATA FATAL (Base: {date.today()})"
                                res = genai.GenerativeModel(mod_escolhido).generate_content(prompt).text
                                st.write(res)
                                if st.button("Salvar", key=f"s_{i}"):
                                    s = conectar_planilha()
                                    if s: 
                                        s.append_row([datetime.now().strftime("%d/%m"), "Email", "Monitor", "Prazo", res[:500]])
                                        st.toast("Salvo!")

else: st.warning("Configure a Chave API.")
