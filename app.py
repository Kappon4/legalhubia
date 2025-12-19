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

# --- NOVA FUNÇÃO: GERADOR DE ARQUIVO DE AGENDA (.ICS) ---
def criar_ics_calendario(processo, data_fatal, descricao):
    # Formata datas para o padrão universal de calendário (YYYYMMDD)
    dt_inicio = data_fatal.strftime('%Y%m%d')
    # Evento de dia inteiro termina no dia seguinte
    dt_fim = (data_fatal + timedelta(days=1)).strftime('%Y%m%d')
    
    # Conteúdo do arquivo .ics (Padrão Outlook/Google/Apple)
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//LegalHub//Monitor Prazos//PT
BEGIN:VEVENT
SUMMARY:🚨 PRAZO FATAL: Proc. {processo}
DTSTART;VALUE=DATE:{dt_inicio}
DTEND;VALUE=DATE:{dt_fim}
DESCRIPTION:{descricao}
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-P1D
DESCRIPTION:Lembrete LegalHub - Prazo Vence Amanhã
ACTION:DISPLAY
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics_content

# 4. LÓGICA PRINCIPAL
if api_key:
    genai.configure(api_key=api_key)
    
    # MEMÓRIA
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    # DETECÇÃO DE MODELOS
    st.sidebar.divider()
    try:
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
            st.sidebar.error("Sem modelos.")
            modelo_escolhido = "models/gemini-1.5-flash" 
    except Exception as e:
        st.sidebar.error(f"Erro Google: {e}")
        modelo_escolhido = "models/gemini-1.5-flash"

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas", "📅 Calc", "🏛️ Audiência", "🚦 Monitor"
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

    # --- ABA 2 a 5 (PADRÃO) ---
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

    # --- ABA 6: PASTAS (GED) ---
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
                    
                    st.info("Recuperar documento:")
                    if not df_show.empty:
                        doc_id = st.selectbox("ID:", df_show.index.tolist())
                        if st.button(f"📂 Abrir Doc {doc_id}"):
                            linha = df.loc[doc_id]
                            st.session_state.cliente_recuperado = linha["Cliente"]
                            conteudo = str(linha.iloc[-1]) 
                            st.session_state.fatos_recuperados = conteudo.split("||")[0] if "||" in conteudo else conteudo
                            st.success("Carregado no Redator!")
                else: st.warning("Planilha vazia ou sem coluna 'Cliente'.")
            except Exception as e: st.error(f"Erro: {e}")

    # --- ABA 7 E 8 ---
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

    # --- ABA 9: MONITOR (COM CALENDÁRIO!) ---
    with tab9:
        st.header("🚦 Monitor de Prazos & Agenda")
        st.markdown("Cole a movimentação para análise e agendamento.")

        col1, col2, col3 = st.columns(3)
        with col1: n_proc = st.text_input("Nº Processo")
        with col2: data_mov = st.date_input("Data Mov.", datetime.now())
        with col3: tipo_prazo = st.selectbox("Contagem", ["Dias Úteis", "Corridos", "CLT"])

        texto_movimentacao = st.text_area("Movimentação:", height=150)

        if "analise_prazo" not in st.session_state: st.session_state.analise_prazo = None

        if st.button("🔍 Analisar Movimentação"):
            if texto_movimentacao:
                with st.spinner("Analisando..."):
                    prompt = f"""
                    Analise movimentação jurídica. Base: {data_mov}. Tipo: {tipo_prazo}. Texto: "{texto_movimentacao}"
                    SAÍDA: RESUMO, AÇÃO REQUERIDA, TEM PRAZO?, DIAS, DATA FATAL SUGERIDA.
                    """
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt).text
                        st.session_state.analise_prazo = res
                    except Exception as e: st.error(f"Erro: {e}")

        if st.session_state.analise_prazo:
            st.divider()
            st.markdown(st.session_state.analise_prazo)
            
            st.divider()
            st.subheader("⏱️ Ações")
            c_a, c_b = st.columns(2)
            with c_a: 
                data_fatal_input = st.date_input("Data Fatal:", datetime.now() + timedelta(days=15))
                # --- BOTÃO DE CALENDÁRIO AQUI ---
                arquivo_ics = criar_ics_calendario(n_proc, data_fatal_input, texto_movimentacao[:200])
                st.download_button(
                    label="📅 Baixar Agendamento (Outlook/Google)",
                    data=arquivo_ics,
                    file_name=f"prazo_{n_proc}.ics",
                    mime="text/calendar"
                )

            with c_b:
                dias = (data_fatal_input - date.today()).days
                if dias < 0: st.error(f"VENCIDO HÁ {abs(dias)} DIAS!")
                elif dias <= 3: st.warning(f"Faltam {dias} dias.")
                else: st.success(f"Faltam {dias} dias.")
                
                if st.button("💾 Salvar na Planilha"):
                    s = conectar_planilha()
                    if s:
                        conteudo = f"MOV: {texto_movimentacao[:30]}... | FATAL: {data_fatal_input}"
                        s.append_row([datetime.now().strftime("%d/%m"), n_proc, "Monitor", "Prazo", conteudo])
                        st.toast("Salvo!", icon="💾")

else: st.warning("Insira uma chave de API para começar.")
