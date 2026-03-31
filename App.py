import streamlit as st
import requests
import pandas as pd
import json

st.set_page_config(page_title='PolySniper', page_icon='📈', layout='wide')

st.markdown('''
<style>
.main { background-color: #f5f7f9; }
</style>
''', unsafe_allow_html=True)

DATA_API  = 'https://data-api.polymarket.com'
GAMMA_API = 'https://gamma-api.polymarket.com'

@st.cache_data(ttl=300)
def fetch(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

st.title('📈 PolySniper')
st.caption('Analisi in tempo reale dei migliori trader su Polymarket')

st.sidebar.header('Filtri')

periodo = st.sidebar.selectbox(
    'Periodo',
    ['DAY', 'WEEK', 'MONTH', 'ALL'],
    index=2,
    format_func=lambda x: {'DAY': 'Oggi', 'WEEK': 'Settimana', 'MONTH': 'Mese', 'ALL': 'Sempre'}[x]
)

categoria = st.sidebar.selectbox(
    'Categoria',
    ['OVERALL', 'POLITICS', 'SPORTS', 'CRYPTO', 'CULTURE', 'ECONOMICS', 'TECH', 'FINANCE'],
    index=0
)

ordina = st.sidebar.selectbox(
    'Ordina per',
    ['PNL', 'VOL'],
    format_func=lambda x: 'Profitto (PnL)' if x == 'PNL' else 'Volume'
)

n_trader = st.sidebar.slider('Numero trader', 5, 50, 20)
st.sidebar.divider()
st.sidebar.info('Dati: API pubblica Polymarket')

st.subheader('🏆 Classifica Trader')

data = fetch(
    DATA_API + '/v1/leaderboard',
    params={'timePeriod': periodo, 'category': categoria, 'orderBy': ordina, 'limit': n_trader}
)

if not data:
    st.error('Impossibile caricare la leaderboard. Riprova tra poco.')
    st.stop()

df_raw = pd.DataFrame(data)
cols = [c for c in ['rank', 'userName', 'pnl', 'vol', 'xUsername', 'verifiedBadge', 'proxyWallet'] if c in df_raw.columns]
df = df_raw[cols].copy()

rename_map = {'rank': 'Rank', 'userName': 'Trader', 'pnl': 'PnL USD', 'vol': 'Volume USD', 'xUsername': 'Twitter', 'verifiedBadge': 'Verificato', 'proxyWallet': 'Wallet'}
df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

if 'PnL USD' in df.columns:
    df['PnL USD'] = df['PnL USD'].apply(lambda x: '${:,.2f}'.format(float(x)) if pd.notna(x) else 'N/A')
if 'Volume USD' in df.columns:
    df['Volume USD'] = df['Volume USD'].apply(lambda x: '${:,.0f}'.format(float(x)) if pd.notna(x) else 'N/A')

st.dataframe(df.drop(columns=['Wallet'], errors='ignore'), use_container_width=True, hide_index=True)

st.divider()
st.subheader('🕵️ Analizza un Portafoglio')

nomi_trader = df['Trader'].dropna().tolist() if 'Trader' in df.columns else []
if not nomi_trader:
    st.warning('Nessun trader disponibile.')
    st.stop()

nome_col   = 'userName'    if 'userName'    in df_raw.columns else None
wallet_col = 'proxyWallet' if 'proxyWallet' in df_raw.columns else None

selected_name = st.selectbox('Scegli un trader:', nomi_trader)

if nome_col and wallet_col:
    wallet_row = df_raw[df_raw[nome_col] == selected_name][wallet_col].values
    wallet = wallet_row[0] if len(wallet_row) > 0 else None
else:
    wallet = None

col1, col2 = st.columns(2)

with col1:
    if st.button('Posizioni aperte', use_container_width=True):
        if not wallet:
            st.error('Wallet non disponibile.')
        else:
            positions = fetch(DATA_API + '/positions', params={'user': wallet, 'sizeThreshold': 0})
            if positions:
                st.success('Trovate {} posizioni'.format(len(positions)))
                rows = []
                for p in positions:
                    rows.append({
                        'Mercato': p.get('title', 'N/A'),
                        'Esito': p.get('outcome', 'N/A'),
                        'Quantita': round(float(p.get('size', 0)), 2),
                        'Valore': '${:,.2f}'.format(float(p.get('currentValue', p.get('curValue', 0)))),
                        'PnL': '${:,.2f}'.format(float(p.get('cashPnl', 0))),
                        'Prezzo medio': '${:.3f}'.format(float(p.get('avgPrice', 0))),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info('Nessuna posizione aperta trovata.')

with col2:
    if st.button('Attivita recente', use_container_width=True):
        if not wallet:
            st.error('Wallet non disponibile.')
        else:
            activity = fetch(DATA_API + '/activity', params={'user': wallet, 'limit': 20})
            if activity:
                rows = []
                for a in activity:
                    ts = a.get('timestamp', 0)
                    data_str = pd.to_datetime(ts, unit='s').strftime('%d/%m/%Y %H:%M') if ts else 'N/A'
                    rows.append({
                        'Data': data_str,
                        'Tipo': a.get('type', a.get('side', 'N/A')),
                        'Mercato': str(a.get('title', 'N/A'))[:60],
                        'Esito': a.get('outcome', 'N/A'),
                        'Quantita': round(float(a.get('size', 0)), 2),
                        'Prezzo': '${:.3f}'.format(float(a.get('price', 0))),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info('Nessuna attivita recente trovata.')

st.divider()
st.subheader('🔥 Mercati con piu volume ora')

markets = fetch(GAMMA_API + '/markets', params={'active': 'true', 'closed': 'false', 'limit': 10, 'order': 'volume24hr', 'ascending': 'false'})

if markets:
    rows = []
    for m in markets:
        try:
            prices = m.get('outcomePrices', '[]')
            if isinstance(prices, str):
                prices = json.loads(prices)
            yes_price = float(prices[0]) if prices else 0.0
        except Exception:
            yes_price = 0.0
        rows.append({
            'Mercato': str(m.get('question', m.get('title', 'N/A')))[:70],
            'YES': '{:.1f}%'.format(yes_price * 100),
            'Volume 24h': '${:,.0f}'.format(float(m.get('volume24hr', m.get('volumeNum', 0)))),
            'Liquidita': '${:,.0f}'.format(float(m.get('liquidity', m.get('liquidityNum', 0)))),
            'Categoria': m.get('category', 'N/A'),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.warning('Impossibile caricare i mercati trending.')
