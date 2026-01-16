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
    st.info("Preencha a qualificação completa para gerar documentos prontos.")
    
    with st.container(border=True):
        st.subheader("👤 Dados do Contratante (Cliente)")
        
        # Linha 1
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome Completo")
        nacionalidade = c2.text_input("Nacionalidade", value="Brasileiro(a)")
        est_civil = c3.selectbox("Estado Civil", ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"])
        
        # Linha 2
        c4, c5, c6 = st.columns(3)
        prof = c4.text_input("Profissão")
        rg = c5.text_input("RG")
        cpf = c6.text_input("CPF")
        
        # Linha 3
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

    if st.button("GERAR CONTRATO + PROCURAÇÃO", use_container_width=True):
        if nome and cpf and obj:
            with st.spinner("Redigindo documentos com qualificação completa..."):
                # Monta a string de qualificação para o Prompt
                qualificacao = f"{nome}, {nacionalidade}, {est_civil}, {prof}, portador do RG nº {rg} e CPF nº {cpf}, residente e domiciliado em {end}, CEP {cep}, e-mail {email}"
                
                prompt = f"""
                Atue como advogado. Redija dois documentos formais em sequência:
                
                1. CONTRATO DE HONORÁRIOS ADVOCATÍCIOS.
                CONTRATANTE: {qualificacao}.
                CONTRATADO: LBA Advocacia (Sociedade de Advogados).
                OBJETO: {obj}.
                VALOR: R$ {val} ({forma_pag}).
                CLÁUSULAS: Padrão da OAB, foro da comarca do cliente.
                
                --- QUEBRA DE PÁGINA ---
                
                2. PROCURAÇÃO AD JUDICIA.
                OUTORGANTE: {qualificacao}.
                OUTORGADO: LBA Advocacia.
                PODERES: Gerais para o foro e Especiais para transigir, firmar acordos, receber e dar quitação.
                """
                
                res = tentar_gerar_conteudo(prompt, None)
                st.markdown(res)
                salvar_documento_memoria("Contrato+Proc", nome, res)
                st.download_button("Baixar Documentos", gerar_word(res), f"Contrato_{nome}.docx")
        else:
            st.warning("Preencha pelo menos Nome, CPF e Objeto para gerar.")

# --- CÁLCULOS ---
# --- CÁLCULOS ---
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
        st.markdown("#### ⚖️ Cálculos Cíveis Completos")
        
        # Criação das sub-abas para organizar as funcionalidades pedidas
        tab_divida, tab_banco, tab_imob, tab_causa, tab_hon = st.tabs([
            "Atualização de Dívidas", 
            "Bancário & Contratos", 
            "Imobiliário & Aluguel",
            "Valor da Causa (CPC)",
            "Honorários"
        ])
        
        # --- TAB 1: ATUALIZAÇÃO DE DÍVIDAS E LIQUIDAÇÃO ---
        with tab_divida:
            st.info("Correção Monetária + Juros de Mora + Danos (Liquidação)")
            
            c1, c2 = st.columns(2)
            val_origem = c1.number_input("Valor Original da Dívida/Indenização", value=0.0, format="%.2f", key="civ_val_origem")
            data_inicio = c2.date_input("Data do Evento/Vencimento", date(2023, 1, 1), key="civ_dt_ini")
            data_fim = date.today()
            
            # Cálculo de meses
            dias = (data_fim - data_inicio).days
            meses = dias // 30
            
            st.write(f"📅 Tempo decorrido: **{meses} meses** ({dias} dias)")
            
            c3, c4, c5 = st.columns(3)
            indice = c3.number_input("Índice Acumulado (Ex: 1.05 para 5%)", value=1.0, help="Consulte a tabela TJ/INPC/IGPM e insira o fator acumulado.", key="civ_indice")
            juros_tipo = c4.selectbox("Juros de Mora", ["1% ao mês (Simples)", "0.5% ao mês", "Selic", "Sem Juros"], key="civ_juros_tipo")
            multa_pct = c5.number_input("Multa (%)", value=0.0, key="civ_multa")
            
            st.markdown("---")
            st.markdown("**Adicionais (Liquidação de Sentença):**")
            k1, k2, k3 = st.columns(3)
            danos_morais = k1.number_input("Danos Morais", value=0.0, key="civ_dm")
            danos_materiais = k2.number_input("Lucros Cessantes/Emergentes", value=0.0, key="civ_lucros")
            hon_sucumb = k3.number_input("Honorários Sucumbenciais (%)", value=10.0, key="civ_sucumb")

            if st.button("CALCULAR ATUALIZAÇÃO", key="btn_calc_divida"):
                # 1. Correção Monetária
                valor_corrigido = val_origem * indice
                
                # 2. Juros
                val_juros = 0.0
                if juros_tipo == "1% ao mês (Simples)":
                    val_juros = valor_corrigido * (0.01 * meses)
                elif juros_tipo == "0.5% ao mês":
                    val_juros = valor_corrigido * (0.005 * meses)
                elif juros_tipo == "Selic":
                    val_juros = valor_corrigido * 0.15  # Estimativa fixa para exemplo
                
                # 3. Multa
                val_multa = valor_corrigido * (multa_pct / 100)
                
                # 4. Subtotal da Dívida Principal
                subtotal = valor_corrigido + val_juros + val_multa
                
                # 5. Adicionais
                total_geral = subtotal + danos_morais + danos_materiais
                val_honorarios = total_geral * (hon_sucumb / 100)
                total_final = total_geral + val_honorarios
                
                st.success(f"💰 TOTAL FINAL: R$ {total_final:,.2f}")
                
                # Tabela detalhada
                df_res = pd.DataFrame([
                    ("Principal Corrigido", f"R$ {valor_corrigido:,.2f}"),
                    (f"Juros ({meses} meses)", f"R$ {val_juros:,.2f}"),
                    ("Multa Contratual", f"R$ {val_multa:,.2f}"),
                    ("Danos Morais/Materiais", f"R$ {danos_morais + danos_materiais:,.2f}"),
                    ("Honorários Sucumbenciais", f"R$ {val_honorarios:,.2f}")
                ], columns=["Item", "Valor"])
                st.table(df_res)

        # --- TAB 2: BANCÁRIO & CONTRATOS ---
        with tab_banco:
            st.info("Revisional, Anatocismo e Financiamentos (SFH/Leasing)")
            
            b1, b2 = st.columns(2)
            divida_banc = b1.number_input("Valor Financiado/Empréstimo", value=50000.0, key="banc_valor")
            prazo_meses = b2.number_input("Prazo (Meses)", value=60, key="banc_prazo")
            
            b3, b4 = st.columns(2)
            taxa_mensal = b3.number_input("Taxa de Juros Mensal (%)", value=1.5, key="banc_taxa")
            sistema = b4.radio("Sistema de Amortização", ["Tabela Price (Juros Compostos)", "SAC", "Método de Gauss (Juros Simples - Tese Jurídica)"], key="banc_sistema")
            
            if st.button("SIMULAR REVISIONAL", key="btn_bancario"):
                i = taxa_mensal / 100
                n = prazo_meses
                
                # Cálculo Price (Composto)
                parcela_price = divida_banc * (i * (1+i)**n) / ((1+i)**n - 1)
                total_price = parcela_price * n
                
                # Cálculo Gauss (Simples - Tese Revisional)
                fator_gauss = (n * i) + 1
                parcela_gauss = (divida_banc * fator_gauss) / n 
                total_gauss = parcela_gauss * n
                
                # Cálculo SAC (Primeira Parcela)
                amort = divida_banc / n
                juros_sac = divida_banc * i
                parcela_sac = amort + juros_sac
                
                st.write("---")
                col_res1, col_res2 = st.columns(2)
                
                if sistema == "Tabela Price (Juros Compostos)":
                    col_res1.metric("Parcela Mensal (Price)", f"R$ {parcela_price:,.2f}")
                    col_res1.metric("Total ao Final", f"R$ {total_price:,.2f}")
                    st.warning("Este sistema utiliza capitalização de juros (Anatocismo).")
                    
                elif sistema == "Método de Gauss (Juros Simples - Tese Jurídica)":
                    col_res2.metric("Parcela Recalculada (Gauss)", f"R$ {parcela_gauss:,.2f}")
                    col_res2.metric("Total Recalculado", f"R$ {total_gauss:,.2f}")
                    col_res2.metric("Economia Estimada (Indébito)", f"R$ {total_price - total_gauss:,.2f}")
                    st.success("Cálculo utilizado para teses de afastamento de anatocismo.")
                    
                else: # SAC
                    st.metric("Primeira Parcela (SAC)", f"R$ {parcela_sac:,.2f}")
                    st.info("No SAC as parcelas são decrescentes.")

        # --- TAB 3: IMOBILIÁRIO ---
        with tab_imob:
            st.info("Reajuste de Aluguel, Despejo e Multas")
            acao_imob = st.radio("Tipo de Cálculo", ["Reajuste Anual", "Cobrança de Aluguéis Atrasados (Despejo)", "Multa por Rescisão Antecipada"], horizontal=True, key="imob_tipo")
            
            val_aluguel = st.number_input("Valor do Aluguel Atual", value=2000.0, key="imob_val")
            
            if acao_imob == "Reajuste Anual":
                idx_imob = st.number_input("Índice Acumulado (IGPM/IPCA) em %", value=4.5, key="imob_idx")
                if st.button("Calcular Novo Aluguel"):
                    novo_val = val_aluguel * (1 + idx_imob/100)
                    st.success(f"Novo Aluguel: R$ {novo_val:,.2f}")
            
            elif acao_imob == "Cobrança de Aluguéis Atrasados (Despejo)":
                meses_atraso = st.number_input("Meses em Atraso", value=3, key="imob_meses")
                multa_moratoria = st.checkbox("Aplicar Multa Moratória (10% ou 20%)", value=True, key="imob_check_multa")
                multa_pct_imob = 10.0 if multa_moratoria else 0.0
                hon_despejo = st.checkbox("Honorários Contratuais no Despejo (10-20%)", value=True, key="imob_hon")
                
                if st.button("Calcular Débito Total"):
                    sub_aluguel = val_aluguel * meses_atraso
                    val_multa_imob = sub_aluguel * (multa_pct_imob/100)
                    juros_imob = sub_aluguel * 0.01 * meses_atraso # 1% ao mês
                    
                    total_imob = sub_aluguel + val_multa_imob + juros_imob
                    if hon_despejo: total_imob *= 1.20 # +20%
                    
                    st.error(f"Total da Ação de Despejo: R$ {total_imob:,.2f}")
                    st.caption("Inclui: Parcelas vencidas + Multa moratória + Juros 1% a.m. + Honorários (se marcado)")

            elif acao_imob == "Multa por Rescisão Antecipada":
                st.caption("Cálculo Proporcional (Lei do Inquilinato)")
                multa_contrato = st.number_input("Valor da Multa Cheia (Ex: 3 aluguéis)", value=6000.0, key="imob_multa_cheia")
                prazo_total = st.number_input("Prazo Total do Contrato (meses)", value=30, key="imob_prazo_total")
                meses_cumpridos = st.number_input("Meses Cumpridos", value=10, key="imob_meses_cump")
                
                if st.button("Calcular Multa Proporcional"):
                    meses_restantes = prazo_total - meses_cumpridos
                    multa_devida = (multa_contrato / prazo_total) * meses_restantes
                    st.warning(f"Multa Devida: R$ {multa_devida:,.2f}")

        # --- TAB 4: VALOR DA CAUSA ---
        with tab_causa:
            st.info("Art. 292 CPC - Parcelas Vencidas e Vincendas")
            
            tipo_acao_causa = st.selectbox("Tipo de Ação", ["Cobrança / Indenizatória", "Alimentos", "Obrigação de Pagar (Vencidas + Vincendas)"], key="causa_tipo")
            
            if tipo_acao_causa == "Alimentos":
                mensalidade = st.number_input("Valor da Prestação Mensal", key="causa_alim")
                st.metric("Valor da Causa (12x)", f"R$ {mensalidade * 12:,.2f}")
            
            elif tipo_acao_causa == "Cobrança / Indenizatória":
                dano_material = st.number_input("Dano Material / Dívida", key="causa_mat")
                dano_moral = st.number_input("Dano Moral Pretendido", key="causa_moral")
                st.metric("Valor da Causa", f"R$ {dano_material + dano_moral:,.2f}")
                
            else: # Vencidas + Vincendas
                vencidas = st.number_input("Soma das Parcelas Vencidas (com juros/correção)", key="causa_venc")
                vincendas_val = st.number_input("Valor da Parcela Vincenda", key="causa_vinc_val")
                qtd_vincendas = st.number_input("Quantidade de Vincendas (Máx 12 p/ cálculo)", value=12, max_value=12, help="Art. 292 § 2º: Até uma prestação anual")
                
                if st.button("Calcular Valor da Causa"):
                    total_causa = vencidas + (vincendas_val * qtd_vincendas)
                    st.success(f"Valor da Causa: R$ {total_causa:,.2f}")

        # --- TAB 5: HONORÁRIOS ---
        with tab_hon:
            st.info("Cálculo de Honorários Advocatícios")
            base_calc = st.number_input("Base de Cálculo (Valor da Causa/Condenação/Proveito)", value=10000.0, key="hon_base")
            
            h1, h2 = st.columns(2)
            pct_contratual = h1.number_input("% Contratual", value=30.0, key="hon_pct_cont")
            pct_sucumbencia = h2.number_input("% Sucumbência", value=10.0, key="hon_pct_suc")
            
            if st.button("CALCULAR HONORÁRIOS", key="btn_hon"):
                val_cont = base_calc * (pct_contratual / 100)
                val_suc = base_calc * (pct_sucumbencia / 100)
                
                st.markdown(f"### 💼 Total: R$ {val_cont + val_suc:,.2f}")
                st.write(f"- Contratuais ({pct_contratual}%): **R$ {val_cont:,.2f}**")
                st.write(f"- Sucumbenciais ({pct_sucumbencia}%): **R$ {val_suc:,.2f}**")

    elif area_calc == "Família":
        st.markdown("#### 👨‍👩‍👧‍👦 Cálculo Avançado de Pensão Alimentícia (Trinômio)")
        st.caption("Baseado no Art. 1.694, §1º do Código Civil (Necessidade x Possibilidade x Proporcionalidade)")
        
        tab_fixacao, tab_revisao = st.tabs(["Fixação de Pensão", "Atualização/Revisão"])
        
        with tab_fixacao:
            # 1. POSSIBILIDADE (Rendas)
            st.markdown("##### 1. Possibilidade (Renda dos Pais)")
            c1, c2 = st.columns(2)
            renda_alimentante = c1.number_input("Renda Líquida do Alimentante (Quem paga)", value=3000.0, help="Salário menos descontos legais (INSS/IR).", key="fam_renda1")
            renda_guardiao = c2.number_input("Renda Líquida do Guardião (Quem cuida)", value=2000.0, help="Renda de quem mora com a criança.", key="fam_renda2")
            
            renda_total_pais = renda_alimentante + renda_guardiao
            if renda_total_pais > 0:
                prop_alimentante = (renda_alimentante / renda_total_pais) * 100
                st.progress(prop_alimentante / 100)
                st.caption(f"O Alimentante contribui com **{prop_alimentante:.1f}%** da renda familiar total.")
            else:
                prop_alimentante = 0

            # 2. NECESSIDADE (Despesas da Criança)
            st.markdown("---")
            st.markdown("##### 2. Necessidade (Despesas da Criança)")
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                gastos_diretos = st.number_input("Gastos Diretos (Escola, Saúde, Lazer)", value=800.0, help="Mensalidade escolar, plano de saúde, natação, etc.", key="fam_gasto_dir")
            with col_d2:
                gastos_moradia = st.number_input("Total Gastos da Casa (Aluguel, Luz, Água)", value=1500.0, help="Total das contas da casa onde a criança mora.", key="fam_gasto_casa")
                pessoas_casa = st.number_input("Total de Pessoas na Casa", value=3, min_value=2, key="fam_pessoas")
            
            # Rateio da moradia (Criança paga sua parte)
            parte_crianca_moradia = gastos_moradia / pessoas_casa
            necessidade_total = gastos_diretos + parte_crianca_moradia
            
            st.info(f"💰 Necessidade Mensal Apurada: **R$ {necessidade_total:,.2f}**")

            # 3. CÁLCULO FINAL
            st.markdown("---")
            if st.button("CALCULAR PENSÃO SUGERIDA", key="btn_fam_calc"):
                # A pensão deve ser a % da renda do pai aplicada sobre a necessidade do filho
                valor_sugerido = necessidade_total * (prop_alimentante / 100)
                
                # Checagem de segurança (Jurisprudência costuma teto de 30% da renda)
                teto_30 = renda_alimentante * 0.30
                
                c_res1, c_res2 = st.columns(2)
                
                c_res1.metric("Valor Sugerido (Proporcional)", f"R$ {valor_sugerido:,.2f}")
                c_res1.caption(f"Equivale a {valor_sugerido/renda_alimentante*100:.1f}% da renda do pagador.")
                
                color = "green" if valor_sugerido <= teto_30 else "red"
                c_res2.markdown(f"#### Teto de 30%: R$ {teto_30:,.2f}")
                
                if valor_sugerido > teto_30:
                    st.warning("⚠️ O valor proporcional ultrapassa 30% da renda do alimentante. O juiz pode fixar o teto de 30% (R$ " + f"{teto_30:,.2f}" + ") se houver risco à subsistência dele.")
                else:
                    st.success("✅ O valor está dentro de uma margem segura (abaixo de 30% da renda).")

        with tab_revisao:
            st.markdown("##### Atualização de Valor Defasado")
            val_antigo = st.number_input("Valor da Pensão Fixada", value=500.0, key="fam_val_antigo")
            indice_rev = st.number_input("Índice de Reajuste Anual (IGPM/INPC) %", value=4.5, key="fam_idx_rev")
            
            if st.button("ATUALIZAR VALOR", key="btn_fam_upd"):
                novo = val_antigo * (1 + indice_rev/100)
                st.success(f"Novo Valor: R$ {novo:,.2f}")

    elif area_calc == "Tributária":
        st.markdown("#### 🏛️ Cálculos e Teses Tributárias")
        
        tab_fed, tab_tese, tab_mora = st.tabs([
            "Atualização Débito Federal (CDA)", 
            "Tese do Século (PIS/COFINS)", 
            "Cálculo de Multa de Mora"
        ])
        
        # --- TAB 1: ATUALIZAÇÃO FEDERAL (SELIC) ---
        with tab_fed:
            st.info("Atualização pela Taxa SELIC (Lei 9.430/96)")
            st.caption("A SELIC engloba juros e correção monetária. Não deve ser cumulada com outro índice.")
            
            c1, c2 = st.columns(2)
            principal = c1.number_input("Valor Principal do Débito (R$)", value=10000.0, key="trib_principal")
            selic_acum = c2.number_input("Taxa SELIC Acumulada no Período (%)", value=15.5, help="Consulte a tabela da Receita Federal para o período.", key="trib_selic")
            
            c3, c4 = st.columns(2)
            multa_oficio = c3.number_input("Multa de Ofício/Punitiva (%)", value=75.0, help="Padrão: 75% em lançamentos de ofício.", key="trib_multa_oficio")
            encargo_legal = c4.checkbox("Incluir Encargo Legal (20% - DL 1.025/69)?", value=True, key="trib_encargo")
            
            if st.button("CALCULAR DÉBITO FISCAL", key="btn_trib_cda"):
                val_juros = principal * (selic_acum / 100)
                val_multa = principal * (multa_oficio / 100)
                base_parcial = principal + val_juros + val_multa
                
                val_encargo = 0
                if encargo_legal:
                    val_encargo = base_parcial * 0.20
                
                total_divida = base_parcial + val_encargo
                
                st.write("---")
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("Valor Atualizado (Principal + SELIC)", f"R$ {principal + val_juros:,.2f}")
                col_res2.metric("TOTAL DA CDA (Com Encargos)", f"R$ {total_divida:,.2f}")
                
                st.table(pd.DataFrame([
                    ("Principal", f"R$ {principal:,.2f}"),
                    ("Juros (SELIC)", f"R$ {val_juros:,.2f}"),
                    ("Multa de Ofício", f"R$ {val_multa:,.2f}"),
                    ("Encargo Legal (20%)", f"R$ {val_encargo:,.2f}")
                ], columns=["Item", "Valor"]))

        # --- TAB 2: TESE DO SÉCULO (RECUPERAÇÃO) ---
        with tab_tese:
            st.info("Estimativa de Crédito: Exclusão do ICMS da Base do PIS/COFINS (RE 574.706/STF)")
            
            faturamento = st.number_input("Faturamento Mensal Médio (R$)", value=100000.0, key="tese_fat")
            
            t1, t2, t3 = st.columns(3)
            aliq_icms = t1.number_input("Alíquota ICMS (%)", value=18.0, key="tese_icms")
            aliq_pis = t2.number_input("Alíquota PIS (%)", value=1.65, key="tese_pis")
            aliq_cofins = t3.number_input("Alíquota COFINS (%)", value=7.60, key="tese_cofins")
            
            meses_recup = st.slider("Meses para Recuperar (Ex: 60 meses = 5 anos)", 12, 60, 60, key="tese_meses")
            
            if st.button("SIMULAR CRÉDITO A RECUPERAR", key="btn_trib_tese"):
                # 1. Cálculo do PIS/COFINS Pago (Base Cheia)
                total_aliq = (aliq_pis + aliq_cofins) / 100
                pago_mensal = faturamento * total_aliq
                
                # 2. Cálculo da Base Correta (Sem ICMS)
                valor_icms = faturamento * (aliq_icms / 100)
                base_correta = faturamento - valor_icms
                devido_mensal = base_correta * total_aliq
                
                # 3. Diferença (Crédito)
                credito_mensal = pago_mensal - devido_mensal
                credito_total = credito_mensal * meses_recup
                
                st.success(f"💰 Crédito Estimado Total: R$ {credito_total:,.2f}")
                st.write(f"Pagamento Mensal Indevido: **R$ {credito_mensal:,.2f}**")
                st.warning("Nota: Este é um cálculo estimativo linear. O cálculo real exige análise nota a nota.")

        # --- TAB 3: MULTA DE MORA ---
        with tab_mora:
            st.info("Cálculo de Multa de Mora (Atraso de Pagamento)")
            st.caption("Regra Federal: 0,33% ao dia, limitado a 20% (a partir do 61º dia).")
            
            val_guia = st.number_input("Valor da Guia (Principal)", value=1000.0, key="mora_val")
            dias_atraso = st.number_input("Dias de Atraso", value=15, min_value=1, key="mora_dias")
            
            if st.button("CALCULAR GUIA EM ATRASO", key="btn_trib_mora"):
                # Regra: 0.33% por dia, teto 20%
                percentual_multa = dias_atraso * 0.33
                if percentual_multa > 20.0:
                    percentual_multa = 20.0
                
                valor_multa = val_guia * (percentual_multa / 100)
                total_pagar = val_guia + valor_multa
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Percentual Aplicado", f"{percentual_multa:.2f}%")
                col_m2.metric("Valor da Multa", f"R$ {valor_multa:,.2f}")
                st.success(f"Valor para Pagamento: R$ {total_pagar:,.2f}")

    elif area_calc == "Criminal":
        p_min = st.number_input("Pena Mínima")
        p_max = st.number_input("Pena Máxima")
        c = st.slider("Circunstâncias Ruins", 0, 8)
        if st.button("CALCULAR PENA"): st.error(f"Base: {p_min + ((p_max-p_min)/8 * c):.1f} anos")
            
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





