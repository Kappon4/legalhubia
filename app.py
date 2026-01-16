import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS
from datetime import datetime, timedelta, date
import time
import pandas as pd
import psycopg2 
import sys
import subprocess

# --- SETUP INICIAL ---
try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

st.set_page_config(page_title="LegalHub Elite v7.8", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

# ==========================================================
# 1. CONEXÃO COM BANCO DE DADOS
# ==========================================================
try:
    DB_URI = st.secrets["DB_URI"]
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
    USAR_SQLITE_BACKUP = False
except:
    # Fallback para execução local
    DB_URI = "postgresql://postgres:0OquFTc7ovRHTBGM@db.qhcjfmzkwczjupkfpmdk.supabase.co:5432/postgres"
    API_KEY_FIXA = "AIzaSyA5lMfeDUE71k6BOOxYRZDtOolPZaqCurA"
    USAR_SQLITE_BACKUP = False

def get_db_connection():
    if USAR_SQLITE_BACKUP:
        import sqlite3
        return sqlite3.connect('legalhub.db')
    else:
        return psycopg2.connect(DB_URI)

def run_query(query, params=(), return_data=False):
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if not USAR_SQLITE_BACKUP: query = query.replace('?', '%s')
        c.execute(query, params)
        if return_data:
            data = c.fetchall()
            col_names = [desc[0] for desc in c.description] if c.description else []
            conn.close()
            return pd.DataFrame(data, columns=col_names)
        else:
            conn.commit(); conn.close()
            return True
    except Exception as e:
        if conn: conn.close()
        return None

# ==========================================================
# 2. FUNÇÕES ÚTEIS & IA
# ==========================================================
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

# --- NOVA FUNÇÃO: BUSCA ANTI-ALUCINAÇÃO ---
def buscar_contexto_juridico(tema, area):
    """Realiza busca em fontes oficiais para fundamentar a IA."""
    fontes = {
        "Criminal": "site:stj.jus.br OR site:stf.jus.br OR site:conjur.com.br",
        "Trabalhista": "site:tst.jus.br OR site:csjt.jus.br OR site:trtsp.jus.br",
        "Tributário": "site:carf.fazenda.gov.br OR site:stj.jus.br",
        "Previdenciário": "site:gov.br/inss OR site:trf3.jus.br",
        "Cível": "site:stj.jus.br OR site:tjsp.jus.br OR site:ibdfam.org.br"
    }
    site_query = fontes.get(area, "site:jusbrasil.com.br")
    query = f"{tema} jurisprudência {site_query}"
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="br-pt", max_results=3))
            if results:
                texto_res = "\n".join([f"- {r['title']}: {r['body']} (Fonte: {r['href']})" for r in results])
                return f"\n\n[JURISPRUDÊNCIA REAL ENCONTRADA]:\n{texto_res}"
    except:
        pass
    return "\n\n[NENHUMA JURISPRUDÊNCIA ESPECÍFICA ENCONTRADA NOS CANAIS OFICIAIS]"

def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ Erro: API Key não configurada."
    genai.configure(api_key=chave)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash") # Modelo rápido e eficiente
        return model.generate_content(prompt).text
    except Exception as e: return f"❌ Erro IA: {str(e)}"

# ==========================================================
# 3. FUNÇÕES DE CÁLCULO
# ==========================================================
def calcular_rescisao_completa(admissao, demissao, salario_base, motivo, saldo_fgts, ferias_vencidas, aviso_tipo, grau_insalubridade, tem_periculosidade):
    formato = "%Y-%m-%d"
    d1 = datetime.strptime(str(admissao), formato)
    d2 = datetime.strptime(str(demissao), formato)
    
    verbas = {}
    
    # Adicionais
    sal_min = 1412.00
    adic_insal = 0
    if grau_insalubridade == "Mínimo (10%)": adic_insal = sal_min * 0.10
    elif grau_insalubridade == "Médio (20%)": adic_insal = sal_min * 0.20
    elif grau_insalubridade == "Máximo (40%)": adic_insal = sal_min * 0.40
    
    adic_peric = salario_base * 0.30 if tem_periculosidade else 0
    
    # Base de cálculo (Periculosidade prevalece se ambos existirem, regra geral CLT, mas aqui somamos para demonstrar)
    remuneracao = salario_base + max(adic_insal, adic_peric) 
    
    if adic_insal > 0: verbas["Adicional Insalubridade (Reflexo)"] = adic_insal
    if adic_peric > 0: verbas["Adicional Periculosidade (Reflexo)"] = adic_peric

    meses_trab = (d2.year - d1.year) * 12 + d2.month - d1.month
    anos_completos = meses_trab // 12
    
    # Saldo Salário
    verbas["Saldo Salário"] = (remuneracao/30) * d2.day
    
    # Aviso Prévio (Lei 12.506)
    dias_aviso = min(90, 30 + (3 * anos_completos))
    
    if motivo == "Demissão sem Justa Causa":
        if aviso_tipo == "Indenizado":
            verbas[f"Aviso Prévio ({dias_aviso} dias)"] = (remuneracao/30) * dias_aviso
            d2 = d2 + timedelta(days=dias_aviso) # Projeção
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
# 4. LOGIN & SETUP (MANTIDO SEGURO)
# ==========================================================
try:
    if USAR_SQLITE_BACKUP:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    else:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    
    # Cria Admin Padrão com segurança
    run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING", ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full'))
except: pass

if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #00F3FF;'>LEGALHUB ELITE v7.8</h2>", unsafe_allow_html=True)
        
        if USAR_SQLITE_BACKUP: st.warning("⚠️ MODO OFFLINE")
        else: st.success("☁️ CONEXÃO SEGURA ATIVA")
        
        tab_log, tab_cad = st.tabs(["ENTRAR", "CRIAR CONTA"])
        
        with tab_log:
            u = st.text_input("Usuário", key="l_u")
            p = st.text_input("Senha", type="password", key="l_p")
            c1, c2 = st.columns(2)
            if c1.button("LOGIN", use_container_width=True):
                res = run_query("SELECT * FROM usuarios WHERE username = %s AND senha = %s", (u, p), return_data=True)
                if res is not None and not res.empty:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = u
                    st.session_state.escritorio_atual = res.iloc[0]['escritorio']
                    st.session_state.plano_atual = res.iloc[0]['plano']
                    st.rerun()
                else: st.error("Acesso Negado")
            
            if c2.button("🆘 Resetar Admin", use_container_width=True):
                run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full') ON CONFLICT (username) DO UPDATE SET senha = 'admin'")
                st.success("Admin Resetado!")

        with tab_cad:
            nu = st.text_input("Novo Usuário", key="c_u")
            np = st.text_input("Nova Senha", type="password", key="c_p")
            ne = st.text_input("Escritório", key="c_e")
            if st.button("CADASTRAR", use_container_width=True):
                if nu and np and ne:
                    try:
                        run_query("INSERT INTO usuarios (username, senha, escritorio, creditos, plano) VALUES (%s, %s, %s, 10, 'starter')", (nu, np, ne))
                        st.success("Cadastrado! Faça login.")
                    except: st.error("Usuário já existe.")
    st.stop()

# ==========================================================
# 5. APP PRINCIPAL
# ==========================================================
if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
else: api_key = st.text_input("🔑 API Key:", type="password", key="sidebar_api_key")

# CSS e Menu
st.markdown("""<style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { border: 1px solid #00F3FF; color: #00F3FF; background: transparent; width: 100%; }
    .stButton>button:hover { background: #00F3FF; color: black; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🛡️ MENU")
    st.caption(f"User: {st.session_state.usuario_atual}")
    menu = st.radio("Navegação", ["Dashboard", "Redator IA", "📜 Contratos", "🧮 Cálculos Jurídicos", "Audiência", "Cofre Digital"])
    st.divider()
    if st.button("SAIR"): st.session_state.logado = False; st.rerun()

# --- LÓGICA ---

if menu == "Dashboard":
    st.header("📊 Visão Geral")
    c1, c2 = st.columns(2)
    docs = run_query("SELECT count(*) FROM documentos WHERE escritorio = %s", (st.session_state.escritorio_atual,), return_data=True)
    c1.metric("Documentos", docs.iloc[0][0] if docs is not None else 0)
    c2.metric("Plano", st.session_state.plano_atual.upper())

elif menu == "Redator IA":
    st.header("✍️ Redator Jurídico (Anti-Alucinação)")
    
    # SELETOR DE ÁREA E PEÇAS ESPECÍFICAS (ATUALIZADO CONFORME PEDIDO)
    area_direito = st.selectbox("Área do Direito", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    pecas = []
    if area_direito == "Cível":
        pecas = ["Petição Inicial", "Contestação", "Réplica", "Reconvenção", "Ação Rescisória", "Mandado de Segurança", "Embargos à Execução", "Embargos de Terceiro", "Agravo de Instrumento", "Apelação", "Embargos de Declaração", "Recurso Especial", "Pedido de Tutela Provisória", "Impugnação ao Cumprimento de Sentença"]
    elif area_direito == "Trabalhista":
        pecas = ["Reclamação Trabalhista", "Contestação", "Reconvenção", "Recurso Ordinário", "Recurso de Revista", "Agravo de Petição", "Embargos à Execução", "Consignação em Pagamento", "Exceção de Incompetência"]
    elif area_direito == "Criminal":
        pecas = ["Resposta à Acusação", "Memoriais", "Habeas Corpus", "Relaxamento de Prisão", "Queixa-Crime", "Apelação", "Recurso em Sentido Estrito", "Revisão Criminal", "Pedido de Liberdade Provisória", "Representação Criminal"]
    elif area_direito == "Tributário":
        pecas = ["Ação Declaratória de Inexistência", "Ação Anulatória de Débito", "Repetição de Indébito", "Mandado de Segurança", "Embargos à Execução Fiscal", "Exceção de Pré-Executividade", "Defesa Administrativa"]
    elif area_direito == "Previdenciário":
        pecas = ["Petição Inicial (Concessão/Revisão)", "Recurso Administrativo", "Pedido de Revisão", "Aposentadoria Especial", "Auxílio-Doença", "Petição de Juntada", "Recurso Inominado"]
        
    tipo = st.selectbox("Selecione a Peça", pecas)
    
    c1, c2 = st.columns(2)
    cli = c1.text_input("Cliente")
    parte_contraria = c2.text_input("Parte Contrária")
    
    fatos = st.text_area("Narrativa dos Fatos e Pedidos", height=150)
    
    # CHECKBOX PODEROSO
    anti_alucinacao = st.checkbox("🔍 Ativar Busca Anti-Alucinação (Fontes Oficiais: STF, STJ, TST, Gov)", value=True)
    
    if st.button("GERAR PEÇA JURÍDICA"):
        if fatos and cli:
            with st.spinner(f"Consultando bases oficiais do {area_direito} e redigindo..."):
                contexto_real = ""
                if anti_alucinacao:
                    contexto_real = buscar_contexto_juridico(f"{tipo} {fatos}", area_direito)
                
                prompt = f"""
                Atue como Advogado Especialista em Direito {area_direito}.
                Redija uma {tipo} completa e robusta.
                Cliente: {cli}. Parte Contrária: {parte_contraria}.
                Fatos: {fatos}.
                
                INSTRUÇÕES ESPECIAIS:
                1. Use o seguinte contexto real (se houver) para fundamentar: {contexto_real}
                2. Use linguagem técnica e formal.
                3. Se houver jurisprudência acima, cite-a. Se não, utilize doutrina consolidada sem inventar julgados.
                4. Estruture com: Endereçamento, Qualificação, Fatos, Direito (cite artigos), Pedidos e Valor da Causa.
                """
                
                res = tentar_gerar_conteudo(prompt, api_key)
                
                st.markdown(res)
                if "❌" not in res:
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)", 
                             (st.session_state.escritorio_atual, str(date.today()), cli, area_direito, tipo, res))

elif menu == "📜 Contratos":
    st.header("📜 Fábrica de Contratos")
    c1, c2 = st.columns(2)
    cli = c1.text_input("Contratante")
    cpf = c2.text_input("CPF/CNPJ")
    obj = st.text_area("Objeto")
    val = st.number_input("Valor", step=100.0)
    
    if st.button("GERAR CONTRATO"):
        prompt = f"Contrato de Honorários. Cliente: {cli}, CPF {cpf}. Objeto: {obj}. Valor: {val}. Contratado: {st.session_state.escritorio_atual}. Incluir cláusulas de inadimplência e foro."
        res = tentar_gerar_conteudo(prompt, api_key)
        st.markdown(res)
        st.download_button("Baixar", gerar_word(res), "Contrato.docx")

# === CALCULADORA UNIFICADA (ATUALIZADA) ===
elif menu == "🧮 Cálculos Jurídicos":
    st.header("🧮 Central de Cálculos")
    area_calc = st.selectbox("Área", ["Trabalhista", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    st.markdown("---")

    if area_calc == "Trabalhista":
        st.subheader("Rescisão Trabalhista + Insalubridade")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            adm = c1.date_input("Admissão", date(2022,1,1))
            dem = c2.date_input("Demissão", date.today())
            motivo = c3.selectbox("Motivo", ["Demissão sem Justa Causa", "Pedido de Demissão", "Justa Causa"])
            sal = st.number_input("Salário Base", value=2000.0)
            fgts = st.number_input("Saldo FGTS", value=0.0)
            aviso = st.selectbox("Aviso Prévio", ["Indenizado", "Trabalhado"])
            
            c4, c5 = st.columns(2)
            insal = c4.selectbox("Insalubridade", ["Não", "Mínimo (10%)", "Médio (20%)", "Máximo (40%)"])
            peric = c5.checkbox("Periculosidade (30%)")
            
            if st.button("CALCULAR TRABALHISTA"):
                if dem > adm:
                    v = calcular_rescisao_completa(adm, dem, sal, motivo, fgts, False, aviso, insal, peric)
                    st.table(pd.DataFrame(list(v.items()), columns=["Verba", "Valor"]))
                    st.success(f"Total: R$ {sum(v.values()):,.2f}")

    # === ATUALIZAÇÃO DA ABA CÍVEL (ART 292, LIQUIDAÇÃO, ETC) ===
    elif area_calc == "Cível (Art. 292/Liquidação)":
        tab_liq, tab_valor, tab_rev = st.tabs(["Liquidação de Sentença", "Valor da Causa (CPC)", "Revisão Bancária"])
        
        # 1. Liquidação Detalhada
        with tab_liq:
            st.info("Cálculo de Atualização + Juros + Multas Processuais + Honorários")
            
            col_l1, col_l2 = st.columns(2)
            val = col_l1.number_input("Valor Condenação")
            indice = col_l2.number_input("Índice Correção (TJ)", value=1.0)
            
            col_l3, col_l4 = st.columns(2)
            juros = col_l3.selectbox("Juros", ["1% a.m.", "Selic", "Sem Juros"])
            meses_juros = col_l4.number_input("Meses de Atraso", value=12)
            
            st.markdown("##### Acréscimos Legais")
            c1, c2, c3 = st.columns(3)
            multa_523 = c1.checkbox("Multa Art. 523 CPC (10%)")
            hon_exec = c2.checkbox("Honorários Execução (10%)")
            multa_litig = c3.checkbox("Multa Litigância Má-Fé (Específico)")
            
            if st.button("LIQUIDAR SENTENÇA"):
                res = val * indice
                val_juros = 0
                if juros == "1% a.m.": val_juros = res * (0.01 * meses_juros)
                elif juros == "Selic": val_juros = res * 0.12 # Estimativa simples
                
                subtotal = res + val_juros
                
                v_multa523 = subtotal * 0.10 if multa_523 else 0
                v_hon = subtotal * 0.10 if hon_exec else 0
                
                total = subtotal + v_multa523 + v_hon
                if multa_litig: total += val * 0.05 # Ex: 5% sobre valor corrigido
                
                st.success(f"Valor Execução: R$ {total:,.2f}")
                st.write(f"Base: {res:.2f} | Juros: {val_juros:.2f} | Multa 523: {v_multa523:.2f}")

        # 2. Valor da Causa
        with tab_valor:
            st.info("Art. 292 CPC - Definição de Valor da Causa")
            tipo = st.radio("Ação", ["Cobrança", "Alimentos", "Indenização"])
            if tipo == "Alimentos":
                m = st.number_input("Mensalidade")
                st.metric("Valor da Causa (12x)", f"R$ {m*12:,.2f}")
            elif tipo == "Cobrança":
                p = st.number_input("Principal")
                j = st.number_input("Juros Vencidos")
                m = st.number_input("Multas Contratuais")
                st.metric("Valor da Causa", f"R$ {p+j+m:,.2f}")
            elif tipo == "Indenização":
                mor = st.number_input("Danos Morais")
                mat = st.number_input("Danos Materiais")
                st.metric("Valor da Causa", f"R$ {mor+mat:,.2f}")

        # 3. Revisão
        with tab_rev:
            st.info("Revisão de Contratos (Price vs Gauss)")
            emp = st.number_input("Empréstimo")
            tx = st.number_input("Taxa (%)")
            prazo = st.number_input("Prazo")
            if st.button("SIMULAR ABUSIVIDADE"):
                j_comp = emp * ((1 + tx/100)**prazo) - emp
                j_simp = emp * (tx/100) * prazo
                st.warning(f"Economia (Gauss): R$ {j_comp - j_simp:,.2f}")

    elif area_calc == "Família":
        st.subheader("Pensão e Partilha")
        c1, c2 = st.columns(2)
        renda = c1.number_input("Renda Líquida")
        filhos = c2.slider("Filhos", 1, 5)
        if st.button("SUGERIR PENSÃO"):
            st.info(f"Sugestão ({25 + (filhos*5)}%): R$ {renda * (0.25 + (filhos*0.05)):,.2f}")

    elif area_calc == "Criminal":
        st.subheader("Dosimetria Básica")
        min_p = st.number_input("Pena Mínima")
        max_p = st.number_input("Pena Máxima")
        circ = st.slider("Circunstâncias Desfavoráveis", 0, 8)
        if st.button("CALCULAR PENA BASE"):
            base = min_p + ((max_p - min_p)/8 * circ)
            st.error(f"Pena Base: {base:.1f} anos")

elif menu == "Cofre Digital":
    st.header("📂 Arquivo Morto & Ativo")
    df = run_query("SELECT * FROM documentos WHERE escritorio = %s ORDER BY id DESC", (st.session_state.escritorio_atual,), return_data=True)
    if df is not None and not df.empty:
        for i, row in df.iterrows():
            with st.expander(f"{row['tipo']} - {row['cliente']}"):
                st.write(row['conteudo'][:200] + "...")
                st.download_button("Baixar", gerar_word(row['conteudo']), "Doc.docx", key=f"d{i}")
                if st.button("Excluir", key=f"x{i}"):
                    run_query("DELETE FROM documentos WHERE id = %s", (row['id'],))
                    st.rerun()
    else: st.info("Nenhum documento.")

elif menu == "Audiência":
    st.header("🏛️ Simulador de Audiência")
    st.info("Em breve: Simulação de perguntas cruzadas com IA.")
