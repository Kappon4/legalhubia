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

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")

# --- 🔐 SISTEMA DE LOGIN (NOVO) ---
def check_password():
    """Retorna True se o usuário logou corretamente."""
    if "logado" not in st.session_state:
        st.session_state.logado = False

    if st.session_state.logado:
        return True

    # Tela de Login
    st.markdown("## 🔒 Acesso Restrito - LegalHub")
    senha = st.text_input("Digite a senha de acesso:", type="password")
    
    if st.button("Entrar"):
        # Verifica se a senha bate com a que está nos Secrets
        if senha == st.secrets["SENHA_ACESSO"]:
            st.session_state.logado = True
            st.rerun() # Recarrega a página para entrar
        else:
            st.error("Senha incorreta.")
    return False

# Se não estiver logado, para o código aqui.
if not check_password():
    st.stop()
# ----------------------------------

st.title("⚖️ LegalHub IA (Sistema Seguro)")

# 2. SEGURANÇA E CONEXÕES
st.sidebar.header("Painel de Controle")
if st.sidebar.button("Sair (Logout)"):
    st.session_state.logado = False
    st.rerun()

# A) Conexão Google Gemini
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ IA: Conectada")
else:
    api_key = st.sidebar.text_input("Chave API Google:", type="password")

# B) Conexão Planilha Google
def conectar_planilha():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Substitua pelo nome EXATO da sua planilha
        sheet = client.open("Casos Juridicos - LegalHub").sheet1 
        return sheet
    except Exception as e:
        st.sidebar.error(f"Erro Planilha: {e}")
        return None

# 3. FUNÇÕES INTELIGENTES
def descobrir_modelos():
    try:
        modelos = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos.append(m.name)
        return modelos
    except:
        return []

def buscar_jurisprudencia_real(tema, qtd=5):
    try:
        query = f"{tema} (ementa OR acordao OR jurisprudencia) (site:stf.jus.br OR site:stj.jus.br OR site:jusbrasil.com.br)"
        results = DDGS().text(query, region="br-pt", max_results=qtd)
        if not results: return "Nenhuma jurisprudência encontrada."
        
        texto = ""
        for i, r in enumerate(results):
            texto += f"\n--- FONTE {i+1} ({r['title']}) ---\nLink: {r['href']}\nResumo: {r['body']}\n"
        return texto
    except: return "Erro na busca."

def gerar_word(texto):
    doc = Document()
    for p in texto.split('\n'):
        if p.strip(): doc.add_paragraph(p)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def extrair_texto_pdf(arquivo):
    try:
        return "".join([p.extract_text() for p in PdfReader(arquivo).pages])
    except: return None

# 4. LÓGICA PRINCIPAL
if api_key:
    genai.configure(api_key=api_key)
    modelos = descobrir_modelos()
    
    if modelos:
        modelo_atual = st.sidebar.selectbox("Modelo:", modelos, index=0)
        
        tab1, tab2, tab3, tab4 = st.tabs(["✍️ Redator", "📂 Ler PDF", "💬 Chat", "🗄️ Meus Casos"])
        
        # --- ABA 1: REDATOR ---
        with tab1:
            st.header("Gerador de Peças")
            c1, c2 = st.columns(2)
            with c1:
                tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Habeas Corpus", "Contrato"])
                area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
                web = st.checkbox("Buscar Jurisprudência?", value=True)
            with c2:
                cliente = st.text_input("Nome do Cliente:")
                fatos = st.text_area("Fatos:", height=150)
            
            if st.button("✨ Gerar e Salvar"):
                if not fatos:
                    st.warning("Preencha os fatos.")
                else:
                    with st.spinner("Gerando..."):
                        jurisp = ""
                        if web:
                            jurisp = buscar_jurisprudencia_real(f"{area} {tipo} {fatos}")
                        
                        model = genai.GenerativeModel(modelo_atual)
                        prompt = f"Advogado {area}. Peça: {tipo}. Fatos: {fatos}. Jurisprudência: {jurisp}."
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                        
                        st.download_button("Baixar Word", gerar_word(res.text), "minuta.docx")
                        
                        if cliente:
                            sheet = conectar_planilha()
                            if sheet:
                                data_hoje = datetime.now().strftime("%d/%m/%Y")
                                try:
                                    sheet.append_row([data_hoje, cliente, tipo, fatos[:100]+"..."])
                                    st.success(f"✅ Salvo na planilha!")
                                except:
                                    st.warning("Erro ao salvar (verifique permissões).")

        # --- ABA 2: PDF ---
        with tab2:
            st.header("PDF")
            up = st.file_uploader("PDF", type="pdf")
            if up:
                txt = extrair_texto_pdf(up)
                if st.button("Resumir"): 
                    st.write(genai.GenerativeModel(modelo_atual).generate_content(f"Resuma: {txt}").text)

        # --- ABA 3: CHAT ---
        with tab3:
            st.header("Chat")
            if "hist" not in st.session_state: st.session_state.hist = []
            for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
            if p := st.chat_input("Msg"):
                st.chat_message("user").write(p)
                st.session_state.hist.append({"role":"user", "content":p})
                res = genai.GenerativeModel(modelo_atual).generate_content(p).text
                st.chat_message("assistant").write(res)
                st.session_state.hist.append({"role":"assistant", "content":res})

        # --- ABA 4: BANCO DE DADOS ---
        with tab4:
            st.header("🗄️ Banco de Casos")
            if st.button("🔄 Atualizar Lista"):
                sheet = conectar_planilha()
                if sheet:
                    try:
                        dados = sheet.get_all_records()
                        st.dataframe(dados)
                    except:
                        st.info("Planilha vazia ou erro de leitura.")

else:
    st.warning("Configure as Chaves de API.")
