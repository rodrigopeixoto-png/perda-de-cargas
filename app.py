import streamlit as st
import pandas as pd
import math
import networkx as nx
import matplotlib.pyplot as plt
from fpdf import FPDF

# --- BANCO DE DADOS DE MATERIAIS E CONEXÕES ---
MATERIAIS_C = {
    "PVC": 150, "Cobre": 130, "Aço Carbono": 120, 
    "Ferro Fundido": 100, "Aço Galvanizado": 125
}

CONEXOES_K = {
    "Cotovelo 90°": 0.9, "Cotovelo 45°": 0.4, "Tê (Passagem Direta)": 0.2,
    "Tê (Saída Lateral)": 1.2, "Válvula de Gaveta (Aberta)": 0.2,
    "Válvula Globo (Aberta)": 10.0, "Válvula de Retenção": 2.5
}

st.set_page_config(page_title="Simulador de Redes Hidráulicas", layout="wide")
st.title("💧 Simulador de Perda de Carga & Bomba")

# --- 1. CONDIÇÕES DE ENTRADA (CONCESSIONÁRIA) ---
st.subheader("🚰 Condições da Ligação de Água (Rua)")
col_e1, col_e2, col_e3 = st.columns(3)
with col_e1:
    pressao_rua = st.number_input("Pressão Disponível na Rua (mca)", min_value=0.0, value=15.0)
with col_e2:
    tipo_entrada = st.selectbox(
        "Estrutura do Cavalete / Hidrômetro", 
        [
            "Ligação Direta (K=0.0)", 
            "Hidrômetro Padrão 1/2\" (K=15.0)", 
            "Hidrômetro Padrão 3/4\" (K=10.0)",
            "Hidrômetro Woltmann 2\" (K=4.0)"
        ]
    )
    k_entrada = float(tipo_entrada.split("K=")[1].replace(")", ""))
with col_e3:
    vazao_entrada = st.number_input("Vazão de Entrada (L/s)", min_value=0.1, value=2.0)

st.divider()

# --- 2. CONSTRUTOR DINÂMICO DE RAMAIS ---
st.subheader("✏️ Construtor de Ramais")

if 'trechos' not in st.session_state:
    # Estado inicial com 1 trecho vazio
    st.session_state.trechos = [{
        "Origem": "Rua", "Destino": "A", "Comprimento": 15.0,
        "Diâmetro": 60.0, "Vazão": vazao_entrada, "Material": "PVC",
        "Conexoes": {k: 0 for k in CONEXOES_K.keys()}
    }]

col_add, col_rem = st.columns([1, 5])
with col_add:
    if st.button("➕ Adicionar Ramal", type="primary"):
        st.session_state.trechos.append({
            "Origem": "", "Destino": "", "Comprimento": 10.0,
            "Diâmetro": 25.0, "Vazão": 1.0, "Material": "PVC",
            "Conexoes": {k: 0 for k in CONEXOES_K.keys()}
        })
        st.rerun()
with col_rem:
    if st.button("🗑️ Remover Último") and len(st.session_state.trechos) > 0:
        st.session_state.trechos.pop()
        st.rerun()

# Renderiza os trechos interativos
for i, t in enumerate(st.session_state.trechos):
    with st.container(border=True):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        t["Origem"] = c1.text_input("Origem", t["Origem"], key=f"o_{i}")
        t["Destino"] = c2.text_input("Destino", t["Destino"], key=f"d_{i}")
        t["Comprimento"] = c3.number_input("Comp. (m)", 0.1, 5000.0, t["Comprimento"], key=f"c_{i}")
        t["Diâmetro"] = c4.number_input("Diâm. (mm)", 1.0, 1000.0, t["Diâmetro"], key=f"di_{i}")
        t["Vazão"] = c5.number_input("Vazão (L/s)", 0.01, 1000.0, t["Vazão"], key=f"v_{i}")
        t["Material"] = c6.selectbox("Material", list(MATERIAIS_C.keys()), index=list(MATERIAIS_C.keys()).index(t["Material"]), key=f"m_{i}")
        
        with st.expander(f"🛠️ Selecionar Conexões do Ramal ({t['Origem']} ➔ {t['Destino']})"):
            ccols = st.columns(4)
            for j, (nome_con, k_val) in enumerate(CONEXOES_K.items()):
                # Atualiza a quantidade de cada conexão no dicionário
                qtd = ccols[j % 4].number_input(f"{nome_con}", 0, 50, t.get("Conexoes", {}).get(nome_con, 0), key=f"cx_{i}_{nome_con}")
                t["Conexoes"][nome_con] = qtd

st.divider()

# --- 3. CÁLCULOS E RESULTADOS ---
if st.button("🚀 Processar Simulação de Rede", type="primary", use_container_width=True):
    
    resultados = []
    for t in st.session_state.trechos:
        if not t["Origem"] or not t["Destino"]: continue
            
        Q_m3s = t["Vazão"] / 1000
        D_m = t["Diâmetro"] / 1000
        L = t["Comprimento"]
        C = MATERIAIS_C[t["Material"]]
        
        # Soma K dinâmico baseado nas quantidades inseridas
        soma_k = sum(qtd * CONEXOES_K[nome] for nome, qtd in t["Conexoes"].items())
        
        area = math.pi * (D_m ** 2) / 4
        v = Q_m3s / area if area > 0 else 0
        
        hf = 10.67 * L * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87)) if D_m > 0 else 0
        hl = soma_k * (v ** 2) / (2 * 9.81)
        
        resultados.append({
            "Trecho": f"{t['Origem']} ➔ {t['Destino']}",
            "Diam(mm)": t["Diâmetro"],
            "Q(L/s)": t["Vazão"],
            "Vel(m/s)": round(v, 2),
            "ΣK": round(soma_k, 2),
            "P. Distr(mca)": round(hf, 3),
            "P. Local(mca)": round(hl, 3),
            "Total(mca)": round(hf + hl, 3)
        })
        
    df_resultados = pd.DataFrame(resultados)
    
    col_r1, col_r2 = st.columns([5, 2])
    with col_r1:
        st.subheader("📋 Resumo Hidráulico")
        st.dataframe(df_resultados, use_container_width=True)
        
    with col_r2:
        st.subheader("🗺️ Diagrama Unifilar")
        G = nx.DiGraph()
        for t in st.session_state.trechos:
            if t["Origem"] and t["Destino"]:
                G.add_edge(t["Origem"], t["Destino"], label=f"Ø{t['Diâmetro']}")
                
        if len(G.nodes) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            pos = nx.spring_layout(G)
            nx.draw(G, pos, with_labels=True, node_color='#4CA1AF', node_size=1000, edge_color='gray', font_weight='bold', font_size=8, arrows=True, ax=ax)
            edge_labels = nx.get_edge_attributes(G, 'label')
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)
            st.pyplot(fig)
            
    st.divider()

    # --- 4. BALANÇO DE ENERGIA E DIMENSIONAMENTO ---
    st.subheader("⚖️ Balanço de Pressão e Bomba")
    
    v_inicial = df_resultados['Vel(m/s)'].iloc[0] if not df_resultados.empty else 0
    perda_entrada_mca = k_entrada * (v_inicial ** 2) / (2 * 9.81)
    perda_rede = df_resultados['Total(mca)'].sum() if not df_resultados.empty else 0
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        desnivel = st.number_input("Desnível Geométrico Total (m)", min_value=0.0, value=10.0)
        rendimento = st.slider("Rendimento da Bomba (%)", 10, 100, 75) / 100.0
        
    with col_b2:
        pressao_necessaria = desnivel + perda_rede + perda_entrada_mca
        amt_bomba = pressao_necessaria - pressao_rua
        
        st.write(f"**Perda de Carga (Rede + Cavalete):** {(perda_rede + perda_entrada_mca):.2f} mca")
        st.write(f"**Energia Total Exigida:** {pressao_necessaria:.2f} mca")
        
        if amt_bomba <= 0:
            st.success(f"✅ **Escoamento Natural:** A pressão da rua ({pressao_rua:.1f} mca) atende ao sistema. Pressão residual de {abs(amt_bomba):.2f} mca no ponto final.")
        else:
            potencia_cv = ((vazao_entrada / 1000) * amt_bomba * 1000) / (75 * rendimento)
            st.warning(f"⚠️ **Pressão Insuficiente:** A rede requer pressurização suplementar.")
            st.error(f"**AMT da Bomba (Buster):** {amt_bomba:.2f} mca  \n**Potência Estimada:** {potencia_cv:.2f} cv")
