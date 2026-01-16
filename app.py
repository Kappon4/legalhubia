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
# 1. CONFIGURAÇÃO VISUAL - CYBER THEME
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v9.8", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================================
# 2. FUNÇÕES RESTAURADAS & UTILITÁRIAS
# ==========================================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

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
    return "\n\n[NENHUMA JURISPRUDÊNCIA ESPECÍFICA ENCONTRADA]"

# Configuração API Key
try:
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY_FIXA = ""

def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ Erro: API Key não configurada."
    genai.configure(api_key=chave)
    try:
        return genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt).text
    except Exception as e: return f"❌ Erro IA: {str(e)}"

# --- CÁLCULO TRABALHISTA COMPLETO ---
def calcular_rescisao_completa(admissao, demissao, salario_base, motivo, saldo_fgts, ferias_vencidas, aviso_tipo, grau_insalubridade, tem_periculosidade):
    formato = "%Y-%m-%d"
    d1 = datetime.strptime(str(admissao), formato)
    d2 = datetime.strptime(str(demissao), formato)
    verbas = {}
    
    sal_min = 1412.00
    adic_insal = 0
    if grau_insalubridade == "Mínimo (10%)": adic_insal = sal_min * 0.10
    elif grau_insalubridade == "Médio (20%)": adic_insal = sal_min * 0.20
    elif grau_insalubridade == "Máximo (40%)": adic_insal = sal_min * 0.40
    
    adic_peric = salario_base * 0.30 if tem_periculosidade else 0
    remuneracao = salario_base + max(adic_insal, adic_peric) 
    
    if adic_insal > 0: verbas["Adicional Insalubridade"] = adic_insal
    if adic_peric > 0: verbas["Adicional Periculosidade"] = adic_peric

    meses_trab = (d2.year - d1.year) * 12 + d2.month - d1.month
    
    # Aviso Prévio Proporcional
    anos_completos = meses_trab // 12
    dias_aviso = min(90, 30 + (3 * anos_completos))
    
    verbas["Saldo Salário"] = (remuneracao/30) * d2.day
    
    if motivo == "Demissão sem Justa Causa":
        if aviso_tipo == "Indenizado":
            verbas[f"Aviso Prévio ({dias_aviso} dias)"] = (remuneracao/30) * dias_aviso
            d2 = d2 + timedelta(days=dias_aviso)
    elif motivo == "Pedido de Demissão" and aviso_tipo == "Não Trabalhado":
        verbas["Desconto Aviso Prévio"] = -remuneracao

    meses_ano = d2.month
    if d2.day < 15: meses_ano -= 1
    if meses_ano == 0: meses_ano = 12

    if motivo != "Justa Causa":
        verbas[f"13º Proporcional ({meses_ano}/12)"] = (remuneracao/12) * meses_ano
        verbas[f"Férias Prop. ({meses_ano}/12) + 1/3"] = ((remuneracao/12) * meses_ano) * 1.3333
        if ferias_vencidas: verbas["Férias Vencidas + 1/3"] = remuneracao * 1.3333
        
    if motivo == "Demissão sem Justa Causa": verbas["Multa 40% FGTS"] = saldo_fgts * 0.4
    elif motivo == "Acordo": verbas["Multa 20% FGTS"] = saldo_fgts * 0.2
    
    return verbas

# ==========================================================
# 3. CSS VISUAL (CYBER FUTURE)
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
# 4. MEMÓRIA TEMPORÁRIA (DEV MODE)
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
# 5. LAYOUT DE NAVEGAÇÃO
# ==========================================================
if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: 
    st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)

with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Contratos": "📜 Contratos", "Calculos": "🧮 Cálculos Jurídicos", "Audiência": "🏛️ Simulador Audiência", "Gestão Casos": "📂 Cofre Digital"}
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
        if st.button("✍️ NOVA PETIÇÃO", use_container_width=True): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r2:
        if st.button("🧮 NOVO CÁLCULO", use_container_width=True): st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"; st.rerun()
    with r3:
        if st.button("📜 NOVO CONTRATO", use_container_width=True): st.session_state.navegacao_override = "📜 Contratos"; st.rerun()

# --- REDATOR IA (COM UPLOAD PDF) ---
elif menu_opcao == "✍️ Redator Jurídico":
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO</h2>", unsafe_allow_html=True)
    area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    pecas = []
    if area == "Cível": 
        pecas = ["Petição Inicial", "Contestação", "Réplica", "Reconvenção", "Ação Rescisória", "Mandado de Segurança", "Ação Civil Pública", "Embargos à Execução", "Embargos de Terceiro", "Exceção de Incompetência", "Impugnação ao Valor da Causa", "Pedido de Tutela", "Impugnação ao Cumprimento", "Apelação", "Agravo de Instrumento", "Embargos de Declaração", "Recurso Especial", "Recurso Extraordinário"]
    elif area == "Trabalhista": 
        pecas = ["Reclamação Trabalhista", "Contestação", "Reconvenção", "Exceção de Incompetência", "Impugnação ao Valor", "Recurso Ordinário", "Recurso de Revista", "Embargos (TST)", "Agravo de Instrumento", "Agravo de Petição", "Embargos à Execução", "Consignação em Pagamento"]
    elif area == "Criminal": 
        pecas = ["Resposta à Acusação", "Memoriais", "Queixa-Crime", "Defesa Preliminar (Drogas)", "Apelação", "RSE", "Agravo em Execução", "Embargos de Declaração", "Recurso Especial", "Recurso Extraordinário", "ROC", "Habeas Corpus", "Revisão Criminal", "Pedido de Liberdade", "Relaxamento de Prisão", "Restituição de Coisas", "Representação"]
    elif area == "Tributário": 
        pecas = ["Declaratória de Inexistência", "Anulatória de Débito", "Repetição de Indébito", "Mandado de Segurança", "Consignação em Pagamento", "Embargos à Execução Fiscal", "Exceção de Pré-Executividade", "Apelação", "Agravo", "Recurso Especial", "Defesa Administrativa", "Recurso Administrativo"]
    elif area == "Previdenciário": 
        pecas = ["Requerimento Administrativo", "Petição Inicial Administrativa", "Recurso Administrativo", "Petição de Juntada", "Petição Inicial Judicial", "Contestação", "Réplica", "Recurso Inominado", "Apelação", "Pedido de Tutela", "Cumprimento de Sentença"]
    
    tipo = st.selectbox("Peça", pecas)
    c1, c2 = st.columns(2)
    cli = c1.text_input("Cliente")
    adv = c2.text_input("Parte Contrária")
    
    # NOVA FUNÇÃO: UPLOAD DE PDF
    st.write("---")
    uploaded_file = st.file_uploader("📂 Carregar PDF (Opcional - Extrai fatos automaticamente)", type="pdf")
    
    fatos_iniciais = ""
    if uploaded_file is not None:
        with st.spinner("Lendo PDF..."):
            fatos_iniciais = extrair_texto_pdf(uploaded_file)
            st.success("Texto extraído do PDF com sucesso! Edite abaixo se necessário.")

    fatos = st.text_area("Fatos", value=fatos_iniciais, height=150, placeholder="Descreva os fatos ou use o PDF acima...")
    
    busca_real = st.checkbox("🔍 Buscar Jurisprudência Real (STF/STJ/TST)", value=True)
    
    if st.button("GERAR PEÇA", use_container_width=True):
        if fatos and cli:
            with st.spinner("Pesquisando e Redigindo..."):
                ctx = ""
                if busca_real: ctx = buscar_contexto_juridico(f"{tipo} {fatos}", area)
                
                prompt = f"Advogado {area}. Redija {tipo}. Cliente: {cli} vs {adv}. Fatos: {fatos}. {ctx}. Cite leis e jurisprudência se houver."
                res = tentar_gerar_conteudo(prompt, None)
                st.markdown(res)
                if "❌" not in res:
                    salvar_documento_memoria(tipo, cli, res)
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")

# --- CONTRATOS (+ PROCURAÇÃO) ---
elif menu_opcao == "📜 Contratos":
    st.header("📜 Fábrica de Contratos & Procurações")
    c1, c2 = st.columns(2)
    cli = c1.text_input("Contratante")
    cpf = c2.text_input("CPF/CNPJ")
    obj = st.text_area("Objeto do Contrato (Ex: Ação Trabalhista contra X)")
    val = st.number_input("Valor Honorários (R$)", step=100.0)
    
    if st.button("GERAR CONTRATO + PROCURAÇÃO", use_container_width=True):
        if cli and obj:
            with st.spinner("Redigindo documentos..."):
                # Prompt atualizado para pedir os dois documentos
                prompt = f"""
                Atue como advogado. Redija dois documentos completos em sequência:
                1. CONTRATO DE HONORÁRIOS ADVOCATÍCIOS. Cliente: {cli}, CPF {cpf}. Objeto: {obj}. Valor: R$ {val}. Contratado: LBA Advocacia.
                
                --- QUEBRA DE PÁGINA ---
                
                2. PROCURAÇÃO AD JUDICIA. Outorgante: {cli}, CPF {cpf}. Outorgado: LBA Advocacia. Poderes: Gerais e Especiais para transigir, firmar acordos, receber e dar quitação.
                """
                res = tentar_gerar_conteudo(prompt, None)
                st.markdown(res)
                salvar_documento_memoria("Contrato+Proc", cli, res)
                st.download_button("Baixar", gerar_word(res), "Contrato_Procuracao.docx")
        else:
            st.warning("Preencha o cliente e o objeto.")

# --- CÁLCULOS ---
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Calculadoras Jurídicas")
    area_calc = st.selectbox("Área", ["Trabalhista (CLT)", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    st.markdown("---")

    if area_calc == "Trabalhista (CLT)":
        st.subheader("Rescisão CLT + Adicionais")
        c1, c2, c3 = st.columns(3)
        adm = c1.date_input("Admissão", date(2022,1,1))
        dem = c2.date_input("Demissão", date.today())
        motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa"])
        
        c4, c5, c6 = st.columns(3)
        sal = c4.number_input("Salário", value=2000.0)
        fgts = c5.number_input("Saldo FGTS", value=0.0)
        aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado"])
        
        c7, c8 = st.columns(2)
        insal = c7.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
        peric = c8.checkbox("Periculosidade (30%)")
        
        if st.button("CALCULAR TRABALHISTA"):
            if dem > adm:
                v = calcular_rescisao_completa(adm, dem, sal, motivo, fgts, False, aviso, insal, peric)
                st.table(pd.DataFrame(list(v.items()), columns=["Verba", "Valor"]))
                st.success(f"Total: R$ {sum(v.values()):,.2f}")

    elif area_calc == "Cível (Art. 292/Liquidação)":
        tab1, tab2, tab3 = st.tabs(["Liquidação de Sentença", "Valor da Causa", "Revisão Bancária"])
        
        with tab1:
            st.info("Atualização + Juros + Multa Art. 523")
            c1, c2 = st.columns(2)
            val = c1.number_input("Valor Condenação")
            idx = c2.number_input("Índice Correção", value=1.0)
            c3, c4 = st.columns(2)
            juros = c3.selectbox("Juros", ["1% a.m.", "Selic", "Sem"])
            meses = c4.number_input("Meses", value=12)
            c5, c6 = st.columns(2)
            multa = c5.checkbox("Multa Art. 523 (10%)")
            hon = c6.checkbox("Honorários Execução (10%)")
            if st.button("LIQUIDAR"):
                res = val * idx
                val_juros = 0
                if juros == "1% a.m.": val_juros = res * (0.01 * meses)
                subtotal = res + val_juros
                total = subtotal + (subtotal*0.1 if multa else 0) + (subtotal*0.1 if hon else 0)
                st.success(f"Total Execução: R$ {total:,.2f}")
        
        with tab2:
            st.info("Art. 292 CPC")
            tipo = st.radio("Ação", ["Cobrança", "Alimentos", "Indenização"])
            if tipo == "Alimentos":
                m = st.number_input("Mensalidade")
                st.metric("Valor (12x)", f"R$ {m*12:,.2f}")
            elif tipo == "Cobrança":
                p = st.number_input("Principal")
                j = st.number_input("Juros Vencidos")
                m = st.number_input("Multas")
                st.metric("Valor Causa", f"R$ {p+j+m:,.2f}")
            else:
                d = st.number_input("Valor Pretendido")
                st.metric("Valor Causa", f"R$ {d:,.2f}")

        with tab3:
            emp = st.number_input("Empréstimo")
            tx = st.number_input("Taxa %")
            m = st.number_input("Meses", value=12)
            if st.button("SIMULAR"):
                price = emp * ((tx/100) * (1 + tx/100)**m) / ((1 + tx/100)**m - 1)
                st.warning(f"Parcela Price: R$ {price:.2f} | Gauss (Est.): R$ {price*0.8:.2f}")

    elif area_calc == "Família":
        renda = st.number_input("Renda Líquida")
        f = st.slider("Filhos", 1, 5)
        if st.button("SUGERIR PENSÃO"): st.info(f"Sugerido: R$ {renda * (0.3 + (f-1)*0.05):,.2f}")

    elif area_calc == "Tributária":
        p = st.number_input("Tributo")
        m = st.number_input("Multa %")
        if st.button("ATUALIZAR TRIBUTO"): st.metric("Total", f"R$ {p * (1+m/100):,.2f}")

    elif area_calc == "Criminal":
        p_min = st.number_input("Pena Mínima")
        p_max = st.number_input("Pena Máxima")
        c = st.slider("Circunstâncias Ruins", 0, 8)
        if st.button("CALCULAR PENA"): st.error(f"Base: {p_min + ((p_max-p_min)/8 * c):.1f} anos")

# --- COFRE (MEMÓRIA) ---
elif menu_opcao == "📂 Cofre Digital":
    st.header("📂 Cofre Digital (Sessão Atual)")
    if len(st.session_state.meus_docs) > 0:
        for i, doc in enumerate(st.session_state.meus_docs):
            with st.expander(f"{doc['data']} - {doc['tipo']} - {doc['cliente']}"):
                st.write(doc['conteudo'][:200])
                st.download_button("Baixar", gerar_word(doc['conteudo']), "Doc.docx", key=f"d{i}")
    else: st.info("Cofre vazio nesta sessão.")

# --- SIMULADOR DE AUDIÊNCIA (NOVO) ---
elif menu_opcao == "🏛️ Simulador Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ SIMULADOR DE AUDIÊNCIA (IA PREPARATÓRIA)</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🛡️ Minha Defesa")
        meu_cli = st.text_area("O que meu cliente alega?", height=150, placeholder="Ex: Meu cliente afirma que não recebeu horas extras...")
    
    with col2:
        st.markdown("#### ⚔️ Parte Contrária")
        outra_parte = st.text_area("O que a outra parte alega?", height=150, placeholder="Ex: A empresa diz que ele tinha cargo de confiança...")
    
    tipo_aud = st.selectbox("Tipo de Audiência", ["Instrução Trabalhista", "Cível (Conciliação/Instrução)", "Criminal", "Família"])
    
    if st.button("GERAR PREPARAÇÃO PARA AUDIÊNCIA", use_container_width=True):
        if meu_cli and outra_parte:
            with st.spinner("IA Analisando estratégia e gerando perguntas..."):
                prompt = f"""
                Atue como um Advogado Sênior experiente em audiências de {tipo_aud}.
                Prepare um roteiro de audiência para mim.
                
                CASO:
                - Minha tese: {meu_cli}
                - Tese da parte contrária: {outra_parte}
                
                GERE:
                1. Lista de 5 Perguntas CRUZADAS para fazer à parte contrária (para derrubar a tese deles).
                2. Lista de 3 Perguntas para fazer ao meu cliente (para reforçar nossa tese).
                3. Possíveis "Pegadinhas" que o outro advogado pode tentar fazer.
                """
                res = tentar_gerar_conteudo(prompt, None)
                st.markdown(res)
                
                if "❌" not in res:
                    salvar_documento_memoria("Audiencia", "Simulação", res)
                    st.download_button("Baixar Roteiro", gerar_word(res), "Roteiro_Audiencia.docx")
        else:
            st.warning("Preencha as teses de ambas as partes para gerar a simulação.")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v9.8 | DEV MODE (NO LOGIN)</center>", unsafe_allow_html=True)
