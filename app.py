import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
from datetime import datetime, timedelta, date
import time
import pandas as pd
import base64

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - CYBER THEME (RESGATADO)
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v9.6", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================================
# 2. FUNÇÕES GERAIS (REDATOR, CÁLCULOS, ETC.)
# ==========================================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

def gerar_word(texto):
    doc = Document(); 
    for p in texto.split('\n'): 
        if p.strip(): doc.add_paragraph(p)
    buf = BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def extrair_texto_pdf(arquivo):
    try: return "".join([p.extract_text() for p in PdfReader(arquivo).pages])
    except: return ""

def buscar_contexto_juridico(tema, area):
    fontes = {
        "Criminal": "site:stj.jus.br OR site:stf.jus.br",
        "Trabalhista": "site:tst.jus.br OR site:trtsp.jus.br",
        "Tributário": "site:carf.fazenda.gov.br",
        "Cível": "site:stj.jus.br OR site:tjsp.jus.br"
    }
    query = f"{tema} jurisprudência {fontes.get(area, 'site:jusbrasil.com.br')}"
    try:
        with DDGS() as ddgs:
            res = list(ddgs.text(query, region="br-pt", max_results=3))
            if res: return "\n\n[JURISPRUDÊNCIA REAL ENCONTRADA]:\n" + "\n".join([f"- {r['body']}" for r in res])
    except: pass
    return ""

# Tenta pegar API Key dos Secrets ou usa vazia
try:
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY_FIXA = ""

def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ ERRO: API Key não configurada."
    genai.configure(api_key=chave)
    try:
        return genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt).text
    except Exception as e: return f"❌ Erro IA: {e}"

def calcular_rescisao_completa(admissao, demissao, salario, motivo, saldo_fgts, ferias_venc, aviso, insal, peric):
    verbas = {}
    base = salario
    if peric: base += salario * 0.3
    if insal == "Mínimo": base += 1412 * 0.1
    elif insal == "Médio": base += 1412 * 0.2
    elif insal == "Máximo": base += 1412 * 0.4
    
    d1 = datetime.strptime(str(admissao), "%Y-%m-%d")
    d2 = datetime.strptime(str(demissao), "%Y-%m-%d")
    
    verbas["Saldo Salário"] = (base/30) * d2.day
    meses = (d2.year - d1.year) * 12 + d2.month - d1.month
    
    if motivo == "Demissão sem Justa Causa":
        verbas["Multa 40% FGTS"] = saldo_fgts * 0.4
        aviso_dias = min(90, 30 + (3 * (meses//12)))
        if aviso == "Indenizado": verbas[f"Aviso ({aviso_dias}d)"] = (base/30)*aviso_dias
    return verbas

# ==========================================================
# 3. CSS VISUAL (CYBER FUTURE - RESTAURADO)
# ==========================================================
def local_css():
    bg_image_b64 = get_base64_of_bin_file("unnamed.jpg")
    bg_css = f"""
    .stApp::before {{
        content: ""; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        width: 60%; height: 60%; background-image: url("data:image/jpeg;base64,{bg_image_b64}");
        background-size: contain; background-repeat: no-repeat; background-position: center;
        opacity: 0.08; z-index: 0; pointer-events: none; animation: float-logo 15s ease-in-out infinite;
    }}
    @keyframes float-logo {{ 0%, 100% {{ transform: translate(-50%, -50%) translateY(0px); }} 50% {{ transform: translate(-50%, -50%) translateY(-20px); }} }}
    """ if bg_image_b64 else ""
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');
        :root {{ --bg-dark: #020617; --neon-blue: #00F3FF; --neon-red: #FF0055; --text-main: #FFFFFF; --bg-card: rgba(15, 23, 42, 0.6); }}
        .stApp {{ background-color: var(--bg-dark); color: var(--text-main); font-family: 'Inter'; }}
        {bg_css}
        h1, h2, h3, h4, h5, h6 {{ font-family: 'Rajdhani'; color: #FFF !important; text-transform: uppercase; letter-spacing: 1.5px; z-index: 1; position: relative; }}
        .tech-header {{ background: linear-gradient(90deg, #FFF, var(--neon-blue)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 700; }}
        .stButton>button {{ border: 1px solid var(--neon-blue); color: var(--neon-blue); background: transparent; width: 100%; font-family: 'Rajdhani'; letter-spacing: 1px; transition: 0.3s; }}
        .stButton>button:hover {{ background: var(--neon-blue); color: #000; box-shadow: 0 0 15px var(--neon-blue); border: 1px solid var(--neon-blue); }}
    </style>
    """, unsafe_allow_html=True)
local_css()

# ==========================================================
# 4. MEMÓRIA TEMPORÁRIA
# ==========================================================
if "meus_docs" not in st.session_state:
    st.session_state.meus_docs = []

def salvar_documento_memoria(tipo, cliente, conteudo):
    doc = {
        "id": len(st.session_state.meus_docs) + 1,
        "data": datetime.now().strftime("%d/%m/%Y"),
        "tipo": tipo,
        "cliente": cliente,
        "conteudo": conteudo
    }
    st.session_state.meus_docs.append(doc)

# ==========================================================
# 5. LAYOUT DE NAVEGAÇÃO SUPERIOR (CYBER)
# ==========================================================
if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: 
    st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)

with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Contratos": "📜 Contratos", "Calculos": "🧮 Cálculos Jurídicos", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos (Temp)"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.navegacao_override:
        try: idx_radio = opcoes_menu.index([k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0])
        except: pass
        st.session_state.navegacao_override = None
    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")

# ==========================================================
# 6. TELAS DO SISTEMA
# ==========================================================

# --- DASHBOARD ---
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| DEV MODE</span></h2>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("DOCS NA SESSÃO", len(st.session_state.meus_docs))
    c2.metric("STATUS", "Online (Sem Banco)")
    c3.metric("PLANO", "FULL ACCESS")
    
    st.write("")
    st.subheader("🛠️ CENTRAL DE COMANDO")
    r1, r2, r3 = st.columns(3)
    with r1:
        with st.container(border=True):
            st.markdown("#### ✍️ REDATOR IA")
            st.markdown("Gere peças jurídicas completas.")
            if st.button("ABRIR REDATOR"): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r2:
        with st.container(border=True):
            st.markdown("#### 🧮 CÁLCULOS")
            st.markdown("Trabalhista, Cível, Família.")
            if st.button("ABRIR CÁLCULOS"): st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"; st.rerun()

# --- REDATOR IA ---
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO (ANTI-ALUCINAÇÃO)</h2>", unsafe_allow_html=True)
    
    area_direito = st.selectbox("Área do Direito", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    pecas = []
    if area_direito == "Cível": pecas = ["Petição Inicial", "Contestação", "Réplica", "Reconvenção", "Agravo", "Apelação", "Embargos", "Mandado de Segurança"]
    elif area_direito == "Trabalhista": pecas = ["Reclamação", "Contestação", "Recurso Ordinário", "Consignação"]
    elif area_direito == "Criminal": pecas = ["Resposta à Acusação", "Memoriais", "Habeas Corpus", "Relaxamento Prisão"]
    elif area_direito == "Tributário": pecas = ["Anulatória", "Mandado Segurança", "Embargos Execução"]
    elif area_direito == "Previdenciário": pecas = ["Requerimento Adm", "Petição Inicial", "Recurso", "Aposentadoria"]
    
    c1, c2 = st.columns([1, 2])
    with c1:
        tipo = st.selectbox("Selecione a Peça", pecas)
        cli = st.text_input("Cliente")
        parte_contraria = st.text_input("Parte Contrária")
    with c2:
        fatos = st.text_area("Narrativa dos Fatos e Pedidos", height=200)
    
    anti_alucinacao = st.checkbox("🔍 Ativar Busca Anti-Alucinação", value=True)
    
    if st.button("✨ GERAR PEÇA JURÍDICA", use_container_width=True):
        if fatos and cli:
            with st.spinner(f"Redigindo..."):
                ctx = buscar_contexto_juridico(f"{tipo} {fatos}", area_direito) if anti_alucinacao else ""
                prompt = f"Advogado {area_direito}. Redija {tipo}. Cliente: {cli}. Fatos: {fatos}. {ctx}"
                res = tentar_gerar_conteudo(prompt, None)
                
                st.markdown(res)
                if "❌" not in res:
                    salvar_documento_memoria(tipo, cli, res)
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")

# --- CÁLCULOS ---
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Central Unificada de Cálculos")
    area_calc = st.selectbox("Selecione a Área:", ["Trabalhista (CLT)", "Cível & Processual", "Família & Sucessões", "Tributária", "Criminal"])
    st.markdown("---")

    if area_calc == "Trabalhista (CLT)":
        st.subheader("🛠️ Rescisão Trabalhista Completa")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            dt_adm = c1.date_input("Admissão", date(2022, 1, 1))
            dt_dem = c2.date_input("Demissão", date.today())
            motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo"])
            c4, c5, c6 = st.columns(3)
            salario = c4.number_input("Salário Base", value=2500.0)
            fgts = c5.number_input("Saldo FGTS", value=0.0)
            aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado", "Não Trabalhado"])
            c7, c8 = st.columns(2)
            insal = c7.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
            peric = c8.checkbox("Periculosidade (30%)")
            
            if st.button("CALCULAR RESCISÃO"):
                if dt_dem > dt_adm:
                    v = calcular_rescisao_completa(dt_adm, dt_dem, salario, motivo, fgts, False, aviso, insal, peric)
                    st.success(f"Total Estimado: R$ {sum(v.values()):,.2f}")
                    st.dataframe(pd.DataFrame(list(v.items()), columns=["Verba", "Valor"]), use_container_width=True)

    elif area_calc == "Cível & Processual":
        tab_liq, tab_causa = st.tabs(["Liquidação de Sentença", "Valor da Causa (CPC)"])
        
        with tab_liq:
            st.info("Atualização + Juros + Multa Art. 523 + Honorários")
            c1, c2 = st.columns(2)
            val = c1.number_input("Valor Condenação")
            indice = c2.number_input("Índice Correção", value=1.0)
            c3, c4 = st.columns(2)
            juros = c3.selectbox("Juros", ["1% a.m.", "Selic", "Sem Juros"])
            multa = c4.checkbox("Multa 10% (Art 523 CPC)")
            hon = st.checkbox("Honorários Execução (10%)")
            
            if st.button("LIQUIDAR"):
                res = val * indice
                if juros == "1% a.m.": res *= 1.12 
                total = res + (res*0.10 if multa else 0) + (res*0.10 if hon else 0)
                st.success(f"Total Execução: R$ {total:,.2f}")

        with tab_causa:
            st.info("Art. 292 CPC")
            tipo = st.radio("Ação", ["Cobrança", "Alimentos", "Indenização"])
            v_base = st.number_input("Valor Base")
            if st.button("CALCULAR VALOR DA CAUSA"):
                final = v_base * 12 if tipo == "Alimentos" else v_base
                st.info(f"Valor da Causa: R$ {final:,.2f}")

# --- COFRE DIGITAL (TEMP) ---
elif menu_opcao == "📂 Gestão de Casos (Temp)":
    st.markdown("<h2 class='tech-header'>📂 COFRE DIGITAL (MEMÓRIA)</h2>", unsafe_allow_html=True)
    if len(st.session_state.meus_docs) > 0:
        for i, doc in enumerate(st.session_state.meus_docs):
            with st.expander(f"{doc['data']} - {doc['tipo']} - {doc['cliente']}"):
                st.write(doc['conteudo'][:200] + "...")
                st.download_button("Baixar", gerar_word(doc['conteudo']), "Doc.docx", key=f"d{i}")
    else:
        st.info("Nenhum documento gerado nesta sessão.")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v9.6 | DEV MODE (NO LOGIN)</center>", unsafe_allow_html=True)
