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
    modelos = descobrir_modelos()
    
    if modelos:
        modelo_escolhido = st.sidebar.selectbox("Modelo:", modelos, index=0)
        
        # DEFINIÇÃO DAS ABAS
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "✍️ Redator", 
            "📂 Ler PDF", 
            "🎙️ Transcritor", 
            "⚖️ Comparador", 
            "💬 Chat", 
            "📊 Dashboard (Novo)"
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
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt).text
                        st.markdown(res)
                        st.download_button("Baixar Word", gerar_word(res), "minuta.docx")
                        
                        # Salvar no Banco
                        if cliente:
                            s = conectar_planilha()
                            if s: 
                                s.append_row([datetime.now().strftime("%d/%m/%Y"), cliente, area, tipo, fatos[:50]]) # Ordem ajustada: Data, Cliente, Area, Tipo
                                st.success("✅ Caso salvo no Dashboard!")

        # --- ABA 2: PDF ---
        with tab2:
            st.header("Análise de Processos")
            up = st.file_uploader("Subir PDF", type="pdf")
            if up:
                if st.button("Resumir"): st.write(genai.GenerativeModel(modelo_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)}").text)

        # --- ABA 3: TRANSCRITOR ---
        with tab3:
            st.header("🎙️ Transcrição")
            aud = st.file_uploader("Áudio", type=["mp3", "wav", "m4a"])
            if aud and st.button("Transcrever"):
                with st.spinner("Ouvindo..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp.write(aud.getvalue())
                        tmp_path = tmp.name
                    f = genai.upload_file(tmp_path)
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(["Transcreva e resuma.", f]).text
                    os.remove(tmp_path)
                    st.markdown(res)
                    st.download_button("Baixar", gerar_word(res), "transcricao.docx")

        # --- ABA 4: COMPARADOR ---
        with tab4:
            st.header("⚖️ Comparador")
            c_a, c_b = st.columns(2)
            p1 = c_a.file_uploader("Original", type="pdf", key="v1")
            p2 = c_b.file_uploader("Alterado", type="pdf", key="v2")
            if p1 and p2 and st.button("Comparar"):
                with st.spinner("Comparando..."):
                    t1, t2 = extrair_texto_pdf(p1), extrair_texto_pdf(p2)
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(f"Compare os textos. Diferenças e Riscos:\nTexto 1: {t1}\nTexto 2: {t2}").text
                    st.markdown(res)

        # --- ABA 5: CHAT ---
        with tab5:
            st.header("Chat")
            if "hist" not in st.session_state: st.session_state.hist = []
            for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
            if p := st.chat_input("Msg"):
                st.chat_message("user").write(p)
                st.session_state.hist.append({"role":"user", "content":p})
                res = genai.GenerativeModel(modelo_escolhido).generate_content(p).text
                st.chat_message("assistant").write(res)
                st.session_state.hist.append({"role":"assistant", "content":res})

        # --- ABA 6: DASHBOARD (NOVO!) ---
        with tab6:
            st.header("📊 Dashboard do Escritório")
            
            if st.button("🔄 Atualizar Dados"):
                sheet = conectar_planilha()
                if sheet:
                    try:
                        # Pega todos os dados da planilha
                        dados = sheet.get_all_records()
                        df = pd.DataFrame(dados)
                        
                        if not df.empty:
                            # Métricas no Topo
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Total de Casos", len(df))
                            m2.metric("Último Cliente", df.iloc[-1]["Cliente"] if "Cliente" in df.columns else "N/A")
                            m3.metric("Área Mais Ativa", df["Tipo de Ação"].mode()[0] if "Tipo de Ação" in df.columns else "N/A")
                            
                            st.divider()
                            
                            # Gráficos Lado a Lado
                            g1, g2 = st.columns(2)
                            
                            # Gráfico de Pizza (Áreas ou Tipos)
                            if "Tipo de Ação" in df.columns:
                                fig_pizza = px.pie(df, names="Tipo de Ação", title="Distribuição por Tipo de Peça")
                                g1.plotly_chart(fig_pizza, use_container_width=True)
                            
                            # Gráfico de Barras (Clientes)
                            if "Cliente" in df.columns:
                                contagem_clientes = df["Cliente"].value_counts().reset_index()
                                contagem_clientes.columns = ["Cliente", "Qtd"]
                                fig_barras = px.bar(contagem_clientes, x="Cliente", y="Qtd", title="Processos por Cliente")
                                g2.plotly_chart(fig_barras, use_container_width=True)
                            
                            st.divider()
                            st.subheader("Base de Dados Completa")
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("A planilha está vazia. Gere algumas peças na aba 'Redator' para alimentar o gráfico!")
                            
                    except Exception as e:
                        st.error(f"Erro ao ler dados: {e}")
                        st.info("Dica: Verifique se o cabeçalho da sua planilha no Google Sheets está exatamente assim: Data | Cliente | Tipo de Ação | Resumo")

else: st.warning("Configure as Chaves de API.")
