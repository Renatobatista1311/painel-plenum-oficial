import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, date, timedelta

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Dashboard de Suporte - Plenum", layout="wide", initial_sidebar_state="expanded")

# --- CONFIGURAÇÕES DA PLENUM E API ---
COR_PLENUM = '#FF6400'
COR_SECUNDARIA = '#555555'
TAMANHO_FONTE = 14
CORES_EXTRAS = ['#FF6400', '#555555', '#FF8533', '#888888', '#FFA666', '#333333', '#FFC299']
PRODUTOS_PRINCIPAIS = ['PDV LEGAL', 'XMENU', 'DIGISAT', 'HIPER', 'SAIPOS']

# Lista de exclusão EXATA para limpar o ranking (Não afeta nomes parecidos)
COLABORADORES_INTERNOS = [
    'A Mariana Vilela',
    'Tais Alves - Plenum Sistemas',
    'Mirian - Plenum sistemas',
    'Jessica - Plenum Sistemas'
]

# --- TRAVA DE SEGURANÇA (NUVEM VS LOCAL) ---
TOKEN_MOVIDESK = st.secrets["TOKEN_MOVIDESK"]

# --- MOTOR DE TEMPO (Formato Cronômetro HH:MM:SS) ---
def formata_tempo(segundos):
    if pd.isna(segundos) or segundos < 0: return "00:00:00"
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# --- MENU LATERAL (NAVEGAÇÃO DE PÁGINAS) ---
st.sidebar.image("https://plenumsistemas.com.br/wp-content/uploads/2021/08/cropped-logo_plenum_laranja-3-1.png", width=200)
st.sidebar.title("Navegação")
pagina_selecionada = st.sidebar.radio(
    "Escolha o Setor:",
    ["📊 Visão Operacional", "🏢 Ranking de Clientes"]
)

# --- CABEÇALHO E FILTRO GLOBAL DE DATAS (NO TOPO) ---
st.title("Painel de Gestão - Plenum Sistemas")
st.markdown("---")

st.subheader("📅 Filtro Global de Período")
hoje = datetime.now()
col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

with col_f1:
    opcao_periodo = st.selectbox("Escolha o filtro:", ["Esse Mês", "Mês Passado", "Personalizado"])

if opcao_periodo == "Esse Mês":
    data_inicio_ui = date(hoje.year, hoje.month, 1)
    data_fim_ui = hoje.date()
elif opcao_periodo == "Mês Passado":
    primeiro_dia_este_mes = date(hoje.year, hoje.month, 1)
    ultimo_dia_mes_passado = primeiro_dia_este_mes - timedelta(days=1)
    data_inicio_ui = date(ultimo_dia_mes_passado.year, ultimo_dia_mes_passado.month, 1)
    data_fim_ui = ultimo_dia_mes_passado
else:
    with col_f2:
        data_inicio_ui = st.date_input("Data Inicial", date(hoje.year, hoje.month, 1), format="DD/MM/YYYY")
    with col_f3:
        data_fim_ui = st.date_input("Data Final", hoje.date(), format="DD/MM/YYYY")

st.write("") 
atualizar = st.button("🔄 Sincronizar Movidesk com este período", type="primary", use_container_width=True)

st.markdown("---")

# Ajuste do Fuso Horário
inicio_brt = datetime.combine(data_inicio_ui, datetime.min.time())
fim_brt = datetime.combine(data_fim_ui, datetime.max.time())
inicio_utc = inicio_brt + timedelta(hours=3)
fim_utc = fim_brt + timedelta(hours=3)
data_inicio_api = inicio_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')
data_fim_api = fim_utc.strftime('%Y-%m-%dT%H:%M:%S.999Z')

# --- MOTOR DE BUSCA (API) ---
@st.cache_data(ttl=3600) 
def buscar_dados_movidesk(inicio_iso, fim_iso):
    todas_linhas = []
    skip = 0
    limite_maximo = 50000 
    
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
                        except Exception: 
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
    
    return pd.DataFrame(todas_linhas), skip

if 'base_completa' not in st.session_state or atualizar:
    with st.spinner('Puxando dados e processando kpis...'):
        st.cache_data.clear() 
        df, registros_lidos = buscar_dados_movidesk(data_inicio_api, data_fim_api)
        st.session_state.base_completa = df
        st.session_state.registros_lidos = registros_lidos

base_completa = st.session_state.base_completa
registros_lidos = st.session_state.registros_lidos

if registros_lidos >= 50000:
    st.warning("⚠️ Limite de 50.000 chamados atingido na busca! Reduza o filtro de datas para garantir que nenhum dado antigo fique de fora.")

if not base_completa.empty:
    base_completa['Tempo Conversa'] = pd.to_numeric(base_completa['Tempo Conversa'], errors='coerce')
    base_completa['Tempo Espera'] = pd.to_numeric(base_completa['Tempo Espera'], errors='coerce')
    base_completa['Produto_Upper'] = base_completa['Produto'].str.upper().str.strip()
    base_completa['Servico_Upper'] = base_completa['Servico'].str.upper().str.strip()
    
    tem_implanta = base_completa['Produto_Upper'].str.contains('IMPLANTA') | base_completa['Servico_Upper'].str.contains('IMPLANTA')
    tem_pos = base_completa['Produto_Upper'].str.contains('PÓS|POS') | base_completa['Servico_Upper'].str.contains('PÓS|POS')
    
    base_completa['É_Implantacao'] = tem_implanta & ~tem_pos
    base_completa['É_Produto_Principal'] = base_completa['Produto_Upper'].isin(PRODUTOS_PRINCIPAIS)
    
    # =========================================================
    # PÁGINA 1: VISÃO OPERACIONAL
    # =========================================================
    if pagina_selecionada == "📊 Visão Operacional":
        
        st.header("📊 Visão Operacional do Suporte")
        
        col1, col2, col3 = st.columns(3)
        total_chamados = len(base_completa)
        base_principais = base_completa[base_completa['É_Produto_Principal'] & ~base_completa['É_Implantacao']]
        produto_campeao = base_principais['Produto'].value_counts().idxmax() if not base_principais.empty else "Nenhum"
        qtd_produtos = base_principais['Produto'].nunique()
        
        col1.metric("Total Absoluto de Chamados", total_chamados)
        col2.metric("Software Campeão de Demandas", produto_campeao)
        col3.metric("Softwares Atendidos", qtd_produtos)
        st.divider()
        
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

        st.header("🔧 O Peso do Hardware no Suporte")
        base_hardware = base_principais[base_principais['Servico_Upper'] == 'HARDWARE']
        
        if not base_hardware.empty:
            hw_nao_detalhado = base_hardware[base_hardware['Subservico'] == 'Geral/Não detalhado']
            
            # --- ALERTA CORPORATIVO 1: HARDWARE ---
            if not hw_nao_detalhado.empty:
                st.error(f"🚨 **Alerta de Gestão:** Existem {len(hw_nao_detalhado)} ticket(s) de Hardware sem o equipamento preenchido.")
                with st.expander("🔍 Ver detalhamento dos tickets"):
                    df_hw_nd = hw_nao_detalhado[['Número', 'Produto', 'Responsável']].copy()
                    df_hw_nd['Número'] = df_hw_nd['Número'].astype(str).str.replace(".0", "", regex=False)
                    st.dataframe(df_hw_nd, hide_index=True, use_container_width=True)
            
            total_hw = len(base_hardware)
            pct_hw = (total_hw / total_principais) * 100 if total_principais > 0 else 0
            
            col_hw1, col_hw2 = st.columns([1, 2])
            with col_hw1:
                st.metric("Total de Chamados de Hardware", total_hw, f"{pct_hw:.2f}% dos produtos principais", delta_color="inverse")
                contagem_equip = base_hardware['Subservico'].value_counts().reset_index()
                contagem_equip.columns = ['Equipamento / 3º Nível', 'Qtd.']
                contagem_equip['%'] = (contagem_equip['Qtd.'] / total_hw * 100).apply(lambda x: f"{x:.2f}%")
                df_equip_view = contagem_equip.copy()
                df_equip_view.loc[len(df_equip_view)] = ['TOTAL', total_hw, "100.00%"]
                st.dataframe(df_equip_view, hide_index=True, use_container_width=True)
            with col_hw2:
                df_hw_prod = base_hardware.groupby(['Produto', 'Subservico']).size().reset_index(name='Qtd.')
                fig_hw = px.bar(df_hw_prod, x='Produto', y='Qtd.', color='Subservico', text='Qtd.', title="Desgaste de Hardware por Software", color_discrete_sequence=CORES_EXTRAS)
                fig_hw.update_layout(xaxis_title="", yaxis_title="Chamados", barmode='stack')
                st.plotly_chart(fig_hw, use_container_width=True)
        else:
            st.success("🎉 Nenhum chamado de Hardware registrado neste período!")
        st.divider()

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
            st.info("Nenhuma implantação registrada.")
        st.divider()
        
        st.header("⚙️ Atendimentos Internos & Operacionais")
        base_internos = base_completa[~base_completa['É_Produto_Principal'] & ~base_completa['É_Implantacao']]
        st.markdown(f"**Total de tickets nesta categoria:** {len(base_internos)}")
        
        base_nao_definidos = base_internos[base_internos['Produto'] == 'Não definido']
        
        # --- ALERTA CORPORATIVO 2: NÃO DEFINIDOS ---
        if not base_nao_definidos.empty:
            st.error(f"🚨 **Alerta de Gestão:** Existem {len(base_nao_definidos)} ticket(s) classificado(s) como 'Não definido'.")
            with st.expander("🔍 Ver detalhamento dos tickets"):
                df_nd = base_nao_definidos[['Número', 'Responsável', 'Canal']].copy()
                df_nd['Número'] = df_nd['Número'].astype(str).str.replace(".0", "", regex=False)
                st.dataframe(df_nd, hide_index=True, use_container_width=True)
        
        if not base_internos.empty:
            contagem_internos = base_internos['Produto'].value_counts().reset_index()
            contagem_internos.columns = ['Tipo de Atendimento', 'Chamados']
            fig_int = px.bar(contagem_internos, x='Tipo de Atendimento', y='Chamados', text='Chamados', color_discrete_sequence=[COR_PLENUM])
            fig_int.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
            st.plotly_chart(fig_int, use_container_width=True)
        st.divider()

        col_ef1, col_ef2 = st.columns(2)
        with col_ef1:
            st.header("⚡ Atendeu na Hora (FCR)")
            base_fcr = base_completa[base_completa['Atendeu na Hora'].isin(['Sim', 'Não'])] 
            if not base_fcr.empty:
                df_fcr = base_fcr['Atendeu na Hora'].value_counts().reset_index()
                df_fcr.columns = ['FCR', 'Qtd']
                fig_fcr = px.pie(df_fcr, values='Qtd', names='FCR', hole=0.4, color='FCR', color_discrete_map={'Sim': COR_PLENUM, 'Não': COR_SECUNDARIA})
                fig_fcr.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_fcr, use_container_width=True)
        
        with col_ef2:
            st.header("📞 Canais de Abertura")
            contagem_canais = base_completa['Canal'].value_counts().reset_index()
            contagem_canais.columns = ['Canal', 'Qtd']
            fig_canais = px.pie(contagem_canais, values='Qtd', names='Canal', hole=0.4, color_discrete_sequence=CORES_EXTRAS)
            fig_canais.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_canais, use_container_width=True)
        st.divider()
        
        st.header("🚨 Indicadores de Plantão")
        base_plantao = base_completa[base_completa['Categoria'].astype(str).str.strip().str.lower().isin(['plantão', 'plantao'])].copy()
        if not base_plantao.empty:
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.subheader("Plantão por Produto")
                contagem_plantao_prod = base_plantao['Produto'].value_counts().reset_index()
                contagem_plantao_prod.columns = ['Produto', 'Chamados']
                fig_p1 = px.bar(contagem_plantao_prod, x='Produto', y='Chamados', text='Chamados', color_discrete_sequence=[COR_PLENUM])
                st.plotly_chart(fig_p1, use_container_width=True)
            with col_p2:
                st.subheader("Tabela de Pendentes")
                base_plantao['Status Simplificado'] = base_plantao['Status'].apply(lambda x: 'Resolvidos' if x == 'Resolvido' else 'Não Resolvidos')
                tickets_pendentes = base_plantao[base_plantao['Status Simplificado'] == 'Não Resolvidos']
                if not tickets_pendentes.empty:
                    tabela_exibicao = tickets_pendentes[['Número', 'Produto', 'Responsável', 'Status']].copy()
                    tabela_exibicao['Número'] = tabela_exibicao['Número'].astype(str).str.replace(".0", "", regex=False)
                    st.dataframe(tabela_exibicao, hide_index=True, use_container_width=True)
                else:
                    st.success("🎉 Todos os tickets de plantão foram resolvidos!")
        else:
            st.info("Nenhum atendimento de 'Plantão' encontrado.")
        st.divider()

        st.header("💬 Indicadores de Chat")
        base_chat = base_completa.dropna(subset=['Tempo Conversa', 'Tempo Espera'], how='all').copy()
        if not base_chat.empty:
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Total de Chats Atendidos", len(base_chat))
            cc2.metric("Média de Espera na Fila", formata_tempo(base_chat['Tempo Espera'].mean()))
            cc3.metric("Média de Duração", formata_tempo(base_chat['Tempo Conversa'].mean()))
            
            st.markdown("#### 🏆 Desempenho por Atendente")
            st.info("💡 **Dica de Análise:** A tabela abaixo está ordenada pelo volume de chamados. **Clique nos títulos das colunas** (como 'Duração Média') para reordenar do mais rápido para o mais lento!")
            
            ranking = base_chat.groupby('Responsável').agg(
                Qtd_Chats=('Número', 'count'), Media_Esp=('Tempo Espera', 'mean'), Media_Conv=('Tempo Conversa', 'mean')
            ).reset_index().sort_values('Qtd_Chats', ascending=False)
            ranking['Espera Média'] = ranking['Media_Esp'].apply(formata_tempo)
            ranking['Duração Média'] = ranking['Media_Conv'].apply(formata_tempo)
            df_ranking_view = ranking[['Responsável', 'Qtd_Chats', 'Espera Média', 'Duração Média']].rename(columns={'Qtd_Chats': 'Total Atendido'})
            st.dataframe(df_ranking_view, hide_index=True, use_container_width=True)
            
            chats_sem_dono = base_chat[base_chat['Responsável'] == 'Sem Responsável']
            
            # --- ALERTA CORPORATIVO 3: SEM RESPONSÁVEL ---
            if not chats_sem_dono.empty:
                st.error(f"🚨 **Alerta de Gestão:** Existem {len(chats_sem_dono)} chat(s) sem responsável atribuído.")
                with st.expander("🔍 Ver detalhamento dos tickets"):
                    tabela_infratores = chats_sem_dono[['Número', 'Aberto em', 'Cliente', 'Status']].copy()
                    tabela_infratores['Número'] = tabela_infratores['Número'].astype(str).str.replace(".0", "", regex=False)
                    st.dataframe(tabela_infratores, hide_index=True, use_container_width=True)

        else:
            st.info("Nenhum atendimento via Chat foi registrado.")


    # =========================================================
    # PÁGINA 2: RANKING DE CLIENTES
    # =========================================================
    elif pagina_selecionada == "🏢 Ranking de Clientes":
        
        st.header("🏢 Análise e Ranking de Clientes")
        st.markdown("Identifique os maiores ofensores da operação técnica para suporte comercial e tomada de decisão.")
        
        base_clientes = base_completa[
            (base_completa['Cliente'] != 'Não Informado') & 
            (~base_completa['Cliente'].isin(COLABORADORES_INTERNOS))
        ].copy()
        
        if not base_clientes.empty:
            col_rc1, col_rc2 = st.columns([1, 2])
            
            top_n = st.slider("Quantidade de Clientes no Top Ranking:", min_value=5, max_value=30, value=15, step=5)
            
            ranking_clientes = base_clientes.groupby('Cliente').size().reset_index(name='Total de Chamados')
            ranking_clientes = ranking_clientes.sort_values(by='Total de Chamados', ascending=False).head(top_n)
            
            with col_rc1:
                st.subheader(f"🏆 Top {top_n} Ofensores")
                st.dataframe(ranking_clientes, hide_index=True, use_container_width=True)
                
            with col_rc2:
                st.subheader(f"Volume de Demandas (Top {top_n})")
                fig_ranking = px.bar(ranking_clientes, x='Total de Chamados', y='Cliente', orientation='h', 
                                     text='Total de Chamados', color_discrete_sequence=[COR_PLENUM])
                fig_ranking.update_traces(textposition='outside', textfont_size=TAMANHO_FONTE, cliponaxis=False)
                fig_ranking.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="Qtd de Chamados", yaxis_title="", margin=dict(r=40))
                st.plotly_chart(fig_ranking, use_container_width=True)
                
            st.divider()
            
            st.subheader("🔍 Raio-X do Cliente")
            st.markdown("Escolha um cliente da lista abaixo para ver exatamente O QUE ele está demandando.")
            cliente_alvo = st.selectbox("Selecione o Cliente:", base_clientes['Cliente'].unique())
            
            dados_alvo = base_clientes[base_clientes['Cliente'] == cliente_alvo]
            
            st.metric(f"Total de tickets abertos por {cliente_alvo}:", len(dados_alvo))
            
            c_alvo1, c_alvo2 = st.columns(2)
            with c_alvo1:
                st.write("Serviços Demandados:")
                agrupado_alvo_prod = dados_alvo.groupby(['Produto', 'Servico']).size().reset_index(name='Qtd')
                fig_alvo = px.pie(agrupado_alvo_prod, values='Qtd', names='Servico', hole=0.4, color_discrete_sequence=CORES_EXTRAS)
                st.plotly_chart(fig_alvo, use_container_width=True)
            with c_alvo2:
                st.write("Últimos Chamados:")
                df_alvo_tabela = dados_alvo[['Número', 'Aberto em', 'Produto', 'Servico', 'Status', 'Responsável']].head(10).copy()
                df_alvo_tabela['Número'] = df_alvo_tabela['Número'].astype(str).str.replace(".0", "", regex=False)
                st.dataframe(df_alvo_tabela, hide_index=True, use_container_width=True)

        else:
            st.info("Nenhum dado de cliente válido para gerar o ranking neste período.")

else:
    st.warning("Nenhum ticket encontrado para as datas selecionadas.")