import streamlit as st
import pandas as pd
import math
import networkx as nx
import matplotlib.pyplot as plt
from fpdf import FPDF

# --- BANCO DE DADOS DE MATERIAIS E CONEXÕES ---
MATERIAIS_C = {
    "PVC": 150, "Cobre": 130, "Aço Carbono (Novo)": 120, 
    "Ferro Fundido": 100, "Aço Galvanizado": 125
}

CONEXOES_K = {
    "Cotovelo 90°": 0.9, "Cotovelo 45°": 0.4, "Tê (Passagem Direta)": 0.2,
    "Tê (Saída Lateral)": 1.2, "Válvula de Gaveta (Aberta)": 0.2,
    "Válvula Globo (Aberta)": 10.0, "Válvula de Retenção": 2.5
}

st.set_page_config(page_title="Simulador de Redes Hidráulicas", layout="wide")
st.title("💧 Simulador de Perda de Carga & Bomba")

# --- BARRA LATERAL: REFERÊNCIA DE CONEXÕES ---
with st.sidebar:
    st.header("🧮 Referência de Conexões (Fator K)")
    st.write("Use esta calculadora rápida para somar os Ks e lançar na planilha.")
    
    soma_k_temp = 0.0
    for conexao, k_val in CONEXOES_K.items():
        qtd = st.number_input(f"{conexao} (K={k_val})", min_value=0, value=0, step=1)
        soma_k_temp += qtd * k_val
        
    st.info(f"**Soma Total de K = {soma_k_temp:.2f}**")
    st.divider()
    st.write("Valores de Material (C):")
    st.json(MATERIAIS_C)

# --- CONDIÇÕES DE ENTRADA (NOVO) ---
st.subheader("🚰 Condições Iniciais (Concessionária)")
col_e1, col_e2 = st.columns(2)
with col_e1:
    pressao_rua = st.number_input("Pressão Disponível na Rua (mca)", min_value=0.0, value=12.0)
with col_e2:
    tipo_entrada = st.selectbox(
        "Estrutura de Entrada (Cavalete)", 
        ["Ligação Direta (K=0)", "Cavalete com Hidrômetro 1/2\" (K=15.0)", "Cavalete com Hidrômetro 3/4\" (K=10.0)"]
    )
    # Extrai o valor de K da string selecionada
    k_entrada = float(tipo_entrada.split("K=")[1].replace(")", ""))

st.divider()

# --- PLANILHA INTERATIVA DE ENTRADA ---
st.subheader("✏️ Desenho da Rede (Planilha Interativa)")
st.write("Adicione novos trechos clicando na última linha vazia.")

if 'df_input' not in st.session_state:
    st.session_state.df_input = pd.DataFrame([{
        "Origem": "A", "Destino": "B", "Comprimento (m)": 10.0,
        "Diâmetro (mm)": 50.0, "Vazão (L/s)": 2.0, 
        "Material": "PVC", "Soma K (Conexões)": 0.9
    }])

edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Material": st.column_config.SelectboxColumn("Material", options=list(MATERIAIS_C.keys()), required=True),
        "Soma K (Conexões)": st.column_config.NumberColumn("Soma K (Conexões)", min_value=0.0, format="%.2f")
    }
)

st.session_state.df_input = edited_df

# --- CÁLCULO E RESULTADOS ---
if not edited_df.empty and st.button("🚀 Calcular Rede e Dimensionar Bomba", type="primary"):
    
    resultados = []
    for _, t in edited_df.iterrows():
        if pd.isna(t["Origem"]) or pd.isna(t["Destino"]): continue
            
        Q_m3s = t["Vazão (L/s)"] / 1000
        D_m = t["Diâmetro (mm)"] / 1000
        L = t["Comprimento (m)"]
        C = MATERIAIS_C.get(t["Material"], 150)
        soma_k = t["Soma K (Conexões)"]
        
        area = math.pi * (D_m ** 2) / 4
        v = Q_m3s / area if area > 0 else 0
        
        hf = 10.67 * L * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87)) if D_m > 0 else 0
        hl = soma_k * (v ** 2) / (2 * 9.81)
        
        resultados.append({
            "Trecho": f"{t['Origem']}-{t['Destino']}",
            "Vazão (L/s)": t["Vazão (L/s)"],
            "Velocidade (m/s)": round(v, 2),
            "P. Distr. (mca)": round(hf, 3),
            "P. Local. (mca)": round(hl, 3),
            "Total (mca)": round(hf + hl, 3)
        })
        
    df_resultados = pd.DataFrame(resultados)
    
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📋 Resultados Detalhados")
        st.dataframe(df_resultados, use_container_width=True)
        
    with col2:
        st.subheader("🗺️ Esquema da Rede")
        G = nx.DiGraph()
        for _, t in edited_df.iterrows():
            if not pd.isna(t["Origem"]) and not pd.isna(t["Destino"]):
                G.add_edge(str(t["Origem"]), str(t["Destino"]))
                
        if len(G.nodes) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            pos = nx.spring_layout(G)
            nx.draw(G, pos, with_labels=True, node_color='#4CA1AF', node_size=1200, edge_color='gray', font_weight='bold', arrows=True, ax=ax)
            st.pyplot(fig)
            
    st.divider()

    # --- MÓDULO DA BOMBA COM PRESSÃO DA RUA ---
    st.subheader("⚙️ Dimensionamento da Bomba Centrífuga")
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        desnivel = st.number_input("Desnível Geométrico (m)", min_value=0.0, value=15.0)
        rendimento = st.slider("Rendimento da Bomba (%)", 10, 100, 70) / 100.0

    with col_b2:
        vazao_max = float(df_resultados['Vazão (L/s)'].max()) if not df_resultados.empty else 2.0
        vazao_bomba = st.number_input("Vazão de Projeto da Bomba (L/s)", min_value=0.1, value=vazao_max)
        
        # Calcula perda específica do hidrômetro usando a velocidade do primeiro trecho
        v_inicial = df_resultados['Velocidade (m/s)'].iloc[0] if not df_resultados.empty else 0
        perda_entrada_mca = k_entrada * (v_inicial ** 2) / (2 * 9.81)
        
        perda_carga_total = df_resultados['Total (mca)'].sum() if not df_resultados.empty else 0
        perda_sistema_completo = perda_carga_total + perda_entrada_mca
        pressao_necessaria = desnivel + perda_sistema_completo
        
        # Desconta a pressão da rua
        amt_bomba = pressao_necessaria - pressao_rua
        
        st.write(f"**Perda de Carga do Sistema + Cavalete:** {perda_sistema_completo:.2f} mca")
        st.write(f"**Pressão Total Necessária:** {pressao_necessaria:.2f} mca")
        
        if amt_bomba <= 0:
            st.success(f"✅ **Bomba Desnecessária:** A pressão da rua ({pressao_rua} mca) atende à demanda do sistema com folga de {abs(amt_bomba):.2f} mca.")
            potencia_cv = 0.0
        else:
            potencia_cv = ((vazao_bomba / 1000) * amt_bomba * 1000) / (75 * rendimento)
            st.warning(f"**Altura Manométrica Restante (AMT da Bomba):** {amt_bomba:.2f} mca")
            st.error(f"**Potência Estimada:** {potencia_cv:.2f} cv")
