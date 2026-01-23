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
# 1. CONFIGURAÇÃO VISUAL
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
try:
    API_KEY_FINAL = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ ERRO CRÍTICO: Chave de API não configurada. Configure no Secrets do Streamlit Cloud.")
    st.stop()

# ==========================================================
# 3. IA DEDICADA: GEMINI 2.5 (ULTRA MODERN)
# ==========================================================
def tentar_gerar_conteudo(prompt, ignored_param=None):
    if not API_KEY_FINAL: return "⚠️ Chave Inválida"
    
    genai.configure(api_key=API_KEY_FINAL)

    # --- LISTA DE MODELOS 2.5+ (Conforme solicitado) ---
    # O código vai tentar um por um.
    modelos_elite = [
        "gemini-2.5-flash",          # Versão Estável Rápida
        "gemini-2.5-pro",            # Versão Estável Potente
        "gemini-2.5-flash-exp",      # Experimental Rápida
        "gemini-2.5-pro-exp",        # Experimental Potente
        "gemini-ultra-2.5"           # Caso disponível na sua chave
    ]

    log_erros = []

    for modelo in modelos_elite:
        tentativas = 0
        max_tentativas = 3  # Insiste 3x no mesmo modelo antes de trocar
        
        while tentativas < max_tentativas:
            try:
                # Tenta instanciar o modelo específico
                model_instance = genai.GenerativeModel(modelo)
                response = model_instance.generate_content(prompt)
                return response.text # SUCESSO! Retorna o texto.
            
            except Exception as e:
                erro_msg = str(e)
                
                # Tratamento de Erro de Cota (429)
                if "429" in erro_msg or "quota" in erro_msg.lower():
                    tempo_espera = (tentativas + 1) * 5
                    log_erros.append(f"⏳ {modelo}: Cota cheia. Aguardando {tempo_espera}s...")
                    time.sleep(tempo_espera) # Espera o Google liberar
                    tentativas += 1
                    continue
                
                # Tratamento de Modelo Inexistente (404)
                elif "404" in erro_msg or "not found" in erro_msg.lower():
                    log_erros.append(f"🚫 {modelo}: Não disponível para esta chave/lib.")
                    break # Pula para o próximo modelo da lista
                
                else:
                    log_erros.append(f"⚠️ {modelo}: {erro_msg[:40]}...")
                    break # Outro erro, troca de modelo

    # Se saiu do loop, nenhum funcionou
    return f"""❌ FALHA GERAL (MODO 2.5).
    
    Diagnóstico:
    O sistema tentou usar apenas modelos da linha 2.5, mas sua chave ou biblioteca não conseguiu conectar.
    
    Log Técnico:
    {chr(10).join(log_erros)}
    
    Solução:
    1. Atualize sua lib: `pip install -U google-generativeai`
    2. Verifique se sua chave tem acesso ao 'Gemini 2.5' no Google AI Studio.
    """

# ==========================================================
# 4. FUNÇÕES UTILITÁRIAS
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

# ==========================================================
# 5. CÁLCULO TRABALHISTA
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
# 6. CSS VISUAL
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
# 7. NAVEGAÇÃO
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
# 8. CONTEÚDO DAS TELAS
# ==========================================================

# --- DASHBOARD ---
if menu_opcao == "📊 Dashboard":
    st.markdown(f"<h2 class='tech-header'>BEM-VINDO AO HUB <span style='font-weight:300; font-size: 1.5rem; color:#64748b;'>| GEMINI 2.0 ONLY</span></h2>", unsafe_allow_html=True)
    
    # Mostra a versão da biblioteca (para debug se o 2.0 der 404)
    import google.generativeai as gai
    versao_atual = gai.__version__
    
    c1, c2, c3 = st.columns(3)
    c1.metric("DOCS NA SESSÃO", len(st.session_state.meus_docs))
    c2.metric("LIB VERSION", f"v{versao_atual}")
    c3.metric("MODO", "2.0 (High Precision)")
    
    if versao_atual < "0.8.3":
        st.warning(f"⚠️ Sua biblioteca v{versao_atual} pode não encontrar o Gemini 2.0. Verifique o requirements.txt.")
    
    st.write("")
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
    st.markdown("<h2 class='tech-header'>✍️ REDATOR IA AVANÇADO (2.0)</h2>", unsafe_allow_html=True)
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
    
    if st.button("GERAR PEÇA (MODO 2.0)", use_container_width=True):
        if fatos and cli:
            with st.spinner("Pesquisando e Redigindo com Gemini 2.0 (Isso pode levar alguns segundos)..."):
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

    if st.button("GERAR CONTRATO (MODO 2.0)", use_container_width=True):
        if nome and cpf and obj:
            with st.spinner("Redigindo com Gemini 2.0..."):
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
        
        tab_divida, tab_banco, tab_imob, tab_causa, tab_hon = st.tabs([
            "Atualização de Dívidas", 
            "Bancário & Contratos", 
            "Imobiliário & Aluguel",
            "Valor da Causa (CPC)",
            "Honorários"
        ])
        
        with tab_divida:
            st.info("Correção Monetária + Juros de Mora + Danos (Liquidação)")
            c1, c2 = st.columns(2)
            val_origem = c1.number_input("Valor Original", value=0.0, format="%.2f", key="civ_val_origem")
            data_inicio = c2.date_input("Data do Evento", date(2023, 1, 1), key="civ_dt_ini")
            data_fim = date.today()
            
            dias = (data_fim - data_inicio).days
            meses = dias // 30
            st.write(f"📅 Tempo decorrido: **{meses} meses**")
            
            c3, c4, c5 = st.columns(3)
            indice = c3.number_input("Índice Acumulado (Ex: 1.05)", value=1.0, key="civ_indice")
            juros_tipo = c4.selectbox("Juros de Mora", ["1% a.m.", "0.5% a.m.", "Selic"], key="civ_juros_tipo")
            multa_pct = c5.number_input("Multa (%)", value=0.0, key="civ_multa")
            
            k1, k2, k3 = st.columns(3)
            danos_morais = k1.number_input("Danos Morais", value=0.0, key="civ_dm")
            danos_materiais = k2.number_input("Lucros Cessantes", value=0.0, key="civ_lucros")
            hon_sucumb = k3.number_input("Honorários (%)", value=10.0, key="civ_sucumb")

            if st.button("CALCULAR ATUALIZAÇÃO", key="btn_calc_divida"):
                valor_corrigido = val_origem * indice
                val_juros = 0.0
                if juros_tipo == "1% a.m.": val_juros = valor_corrigido * (0.01 * meses)
                elif juros_tipo == "0.5% a.m.": val_juros = valor_corrigido * (0.005 * meses)
                elif juros_tipo == "Selic": val_juros = valor_corrigido * 0.15
                
                val_multa = valor_corrigido * (multa_pct / 100)
                subtotal = valor_corrigido + val_juros + val_multa
                total_geral = subtotal + danos_morais + danos_materiais
                val_honorarios = total_geral * (hon_sucumb / 100)
                total_final = total_geral + val_honorarios
                
                st.success(f"💰 TOTAL FINAL: R$ {total_final:,.2f}")
                st.table(pd.DataFrame([
                    ("Principal Corrigido", f"R$ {valor_corrigido:,.2f}"),
                    (f"Juros ({meses} m)", f"R$ {val_juros:,.2f}"),
                    ("Danos Morais/Mat", f"R$ {danos_morais + danos_materiais:,.2f}"),
                    ("Honorários", f"R$ {val_honorarios:,.2f}")
                ], columns=["Item", "Valor"]))

        with tab_banco:
            st.info("Revisional, Anatocismo e Financiamentos")
            b1, b2 = st.columns(2)
            divida_banc = b1.number_input("Valor Financiado", value=50000.0, key="banc_valor")
            prazo_meses = b2.number_input("Prazo (Meses)", value=60, key="banc_prazo")
            b3, b4 = st.columns(2)
            taxa_mensal = b3.number_input("Taxa Juros Mensal (%)", value=1.5, key="banc_taxa")
            sistema = b4.radio("Sistema", ["Price (Composto)", "Gauss (Simples)"], key="banc_sistema")
            
            if st.button("SIMULAR REVISIONAL", key="btn_bancario"):
                i = taxa_mensal / 100
                n = prazo_meses
                parcela_price = divida_banc * (i * (1+i)**n) / ((1+i)**n - 1)
                total_price = parcela_price * n
                fator_gauss = (n * i) + 1
                parcela_gauss = (divida_banc * fator_gauss) / n 
                total_gauss = parcela_gauss * n
                
                c_res1, c_res2 = st.columns(2)
                c_res1.metric("Parcela Price", f"R$ {parcela_price:,.2f}")
                c_res2.metric("Parcela Gauss (Tese)", f"R$ {parcela_gauss:,.2f}")
                st.info(f"Diferença Total (Indébito): R$ {total_price - total_gauss:,.2f}")

        with tab_imob:
            st.info("Imobiliário: Reajustes e Despejo")
            acao_imob = st.radio("Tipo", ["Reajuste Aluguel", "Despejo (Cobrança)"], horizontal=True, key="imob_tipo")
            val_aluguel = st.number_input("Valor Aluguel", value=2000.0, key="imob_val")
            
            if acao_imob == "Reajuste Aluguel":
                idx_imob = st.number_input("Índice % (IGPM/IPCA)", value=4.5, key="imob_idx")
                if st.button("Calcular Novo Aluguel"):
                    st.success(f"Novo Aluguel: R$ {val_aluguel * (1 + idx_imob/100):,.2f}")
            else:
                meses_atraso = st.number_input("Meses Atraso", value=3, key="imob_meses")
                multa_moratoria = st.checkbox("Multa 10%", value=True, key="imob_check")
                if st.button("Calcular Débito"):
                    total = (val_aluguel * meses_atraso) * (1.10 if multa_moratoria else 1.0)
                    st.error(f"Total Despejo: R$ {total:,.2f}")

        with tab_causa:
            st.info("Valor da Causa (CPC)")
            tipo_causa = st.selectbox("Tipo", ["Alimentos (12x)", "Cobrança (Dano Material + Moral)"], key="causa_tipo")
            if tipo_causa == "Alimentos (12x)":
                mensal = st.number_input("Prestação Mensal", key="causa_alim")
                st.metric("Valor da Causa", f"R$ {mensal * 12:,.2f}")
            else:
                mat = st.number_input("Dano Material", key="causa_mat")
                mor = st.number_input("Dano Moral", key="causa_mor")
                st.metric("Valor da Causa", f"R$ {mat + mor:,.2f}")

        with tab_hon:
            st.info("Honorários")
            base = st.number_input("Base de Cálculo", value=10000.0, key="hon_base")
            pct = st.number_input("% Honorários", value=20.0, key="hon_pct")
            if st.button("Calcular Honorários"):
                st.success(f"Honorários: R$ {base * (pct/100):,.2f}")

    elif area_calc == "Família":
        st.markdown("#### 👨‍👩‍👧‍👦 Cálculo Avançado de Pensão Alimentícia (Trinômio)")
        
        tab_fixacao, tab_revisao = st.tabs(["Fixação de Pensão", "Atualização/Revisão"])
        
        with tab_fixacao:
            st.markdown("##### 1. Possibilidade (Renda dos Pais)")
            c1, c2 = st.columns(2)
            renda_alimentante = c1.number_input("Renda Líquida do Alimentante", value=3000.0, key="fam_renda1")
            renda_guardiao = c2.number_input("Renda Líquida do Guardião", value=2000.0, key="fam_renda2")
            
            renda_total_pais = renda_alimentante + renda_guardiao
            prop_alimentante = (renda_alimentante / renda_total_pais) * 100 if renda_total_pais > 0 else 0
            st.progress(prop_alimentante / 100)
            
            st.markdown("---")
            st.markdown("##### 2. Necessidade (Despesas da Criança)")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                gastos_diretos = st.number_input("Gastos Diretos (Escola, Saúde, Lazer)", value=800.0, key="fam_gasto_dir")
            with col_d2:
                gastos_moradia = st.number_input("Total Gastos da Casa", value=1500.0, key="fam_gasto_casa")
                pessoas_casa = st.number_input("Total de Pessoas na Casa", value=3, min_value=2, key="fam_pessoas")
            
            parte_crianca_moradia = gastos_moradia / pessoas_casa
            necessidade_total = gastos_diretos + parte_crianca_moradia
            st.info(f"💰 Necessidade Mensal Apurada: **R$ {necessidade_total:,.2f}**")

            st.markdown("---")
            if st.button("CALCULAR PENSÃO SUGERIDA", key="btn_fam_calc"):
                valor_sugerido = necessidade_total * (prop_alimentante / 100)
                teto_30 = renda_alimentante * 0.30
                c_res1, c_res2 = st.columns(2)
                c_res1.metric("Valor Sugerido (Proporcional)", f"R$ {valor_sugerido:,.2f}")
                c_res2.markdown(f"#### Teto de 30%: R$ {teto_30:,.2f}")
                
                if valor_sugerido > teto_30:
                    st.warning("⚠️ O valor proporcional ultrapassa 30% da renda.")
                else:
                    st.success("✅ O valor está dentro de uma margem segura.")

        with tab_revisao:
            st.markdown("##### Atualização de Valor Defasado")
            val_antigo = st.number_input("Valor da Pensão Fixada", value=500.0, key="fam_val_antigo")
            indice_rev = st.number_input("Índice de Reajuste (%)", value=4.5, key="fam_idx_rev")
            if st.button("ATUALIZAR VALOR", key="btn_fam_upd"):
                st.success(f"Novo Valor: R$ {val_antigo * (1 + indice_rev/100):,.2f}")

    elif area_calc == "Tributária":
        st.markdown("#### 🏛️ Cálculos e Teses Tributárias")
        
        tab_fed, tab_tese, tab_mora = st.tabs([
            "Atualização Débito Federal (CDA)", 
            "Tese do Século (PIS/COFINS)", 
            "Cálculo de Multa de Mora"
        ])
        
        with tab_fed:
            st.info("Atualização pela Taxa SELIC (Lei 9.430/96)")
            c1, c2 = st.columns(2)
            principal = c1.number_input("Valor Principal (R$)", value=10000.0, key="trib_principal")
            selic_acum = c2.number_input("Taxa SELIC Acumulada (%)", value=15.5, key="trib_selic")
            c3, c4 = st.columns(2)
            multa_oficio = c3.number_input("Multa de Ofício (%)", value=75.0, key="trib_multa_oficio")
            encargo_legal = c4.checkbox("Encargo Legal (20%)?", value=True, key="trib_encargo")
            
            if st.button("CALCULAR DÉBITO FISCAL", key="btn_trib_cda"):
                val_juros = principal * (selic_acum / 100)
                val_multa = principal * (multa_oficio / 100)
                base_parcial = principal + val_juros + val_multa
                val_encargo = base_parcial * 0.20 if encargo_legal else 0
                st.success(f"TOTAL DA CDA: R$ {base_parcial + val_encargo:,.2f}")

        with tab_tese:
            st.info("Tese do Século (Exclusão ICMS da base PIS/COFINS)")
            fat = st.number_input("Faturamento Mensal (R$)", value=100000.0, key="tese_fat")
            t1, t2, t3 = st.columns(3)
            icms = t1.number_input("ICMS (%)", value=18.0, key="tese_icms")
            pis = t2.number_input("PIS (%)", value=1.65, key="tese_pis")
            cofins = t3.number_input("COFINS (%)", value=7.60, key="tese_cofins")
            meses = st.slider("Meses Recuperar", 12, 60, 60, key="tese_meses")
            
            if st.button("SIMULAR CRÉDITO", key="btn_tese"):
                aliq_total = (pis + cofins) / 100
                pago = fat * aliq_total
                devido = (fat - (fat * icms/100)) * aliq_total
                credito = (pago - devido) * meses
                st.success(f"💰 Crédito Estimado: R$ {credito:,.2f}")

        with tab_mora:
            st.info("Multa de Mora Federal (0,33% ao dia, max 20%)")
            val_guia = st.number_input("Valor Guia", value=1000.0, key="mora_val")
            dias = st.number_input("Dias Atraso", value=15, key="mora_dias")
            if st.button("CALCULAR", key="btn_mora"):
                multa = min(dias * 0.33, 20.0)
                val_multa = val_guia * (multa / 100)
                st.success(f"Total: R$ {val_guia + val_multa:,.2f} (Multa: R$ {val_multa:,.2f})")

    elif area_calc == "Criminal":
        st.markdown("#### ⚖️ Penal e Processo Penal")
        
        tab_dosimetria, tab_execucao, tab_prescricao, tab_detracao = st.tabs([
            "Dosimetria (3 Fases)", 
            "Execução & Progressão", 
            "Calculadora de Prescrição",
            "Detração e Remição"
        ])
        
        with tab_dosimetria:
            st.info("Simulação do Sistema Trifásico")
            c1, c2 = st.columns(2)
            pena_min = c1.number_input("Pena Mínima (Anos)", value=5.0, step=0.5, key="crim_min")
            pena_max = c2.number_input("Pena Máxima (Anos)", value=15.0, step=0.5, key="crim_max")
            circunstancias = st.slider("Circunstâncias Desfavoráveis", 0, 8, 0, key="crim_circ")
            
            c_f2a, c_f2b = st.columns(2)
            agravantes = c_f2a.number_input("Agravantes", value=0, key="crim_agrav")
            atenuantes = c_f2b.number_input("Atenuantes", value=0, key="crim_aten")
            
            c_f3a, c_f3b = st.columns(2)
            fracao_aumento = c_f3a.selectbox("Aumento", ["Nenhum", "1/6", "1/3", "1/2", "2/3"], key="crim_aum")
            fracao_diminuicao = c_f3b.selectbox("Diminuição", ["Nenhum", "1/6", "1/3", "1/2", "2/3"], key="crim_dim")
            
            if st.button("CALCULAR PENA", key="btn_dosimetria"):
                pena_base = pena_min + (((pena_max - pena_min)/8) * circunstancias)
                pena_interm = pena_base + (agravantes * (pena_base/6)) - (atenuantes * (pena_base/6))
                if pena_interm < pena_min: pena_interm = pena_min
                
                pena_final = pena_interm
                if fracao_aumento != "Nenhum":
                    n, d = map(int, fracao_aumento.split('/'))
                    pena_final += (pena_final * n / d)
                if fracao_diminuicao != "Nenhum":
                    n, d = map(int, fracao_diminuicao.split('/'))
                    pena_final -= (pena_final * n / d)
                
                st.success(f"⚖️ Pena Final: {pena_final:.2f} anos")

        with tab_execucao:
            st.info("Progressão de Regime")
            pena_total = st.number_input("Pena Total (Anos)", value=8, key="exec_anos")
            data_base = st.date_input("Data Base", date.today(), key="exec_data")
            tipo = st.selectbox("Tipo de Crime", ["16% - Primário s/ Violência", "25% - Primário c/ Violência", "40% - Hediondo Primário", "60% - Hediondo Reincidente"], key="exec_tipo")
            
            if st.button("CALCULAR PROGRESSÃO", key="btn_progressao"):
                pct = int(tipo.split('%')[0])
                dias = (pena_total * 365) * (pct / 100)
                st.success(f"Data Progressão: {(data_base + timedelta(days=dias)).strftime('%d/%m/%Y')}")

        with tab_prescricao:
            st.info("Prescrição (Art. 109 CP)")
            pena = st.number_input("Pena Máxima Abstrata", value=4.0, key="presc_pena")
            if st.button("VERIFICAR", key="btn_presc"):
                prazo = 20
                if pena < 1: prazo = 3
                elif pena < 2: prazo = 4
                elif pena < 4: prazo = 8
                elif pena < 8: prazo = 12
                elif pena < 12: prazo = 16
                st.error(f"Prescreve em: {prazo} anos")

        with tab_detracao:
            st.info("Detração e Remição")
            prov = st.number_input("Dias Preso Provisório", value=0, key="det_prov")
            trab = st.number_input("Dias Trabalhados", value=0, key="det_trab")
            if st.button("CALCULAR", key="btn_det"):
                st.success(f"Total a abater: {prov + (trab//3)} dias")

# --- SIMULADOR DE AUDIÊNCIA ---
elif menu_opcao == "🏛️ Simulador Audiência":
    st.markdown("<h2 class='tech-header'>🏛️ WAR ROOM: ESTRATÉGIA DE AUDIÊNCIA</h2>", unsafe_allow_html=True)
    contexto = st.text_area("Resumo do conflito:", height=300)
    
    if st.button("GERAR ESTRATÉGIA DE GUERRA (2.0)", use_container_width=True):
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
st.markdown("<center>🔒 LEGALHUB ELITE v10.0 | GEMINI 2.0 EXCLUSIVE</center>", unsafe_allow_html=True)


