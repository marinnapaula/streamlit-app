import pandas as pd
import streamlit as st
import plotly.express as px

def classificar_tipo(categoria):
    categoria = str(categoria).lower()
    if 'receita' in categoria:
        return 'Receita'
    if 'despesa' in categoria or 'custo' in categoria:
        return 'Despesa'
    if 'imposto' in categoria:
        return 'Imposto'
    if 'fapesb' in categoria or 'investimento' in categoria:
        return 'Investimento'
    return 'Outros'

st.title("📊 Análise Integrada: Despesas, Receitas e Gap de Caixa")

uploaded_file = st.file_uploader("📤 Escolha o arquivo CSV", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8', sep=',')
    except:
        df = pd.read_csv(uploaded_file, encoding='latin1', sep=',')

    df.columns = df.columns.str.strip().str.lower()

    obrigatorias = ['data de vencimento', 'data de pagamento', 'valor', 'categoria', 'descrição', 'cliente/fornecedor']
    faltantes = [col for col in obrigatorias if col not in df.columns]
    if faltantes:
        st.error(f"⚠️ Colunas faltando: {faltantes}")
        st.stop()

    df['data de vencimento'] = pd.to_datetime(df['data de vencimento'], dayfirst=True, errors='coerce')
    df['data de pagamento'] = pd.to_datetime(df['data de pagamento'], dayfirst=True, errors='coerce')

    df['valor'] = df['valor'].astype(str).str.replace('R\$', '', regex=True)
    df['valor'] = df['valor'].str.replace(',', '.').str.strip()
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce')

    df['tipo'] = df['categoria'].apply(classificar_tipo)
    df['status'] = df['data de pagamento'].apply(lambda x: 'Pago' if pd.notnull(x) else 'Pendente')

    hoje = pd.to_datetime('today')

    # ✅ DESPESAS
    st.header("💸 Análise de Despesas")

    despesas_pendentes = df[(df['tipo'] == 'Despesa') & (df['status'] == 'Pendente')].copy()

    atrasadas = despesas_pendentes[despesas_pendentes['data de vencimento'] <= hoje]
    a_vencer = despesas_pendentes[despesas_pendentes['data de vencimento'] > hoje].copy()

    # Substituir valores zero pela média histórica
    for idx, row in a_vencer.iterrows():
        if row['valor'] == 0 or pd.isna(row['valor']):
            historico = df[
                (df['descrição'] == row['descrição']) &
                (df['categoria'] == row['categoria']) &
                (df['cliente/fornecedor'] == row['cliente/fornecedor']) &
                (df['status'] == 'Pago')
            ]
            if not historico.empty:
                media_valor = historico['valor'].mean()
                a_vencer.at[idx, 'valor'] = media_valor

    st.subheader("⏰ Despesas Atrasadas — Agrupadas")

    atrasadas['mes_ano'] = atrasadas['data de vencimento'].dt.to_period('M').astype(str)

    atrasadas_group = atrasadas.groupby(['cliente/fornecedor', 'categoria', 'mes_ano'])['valor'].sum().reset_index()

    st.dataframe(atrasadas_group)

    total_atrasadas = atrasadas['valor'].sum()
    n_atrasadas = len(atrasadas)

    if not atrasadas.empty:
        min_date = atrasadas['data de vencimento'].min().strftime('%b/%Y')
        max_date = atrasadas['data de vencimento'].max().strftime('%b/%Y')
        periodo = f"De {min_date} até {max_date}"
    else:
        periodo = "Sem despesas atrasadas"

    st.write(f"**Total:** R$ {total_atrasadas:,.2f} | **{n_atrasadas} registros**")
    st.write(f"**Período:** {periodo}")

    st.subheader("⏳ Despesas A Vencer (com valores previstos) — Agrupadas")

    a_vencer_group = a_vencer.groupby(['cliente/fornecedor', 'categoria', 'data de vencimento'])['valor'].sum().reset_index()

    st.dataframe(a_vencer_group)

    total_avencer = a_vencer['valor'].sum()
    n_avencer = len(a_vencer)

    st.write(f"**Total:** R$ {total_avencer:,.2f} | **{n_avencer} registros**")

    # Gráfico de Despesas a Vencer
    a_vencer['mes_ano'] = a_vencer['data de vencimento'].dt.to_period('M').astype(str)
    grafico_despesas = a_vencer.groupby('mes_ano')['valor'].sum().reset_index()

    st.subheader("📊 Gráfico: Despesas a Vencer Mês a Mês (com valores previstos)")
    fig_desp = px.bar(grafico_despesas, x='mes_ano', y='valor', title='Despesas Pendentes a Vencer Mês a Mês (Com Valores Previstos)')
    st.plotly_chart(fig_desp)

    # ✅ RECEITAS
    st.header("💰 Análise de Receitas")

    receitas = df[
        (df['categoria'].str.lower().str.contains('receita')) &
        (~df['categoria'].str.lower().str.contains('financeira')) &
        (~df['categoria'].str.lower().str.contains('recurso próprio'))
    ].copy()

    receitas['status'] = receitas['data de pagamento'].apply(lambda x: 'Pago' if pd.notnull(x) else 'Pendente')

    receitas_pendentes = receitas[receitas['status'] == 'Pendente']

    st.subheader("📥 Receitas Pendentes de Recebimento — Agrupadas")

    receitas_group = receitas_pendentes.groupby(['cliente/fornecedor', 'categoria', 'data de vencimento'])['valor'].sum().reset_index()

    st.dataframe(receitas_group)

    total_receitas = receitas_pendentes['valor'].sum()
    n_receitas = len(receitas_pendentes)

    st.write(f"**Total:** R$ {total_receitas:,.2f} | **{n_receitas} registros**")

    receitas_recebidas = receitas[receitas['status'] == 'Pago'].copy()
    receitas_recebidas['mes_recebimento'] = receitas_recebidas['data de pagamento'].dt.to_period('M')

    # Receita Mensal últimos 12 meses
    ultimos_12 = pd.period_range(
        end=pd.to_datetime('today').to_period('M'), periods=12, freq='M'
    )

    receita_mensal = receitas_recebidas.groupby('mes_recebimento')['valor'].sum().reindex(ultimos_12, fill_value=0).reset_index()
    receita_mensal.columns = ['mes', 'valor']
    receita_mensal['mes'] = receita_mensal['mes'].astype(str)

    st.subheader("📊 Gráfico: Receita Mensal dos Últimos 12 Meses")
    fig_receita = px.bar(receita_mensal, x='mes', y='valor', title='Receita Mensal — Últimos 12 Meses')
    st.plotly_chart(fig_receita)

    # Projeção: Média Móvel Exponencial (EMA)
    if receita_mensal['valor'].sum() > 0:
        receita_mensal['EMA'] = receita_mensal['valor'].ewm(span=3, adjust=False).mean()
        ultima_data = pd.to_datetime(receita_mensal['mes'].iloc[-1])

        meses_futuros = pd.period_range(
            start=ultima_data.to_period('M') + 1,
            end=pd.Period(f"{ultima_data.year}-12", freq='M'),
            freq='M'
        )

        ultima_ema = receita_mensal['EMA'].iloc[-1]

        previsao = pd.DataFrame({
            'mes': meses_futuros.astype(str),
            'valor_projetado': [ultima_ema] * len(meses_futuros)
        })

        st.subheader("📈 Projeção de Receita para os Próximos Meses")
        st.dataframe(previsao)

        fig_proj = px.bar(previsao, x='mes', y='valor_projetado', title='Projeção de Receita — Próximos Meses (EMA)')
        st.plotly_chart(fig_proj)

        # GAP DE CAIXA: Receita projetada - Despesa prevista

        despesa_prevista = a_vencer.copy()
        despesa_prevista['mes_ano'] = despesa_prevista['data de vencimento'].dt.to_period('M').astype(str)
        despesa_agregada = despesa_prevista.groupby('mes_ano')['valor'].sum().reset_index()
        despesa_agregada = despesa_agregada.rename(columns={'valor': 'despesa_prevista'})

        gap_df = previsao.copy()
        gap_df = gap_df.rename(columns={'valor_projetado': 'receita_projetada'})
        gap_df['despesa_prevista'] = gap_df['mes'].map(
            despesa_agregada.set_index('mes_ano')['despesa_prevista']
        ).fillna(0)

        gap_df['despesa_prevista'] = gap_df['despesa_prevista'].abs()

        gap_df['gap_caixa'] = gap_df['receita_projetada'] - gap_df['despesa_prevista']

        st.subheader("📊 Gráfico: Gap de Caixa (Receita Projetada - Despesa Prevista)")

        fig_gap = px.bar(
            gap_df, 
            x='mes', 
            y='gap_caixa', 
            title='Gap de Caixa — Receita Projetada vs. Despesa Prevista',
            labels={'gap_caixa': 'Gap de Caixa (R$)'},
            color='gap_caixa',
            color_continuous_scale='RdYlGn'
        )

        st.plotly_chart(fig_gap)

    else:
        st.warning("❗ Não há dados de receita recebida suficientes para gerar projeção e gap de caixa.")
