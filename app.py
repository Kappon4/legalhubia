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
    
    # --- DETECÇÃO REAL DE MODELOS ---
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

    # --- DEFINIÇÃO DAS ABAS (AGORA SÃO 9) ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "✍️ Redator", "📂 PDF", "🎙️ Áudio", "⚖️ Comparar", "💬 Chat", "📊 Dash", "📅 Calc", "🏛️ Audiência", "🚦 Monitor de Prazos"
    ])
    
    # --- ABA 1 a 8 (CÓDIGO ANTERIOR MANTIDO) ---
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
                    except Exception as e: st.error(f"Erro: {e}")

    with tab2: # PDF
        st.header("Análise de Processos (PDF)")
        up = st.file_uploader("Subir PDF", type="pdf")
        if up and st.button("Resumir PDF"): 
             with st.spinner("Lendo..."):
                st.write(genai.GenerativeModel(modelo_escolhido).generate_content(f"Resuma: {extrair_texto_pdf(up)[:30000]}").text)

    with tab3: # Transcritor
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

    with tab4: # Comparador
        st.header("⚖️ Comparador")
        p1 = st.file_uploader("Original", type="pdf", key="v1")
        p2 = st.file_uploader("Alterado", type="pdf", key="v2")
        if p1 and p2 and st.button("Comparar"):
            with st.spinner("Comparando..."):
                t1, t2 = extrair_texto_pdf(p1), extrair_texto_pdf(p2)
                st.markdown(genai.GenerativeModel(modelo_escolhido).generate_content(f"Compare: {t1[:10000]} vs {t2[:10000]}").text)

    with tab5: # Chat
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

    with tab6: # Dashboard
        st.header("📊 Dashboard")
        if st.button("Atualizar"):
            s = conectar_planilha()
            if s:
                df = pd.DataFrame(s.get_all_records())
                if not df.empty:
                    st.dataframe(df)
                    st.metric("Total Casos", len(df))

    with tab7: # Calculadora
        st.header("📅 Calculadora de Prazos")
        st.info("⚠️ Sugestão baseada em IA. Sempre confira feriados locais.")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            data_pub = st.date_input("Data da Publicação", datetime.now())
        with col_p2:
            esfera = st.selectbox("Esfera", ["Cível (CPC - Dias Úteis)", "Trabalhista (CLT)", "Penal (CPP - Dias Corridos)", "Juizado Especial"])
        texto_prazo = st.text_area("Texto da Intimação:", height=150)

        if st.button("📆 Calcular Prazo"):
            if texto_prazo:
                with st.spinner("Calculando..."):
                    prompt_prazo = f"""
                    Assistente jurídico Sênior. Contexto: {esfera}. Data Ref: {data_pub.strftime('%d/%m/%Y')}.
                    Texto: "{texto_prazo}".
                    TAREFA: 1. Identifique o Ato. 2. Prazo Legal. 3. Úteis ou Corridos? 4. Data Fatal Sugerida. 5. Atenção a Feriados.
                    """
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_prazo).text
                        st.markdown(res)
                    except Exception as e: st.error(f"Erro: {e}")

    with tab8: # Audiencia
        st.header("🏛️ Preparador de Audiência")
        st.markdown("Gere um roteiro estratégico de perguntas e riscos para sua audiência.")
        
        col_aud1, col_aud2 = st.columns(2)
        with col_aud1:
            meu_papel = st.selectbox("Você representa:", ["Autor / Reclamante", "Réu / Reclamado"])
            tipo_aud = st.selectbox("Tipo de Audiência:", ["Instrução e Julgamento", "Conciliação", "Inicial (Trabalhista)", "UNA"])
        with col_aud2:
            fatos_caso = st.text_area("Resumo dos Fatos / Pontos Controvertidos:", height=150, placeholder="Ex: O reclamante alega horas extras não pagas, mas batia ponto britânico...")
            
        if st.button("🎭 Gerar Roteiro de Audiência"):
            if fatos_caso:
                with st.spinner("Simulando cenário e gerando perguntas..."):
                    prompt_aud = f"""
                    Aja como um advogado especialista experiente.
                    Vou realizar uma audiência de {tipo_aud}.
                    Eu represento o: {meu_papel}.
                    Fatos do caso: "{fatos_caso}".

                    GERE UM ROTEIRO ESTRATÉGICO COM:
                    1. 🎯 **Perguntas para a Parte Contrária:** (Focadas em extrair contradições ou confissões).
                    2. 🛡️ **Perguntas para Minhas Testemunhas:** (Para reforçar minha tese).
                    3. ⚠️ **Pontos Fracos / Riscos:** (Onde o outro advogado vai tentar me atacar e como me defender).
                    4. 🤝 **Estratégia de Acordo:** (Vale a pena? Qual seria um valor teto/piso sugerido com base nos riscos?).

                    Use linguagem direta e prática para leitura rápida na mesa de audiência.
                    """
                    try:
                        res_aud = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_aud).text
                        st.markdown(res_aud)
                        st.download_button("Baixar Roteiro (Word)", gerar_word(res_aud), "roteiro_audiencia.docx")
                    except Exception as e:
                        st.error(f"Erro ao gerar roteiro: {e}")

    # --- ABA 9: MONITOR DE PRAZOS (A NOVA FUNCIONALIDADE!) ---
    with tab9:
        st.header("🚦 Monitor de Movimentações e Prazos")
        st.markdown("Cole a movimentação (e-mail/diário) para a IA analisar, resumir e iniciar o contador.")

        col_mov1, col_mov2, col_mov3 = st.columns(3)
        with col_mov1:
            n_processo = st.text_input("Nº Processo", placeholder="0000000-00.2025...")
        with col_mov2:
            data_mov = st.date_input("Data da Movimentação", datetime.now())
        with col_mov3:
            tipo_prazo = st.selectbox("Contagem", ["Dias Úteis (CPC)", "Dias Corridos", "CLT"])

        texto_movimentacao = st.text_area("Cole o texto da Movimentação aqui:", height=150)

        # Estado da sessão para guardar o resultado temporariamente
        if "analise_prazo" not in st.session_state:
            st.session_state.analise_prazo = None

        if st.button("🔍 Analisar Movimentação"):
            if texto_movimentacao:
                with st.spinner("A IA está lendo a movimentação e calculando prazos..."):
                    prompt_monitor = f"""
                    Analise esta movimentação processual jurídica.
                    Data Base: {data_mov.strftime('%d/%m/%Y')}.
                    Tipo Contagem: {tipo_prazo}.
                    Texto: "{texto_movimentacao}"

                    SAÍDA ESPERADA (Responda exatamente neste formato):
                    RESUMO: [Resumo de 1 linha do que aconteceu]
                    AÇÃO REQUERIDA: [O que o advogado deve fazer? ex: Apresentar Réplica]
                    TEM PRAZO?: [Sim/Não]
                    DIAS: [Quantidade numérica]
                    DATA FATAL SUGERIDA: [Data DD/MM/AAAA]
                    """
                    try:
                        res = genai.GenerativeModel(modelo_escolhido).generate_content(prompt_monitor).text
                        st.session_state.analise_prazo = res # Salva na memória
                    except Exception as e:
                        st.error(f"Erro: {e}")

        # Exibe o resultado se existir
        if st.session_state.analise_prazo:
            st.divider()
            st.subheader("📋 Resultado da Análise")
            st.markdown(st.session_state.analise_prazo)
            
            # --- O CONTADOR VISUAL ---
            st.divider()
            st.subheader("⏱️ Contador de Prazo")
            
            c1, c2 = st.columns(2)
            with c1:
                data_fatal_input = st.date_input("Confirme a Data Fatal (Sugerida pela IA):", datetime.now() + timedelta(days=15))
            
            with c2:
                # Lógica do Contador
                hoje = date.today()
                dias_restantes = (data_fatal_input - hoje).days
                
                if dias_restantes < 0:
                    st.error(f"🚨 PRAZO VENCIDO HÁ {abs(dias_restantes)} DIAS!")
                elif dias_restantes == 0:
                    st.error("🚨 O PRAZO VENCE HOJE!")
                elif dias_restantes <= 3:
                    st.warning(f"⚠️ ATENÇÃO: Faltam {dias_restantes} dias.")
                else:
                    st.success(f"✅ Tranquilo: Faltam {dias_restantes} dias.")

            # Botão para salvar esse prazo na planilha geral
            if st.button("💾 Salvar Movimentação no Controle"):
                s = conectar_planilha()
                if s:
                    # Formato: Data | Cliente/Processo | Tipo | Resumo da Movimentação + Prazo
                    conteudo_salvar = f"MOVIMENTAÇÃO: {texto_movimentacao[:30]}... | PRAZO: {dias_restantes} dias | FATAL: {data_fatal_input.strftime('%d/%m/%Y')}"
                    try:
                        s.append_row([
                            datetime.now().strftime("%d/%m/%Y"), 
                            n_processo if n_processo else "Processo S/N", 
                            "Movimentação/Prazo", 
                            "Acompanhamento", 
                            conteudo_salvar
                        ])
                        st.toast("Movimentação salva com sucesso!", icon="💾")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

else: st.warning("Insira uma chave de API para começar.")

