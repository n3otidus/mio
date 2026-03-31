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
    except:
        return None

def fmt_usd(val):
    try:
        v = float(val)
        sign = "+" if v >= 0 else ""
        return "{}{:,.2f} USD".format(sign, v)
    except:
        return "N/A"

# 🔥 FIX DEFINITIVO LINK
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

            market_id = data[0].get("id")
            if market_id:
                return f"https://polymarket.com/market/{market_id}"

    market_id = p.get("marketId") or p.get("id")
    if market_id:
        return f"https://polymarket.com/market/{market_id}"

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
if "alerts" not in st.session_state:
    st.session_state.alerts = []

# SIDEBAR
st.sidebar.header("Filtri")

periodo = st.sidebar.selectbox("Periodo", ["DAY", "WEEK", "MONTH", "ALL"], index=2)
categoria = st.sidebar.selectbox("Categoria",
    ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "CULTURE", "ECONOMICS", "TECH", "FINANCE"])
ordina = st.sidebar.selectbox("Ordina per", ["PNL", "VOL"])
n_trader = st.sidebar.slider("Numero trader", 5, 50, 20)

st.title("📈 PolySniper")

# TABS RIPRISTINATI
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏆 Leaderboard",
    "🕵️ Trader Detail",
    "⚔️ Confronto",
    "🔍 Cerca Mercato",
    "🤖 AI Consiglia"
])

# =========================
# TAB 1 LEADERBOARD
# =========================
with tab1:
    data = get_leaderboard(periodo, categoria, ordina, n_trader)

    if not data:
        st.error("Errore caricamento leaderboard")
        st.stop()

    df = pd.DataFrame(data)
    st.session_state["df"] = df

    for _, row in df.iterrows():
        name = row.get("userName")
        wallet = row.get("proxyWallet")
        pnl = float(row.get("pnl", 0))

        c1, c2, c3, c4 = st.columns([1, 3, 2, 2])

        c1.write(f"#{row.get('rank')}")
        c2.markdown(f"[{name}](https://polymarket.com/profile/{wallet})")
        c3.write(fmt_usd(pnl))

        if c4.button("👁 Watch", key=wallet):
            positions = get_positions(wallet)
            ids = set(p.get("conditionId") for p in positions)
            st.session_state.watchlist[wallet] = {"name": name, "ids": ids}

        st.divider()

# =========================
# TAB 2 DETAIL
# =========================
with tab2:
    df = st.session_state.get("df", pd.DataFrame())
    names = df["userName"].dropna().tolist() if "userName" in df.columns else []

    selected = st.selectbox("Trader", names)

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

# =========================
# TAB 3 CONFRONTO
# =========================
with tab3:
    st.info("Confronto trader attivo")

# =========================
# TAB 4 SEARCH
# =========================
with tab4:
    keyword = st.text_input("Cerca mercato")

    if keyword:
        df = st.session_state.get("df", pd.DataFrame())
        names = df["userName"].tolist()

        for name in names:
            wallet = get_wallet(name, df)
            for p in get_positions(wallet):
                if keyword.lower() in p.get("title", "").lower():
                    link = get_market_link(p, wallet)
                    if not link:
                        continue

                    st.markdown(f"""
                    **{name}**  
                    {p.get("title")}  
                    [Apri]({link})
                    """)
                    st.divider()

# =========================
# TAB 5 AI
# =========================
with tab5:
    if st.button("Analizza"):
        df = st.session_state.get("df", pd.DataFrame())

        results = []

        for _, row in df.head(10).iterrows():
            wallet = row["proxyWallet"]
            pnl = float(row.get("pnl", 0))

            for p in get_positions(wallet):
                price = float(p.get("curPrice", 0))
                size = float(p.get("size", 0))

                if price < 0.05 or price > 0.95 or size < 1:
                    continue

                link = get_market_link(p, wallet)
                if not link:
                    continue

                score = pnl / 1000 + (1 - price) * 50

                results.append((score, p, wallet))

        results.sort(reverse=True)

        for score, p, wallet in results[:10]:
            st.markdown(f"""
            **{p.get("title")}**  
            Score: {round(score,1)}  
            [Copia trade]({link})
            """)
            st.divider()
