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

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument, PermissionDenied

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- FUNÇÃO DE LEITURA DE E-MAIL (IMAP) ---
def buscar_intimacoes_email(email_user, senha_app, provedor="gmail"):
    """
    Conecta no e-mail, busca mensagens não lidas com termos jurídicos e retorna o texto.
    """
    imap_server = "imap.gmail.com" if provedor == "gmail" else "outlook.office365.com"
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, senha_app)
        mail.select("inbox")

        # Busca e-mails NÃO LIDOS (UNSEEN)
        status, messages = mail.search(None, '(UNSEEN)')
        email_ids = messages[0].split()
        
        intimacoes_encontradas = []

        # Pega apenas os últimos 5 para não travar o sistema
        for e_id in email_ids[-5:]:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decodifica o Assunto
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # FILTRO: Só processa se parecer jurídico
                    termos_chave = ["intimação", "processo", "movimentação", "push", "tribunal", "pje", "esaj", "projudi"]
                    if any(termo in subject.lower() for termo in termos_chave):
                        
                        # Extrai o corpo do e-mail
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True).decode()
                                    break # Pega só o texto puro
                        else:
                            body = msg.get_payload(decode=True).decode()
                        
                        intimacoes_encontradas.append({
                            "assunto": subject,
                            "corpo": body[:2000] # Limita caracteres para a IA
                        })
        
        mail.close()
        mail.logout()
        return intimacoes_encontradas, None

    except Exception as e:
        return [], str(e)

# --- 2. PAINEL LATERAL E DIAGNÓSTICO ---
st.sidebar.header("Painel de Controle")

versao_lib = genai.__version__
st.sidebar.caption(f"Versão da Lib: {versao_lib}")

# Seleção de Chave
uso_manual = st.sidebar.checkbox("Usar chave manual", value=False)
api_key = None

if uso_manual:
    api_key = st.sidebar.text_input("Cole sua NOVA API Key:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ Chave IA Conectada")
else:
    api_key = st.sidebar.text_input("Cole sua API Key:", type="password")

st.sidebar.divider()
# --- CONFIGURAÇÃO DE E-MAIL PARA LEITURA ---
st.sidebar.markdown("📧 **Ler E-mails do Tribunal**")
st.sidebar.caption("Para ler automaticamente, configure abaixo:")
email_leitura = st.sidebar.text_input("Seu E-mail (Gmail/Outlook):")
senha_leitura = st.sidebar.text_input("Senha de App (Não a normal):", type="password", help="Gere uma Senha de App no Google/Microsoft para permitir o acesso.")
provedor_email = st.sidebar.selectbox("Provedor:", ["gmail", "outlook"])

if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.rerun()

# --- 🔐 SISTEMA DE LOGIN ---
def check_password():
    if "logado" not in st.session_state: st.session_state.logado = False
    if st.session_state.logado: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔒 Acesso Restrito - LegalHub")
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar"):
            if "SENHA_ACESSO" not in st.secrets or senha == st.secrets["SENHA_ACESSO"]:
                st.session_state.logado = True
                st.rerun()
            else: st.error("Senha incorreta.")
    return False

if not check_password(): st.stop()
# ---------------------------

st.title("⚖️ LegalHub IA (Gestão & Inteligência)")

# 3. CONEXÕES E FUNÇÕES
def conectar_planilha():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Casos Juridicos - LegalHub").sheet1 
    except Exception as e: return None

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

# 4. LÓGICA PRINCIPAL
if api_key:
    genai.configure(api_key=api_key)
    
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    st.sidebar.divider()
    try:
        modelos_reais = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_reais.append(m.name)
        if modelos_reais:
            modelo_escolhido = st.sidebar.selectbox("Modelo IA:", modelos_reais, index=0)
        else:
            modelo_escolhido = "models/gemini-1.5-flash" 
    except:
        modelo_escolhido = "models/gemini-1.5-flash"

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas", "📅 Calc", "🏛️ Audiência", "🚦 Monitor (Auto)"
    ])
    
    # --- ABA 1: REDATOR ---
    with tab1:
        st.header("Gerador de Peças")
        if st.button("🔄 Novo Caso"):
            st.session_state.fatos_recuperados = ""
            st.session_state.cliente_recuperado = ""
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato", "Parecer"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
            web = st.checkbox("Buscar Jurisprudência?", value=True)
        with c2:
            cliente = st.text_input("Cliente:", value=st.session_state.cliente_recuperado)
            fatos = st.text_area("Fatos / Texto:", height=150, value=st.session_state.fatos_recuperados)
        
        if st.button("✨ Gerar Minuta"):
            if fatos:
                with st.spinner(f"Usando {modelo_escolhido}..."):
                    jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                    prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}. Estruture formalmente."
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt).text
                        st.markdown(res)
                        st.download_button("Baixar Word", gerar_word(res), "minuta.docx")
                        if cliente:
                            s = conectar_planilha()
                            if s: 
                                conteudo_backup = fatos + " || " + res[:500] 
                                s.append_row([datetime.now().strftime("%d/%m/%Y"), cliente, area, tipo, conteudo_backup]) 
                                st.success("Salvo na Pasta!")
                    except Exception as e: st.error(f"Erro: {e}")

    # --- ABAS 2 a 8 MANTIDAS IGUAIS ---
    with tab2: 
        st.header("Análise PDF")
        up = st.file_uploader("Subir PDF", type="pdf")
        if up and st.button("Resumir"): 
             with st.spinner("Lendo..."):
                st.write(genai.GenerativeModel(modelo_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)[:30000]}").text)

    with tab3:
        st.header("🎙️ Transcrição")
        aud = st.file_uploader("Áudio", type=["mp3", "wav", "m4a", "ogg"])
        if aud and st.button("Transcrever"):
            with st.spinner("Processando..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp.write(aud.getvalue())
                        tmp_path = tmp.name
                    f = genai.upload_file(tmp_path)
                    time.sleep(2) 
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(["Transcreva e resuma.", f]).text
                    st.markdown(res)
                finally: os.remove(tmp_path)

    with tab4:
        st.header("⚖️ Comparador")
        p1 = st.file_uploader("Original", type="pdf", key="v1")
        p2 = st.file_uploader("Alterado", type="pdf", key="v2")
        if p1 and p2 and st.button("Comparar"):
            with st.spinner("Comparando..."):
                t1, t2 = extrair_texto_pdf(p1), extrair_texto_pdf(p2)
                st.markdown(genai.GenerativeModel(modelo_escolhido).generate_content(f"Compare: {t1[:10000]} vs {t2[:10000]}").text)

    with tab5:
        st.header("Chat Jurídico")
        if "hist" not in st.session_state: st.session_state.hist = []
        for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
        if p := st.chat_input("Dúvida?"):
            st.chat_message("user").write(p)
            st.session_state.hist.append({"role":"user", "content":p})
            try:
                res = genai.GenerativeModel(modelo_escolhido).generate_content(p).text
            except Exception as e: res = str(e)
            st.chat_message("assistant").write(res)
            st.session_state.hist.append({"role":"assistant", "content":res})

    with tab6:
        st.header("📂 Pastas de Clientes")
        if st.button("🔄 Atualizar"): st.session_state.dados_planilha = None 
        s = conectar_planilha()
        if s:
            try:
                dados = s.get_all_records()
                df = pd.DataFrame(dados)
                if not df.empty and "Cliente" in df.columns:
                    lista = df["Cliente"].unique()
                    cliente_sel = st.selectbox("Filtrar Cliente:", ["Todos"] + list(lista))
                    df_show = df[df["Cliente"] == cliente_sel] if cliente_sel != "Todos" else df
                    st.dataframe(df_show, use_container_width=True)
                    if not df_show.empty:
                        doc_id = st.selectbox("ID:", df_show.index.tolist())
                        if st.button(f"📂 Abrir Doc {doc_id}"):
                            linha = df.loc[doc_id]
                            st.session_state.cliente_recuperado = linha["Cliente"]
                            conteudo = str(linha.iloc[-1]) 
                            st.session_state.fatos_recuperados = conteudo.split("||")[0] if "||" in conteudo else conteudo
                            st.success("Carregado no Redator!")
                else: st.warning("Planilha vazia.")
            except Exception as e: st.error(f"Erro: {e}")

    with tab7: 
        st.header("📅 Calculadora")
        c1, c2 = st.columns(2)
        with c1: dt = st.date_input("Publicação", datetime.now())
        with c2: esf = st.selectbox("Esfera", ["Cível", "Trabalhista", "Penal"])
        txt = st.text_area("Texto")
        if st.button("Calc"):
            st.write(genai.GenerativeModel(modelo_escolhido).generate_content(f"Calc prazo {esf} data {dt}: {txt}").text)

    with tab8:
        st.header("🏛️ Audiência")
        c1, c2 = st.columns(2)
        with c1: papel = st.selectbox("Papel", ["Autor", "Réu"])
        with c2: fatos = st.text_area("Fatos Caso")
        if st.button("Roteiro"):
            res = genai.GenerativeModel(modelo_escolhido).generate_content(f"Roteiro audiência para {papel}: {fatos}").text
            st.markdown(res)

    # --- ABA 9: MONITOR AUTOMÁTICO VIA E-MAIL ---
    with tab9:
        st.header("🚦 Monitor de Movimentações (Integração E-mail)")
        st.markdown("Busca automática de e-mails do Tribunal (Push/Intimações) na sua caixa de entrada.")

        # Botão de Sincronização
        c_sync1, c_sync2 = st.columns([1, 3])
        with c_sync1:
            if st.button("🔄 Buscar Intimações no E-mail"):
                if not email_leitura or not senha_leitura:
                    st.error("Configure seu e-mail e SENHA DE APP na barra lateral primeiro.")
                else:
                    with st.spinner("Conectando ao e-mail e buscando mensagens do Tribunal..."):
                        mensagens, erro = buscar_intimacoes_email(email_leitura, senha_leitura, provedor_email)
                        
                        if erro:
                            st.error(f"Erro na conexão: {erro}")
                            st.info("Dica: Use uma 'Senha de App' (não a senha normal) e ative o IMAP nas configurações do Gmail.")
                        elif not mensagens:
                            st.warning("Nenhum e-mail novo com termos 'Intimação' ou 'Processo' encontrado.")
                        else:
                            st.success(f"{len(mensagens)} movimentações encontradas!")
                            
                            # Processa cada e-mail encontrado
                            for i, msg in enumerate(mensagens):
                                st.divider()
                                st.subheader(f"📧 E-mail {i+1}: {msg['assunto']}")
                                with st.expander("Ver conteúdo do e-mail"):
                                    st.write(msg['corpo'])
                                
                                # Análise Automática da IA
                                if st.button(f"🤖 Analisar E-mail {i+1} e Calcular Prazo", key=f"btn_analise_{i}"):
                                    prompt = f"""
                                    Analise este e-mail jurídico recebido pelo advogado.
                                    Assunto: {msg['assunto']}
                                    Corpo: {msg['corpo'][:3000]}
                                    
                                    TAREFA:
                                    1. Identifique o número do processo (se houver).
                                    2. Resuma a movimentação.
                                    3. Diga se há prazo fatal e calcule a data (baseado na data de hoje: {date.today()}).
                                    
                                    SAÍDA: RESUMO | AÇÃO | DATA FATAL.
                                    """
                                    res_ia = genai.GenerativeModel(modelo_escolhido).generate_content(prompt).text
                                    st.info("Análise da IA:")
                                    st.write(res_ia)
                                    
                                    # Opção de Salvar
                                    if st.button(f"💾 Salvar E-mail {i+1} no Monitor", key=f"btn_save_{i}"):
                                        s = conectar_planilha()
                                        if s:
                                            conteudo = f"EMAIL: {msg['assunto']} | IA: {res_ia[:200]}"
                                            s.append_row([datetime.now().strftime("%d/%m"), "Auto-Email", "Monitor", "Prazo", conteudo])
                                            st.toast("Movimentação salva!", icon="✅")

        st.divider()
        st.caption("Ou insira manualmente abaixo:")
        # (Opção manual mantida caso o e-mail falhe)
        n_proc = st.text_input("Nº Processo (Manual)")
        txt_mov = st.text_area("Texto Movimentação (Manual)")
        if st.button("Analisar Manual"):
            res = genai.GenerativeModel(modelo_escolhido).generate_content(f"Analise prazo: {txt_mov}").text
            st.write(res)

else: st.warning("Insira uma chave de API para começar.")
