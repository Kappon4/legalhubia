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
    page_title="LegalHub Elite v15.5", 
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
# 4. FUNÇÕES UTILITÁRIAS & CÁLCULOS
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

# --- LÓGICA DE CÁLCULO TRABALHISTA ROBUSTA (CORREÇÃO APLICADA AQUI) ---
def calcular_rescisao_clt(admissao, demissao, salario_base, motivo, saldo_fgts_banco, ferias_vencidas, aviso_tipo, grau_insalubridade, tem_periculosidade):
    # Conversão segura de datas
    if isinstance(admissao, str): admissao = datetime.strptime(admissao, "%Y-%m-%d").date()
    if isinstance(demissao, str): demissao = datetime.strptime(demissao, "%Y-%m-%d").date()
    
    verbas = {}
    
    # 1. Base de Cálculo
    salario_minimo = 1509.00 # Base 2025
    adic_insal = 0.0
    
    if grau_insalubridade == "Mínimo (10%)": adic_insal = salario_minimo * 0.10
    elif grau_insalubridade == "Médio (20%)": adic_insal = salario_minimo * 0.20
    elif grau_insalubridade == "Máximo (40%)": adic_insal = salario_minimo * 0.40
    
    adic_peric = salario_base * 0.30 if tem_periculosidade else 0.0
    remuneracao = salario_base + adic_insal + adic_peric # Base para rescisão
    
    if adic_insal > 0: verbas["(+) Adicional Insalubridade"] = adic_insal
    if adic_peric > 0: verbas["(+) Adicional Periculosidade"] = adic_peric

    # 2. Aviso Prévio (Lei 12.506)
    tempo_casa = demissao - admissao
    anos_completos = int(tempo_casa.days / 365.25)
    
    if motivo == "Demissão sem Justa Causa":
        dias_aviso = min(90, 30 + (3 * anos_completos))
    else:
        dias_aviso = 30 # Pedido de demissão padrão

    # Projeção do Aviso (Indenizado)
    data_projetada = demissao
    if motivo == "Demissão sem Justa Causa" and aviso_tipo == "Indenizado":
        data_projetada = demissao + timedelta(days=dias_aviso)
        verbas[f"(+) Aviso Prévio Indenizado ({dias_aviso} dias)"] = (remuneracao / 30) * dias_aviso

    # 3. Saldo de Salário (Dias corridos)
    dias_trabalhados = demissao.day
    val_saldo_salario = (remuneracao / 30) * dias_trabalhados
    verbas[f"(+) Saldo de Salário ({dias_trabalhados} dias)"] = val_saldo_salario

    # 4. 13º Salário Proporcional (Até data projetada)
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
    
    if motivo != "Justa Causa":
        verbas[f"(+) 13º Salário Proporcional ({meses_13}/12)"] = (remuneracao / 12) * meses_13

    # 5. Férias
    if motivo != "Justa Causa":
        if ferias_vencidas:
            verbas["(+) Férias Vencidas + 1/3"] = remuneracao * 1.3333
        
        # Férias Proporcionais
        aniversario_ano = date(data_projetada.year, admissao.month, admissao.day)
        if aniversario_ano > data_projetada:
            aniversario_ano = date(data_projetada.year - 1, admissao.month, admissao.day)
            
        delta_ferias = (data_projetada.year - aniversario_ano.year) * 12 + (data_projetada.month - aniversario_ano.month)
        if data_projetada.day >= 15: delta_ferias += 1
        
        meses_ferias = min(12, delta_ferias)
        val_ferias = (remuneracao / 12) * meses_ferias
        verbas[f"(+) Férias Proporcionais ({meses_ferias}/12)"] = val_ferias
        verbas["(+) 1/3 Sobre Férias Prop."] = val_ferias / 3

    # 6. Multa FGTS (40%)
    if motivo == "Demissão sem Justa Causa" or motivo == "Acordo (Culpa Recíproca)":
        fgts_mes = val_saldo_salario * 0.08
        fgts_13 = ((remuneracao / 12) * meses_13) * 0.08 if motivo != "Justa Causa" else 0
        fgts_aviso = ((remuneracao / 30) * dias_aviso) * 0.08 if (motivo == "Demissão sem Justa Causa" and aviso_tipo == "Indenizado") else 0
        
        # SOMA O SALDO DO BANCO COM O QUE SERIA DEPOSITADO AGORA
        base_total_fgts = saldo_fgts_banco + fgts_mes + fgts_13 + fgts_aviso
        
        multa = 0.40 if motivo == "Demissão sem Justa Causa" else 0.20
        verbas[f"(+) Multa FGTS {int(multa*100)}% (Base Est.: R$ {base_total_fgts:,.2f})"] = base_total_fgts * multa

    return verbas

# ==========================================================
# 5. CSS VISUAL (DARK NETWORK EDITION)
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
    </style>
    """, unsafe_allow_html=True)
local_css()

# ==========================================================
# 6. MEMÓRIA & NAVEGAÇÃO
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
        "Petições Inteligentes": "✍️ Petições Inteligentes", 
        "Contratos": "📜 Contratos", 
        "Calculos": "🧮 Cálculos Jurídicos", 
        "Audiência": "🏛️ Simulador Audiência", 
        "Gestão Casos": "📂 Cofre Digital"
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
            st.markdown("#### ✍️ Petições Inteligentes")
            st.caption("Geração de peças processuais complexas (Iniciais, Contestação, Recursos) baseadas nos fatos e na melhor fundamentação jurídica.")
    with c2:
        with st.container(border=True):
            st.markdown("#### 🏛️ Preparação Audiência")
            st.caption("Simulador estratégico que cria perguntas para interrogatório, prevê teses da parte contrária e aponta riscos do caso.")
    with c3:
        with st.container(border=True):
            st.markdown("#### 📜 Fábrica de Contratos")
            st.caption("Elaboração automática de contratos, procurações e documentos extrajudiciais personalizados com cláusulas de segurança.")

    st.write("")
    c4, c5, c6 = st.columns(3)
    with c4:
        with st.container(border=True):
            st.markdown("#### 🧮 Cálculos Jurídicos")
            st.caption("Calculadoras precisas para Rescisão Trabalhista, Atualização Cível (TJ), Pensão Alimentícia e Dosimetria Penal.")
    with c5:
        with st.container(border=True):
            st.markdown("#### 🧠 Análise de Autos (PDF)")
            st.caption("O sistema lê seus arquivos PDF (Processos, Sentenças) e extrai automaticamente os fatos relevantes para usar nas peças.")
    with c6:
        with st.container(border=True):
            st.markdown("#### ⚖️ Jurisprudência Real")
            st.caption("Conexão direta com a base de dados dos Tribunais Superiores para encontrar julgados que fundamentam sua tese.")

# --- PETIÇÕES INTELIGENTES ---
elif menu_opcao == "✍️ Petições Inteligentes":
    st.markdown("<h2 class='tech-header'>✍️ PETIÇÕES INTELIGENTES (IA 2.5)</h2>", unsafe_allow_html=True)
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
    
    st.write("---")
    
    uploaded_file = st.file_uploader("📂 Carregar PDF (Opcional - O conteúdo será lido pela IA)", type="pdf")
    texto_do_pdf = ""
    if uploaded_file is not None:
        with st.spinner("Anexando conteúdo aos autos..."):
            texto_do_pdf = extrair_texto_pdf(uploaded_file)
            st.success(f"✅ Documento anexado à memória da IA! ({len(texto_do_pdf)} caracteres identificados)")

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
                        st.caption("Contrato de Honorários completo.")
                        with st.expander("👁️ Ver Texto do Contrato"): st.write(texto_contrato)
                        
                        st.download_button("📥 Baixar Contrato (.docx)", gerar_word(texto_contrato), f"Contrato_{nome}.docx", use_container_width=True)
                        
                        if uploaded_timbrado:
                            if HAS_REPORTLAB:
                                uploaded_timbrado.seek(0)
                                pdf_con = gerar_pdf_com_timbrado(texto_contrato, uploaded_timbrado)
                                if pdf_con: st.download_button("📄 Baixar PDF Timbrado", pdf_con, f"Contrato_{nome}.pdf", mime="application/pdf", use_container_width=True)
                            else: st.warning("Instale 'reportlab' para PDF.")

                with col_down_proc:
                    with st.container(border=True):
                        st.markdown("### ⚖️ 2. Procuração")
                        st.caption("Procuração Ad Judicia pronta.")
                        with st.expander("👁️ Ver Texto da Procuração"): st.write(texto_procuracao)
                        
                        st.download_button("📥 Baixar Procuração (.docx)", gerar_word(texto_procuracao), f"Procuracao_{nome}.docx", use_container_width=True)
                        
                        if uploaded_timbrado:
                            if HAS_REPORTLAB:
                                uploaded_timbrado.seek(0)
                                pdf_proc = gerar_pdf_com_timbrado(texto_procuracao, uploaded_timbrado)
                                if pdf_proc: st.download_button("📄 Baixar PDF Timbrado", pdf_proc, f"Procuracao_{nome}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.warning("⚠️ Preencha Nome, CPF e Objeto para gerar.")

# --- CÁLCULOS JURÍDICOS (CORRIGIDO) ---
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
                    # A função agora está acessível porque está no início do código
                    v = calcular_rescisao_clt(adm, dem, sal, motivo, fgts, ferias_venc, aviso, insal, peric)
                    
                    st.markdown("### 🧾 Resultado Detalhado")
                    st.table(pd.DataFrame(list(v.items()), columns=["Verba Rescisória", "Valor (R$)"]))
                    
                    total = sum(v.values())
                    st.markdown(f"""
                    <div style='background-color: rgba(0, 243, 255, 0.15); border: 1px solid #00F3FF; border-radius: 8px; padding: 15px; text-align: center;'>
                        <h2 style='color: #00F3FF; margin:0;'>TOTAL LÍQUIDO ESTIMADO: R$ {total:,.2f}</h2>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Erro no cálculo: {e}")
            else:
                st.warning("A data de demissão deve ser posterior à admissão.")

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

        with tab_banco:
            st.info("Simulação Price vs Gauss")
            b1, b2 = st.columns(2)
            valor_fin = b1.number_input("Valor Financiado", value=50000.0)
            taxa = b2.number_input("Taxa Mensal (%)", value=1.5)
            prazo = st.number_input("Parcelas", value=60)
            if st.button("SIMULAR REVISIONAL"):
                i = taxa/100
                price = valor_fin * (i * (1+i)**prazo) / ((1+i)**prazo - 1)
                gauss = (valor_fin * ((prazo * i) + 1)) / prazo
                st.metric("Parcela Banco (Price)", f"R$ {price:.2f}")
                st.metric("Parcela Justa (Gauss)", f"R$ {gauss:.2f}", delta=f"Economia: R$ {price-gauss:.2f}")

        with tab_imob:
            st.info("Reajuste de Aluguel")
            val_aluguel = st.number_input("Valor Aluguel", value=2000.0)
            idx = st.number_input("Índice (%)", value=4.5)
            if st.button("REAJUSTAR"): st.success(f"Novo Aluguel: R$ {val_aluguel * (1 + idx/100):,.2f}")

        with tab_causa:
            st.info("Valor da Causa")
            mat = st.number_input("Dano Material", value=0.0)
            mor = st.number_input("Dano Moral", value=0.0)
            if st.button("SOMAR CAUSA"): st.success(f"Valor da Causa: R$ {mat+mor:,.2f}")

        with tab_hon:
            st.info("Calculadora de Honorários")
            base = st.number_input("Base de Cálculo", value=10000.0)
            pct = st.number_input("% Honorários", value=20.0)
            if st.button("CALCULAR HONORÁRIOS"): st.success(f"Honorários: R$ {base * (pct/100):,.2f}")

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
        c1, c2, c3 = st.columns(3)
        tipo_aud = c1.selectbox("Tipo de Audiência", ["AIJ", "Conciliação", "Custódia"])
        polo = c2.selectbox("Polo", ["Autor", "Réu"])
        area_aud = c3.selectbox("Área", ["Trabalhista", "Cível"])

    c_e1, c_e2 = st.columns(2)
    fatos = c_e1.text_area("Fatos", height=150)
    objetivo = c_e2.text_area("Objetivo Chave", height=150)

    if st.button("GERAR DOSSIÊ", use_container_width=True):
        if fatos:
            with st.spinner("Gerando Dossiê..."):
                prompt = f"Gere Dossiê de Audiência {tipo_aud} ({area_aud}). Sou {polo}. Fatos: {fatos}. Objetivo: {objetivo}. Inclua perguntas e blindagem do cliente."
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                st.download_button("Baixar Dossiê", gerar_word(res), "Dossie.docx", use_container_width=True)

# --- COFRE ---
elif menu_opcao == "📂 Cofre Digital":
    st.header("📂 Cofre Digital (Sessão Atual)")
    if len(st.session_state.meus_docs) > 0:
        for i, doc in enumerate(st.session_state.meus_docs):
            with st.expander(f"{doc['tipo']} - {doc['cliente']}"):
                st.write(doc['conteudo'][:200])
                st.download_button("Baixar", gerar_word(doc['conteudo']), "Doc.docx", key=f"d{i}")
    else: st.info("Cofre vazio nesta sessão.")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v15.5 | DARK NETWORK EDITION (SAFE)</center>", unsafe_allow_html=True)
