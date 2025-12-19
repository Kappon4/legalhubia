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

# Diagnóstico de Versão
versao_lib = genai.__version__
st.sidebar.caption(f"Versão da Lib: {versao_lib}")
if versao_lib < "0.7.0":
    st.sidebar.error("⚠️ Lib desatualizada. Atualize o requirements.txt")

# Seleção de Chave
uso_manual = st.sidebar.checkbox("Usar chave manual", value=False)
api_key = None

if uso_manual:
    api_key = st.sidebar.text_input("Cole sua NOVA API Key:", type="password")
elif "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ Chave do Sistema")
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
            # Se não tiver senha configurada, entra direto (pra facilitar)
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
    
    try:
        # Tenta listar o que a chave realmente enxerga
        modelos_reais = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_reais.append(m.name)
        
        if modelos_reais:
            index_flash = 0
            for i, nome in enumerate(modelos_reais):
                if "flash" in nome and "1.5" in nome:
                    index_flash = i
                    break
            modelo_escolhido = st.sidebar.selectbox("Modelo:", modelos_reais, index=index_flash)
        else:
            st.sidebar.error("Sem modelos disponíveis.")
            modelo_escolhido = "models/gemini-1.5-flash" # Fallback

    except Exception as e:
        st.sidebar.error(f"Erro Google: {e}")
        modelo_escolhido = "models/gemini-1.5-flash"

    # --- ABAS (CÓDIGO COMPLETO RESTAURADO) ---
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
                                
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # --- ABA 2: LER PDF ---
    with tab2:
        st.header("Análise de Processos (PDF)")
        up = st.file_uploader("Subir PDF", type="pdf")
        if up:
            if st.button("Resumir PDF"): 
                with st.spinner("Lendo documento..."):
                    try:
                        texto_pdf = extrair_texto_pdf(up)
                        prompt_pdf = f"Resuma os pontos principais e prazos deste documento jurídico: {texto_pdf[:30000]}" # Limite de caracteres para segurança
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_pdf).text
                        st.markdown(res)
                    except Exception as e: st.error(f"Erro: {e}")

    # --- ABA 3: TRANSCRITOR ---
    with tab3:
        st.header("🎙️ Transcrição de Áudio")
        aud = st.file_uploader("Áudio", type=["mp3", "wav", "m4a", "ogg"])
        if aud and st.button("Transcrever"):
            with st.spinner("Ouvindo e transcrevendo..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp.write(aud.getvalue())
                        tmp_path = tmp.name
                    
                    f = genai.upload_file(tmp_path)
                    
                    # Espera processar (o Google precisa de um tempo para o arquivo ficar 'ACTIVE')
                    time.sleep(2) 
                    
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(["Transcreva o áudio e faça um resumo jurídico.", f]).text
                    st.markdown(res)
                    st.download_button("Baixar", gerar_word(res), "transcricao.docx")
                except Exception as e: st.error(f"Erro: {e}")
                finally: 
                    if 'tmp_path' in locals(): os.remove(tmp_path)

    # --- ABA 4: COMPARADOR ---
    with tab4:
        st.header("⚖️ Comparador de Versões")
        st.info("Compare dois PDFs para achar diferenças (ex: contrato original vs alterado).")
        c_a, c_b = st.columns(2)
        p1 = c_a.file_uploader("Original", type="pdf", key="v1")
        p2 = c_b.file_uploader("Alterado", type="pdf", key="v2")
        
        if p1 and p2 and st.button("Comparar Documentos"):
            with st.spinner("Comparando..."):
                try:
                    t1, t2 = extrair_texto_pdf(p1), extrair_texto_pdf(p2)
                    prompt_comparacao = f"Compare os textos. Liste as alterações, supressões e riscos jurídicos criados:\nTexto 1: {t1[:15000]}\nTexto 2: {t2[:15000]}"
                    res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_comparacao).text
                    st.markdown(res)
                except Exception as e: st.error(f"Erro: {e}")

    # --- ABA 5: CHAT ---
    with tab5:
        st.header("Chat Jurídico")
        if "hist" not in st.session_state: st.session_state.hist = []
        for m in st.session_state.hist: st.chat_message(m["role"]).write(m["content"])
        
        if p := st.chat_input("Tire suas dúvidas..."):
            st.chat_message("user").write(p)
            st.session_state.hist.append({"role":"user", "content":p})
            
            try:
                response = genai.GenerativeModel(modelo_escolhido).generate_content(p)
                res = response.text
            except Exception as e:
                res = f"Erro: {e}"
            
            st.chat_message("assistant").write(res)
            st.session_state.hist.append({"role":"assistant", "content":res})

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("📊 Dashboard do Escritório")
        if st.button("🔄 Atualizar Dados"):
            sheet = conectar_planilha()
            if sheet:
                try:
                    dados = sheet.get_all_records()
                    df = pd.DataFrame(dados)
                    if not df.empty:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Total de Casos", len(df))
                        m2.metric("Último Cliente", df.iloc[-1]["Cliente"] if "Cliente" in df.columns else "N/A")
                        
                        st.divider()
                        g1, g2 = st.columns(2)
                        if "Tipo de Ação" in df.columns:
                            fig_pizza = px.pie(df, names="Tipo de Ação", title="Distribuição")
                            g1.plotly_chart(fig_pizza, use_container_width=True)
                        if "Cliente" in df.columns:
                            contagem = df["Cliente"].value_counts().reset_index()
                            contagem.columns = ["Cliente", "Qtd"]
                            fig_barras = px.bar(contagem, x="Cliente", y="Qtd", title="Clientes")
                            g2.plotly_chart(fig_barras, use_container_width=True)
                        st.dataframe(df, use_container_width=True)
                    else: st.info("Planilha vazia ou cabeçalhos incorretos.")
                except Exception as e: st.error(f"Erro ao ler planilha: {e}")
            else:
                st.warning("Planilha não conectada. Verifique as credenciais.")

else: st.warning("Insira uma chave de API para começar.")
