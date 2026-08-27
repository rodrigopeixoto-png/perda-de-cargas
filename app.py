import streamlit as st
import pandas as pd
import math
import networkx as nx
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os

# --- BANCO DE DADOS DE MATERIAIS ---
MATERIAIS_C = {
    "PVC": 150, "Cobre": 130, "Aço Carbono": 120, 
    "Ferro Fundido": 100, "Aço Galvanizado": 125
}

# --- DIÂMETROS INTERNOS REAIS (Exemplo p/ PVC Soldável) ---
# Mapeamento de Diâmetro Nominal (Comercial) para Diâmetro Interno real aproximado (mm)
DIAMETROS_INTERNOS = {
    20: 17.0, 25: 21.6, 32: 27.8, 40: 35.2, 
    50: 44.0, 60: 53.4, 75: 66.6, 85: 75.4, 110: 97.6
}

# --- CADASTRO DE COMPRIMENTOS EQUIVALENTES (M) ---
COMPRIMENTOS_EQUIVALENTES = {
    "Cotovelo 90°": {20: 1.2, 25: 1.5, 32: 2.0, 40: 3.2, 50: 3.4, 60: 3.5, 75: 3.8, 85: 4.1, 110: 5.0},
    "Cotovelo 45°": {20: 0.6, 25: 0.7, 32: 1.0, 40: 1.4, 50: 1.5, 60: 1.7, 75: 1.9, 85: 2.1, 110: 2.5},
    "Curva 90°": {20: 0.4, 25: 0.5, 32: 0.7, 40: 1.0, 50: 1.2, 60: 1.3, 75: 1.4, 85: 1.5, 110: 1.9},
    "Curva 45°": {20: 0.2, 25: 0.3, 32: 0.4, 40: 0.5, 50: 0.6, 60: 0.7, 75: 0.8, 85: 0.9, 110: 1.2},
    "Tê 90° Passagem Direta": {20: 0.7, 25: 0.8, 32: 1.1, 40: 1.5, 50: 1.6, 60: 1.8, 75: 2.0, 85: 2.2, 110: 2.5},
    "Tê 90° Saída de Lado": {20: 2.4, 25: 3.1, 32: 4.3, 40: 6.2, 50: 6.6, 60: 7.3, 75: 7.6, 85: 8.0, 110: 9.0},
    "Registro de Gaveta Aberto": {20: 0.1, 25: 0.2, 32: 0.2, 40: 0.3, 50: 0.4, 60: 0.5, 75: 0.6, 85: 0.7, 110: 1.0},
    "Registro de Globo Aberto": {20: 7.4, 25: 9.5, 32: 12.4, 40: 17.0, 50: 19.0, 60: 22.0, 75: 25.0, 85: 28.0, 110: 35.0},
    "Válvula de Retenção (Leve)": {20: 1.9, 25: 2.4, 32: 3.2, 40: 4.4, 50: 4.8, 60: 5.4, 75: 6.1, 85: 6.8, 110: 8.5},
    "Luva (Emenda Direta)": {20: 0.1, 25: 0.1, 32: 0.15, 40: 0.2, 50: 0.2, 60: 0.25, 75: 0.3, 85: 0.4, 110: 0.5},
    "Redução (Bucha)": {20: 0.2, 25: 0.2, 32: 0.3, 40: 0.3, 50: 0.4, 60: 0.5, 75: 0.6, 85: 0.7, 110: 0.9},
    "Saída de Canalização": {20: 0.8, 25: 0.9, 32: 1.2, 40: 1.5, 50: 1.9, 60: 2.2, 75: 2.6, 85: 3.2, 110: 4.0}
}

def get_dn_mais_proximo(diametro_informado):
    dns_disponiveis = list(COMPRIMENTOS_EQUIVALENTES["Cotovelo 90°"].keys())
    return min(dns_disponiveis, key=lambda x: abs(x - diametro_informado))

st.set_page_config(page_title="Simulador de Redes Hidráulicas", layout="wide")
st.title("💧 Simulador de Perda de Carga & Lista de Materiais")

# --- 1. CONDIÇÕES DE ENTRADA ---
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
    velocidade_entrada = st.number_input("Velocidade no Alimentador (m/s)", min_value=0.1, value=1.5)

st.divider()

# --- 2. CONSTRUTOR DINÂMICO DE RAMAIS ---
st.subheader("✏️ Construtor de Ramais")
st.info("💡 **Atenção aos Nomes:** Para que o diagrama desenhe a rede corretamente, o nome do 'Destino' de um trecho deve ser **exatamente igual** ao nome da 'Origem' do trecho seguinte (cuidado com espaços e acentos).")

if 'trechos' not in st.session_state:
    vazao_inicial_sugerida = (velocidade_entrada * math.pi * ((53.4/1000)**2) / 4) * 1000
    st.session_state.trechos = [{
        "Origem": "Rua", "Destino": "Hidrometro", "Comprimento": 15.0,
        "DN_Comercial": 60, "Diâmetro": 53.4, "Vazão": float(round(vazao_inicial_sugerida, 2)), "Material": "PVC",
        "Conexoes": {k: 0 for k in COMPRIMENTOS_EQUIVALENTES.keys()}
    }]

col_add, col_rem = st.columns([1, 5])
with col_add:
    if st.button("➕ Adicionar Ramal", type="primary"):
        ultimo_destino = st.session_state.trechos[-1]["Destino"] if st.session_state.trechos else ""
        ultima_vazao = st.session_state.trechos[-1]["Vazão"] if st.session_state.trechos else 1.0
        st.session_state.trechos.append({
            "Origem": ultimo_destino, "Destino": "", "Comprimento": 10.0,
            "DN_Comercial": 25, "Diâmetro": 21.6, "Vazão": ultima_vazao, "Material": "PVC",
            "Conexoes": {k: 0 for k in COMPRIMENTOS_EQUIVALENTES.keys()}
        })
        st.rerun()
with col_rem:
    if st.button("🗑️ Remover Último") and len(st.session_state.trechos) > 0:
        st.session_state.trechos.pop()
        st.rerun()

for i, t in enumerate(st.session_state.trechos):
    with st.container(border=True):
        c1, c2, c3, c4, c4_2, c5, c6 = st.columns([1.2, 1.2, 0.8, 0.8, 0.8, 0.8, 1.0])
        t["Origem"] = c1.text_input("Origem", t["Origem"], key=f"o_{i}").strip()
        t["Destino"] = c2.text_input("Destino", t["Destino"], key=f"d_{i}").strip()
        t["Comprimento"] = c3.number_input("Comp. (m)", 0.1, 5000.0, float(t["Comprimento"]), key=f"c_{i}")
        
        # Lógica inteligente para Diâmetro Nominal vs Interno
        dn_opcoes = [20, 25, 32, 40, 50, 60, 75, 85, 110]
        dn_atual = t.get("DN_Comercial", 60)
        if dn_atual not in dn_opcoes:
            dn_atual = get_dn_mais_proximo(dn_atual)
            
        dn_comercial = c4.selectbox("DN Comercial", dn_opcoes, index=dn_opcoes.index(dn_atual), key=f"dn_{i}")
        
        # Se o usuário mudou o DN comercial, atualiza o Di automaticamente
        if t.get("DN_Comercial") != dn_comercial:
            t["DN_Comercial"] = dn_comercial
            t["Diâmetro"] = DIAMETROS_INTERNOS.get(dn_comercial, dn_comercial)
            
        t["Diâmetro"] = c4_2.number_input("Diâm. Interno (mm)", 1.0, 1000.0, float(t["Diâmetro"]), key=f"di_{i}", help="O cálculo hidráulico exige o diâmetro interno real da tubulação.")
        
        if i == 0:
            d_m = t["Diâmetro"] / 1000
            vazao_calc = (velocidade_entrada * math.pi * (d_m**2) / 4) * 1000
            t["Vazão"] = float(vazao_calc)
            c5.number_input("Vazão (L/s)", value=float(t["Vazão"]), key=f"v_{i}_calc", disabled=True)
        else:
            t["Vazão"] = c5.number_input("Vazão (L/s)", 0.01, 1000.0, float(t["Vazão"]), key=f"v_{i}")
            
        t["Material"] = c6.selectbox("Material", list(MATERIAIS_C.keys()), index=list(MATERIAIS_C.keys()).index(t["Material"]), key=f"m_{i}")
        
        with st.expander(f"🛠️ Selecionar Conexões ({t['Origem']} -> {t['Destino']}) - Tabela Base: DN {get_dn_mais_proximo(t['DN_Comercial'])}"):
            ccols = st.columns(4)
            for j, nome_con in enumerate(COMPRIMENTOS_EQUIVALENTES.keys()):
                qtd_atual = t.get("Conexoes", {}).get(nome_con, 0)
                qtd = ccols[j % 4].number_input(f"{nome_con}", 0, 50, int(qtd_atual), key=f"cx_{i}_{nome_con}")
                if "Conexoes" not in t:
                    t["Conexoes"] = {}
                t["Conexoes"][nome_con] = qtd

st.divider()

# --- 3. PROCESSAMENTO ---
if st.button("🚀 Processar Simulação Completa", type="primary", use_container_width=True):
    st.session_state.processado = True

if st.session_state.get("processado", False):
    resultados = []
    tubos_agrupados = {}
    conexoes_totais = {k: 0 for k in COMPRIMENTOS_EQUIVALENTES.keys()}

    for t in st.session_state.trechos:
        if not t["Origem"] or not t["Destino"]: continue
            
        Q_m3s = t["Vazão"] / 1000
        D_m = t["Diâmetro"] / 1000  # USA O DIÂMETRO INTERNO PARA O CÁLCULO
        L_fisico = t["Comprimento"]
        C = MATERIAIS_C.get(t["Material"], 150)
        dn_aprox = get_dn_mais_proximo(t["DN_Comercial"])
        
        L_eq_total = 0.0
        for nome_con, qtd in t.get("Conexoes", {}).items():
            if qtd > 0 and nome_con in COMPRIMENTOS_EQUIVALENTES:
                L_eq_total += qtd * COMPRIMENTOS_EQUIVALENTES[nome_con][dn_aprox]
                conexoes_totais[nome_con] += qtd

        area = math.pi * (D_m ** 2) / 4
        v = Q_m3s / area if area > 0 else 0
        
        fator_hw = 10.67 * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87)) if D_m > 0 else 0
        hf_distribuida = fator_hw * L_fisico
        hf_localizada = fator_hw * L_eq_total
        
        resultados.append({
            "Origem": t['Origem'], "Destino": t['Destino'],
            "Trecho": f"{t['Origem']} -> {t['Destino']}", "DN": t["DN_Comercial"], "Di(mm)": t["Diâmetro"],
            "Q(L/s)": round(t["Vazão"], 2), "Vel(m/s)": round(v, 2), "Leq(m)": round(L_eq_total, 2),
            "P. Distr(mca)": round(hf_distribuida, 3), "P. Local(mca)": round(hf_localizada, 3), 
            "Total(mca)": round(hf_distribuida + hf_localizada, 3)
        })

        chave_tubo = f"{t['Material']} DN {t['DN_Comercial']} (Di {t['Diâmetro']:.1f}mm)"
        tubos_agrupados[chave_tubo] = tubos_agrupados.get(chave_tubo, 0) + L_fisico
        
    df_resultados = pd.DataFrame(resultados)
    df_tubos = pd.DataFrame(list(tubos_agrupados.items()), columns=["Especificação", "Comprimento Físico (m)"])
    df_conexoes = pd.DataFrame([(k, v) for k, v in conexoes_totais.items() if v > 0], columns=["Conexão", "Quantidade Total"])
    
    st.subheader("📋 Resumo Hidráulico")
    st.dataframe(df_resultados.drop(columns=['Origem', 'Destino']), use_container_width=True)

    # --- DIAGRAMAS (ESTILO EPANET) OTIMIZADOS ---
    st.subheader("🗺️ Diagramas de Pressão e Perda de Carga")
    col_d1, col_d2 = st.columns(2)
    
    # 1. Mapa de Calor da Rede (NetworkX)
    G = nx.DiGraph()
    if not df_resultados.empty:
        for _, row in df_resultados.iterrows():
            G.add_edge(row["Origem"], row["Destino"], weight=row['Total(mca)'], 
                       label=f"DN{row['DN']}
hf={row['Total(mca)']}mca")
    
    fig_net, ax_net = plt.subplots(figsize=(8, 6))
    if len(G.nodes) > 0:
        try:
            # Algoritmo melhor para evitar cruzamentos em redes (se scipy estiver instalado)
            pos = nx.kamada_kawai_layout(G)
        except:
            pos = nx.spring_layout(G, k=3.0, iterations=100, seed=42)
            
        edges = G.edges()
        weights = [G[u][v]['weight'] for u, v in edges]
        
        vmin = min(weights) if weights else 0
        vmax = max(weights) if weights else 1
        if vmin == vmax:
            vmin, vmax = 0, vmax + 1

        nx.draw_networkx_nodes(G, pos, node_color='#ecf0f1', edgecolors='#bdc3c7', node_size=150, ax=ax_net)
        
        pos_labels = {node: (coords[0], coords[1] + 0.1) for node, coords in pos.items()}
        nx.draw_networkx_labels(G, pos_labels, font_size=9, font_weight="bold", font_color="black", ax=ax_net)
        
        nx.draw_networkx_edges(
            G, pos, edgelist=edges, edge_color=weights,
            edge_cmap=plt.cm.jet, edge_vmin=vmin, edge_vmax=vmax,
            width=3, arrows=True, arrowsize=15, ax=ax_net
        )
        
        bbox_props = dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85)
        nx.draw_networkx_edge_labels(
            G, pos, edge_labels=nx.get_edge_attributes(G, 'label'), 
            font_size=7, font_color="black", bbox=bbox_props, ax=ax_net
        )
        
        sm = plt.cm.ScalarMappable(cmap=plt.cm.jet, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([]) 
        
        cbar = plt.colorbar(sm, ax=ax_net, fraction=0.046, pad=0.04)
        cbar.set_label('Perda de Carga Total (mca)', rotation=270, labelpad=15)
        ax_net.set_title("Esquema da Rede (Mapa de Calor de Perdas)")
        ax_net.axis('off')

    # 2. Gráfico de Barras Empilhadas
    fig_bar, ax_bar = plt.subplots(figsize=(6, 5))
    if not df_resultados.empty:
        df_resultados.plot.barh(x='Trecho', y=['P. Distr(mca)', 'P. Local(mca)'], 
                                stacked=True, ax=ax_bar, color=['#3498db', '#e74c3c'])
        ax_bar.set_title("Composição da Perda de Carga por Ramal")
        ax_bar.set_xlabel("Perda de Carga (mca)")
        ax_bar.set_ylabel("")
        plt.tight_layout()

    with col_d1:
        st.pyplot(fig_net)
    with col_d2:
        st.pyplot(fig_bar)

    st.divider()

    # --- 4. VERIFICAÇÃO DE PRESSÕES (NBR 5626) ---
    st.subheader("⚖️ Verificação de Pressões e Balanço Hidráulico")
    
    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
        desnivel = st.number_input("Desnível Geométrico (m)", min_value=0.0, value=10.0)
    with col_v2:
        pressao_req = st.number_input("Pressão Mínima Requerida (mca)", min_value=0.0, value=1.0)
    with col_v3:
        rendimento = st.slider("Rendimento da Bomba (%)", 10, 100, 75) / 100.0

    v_inicial = df_resultados['Vel(m/s)'].iloc[0] if not df_resultados.empty else 0
    perda_entrada_mca = k_entrada * (v_inicial ** 2) / (2 * 9.81)
    perda_rede = df_resultados['Total(mca)'].sum() if not df_resultados.empty else 0
    vazao_alimentador = df_resultados['Q(L/s)'].iloc[0] if not df_resultados.empty else 0
    perda_total_dh = perda_rede + perda_entrada_mca
    
    pressao_disp_resultante = pressao_rua - desnivel - perda_total_dh
    balanco = pressao_disp_resultante - pressao_req

    df_balanco = pd.DataFrame([{
        "Pressão Concessionária (m.c.a)": round(pressao_rua, 2),
        "Desnível Geométrico (m)": round(desnivel, 2),
        "Perda de Carga dH (m.c.a)": round(perda_total_dh, 2),
        "Pressão Disp. Resultante (m.c.a)": round(pressao_disp_resultante, 2),
        "Pressão Mín. Requerida (m.c.a)": round(pressao_req, 2),
        "Balanço NBR 5626 (m.c.a)": round(balanco, 2)
    }])

    st.dataframe(df_balanco, use_container_width=True, hide_index=True)

    if balanco >= 0:
        status_bomba_pdf = f"Escoamento Natural NBR 5626. Balanco Positivo: {balanco:.2f} mca"
        st.success(f"✅ **Atende NBR 5626 (Escoamento Natural):** O sistema possui um balanço de pressão positivo de {balanco:.2f} mca. Não é necessário uso de bomba.")
    else:
        amt_bomba = abs(balanco)
        potencia_cv = ((vazao_alimentador / 1000) * amt_bomba * 1000) / (75 * rendimento)
        status_bomba_pdf = f"Nao Atende (Necessita Bomba). AMT: {amt_bomba:.2f} mca | Pot: {potencia_cv:.2f} cv"
        st.error(f"⚠️ **Não Atende NBR 5626:** O sistema tem um déficit de {amt_bomba:.2f} mca. É necessário um sistema de recalque (Bomba).")
        st.warning(f"⚙️ **Dimensionamento da Bomba:** Altura Manométrica Total (AMT) = {amt_bomba:.2f} mca | Potência Estimada = {potencia_cv:.2f} cv")

    st.divider()

    # --- 5. LISTA DE MATERIAIS ---
    st.subheader("📦 Quantitativo de Materiais")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.write("**Tubulação por Material e Diâmetro (Apenas Extensão Física)**")
        st.dataframe(df_tubos, use_container_width=True, hide_index=True)
    with col_m2:
        st.write("**Total de Conexões**")
        if not df_conexoes.empty:
            st.dataframe(df_conexoes, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma conexão selecionada.")

    # --- 6. EXPORTAÇÃO PDF ---
    def gerar_pdf_projeto(df_h, df_b, df_t, df_c, st_bomba, f_net, f_bar):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="Relatorio Tecnico - Rede Hidraulica", ln=True, align='C')
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="1. Resumo de Perda de Carga", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(40, 8, "Trecho", border=1, align='C')
        pdf.cell(20, 8, "Di(mm)", border=1, align='C')
        pdf.cell(20, 8, "Vel(m/s)", border=1, align='C')
        pdf.cell(30, 8, "Total(mca)", border=1, align='C')
        pdf.ln()
        for _, row in df_h.iterrows():
            pdf.cell(40, 8, str(row['Trecho']), border=1, align='C')
            pdf.cell(20, 8, str(row['Di(mm)']), border=1, align='C')
            pdf.cell(20, 8, str(row['Vel(m/s)']), border=1, align='C')
            pdf.cell(30, 8, str(row['Total(mca)']), border=1, align='C')
            pdf.ln()
            
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="2. Verificacao de Pressoes (NBR 5626)", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(40, 8, "P. Concessionaria", border=1, align='C')
        pdf.cell(30, 8, "Desnivel (m)", border=1, align='C')
        pdf.cell(30, 8, "Perda dH (mca)", border=1, align='C')
        pdf.cell(30, 8, "P. Disp Result", border=1, align='C')
        pdf.cell(30, 8, "Balanco NBR", border=1, align='C')
        pdf.ln()
        
        b = df_b.iloc[0]
        pdf.cell(40, 8, str(b["Pressão Concessionária (m.c.a)"]), border=1, align='C')
        pdf.cell(30, 8, str(b["Desnível Geométrico (m)"]), border=1, align='C')
        pdf.cell(30, 8, str(b["Perda de Carga dH (m.c.a)"]), border=1, align='C')
        pdf.cell(30, 8, str(b["Pressão Disp. Resultante (m.c.a)"]), border=1, align='C')
        pdf.cell(30, 8, str(b["Balanço NBR 5626 (m.c.a)"]), border=1, align='C')
        pdf.ln(8)
        
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, txt=st_bomba, ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 8, txt="3. Lista de Materiais (Quantitativo)", ln=True)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(80, 8, "Tubulacao (Material/DN)", border=1)
        pdf.cell(40, 8, "Metragem (m)", border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", size=9)
        for _, row in df_t.iterrows():
            pdf.cell(80, 8, str(row['Especificação']), border=1)
            pdf.cell(40, 8, f"{row['Comprimento Físico (m)']:.2f}", border=1, align='C')
            pdf.ln()
            
        pdf.ln(3)
        if not df_c.empty:
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(80, 8, "Conexao", border=1)
            pdf.cell(40, 8, "Quantidade", border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", size=9)
            for _, row in df_c.iterrows():
                nome_conexao = str(row['Conexão']).replace('°', ' graus').replace('ê', 'e').replace('ç', 'c').replace('ã', 'a')
                pdf.cell(80, 8, nome_conexao, border=1)
                pdf.cell(40, 8, str(row['Quantidade Total']), border=1, align='C')
                pdf.ln()

        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt="4. Diagramas Hidraulicos", ln=True, align='C')
        pdf.ln(5)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_net:
            f_net.savefig(tmp_net.name, format="png", bbox_inches="tight", dpi=150)
            path_net = tmp_net.name
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_bar:
            f_bar.savefig(tmp_bar.name, format="png", bbox_inches="tight", dpi=150)
            path_bar = tmp_bar.name

        pdf.image(path_net, x=35, y=pdf.get_y(), w=140)
        pdf.ln(110)
        pdf.image(path_bar, x=35, y=pdf.get_y(), w=140)

        os.remove(path_net)
        os.remove(path_bar)

        return pdf.output(dest='S').encode('latin-1', errors='replace')

    pdf_bytes = gerar_pdf_projeto(df_resultados, df_balanco, df_tubos, df_conexoes, status_bomba_pdf, fig_net, fig_bar)
    st.download_button(
        label="📄 Baixar Relatório Técnico Completo (PDF com Diagramas)",
        data=pdf_bytes,
        file_name="projeto_hidraulico_quantitativo.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )
