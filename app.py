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
import os

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL - CYBER THEME
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v10.0", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================================
# 2. AUTOMAÇÃO DE ACESSO (SECRETS)
# ==========================================================
# O Streamlit Cloud vai injetar a senha aqui automaticamente
try:
    API_KEY_FINAL = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ ERRO: Chave de API não configurada. Vá nas configurações do Streamlit Cloud > Secrets e adicione a GOOGLE_API_KEY.")
    st.stop()

# ==========================================================
# 3. IA COM SISTEMA DE CASCATA (ANTI-FALHA 429)
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

def tentar_gerar_conteudo(prompt, ignored_param=None):
    chave = API_KEY_FINAL
    if not chave: return "⚠️ Chave API inválida."
    
    genai.configure(api_key=chave)

    # --- LISTA DE CASCATA (FALLBACK) ---
    # Se o primeiro falhar (cota), ele pula pro segundo imediatamente.
    # 1.5 Flash: Maior cota gratuita (15 RPM / 1500 RPD)
    # 1.5 Pro: Cota menor, mas serve de backup (2 RPM / 50 RPD)
    # 2.0 Flash: Cota instável (Experimental), fica por último
    modelos_cascata = [
        "gemini-1.5-flash", 
        "gemini-1.5-pro", 
        "gemini-2.0-flash",
        "gemini-1.0-pro"
    ]

    erros_acumulados = []

    for modelo in modelos_cascata:
        try:
            # Tenta instanciar e gerar com o modelo atual da lista
            model_instance = genai.GenerativeModel(modelo)
            response = model_instance.generate_content(prompt)
            return response.text # Se der certo, retorna e encerra a função
            
        except Exception as e:
            erro_msg = str(e)
            # Se for erro de cota (429), apenas loga e tenta o próximo
            if "429" in erro_msg or "quota" in erro_msg.lower():
                erros_acumulados.append(f"{modelo}: Cota cheia")
                continue # PULA PARA O PRÓXIMO MODELO DA LISTA
            else:
                # Se for outro erro (ex: modelo não existe), também pula
                erros_acumulados.append(f"{modelo}: {erro_msg}")
                continue

    # Se saiu do loop, nenhum modelo funcionou
    return f"❌ TODOS OS MODELOS FALHARAM. Detalhes: {'; '.join(erros_acumulados)}. Tente novamente em 2 minutos."

# ==========================================================
# 4. CÁLCULO TRABALHISTA COMPLETO
# ==========================================================
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
# 5. CSS VISUAL (CYBER FUTURE)
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
# 7. TELAS DO SISTEMA
# ==========================================================

# --- DASHBOARD ---
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| CASCATA MODE</span></h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("DOCS NA SESSÃO", len(st.session_state.meus_docs))
    c2.metric("STATUS", "Blindado (Anti-429)")
    c3.metric("PLANO", "FULL ACCESS")
    
    st.write("")
    st.info("💡 Dica: Agora o sistema tenta 4 modelos diferentes automaticamente antes de falhar.")
    
    st.subheader("🛠️ CENTRAL DE COMANDO")
    r1, r2, r3 = st.columns(3)
    with r1:
        if st.button("✍️ NOVA PETIÇÃO", use_container_width=True): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    with r2:
        if st.button("🧮 NOVO CÁLCULO", use_container_width=True): st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"; st.rerun()
    with r3:
        if st.button("📜 NOVO CONTRATO", use_container_width=True): st.session_state.navegacao_override = "📜 Contratos"; st.rerun()

# --- REDATOR IA ---
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
            with st.spinner("Pesquisando nos Tribunais e Redigindo..."):
                ctx = ""
                if busca_real: ctx = buscar_contexto_juridico(f"{tipo} {fatos}", area)
                
                prompt = f"Advogado {area}. Redija {tipo}. Cliente: {cli} vs {adv}. Fatos: {fatos}. {ctx}. Cite leis e jurisprudência se houver."
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                if "❌" not in res:
                    salvar_documento_memoria(tipo, cli, res)
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")

# --- CONTRATOS ---
elif menu_opcao == "📜 Contratos":
    st.header("📜 Fábrica de Contratos & Procurações")
    st.info("Preencha a qualificação completa para gerar documentos prontos.")
    
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

    if st.button("GERAR CONTRATO + PROCURAÇÃO", use_container_width=True):
        if nome and cpf and obj:
            with st.spinner("Redigindo documentos com qualificação completa..."):
                qualificacao = f"{nome}, {nacionalidade}, {est_civil}, {prof}, portador do RG nº {rg} e CPF nº {cpf}, residente e domiciliado em {end}, CEP {cep}, e-mail {email}"
                
                prompt = f"""
                Atue como advogado. Redija dois documentos formais em sequência:
                
                1. CONTRATO DE HONORÁRIOS ADVOCATÍCIOS.
                CONTRATANTE: {qualificacao}.
                CONTRATADO: LBA Advocacia.
                OBJETO: {obj}.
                VALOR: R$ {val} ({forma_pag}).
                CLÁUSULAS: Padrão da OAB, foro da comarca do cliente.
                
                --- QUEBRA DE PÁGINA ---
                
                2. PROCURAÇÃO AD JUDICIA.
                OUTORGANTE: {qualificacao}.
                OUTORGADO: LBA Advocacia.
                PODERES: Gerais para o foro e Especiais para transigir, firmar acordos, receber e dar quitação.
                """
                
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                salvar_documento_memoria("Contrato+Proc", nome, res)
                st.download_button("Baixar Documentos", gerar_word(res), f"Contrato_{nome}.docx")
        else:
            st.warning("Preencha pelo menos Nome, CPF e Objeto para gerar.")

# --- CÁLCULOS JURÍDICOS ---
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Calculadoras Jurídicas")
    area_calc = st.selectbox("Área", ["Trabalhista (CLT)", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    
    if area_calc == "Trabalhista (CLT)":
        st.subheader("Rescisão CLT + Adicionais")
        c1, c2, c3 = st.columns(3)
        adm = c1.date_input("Admissão", date(2022,1,1))
        dem = c2.date_input("Demissão", date.today())
        motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa"])
        sal = st.number_input("Salário", value=2000.0)
        
        if st.button("CALCULAR TRABALHISTA"):
            if dem > adm:
                v = calcular_rescisao_completa(adm, dem, sal, motivo, 0, False, "Trabalhado", "Não", False)
                st.table(pd.DataFrame(list(v.items()), columns=["Verba", "Valor"]))
                st.success(f"Total: R$ {sum(v.values()):,.2f}")

# --- SIMULADOR DE AUDIÊNCIA ---
elif menu_opcao == "🏛️ Simulador Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ WAR ROOM: ESTRATÉGIA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
    contexto = st.text_area("Resumo do conflito:", height=300)
    
    if st.button("GERAR ESTRATÉGIA DE GUERRA", use_container_width=True):
        if contexto:
            with st.spinner("IA formulando estratégia..."):
                prompt = f"Advogado Sênior. Gere estratégia de audiência para: {contexto}. Inclua teses, perguntas e riscos."
                res = tentar_gerar_conteudo(prompt)
                st.markdown(res)
                salvar_documento_memoria("Estratégia", "Audiência", res)
                st.download_button("Baixar Roteiro", gerar_word(res), "Roteiro.docx")

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
st.markdown("<center>🔒 LEGALHUB ELITE v10.0 | CASCATA MODE</center>", unsafe_allow_html=True)
