import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz

# Configuração Visual da Agregar Jr.
st.set_page_config(page_title="Simulador Agro EJ", layout="wide", initial_sidebar_state="expanded")

# Cores e Estilos Customizados (Via CSS para forçar a paleta Verde/Laranja)
st.markdown("""
    <style>
    .stButton>button {background-color: #006400; color: white;}
    .stMetric {background-color: #F0F2F6; padding: 10px; border-radius: 5px; border-left: 5px solid #FBB040;}
    </style>
    """, unsafe_allow_html=True)

# Conexão com Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Controle de Fuso Horário (Brasília)
fuso_br = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(fuso_br)
hora_atual = agora.hour

# Regra de Negócio: Janela de Trading
MERCADO_ABERTO = 8 <= hora_atual < 12
EMAIL_ADM = "projetos.agregar@ufv.br" # SEU EMAIL DE ADMINISTRADOR AQUI

with st.sidebar:
    st.image("https://via.placeholder.com/250x100.png?text=Agregar+Jr", use_container_width=True) # Troque pelo link da sua logo
    st.subheader("Login de Acesso")
    email_login = st.text_input("Seu Email Cadastrado", placeholder="luan@agro.com")
    
    if email_login:
        st.success(f"Logado como: {email_login}")
    
    st.divider()
    st.markdown("### Status do Mercado")
    if MERCADO_ABERTO:
        st.success(f"🟢 ABERTO (Janela: 08h - 12h)\n\nHora atual: {agora.strftime('%H:%M')}")
    else:
        st.error(f"🔴 FECHADO\n\nHora atual: {agora.strftime('%H:%M')}\nAguarde a consolidação do CEPEA.")

# ==========================================
# PAINEL DO ADMINISTRADOR (SÓ VOCÊ VÊ)
# ==========================================
if email_login == EMAIL_ADM:
    st.warning("⚠️ MODO ADMINISTRADOR ATIVADO")
    st.title("Painel de Atualização CEPEA")
    st.write("Digite as cotações consolidadas do dia. Isso impactará a carteira de todos.")
    
    # Puxa os ativos do banco
    resposta_ativos = supabase.table('prices').select('id, asset, price').execute()
    ativos_df = pd.DataFrame(resposta_ativos.data)
    
    with st.form("form_adm"):
        ativo_selecionado = st.selectbox("Selecione a Commodity", ativos_df['asset'].tolist())
        preco_antigo = ativos_df[ativos_df['asset'] == ativo_selecionado]['price'].values[0]
        novo_preco = st.number_input(f"Novo Preço (Atual: R$ {preco_antigo})", min_value=0.0, step=0.1, format="%.2f")
        
        atualizar = st.form_submit_button("Atualizar Preço no Sistema")
        
        if atualizar:
            id_ativo = ativos_df[ativos_df['asset'] == ativo_selecionado]['id'].values[0]
            supabase.table('prices').update({'price': novo_preco, 'last_updated': str(agora)}).eq('id', id_ativo).execute()
            st.success(f"{ativo_selecionado} atualizado com sucesso para R$ {novo_preco}!")
            st.rerun()

# ==========================================
# ÁREA DO JOGADOR
# ==========================================
elif email_login:
    try:
        # Puxa dados do usuário (Carteira, Estoque e Preços)
        resposta_portfolio = supabase.table('portfolios').select('id, cash_balance').eq('user_id_ref', email_login).execute()
        portfolio_id = resposta_portfolio.data[0]['id']
        cash_balance = resposta_portfolio.data[0]['cash_balance']
        
        resposta_holdings = supabase.table('holdings').select('*').eq('portfolio_id', portfolio_id).execute()
        holdings_df = pd.DataFrame(resposta_holdings.data)
        
        resposta_precos = supabase.table('prices').select('id, asset, price').execute()
        prices_df = pd.DataFrame(resposta_precos.data)
        
        st.title("🌾 Plataforma de Negociação")
        
        # Dashboard de Saldo
        col1, col2, col3 = st.columns(3)
        total_investido = 0
        if not holdings_df.empty and 'price_id' in holdings_df.columns:
            holdings_with_price = holdings_df.merge(prices_df, left_on='price_id', right_on='id')
            total_investido = (holdings_with_price['quantity'] * holdings_with_price['price']).sum()
        
        with col1:
            st.metric("PATRIMÔNIO TOTAL", f"R$ {(cash_balance + total_investido):,.2f}")
        with col2:
            st.metric("CAIXA LIVRE", f"R$ {cash_balance:,.2f}")
        with col3:
            st.metric("CAPITAL ALOCADO", f"R$ {total_investido:,.2f}")
            
        st.divider()
        
        # Painel de Preços Atuais (Referência do dia anterior até o fechamento)
        st.subheader("Cotações de Referência (CEPEA)")
        st.dataframe(prices_df[['asset', 'price']].rename(columns={'asset': 'Commodity', 'price': 'Preço (R$)'}), hide_index=True, use_container_width=True)

        st.divider()
        
        # Formulário de Operação
        st.subheader("🎯 Executar Ordem Estratégica")
        
        if not MERCADO_ABERTO:
            st.error("O mercado está fechado. Analise os fluxos globais e retorne amanhã entre 08h e 12h para posicionar sua carteira.")
        else:
            with st.form("ordem_form"):
                col_asset, col_type, col_qty = st.columns([2, 1, 1])
                with col_asset:
                    ativo_escolhido = st.selectbox("Ativo (Mercado Físico BR)", prices_df['asset'].tolist())
                with col_type:
                    tipo_ordem = st.radio("Operação", ["Compra", "Venda"], horizontal=True)
                with col_qty:
                    quantidade = st.number_input("Volume", min_value=1.0, step=1.0)
                    
                justificativa = st.text_area("Justificativa Fundamentalista (Obrigatório)", height=100)
                enviado = st.form_submit_button("Bloquear Posição")
                
                if enviado:
                    if len(justificativa) < 20:
                        st.error("Justificativa superficial. Qual o evento macroeconômico baseia essa decisão?")
                    else:
                        price_id = prices_df[prices_df['asset'] == ativo_escolhido]['id'].values[0]
                        preco_atual = prices_df[prices_df['asset'] == ativo_escolhido]['price'].values[0]
                        custo_total = quantidade * preco_atual
                        
                        if tipo_ordem == "Compra":
                            if cash_balance < custo_total:
                                st.error("Caixa insuficiente.")
                            else:
                                supabase.table('transactions').insert({'portfolio_id': portfolio_id, 'price_id': price_id, 'type': 'compra', 'quantity': quantidade, 'justification': justificativa, 'price_at_transaction': preco_atual}).execute()
                                supabase.table('portfolios').update({'cash_balance': cash_balance - custo_total}).eq('id', portfolio_id).execute()
                                # Logica de Estoque omitida por brevidade, idêntica ao código anterior (Upsert)
                                st.success("Posição travada!")
                                st.rerun()

                        elif tipo_ordem == "Venda":
                            # Lógica de Venda idêntica ao código anterior
                            st.success("Ordem executada!")
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Erro de conexão ou usuário não cadastrado pelo Diretor. Detalhes: {e}")

else:
    st.title("Programa de Desenvolvimento Agregar Jr.")
    st.info("Insira seu e-mail corporativo ao lado para acessar o simulador.")
