import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="PolySniper", page_icon="📈", layout="wide")

DATA_API  = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

@st.cache_data(ttl=60)
def fetch(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fmt_usd(val):
    try:
        v = float(val)
        sign = "+" if v >= 0 else ""
        return "{}{:,.2f} USD".format(sign, v)
    except:
        return "N/A"

# 🔥 FIX PRINCIPALE
def get_market_link(p, wallet=None):
    slug = p.get("slug") or p.get("eventSlug")

    if slug:
        return f"https://polymarket.com/event/{slug}"

    condition_id = p.get("conditionId")
    if condition_id:
        data = fetch(GAMMA_API + "/markets", params={"conditionId": condition_id})
        if data and len(data) > 0:
            slug = data[0].get("slug")
            if slug:
                return f"https://polymarket.com/event/{slug}"

    return f"https://polymarket.com/profile/{wallet}" if wallet else None

def get_leaderboard(periodo, categoria, ordina, n):
    return fetch(DATA_API + "/v1/leaderboard",
        params={"timePeriod": periodo, "category": categoria, "orderBy": ordina, "limit": n})

def get_positions(wallet):
    return fetch(DATA_API + "/positions", params={"user": wallet, "sizeThreshold": 0}) or []

def get_activity(wallet, limit=30):
    return fetch(DATA_API + "/activity", params={"user": wallet, "limit": limit}) or []

def get_wallet(name, df):
    row = df[df["userName"] == name]["proxyWallet"].values if "proxyWallet" in df.columns else []
    return row[0] if len(row) > 0 else None

# STATE
if "watchlist" not in st.session_state:
    st.session_state.watchlist = {}

st.title("📈 PolySniper")

# SIDEBAR
periodo = st.sidebar.selectbox("Periodo", ["DAY", "WEEK", "MONTH", "ALL"], index=2)
categoria = st.sidebar.selectbox("Categoria",
    ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "CULTURE", "ECONOMICS", "TECH", "FINANCE"])
ordina = st.sidebar.selectbox("Ordina per", ["PNL", "VOL"])
n_trader = st.sidebar.slider("Numero trader", 5, 50, 20)

# LEADERBOARD
data = get_leaderboard(periodo, categoria, ordina, n_trader)

if not data:
    st.error("Errore caricamento leaderboard")
    st.stop()

df = pd.DataFrame(data)
st.session_state["df"] = df

st.subheader("🏆 Leaderboard")

for _, row in df.iterrows():
    name = row.get("userName")
    wallet = row.get("proxyWallet")
    pnl = float(row.get("pnl", 0))

    col1, col2, col3, col4 = st.columns([1, 3, 2, 2])

    col1.write(f"#{row.get('rank')}")
    col2.markdown(f"[{name}](https://polymarket.com/profile/{wallet})")
    col3.write(fmt_usd(pnl))

    if col4.button("👁 Watch", key=wallet):
        positions = get_positions(wallet)
        ids = set(p.get("conditionId") for p in positions)
        st.session_state.watchlist[wallet] = {"name": name, "ids": ids}

    st.divider()

# WATCHLIST CHECK
if st.session_state.watchlist:
    st.subheader("👀 Watchlist")

    if st.button("Controlla nuove posizioni"):
        for wallet, info in st.session_state.watchlist.items():
            positions = get_positions(wallet)
            current_ids = set(p.get("conditionId") for p in positions)

            new_ids = current_ids - info["ids"]

            for p in positions:
                if p.get("conditionId") in new_ids:
                    link = get_market_link(p, wallet)

                    if not link:
                        continue

                    st.warning(f"{info['name']} ha aperto:")
                    st.markdown(f"""
                    **{p.get("title")}**  
                    Esito: {p.get("outcome")}  
                    Prezzo: {round(float(p.get("curPrice", 0))*100)}%  
                    [Copia trade]({link})
                    """)

            st.session_state.watchlist[wallet]["ids"] = current_ids

# TRADER DETAIL
st.subheader("🕵️ Trader Detail")

names = df["userName"].dropna().tolist()

selected = st.selectbox("Seleziona trader", names)

wallet = get_wallet(selected, df)

if wallet:
    positions = get_positions(wallet)

    for p in positions:
        link = get_market_link(p, wallet)

        if not link:
            continue

        st.markdown(f"""
        **{p.get("title")}**  
        {p.get("outcome")} @ {round(float(p.get("curPrice", 0))*100)}%  
        [Copia trade]({link})
        """)
        st.divider()

# AI TAB (semplificata)
st.subheader("🤖 AI Consiglia")

if st.button("Analizza"):
    candidates = []

    for _, row in df.head(10).iterrows():
        name = row["userName"]
        wallet = row["proxyWallet"]
        pnl = float(row.get("pnl", 0))

        positions = get_positions(wallet)

        for p in positions:
            price = float(p.get("curPrice", 0))
            size = float(p.get("size", 0))

            if price < 0.05 or price > 0.95 or size < 1:
                continue

            link = get_market_link(p, wallet)

            if not link:
                continue

            score = pnl / 1000 + (1 - price) * 50

            candidates.append({
                "score": score,
                "name": name,
                "title": p.get("title"),
                "outcome": p.get("outcome"),
                "price": price,
                "link": link
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    for c in candidates[:10]:
        st.markdown(f"""
        ### {c['title']}
        Trader: {c['name']}  
        Esito: {c['outcome']}  
        Prezzo: {round(c['price']*100)}%  
        Score: {round(c['score'],1)}  

        [Copia trade]({c['link']})
        """)
        st.divider()
