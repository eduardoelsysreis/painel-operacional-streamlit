import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# Tentativa de carregar as credenciais seguras da nuvem ou do arquivo local
try:
    USERNAME = st.secrets["api"]["username"]
    PASSWORD = st.secrets["api"]["password"]
except:
    # Fallback apenas para uso local (Não recomendado caso o repositório seja público na web)
    USERNAME = "002290"
    PASSWORD = "#Elsys2025@"

BASE_API_URL = "https://elsysequipamentos166583.protheus.cloudtotvs.com.br:4051/rest"
LOGIN_URL = f"{BASE_API_URL}/api/oauth2/v1/token"
DATA_URL = f"{BASE_API_URL}/ELS_WEBAPP/pickingsky?pageSize=4000&page=0"

STATUS_MAP = {
    "AG. SEPARACAO": "NÃO INICIADA",
    "AG. SEPARAÇÃO": "NÃO INICIADA",
    "EM SEPARACAO": "SEPARANDO",
    "EM SEPARAÇÃO": "SEPARANDO",
    "AG. NOTA SKY": "AGUARDANDO RETORNO SAP SKY",
    "AG. EMBARQUE": "AGUARDANDO DESPACHO OP.",
    "EMBARCANDO": "AGUARDANDO DESPACHO OP.",
    "AG. NOTA ELSYS": "DESPACHADO"
}

# Configuração da Página para TV
st.set_page_config(page_title="Painel de Separação - Expedição", layout="wide")

# Estilos CSS Customizados para TV com novo design
st.markdown("""
    <style>
    /* Resetando margens para maximizar uso da tela */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 100%;
        background-color: #f4f7f6;
    }
    
    /* Aumentando tamanho da fonte das métricas */
    [data-testid="stMetricValue"] {
        font-size: 3.0rem !important;
        font-weight: 800;
        color: #1f3a93;
    }
    [data-testid="stMetricLabel"] {
        font-size: 1.4rem !important;
        font-weight: bold;
        color: #555;
    }
    
    /* Títulos de colunas e seções */
    h1, h2, h3 {
        text-align: center;
        color: #2c3e50;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Container da próxima remessa */
    .next-order-container {
        background: linear-gradient(135deg, #FF416C 0%, #FF4B2B 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        margin-bottom: 20px;
        animation: pulse 2s infinite;
    }
    
    .next-order-title {
        font-size: 1.5rem;
        font-weight: bold;
        margin: 0;
        opacity: 0.9;
    }
    
    .next-order-value {
        font-size: 4.5rem;
        font-weight: 900;
        margin: 0;
        line-height: 1.2;
    }
    
    .next-order-sub {
        font-size: 1.2rem;
        margin: 0;
        opacity: 0.8;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.01); }
        100% { transform: scale(1); }
    }
    
    /* Tabelas */
    .dataframe {
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Lógica de Autenticação e Busca
@st.cache_resource(ttl=3400) # Token geralmente expira em 1 hora
def obter_token():
    session = requests.Session()
    login_headers = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "Content-Type": "application/json"
    }
    try:
        response_auth = session.post(LOGIN_URL, headers=login_headers, json={}, verify=False)
        response_auth.raise_for_status()
        token_data = response_auth.json()
        return token_data.get("access_token")
    except Exception as e:
        st.error(f"Erro ao autenticar: {e}")
        return None

def carregar_dados():
    token = obter_token()
    if not token:
        return pd.DataFrame()
    
    headers_api = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        # Ignore warning if verify=False is needed (adding to login as well just in case)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response_data = requests.get(DATA_URL, headers=headers_api, verify=False) 
        response_data.raise_for_status()
        dados = response_data.json()
        
        if isinstance(dados, dict):
            items = dados.get("items", dados)
        else:
            items = dados

        if not items:
             return pd.DataFrame()
             
        df = pd.DataFrame(items)
        if df.empty or "STATUS" not in df.columns:
            return pd.DataFrame()
            
        df = df[df["STATUS"] != "SEM REMESSA SKY"]
        # Convertemos colunas chaves para string para evitar problemas null\vazio
        if "ORDSEP" in df.columns:
            df["ORDSEP"] = df["ORDSEP"].astype(str).str.strip()
        if "ORDEM_SKY" in df.columns:
            df["ORDEM_SKY"] = df["ORDEM_SKY"].astype(str).str.strip()
            
        df["STATUS_PAINEL"] = df["STATUS"].map(STATUS_MAP).fillna(df["STATUS"])
        
        return df
    except Exception as e:
        st.error(f"Erro ao conectar na API de dados: {e}")
        return pd.DataFrame()

# Inicializa sessão para lógica de finalizados
if "historico_ordens" not in st.session_state:
    st.session_state.historico_ordens = set()
if "finalizados_hoje" not in st.session_state:
    st.session_state.finalizados_hoje = []
if "tempos_separacao" not in st.session_state:
    st.session_state.tempos_separacao = {}

# Título principal
st.title("📦 PAINEL DE SEPARAÇÃO E EXPEDIÇÃO 🚚")

# Busca os dados atuais
df_atual = carregar_dados()

if df_atual.empty:
    st.warning("Nenhum dado retornado da API no momento...")
else:
    if "ORDSEP" in df_atual.columns and "ORDEM_SKY" in df_atual.columns:
        ordens_atuais_val = df_atual.dropna(subset=['ORDSEP']).copy()
        
        # Filtra registros com ORDSEP vazios ou nan após o dropna (ex: strings vazias ou "nan")
        ordens_atuais_val = ordens_atuais_val[(ordens_atuais_val['ORDSEP'] != "") & (ordens_atuais_val['ORDSEP'].str.lower() != "nan")]
        
        conjunto_atual = set(ordens_atuais_val["ORDSEP"])
        
        # --- Lógica de Baixas / Finalizações ---
        # 1. Identificar as remessas que "sumiram" do painel
        if st.session_state.historico_ordens:
            sumiram = st.session_state.historico_ordens - conjunto_atual
            for ord_sumida in sumiram:
                hora_finalizacao = datetime.now().strftime("%H:%M:%S")
                # Previne erro com dicionário da estrutura antiga
                ja_tem = any(item.get('Ordem SEP', item.get('Ordem', '')) == ord_sumida for item in st.session_state.finalizados_hoje)
                if not ja_tem:
                    st.session_state.finalizados_hoje.insert(0, {
                        "Ordem SEP": ord_sumida, 
                        "Remessa": "N/D", 
                        "Status Final": "DESPACHADA (Sistêmica)",
                        "Hora Baixa": hora_finalizacao
                    })
                    
        # Atualiza histórico com as ordens na base atual
        st.session_state.historico_ordens = conjunto_atual
        
        # --- Limpeza e Padronização ---
        if "OPERADOR" not in df_atual.columns:
            df_atual["OPERADOR"] = "---"
            
        df_base = df_atual[[
            "ORDSEP", "ORDEM_SKY", "TRANSPORTADORA", "HORA_COLETA", "STATUS_PAINEL", "OPERADOR"
        ]].copy()
        df_base.columns = ["ORDEM SEP", "REMESSA", "TRANSPORTADORA", "HORA COLETA", "STATUS", "OPERADOR"]
        
        # --- Categorização ---
        # 1. Não Iniciadas (Fila)
        df_fila = df_base[df_base["STATUS"] == "NÃO INICIADA"].copy()
        # Ordenar as Não Iniciadas por Hora de Coleta/Ordem
        df_fila = df_fila.sort_values(by=["HORA COLETA", "ORDEM SEP"], na_position='last')
        
        # 2. Em Separação
        df_separando = df_base[df_base["STATUS"] == "SEPARANDO"].copy()
        
        # Atualiza métricas de tempo de separação
        ordens_sep_ativas = set(df_separando["ORDEM SEP"])
        for o_sep in list(st.session_state.tempos_separacao.keys()):
            if o_sep not in ordens_sep_ativas:
                del st.session_state.tempos_separacao[o_sep]
                
        for o_sep in ordens_sep_ativas:
            if o_sep not in st.session_state.tempos_separacao:
                st.session_state.tempos_separacao[o_sep] = time.time()
        
        # 3. Aguardando Despacho Op. e Retorno SKY
        status_aguardando = ["AGUARDANDO DESPACHO OP.", "AGUARDANDO RETORNO SAP SKY"]
        df_aguardando = df_base[df_base["STATUS"].isin(status_aguardando)].copy()
        
        # 4. Despachadas (Atuais)
        df_despachadas_atuais = df_base[df_base["STATUS"] == "DESPACHADO"].copy()
        df_despachadas_atuais.rename(columns={"ORDEM SEP": "Ordem SEP", "REMESSA": "Remessa"}, inplace=True)
        if not df_despachadas_atuais.empty:
            df_despachadas_atuais["Status Final"] = "DESPACHADA"
            df_despachadas_atuais["Hora Baixa"] = "---"
            df_despachadas_atuais = df_despachadas_atuais[["Ordem SEP", "Remessa", "Status Final", "Hora Baixa"]]
        
        # --- DataFrame Consolidado de Finalizadas ---
        df_finalizados_sumiram_raw = []
        for item in st.session_state.finalizados_hoje:
            ord_sep = item.get("Ordem SEP", item.get("Ordem", "N/A"))
            hora = item.get("Hora Baixa", item.get("Hora", "---"))
            df_finalizados_sumiram_raw.append({
                "Ordem SEP": ord_sep,
                "Remessa": "N/D",
                "Status Final": "DESPACHADA (Sist.)",
                "Hora Baixa": hora
            })
        df_finalizados_sumiram = pd.DataFrame(df_finalizados_sumiram_raw)
        
        if not df_finalizados_sumiram.empty and not df_despachadas_atuais.empty:
            df_finalizadas_total = pd.concat([df_despachadas_atuais, df_finalizados_sumiram], ignore_index=True)
        elif not df_finalizados_sumiram.empty:
            df_finalizadas_total = df_finalizados_sumiram
        elif not df_despachadas_atuais.empty:
            df_finalizadas_total = df_despachadas_atuais
        else:
            df_finalizadas_total = pd.DataFrame(columns=["Ordem SEP", "Remessa", "Status Final", "Hora Baixa"])
            
        if not df_finalizadas_total.empty:
            df_finalizadas_total = df_finalizadas_total.drop_duplicates(subset=["Ordem SEP"], keep='first')

        # ==== 🚨 ALERTA DA PRÓXIMA REMESSA 🚨 ====
        if not df_fila.empty:
            proxima_remessa = df_fila.iloc[0]
            remessa_val = proxima_remessa['REMESSA']
            ordem_val = proxima_remessa['ORDEM SEP']
            transp_val = proxima_remessa['TRANSPORTADORA']
            
            st.markdown(f"""
                <div class="next-order-container">
                    <p class="next-order-title">👉 PRÓXIMA REMESSA A SEPARAR 👈</p>
                    <p class="next-order-value">{remessa_val}</p>
                    <p class="next-order-sub">Ordem SEP: <b>{ordem_val}</b> | Transp: <b>{transp_val}</b></p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div class="next-order-container" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); animation: none;">
                    <p class="next-order-value" style="font-size: 3rem;">TUDO LIMPO! ✅</p>
                    <p class="next-order-sub">Nenhuma remessa aguardando separação no momento.</p>
                </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ==== GRÁFICO E MÉTRICAS GERAIS ====
        st.subheader("📊 Resumo da Operação")
        
        qtd_nao_iniciada = len(df_fila)
        qtd_separando = len(df_separando)
        qtd_aguardando = len(df_aguardando)
        qtd_finalizadas = len(df_finalizadas_total)
        
        col_metrics, col_chart = st.columns([1.5, 1])
        
        with col_metrics:
            m1, m2 = st.columns(2)
            with m1:
                st.metric("🔴 A SEPARAR", qtd_nao_iniciada)
                st.metric("🟡 EM SEPARAÇÃO", qtd_separando)
            with m2:    
                st.metric("🟠 AG. DESPACHO", qtd_aguardando)
                st.metric("🟢 FINALIZADAS", qtd_finalizadas)
                
        with col_chart:
            try:
                import plotly.express as px
                dados_grafico = pd.DataFrame({
                    "Status": ["A Separar", "Em Separação", "Ag. Despacho", "Finalizadas"],
                    "Quantidade": [qtd_nao_iniciada, qtd_separando, qtd_aguardando, qtd_finalizadas],
                })
                dados_grafico = dados_grafico[dados_grafico["Quantidade"] > 0]
                
                if not dados_grafico.empty:
                    fig = px.pie(
                        dados_grafico, 
                        values='Quantidade', 
                        names='Status', 
                        hole=0.4,
                        color='Status',
                        color_discrete_map={
                            "A Separar": "#e74c3c",
                            "Em Separação": "#f1c40f",
                            "Ag. Despacho": "#e67e22",
                            "Finalizadas": "#2ecc71"
                        }
                    )
                    fig.update_layout(
                        margin=dict(l=20, r=20, t=20, b=20),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                        height=250
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+value', 
                                      marker=dict(line=dict(color='#FFFFFF', width=2)))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Visualização indisponível.")
            except ImportError:
                st.warning("Gráfico de uso indisponível. Por favor instale o pacote `plotly` digitando `pip install plotly`")

        st.divider()
        
        # ==== TABELAS DE VISUALIZAÇÃO ====
        c_fila, c_andamento, c_fim = st.columns(3)
        
        with c_fila:
            st.markdown("<h3 style='color:#e74c3c;'>📥 FILA (NÃO INICIADAS)</h3>", unsafe_allow_html=True)
            if not df_fila.empty:
                st.dataframe(df_fila[["ORDEM SEP", "REMESSA", "TRANSPORTADORA", "HORA COLETA"]], use_container_width=True, hide_index=True)
            else:
                st.success("Fila de separação vazia.")
            
        with c_andamento:
            st.markdown("<h3 style='color:#f39c12;'>⏳ EM ANDAMENTO</h3>", unsafe_allow_html=True)
            st.markdown("**🟡 Em Separação:**")
            if not df_separando.empty:
                html_separacao = ["<div style='background: white; padding: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'>"]
                for i, row in enumerate(df_separando.itertuples(), 1):
                    ordem_v = row._1  # ORDEM SEP
                    operador_v = getattr(row, "OPERADOR", "---")
                    
                    if not operador_v or str(operador_v).strip() == "" or str(operador_v).lower() == "nan":
                        operador_v = "N/I"
                    else:
                        operador_v = str(operador_v).strip()
                        # Manter nome curto caso seja longo demais, ou deixar inteiro.
                        # Ex: 'ANA B. SILVA'
                        if len(operador_v) > 15:
                            operador_v = operador_v[:13] + ".."
                            
                    start_t = st.session_state.tempos_separacao.get(ordem_v, time.time())
                    elapsed = int(time.time() - start_t)
                    m = elapsed // 60
                    s = elapsed % 60
                    time_str = f"{m}:{s:02d}M"
                    
                    # Formato: 3 --------- l 11235 l 002290 - 1:30M l
                    html_separacao.append(f"<div style='font-family: monospace; font-size: 1.15rem; margin-bottom: 5px; border-bottom: 1px dashed #eee; padding-bottom: 3px;'>")
                    html_separacao.append(f"<b>{i}</b> --- | {ordem_v} | <span style='color:#2980b9;'>{operador_v}</span> - <b style='color:#e74c3c;'>{time_str}</b> |</div>")
                html_separacao.append("</div>")
                
                st.markdown("".join(html_separacao), unsafe_allow_html=True)
            else:
                st.info("Nenhuma ordem em separação.")
                
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            st.markdown("**🟠 Aguardando Despacho Op:**")
            if not df_aguardando.empty:
                st.dataframe(df_aguardando[["REMESSA", "STATUS"]], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma ordem aguardando despacho.")
                
        with c_fim:
            st.markdown("<h3 style='color:#27ae60;'>✅ FINALIZADAS</h3>", unsafe_allow_html=True)
            if not df_finalizadas_total.empty:
                st.dataframe(df_finalizadas_total, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma ordem concluída ainda.")
                
    else:
         st.warning("Colunas esperadas (ORDSEP, ORDEM_SKY) não encontradas nos dados retornados")

# Refresh a cada 5 segundos
time.sleep(5)
st.rerun()
