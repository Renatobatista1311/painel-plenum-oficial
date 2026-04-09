import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, date, timedelta

# Título e layout
st.set_page_config(page_title="Dashboard de Suporte - Plenum", layout="wide")
st.title("📊 Painel de Análise de Suporte - Plenum Sistemas")

# --- CONFIGURAÇÕES DA PLENUM E API ---
COR_PLENUM = '#FF6400'
COR_SECUNDARIA = '#555555'
TAMANHO_FONTE = 14
TOKEN_MOVIDESK = st.secrets["TOKEN_MOVIDESK"]
CORES_EXTRAS = ['#FF6400', '#555555', '#FF8533', '#888888', '#FFA666', '#333333', '#FFC299']

PRODUTOS_PRINCIPAIS = ['PDV LEGAL', 'XMENU', 'DIGISAT', 'HIPER', 'SAIPOS']

def formata_tempo(segundos):
    if pd.isna(segundos) or segundos < 0: return "0s"
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

# --- LÓGICA DE DATAS ---
hoje = datetime.now()

st.sidebar.header("📅 Período de Análise")
opcao_periodo = st.sidebar.radio(
    "Escolha o filtro:",
    ["Esse Mês", "Mês Passado", "Personalizado"]
)

if opcao_periodo == "Esse Mês":
    data_inicio_ui = date(hoje.year, hoje.month, 1)
    data_fim_ui = hoje.date()
elif opcao_periodo == "Mês Passado":
    primeiro_dia_este_mes = date(hoje.year, hoje.month, 1)
    ultimo_dia_mes_passado = primeiro_dia_este_mes - timedelta(days=1)
    data_inicio_ui = date(ultimo_dia_mes_passado.year, ultimo_dia_mes_passado.month, 1)
    data_fim_ui = ultimo_dia_mes_passado
else:
    data_inicio_ui = st.sidebar.date_input("Data Inicial", date(hoje.year, hoje.month, 1), format="DD/MM/YYYY")
    data_fim_ui = st.sidebar.date_input("Data Final", hoje.date(), format="DD/MM/YYYY")

st.sidebar.divider()

inicio_brt = datetime.combine(data_inicio_ui, datetime.min.time())
fim_brt = datetime.combine(data_fim_ui, datetime.max.time())

inicio_utc = inicio_brt + timedelta(hours=3)
fim_utc = fim_brt + timedelta(hours=3)

data_inicio_api = inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')
data_fim_api = fim_utc.strftime('%Y-%m-%dT%H:%M:%S.999Z')

@st.cache_data(ttl=3600) 
def buscar_dados_movidesk(inicio_iso, fim_iso):
    todas_linhas = []
    skip = 0
    limite_maximo = 10000 
    
    tradutor_status = {
        'New': 'Novo',
        'In progress': 'Em andamento',
        'InAttendance': 'Em atendimento',
        'Stopped': 'Parado',
        'Resolved': 'Resolvido',
        'Closed': 'Resolvido', 
        'Canceled': 'Cancelado'
    }
    
    url = "https://api.movidesk.com/public/v1/tickets"
    
    while skip < limite_maximo:
        params = {
            'token': TOKEN_MOVIDESK,
            '$select': 'id,category,baseStatus,createdDate,serviceFull,owner,resolvedInFirstCall,chatTalkTime,chatWaitingTime,origin,clients',
            '$expand': 'owner,clients',
            '$filter': f"createdDate ge {inicio_iso} and createdDate le {fim_iso}",
            '$top': '1000',
            '$skip': str(skip),
            '$orderby': 'createdDate desc'
        }
        
        try:
            resposta = requests.get(url, params=params, timeout=30)
            
            if resposta.status_code == 200:
                dados_json = resposta.json()
                if not dados_json: 
                    break 
                
                for ticket in dados_json:
                    numero = str(ticket.get('id', ''))
                    categoria = ticket.get('category')
                    categoria = categoria.strip() if categoria else 'Não definido'
                    
                    status_raw = ticket.get('baseStatus', '')
                    status = tradutor_status.get(status_raw, status_raw)
                    
                    data_criacao = ticket.get('createdDate', '')
                    aberto_em = ''
                    if data_criacao:
                        try:
                            data_obj = datetime.fromisoformat(data_criacao.split('.')[0])
                            data_obj_brt = data_obj - timedelta(hours=3)
                            aberto_em = data_obj_brt.strftime('%d/%m/%Y')
                        except:
                            aberto_em = data_criacao
                            
                    owner_dict = ticket.get('owner') or {}
                    responsavel = owner_dict.get('businessName', 'Sem Responsável')
                    
                    clientes_lista = ticket.get('clients') or []
                    cliente_nome = clientes_lista[0].get('businessName', 'Não Informado') if clientes_lista else 'Não Informado'
                    
                    lista_servicos = ticket.get('serviceFull') or []
                    produto = lista_servicos[0].strip() if len(lista_servicos) > 0 else "Não definido"
                    servico = lista_servicos[1].strip() if len(lista_servicos) > 1 else "Não definido"
                    subservico = lista_servicos[2].strip() if len(lista_servicos) > 2 else "Geral/Não detalhado" 
                    
                    atendeu_hora = 'Sim' if ticket.get('resolvedInFirstCall') is True else 'Não'
                    
                    chat_talk = ticket.get('chatTalkTime')
                    chat_wait = ticket.get('chatWaitingTime')
                    
                    origem_cod = ticket.get('origin')
                    if origem_cod in [1, 5, 8]:
                        canal = "Cliente"
                    elif origem_cod in [3, 7]:
                        canal = "E-mail"
                    elif origem_cod in [18, 20, 23, 24, 25]:
                        canal = "WhatsApp Business Movidesk"
                    elif origem_cod in [2, 13, 14, 15, 16, 21]:
                        canal = "Agente"
                    else:
                        canal = "Outros"
                            
                    todas_linhas.append({
                        'Número': numero,
                        'Cliente': cliente_nome,
                        'Categoria': categoria,
                        'Status': status,
                        'Aberto em': aberto_em,
                        'Responsável': responsavel,
                        'Produto': produto,
                        'Servico': servico,
                        'Subservico': subservico,
                        'Atendeu na Hora': atendeu_hora,
                        'Tempo Conversa': chat_talk,
                        'Tempo Espera': chat_wait,
                        'Canal': canal
                    })
                    
                skip += 1000 
            else:
                st.error(f"Erro do Movidesk: {resposta.status_code} - {resposta.text}")
                break
        except Exception as e:
            st.error(f"Erro de conexão com a internet: {e}")
            break
            
    return pd.DataFrame(todas_linhas)

atualizar = st.sidebar.button("🔄 Buscar Dados Deste Período", use_container_width=True)

if 'base_completa' not in st.session_state or atualizar:
    with st.spinner('Puxando tickets, mapeando hardware e calculando KPIs...'):
        st.cache_data.clear() 
        st.session_state.base_completa = buscar_dados_movidesk(data_inicio_api, data_fim_api)

base_completa = st.session_state.base_completa

if not base_completa.empty:
    coluna_numero = 'Número'
    coluna_data = 'Aberto em'
    coluna_resp = 'Responsável'
    coluna_status = 'Status' 
    coluna_categoria = 'Categoria'
    
    base_completa['Tempo Conversa'] = pd.to_numeric(base_completa['Tempo Conversa'], errors='coerce')
    base_completa['Tempo Espera'] = pd.to_numeric(base_completa['Tempo Espera'], errors='coerce')
    
    base_completa['Produto_Upper'] = base_completa['Produto'].str.upper().str.strip()
    base_completa['Servico_Upper'] = base_completa['Servico'].str.upper().str.strip()
    
    tem_implanta = base_completa['Produto_Upper'].str.contains('IMPLANTA') | base_completa['Servico_Upper'].str.contains('IMPLANTA')
    tem_pos = base_completa['Produto_Upper'].str.contains('PÓS|POS') | base_completa['Servico_Upper'].str.contains('PÓS|POS')
    
    base_completa['É_Implantacao'] = tem_implanta & ~tem_pos
    base_completa['É_Produto_Principal'] = base_completa['Produto_Upper'].isin(PRODUTOS_PRINCIPAIS)
    
    # 1. RESUMO GERAL
    st.subheader(f"💡 Resumo Geral - De {data_inicio_ui.strftime('%d/%m/%Y')} até {data_fim_ui.strftime('%d/%m/%Y')}")
    col1, col2, col3 = st.columns(3)
    
    total_chamados = len(base_completa)
    
    base_principais = base_completa[base_completa['É_Produto_Principal'] & ~base_completa['É_Implantacao']]
    produto_campeao = base_principais['Produto'].value_counts().idxmax() if not base_principais.empty else "Nenhum"
    qtd_produtos = base_principais['Produto'].nunique()
    
    col1.metric("Total Absoluto de Chamados", total_chamados)
    col2.metric("Software Campeão de Demandas", produto_campeao)
    col3.metric("Softwares Atendidos", qtd_produtos)
    
    st.divider()
    
    # 2. VISÃO GERAL POR PRODUTO (SÓ OS PRINCIPAIS)
    st.header("💻 Desempenho dos Softwares (Produtos Principais)")
    total_principais = len(base_principais)
    st.markdown(f"**Total de tickets nesta categoria:** {total_principais}")
    
    col_grafico1, col_grafico2 = st.columns([1, 2])
    
    with col_grafico1:
        if not base_principais.empty:
            st.write("Representatividade por Software:")
            contagem_produto = base_principais['Produto'].value_counts().reset_index()
            contagem_produto.columns = ['Software', 'Qtd.']
            contagem_produto['%'] = (contagem_produto['Qtd.'] / total_principais * 100).apply(lambda x: f"{x:.2f}%")
            
            df_exibicao_prod = contagem_produto.copy()
            df_exibicao_prod.loc[len(df_exibicao_prod)] = ['TOTAL', total_principais, "100.00%"]
            st.dataframe(df_exibicao_prod, hide_index=True, use_container_width=True)
        else:
            st.info("Sem dados")
    
    with col_grafico2:
        if not base_principais.empty:
            fig1 = px.bar(contagem_produto, x='Software', y='Qtd.', text='Qtd.', color_discrete_sequence=[COR_PLENUM])
            fig1.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
            fig1.update_layout(xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(t=20))
            st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("#### Detalhamento de Serviços do Software")
    if not base_principais.empty:
        produto_selecionado = st.selectbox("Escolha um produto principal para detalhar:", base_principais['Produto'].unique())
        dados_filtrados = base_principais[base_principais['Produto'] == produto_selecionado]
        contagem_servico = dados_filtrados['Servico'].value_counts().reset_index()
        contagem_servico.columns = ['Serviço', 'Chamados']
        fig2 = px.bar(contagem_servico, x='Serviço', y='Chamados', text='Chamados', color_discrete_sequence=[COR_PLENUM])
        fig2.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
        fig2.update_layout(xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(t=20, b=0))
        st.plotly_chart(fig2, use_container_width=True)
            
    st.divider()

    # --- O PESO DO HARDWARE NO SUPORTE ---
    st.header("🔧 O Peso do Hardware no Suporte")
    st.markdown("A dor da operação: Atendimentos físicos e de infraestrutura assumidos pelo time de software.")
    
    base_hardware = base_principais[base_principais['Servico_Upper'] == 'HARDWARE']
    
    if not base_hardware.empty:
        # RADAR ANTI-PREGUIÇA DO HARDWARE
        hw_nao_detalhado = base_hardware[base_hardware['Subservico'] == 'Geral/Não detalhado']
        if not hw_nao_detalhado.empty:
            st.warning(f"⚠️ **Atenção da Gestão:** Existem {len(hw_nao_detalhado)} ticket(s) de Hardware sem o equipamento (3º nível) preenchido. Ajuste no Movidesk:")
            df_hw_nd = hw_nao_detalhado[['Número', 'Produto', 'Responsável']].copy()
            df_hw_nd['Número'] = df_hw_nd['Número'].astype(str).str.replace(".0", "", regex=False)
            st.dataframe(df_hw_nd, hide_index=True, use_container_width=True)
        
        total_hw = len(base_hardware)
        pct_hw = (total_hw / total_principais) * 100 if total_principais > 0 else 0
        
        col_hw1, col_hw2 = st.columns([1, 2])
        with col_hw1:
            st.metric("Total de Chamados de Hardware", total_hw, f"{pct_hw:.2f}% dos produtos principais", delta_color="inverse")
            st.write("Principais Ofensores (Equipamentos):")
            
            contagem_equip = base_hardware['Subservico'].value_counts().reset_index()
            contagem_equip.columns = ['Equipamento / 3º Nível', 'Qtd.']
            contagem_equip['%'] = (contagem_equip['Qtd.'] / total_hw * 100).apply(lambda x: f"{x:.2f}%")
            
            df_equip_view = contagem_equip.copy()
            df_equip_view.loc[len(df_equip_view)] = ['TOTAL', total_hw, "100.00%"]
            st.dataframe(df_equip_view, hide_index=True, use_container_width=True)
            
        with col_hw2:
            df_hw_prod = base_hardware.groupby(['Produto', 'Subservico']).size().reset_index(name='Qtd.')
            fig_hw = px.bar(df_hw_prod, x='Produto', y='Qtd.', color='Subservico', text='Qtd.', 
                            title="Desgaste de Hardware por Software", color_discrete_sequence=CORES_EXTRAS)
            fig_hw.update_layout(xaxis_title="", yaxis_title="Chamados", font=dict(size=TAMANHO_FONTE), barmode='stack')
            st.plotly_chart(fig_hw, use_container_width=True)
    else:
        st.success("🎉 Nenhum chamado de Hardware registrado neste período! A infraestrutura dos clientes está voando!")

    st.divider()

    # 3. O SHOW: IMPLANTAÇÕES SEPARADAS
    st.header("🚀 Acompanhamento de Implantações")
    base_implantacao = base_completa[base_completa['É_Implantacao']]
    
    if not base_implantacao.empty:
        col_i1, col_i2 = st.columns([1, 4])
        with col_i1:
            st.metric("Total de Implantações", len(base_implantacao))
        with col_i2:
            df_implantacao = base_implantacao[['Número', 'Cliente', 'Produto', 'Servico', 'Responsável', 'Status']].copy()
            df_implantacao['Número'] = df_implantacao['Número'].astype(str).str.replace(".0", "", regex=False)
            st.dataframe(df_implantacao, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhuma implantação registrada para o período selecionado.")

    st.divider()
    
    # 4. ATENDIMENTOS INTERNOS E OPERACIONAIS
    st.header("⚙️ Atendimentos Internos & Operacionais")
    base_internos = base_completa[~base_completa['É_Produto_Principal'] & ~base_completa['É_Implantacao']]
    
    st.markdown(f"**Total de tickets nesta categoria:** {len(base_internos)}")
    
    base_nao_definidos = base_internos[base_internos['Produto'] == 'Não definido']
    if not base_nao_definidos.empty:
        st.warning(f"⚠️ **Atenção da Gestão:** Encontramos {len(base_nao_definidos)} ticket(s) classificado(s) como 'Não definido'. Ajuste no Movidesk:")
        df_nd = base_nao_definidos[['Número', 'Responsável', 'Canal']].copy()
        df_nd['Número'] = df_nd['Número'].astype(str).str.replace(".0", "", regex=False)
        st.dataframe(df_nd, hide_index=True, use_container_width=True)
    
    if not base_internos.empty:
        contagem_internos = base_internos['Produto'].value_counts().reset_index()
        contagem_internos.columns = ['Tipo de Atendimento', 'Chamados']
        fig_int = px.bar(contagem_internos, x='Tipo de Atendimento', y='Chamados', text='Chamados', color_discrete_sequence=[COR_PLENUM])
        fig_int.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
        fig_int.update_layout(xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(t=20))
        st.plotly_chart(fig_int, use_container_width=True)
    else:
        st.info("Nenhum atendimento operacional/interno no período.")

    st.divider()

    # 5. EFICIÊNCIA GERAL: ATENDEU NA HORA
    st.header("⚡ Eficiência Geral: Atendeu na Hora (Sim/Não)")
    base_fcr = base_completa[base_completa['Atendeu na Hora'].isin(['Sim', 'Não'])] 
    
    if not base_fcr.empty:
        total_fcr = len(base_fcr)
        qtd_sim = len(base_fcr[base_fcr['Atendeu na Hora'] == 'Sim'])
        qtd_nao = len(base_fcr[base_fcr['Atendeu na Hora'] == 'Não'])
        
        pct_sim = (qtd_sim / total_fcr) * 100 if total_fcr > 0 else 0
        pct_nao = (qtd_nao / total_fcr) * 100 if total_fcr > 0 else 0
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            df_fcr = pd.DataFrame({
                'ATENDEU NA HORA (SIM OU NÃO)': ['Sim', 'Não'],
                'Qtd.': [qtd_sim, qtd_nao],
                '%': [f"{pct_sim:.2f}%", f"{pct_nao:.2f}%"]
            })
            st.dataframe(df_fcr, hide_index=True, use_container_width=True)
            
        with col_f2:
            fig_fcr = px.pie(df_fcr, values='Qtd.', names='ATENDEU NA HORA (SIM OU NÃO)', hole=0.4, 
                             color='ATENDEU NA HORA (SIM OU NÃO)', color_discrete_map={'Sim': COR_PLENUM, 'Não': COR_SECUNDARIA})
            fig_fcr.update_traces(textinfo='percent+label', textfont_size=TAMANHO_FONTE)
            fig_fcr.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_fcr, use_container_width=True)
            
    st.divider()
    
    # 6. TICKETS POR CANAL DE ABERTURA
    st.header("📞 Tickets por Canal de Abertura")
    
    contagem_canais = base_completa['Canal'].value_counts().reset_index()
    contagem_canais.columns = ['TICKETS POR CANAL DE ABERTURA', 'Qtd.']
    
    total_canais = contagem_canais['Qtd.'].sum()
    contagem_canais['%'] = (contagem_canais['Qtd.'] / total_canais * 100).apply(lambda x: f"{x:.2f}%")
    
    col_cn1, col_cn2 = st.columns(2)
    with col_cn1:
        df_exibicao_canais = contagem_canais.copy()
        df_exibicao_canais.loc[len(df_exibicao_canais)] = ['TOTAL', total_canais, "100.00%"]
        st.dataframe(df_exibicao_canais, hide_index=True, use_container_width=True)
        
    with col_cn2:
        fig_canais = px.pie(contagem_canais, values='Qtd.', names='TICKETS POR CANAL DE ABERTURA', hole=0.4, 
                            color_discrete_sequence=['#FF6400', '#555555', '#FF8533', '#888888', '#FFA666'])
        fig_canais.update_traces(textinfo='percent+label', textfont_size=TAMANHO_FONTE)
        fig_canais.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_canais, use_container_width=True)
        
    st.divider()
    
    # 7. RESOLVIDOS POR ATENDENTE
    st.subheader("Tickets Resolvidos por Atendente (Geral)")
    base_resolvidos = base_completa[base_completa[coluna_status] == 'Resolvido']
    if not base_resolvidos.empty:
        contagem_resp = base_resolvidos[coluna_resp].value_counts().reset_index()
        contagem_resp.columns = ['Responsável', 'Chamados']
        fig3 = px.bar(contagem_resp, x='Chamados', y='Responsável', orientation='h', text='Chamados', color_discrete_sequence=[COR_PLENUM])
        fig3.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
        fig3.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(r=40))
        st.plotly_chart(fig3, use_container_width=True)
    
    st.divider()
    
    # 8. INDICADORES DE PLANTÃO
    st.header("🚨 Indicadores de Plantão")
    base_plantao = base_completa[base_completa[coluna_categoria].astype(str).str.strip().str.lower().isin(['plantão', 'plantao'])].copy()
    
    if not base_plantao.empty:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.subheader("Plantão por Produto")
            contagem_plantao_prod = base_plantao['Produto'].value_counts().reset_index()
            contagem_plantao_prod.columns = ['Produto', 'Chamados']
            fig_p1 = px.bar(contagem_plantao_prod, x='Produto', y='Chamados', text='Chamados', color_discrete_sequence=[COR_PLENUM])
            fig_p1.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
            fig_p1.update_layout(xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(t=40))
            st.plotly_chart(fig_p1, use_container_width=True)
        
        with col_p2:
            st.subheader("Plantão por Responsável")
            contagem_plantao_resp = base_plantao[coluna_resp].value_counts().reset_index()
            contagem_plantao_resp.columns = ['Responsável', 'Chamados']
            fig_p2 = px.bar(contagem_plantao_resp, x='Chamados', y='Responsável', orientation='h', text='Chamados', color_discrete_sequence=[COR_PLENUM])
            fig_p2.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
            fig_p2.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(r=40))
            st.plotly_chart(fig_p2, use_container_width=True)
        
        st.divider()
        
        base_plantao['Status Simplificado'] = base_plantao[coluna_status].apply(
            lambda x: 'Resolvidos' if x == 'Resolvido' else 'Não Resolvidos'
        )
        col_p3, col_p4 = st.columns(2)
        with col_p3:
            st.subheader("Eficácia do Plantão")
            contagem_status = base_plantao['Status Simplificado'].value_counts().reset_index()
            contagem_status.columns = ['Status', 'Chamados']
            fig_p3 = px.bar(contagem_status, x='Status', y='Chamados', text='Chamados', color='Status', 
                            color_discrete_map={'Resolvidos': COR_PLENUM, 'Não Resolvidos': COR_SECUNDARIA})
            fig_p3.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
            fig_p3.update_layout(xaxis_title="", yaxis_title="", font=dict(size=TAMANHO_FONTE), margin=dict(t=40), showlegend=False)
            st.plotly_chart(fig_p3, use_container_width=True)
        
        with col_p4:
            st.subheader("Tabela de Tickets Pendentes")
            tickets_pendentes = base_plantao[base_plantao['Status Simplificado'] == 'Não Resolvidos']
            if not tickets_pendentes.empty:
                tabela_exibicao = tickets_pendentes[[coluna_numero, 'Produto', coluna_resp, coluna_status]].copy()
                tabela_exibicao[coluna_numero] = tabela_exibicao[coluna_numero].astype(str).str.replace(".0", "", regex=False)
                st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)
            else:
                st.success("🎉 Todos os tickets de plantão foram resolvidos!")

        st.divider()

        # --- O PESO DO HARDWARE NO PLANTÃO (MOVIDO PARA CÁ) ---
        st.subheader("🔧 O Peso do Hardware no Plantão")
        base_plantao_hw = base_plantao[base_plantao['Servico_Upper'] == 'HARDWARE']
        
        if not base_plantao_hw.empty:
            # RADAR ANTI-PREGUIÇA NO PLANTÃO
            phw_nao_detalhado = base_plantao_hw[base_plantao_hw['Subservico'] == 'Geral/Não detalhado']
            if not phw_nao_detalhado.empty:
                st.warning(f"⚠️ **Atenção da Gestão:** Existem {len(phw_nao_detalhado)} ticket(s) de Hardware no Plantão sem o equipamento (3º nível) preenchido:")
                df_phw_nd = phw_nao_detalhado[['Número', 'Produto', 'Responsável']].copy()
                df_phw_nd['Número'] = df_phw_nd['Número'].astype(str).str.replace(".0", "", regex=False)
                st.dataframe(df_phw_nd, hide_index=True, use_container_width=True)

            col_phw1, col_phw2 = st.columns(2)
            with col_phw1:
                df_phw = base_plantao_hw['Subservico'].value_counts().reset_index()
                df_phw.columns = ['Equipamento', 'Qtd.']
                fig_phw = px.pie(df_phw, values='Qtd.', names='Equipamento', hole=0.4, color_discrete_sequence=CORES_EXTRAS)
                fig_phw.update_traces(textinfo='percent+label')
                fig_phw.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_phw, use_container_width=True)
            with col_phw2:
                st.write("Detalhamento dos Tickets de Hardware no Plantão:")
                df_phw_tabela = base_plantao_hw[['Número', 'Produto', 'Subservico', 'Responsável']].copy()
                df_phw_tabela['Número'] = df_phw_tabela['Número'].astype(str).str.replace(".0", "", regex=False)
                st.dataframe(df_phw_tabela, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhum B.O de Hardware resolvido no plantão. Milagre!")
            
    else:
        st.info("Nenhum atendimento de 'Plantão' encontrado no período selecionado.")

    st.divider()

    # 9. INDICADORES DE CHAT 
    st.header("💬 Indicadores de Chat")
    
    base_chat = base_completa.dropna(subset=['Tempo Conversa', 'Tempo Espera'], how='all').copy()
    
    if not base_chat.empty:
        total_chats = len(base_chat)
        chats_sim = len(base_chat[base_chat['Atendeu na Hora'] == 'Sim'])
        chats_nao = total_chats - chats_sim
        
        pct_chats_sim = (chats_sim / total_chats) * 100 if total_chats > 0 else 0
        pct_chats_nao = (chats_nao / total_chats) * 100 if total_chats > 0 else 0
        
        media_conversa = base_chat['Tempo Conversa'].mean()
        media_espera = base_chat['Tempo Espera'].mean()
        
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Total de Chats Atendidos", total_chats)
        cc2.metric("Média de Espera na Fila", formata_tempo(media_espera))
        cc3.metric("Média de Duração (Conversa)", formata_tempo(media_conversa))
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.write("Resolutividade do Chat (FCR):")
            df_chat_fcr = pd.DataFrame({
                'INDICADORES CHAT': ['Chats Resolvidos em Primeiro Atendimento', 'Chats Não Resolvidos em Primeiro Atendimento'],
                'Qtd.': [chats_sim, chats_nao],
                '%': [f"{pct_chats_sim:.2f}%", f"{pct_chats_nao:.2f}%"]
            })
            st.dataframe(df_chat_fcr, hide_index=True, use_container_width=True)
            
        with col_c2:
            st.write("🏆 Ranking de Agilidade por Atendente:")
            ranking = base_chat.groupby('Responsável').agg(
                Qtd_Chats=('Número', 'count'),
                Media_Esp=('Tempo Espera', 'mean'),
                Media_Conv=('Tempo Conversa', 'mean')
            ).reset_index()
            
            ranking['Espera Média'] = ranking['Media_Esp'].apply(formata_tempo)
            ranking['Duração Média'] = ranking['Media_Conv'].apply(formata_tempo)
            
            ranking = ranking.sort_values('Qtd_Chats', ascending=False)
            
            df_ranking_view = ranking[['Responsável', 'Qtd_Chats', 'Espera Média', 'Duração Média']].rename(columns={'Qtd_Chats': 'Total Atendido'})
            st.dataframe(df_ranking_view, hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum atendimento via Chat foi registrado neste período.")

else:
    st.warning("Nenhum ticket encontrado para as datas selecionadas.")