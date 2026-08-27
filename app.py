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
st.title("💧 Simulador de Perda de Carga & Lista de Materiais")

# --- 1. CONDIÇÕES DE ENTRADA (CONCESSIONÁRIA) ---
st.subheader("🚰 Condições da Ligação de Água (Rua)")
col_e1, col_e2, col_e3 = st.columns(3)
with col_e1:
    pressao_rua = st.number_input("Pressão Disponível na Rua (mca)", min_value=0.0, value=15.0)
with col_e2:
    tipo_entrada = st.selectbox(
        "Estrutura do Cavalete / Hidrômetro", 
        ["Ligação Direta (K=0.0)", "Hidrômetro Padrão 1/2\" (K=15.0)", "Hidrômetro Padrão 3/4\" (K=10.0)", "Hidrômetro Woltmann 2\" (K=4.0)"]
    )
    k_entrada = float(tipo_entrada.split("K=")[1].replace(")", ""))
with col_e3:
    velocidade_entrada = st.number_input("Velocidade no Alimentador (m/s)", min_value=0.1, value=1.5, help="Define a vazão inicial baseada no diâmetro do primeiro trecho.")

st.divider()

# --- 2. CONSTRUTOR DINÂMICO DE RAMAIS ---
st.subheader("✏️ Construtor de Ramais")

if 'trechos' not in st.session_state:
    st.session_state.trechos = [{
        "Origem": "Rua", "Destino": "A", "Comprimento": 15.0,
        "Diâmetro": 60.0, "Vazão": 0.0, "Material": "PVC",
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

for i, t in enumerate(st.session_state.trechos):
    with st.container(border=True):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        t["Origem"] = c1.text_input("Origem", t["Origem"], key=f"o_{i}")
        t["Destino"] = c2.text_input("Destino", t["Destino"], key=f"d_{i}")
        t["Comprimento"] = c3.number_input("Comp. (m)", 0.1, 5000.0, float(t["Comprimento"]), key=f"c_{i}")
        t["Diâmetro"] = c4.number_input("Diâm. (mm)", 1.0, 1000.0, float(t["Diâmetro"]), key=f"di_{i}")
        
        # O primeiro trecho (Alimentador) tem a vazão calculada automaticamente
        if i == 0:
            d_m = t["Diâmetro"] / 1000
            vazao_calc = (velocidade_entrada * math.pi * (d_m**2) / 4) * 1000
            t["Vazão"] = float(vazao_calc)
            c5.number_input("Vazão (L/s)", value=float(t["Vazão"]), key=f"v_{i}_calc", disabled=True, help="Calculada automaticamente pela velocidade x área.")
        else:
            t["Vazão"] = c5.number_input("Vazão (L/s)", 0.01, 1000.0, float(t["Vazão"]), key=f"v_{i}")
            
        t["Material"] = c6.selectbox("Material", list(MATERIAIS_C.keys()), index=list(MATERIAIS_C.keys()).index(t["Material"]), key=f"m_{i}")
        
        with st.expander(f"🛠️ Selecionar Conexões do Ramal ({t['Origem']} ➔ {t['Destino']})"):
            ccols = st.columns(4)
            for j, (nome_con, k_val) in enumerate(CONEXOES_K.items()):
                qtd = ccols[j % 4].number_input(f"{nome_con}", 0, 50, t.get("Conexoes", {}).get(nome_con, 0), key=f"cx_{i}_{nome_con}")
                t["Conexoes"][nome_con] = qtd

st.divider()

# --- 3. PROCESSAMENTO E LISTA DE MATERIAIS ---
if st.button("🚀 Processar Simulação Completa", type="primary", use_container_width=True):
    
    resultados = []
    tubos_agrupados = {}
    conexoes_totais = {k: 0 for k in CONEXOES_K.keys()}

    for t in st.session_state.trechos:
        if not t["Origem"] or not t["Destino"]: continue
            
        Q_m3s = t["Vazão"] / 1000
        D_m = t["Diâmetro"] / 1000
        L = t["Comprimento"]
        C = MATERIAIS_C[t["Material"]]
        
        soma_k = sum(qtd * CONEXOES_K[nome] for nome, qtd in t["Conexoes"].items())
        area = math.pi * (D_m ** 2) / 4
        v = Q_m3s / area if area > 0 else 0
        
        hf = 10.67 * L * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87)) if D_m > 0 else 0
        hl = soma_k * (v ** 2) / (2 * 9.81)
        
        resultados.append({
            "Trecho": f"{t['Origem']} ➔ {t['Destino']}", "Diam(mm)": t["Diâmetro"],
            "Q(L/s)": round(t["Vazão"], 2), "Vel(m/s)": round(v, 2), "P. Distr(mca)": round(hf, 3),
            "P. Local(mca)": round(hl, 3), "Total(mca)": round(hf + hl, 3)
        })

        chave_tubo = f"{t['Material']} Ø {t['Diâmetro']:.1f} mm"
        tubos_agrupados[chave_tubo] = tubos_agrupados.get(chave_tubo, 0) + L

        for nome, qtd in t["Conexoes"].items():
            conexoes_totais[nome] += qtd
        
    df_resultados = pd.DataFrame(resultados)
    df_tubos = pd.DataFrame(list(tubos_agrupados.items()), columns=["Especificação", "Comprimento Total (m)"])
    df_conexoes = pd.DataFrame([(k, v) for k, v in conexoes_totais.items() if v > 0], columns=["Conexão", "Quantidade Total"])
    
    col_r1, col_r2 = st.columns([5, 2])
    with col_r1:
        st.subheader("📋 Resumo Hidráulico")
        st.dataframe(df_resultados, use_container_width=True)
    with col_r2:
        st.subheader("🗺️ Diagrama")
        G = nx.DiGraph()
        for t in st.session_state.trechos:
            if t["Origem"] and t["Destino"]:
                G.add_edge(t["Origem"], t["Destino"], label=f"Ø{t['Diâmetro']}")
        if len(G.nodes) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            pos = nx.spring_layout(G)
            nx.draw(G, pos, with_labels=True, node_color='#4CA1AF', node_size=1000, edge_color='gray', font_size=8, arrows=True, ax=ax)
            nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G, 'label'), font_size=7)
            st.pyplot(fig)
            
    st.divider()

    # --- 4. BALANÇO DE ENERGIA E DIMENSIONAMENTO ---
    st.subheader("⚖️ Balanço de Pressão e Bomba")
    v_inicial = df_resultados['Vel(m/s)'].iloc[0] if not df_resultados.empty else 0
    perda_entrada_mca = k_entrada * (v_inicial ** 2) / (2 * 9.81)
    perda_rede = df_resultados['Total(mca)'].sum() if not df_resultados.empty else 0
    vazao_alimentador = df_resultados['Q(L/s)'].iloc[0] if not df_resultados.empty else 0
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        desnivel = st.number_input("Desnível Geométrico Total (m)", min_value=0.0, value=10.0)
        rendimento = st.slider("Rendimento da Bomba (%)", 10, 100, 75) / 100.0
    with col_b2:
        pressao_necessaria = desnivel + perda_rede + perda_entrada_mca
        amt_bomba = pressao_necessaria - pressao_rua
        
        st.write(f"**Vazão Total do Alimentador:** {vazao_alimentador:.2f} L/s")
        st.write(f"**Perda de Carga (Rede + Cavalete):** {(perda_rede + perda_entrada_mca):.2f} mca")
        st.write(f"**Energia Total Exigida:** {pressao_necessaria:.2f} mca")
        
        if amt_bomba <= 0:
            status_bomba = f"Escoamento Natural. Pressao residual: {abs(amt_bomba):.2f} mca"
            potencia_cv = 0
            st.success(f"✅ **{status_bomba}**")
        else:
            potencia_cv = ((vazao_alimentador / 1000) * amt_bomba * 1000) / (75 * rendimento)
            status_bomba = f"Bomba Necessaria - AMT: {amt_bomba:.2f} mca | Pot: {potencia_cv:.2f} cv"
            st.error(f"**Bomba Necessária:** AMT: {amt_bomba:.2f} mca | Potência: {potencia_cv:.2f} cv")

    st.divider()

    # --- 5. LISTA DE MATERIAIS ---
    st.subheader("📦 Quantitativo de Materiais")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.write("**Tubulação por Material e Diâmetro**")
        st.dataframe(df_tubos, use_container_width=True, hide_index=True)
    with col_m2:
        st.write("**Total de Conexões**")
        if not df_conexoes.empty:
            st.dataframe(df_conexoes, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma conexão selecionada.")

    # --- 6. EXPORTAÇÃO PDF ---
    def gerar_pdf_projeto(df_h, df_t, df_c, st_bomba):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="Relatorio Tecnico - Rede Hidraulica", ln=True, align='C')
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="1. Resumo de Perda de Carga", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(40, 8, "Trecho", border=1, align='C')
        pdf.cell(20, 8, "Diam(mm)", border=1, align='C')
        pdf.cell(20, 8, "Vel(m/s)", border=1, align='C')
        pdf.cell(30, 8, "Total(mca)", border=1, align='C')
        pdf.ln()
        for _, row in df_h.iterrows():
            pdf.cell(40, 8, str(row['Trecho']), border=1, align='C')
            pdf.cell(20, 8, str(row['Diam(mm)']), border=1, align='C')
            pdf.cell(20, 8, str(row['Vel(m/s)']), border=1, align='C')
            pdf.cell(30, 8, str(row['Total(mca)']), border=1, align='C')
            pdf.ln()
            
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="2. Dimensionamento e Pressao", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, txt=st_bomba, ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="3. Lista de Materiais (Quantitativo)", ln=True)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(80, 8, "Tubulacao (Material/Diam)", border=1)
        pdf.cell(40, 8, "Metragem (m)", border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", size=9)
        for _, row in df_t.iterrows():
            pdf.cell(80, 8, str(row['Especificação']), border=1)
            pdf.cell(40, 8, f"{row['Comprimento Total (m)']:.2f}", border=1, align='C')
            pdf.ln()
            
        pdf.ln(3)
        if not df_c.empty:
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(80, 8, "Conexao", border=1)
            pdf.cell(40, 8, "Quantidade", border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", size=9)
            for _, row in df_c.iterrows():
                pdf.cell(80, 8, str(row['Conexão']), border=1)
                pdf.cell(40, 8, str(row['Quantidade Total']), border=1, align='C')
                pdf.ln()

        return pdf.output(dest='S').encode('latin-1')

    pdf_bytes = gerar_pdf_projeto(df_resultados, df_tubos, df_conexoes, status_bomba)
    st.download_button(
        label="📄 Baixar Relatório Técnico Completo (PDF)",
        data=pdf_bytes,
        file_name="projeto_hidraulico_quantitativo.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )
