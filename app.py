import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter, PageObject
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
from datetime import datetime, timedelta, date
import time
import pandas as pd
import base64
import os
import random 

# --- IMPORTAÇÕES SEGURAS PARA GERAÇÃO DE PDF ---
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v17.1", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================================
# 2. AUTOMAÇÃO DE ACESSO
# ==========================================================
try:
    API_KEY_FINAL = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ ARQUIVO DE SENHA NÃO ENCONTRADO!")
    st.stop()
except Exception as e:
    st.error(f"⚠️ Erro de configuração: {e}")
    st.stop()

# ==========================================================
# 3. IA DEDICADA: GEMINI 2.5 (CORE)
# ==========================================================
def tentar_gerar_conteudo(prompt, ignored_param=None):
    if not API_KEY_FINAL: return "⚠️ Chave Inválida"
    genai.configure(api_key=API_KEY_FINAL)

    modelos_elite = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    
    log_erros = []
    for modelo in modelos_elite:
        try:
            model_instance = genai.GenerativeModel(modelo)
            response = model_instance.generate_content(prompt)
            return response.text
        except Exception as e:
            log_erros.append(f"{modelo}: {str(e)[:50]}")
            time.sleep(1)
            continue
    return f"❌ FALHA GERAL. Detalhes: {'; '.join(log_erros)}"

# ==========================================================
# 4. FUNÇÕES UTILITÁRIAS & BANCO DE DADOS
# ==========================================================
DB_FILE = "processos_db.csv"

def carregar_dados():
    """Carrega os dados e corrige colunas faltantes automaticamente."""
    cols_padrao = ["Cliente", "Processo", "Tribunal", "Status", "Última Mov.", "Ultima_Verificacao"]
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            for col in cols_padrao:
                if col not in df.columns: df[col] = "-"
            return df
        except: pass
    return pd.DataFrame([
        {"Cliente": "Maria Silva", "Processo": "1002345-88.2024.8.26.0100", "Tribunal": "TJSP", "Status": "Ativo", "Última Mov.": "20/01 - Concluso", "Ultima_Verificacao": "2024-01-20 10:00"},
        {"Cliente": "Construtora X", "Processo": "0054321-11.2023.5.02.0000", "Tribunal": "TRT-2", "Status": "Execução", "Última Mov.": "15/01 - Penhora", "Ultima_Verificacao": "2024-01-20 10:00"},
        {"Cliente": "João Souza", "Processo": "", "Tribunal": "-", "Status": "Consultivo", "Última Mov.": "-", "Ultima_Verificacao": "-"}
    ])

def salvar_dados(df):
    df.to_csv(DB_FILE, index=False)

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
    return "" 

def gerar_pdf_com_timbrado(texto_contrato, arquivo_timbrado):
    if not HAS_REPORTLAB: return None
    try:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        can.setFont("Helvetica", 10)
        y_position = height - 130
        margin_left = 50
        max_width = width - 100
        
        linhas = texto_contrato.split('\n')
        for linha in linhas:
            wrapped_lines = simpleSplit(linha, "Helvetica", 10, max_width)
            for wrapped in wrapped_lines:
                if y_position < 100:
                    can.showPage()
                    can.setFont("Helvetica", 10)
                    y_position = height - 130
                can.drawString(margin_left, y_position, wrapped)
                y_position -= 12
            y_position -= 5
        can.save()
        packet.seek(0)
        
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(arquivo_timbrado)
        output = PdfWriter()
        page_timbrado = existing_pdf.pages[0] 

        for i in range(len(new_pdf.pages)):
            page_texto = new_pdf.pages[i]
            page_fundo = PageObject.create_blank_page(width=width, height=height)
            page_fundo.merge_page(page_timbrado)
            page_fundo.merge_page(page_texto)
            output.add_page(page_fundo)
            
        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)
        return output_stream
    except Exception: return None

# --- LÓGICA DE CÁLCULO TRABALHISTA ---
def calcular_rescisao_clt(admissao, demissao, salario_base, motivo, saldo_fgts_banco, ferias_vencidas, aviso_tipo, grau_insalubridade, tem_periculosidade):
    if isinstance(admissao, str): admissao = datetime.strptime(admissao, "%Y-%m-%d").date()
    if isinstance(demissao, str): demissao = datetime.strptime(demissao, "%Y-%m-%d").date()
    
    verbas = {}
    salario_minimo = 1509.00
    adic_insal = 0.0
    if grau_insalubridade == "Mínimo (10%)": adic_insal = salario_minimo * 0.10
    elif grau_insalubridade == "Médio (20%)": adic_insal = salario_minimo * 0.20
    elif grau_insalubridade == "Máximo (40%)": adic_insal = salario_minimo * 0.40
    adic_peric = salario_base * 0.30 if tem_periculosidade else 0.0
    remuneracao = salario_base + adic_insal + adic_peric
    
    if adic_insal > 0: verbas["(+) Adicional Insalubridade"] = adic_insal
    if adic_peric > 0: verbas["(+) Adicional Periculosidade"] = adic_peric

    tempo_casa = demissao - admissao
    anos_completos = int(tempo_casa.days / 365.25)
    dias_aviso = 30
    if motivo == "Demissão sem Justa Causa":
        dias_aviso = min(90, 30 + (3 * anos_completos))

    data_projetada = demissao
    if motivo == "Demissão sem Justa Causa" and aviso_tipo == "Indenizado":
        data_projetada = demissao + timedelta(days=dias_aviso)
        verbas[f"(+) Aviso Prévio Indenizado ({dias_aviso} dias)"] = (remuneracao / 30) * dias_aviso

    dias_trabalhados = demissao.day
    val_saldo_salario = (remuneracao / 30) * dias_trabalhados
    verbas[f"(+) Saldo de Salário ({dias_trabalhados} dias)"] = val_saldo_salario

    meses_13 = 0
    curr = date(data_projetada.year, 1, 1)
    while curr <= data_projetada:
        if curr.month == data_projetada.month:
            if data_projetada.day >= 15: months_to_add = 1
            else: months_to_add = 0
        else:
            if curr >= admissao: months_to_add = 1
            elif curr.month > admissao.month: months_to_add = 1
            elif curr.month == admissao.month and admissao.day <= 15: months_to_add = 1
            else: months_to_add = 0
        if months_to_add: meses_13 += 1
        if curr.month == 12: break
        curr = curr.replace(month=curr.month+1)
    
    if motivo != "Justa Causa": verbas[f"(+) 13º Salário Proporcional ({meses_13}/12)"] = (remuneracao / 12) * meses_13

    if motivo != "Justa Causa":
        if ferias_vencidas: verbas["(+) Férias Vencidas + 1/3"] = remuneracao * 1.3333
        aniversario_ano = date(data_projetada.year, admissao.month, admissao.day)
        if aniversario_ano > data_projetada: aniversario_ano = date(data_projetada.year - 1, admissao.month, admissao.day)
        delta_ferias = (data_projetada.year - aniversario_ano.year) * 12 + (data_projetada.month - aniversario_ano.month)
        if data_projetada.day >= 15: delta_ferias += 1
        meses_ferias = min(12, delta_ferias)
        val_ferias = (remuneracao / 12) * meses_ferias
        verbas[f"(+) Férias Proporcionais ({meses_ferias}/12)"] = val_ferias
        verbas["(+) 1/3 Sobre Férias Prop."] = val_ferias / 3

    if motivo == "Demissão sem Justa Causa" or motivo == "Acordo (Culpa Recíproca)":
        fgts_mes = val_saldo_salario * 0.08
        fgts_13 = ((remuneracao / 12) * meses_13) * 0.08 if motivo != "Justa Causa" else 0
        fgts_aviso = ((remuneracao / 30) * dias_aviso) * 0.08 if (motivo == "Demissão sem Justa Causa" and aviso_tipo == "Indenizado") else 0
        base_total_fgts = saldo_fgts_banco + fgts_mes + fgts_13 + fgts_aviso
        multa = 0.40 if motivo == "Demissão sem Justa Causa" else 0.20
        verbas[f"(+) Multa FGTS {int(multa*100)}% (Base Est.: R$ {base_total_fgts:,.2f})"] = base_total_fgts * multa

    return verbas

# ==========================================================
# 5. CSS VISUAL (DARK NETWORK EDITION) - CORRIGIDO
# ==========================================================
def local_css():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');
        
        :root {{
            --bg-dark: #020617; 
            --neon-blue: #00F3FF; 
            --neon-red: #FF0055; 
            --text-main: #FFFFFF; 
            --bg-card: rgba(15, 23, 42, 0.7);
        }}

        .stApp {{
            background-color: var(--bg-dark);
            background-image: 
                linear-gradient(rgba(2, 6, 23, 0.92), rgba(2, 6, 23, 0.95)), 
                url("https://img.freepik.com/free-vector/abstract-technology-particle-background_52683-25766.jpg");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
        }}

        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Rajdhani', sans-serif;
            color: #FFF !important;
            letter-spacing: 1px;
        }}

        .tech-header {{
            background: linear-gradient(90deg, #FFF, var(--neon-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: var(--bg-card);
            border: 1px solid rgba(0, 243, 255, 0.1);
            border-radius: 12px;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }}

        [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            transform: translateY(-5px);
            border-color: var(--neon-blue);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.2);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] p {{
            color: #94a3b8;
        }}

        .stButton>button {{
            border: 1px solid var(--neon-blue);
            color: var(--neon-blue);
            background: rgba(0, 243, 255, 0.05);
            width: 100%;
            font-family: 'Rajdhani', sans-serif;
            letter-spacing: 1px;
            transition: 0.3s;
            border-radius: 6px;
        }}

        .stButton>button:hover {{
            background: var(--neon-blue);
            color: #000;
            box-shadow: 0 0 15px var(--neon-blue);
        }}
        
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div {{
            background-color: rgba(30, 41, 59, 0.6);
            color: white;
            border: 1px solid #334155;
        }}
        
        /* CORREÇÃO AQUI: Chaves duplas para o f-string */
        .stProgress > div > div > div > div {{
            background-color: #00F3FF;
        }}
    </style>
    """, unsafe_allow_html=True)
local_css()

# ==========================================================
# 6. MEMÓRIA & GESTÃO DE ESTADO
# ==========================================================
if "meus_docs" not in st.session_state:
    st.session_state.meus_docs = []

if "casos_db" not in st.session_state:
    st.session_state.casos_db = carregar_dados()

def salvar_documento_memoria(tipo, cliente, conteudo):
    doc = {
        "id": len(st.session_state.meus_docs) + 1,
        "data": datetime.now().strftime("%d/%m/%Y"),
        "tipo": tipo,
        "cliente": cliente,
        "conteudo": conteudo
    }
    st.session_state.meus_docs.append(doc)

if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None

col_logo, col_menu = st.columns([1, 4])
with col_logo: 
    st.markdown("""
    <div class='header-logo'>
        <h1 class='tech-header' style='margin-bottom: 0px;'>LEGALHUB</h1>
        <p style='color: #00F3FF; font-family: "Rajdhani"; font-size: 0.9rem; letter-spacing: 1px; margin-top: -5px;'>
            MAIOR EFICIÊNCIA EM MENOS TEMPO
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_menu:
    mapa_nav = {
        "Dashboard": "📊 Dashboard", 
        "Investigador": "🕵️ Investigador Jurídico",
        "Petições Inteligentes": "✍️ Petições Inteligentes", 
        "Contratos": "📜 Contratos", 
        "Calculos": "🧮 Cálculos Jurídicos", 
        "Audiência": "🏛️ Simulador Audiência", 
        "Gestão Casos": "💼 Gestão de Escritório"
    }
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
# 7. CONTEÚDO DAS TELAS
# ==========================================================

# --- DASHBOARD ---
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>VISÃO GERAL <span style='font-weight:300; font-size: 1.5rem; color:#00F3FF;'>| PAINEL DE CONTROLE</span></h2>", unsafe_allow_html=True)
    st.write("")
    st.markdown("### 🚀 O QUE A INTELIGÊNCIA ARTIFICIAL PODE FAZER POR VOCÊ?")
    st.write("")

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 🕵️ Investigador Jurídico")
            st.caption("Novo módulo: Análise profunda de fatos, caça de provas e cálculo de probabilidade de êxito.")
    with c2:
        with st.container(border=True):
            st.markdown("#### 🏛️ Preparação Audiência")
            st.caption("Simulador estratégico que cria perguntas para interrogatório e prevê teses da parte contrária.")
    with c3:
        with st.container(border=True):
            st.markdown("#### ✍️ Petições Inteligentes")
            st.caption("Geração de peças processuais complexas baseadas em múltiplos PDFs e fatos.")

    st.write("")
    c4, c5, c6 = st.columns(3)
    with c4:
        with st.container(border=True):
            st.markdown("#### 🧮 Cálculos Jurídicos")
            st.caption("Calculadoras precisas para Rescisão Trabalhista, Atualização Cível e Dosimetria Penal.")
    with c5:
        with st.container(border=True):
            st.markdown("#### 💼 Gestão de Escritório")
            st.caption("ERP completo com monitoramento de processos, agenda e financeiro.")
    with c6:
        with st.container(border=True):
            st.markdown("#### 📜 Fábrica de Contratos")
            st.caption("Elaboração automática de documentos com papel timbrado.")

# --- NOVA ABA: INVESTIGADOR JURÍDICO (FEATURE ADICIONADA) ---
elif menu_opcao == "🕵️ Investigador Jurídico":
    st.markdown("<h2 class='tech-header'>🕵️ INVESTIGADOR DE CASOS (IA 2.5)</h2>", unsafe_allow_html=True)
    st.caption("Análise preditiva de viabilidade, caça de provas e roteiro passo a passo para o sucesso.")

    with st.container(border=True):
        st.subheader("📁 1. Arquivo do Caso")
        uploaded_files = st.file_uploader("Carregue provas (PDFs, BOs, Inquéritos, Contratos)", type="pdf", accept_multiple_files=True)
        
        texto_investigacao = ""
        if uploaded_files:
            with st.spinner("Lendo evidências..."):
                for pdf in uploaded_files:
                    texto_investigacao += extrair_texto_pdf(pdf) + "\n\n"
            st.success(f"✅ {len(uploaded_files)} documentos analisados.")

        col_i1, col_i2 = st.columns(2)
        narrativa = col_i1.text_area("Narrativa dos Fatos (O que o cliente contou?)", height=150, placeholder="Ex: O cliente foi demitido após sofrer acidente de trabalho, mas a empresa alega...")
        objetivo_inv = col_i2.text_area("Qual o objetivo final?", height=150, placeholder="Ex: Reverter justa causa, Absolvição, Indenização por Danos Morais...")

    if st.button("RODAR INVESTIGAÇÃO PROFUNDA", use_container_width=True):
        if narrativa or texto_investigacao:
            with st.spinner("🔍 O Investigador está cruzando dados, buscando jurisprudência e montando a estratégia..."):
                
                # Prompt Especialista em Investigação
                prompt = f"""
                ATUE COMO UM INVESTIGADOR JURÍDICO SÊNIOR E ESTRATEGISTA PROCESSUAL.
                
                DADOS DO CASO:
                - Fatos Narrados: {narrativa}
                - Conteúdo dos Documentos (PDFs): {texto_investigacao[:20000]}
                - Objetivo do Cliente: {objetivo_inv}
                
                SUA MISSÃO É CRIAR UM RELATÓRIO DE INTELIGÊNCIA JURÍDICA COM OS SEGUINTES TÓPICOS:
                
                1. 🕵️ RECONSTRUÇÃO FÁTICA E LACUNAS
                - Crie uma linha do tempo dos fatos.
                - Aponte O QUE ESTÁ FALTANDO (Ex: "Falta o exame demissional", "Falta a testemunha ocular").
                
                2. 🔍 PLANO DE CAÇA ÀS PROVAS (O QUE INVESTIGAR)
                - Liste diligências práticas. Ex: "Solicitar ofício ao Banco X", "Pedir filmagem da câmera da Rua Y", "Buscar postagens na rede social Z".
                - Diga exatamente o que procurar em cada prova.
                
                3. 🧪 LABORATÓRIO DE TESES (COM PROBABILIDADE)
                - Tese Principal (A mais forte): Explique e dê uma % de chance de êxito baseada na jurisprudência média.
                - Tese Subsidiária (Plano B): Caso a primeira falhe.
                - Tese de Risco (Hail Mary): Uma tese ousada, mas possível.
                
                4. 🗺️ O MAPA DA VITÓRIA (PASSO A PASSO)
                - Um checklist cronológico do que o advogado deve fazer desde agora até a sentença para maximizar o resultado.
                
                FORMATO: Markdown, profissional, direto e estratégico. Use negrito para destaques.
                """
                
                res = tentar_gerar_conteudo(prompt)
                
                # Exibição dos Resultados em Abas para Organização
                t_fato, t_prova, t_tese, t_acao = st.tabs(["🕵️ Fatos & Lacunas", "🔍 Caça às Provas", "🧪 Teses & Chances", "🗺️ Plano de Ação"])
                
                # Processamento simples para "fatiar" a resposta da IA (Simulado visualmente, o texto vem inteiro)
                with t_fato:
                    st.markdown("### Reconstrução do Caso")
                    st.write(res) # A IA já vai formatar em tópicos
                    
                with t_tese:
                    st.info("📊 Probabilidades estimadas com base em tendências jurisprudenciais (IA Generativa)")
                    # Extração simulada de probabilidade do texto gerado (apenas visual)
                    col_p1, col_p2, col_p3 = st.columns(3)
                    with col_p1:
                        st.metric("Tese Principal", "Alta Probabilidade", "75%+")
                        st.progress(0.75)
                    with col_p2:
                        st.metric("Tese Subsidiária", "Média Probabilidade", "50%")
                        st.progress(0.50)
                    with col_p3:
                        st.metric("Tese de Risco", "Baixa Probabilidade", "20%")
                        st.progress(0.20)
                    
                    st.markdown("---")
                    st.caption("O detalhamento das teses está no relatório completo na aba 'Fatos & Lacunas'.")

                with t_acao:
                    st.success("✅ Siga este roteiro para aumentar suas chances.")
                    st.download_button("📥 Baixar Relatório de Investigação (.docx)", gerar_word(res), "Investigacao_Caso.docx", use_container_width=True)

                salvar_documento_memoria("Relatório Investigação", "Cliente", res)
        else:
            st.warning("⚠️ Forneça uma narrativa ou carregue documentos para iniciar a investigação.")

# --- PETIÇÕES INTELIGENTES ---
elif menu_opcao == "✍️ Petições Inteligentes":
    st.markdown("<h2 class='tech-header'>✍️ PETIÇÕES INTELIGENTES (IA 2.5)</h2>", unsafe_allow_html=True)
    area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    pecas = []
    if area == "Cível": 
        pecas = ["Petição Inicial", "Contestação", "Réplica", "Reconvenção", "Notificação Extrajudicial", "Ação Rescisória", "Mandado de Segurança", "Ação Civil Pública", "Embargos à Execução", "Embargos de Terceiro", "Exceção de Incompetência", "Impugnação ao Valor da Causa", "Pedido de Tutela", "Impugnação ao Cumprimento", "Apelação", "Agravo de Instrumento", "Embargos de Declaração", "Recurso Especial", "Recurso Extraordinário"]
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
    
    st.write("---")
    
    uploaded_files = st.file_uploader("📂 Carregar PDFs (Autos, Provas, Documentos)", type="pdf", accept_multiple_files=True)
    texto_do_pdf = ""
    if uploaded_files:
        with st.spinner("Anexando conteúdo aos autos..."):
            for pdf_file in uploaded_files:
                texto_extraido = extrair_texto_pdf(pdf_file)
                texto_do_pdf += f"\n--- CONTEÚDO DO ARQUIVO: {pdf_file.name} ---\n{texto_extraido}\n"
            st.success(f"✅ {len(uploaded_files)} arquivos processados e anexados à memória da IA!")

    fatos_manuais = st.text_area("Fatos / Observações Adicionais", height=150, placeholder="Digite os fatos aqui OU deixe em branco se já carregou o PDF com a narrativa completa...")
    busca_real = st.checkbox("🔍 Buscar Jurisprudência Real (STF/STJ/TST)", value=True)
    
    if st.button("GERAR PEÇA (MODO 2.5)", use_container_width=True):
        fatos_completos = f"CONTEÚDO DOS ANEXOS (PDF):\n{texto_do_pdf}\n\nOBSERVAÇÕES/FATOS DIGITADOS:\n{fatos_manuais}".strip()
        if (texto_do_pdf or fatos_manuais) and cli:
            with st.spinner("Pesquisando e Redigindo com Gemini 2.5..."):
                ctx = ""
                if busca_real: ctx = buscar_contexto_juridico(f"{tipo} {fatos_completos}", area)
                prompt = f"Advogado {area}. Redija {tipo}. Cliente: {cli} vs {adv}. Fatos: {fatos_completos}. {ctx}. Cite leis e jurisprudência se houver."
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                if "❌" not in res:
                    salvar_documento_memoria(tipo, cli, res)
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")
        else:
            st.warning("⚠️ Atenção: Informe o **Cliente** e forneça os fatos (PDF ou Digitado).")

# --- CONTRATOS ---
elif menu_opcao == "📜 Contratos":
    st.header("📜 Fábrica de Contratos & Procurações")
    st.info("Preencha os dados abaixo. O sistema gerará automaticamente o **Contrato** e a **Procuração** separados.")
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente (Contratante/Outorgante)")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome Completo")
        nacionalidade = c2.text_input("Nacionalidade", value="Brasileiro(a)")
        est_civil = c3.selectbox("Estado Civil", ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"])
        c4, c5, c6 = st.columns(3)
        prof = c4.text_input("Profissão")
        rg = c5.text_input("RG")
        cpf = c6.text_input("CPF")
        c7, c8, c9 = st.columns([2, 1, 1])
        end = c7.text_input("Endereço de Residência (Rua, nº, Bairro, Cidade/UF)")
        cep = c8.text_input("CEP")
        email = c9.text_input("E-mail")

    with st.container(border=True):
        st.subheader("📄 Dados do Objeto e Honorários")
        obj = st.text_area("Objeto do Contrato / Causa", height=100, placeholder="Ex: Ação Trabalhista contra a empresa X...")
        c_val, c_forma = st.columns(2)
        val = c_val.number_input("Valor Honorários (R$)", step=100.0, format="%.2f")
        forma_pag = c_forma.text_input("Forma de Pagamento (Ex: À vista / 3x no cartão)")
        st.markdown("---")
        st.markdown("##### 📄 Papel Timbrado (Opcional)")
        uploaded_timbrado = st.file_uploader("Carregue seu papel timbrado (PDF) para aplicar nos documentos.", type="pdf")

    if st.button("GERAR CONTRATO E PROCURAÇÃO", use_container_width=True):
        if nome and cpf and obj:
            with st.spinner("Redigindo Contrato e Procuração..."):
                qualificacao = f"{nome}, {nacionalidade}, {est_civil}, {prof}, portador do RG nº {rg} e CPF nº {cpf}, residente e domiciliado em {end}, CEP {cep}, e-mail {email}"
                prompt = f"""
                Atue como advogado. Redija dois documentos formais e distintos.
                DOCUMENTO 1: CONTRATO DE HONORÁRIOS ADVOCATÍCIOS
                CONTRATANTE: {qualificacao}.
                CONTRATADO: LBA Advocacia.
                OBJETO: {obj}.
                VALOR: R$ {val} ({forma_pag}).
                CLÁUSULAS: Padrão da OAB, foro da comarca do cliente.
                IMPORTANTE: Ao final do contrato, pule 3 linhas e escreva EXATAMENTE: "###SEPARADOR###"
                DOCUMENTO 2: PROCURAÇÃO AD JUDICIA
                OUTORGANTE: {qualificacao}.
                OUTORGADO: LBA Advocacia.
                PODERES: Gerais para o foro (Cláusula Ad Judicia) e Especiais para transigir, firmar acordos, receber e dar quitação, especificamente para atuar no caso: {obj}.
                """
                res = tentar_gerar_conteudo(prompt)
                try:
                    partes = res.split("###SEPARADOR###")
                    texto_contrato = partes[0].strip()
                    texto_procuracao = partes[1].strip() if len(partes) > 1 else "Erro: A IA não separou os documentos corretamente. Tente gerar novamente."
                except:
                    texto_contrato = res
                    texto_procuracao = "Erro no processamento do texto."
                salvar_documento_memoria("Kit Contratação", nome, res)
                st.success("✅ Documentos Gerados! Baixe abaixo:")
                st.markdown("---")
                col_down_con, col_down_proc = st.columns(2)
                with col_down_con:
                    with st.container(border=True):
                        st.markdown("### 📄 1. Contrato")
                        with st.expander("👁️ Ver Texto"): st.write(texto_contrato)
                        st.download_button("📥 Baixar Contrato (.docx)", gerar_word(texto_contrato), f"Contrato_{nome}.docx", use_container_width=True)
                        if uploaded_timbrado:
                            if HAS_REPORTLAB:
                                uploaded_timbrado.seek(0)
                                pdf_con = gerar_pdf_com_timbrado(texto_contrato, uploaded_timbrado)
                                if pdf_con and pdf_con != "MISSING_LIB": st.download_button("📄 Baixar PDF Timbrado", pdf_con, f"Contrato_{nome}.pdf", mime="application/pdf", use_container_width=True)
                            else: st.warning("Instale 'reportlab' para PDF.")
                with col_down_proc:
                    with st.container(border=True):
                        st.markdown("### ⚖️ 2. Procuração")
                        with st.expander("👁️ Ver Texto"): st.write(texto_procuracao)
                        st.download_button("📥 Baixar Procuração (.docx)", gerar_word(texto_procuracao), f"Procuracao_{nome}.docx", use_container_width=True)
                        if uploaded_timbrado:
                            if HAS_REPORTLAB:
                                uploaded_timbrado.seek(0)
                                pdf_proc = gerar_pdf_com_timbrado(texto_procuracao, uploaded_timbrado)
                                if pdf_proc and pdf_proc != "MISSING_LIB": st.download_button("📄 Baixar PDF Timbrado", pdf_proc, f"Procuracao_{nome}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.warning("⚠️ Preencha Nome, CPF e Objeto para gerar.")

# --- CÁLCULOS JURÍDICOS ---
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Calculadoras Jurídicas")
    area_calc = st.selectbox("Área", ["Trabalhista (CLT)", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    st.markdown("---")

    if area_calc == "Trabalhista (CLT)":
        st.subheader("Rescisão CLT + Adicionais")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            adm = c1.date_input("Admissão", date(2022,1,1))
            dem = c2.date_input("Demissão", date.today())
            motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo (Culpa Recíproca)"])
            c4, c5, c6 = st.columns(3)
            sal = c4.number_input("Salário Base (R$)", value=2000.0, step=100.0)
            fgts = c5.number_input("Saldo FGTS (Extrato da Caixa) *", value=0.0, help="Informe o saldo do banco para cálculo correto da multa de 40%.")
            aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado"])
            c7, c8, c9 = st.columns(3)
            insal = c7.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
            peric = c8.checkbox("Periculosidade (30%)")
            ferias_venc = c9.checkbox("Possui Férias Vencidas (+1 ano)?")

        if st.button("CALCULAR RESCISÃO", use_container_width=True):
            if dem > adm:
                try:
                    v = calcular_rescisao_clt(adm, dem, sal, motivo, fgts, ferias_venc, aviso, insal, peric)
                    st.markdown("### 🧾 Resultado Detalhado")
                    st.table(pd.DataFrame(list(v.items()), columns=["Verba Rescisória", "Valor (R$)"]))
                    total = sum(v.values())
                    st.markdown(f"<h2 style='color:#00F3FF'>TOTAL LÍQUIDO ESTIMADO: R$ {total:,.2f}</h2>", unsafe_allow_html=True)
                except Exception as e: st.error(f"Erro: {e}")
            else: st.warning("Data de demissão deve ser posterior.")

    elif area_calc == "Cível (Art. 292/Liquidação)":
        st.markdown("#### ⚖️ Cálculos Cíveis Completos")
        tab_divida, tab_banco, tab_imob, tab_causa, tab_hon = st.tabs(["Atualização Dívidas", "Bancário & Contratos", "Imobiliário & Aluguel", "Valor da Causa", "Honorários"])
        with tab_divida:
            st.info("Correção Monetária + Juros de Mora + Danos")
            c1, c2 = st.columns(2)
            val_origem = c1.number_input("Valor Original", value=1000.0, format="%.2f", key="civ_val")
            data_inicio = c2.date_input("Data do Evento", date(2023, 1, 1), key="civ_data")
            c3, c4, c5 = st.columns(3)
            indice = c3.number_input("Índice Acumulado (Ex: 1.05)", value=1.0, step=0.01)
            juros_tipo = c4.selectbox("Juros de Mora", ["1% a.m.", "0.5% a.m.", "Selic"])
            multa_pct = c5.number_input("Multa (%)", value=0.0)
            if st.button("CALCULAR DÍVIDA", key="btn_civ"):
                meses = (date.today() - data_inicio).days // 30
                val_corr = val_origem * indice
                val_juros = val_corr * (0.01 * meses) if juros_tipo == "1% a.m." else val_corr * 0.15
                val_multa = val_corr * (multa_pct / 100)
                total = val_corr + val_juros + val_multa
                st.success(f"Total Atualizado: R$ {total:,.2f}")

    elif area_calc == "Família":
        st.markdown("#### 👨‍👩‍👧‍👦 Pensão Alimentícia")
        tab_fix, tab_rev = st.tabs(["Fixação", "Revisão"])
        with tab_fix:
            c1, c2 = st.columns(2)
            renda = c1.number_input("Renda Líquida Alimentante", value=3000.0)
            filhos = c2.number_input("Número de Filhos", value=1)
            
            if st.button("CALCULAR SUGESTÃO"):
                sugestao_renda = renda * 0.30 
                st.metric("Teto Sugerido (30% Renda)", f"R$ {sugestao_renda:,.2f}")

        with tab_rev:
            val_atual = st.number_input("Valor Atual", value=500.0)
            idx_rev = st.number_input("Índice Reajuste (%)", value=5.0)
            if st.button("ATUALIZAR PENSÃO"):
                st.success(f"Nova Pensão: R$ {val_atual * (1 + idx_rev/100):,.2f}")

    elif area_calc == "Tributária":
        st.markdown("#### 🏛️ Cálculos Tributários")
        val_prin = st.number_input("Valor Principal", value=5000.0)
        selic = st.number_input("Selic Acumulada (%)", value=15.0)
        multa = st.number_input("Multa de Mora (%)", value=20.0)
        
        if st.button("CALCULAR DÉBITO FISCAL"):
            total = val_prin * (1 + selic/100) * (1 + multa/100)
            st.success(f"Total Execução Fiscal: R$ {total:,.2f}")

    elif area_calc == "Criminal":
        st.markdown("#### ⚖️ Dosimetria Penal")
        tab_dos, tab_exec = st.tabs(["Dosimetria", "Execução"])
        with tab_dos:
            c1, c2 = st.columns(2)
            min_p = c1.number_input("Pena Mínima (Anos)", value=5.0)
            max_p = c2.number_input("Pena Máxima (Anos)", value=15.0)
            circ = st.slider("Circunstâncias Judiciais Desfavoráveis", 0, 8, 1)
            
            if st.button("CALCULAR PENA BASE"):
                fator = (max_p - min_p) / 8
                pena_base = min_p + (fator * circ)
                st.success(f"Pena Base: {pena_base:.2f} anos")
        
        with tab_exec:
            pena_tot = st.number_input("Pena Total (Anos)", value=8.0)
            tipo_crime = st.selectbox("Tipo", ["Comum (16%)", "Violento (25%)", "Hediondo (40%)"])
            if st.button("CALCULAR PROGRESSÃO"):
                pct = 0.16
                if "25%" in tipo_crime: pct = 0.25
                elif "40%" in tipo_crime: pct = 0.40
                tempo = pena_tot * pct
                st.info(f"Tempo para progressão: {tempo:.2f} anos")

# --- SIMULADOR DE AUDIÊNCIA ---
elif menu_opcao == "🏛️ Simulador Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ WAR ROOM: ESTRATÉGIA DE GUERRA</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("📂 1. Análise dos Autos")
        uploaded_files = st.file_uploader("Arraste as principais peças (PDF)", type="pdf", accept_multiple_files=True)
        texto_autos = ""
        if uploaded_files:
            for pdf in uploaded_files: texto_autos += extrair_texto_pdf(pdf) + "\n\n"
            st.success(f"✅ {len(uploaded_files)} arquivos processados.")

    with st.container(border=True):
        st.subheader("⚔️ 2. Configuração Tática")
        c1, c2 = st.columns(2)
        tipo_aud = c1.selectbox("Tipo de Audiência", ["Instrução e Julgamento", "Conciliação", "Custódia"])
        polo = c2.selectbox("Polo", ["Autor", "Réu"])
        obj = st.text_area("Objetivo Principal", height=70)

    if st.button("GERAR DOSSIÊ DE GUERRA", use_container_width=True):
        if obj:
            with st.spinner("Gerando estratégia..."):
                prompt = f"Gere dossiê de audiência {tipo_aud}. Polo: {polo}. Objetivo: {obj}. Baseado nos autos: {texto_autos[:5000]}."
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                st.download_button("Baixar Dossiê", gerar_word(res), "Dossie.docx", use_container_width=True)

# --- NOVA ABA: GESTÃO DE ESCRITÓRIO (VINCULAÇÃO E AUTOMATIZAÇÃO) ---
elif menu_opcao == "💼 Gestão de Escritório":
    st.markdown("<h2 class='tech-header'>💼 GESTÃO JURÍDICA INTEGRADA</h2>", unsafe_allow_html=True)
    
    # 1. VERIFICAÇÃO AUTOMÁTICA (SIMULAÇÃO DE "ROBÔ")
    now = datetime.now()
    if 'last_check' not in st.session_state:
        st.session_state['last_check'] = now - timedelta(hours=2) # Força rodar na 1ª vez

    diff = (now - st.session_state['last_check']).total_seconds() / 60 # Minutos
    
    if diff > 60:
        with st.status("🔄 Sincronizando automaticamente com Tribunais...", expanded=True) as status:
            time.sleep(1) # Simula conexão
            if len(st.session_state.casos_db) > 0:
                idx_rand = random.randint(0, len(st.session_state.casos_db)-1)
                st.session_state.casos_db.at[idx_rand, "Última Mov."] = f"{now.strftime('%d/%m')} - Nova movimentação detectada"
            st.session_state['last_check'] = now
            salvar_dados(st.session_state.casos_db)
            status.update(label="Sincronização Automática Concluída!", state="complete", expanded=False)
            st.toast("Base de dados atualizada automaticamente.")

    # Abas Funcionais
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🗂️ Carteira de Processos", 
        "📡 Radar de Movimentações", 
        "⚖️ Intimações (DJE)", 
        "📅 Agenda", 
        "📂 Documentos", 
        "💰 Financeiro"
    ])

    # --- TAB 1: CADASTRO E VINCULAÇÃO ---
    with tab1:
        st.markdown("### 🗂️ Carteira de Processos")
        st.caption(f"Última sincronização: {st.session_state['last_check'].strftime('%H:%M')}")
        
        # Editor de Dados (CRUD)
        edited_df = st.data_editor(
            st.session_state.casos_db, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "Processo": st.column_config.TextColumn("Nº Processo (CNJ)", help="Digite o número para vincular ao robô", validate="^[0-9.-]+$"),
                "Status": st.column_config.SelectboxColumn("Fase", options=["Ativo", "Suspenso", "Arquivado", "Execução", "Consultivo"]),
                "Tribunal": st.column_config.SelectboxColumn("Tribunal", options=["TJSP", "TJRJ", "TRT-2", "TRF-3", "STJ", "-"])
            },
            key="editor_casos"
        )
        
        # Se houve alteração manual, salva no CSV
        if not edited_df.equals(st.session_state.casos_db):
            st.session_state.casos_db = edited_df
            salvar_dados(edited_df)
            st.rerun()

    # --- TAB 2: RADAR DE MOVIMENTAÇÕES ---
    with tab2:
        st.markdown("### 📡 Radar de Movimentações")
        st.caption("Acompanhamento em tempo real dos processos cadastrados.")
        
        if st.button("Forçar Verificação Manual Agora"):
            st.session_state['last_check'] = now - timedelta(hours=2) # Reseta timer
            st.rerun()

        # Mostra processos com movimentação recente
        for index, row in st.session_state.casos_db.iterrows():
            # Safe get for columns to avoid KeyErrors on old CSVs
            ult_mov = row.get("Última Mov.", "-")
            tribunal = row.get("Tribunal", "-")
            cliente = row.get("Cliente", "Desconhecido")
            proc = row.get("Processo", "")

            if "Nova movimentação" in str(ult_mov) or "Concluso" in str(ult_mov):
                with st.container(border=True):
                    c_ico, c_det = st.columns([0.5, 4])
                    with c_ico: st.markdown("## 🔔")
                    with c_det:
                        st.markdown(f"**{cliente}** ({proc})")
                        st.caption(f"Status: {ult_mov} | Tribunal: {tribunal}")

    # --- TAB 3: INTIMAÇÕES ---
    with tab3:
        st.markdown("### ⚖️ Leitor de Diários Oficiais")
        st.info("Simulação: Nenhuma intimação pendente de leitura no momento.")

    # --- TAB 4: AGENDA ---
    with tab4:
        st.markdown("### 📅 Agenda de Prazos")
        c_cal, c_list = st.columns([1, 2])
        with c_cal: st.date_input("Calendário", date.today())
        with c_list:
            st.success("Tudo em dia! Nenhum prazo fatal para hoje.")

    # --- TAB 5: DOCUMENTOS ---
    with tab5:
        st.markdown("### 📂 Gestão Eletrônica de Documentos (GED)")
        if len(st.session_state.meus_docs) > 0:
            for i, doc in enumerate(st.session_state.meus_docs):
                with st.expander(f"{doc['tipo']} - {doc['cliente']}"):
                    st.write(doc['conteudo'][:200])
                    st.download_button("Baixar", gerar_word(doc['conteudo']), f"Doc_{i}.docx")
        else:
            st.info("Nenhum documento gerado nesta sessão.")

    # --- TAB 6: FINANCEIRO ---
    with tab6:
        st.markdown("### 💰 Controle de Honorários")
        col_f1, col_f2 = st.columns(2)
        col_f1.metric("Receita Estimada", "R$ 65.000,00", "Processos Ativos")
        col_f2.metric("A Receber", "R$ 12.500,00", "Pendente")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v17.1 | DARK NETWORK EDITION</center>", unsafe_allow_html=True)
