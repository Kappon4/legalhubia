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

# 4. LÓGICA PRINCIPAL
if api_key:
    genai.configure(api_key=api_key)
    
    # --- MEMÓRIA DE EDIÇÃO (NOVO!) ---
    if "fatos_recuperados" not in st.session_state: st.session_state.fatos_recuperados = ""
    if "cliente_recuperado" not in st.session_state: st.session_state.cliente_recuperado = ""

    # --- DETECÇÃO REAL DE MODELOS (MANTIDO COMO VOCÊ GOSTA) ---
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
            st.sidebar.error("Sem modelos disponíveis.")
            modelo_escolhido = "models/gemini-1.5-flash" 
    except Exception as e:
        st.sidebar.error(f"Erro Google: {e}")
        modelo_escolhido = "models/gemini-1.5-flash"

    # --- DEFINIÇÃO DAS ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📂 Pastas", "📅 Calc", "🏛️ Audiência", "🚦 Monitor"
    ])
    
    # --- ABA 1: REDATOR (ATUALIZADA COM MEMÓRIA) ---
    with tab1:
        st.header("Gerador de Peças")
        
        # Botão para limpar a tela
        if st.button("🔄 Limpar Campos / Novo Caso"):
            st.session_state.fatos_recuperados = ""
            st.session_state.cliente_recuperado = ""
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Peça", ["Inicial", "Contestação", "Recurso", "Contrato", "Parecer"])
            area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Família", "Tributário"])
            web = st.checkbox("Buscar Jurisprudência?", value=True)
        with c2:
            # Campos conectados à memória da sessão
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
                                # Salva o conteúdo completo para poder recuperar depois
                                conteudo_backup = fatos + " || " + res[:500] 
                                s.append_row([
                                    datetime.now().strftime("%d/%m/%Y"), 
                                    cliente, 
                                    area, 
                                    tipo, 
                                    conteudo_backup # Salva aqui para recuperar
                                ]) 
                                st.success("Salvo na Pasta do Cliente!")
                    except Exception as e: st.error(f"Erro: {e}")

    # --- ABA 2 a 5 (MANTIDAS) ---
    with tab2: 
        st.header("Análise de Processos (PDF)")
        up = st.file_uploader("Subir PDF", type="pdf")
        if up and st.button("Resumir PDF"): 
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

    # --- ABA 6: PASTAS INTELIGENTES (ATUALIZADA) ---
    with tab6:
        st.header("📂 Pastas de Clientes (GED)")
        
        if st.button("🔄 Atualizar Lista"):
            st.session_state.dados_planilha = None 

        s = conectar_planilha()
        if s:
            try:
                dados = s.get_all_records()
                df = pd.DataFrame(dados)
                
                if not df.empty:
                    # Métricas
                    c_d1, c_d2 = st.columns(2)
                    c_d1.metric("Arquivos", len(df))
                    lista_clientes = df["Cliente"].unique() if "Cliente" in df.columns else []
                    
                    # Filtros
                    st.divider()
                    st.subheader("🔍 Localizar Arquivo")
                    
                    if "Cliente" in df.columns:
                        cliente_selecionado = st.selectbox("Filtrar por Cliente:", ["Todos"] + list(lista_clientes))
                        
                        if cliente_selecionado != "Todos":
                            df_filtrado = df[df["Cliente"] == cliente_selecionado]
                        else:
                            df_filtrado = df
                        
                        st.dataframe(df_filtrado, use_container_width=True)
                        
                        # RECUPERAÇÃO DE TRABALHO
                        st.info("Para editar um arquivo antigo, selecione o ID (número da linha) abaixo:")
                        if not df_filtrado.empty:
                            opcoes_docs = df_filtrado.index.tolist()
                            doc_id = st.selectbox("ID do Documento:", opcoes_docs)
                            
                            if st.button(f"📂 Abrir Documento {doc_id} no Redator"):
                                linha_dados = df.loc[doc_id]
                                st.session_state.cliente_recuperado = linha_dados["Cliente"]
                                
                                # Tenta pegar o texto. Se salvamos na coluna 5 (índice 4 ou nome 'Resumo')
                                colunas = list(df.columns)
                                # Pega a última coluna onde salvamos o backup
                                conteudo = str(linha_dados.iloc[-1]) 
                                
                                # Limpa o separador se existir
                                if "||" in conteudo:
                                    st.session_state.fatos_recuperados = conteudo.split("||")[0]
                                else:
                                    st.session_state.fatos_recuperados = conteudo
                                
                                st.success("Carregado! Vá para a aba '✍️ Redator'.")
                    else:
                        st.warning("Coluna 'Cliente' não encontrada na planilha.")
            except Exception as e:
                st.error(f"Erro na planilha: {e}")

    # --- ABA 7 E 8 (MANTIDAS) ---
    with tab7: 
        st.header("📅 Calculadora de Prazos")
        st.info("Sugestão IA. Confira feriados.")
        c_p1, c_p2 = st.columns(2)
        with c_p1: data_pub = st.date_input("Data Publicação", datetime.now())
        with c_p2: esfera = st.selectbox("Esfera", ["Cível (CPC)", "Trabalhista", "Penal", "Juizado"])
        texto_prazo = st.text_area("Texto Intimação:")

        if st.button("Calcular"):
            with st.spinner("Calculando..."):
                prompt_prazo = f"Assistente jurídico. {esfera}. Data: {data_pub}. Texto: {texto_prazo}. Identifique prazo, úteis/corridos e data fatal."
                try:
                    st.markdown(genai.GenerativeModel(modelo_escolhido).generate_content(prompt_prazo).text)
                except Exception as e: st.error(str(e))

    with tab8:
        st.header("🏛️ Preparador de Audiência")
        c_a1, c_a2 = st.columns(2)
        with c_a1: 
            papel = st.selectbox("Representa:", ["Autor", "Réu"])
            tipo_aud = st.selectbox("Tipo:", ["Instrução", "Conciliação", "UNA"])
        with c_a2: fatos_aud = st.text_area("Fatos:")
        
        if st.button("Gerar Roteiro"):
            with st.spinner("Gerando..."):
                prompt_aud = f"Roteiro audiência {tipo_aud} para {papel}. Fatos: {fatos_aud}. Perguntas, riscos e estratégia."
                try:
                    res_aud = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_aud).text
                    st.markdown(res_aud)
                    st.download_button("Baixar", gerar_word(res_aud), "roteiro.docx")
                except Exception as e: st.error(str(e))

    # --- ABA 9: MONITOR DE PRAZOS (MANTIDA) ---
    with tab9:
        st.header("🚦 Monitor de Movimentações e Prazos")
        st.markdown("Cole a movimentação para análise.")

        col_mov1, col_mov2, col_mov3 = st.columns(3)
        with col_mov1: n_processo = st.text_input("Nº Processo")
        with col_mov2: data_mov = st.date_input("Data Mov.", datetime.now())
        with col_mov3: tipo_prazo = st.selectbox("Contagem", ["Dias Úteis", "Corridos", "CLT"])

        texto_movimentacao = st.text_area("Movimentação:", height=150)

        if "analise_prazo" not in st.session_state: st.session_state.analise_prazo = None

        if st.button("🔍 Analisar"):
            if texto_movimentacao:
                with st.spinner("Analisando..."):
                    prompt_monitor = f"""
                    Analise movimentação jurídica. Base: {data_mov}. Tipo: {tipo_prazo}. Texto: "{texto_movimentacao}"
                    SAÍDA: RESUMO, AÇÃO REQUERIDA, TEM PRAZO?, DIAS, DATA FATAL.
                    """
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_monitor).text
                        st.session_state.analise_prazo = res
                    except Exception as e: st.error(f"Erro: {e}")

        if st.session_state.analise_prazo:
            st.divider()
            st.markdown(st.session_state.analise_prazo)
            
            st.divider()
            st.subheader("⏱️ Contador")
            c1, c2 = st.columns(2)
            with c1: data_fatal_input = st.date_input("Data Fatal:", datetime.now() + timedelta(days=15))
            with c2:
                dias_restantes = (data_fatal_input - date.today()).days
                if dias_restantes < 0: st.error(f"VENCIDO HÁ {abs(dias_restantes)} DIAS!")
                elif dias_restantes <= 3: st.warning(f"Faltam {dias_restantes} dias.")
                else: st.success(f"Faltam {dias_restantes} dias.")

            if st.button("💾 Salvar Monitoramento"):
                s = conectar_planilha()
                if s:
                    conteudo = f"MOV: {texto_movimentacao[:30]} | FATAL: {data_fatal_input}"
                    s.append_row([datetime.now().strftime("%d/%m"), n_processo, "Monitor", "Prazo", conteudo])
                    st.toast("Salvo!", icon="💾")

else: st.warning("Insira uma chave de API para começar.")
