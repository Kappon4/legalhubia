import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from docx import Document
from io import BytesIO
from duckduckgo_search import DDGS

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="LegalHub IA", page_icon="⚖️", layout="wide")
st.title("⚖️ LegalHub IA (Web & Jurisprudência)")

# 2. CONFIGURAÇÃO DE SEGURANÇA (API KEY)
st.sidebar.header("Configuração")

# Tenta pegar a chave do cofre de segredos do Streamlit
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.sidebar.success("✅ Chave de API carregada do sistema.")
else:
    # Se não houver segredo configurado (ex: rodando localmente), pede manual
    api_key = st.sidebar.text_input("Cole sua Chave API Google:", type="password")

# 3. FUNÇÕES INTELIGENTES
def descobrir_modelos():
    """Lista modelos disponíveis na conta"""
    try:
        modelos = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos.append(m.name)
        return modelos
    except:
        return []

def buscar_jurisprudencia_real(tema, qtd=5):
    """Busca focada em STF, STJ e Jusbrasil"""
    try:
        # Busca unificada com filtros de site
        query = f"{tema} (ementa OR acordao OR jurisprudencia) (site:stf.jus.br OR site:stj.jus.br OR site:jusbrasil.com.br)"
        
        resultados_formatados = ""
        # Realiza a busca
        results = DDGS().text(query, region="br-pt", max_results=qtd)
        
        if not results:
            return "Nenhuma jurisprudência encontrada nesses tribunais."

        for i, r in enumerate(results):
            resultados_formatados += f"\n--- FONTE {i+1} ({r['title']}) ---\n"
            resultados_formatados += f"Resumo: {r['body']}\n"
            resultados_formatados += f"Link: {r['href']}\n"
        
        return resultados_formatados
    except Exception as e:
        return f"Erro na busca online: {e}"

def gerar_word(texto_ia, titulo="Documento Jurídico"):
    """Gera o arquivo .docx para download"""
    doc = Document()
    doc.add_heading(titulo, 0)
    for paragrafo in texto_ia.split('\n'):
        if paragrafo.strip():
            doc.add_paragraph(paragrafo)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def extrair_texto_pdf(arquivo):
    """Lê o conteúdo de arquivos PDF"""
    try:
        leitor = PdfReader(arquivo)
        texto = ""
        for pag in leitor.pages:
            texto += pag.extract_text()
        return texto
    except:
        return None

# 4. LÓGICA PRINCIPAL
if api_key:
    # Configura o Gemini com a chave (seja dos segredos ou manual)
    genai.configure(api_key=api_key)
    modelos = descobrir_modelos()
    
    if modelos:
        # Seleciona automaticamente o primeiro modelo disponível
        modelo_atual = st.sidebar.selectbox("Modelo Inteligente:", modelos, index=0)
        
        # Cria as abas da aplicação
        tab1, tab2, tab3 = st.tabs(["✍️ Redator (STF/STJ)", "📂 Analisar PDF", "💬 Chat Estratégico"])
        
        # --- ABA 1: GERADOR COM BUSCA ESPECÍFICA ---
        with tab1:
            st.header("Gerador de Peças (STF, STJ, Jusbrasil)")
            col1, col2 = st.columns(2)
            with col1:
                tipo = st.selectbox("Tipo da Peça", ["Petição Inicial", "Contestação", "Réplica", "Recurso Especial", "Recurso Extraordinário", "Habeas Corpus"])
                area = st.selectbox("Área", ["Cível", "Trabalhista", "Família", "Criminal", "Previdenciário", "Constitucional"])
                usar_web = st.checkbox("🔎 Buscar Jurisprudência (STF/STJ/Jusbrasil)", value=True)
                
            with col2:
                fatos = st.text_area("Fatos e Fundamentos:", height=200, placeholder="Ex: Recurso sobre ICMS na base de cálculo do PIS/COFINS...")
            
            if st.button("✨ Gerar Minuta"):
                if not fatos:
                    st.warning("Preencha os fatos.")
                else:
                    status_busca = st.empty()
                    contexto_juridico = ""

                    # Se a busca web estiver ativa
                    if usar_web:
                        status_busca.info(f"🕵️‍♂️ Vasculhando STF, STJ e Jusbrasil sobre '{fatos[:30]}...'")
                        termo_busca = f"{area} {tipo} {fatos}" 
                        contexto_juridico = buscar_jurisprudencia_real(termo_busca)
                        status_busca.success("✅ Jurisprudência de Alta Corte encontrada!")
                        with st.expander("Ver Fontes Encontradas"):
                            st.text(contexto_juridico)

                    with st.spinner("A IA está redigindo baseada nas fontes..."):
                        try:
                            model = genai.GenerativeModel(modelo_atual)
                            
                            prompt = f"""Atue como advogado sênior especialista em Tribunais Superiores.
Redija uma {tipo} na área {area}.

FATOS DO CASO:
{fatos}

JURISPRUDÊNCIA COLETADA (STF/STJ/Jusbrasil):
{contexto_juridico}

INSTRUÇÕES DE ESCRITA:
1. Priorize citar as decisões do STF e STJ encontradas acima.
2. Se houver divergência, argumente a favor do cliente.
3. Cite os links das fontes como notas de rodapé ou no corpo do texto se relevante.
4. Estrutura formal completa.
"""
                            
                            response = model.generate_content(prompt)
                            texto_gerado = response.text
                            
                            st.markdown(texto_gerado)
                            
                            # Botão de Download
                            st.download_button(
                                label="📥 Baixar Documento (.docx)",
                                data=gerar_word(texto_gerado, f"{tipo} - {area}"),
                                file_name=f"Minuta_{tipo}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                        except Exception as e:
                            st.error(f"Erro: {e}")

        # --- ABA 2: LEITOR DE PDF ---
        with tab2:
            st.header("Leitura de Processos")
            upload = st.file_uploader("Subir PDF", type="pdf")
            if upload:
                texto = extrair_texto_pdf(upload)
                if texto:
                    st.success(f"PDF carregado ({len(texto)} caracteres).")
                    pergunta = st.text_input("O que deseja saber sobre o arquivo?")
                    if st.button("🔍 Analisar Arquivo"):
                         model = genai.GenerativeModel(modelo_atual)
                         res = model.generate_content(f"Responda com base no texto: {texto}\nPergunta: {pergunta}")
                         st.write(res.text)

        # --- ABA 3: CHAT ESTRATÉGICO ---
        with tab3:
            st.header("Chat Estratégico")
            if "hist" not in st.session_state: st.session_state.hist = []
            
            for m in st.session_state.hist: 
                st.chat_message(m["role"]).write(m["content"])
            
            if p := st.chat_input("Mensagem..."):
                st.chat_message("user").write(p)
                st.session_state.hist.append({"role":"user", "content":p})
                try:
                    model = genai.GenerativeModel(modelo_atual)
                    res = model.generate_content(p).text
                    st.chat_message("assistant").write(res)
                    st.session_state.hist.append({"role":"assistant", "content":res})
                except: pass

    else:
        st.warning("⚠️ Aguardando conexão. Verifique se a chave API está nos 'Secrets' ou cole na barra lateral.")
else:
    st.info("👈 Configure sua API Key para começar.")
