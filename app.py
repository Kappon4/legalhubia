import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import tempfile
import os
import pandas as pd
import plotly.express as px

# --- IMPORTAÇÃO DE ERROS ---
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument, PermissionDenied

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- 2. PAINEL LATERAL E DIAGNÓSTICO ---
st.sidebar.header("Painel de Controle")

# MOSTRA A VERSÃO DA BIBLIOTECA (ESSENCIAL PARA DEBUGAR)
versao_lib = genai.__version__
st.sidebar.caption(f"Versão do Google AI: {versao_lib}")
if versao_lib < "0.7.0":
    st.sidebar.error("⚠️ ATENÇÃO: Sua biblioteca está desatualizada. Crie o arquivo requirements.txt com 'google-generativeai>=0.7.0'")

# SELEÇÃO DA CHAVE (Permite forçar manual se a salva falhar)
uso_manual = st.sidebar.checkbox("Ignorar chave salva e digitar nova")

api_key = None
if uso_manual:
    api_key = st.sidebar.text_input("Cole sua NOVA API Key aqui:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ Chave do Sistema carregada")
else:
    api_key = st.sidebar.text_input("Cole sua API Key:", type="password")

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
            # Se não tiver senha configurada, entra direto (pra facilitar teste)
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
    
    # --- DETECÇÃO REAL DE MODELOS ---
    st.sidebar.divider()
    st.sidebar.write("🤖 Modelos Disponíveis")
    
    try:
        # Tenta listar o que a chave realmente enxerga
        modelos_reais = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                # Limpa o nome para ficar bonito no select
                modelos_reais.append(m.name)
        
        if modelos_reais:
            # Tenta selecionar o Flash automaticamente
            index_flash = 0
            for i, nome in enumerate(modelos_reais):
                if "flash" in nome and "1.5" in nome:
                    index_flash = i
                    break
            
            modelo_escolhido = st.sidebar.selectbox("Selecione:", modelos_reais, index=index_flash)
        else:
            st.sidebar.error("Sua chave API não retornou nenhum modelo. Ela pode estar vazia ou sem permissão.")
            modelo_escolhido = "models/gemini-1.5-flash" # Fallback

    except Exception as e:
        st.sidebar.error(f"Erro de conexão com Google: {e}")
        modelo_escolhido = "models/gemini-1.5-flash"

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["✍️ Redator", "📂 Ler PDF", "🎙️ Transcritor", "⚖️ Comparador", "💬 Chat", "📊 Dashboard"])
    
    # --- ABA 1: REDATOR ---
    with tab1:
        st.header("Gerador de Peças")
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato", "Parecer"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
            web = st.checkbox("Buscar Jurisprudência?", value=True)
        with c2:
            cliente = st.text_input("Cliente:")
            fatos = st.text_area("Fatos:", height=150)
        
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
                                s.append_row([datetime.now().strftime("%d/%m/%Y"), cliente, area, tipo, fatos[:50]]) 
                                st.success("Salvo!")
                                
                    except NotFound:
                        st.error(f"❌ Modelo não encontrado: {modelo_escolhido}")
                        st.info("Sua biblioteca 'google-generativeai' pode estar desatualizada. Verifique o requirements.txt.")
                    except ResourceExhausted:
                        st.error("⚠️ Limite de cota atingido.")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # --- ABA 5: CHAT ---
    with tab5:
        st.header("Chat")
        if "hist" not in st.session_state: st.session_state.hist = []
        for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
        
        if p := st.chat_input("Msg"):
            st.chat_message("user").write(p)
            st.session_state.hist.append({"role":"user", "content":p})
            
            try:
                response = genai.GenerativeModel(modelo_escolhido).generate_content(p)
                res = response.text
            except Exception as e:
                res = f"Erro: {e}"
            
            st.chat_message("assistant").write(res)
            st.session_state.hist.append({"role":"assistant", "content":res})

    # (Mantenha as outras abas iguais, simplifiquei aqui para caber)

else: st.warning("Insira uma chave de API para começar.")
