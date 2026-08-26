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

# --- PLANILHA INTERATIVA DE ENTRADA ---
st.subheader("✏️ Desenho da Rede (Planilha Interativa)")
st.write("Adicione novos trechos clicando na última linha vazia. Você pode editar, copiar e colar dados diretamente.")

# Inicializar o dataframe padrão se não existir
if 'df_input' not in st.session_state:
    st.session_state.df_input = pd.DataFrame([{
        "Origem": "A", "Destino": "B", "Comprimento (m)": 10.0,
        "Diâmetro (mm)": 50.0, "Vazão (L/s)": 2.0, 
        "Material": "PVC", "Soma K (Conexões)": 0.9
    }])

# O st.data_editor permite edição dinâmica como no Excel
edited_df = st.data_editor(
    st.session_state.df_input,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Material": st.column_config.SelectboxColumn(
            "Material", help="Selecione o material da tubulação",
            options=list(MATERIAIS_C.keys()), required=True
        ),
        "Soma K (Conexões)": st.column_config.NumberColumn(
            "Soma K (Conexões)", help="Soma dos coeficientes de perda localizada",
            min_value=0.0, format="%.2f"
        )
    }
)

# Salva as edições no estado
st.session_state.df_input = edited_df

# --- CÁLCULO E RESULTADOS ---
if not edited_df.empty and st.button("🚀 Calcular Rede e Dimensionar Bomba", type="primary"):
    
    # 1. Cálculos Hidráulicos
    resultados = []
    for _, t in edited_df.iterrows():
        # Ignorar linhas vazias acidentais
        if pd.isna(t["Origem"]) or pd.isna(t["Destino"]):
            continue
            
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
    
    # 2. Exibição dos Resultados e Grafo
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

    # 3. Módulo da Bomba
    st.subheader("⚙️ Dimensionamento da Bomba Centrífuga")
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        desnivel = st.number_input("Desnível Geométrico (m)", min_value=0.0, value=15.0)
        rendimento = st.slider("Rendimento da Bomba (%)", 10, 100, 70) / 100.0

    with col_b2:
        vazao_max = float(df_resultados['Vazão (L/s)'].max()) if not df_resultados.empty else 2.0
        vazao_bomba = st.number_input("Vazão de Projeto da Bomba (L/s)", min_value=0.1, value=vazao_max)
        
        perda_carga_total = df_resultados['Total (mca)'].sum() if not df_resultados.empty else 0
        amt = desnivel + perda_carga_total
        potencia_cv = ((vazao_bomba / 1000) * amt * 1000) / (75 * rendimento)
        
        st.info(f"**Altura Manométrica Total (AMT):** {amt:.2f} mca")
        st.success(f"**Potência Estimada:** {potencia_cv:.2f} cv")

    # 4. Geração do PDF
    def gerar_pdf(df, amt_val, pot_val, des_val):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Relatorio de Dimensionamento Hidraulico", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="1. Perda de Carga por Trecho", ln=True)
        pdf.set_font("Arial", size=10)
        
        colunas = ["Trecho", "Vazao", "Velocidade", "P.Dist", "P.Loc", "Total"]
        larguras = [30, 25, 25, 35, 35, 35]
        for col, larg in zip(colunas, larguras):
            pdf.cell(larg, 10, col, border=1, align='C')
        pdf.ln()
        
        for _, row in df.iterrows():
            pdf.cell(larguras[0], 10, str(row['Trecho']), border=1, align='C')
            pdf.cell(larguras[1], 10, str(row['Vazão (L/s)']), border=1, align='C')
            pdf.cell(larguras[2], 10, str(row['Velocidade (m/s)']), border=1, align='C')
            pdf.cell(larguras[3], 10, str(row['P. Distr. (mca)']), border=1, align='C')
            pdf.cell(larguras[4], 10, str(row['P. Local. (mca)']), border=1, align='C')
            pdf.cell(larguras[5], 10, str(row['Total (mca)']), border=1, align='C')
            pdf.ln()
            
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="2. Dimensionamento da Bomba", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 8, txt=f"Desnivel Geometrico: {des_val:.2f} m", ln=True)
        pdf.cell(200, 8, txt=f"Altura Manometrica Total (AMT): {amt_val:.2f} mca", ln=True)
        pdf.cell(200, 8, txt=f"Potencia Estimada: {pot_val:.2f} cv", ln=True)
        return pdf.output(dest='S').encode('latin-1')

    if not df_resultados.empty:
        pdf_bytes = gerar_pdf(df_resultados, amt, potencia_cv, desnivel)
        st.download_button("Baixar Relatório em PDF", pdf_bytes, "relatorio_hidraulico.pdf", "application/pdf")
