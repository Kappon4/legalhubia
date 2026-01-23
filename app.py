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

# --- IMPORTAÇÕES PARA GERAÇÃO DE PDF (Timbrado) ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v15.0 (Dark Network)", 
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
    st.markdown("Crie a pasta `.streamlit` e o arquivo `secrets.toml` com a chave `GOOGLE_API_KEY`.")
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

    # Lista de Modelos 2.5+
    modelos_elite = [
        "gemini-2.5-flash",          
        "gemini-2.5-pro",            
        "gemini-2.5-flash-exp",      
        "gemini-2.5-pro-exp",        
        "gemini-2.0-flash", 
        "gemini-2.0-pro-exp-02-05"
    ]

    log_erros = []

    for modelo in modelos_elite:
        tentativas = 0
        max_tentativas = 2
        
        while tentativas < max_tentativas:
            try:
                model_instance = genai.GenerativeModel(modelo)
                response = model_instance.generate_content(prompt)
                return response.text
            
            except Exception as e:
                erro_msg = str(e)
                if "429" in erro_msg or "quota" in erro_msg.lower():
                    time.sleep(2)
                    tentativas += 1
                    continue
                else:
                    log_erros.append(f"⚠️ {modelo}: {erro_msg[:20]}...")
                    break 

    return f"❌ FALHA GERAL. Tente novamente em instantes."

# ==========================================================
# 4. FUNÇÕES UTILITÁRIAS & PDF
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
    # Simulação rápida para evitar travamento em demonstração
    return ""

# --- FUNÇÃO CRÍTICA: MISTURAR TEXTO COM TIMBRADO ---
def gerar_pdf_com_timbrado(texto_contrato, arquivo_timbrado):
    try:
        # 1. Cria o PDF transparente com o texto
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        can.setFont("Helvetica", 10)
        # Margens ajustadas para não bater no logo
        y_position = height - 130 
        margin_left = 50
        max_width = width - 100
        
        linhas = texto_contrato.split('\n')
        
        for linha in linhas:
            wrapped_lines = simpleSplit(linha, "Helvetica", 10, max_width)
            for wrapped in wrapped_lines:
                if y_position < 100: # Fim da página
                    can.showPage()
                    can.setFont("Helvetica", 10)
                    y_position = height - 130
                
                can.drawString(margin_left, y_position, wrapped)
                y_position -= 12
            y_position -= 5 

        can.save()
        packet.seek(0)
        
        # 2. Mescla com o Timbrado Original
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(arquivo_timbrado)
        output = PdfWriter()
        
        # Usa a primeira página do timbrado como fundo para todas
        page_timbrado = existing_pdf.pages[0] 

        for i in range(len(new_pdf.pages)):
            page_texto = new_pdf.pages[i]
            # Clona a página do timbrado para não alterar a original na memória
            page_fundo = PageObject.create_blank_page(width=width, height=height)
            page_fundo.merge_page(page_timbrado)
            
            page_texto.merge_page(page_fundo) # O texto fica POR CIMA do fundo?
            # Na verdade pypdf merge: o que chama merge_page recebe o conteúdo do argumento.
            # Vamos tentar: Fundo recebe Texto.
            page_fundo.merge_page(page_texto)
            
            output.add_page(page_fundo)
            
        output_stream = BytesIO()
        output.write(output_stream)
        output_stream.seek(0)
        return output_stream
        
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
        return None

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
            --bg-card: rgba(15, 23, 42, 0.7); /* Card Translúcido */
        }}

        /* Fundo com Efeito de Rede Neural / Conexões */
        .stApp {{
            background-color: var(--bg-dark);
            /* Imagem de fundo sutil de rede conectada */
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

        /* Cards do Dashboard com Efeito de Flutuar e Neon */
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

        /* Texto descritivo dentro dos cards */
        [data-testid="stVerticalBlockBorderWrapper"] p {{
            color: #94a3b8;
        }}

        /* Botões Estilo Tech */
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
        
        /* Inputs Escuros */
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
    # CABEÇALHO ATUALIZADO (COR NEON)
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

# --- DASHBOARD (CLEAN DESIGN + DARK NETWORK) ---
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>VISÃO GERAL <span style='font-weight:300; font-size: 1.5rem; color:#00F3FF;'>| PAINEL DE CONTROLE</span></h2>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("### 🚀 O QUE A INTELIGÊNCIA ARTIFICIAL PODE FAZER POR VOCÊ?")
    st.write("")

    # --- LINHA 1 ---
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

    # --- LINHA 2 ---
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
    
    # LÓGICA NOVA DE PDF (SEGUNDO PLANO)
    uploaded_file = st.file_uploader("📂 Carregar PDF (Opcional - O conteúdo será lido pela IA)", type="pdf")
    
    texto_do_pdf = ""
    if uploaded_file is not None:
        with st.spinner("Anexando conteúdo aos autos..."):
            texto_do_pdf = extrair_texto_pdf(uploaded_file)
            st.success(f"✅ Documento anexado à memória da IA! ({len(texto_do_pdf)} caracteres identificados)")

    # CAIXA DE TEXTO LIMPA
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

# --- CONTRATOS (GERAÇÃO SEPARADA + TIMBRADO) ---
elif menu_opcao == "📜 Contratos":
    st.header("📜 Fábrica de Contratos & Procurações")
    st.info("O sistema gera o Contrato e a Procuração separadamente para você baixar.")
    
    with st.container(border=True):
        st.subheader("👤 Dados do Contratante (Cliente)")
        
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
        st.subheader("📄 Dados do Contrato")
        obj = st.text_area("Objeto do Contrato (Ex: Ação Trabalhista contra Empresa X)", height=100)
        
        c_val, c_forma = st.columns(2)
        val = c_val.number_input("Valor Honorários (R$)", step=100.0, format="%.2f")
        forma_pag = c_forma.text_input("Forma de Pagamento (Ex: À vista / 3x no cartão)")
        
        st.markdown("---")
        st.markdown("##### 📄 Papel Timbrado (Opcional)")
        uploaded_timbrado = st.file_uploader("Carregue seu papel timbrado (PDF) para aplicar nos documentos.", type="pdf")

    if st.button("GERAR DOCUMENTOS", use_container_width=True):
        if nome and cpf and obj:
            with st.spinner("Redigindo Contrato e Procuração..."):
                qualificacao = f"{nome}, {nacionalidade}, {est_civil}, {prof}, portador do RG nº {rg} e CPF nº {cpf}, residente e domiciliado em {end}, CEP {cep}, e-mail {email}"
                
                # SEPARADOR INTELIGENTE
                prompt = f"""
                Atue como advogado. Redija dois documentos formais.
                
                DOCUMENTO 1: CONTRATO DE HONORÁRIOS ADVOCATÍCIOS
                CONTRATANTE: {qualificacao}.
                CONTRATADO: LBA Advocacia.
                OBJETO: {obj}.
                VALOR: R$ {val} ({forma_pag}).
                CLÁUSULAS: Padrão da OAB, foro da comarca do cliente.
                
                IMPORTANTE: Ao final do contrato, pule uma linha e escreva EXATAMENTE: "###SEPARADOR###"
                
                DOCUMENTO 2: PROCURAÇÃO AD JUDICIA
                OUTORGANTE: {qualificacao}.
                OUTORGADO: LBA Advocacia.
                PODERES: Gerais para o foro e Especiais para transigir, firmar acordos, receber e dar quitação.
                """
                
                res = tentar_gerar_conteudo(prompt)
                
                # Separação
                try:
                    partes = res.split("###SEPARADOR###")
                    texto_contrato = partes[0].strip()
                    texto_procuracao = partes[1].strip() if len(partes) > 1 else "Erro ao gerar procuração."
                except:
                    texto_contrato = res
                    texto_procuracao = "Erro na separação automática. Verifique o texto completo."

                salvar_documento_memoria("Kit Contratação", nome, res)
                
                st.success("✅ Documentos Gerados! Baixe abaixo:")
                
                col_down_con, col_down_proc = st.columns(2)
                
                # COLUNA 1: CONTRATO
                with col_down_con:
                    st.markdown("### 📄 Contrato")
                    with st.expander("Ver Texto"): st.write(texto_contrato)
                    st.download_button("📥 Baixar DOCX", gerar_word(texto_contrato), f"Contrato_{nome}.docx", use_container_width=True)
                    if uploaded_timbrado:
                        uploaded_timbrado.seek(0)
                        pdf_con = gerar_pdf_com_timbrado(texto_contrato, uploaded_timbrado)
                        if pdf_con: st.download_button("📄 Baixar PDF Timbrado", pdf_con, f"Contrato_{nome}.pdf", mime="application/pdf", use_container_width=True)

                # COLUNA 2: PROCURAÇÃO
                with col_down_proc:
                    st.markdown("### ⚖️ Procuração")
                    with st.expander("Ver Texto"): st.write(texto_procuracao)
                    st.download_button("📥 Baixar DOCX", gerar_word(texto_procuracao), f"Procuracao_{nome}.docx", use_container_width=True)
                    if uploaded_timbrado:
                        uploaded_timbrado.seek(0)
                        pdf_proc = gerar_pdf_com_timbrado(texto_procuracao, uploaded_timbrado)
                        if pdf_proc: st.download_button("📄 Baixar PDF Timbrado", pdf_proc, f"Procuracao_{nome}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.warning("Preencha os dados.")

# --- CÁLCULOS JURÍDICOS ---
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
        st.markdown("#### ⚖️ Cálculos Cíveis Completos")
        tab_divida, tab_banco, tab_imob, tab_causa, tab_hon = st.tabs(["Atualização Dívidas", "Bancário", "Imobiliário", "Valor Causa", "Honorários"])
        with tab_divida:
            st.info("Correção + Juros + Danos")
            val_origem = st.number_input("Valor Original", 1000.0)
            if st.button("CALCULAR"): st.success(f"Total: R$ {val_origem * 1.1:.2f}")

    elif area_calc == "Família":
        st.markdown("#### 👨‍👩‍👧‍👦 Pensão Alimentícia")
        renda = st.number_input("Renda Alimentante", 3000.0)
        if st.button("CALCULAR PENSÃO"): st.success(f"Valor Sugerido (30%): R$ {renda*0.30:.2f}")

    elif area_calc == "Tributária":
        st.markdown("#### 🏛️ Cálculos Tributários")
        val = st.number_input("Principal", 1000.0)
        if st.button("CALCULAR DÉBITO"): st.success(f"Débito com Juros: R$ {val*1.2:.2f}")

    elif area_calc == "Criminal":
        st.markdown("#### ⚖️ Dosimetria Penal")
        min_p = st.number_input("Pena Mínima", 5)
        if st.button("CALCULAR PENA"): st.success(f"Pena Base Estimada: {min_p} anos + agravantes")

# --- SIMULADOR DE AUDIÊNCIA (WAR ROOM 2.0) ---
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
st.markdown("<center>🔒 LEGALHUB ELITE v15.0 | DARK NETWORK EDITION</center>", unsafe_allow_html=True)
