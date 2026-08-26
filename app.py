import streamlit as st
import pandas as pd
import math
import networkx as nx
import matplotlib.pyplot as plt
from fpdf import FPDF
import base64

# --- BANCO DE DADOS DE MATERIAIS E CONEXÕES ---
MATERIAIS_C = {
    "PVC": 150,
    "Cobre": 130,
    "Aço Carbono (Novo)": 120,
    "Ferro Fundido": 100,
    "Aço Galvanizado": 125
}

CONEXOES_K = {
    "Cotovelo 90°": 0.9,
    "Cotovelo 45°": 0.4,
    "Tê (Passagem Direta)": 0.2,
    "Tê (Saída Lateral)": 1.2,
    "Válvula de Gaveta (Aberta)": 0.2,
    "Válvula Globo (Aberta)": 10.0,
    "Válvula de Retenção": 2.5
}

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador de Redes Hidráulicas", layout="wide")
st.title("💧 Simulador de Perda de Carga - Hazen-Williams")

# Inicializar o estado da sessão para armazenar os trechos da rede
if 'trechos' not in st.session_state:
    st.session_state.trechos = []

# --- BARRA LATERAL: ENTRADA DE DADOS ---
st.sidebar.header("Adicionar Trecho à Rede")
with st.sidebar.form("form_trecho"):
    no_origem = st.text_input("Nó de Origem (ex: A)", "A")
    no_destino = st.text_input("Nó de Destino (ex: B)", "B")
    comprimento = st.number_input("Comprimento do Tubo (m)", min_value=0.1, value=10.0)
    diametro = st.number_input("Diâmetro Interno (mm)", min_value=1.0, value=50.0)
    vazao = st.number_input("Vazão (L/s)", min_value=0.1, value=2.0)
    material = st.selectbox("Material da Tubulação", list(MATERIAIS_C.keys()))
    conexoes = st.multiselect("Conexões no Trecho", list(CONEXOES_K.keys()))
    
    submit = st.form_submit_button("Adicionar Trecho")
    
    if submit:
        st.session_state.trechos.append({
            "Origem": no_origem,
            "Destino": no_destino,
            "Comprimento (m)": comprimento,
            "Diâmetro (mm)": diametro,
            "Vazão (L/s)": vazao,
            "Material": material,
            "Conexões": conexoes
        })
        st.success(f"Trecho {no_origem}-{no_destino} adicionado!")

# --- FUNÇÃO DE CÁLCULO ---
def calcular_rede(trechos):
    resultados = []
    for t in trechos:
        # Conversões
        Q_m3s = t["Vazão (L/s)"] / 1000
        D_m = t["Diâmetro (mm)"] / 1000
        L = t["Comprimento (m)"]
        C = MATERIAIS_C[t["Material"]]
        
        # Velocidade (v = Q / A)
        area = math.pi * (D_m ** 2) / 4
        v = Q_m3s / area
        
        # Perda de Carga Distribuída (Hazen-Williams)
        # hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
        hf = 10.67 * L * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87))
        
        # Perda de Carga Localizada (Método dos Ks)
        soma_k = sum([CONEXOES_K[c] for c in t["Conexões"]])
        hl = soma_k * (v ** 2) / (2 * 9.81)
        
        h_total = hf + hl
        
        resultados.append({
            "Trecho": f"{t['Origem']}-{t['Destino']}",
            "Material": t["Material"],
            "Velocidade (m/s)": round(v, 2),
            "Perda Distribuída (mca)": round(hf, 3),
            "Perda Localizada (mca)": round(hl, 3),
            "Perda Total (mca)": round(h_total, 3)
        })
    return pd.DataFrame(resultados)

# --- VISUALIZAÇÃO E EXPORTAÇÃO ---
if st.session_state.trechos:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Resultados dos Cálculos")
        df_resultados = calcular_rede(st.session_state.trechos)
        st.dataframe(df_resultados, use_container_width=True)
        
        if st.button("Limpar Rede"):
            st.session_state.trechos = []
            st.rerun()

    with col2:
        st.subheader("🗺️ Esquema da Rede")
        # Desenhar grafo com NetworkX
        G = nx.DiGraph()
        for t in st.session_state.trechos:
            G.add_edge(t["Origem"], t["Destino"], length=t["Comprimento (m)"])
            
        fig, ax = plt.subplots(figsize=(4, 4))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1500, edge_color='gray', font_weight='bold', arrows=True, ax=ax)
        st.pyplot(fig)

    # --- GERAR PDF ---
    def gerar_pdf(df):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Relatorio de Perda de Carga - Rede Hidraulica", ln=True, align='C')
        
        pdf.set_font("Arial", size=10)
        pdf.ln(10)
        
        # Cabeçalho da Tabela
        colunas = ["Trecho", "Vel (m/s)", "P. Distr (mca)", "P. Local (mca)", "Total (mca)"]
        for col in colunas:
            pdf.cell(38, 10, col, border=1, align='C')
        pdf.ln()
        
        # Dados
        for _, row in df.iterrows():
            pdf.cell(38, 10, str(row['Trecho']), border=1, align='C')
            pdf.cell(38, 10, str(row['Velocidade (m/s)']), border=1, align='C')
            pdf.cell(38, 10, str(row['Perda Distribuída (mca)']), border=1, align='C')
            pdf.cell(38, 10, str(row['Perda Localizada (mca)']), border=1, align='C')
            pdf.cell(38, 10, str(row['Perda Total (mca)']), border=1, align='C')
            pdf.ln()
            
        return pdf.output(dest='S').encode('latin-1')

    st.subheader("📄 Exportar Resultados")
    pdf_bytes = gerar_pdf(df_resultados)
    st.download_button(
        label="Baixar Relatório em PDF",
        data=pdf_bytes,
        file_name="relatorio_hidraulico.pdf",
        mime="application/pdf"
    )
else:
    st.info("👈 Adicione trechos na barra lateral para começar a simulação.")
