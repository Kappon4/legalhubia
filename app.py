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
# 1. CONFIGURAÇÃO VISUAL
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite (Dev Mode)", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# 2. CONFIGURAÇÃO API GOOGLE (IA)
# ==========================================================
# Tenta pegar dos Secrets, senão pede na tela (para não travar)
try:
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY_FIXA = ""

# ==========================================================
# 3. SISTEMA DE MEMÓRIA TEMPORÁRIA (SUBSTITUI O BANCO)
# ==========================================================
# Inicia uma lista vazia para guardar documentos enquanto a janela estiver aberta
if "meus_docs" not in st.session_state:
    st.session_state.meus_docs = []

def salvar_documento_memoria(tipo, cliente, conteudo):
    # Salva na memória RAM do navegador
    doc = {
        "id": len(st.session_state.meus_docs) + 1,
        "data": datetime.now().strftime("%d/%m/%Y"),
        "tipo": tipo,
        "cliente": cliente,
        "conteudo": conteudo
    }
    st.session_state.meus_docs.append(doc)
    return True

# ==========================================================
# 4. FUNÇÕES GERAIS (IA, PDF, ARQUIVOS)
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
    return "\n\n[NENHUMA JURISPRUDÊNCIA ESPECÍFICA ENCONTRADA]"

def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ ERRO: API Key do Google não configurada nos Secrets."
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

# --- CSS ---
def local_css():
    st.markdown("""<style>
        .stApp { background-color: #0e1117; color: white; }
        .stButton>button { border: 1px solid #00F3FF; color: #00F3FF; background: transparent; width: 100%; }
        .stButton>button:hover { background: #00F3FF; color: black; }
        h1, h2, h3 { color: #00F3FF !important; }
        .success-box { border: 1px solid #00F3FF; padding: 10px; border-radius: 5px; color: #00F3FF; }
    </style>""", unsafe_allow_html=True)
local_css()

# ==========================================================
# 5. BARRA LATERAL (SEM LOGIN)
# ==========================================================
with st.sidebar:
    st.title("🛡️ MENU")
    st.caption("Modo Desenvolvedor (Sem Login)")
    
    if "navegacao_override" not in st.session_state: st.session_state.navegacao_override = None
    
    mapa = {
        "Dashboard": "📊 Dashboard", 
        "Redator": "✍️ Redator Jurídico", 
        "Calculos": "🧮 Cálculos Jurídicos", 
        "Contratos": "📜 Contratos", 
        "Cofre": "📂 Cofre (Temp)"
    }
    
    # Lógica para redirecionamento por botões
    idx = 0
    if st.session_state.navegacao_override:
        try: idx = list(mapa.values()).index(st.session_state.navegacao_override)
        except: pass
        st.session_state.navegacao_override = None
        
    escolha = st.radio("Navegação", list(mapa.keys()), index=idx)
    menu = mapa[escolha]
    
    st.divider()
    st.info("💡 Nota: No modo sem login, os documentos salvos somem ao atualizar a página.")

# ==========================================================
# 6. TELAS DO SISTEMA
# ==========================================================

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("📊 Visão Geral")
    
    c1, c2 = st.columns(2)
    qtd_docs = len(st.session_state.meus_docs)
    c1.metric("Documentos na Sessão", qtd_docs)
    c2.metric("Status do Sistema", "Online (Dev)")
    
    st.markdown("---")
    st.subheader("🚀 Acesso Rápido")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✍️ Nova Petição", use_container_width=True): 
            st.session_state.navegacao_override = "✍️ Redator Jurídico"
            st.rerun()
    with col2:
        if st.button("🧮 Novo Cálculo", use_container_width=True): 
            st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"
            st.rerun()
    with col3:
        if st.button("📜 Novo Contrato", use_container_width=True): 
            st.session_state.navegacao_override = "📜 Contratos"
            st.rerun()

# --- REDATOR ---
elif menu == "✍️ Redator Jurídico":
    st.header("✍️ Redator IA (Anti-Alucinação)")
    
    area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    # Listas Inteligentes
    pecas = []
    if area == "Cível": pecas = ["Petição Inicial", "Contestação", "Réplica", "Reconvenção", "Agravo de Instrumento", "Apelação", "Embargos de Declaração", "Recurso Especial", "Mandado de Segurança"]
    elif area == "Trabalhista": pecas = ["Reclamação Trabalhista", "Contestação", "Recurso Ordinário", "Recurso de Revista", "Consignação em Pagamento", "Exceção de Incompetência"]
    elif area == "Criminal": pecas = ["Resposta à Acusação", "Memoriais", "Habeas Corpus", "Relaxamento de Prisão", "Queixa-Crime", "Apelação", "Recurso em Sentido Estrito", "Liberdade Provisória"]
    elif area == "Tributário": pecas = ["Anulatória de Débito", "Mandado de Segurança", "Embargos à Execução Fiscal", "Repetição de Indébito", "Exceção de Pré-Executividade"]
    elif area == "Previdenciário": pecas = ["Petição Inicial (Concessão)", "Recurso Administrativo", "Aposentadoria Especial", "Auxílio-Doença", "Recurso Inominado"]
    
    tipo = st.selectbox("Peça", pecas)
    
    c1, c2 = st.columns(2)
    cli = c1.text_input("Cliente")
    adv = c2.text_input("Parte Contrária")
    
    fatos = st.text_area("Narrativa dos Fatos", height=150, placeholder="Descreva o caso aqui...")
    
    busca_real = st.checkbox("🔍 Buscar Jurisprudência Real (STF/STJ/TST)", value=True)
    
    if st.button("✨ GERAR PEÇA JURÍDICA"):
        if fatos and cli:
            with st.spinner("Pesquisando jurisprudência e redigindo..."):
                # 1. Busca
                ctx = ""
                if busca_real:
                    ctx = buscar_contexto_juridico(f"{tipo} {fatos}", area)
                
                # 2. Redação
                prompt = f"""
                Atue como Advogado Especialista em Direito {area}.
                Redija uma {tipo} completa.
                Cliente: {cli}. Parte Contrária: {adv}.
                Fatos: {fatos}.
                
                Contexto Jurídico Real (Use se relevante):
                {ctx}
                
                Estruture com: Endereçamento, Qualificação, Fatos, Direito, Pedidos.
                """
                
                res = tentar_gerar_conteudo(prompt, None)
                
                # 3. Resultado
                st.markdown(res)
                
                if "❌" not in res:
                    # Salva na memória
                    salvar_documento_memoria(tipo, cli, res)
                    st.success("Documento salvo na sessão!")
                    
                    # Download
                    st.download_button("📥 Baixar DOCX", gerar_word(res), f"{tipo}_{cli}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        else:
            st.warning("Preencha o cliente e os fatos.")

# --- CÁLCULOS ---
elif menu == "🧮 Cálculos Jurídicos":
    st.header("🧮 Central de Cálculos")
    area_calc = st.selectbox("Área", ["Trabalhista (CLT)", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    st.divider()

    if area_calc == "Trabalhista (CLT)":
        st.subheader("Rescisão Trabalhista")
        c1, c2, c3 = st.columns(3)
        adm = c1.date_input("Admissão", date(2022,1,1))
        dem = c2.date_input("Demissão", date.today())
        motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa", "Acordo"])
        
        c4, c5, c6 = st.columns(3)
        sal = c4.number_input("Salário Base", value=2000.0)
        fgts = c5.number_input("Saldo FGTS", value=0.0)
        aviso = c6.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado", "Não Trabalhado"])
        
        c7, c8 = st.columns(2)
        insal = c7.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
        peric = c8.checkbox("Periculosidade (30%)")
        
        if st.button("CALCULAR TRABALHISTA"):
            if dem > adm:
                v = calcular_rescisao_completa(adm, dem, sal, motivo, fgts, False, aviso, insal, peric)
                st.success(f"💰 Total Estimado: R$ {sum(v.values()):,.2f}")
                st.dataframe(pd.DataFrame(list(v.items()), columns=["Verba", "Valor"]), use_container_width=True)

    elif area_calc == "Cível (Art. 292/Liquidação)":
        tab1, tab2, tab3 = st.tabs(["Liquidação de Sentença", "Valor da Causa", "Revisão Bancária"])
        
        with tab1:
            st.info("Cálculo de Atualização + Juros + Multas")
            c1, c2 = st.columns(2)
            val = c1.number_input("Valor da Condenação")
            idx = c2.number_input("Índice Acumulado (Ex: 1.05)", 1.0)
            
            c3, c4 = st.columns(2)
            juros = c3.selectbox("Juros Moratórios", ["1% a.m.", "Selic", "Sem Juros"])
            meses = c4.number_input("Meses de Atraso", 0)
            
            multa_art = st.checkbox("Multa Art. 523 (10%)")
            hon_art = st.checkbox("Honorários Art. 523 (10%)")
            
            if st.button("LIQUIDAR SENTENÇA"):
                atualizado = val * idx
                val_juros = 0
                if juros == "1% a.m.": val_juros = atualizado * (0.01 * meses)
                
                subtotal = atualizado + val_juros
                total = subtotal
                if multa_art: total += subtotal * 0.10
                if hon_art: total += subtotal * 0.10
                
                st.metric("Total da Execução", f"R$ {total:,.2f}")
                st.write(f"Principal Atualizado: R$ {atualizado:,.2f} | Juros: R$ {val_juros:,.2f}")

        with tab2:
            st.info("Cálculo do Valor da Causa (Art. 292 CPC)")
            tipo = st.radio("Tipo de Ação", ["Cobrança de Dívida", "Alimentos (12 meses)", "Indenização"])
            if tipo == "Alimentos":
                mensal = st.number_input("Valor da Prestação Mensal")
                st.metric("Valor da Causa", f"R$ {mensal * 12:,.2f}")
            elif tipo == "Cobrança de Dívida":
                p = st.number_input("Principal")
                j = st.number_input("Juros")
                m = st.number_input("Multa")
                st.metric("Valor da Causa", f"R$ {p+j+m:,.2f}")
            else:
                d = st.number_input("Valor do Dano Moral/Material Pretendido")
                st.metric("Valor da Causa", f"R$ {d:,.2f}")

        with tab3:
            st.info("Simulação Price vs Gauss (Revisional)")
            emp = st.number_input("Valor do Empréstimo")
            tx = st.number_input("Taxa de Juros (%) Mensal")
            m = st.number_input("Número de Parcelas", 12)
            if st.button("SIMULAR REVISIONAL"):
                # Price Simplificada
                i = tx/100
                price = emp * (i * (1+i)**m) / ((1+i)**m - 1)
                # Gauss (Aproximação Jurídica Comum)
                gauss = price * 0.85 # Estimativa de redução comum
                
                c1, c2 = st.columns(2)
                c1.metric("Parcela Atual (Price)", f"R$ {price:,.2f}")
                c2.metric("Parcela Recalculada (Est.)", f"R$ {gauss:,.2f}")
                st.warning("Atenção: Este é um cálculo estimativo para inicial. Requer laudo pericial contábil.")

    elif area_calc == "Família":
        st.subheader("Cálculo de Pensão Alimentícia")
        st.write("Baseado no trinômio: Necessidade x Possibilidade x Proporcionalidade")
        renda = st.number_input("Renda Líquida do Alimentante (Quem paga)")
        filhos = st.slider("Número de Filhos", 1, 5)
        
        if st.button("SUGERIR PENSÃO"):
            # Lógica base comum: 30% para 1 filho, +5% por filho extra (estimativa)
            perc = 0.30 + ((filhos - 1) * 0.05)
            st.info(f"Sugestão Jurisprudencial Comum: {perc*100:.0f}% da renda líquida.")
            st.metric("Valor Sugerido", f"R$ {renda * perc:,.2f}")

    elif area_calc == "Tributária":
        st.subheader("Cálculo de Atualização Fiscal")
        valor = st.number_input("Valor Original do Tributo")
        multa = st.number_input("Multa de Mora (%)", value=20.0)
        selic = st.number_input("Selic Acumulada (%)", value=10.0)
        
        if st.button("ATUALIZAR TRIBUTO"):
            total = valor + (valor * (multa/100)) + (valor * (selic/100))
            st.success(f"Valor Total Devido: R$ {total:,.2f}")

    elif area_calc == "Criminal":
        st.subheader("Dosimetria da Pena (1ª Fase)")
        pena_min = st.number_input("Pena Mínima (anos)")
        pena_max = st.number_input("Pena Máxima (anos)")
        circunstancias = st.slider("Circunstâncias Judiciais Desfavoráveis (Art. 59 CP)", 0, 8)
        
        if st.button("CALCULAR PENA BASE"):
            intervalo = pena_max - pena_min
            aumento = (intervalo / 8) * circunstancias
            st.error(f"Pena Base Estimada: {pena_min + aumento:.1f} anos")

# --- CONTRATOS ---
elif menu == "📜 Contratos":
    st.header("📜 Fábrica de Contratos")
    c1, c2 = st.columns(2)
    cli = c1.text_input("Nome do Cliente")
    cpf = c2.text_input("CPF/CNPJ")
    
    tipo_cont = st.selectbox("Tipo", ["Contrato de Honorários", "Procuração Ad Judicia"])
    
    if tipo_cont == "Contrato de Honorários":
        val = st.number_input("Valor dos Honorários (R$)", step=100.0)
        forma = st.text_input("Forma de Pagamento (Ex: Entrada + 3x)")
        
        if st.button("GERAR CONTRATO"):
            prompt = f"Redija um Contrato de Honorários Advocatícios. Contratante: {cli}, CPF {cpf}. Valor: R$ {val}. Forma: {forma}. Contratado: LBA Advocacia."
            res = tentar_gerar_conteudo(prompt, None)
            st.markdown(res)
            salvar_documento_memoria("Contrato", cli, res)
            st.download_button("Baixar", gerar_word(res), "Contrato.docx")
            
    else:
        poderes = st.selectbox("Poderes", ["Gerais", "Gerais + Especiais"])
        if st.button("GERAR PROCURAÇÃO"):
            prompt = f"Redija uma Procuração Ad Judicia. Outorgante: {cli}, CPF {cpf}. Poderes: {poderes}. Outorgado: LBA Advocacia."
            res = tentar_gerar_conteudo(prompt, None)
            st.markdown(res)
            salvar_documento_memoria("Procuração", cli, res)
            st.download_button("Baixar", gerar_word(res), "Procuracao.docx")

# --- COFRE DIGITAL (MEMÓRIA) ---
elif menu == "📂 Cofre (Temp)":
    st.header("📂 Documentos da Sessão Atual")
    st.warning("⚠️ Nota: Estes documentos sumirão se você fechar a janela ou atualizar a página.")
    
    if len(st.session_state.meus_docs) > 0:
        for i, doc in enumerate(st.session_state.meus_docs):
            with st.expander(f"{doc['data']} - {doc['tipo']} - {doc['cliente']}"):
                st.write(doc['conteudo'][:500] + "...")
                st.download_button("📥 Baixar DOCX", gerar_word(doc['conteudo']), f"Doc_{i}.docx", key=f"dl_{i}")
    else:
        st.info("Nenhum documento gerado nesta sessão ainda.")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v9.5 | DEV MODE (NO LOGIN)</center>", unsafe_allow_html=True)
