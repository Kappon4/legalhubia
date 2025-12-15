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

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- 🔐 SISTEMA DE LOGIN ---
def check_password():
    if "logado" not in st.session_state:
        st.session_state.logado = False
    if st.session_state.logado: return True
    
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

st.title("⚖️ LegalHub IA (Sistema Seguro)")

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

# 3. FUNÇÕES
def descobrir_modelos():
    try: return [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except: return []

def buscar_jurisprudencia_real(tema):
    try:
        res = DDGS().text(f"{tema} (site:stf.jus.br OR site:stj.jus.br OR site:jusbrasil.com.br)", region="br-pt", max_results=5)
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
        
        # AGORA SÃO 6 ABAS (Adicionei o "Comparador")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["✍️ Redator", "📂 Ler PDF", "🎙️ Transcritor", "⚖️ Comparador (Novo)", "💬 Chat", "🗄️ Casos"])
        
        # --- ABA 1: REDATOR ---
        with tab1:
            st.header("Gerador de Peças")
            c1, c2 = st.columns(2)
            with c1:
                tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato"])
                area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família"])
                web = st.checkbox("Buscar Jurisprudência?", value=True)
            with c2:
                cliente = st.text_input("Cliente:")
                fatos = st.text_area("Fatos:", height=150)
            
            if st.button("✨ Gerar"):
                if fatos:
                    with st.spinner("Gerando..."):
                        jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}") if web else ""
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}.").text
                        st.markdown(res)
                        st.download_button("Baixar Word", gerar_word(res), "minuta.docx")
                        if cliente:
                            sheet = conectar_planilha()
                            if sheet: sheet.append_row([datetime.now().strftime("%d/%m/%Y"), cliente, tipo, fatos[:50]])

        # --- ABA 2: PDF ---
        with tab2:
            st.header("Análise de PDF")
            up = st.file_uploader("Subir PDF", type="pdf")
            if up:
                if st.button("Resumir"): st.write(genai.GenerativeModel(modelo_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)}").text)

        # --- ABA 3: TRANSCRITOR ---
        with tab3:
            st.header("🎙️ Transcrição de Áudio")
            aud = st.file_uploader("Áudio", type=["mp3", "wav", "m4a"])
            if aud and st.button("Transcrever"):
                with st.spinner("Ouvindo..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp.write(aud.getvalue())
                        tmp_path = tmp.name
                    f = genai.upload_file(tmp_path)
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(["Transcreva e resuma este áudio jurídico.", f]).text
                    os.remove(tmp_path)
                    st.markdown(res)
                    st.download_button("Baixar", gerar_word(res), "transcricao.docx")

        # --- ABA 4: COMPARADOR (NOVO!) ---
        with tab4:
            st.header("⚖️ Comparador de Contratos/Documentos")
            st.info("Suba dois arquivos para ver o que mudou entre eles.")
            
            col_a, col_b = st.columns(2)
            pdf1 = col_a.file_uploader("Versão Original (Antiga)", type="pdf", key="v1")
            pdf2 = col_b.file_uploader("Versão Alterada (Nova)", type="pdf", key="v2")
            
            if pdf1 and pdf2:
                if st.button("🔍 Comparar Documentos"):
                    with st.spinner("A IA está lendo e comparando cláusula por cláusula..."):
                        txt1 = extrair_texto_pdf(pdf1)
                        txt2 = extrair_texto_pdf(pdf2)
                        
                        prompt_comparacao = f"""
                        Atue como um perito em análise contratual. Compare os dois textos abaixo.
                        
                        TEXTO ORIGINAL:
                        {txt1}
                        
                        TEXTO ALTERADO:
                        {txt2}
                        
                        TAREFA:
                        1. Liste O QUE mudou (cláusulas removidas, adicionadas ou valores alterados).
                        2. Analise se essas mudanças trazem RISCO para a parte contratante.
                        3. Seja direto e aponte as pegadinhas.
                        """
                        
                        modelo = genai.GenerativeModel(modelo_escolhido)
                        resultado = modelo.generate_content(prompt_comparacao).text
                        
                        st.subheader("Relatório de Divergências")
                        st.markdown(resultado)
                        st.download_button("📥 Baixar Relatório (.docx)", gerar_word(resultado), "comparacao.docx")

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

        # --- ABA 6: CASOS ---
        with tab6:
            st.header("🗄️ Casos")
            if st.button("Atualizar"):
                s = conectar_planilha()
                if s: st.dataframe(s.get_all_records())

else: st.warning("Configure as Chaves de API.")
