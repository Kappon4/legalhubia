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
import sys
import subprocess

# --- SETUP E DEPENDÊNCIAS ---
try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

# ==========================================================
# 1. CONFIGURAÇÃO VISUAL
# ==========================================================
st.set_page_config(
    page_title="LegalHub Elite v8.2.1", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# 2. CONEXÃO COM BANCO DE DADOS (BLINDADA)
# ==========================================================
try:
    DB_URI = st.secrets["DB_URI"]
    API_KEY_FIXA = st.secrets["GOOGLE_API_KEY"]
    USAR_SQLITE_BACKUP = False
except:
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
    """Executa queries com tratamento de erro visível."""
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if not USAR_SQLITE_BACKUP: 
            query = query.replace('?', '%s')
            
        c.execute(query, params)
        
        if return_data:
            data = c.fetchall()
            col_names = [desc[0] for desc in c.description] if c.description else []
            conn.close()
            return pd.DataFrame(data, columns=col_names)
        else:
            conn.commit()
            conn.close()
            return True
            
    except Exception as e:
        if conn: conn.close()
        print(f"Erro DB: {e}") 
        return None

# ==========================================================
# 3. FUNÇÕES (IA, PDF, WORD)
# ==========================================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f: data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError: return None

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
    """Busca Anti-Alucinação em fontes oficiais."""
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
    except: pass
    return "\n\n[NENHUMA JURISPRUDÊNCIA ESPECÍFICA ENCONTRADA NOS CANAIS OFICIAIS]"

def tentar_gerar_conteudo(prompt, api_key_val):
    chave = api_key_val if api_key_val else API_KEY_FIXA
    if not chave: return "⚠️ Erro: API Key não configurada."
    genai.configure(api_key=chave)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        return model.generate_content(prompt).text
    except Exception as e: return f"❌ Erro IA: {str(e)}"

# ==========================================================
# 4. FUNÇÕES DE CÁLCULO (MANTIDAS)
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
    verbas["Saldo Salário"] = (remuneracao/30) * d2.day
    
    dias_aviso = min(90, 30 + (3 * anos_completos))
    
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
# 5. CSS VISUAL
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
        .plan-card {{ background: rgba(15,23,42,0.85); border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; text-align: center; }}
        .lock-screen {{ border: 1px solid var(--neon-red); background: rgba(255, 0, 85, 0.05); border-radius: 10px; padding: 40px; text-align: center; margin-top: 20px; }}
        .lock-title {{ color: var(--neon-red) !important; font-family: 'Rajdhani'; font-size: 2rem; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)
local_css()

# ==========================================================
# 6. LOGIN & CADASTRO (BLINDADO)
# ==========================================================
try:
    if USAR_SQLITE_BACKUP:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    else:
        run_query("CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, senha TEXT, escritorio TEXT, email_oab TEXT, creditos INTEGER DEFAULT 10, plano TEXT DEFAULT 'starter')")
        run_query("CREATE TABLE IF NOT EXISTS documentos (id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, escritorio TEXT, data_criacao TEXT, cliente TEXT, area TEXT, tipo TEXT, conteudo TEXT)")
    
    # Garante Admin (Sempre minúsculo)
    run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING", ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full'))
except: pass

if "logado" not in st.session_state: st.session_state.logado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center; font-size: 4rem;'>🛡️</h1>", unsafe_allow_html=True)
        st.markdown("""<div style='text-align: center;'><h1 class='tech-header' style='font-size: 2.5rem;'>LEGALHUB ELITE</h1></div>""", unsafe_allow_html=True)

        if USAR_SQLITE_BACKUP: st.warning("⚠️ MODO OFFLINE")
        else: st.success("☁️ CONEXÃO SEGURA ATIVA")
            
        with st.container(border=True):
            tab_login, tab_cadastro = st.tabs(["🔐 ENTRAR", "📝 CRIAR CONTA"])
            
            with tab_login:
                user_input = st.text_input("Usuário", key="login_user")
                pwd_input = st.text_input("Senha", type="password", key="login_pwd")
                
                c_entrar, c_reset = st.columns(2)
                
                if c_entrar.button("LOGIN", use_container_width=True):
                    # --- NORMALIZAÇÃO: TUDO MINÚSCULO E SEM ESPAÇOS ---
                    u_clean = user_input.strip().lower()
                    p_clean = pwd_input.strip()
                    
                    # 1. Verifica se usuário existe
                    user_check = run_query("SELECT * FROM usuarios WHERE username = %s", (u_clean,), return_data=True)
                    
                    if user_check is None or user_check.empty:
                        st.error("❌ Usuário não encontrado.")
                    else:
                        # 2. Verifica a senha
                        res = run_query("SELECT * FROM usuarios WHERE username = %s AND senha = %s", (u_clean, p_clean), return_data=True)
                        if res is not None and not res.empty:
                            st.session_state.logado = True
                            st.session_state.usuario_atual = u_clean
                            st.session_state.escritorio_atual = res.iloc[0]['escritorio']
                            st.session_state.plano_atual = res.iloc[0]['plano']
                            st.rerun()
                        else:
                            st.error("❌ Senha incorreta.")
                
                if c_reset.button("🆘 Resetar Admin", use_container_width=True):
                    if run_query("INSERT INTO usuarios (username, senha, escritorio, email_oab, creditos, plano) VALUES ('admin', 'admin', 'Master Office', 'adm@lh.com', 9999, 'full') ON CONFLICT (username) DO UPDATE SET senha = 'admin'"):
                        st.success("Admin resetado! Use: admin / admin")
                    else:
                        st.error("Erro ao resetar. Verifique conexão.")

            with tab_cadastro:
                new_user = st.text_input("Novo Usuário", key="cad_user")
                new_pwd = st.text_input("Nova Senha", type="password", key="cad_pwd")
                new_office = st.text_input("Nome do Escritório", key="cad_office")
                
                if st.button("CADASTRAR", use_container_width=True):
                    if new_user and new_pwd and new_office:
                        # NORMALIZAÇÃO NO CADASTRO
                        user_final = new_user.strip().lower()
                        pwd_final = new_pwd.strip()
                        
                        # Verifica duplicidade
                        check = run_query("SELECT * FROM usuarios WHERE username = %s", (user_final,), return_data=True)
                        if check is not None and not check.empty:
                            st.error("⚠️ Este usuário já existe!")
                        else:
                            # Tenta inserir
                            sucesso = run_query("INSERT INTO usuarios (username, senha, escritorio, creditos, plano) VALUES (%s, %s, %s, 10, 'starter')", (user_final, pwd_final, new_office))
                            
                            # Verifica se gravou de verdade
                            double_check = run_query("SELECT * FROM usuarios WHERE username = %s", (user_final,), return_data=True)
                            
                            if sucesso and not double_check.empty:
                                st.success(f"✅ Cadastro realizado! Usuário: {user_final}")
                                time.sleep(1)
                                # Auto Login
                                st.session_state.logado = True
                                st.session_state.usuario_atual = user_final
                                st.session_state.escritorio_atual = new_office
                                st.session_state.plano_atual = 'starter'
                                st.rerun()
                            else:
                                st.error("❌ Erro fatal ao salvar no banco. Tente novamente.")
                    else:
                        st.warning("Preencha todos os campos.")
        st.markdown("<div style='text-align:center; margin-top:10px; color: #475569;'>SYSTEM V8.2 // SECURE</div>", unsafe_allow_html=True)
    st.stop()

# ==========================================================
# 7. APLICAÇÃO PRINCIPAL
# ==========================================================
if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
else: api_key = st.text_input("🔑 API Key:", type="password", key="sidebar_api_key")

df_user = run_query("SELECT creditos, plano FROM usuarios WHERE username = %s", (st.session_state.usuario_atual,), return_data=True)
if df_user is not None and not df_user.empty:
    creditos_atuais = df_user.iloc[0]['creditos']
    st.session_state.plano_atual = df_user.iloc[0]['plano']
else: creditos_atuais = 0

col_logo, col_menu = st.columns([1, 4])
with col_logo: st.markdown("""<div class='header-logo'><h1 class='tech-header'>LEGALHUB<span>ELITE</span></h1></div>""", unsafe_allow_html=True)
with col_menu:
    mapa_nav = {"Dashboard": "📊 Dashboard", "Redator IA": "✍️ Redator Jurídico", "Contratos": "📜 Contratos", "Calculos": "🧮 Cálculos Jurídicos", "Audiência": "🏛️ Estratégia de Audiência", "Gestão Casos": "📂 Gestão de Casos", "Monitor Prazos": "🚦 Monitor de Prazos", "Assinatura": "💎 Planos & Upgrade"}
    opcoes_menu = list(mapa_nav.keys())
    idx_radio = 0
    if st.session_state.get("navegacao_override"):
        try: idx_radio = opcoes_menu.index([k for k, v in mapa_nav.items() if v == st.session_state.navegacao_override][0])
        except: pass
        st.session_state.navegacao_override = None
    escolha_menu = st.radio("Menu Navegação", options=opcoes_menu, index=idx_radio, horizontal=True, label_visibility="collapsed")
    menu_opcao = mapa_nav[escolha_menu]

st.markdown("---")
with st.sidebar:
    st.markdown(f"<div style='font-size:0.8rem;'>User: {st.session_state.usuario_atual}<br>Banca: {st.session_state.escritorio_atual}</div>", unsafe_allow_html=True)
    p_label = st.session_state.plano_atual.upper()
    cor_p = "#FFD700" if p_label == "FULL" else "#00F3FF"
    st.markdown(f"<div style='border:1px solid {cor_p}; padding:5px; border-radius:5px; text-align:center; color:{cor_p}; margin:10px 0; font-weight:bold;'>PLANO: {p_label}</div>", unsafe_allow_html=True)

    # --- NOVO: PAINEL DE ADMINISTRAÇÃO (ADICIONADO AQUI) ---
    with st.expander("⚙️ ADMIN: Gerenciar Conta"):
        novo_plano = st.selectbox("Mudar Plano Para:", ["starter", "full", "criminal", "trabalhista", "civil"])
        if st.button("Atualizar Plano"):
            run_query("UPDATE usuarios SET plano = %s WHERE username = %s", (novo_plano, st.session_state.usuario_atual))
            st.session_state.plano_atual = novo_plano
            st.success("Plano atualizado! Recarregando...")
            time.sleep(1)
            st.rerun()

    st.markdown("<h4 style='font-size:1rem;'>CRÉDITOS</h4>", unsafe_allow_html=True)
    st.progress(min(creditos_atuais/100, 1.0))
    if st.button("LOGOUT"): st.session_state.logado = False; st.rerun()

# --- TELAS ---

if menu_opcao == "📊 Dashboard":
    st.header("📊 Visão Geral")
    c1, c2 = st.columns(2)
    docs = run_query("SELECT count(*) FROM documentos WHERE escritorio = %s", (st.session_state.escritorio_atual,), return_data=True)
    c1.metric("Documentos", docs.iloc[0][0] if docs is not None else 0)
    c2.metric("Plano", st.session_state.plano_atual.upper())
    
    st.subheader("Acesso Rápido")
    c1, c2 = st.columns(2)
    if c1.button("Nova Petição"): st.session_state.navegacao_override = "✍️ Redator Jurídico"; st.rerun()
    if c2.button("Novo Cálculo"): st.session_state.navegacao_override = "🧮 Cálculos Jurídicos"; st.rerun()

elif menu_opcao == "✍️ Redator Jurídico":
    st.header("✍️ Redator IA (Anti-Alucinação)")
    area = st.selectbox("Área", ["Cível", "Trabalhista", "Criminal", "Tributário", "Previdenciário"])
    
    pecas = []
    if area == "Cível": pecas = ["Petição Inicial", "Contestação", "Réplica", "Agravo de Instrumento", "Apelação", "Embargos de Declaração", "Execução"]
    elif area == "Trabalhista": pecas = ["Reclamação Trabalhista", "Contestação", "Recurso Ordinário", "Recurso de Revista", "Consignação"]
    elif area == "Criminal": pecas = ["Resposta à Acusação", "Memoriais", "Habeas Corpus", "Relaxamento de Prisão", "Apelação", "RSE"]
    elif area == "Tributário": pecas = ["Anulatória de Débito", "Mandado de Segurança", "Embargos à Execução Fiscal", "Repetição de Indébito"]
    elif area == "Previdenciário": pecas = ["Petição Inicial (Concessão)", "Recurso Administrativo", "Aposentadoria Especial", "Auxílio-Doença"]
    
    tipo = st.selectbox("Peça", pecas)
    c1, c2 = st.columns(2)
    cli = c1.text_input("Cliente")
    adv = c2.text_input("Parte Contrária")
    fatos = st.text_area("Fatos", height=150)
    busca_real = st.checkbox("🔍 Buscar Jurisprudência Real (STF/STJ/TST)", value=True)
    
    if st.button("GERAR PEÇA"):
        if fatos and cli:
            with st.spinner("Pesquisando e Redigindo..."):
                ctx = ""
                if busca_real: ctx = buscar_contexto_juridico(f"{tipo} {fatos}", area)
                
                prompt = f"Advogado {area}. Redija {tipo}. Cliente: {cli} vs {adv}. Fatos: {fatos}. {ctx}. Cite leis e jurisprudência se houver."
                res = tentar_gerar_conteudo(prompt, api_key)
                st.markdown(res)
                if "❌" not in res:
                    st.download_button("Baixar DOCX", gerar_word(res), f"{tipo}.docx")
                    run_query("INSERT INTO documentos (escritorio, data_criacao, cliente, area, tipo, conteudo) VALUES (%s, %s, %s, %s, %s, %s)", 
                             (st.session_state.escritorio_atual, str(date.today()), cli, area, tipo, res))

elif menu_opcao == "📜 Contratos":
    st.header("📜 Fábrica de Contratos")
    c1, c2 = st.columns(2)
    cli = c1.text_input("Contratante")
    cpf = c2.text_input("CPF/CNPJ")
    obj = st.text_area("Objeto")
    val = st.number_input("Valor", step=100.0)
    if st.button("GERAR CONTRATO"):
        res = tentar_gerar_conteudo(f"Contrato honorários. Cliente {cli}, CPF {cpf}. Objeto: {obj}. Valor R$ {val}. Contratado: {st.session_state.escritorio_atual}", api_key)
        st.markdown(res)
        st.download_button("Baixar", gerar_word(res), "Contrato.docx")

# === CÁLCULOS COMPLETOS (V7.8 +) ===
elif menu_opcao == "🧮 Cálculos Jurídicos":
    st.header("🧮 Calculadoras Jurídicas")
    area_calc = st.selectbox("Área", ["Trabalhista (CLT)", "Cível (Art. 292/Liquidação)", "Família", "Tributária", "Criminal"])
    st.divider()

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
        
        with tab1: # Liquidação
            val = st.number_input("Valor Condenação")
            idx = st.number_input("Índice Correção", value=1.0)
            juros = st.selectbox("Juros", ["1% a.m.", "Selic", "Sem"])
            multa = st.checkbox("Multa Art. 523 (10%)")
            hon = st.checkbox("Honorários Execução (10%)")
            if st.button("LIQUIDAR"):
                res = val * idx
                if juros == "1% a.m.": res *= 1.12 
                total = res + (res*0.1 if multa else 0) + (res*0.1 if hon else 0)
                st.success(f"Total Execução: R$ {total:,.2f}")
        
        with tab2: # Valor da Causa
            tipo = st.radio("Ação", ["Cobrança", "Alimentos", "Indenização"])
            base = st.number_input("Valor Base")
            if st.button("CALCULAR CAUSA"):
                final = base * 12 if tipo == "Alimentos" else base
                st.info(f"Valor da Causa: R$ {final:,.2f}")

        with tab3: # Revisão
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

elif menu == "📂 Gestão de Casos":
    st.header("📂 Cofre Digital")
    df = run_query("SELECT * FROM documentos WHERE escritorio = %s ORDER BY id DESC", (st.session_state.escritorio_atual,), return_data=True)
    if df is not None and not df.empty:
        for i, row in df.iterrows():
            with st.expander(f"{row['tipo']} - {row['cliente']}"):
                st.write(row['conteudo'][:200])
                st.download_button("Baixar", gerar_word(row['conteudo']), "Doc.docx", key=f"d{i}")
                if st.button("Excluir", key=f"x{i}"):
                    run_query("DELETE FROM documentos WHERE id = %s", (row['id'],))
                    st.rerun()
    else: st.info("Cofre vazio.")

elif menu == "Audiência":
    st.header("🏛️ Simulador de Audiência")
    st.info("Em breve: Simulação de perguntas cruzadas com IA.")

st.markdown("---")
st.markdown("<center>🔒 LEGALHUB ELITE v8.2.1 | POSTGRESQL SECURE</center>", unsafe_allow_html=True)
