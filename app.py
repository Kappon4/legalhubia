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

# --- IMPORTAÇÃO DE ERROS (ATUALIZADA) ---
# Adicionei 'NotFound' e 'InvalidArgument' para cobrir o erro novo
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- 🔐 SISTEMA DE LOGIN ---
def check_password():
    if "logado" not in st.session_state: st.session_state.logado = False
    if st.session_state.logado: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔒 Acesso Restrito - LegalHub")
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar"):
            if senha == st.secrets["SENHA_ACESSO"]:
                st.session_state.logado = True
                st.rerun()
            else: st.error("Senha incorreta.")
    return False

if not check_password(): st.stop()
# ---------------------------

st.title("⚖️ LegalHub IA (Gestão & Inteligência)")

# 2. CONEXÕES
st.sidebar.header("Painel de Controle")
if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.rerun()

# API Gemini
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ IA: Conectada")
else: api_key = st.sidebar.text_input("Chave API Google:", type="password")

# Planilha
def conectar_planilha():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open("Casos Juridicos - LegalHub").sheet1 
    except Exception as e: return None

# 3. FUNÇÕES UTILITÁRIAS
def descobrir_modelos():
    try: return [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except: return []

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
    
    # Seletor de Modelo
    # ATENÇÃO: Se o gemini-2.5 der erro de novo, MUDAR A SELEÇÃO PARA O 1.5 NO SITE
    modelo_escolhido = st.sidebar.selectbox(
        "Escolha o Modelo", 
        ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"],
        index=0 
    )
    
    # DEFINIÇÃO DAS ABAS
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "✍️ Redator", 
        "📂 Ler PDF", 
        "🎙️ Transcritor", 
        "⚖️ Comparador", 
        "💬 Chat", 
        "📊 Dashboard"
    ])
    
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
                with st.spinner("Pesquisando e Redigindo..."):
                    jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                    prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}. Estruture formalmente."
                    
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt).text
                        st.markdown(res)
                        st.download_button("Baixar Word", gerar_word(res), "minuta.docx")
                        
                        # Salvar no Banco
                        if cliente:
                            s = conectar_planilha()
                            if s: 
                                s.append_row([datetime.now().strftime("%d/%m/%Y"), cliente
