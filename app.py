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

uploaded_file = st.file_uploader("📄 Escolha o arquivo CSV", type=["csv", "txt"])
data_limite = st.date_input("📆 Selecione a data de análise (Recorte Temporal)")

if uploaded_file is not None and data_limite is not None:
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

    data_limite = pd.to_datetime(data_limite)

    # ✅ DESPESAS
    st.header("💸 Análise de Despesas até a Data Selecionada")

    despesas = df[df['tipo'] == 'Despesa'].copy()

    despesas_atrasadas = despesas[
        (despesas['data de vencimento'] <= data_limite) &
        ((despesas['data de pagamento'] > data_limite) | despesas['data de pagamento'].isna())
    ].copy()

    despesas_a_vencer = despesas[
        (despesas['data de vencimento'] > data_limite)
    ].copy()

    for idx, row in despesas_a_vencer.iterrows():
        if row['valor'] == 0 or pd.isna(row['valor']):
            historico = df[
                (df['descrição'] == row['descrição']) &
                (df['categoria'] == row['categoria']) &
                (df['cliente/fornecedor'] == row['cliente/fornecedor']) &
                (df['status'] == 'Pago')
            ]
            if not historico.empty:
                media_valor = historico['valor'].mean()
                despesas_a_vencer.at[idx, 'valor'] = media_valor

    st.subheader("⏰ Despesas Atrasadas até a data selecionada")
    despesas_atrasadas['mes_ano'] = despesas_atrasadas['data de vencimento'].dt.to_period('M').astype(str)
    atrasadas_group = despesas_atrasadas.groupby(['cliente/fornecedor', 'categoria', 'mes_ano'])['valor'].sum().reset_index()
    st.dataframe(atrasadas_group)
    st.write(f"**Total:** R$ {despesas_atrasadas['valor'].sum():,.2f} | **{len(despesas_atrasadas)} registros**")

    st.subheader("⏳ Despesas A Vencer após a data selecionada")
    a_vencer_group = despesas_a_vencer.groupby(['cliente/fornecedor', 'categoria', 'data de vencimento'])['valor'].sum().reset_index()
    st.dataframe(a_vencer_group)
    st.write(f"**Total:** R$ {despesas_a_vencer['valor'].sum():,.2f} | **{len(despesas_a_vencer)} registros**")

    grafico_despesas = despesas_a_vencer.copy()
    grafico_despesas['mes_ano'] = grafico_despesas['data de vencimento'].dt.to_period('M').astype(str)
    grafico = grafico_despesas.groupby('mes_ano')['valor'].sum().reset_index()

    st.subheader("📊 Gráfico: Despesas a Vencer Mês a Mês")
    fig_desp = px.bar(grafico, x='mes_ano', y='valor')
    st.plotly_chart(fig_desp)

    st.success("✅ Análise de despesas até a data selecionada finalizada com sucesso.")

    # ✅ RECEITAS
    st.header("💰 Análise de Receitas (Projeção com base na data selecionada)")
    receitas = df[(df['tipo'] == 'Receita') & (df['data de pagamento'] <= data_limite)].copy()
    receitas['mes_recebimento'] = receitas['data de pagamento'].dt.to_period('M')

    receita_mensal = receitas.groupby('mes_recebimento')['valor'].sum().reset_index()
    receita_mensal.columns = ['mes', 'valor']
    receita_mensal['mes'] = receita_mensal['mes'].astype(str)

    st.subheader("📊 Receita Mensal Histórica (Base Recorte)")
    fig_receita = px.bar(receita_mensal, x='mes', y='valor')
    st.plotly_chart(fig_receita)

    if receita_mensal['valor'].sum() > 0:
        receita_mensal['EMA'] = receita_mensal['valor'].ewm(span=8, adjust=False).mean()
        ultima_data = pd.to_datetime(receita_mensal['mes'].iloc[-1])

        meses_futuros = pd.period_range(
            start=ultima_data.to_period('M') + 1,
            end=pd.Period(f"{ultima_data.year}-12", freq='M'),
            freq='M'
        )

        ultima_ema = receita_mensal['EMA'].iloc[-1]

        previsao = pd.DataFrame({
            'mes': meses_futuros.astype(str),
            'receita_projetada': [ultima_ema] * len(meses_futuros)
        })

        st.subheader("📈 Projeção de Receita (Base Recorte)")
        st.dataframe(previsao)

        fig_proj = px.bar(previsao, x='mes', y='receita_projetada')
        st.plotly_chart(fig_proj)

        # GAP DE CAIXA
        despesa_prevista = despesas_a_vencer.copy()
        despesa_prevista['mes_ano'] = despesa_prevista['data de vencimento'].dt.to_period('M').astype(str)
        despesa_agregada = despesa_prevista.groupby('mes_ano')['valor'].sum().reset_index()
        despesa_agregada = despesa_agregada.rename(columns={'valor': 'despesa_prevista'})

        gap_df = previsao.merge(despesa_agregada, left_on='mes', right_on='mes_ano', how='left').drop(columns='mes_ano')
        gap_df['despesa_prevista'] = gap_df['despesa_prevista'].fillna(0)
        gap_df['gap_caixa'] = gap_df['receita_projetada'] - gap_df['despesa_prevista'].abs()

        st.subheader("📊 Gap de Caixa Projeção")
        fig_gap = px.bar(
            gap_df,
            x='mes',
            y='gap_caixa',
            color='gap_caixa',
            color_continuous_scale='RdYlGn',
            title='Gap de Caixa — Receita Projetada vs. Despesa Prevista',
            labels={'gap_caixa': 'Gap de Caixa (R$)'}
        )
        st.plotly_chart(fig_gap)
    else:
        st.warning("❗️ Não há dados de receita suficientes antes da data selecionada para projeção.")
