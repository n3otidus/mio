import streamlit as st
import requests
import pandas as pd
import json

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
    except Exception:
        return "N/A"

def get_leaderboard(periodo, categoria, ordina, n):
    return fetch(DATA_API + "/v1/leaderboard",
        params={"timePeriod": periodo, "category": categoria, "orderBy": ordina, "limit": n})

def get_positions(wallet):
    return fetch(DATA_API + "/positions", params={"user": wallet, "sizeThreshold": 0}) or []

def get_activity(wallet, limit=30):
    return fetch(DATA_API + "/activity", params={"user": wallet, "limit": limit}) or []

def compute_score(wallet):
    activity = get_activity(wallet, limit=50)
    if not activity:
        return None
    trades = [a for a in activity if a.get("type", "").upper() in ("BUY", "SELL")
              or a.get("side", "").upper() in ("BUY", "SELL")]
    total = len(trades)
    if total == 0:
        return None
    wins = sum(1 for a in trades if float(a.get("cashPnl", a.get("pnl", 0)) or 0) > 0)
    win_rate = wins / total
    total_pnl = sum(float(a.get("cashPnl", a.get("pnl", 0)) or 0) for a in trades)
    avg_pnl = total_pnl / total
    score = round((win_rate * 50) + min(50, max(0, avg_pnl / 100)), 1)
    return {"win_rate": win_rate, "total_trades": total, "avg_pnl": avg_pnl, "score": score}

def get_wallet(name, df):
    row = df[df["userName"] == name]["proxyWallet"].values if "proxyWallet" in df.columns else []
    return row[0] if len(row) > 0 else None

if "watchlist" not in st.session_state:
    st.session_state.watchlist = {}
if "alerts" not in st.session_state:
    st.session_state.alerts = []

st.sidebar.header("Filtri")

periodo = st.sidebar.selectbox("Periodo", ["DAY", "WEEK", "MONTH", "ALL"], index=2,
    format_func=lambda x: {"DAY": "Oggi", "WEEK": "Settimana", "MONTH": "Mese", "ALL": "Sempre"}[x])

categoria = st.sidebar.selectbox("Categoria",
    ["OVERALL", "POLITICS", "SPORTS", "CRYPTO", "CULTURE", "ECONOMICS", "TECH", "FINANCE"])

ordina = st.sidebar.selectbox("Ordina per", ["PNL", "VOL"],
    format_func=lambda x: "Profitto (PnL)" if x == "PNL" else "Volume")

n_trader = st.sidebar.slider("Numero trader", 5, 50, 20)
st.sidebar.divider()

if st.session_state.watchlist:
    st.sidebar.subheader("Watchlist attiva")
    for w, info in list(st.session_state.watchlist.items()):
        ca, cb = st.sidebar.columns([3, 1])
        ca.write(info["name"])
        if cb.button("X", key="rm_" + w[:8]):
            del st.session_state.watchlist[w]
            st.rerun()

st.sidebar.divider()
st.sidebar.info("Dati: API pubblica Polymarket")

st.title("📈 PolySniper")
st.caption("Copia i migliori trader su Polymarket")

if st.session_state.watchlist:
    if st.button("Controlla nuove posizioni (watchlist)", use_container_width=True):
        new_alerts = []
        for wallet, info in st.session_state.watchlist.items():
            positions = get_positions(wallet)
            current_ids = set(p.get("asset", p.get("conditionId", "")) for p in positions)
            prev_ids = info.get("last_positions", set())
            for pid in (current_ids - prev_ids):
                for p in positions:
                    if p.get("asset", p.get("conditionId", "")) == pid:
                        slug = p.get("slug", p.get("eventSlug", ""))
                        new_alerts.append({
                            "trader": info["name"],
                            "mercato": p.get("title", "N/A"),
                            "esito": p.get("outcome", "N/A"),
                            "prezzo": float(p.get("curPrice", 0)) * 100,
                            "link": "https://polymarket.com/event/" + slug if slug else "https://polymarket.com/profile/" + wallet,
                        })
            st.session_state.watchlist[wallet]["last_positions"] = current_ids
        st.session_state.alerts = new_alerts
        if not new_alerts:
            st.success("Nessuna nuova posizione trovata.")

if st.session_state.alerts:
    st.error("Nuove posizioni rilevate!")
    for a in st.session_state.alerts:
        st.markdown("**{}** ha aperto: **{}** ({}) @ {:.0f}% — [Apri su Polymarket]({})".format(
            a["trader"], a["mercato"], a["esito"], a["prezzo"], a["link"]))
    st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["🏆 Leaderboard", "🕵️ Trader Detail", "⚔️ Confronto", "🔍 Cerca Mercato"])

with tab1:
    data = get_leaderboard(periodo, categoria, ordina, n_trader)
    if not data:
        st.error("Impossibile caricare la leaderboard.")
        st.stop()

    df_raw = pd.DataFrame(data)
    st.session_state["df_raw"] = df_raw

    for _, row in df_raw.iterrows():
        trader_name = row.get("userName", "N/A")
        wallet      = row.get("proxyWallet", "")
        pnl_val     = float(row.get("pnl", 0) or 0)
        vol_val     = float(row.get("vol", 0) or 0)
        pnl_color   = "green" if pnl_val >= 0 else "red"
        poly_url    = "https://polymarket.com/profile/" + wallet if wallet else "#"

        c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 2, 2])
        c1.write("**#{}**".format(row.get("rank", "-")))
        c2.markdown("[**{}**]({})".format(trader_name, poly_url))
        c3.markdown("<span style=\"color:{}\">**{}**</span>".format(pnl_color, fmt_usd(pnl_val)), unsafe_allow_html=True)
        c4.write("Vol: " + fmt_usd(vol_val))

        in_watch = wallet in st.session_state.watchlist
        btn_label = "Rimuovi Watch" if in_watch else "+ Watch"
        if c5.button(btn_label, key="w_" + str(wallet)[:10]):
            if in_watch:
                del st.session_state.watchlist[wallet]
            else:
                positions = get_positions(wallet)
                current_ids = set(p.get("asset", p.get("conditionId", "")) for p in positions)
                st.session_state.watchlist[wallet] = {"name": trader_name, "last_positions": current_ids}
            st.rerun()

        st.divider()

with tab2:
    df_raw2 = st.session_state.get("df_raw", pd.DataFrame())
    nomi2 = df_raw2["userName"].dropna().tolist() if "userName" in df_raw2.columns else []

    if not nomi2:
        st.info("Carica prima la leaderboard.")
    else:
        selected_name = st.selectbox("Scegli trader:", nomi2, key="sel2")
        wallet2 = get_wallet(selected_name, df_raw2)

        if wallet2:
            poly_url2 = "https://polymarket.com/profile/" + wallet2
            st.markdown("### {} — [Apri profilo Polymarket]({})".format(selected_name, poly_url2))

            with st.spinner("Calcolo score..."):
                score_data = compute_score(wallet2)

            if score_data:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Score affidabilita", "{}/100".format(score_data["score"]))
                m2.metric("Win Rate", "{:.1f}%".format(score_data["win_rate"] * 100))
                m3.metric("Trade analizzati", score_data["total_trades"])
                m4.metric("PnL medio per trade", fmt_usd(score_data["avg_pnl"]))

            st.divider()
            st.subheader("Posizioni aperte")

            positions2 = get_positions(wallet2)
            if positions2:
                for p in positions2:
                    slug = p.get("slug", p.get("eventSlug", ""))
                    link = "https://polymarket.com/event/" + slug if slug else poly_url2
                    cur_price = float(p.get("curPrice", 0)) * 100
                    pnl_p = float(p.get("cashPnl", 0))
                    pnl_col = "green" if pnl_p >= 0 else "red"
                    ca, cb, cc = st.columns([5, 2, 1])
                    ca.markdown("**{}** - {} @ **{:.0f}%**".format(
                        p.get("title", "N/A")[:55], p.get("outcome", "N/A"), cur_price))
                    cb.markdown("<span style=\"color:{}\">PnL: {}</span>".format(
                        pnl_col, fmt_usd(pnl_p)), unsafe_allow_html=True)
                    cc.markdown("[Copia]({})".format(link))
                    st.markdown("---")
            else:
                st.info("Nessuna posizione aperta.")

            st.divider()
            st.subheader("Attivita recente")
            activity2 = get_activity(wallet2, 20)
            if activity2:
                rows_a = []
                for a in activity2:
                    ts = a.get("timestamp", 0)
                    data_str = pd.to_datetime(ts, unit="s").strftime("%d/%m %H:%M") if ts else "N/A"
                    rows_a.append({
                        "Data": data_str,
                        "Tipo": a.get("type", a.get("side", "N/A")),
                        "Mercato": str(a.get("title", "N/A"))[:55],
                        "Esito": a.get("outcome", "N/A"),
                        "Quantita": round(float(a.get("size", 0)), 2),
                        "Prezzo": "{:.0f}%".format(float(a.get("price", 0)) * 100),
                    })
                st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)
            else:
                st.info("Nessuna attivita recente.")

with tab3:
    df_raw3 = st.session_state.get("df_raw", pd.DataFrame())
    nomi3 = df_raw3["userName"].dropna().tolist() if "userName" in df_raw3.columns else []

    if not nomi3:
        st.info("Carica prima la leaderboard.")
    else:
        ca3, cb3 = st.columns(2)
        trader_a = ca3.selectbox("Trader A", nomi3, index=0, key="cmp_a")
        trader_b = cb3.selectbox("Trader B", nomi3, index=min(1, len(nomi3) - 1), key="cmp_b")

        if st.button("Confronta", use_container_width=True):
            col_a, col_b = st.columns(2)
            for col, name in [(col_a, trader_a), (col_b, trader_b)]:
                with col:
                    wallet3 = get_wallet(name, df_raw3)
                    st.markdown("### {}".format(name))
                    if not wallet3:
                        st.error("Wallet non trovato.")
                        continue
                    poly_url3 = "https://polymarket.com/profile/" + wallet3
                    st.markdown("[Profilo Polymarket]({})".format(poly_url3))
                    pnl3 = df_raw3[df_raw3["userName"] == name]["pnl"].values if "pnl" in df_raw3.columns else [0]
                    vol3 = df_raw3[df_raw3["userName"] == name]["vol"].values if "vol" in df_raw3.columns else [0]
                    st.metric("PnL", fmt_usd(pnl3[0] if len(pnl3) > 0 else 0))
                    st.metric("Volume", fmt_usd(vol3[0] if len(vol3) > 0 else 0))
                    sc3 = compute_score(wallet3)
                    if sc3:
                        st.metric("Score", "{}/100".format(sc3["score"]))
                        st.metric("Win Rate", "{:.1f}%".format(sc3["win_rate"] * 100))
                        st.metric("Trade analizzati", sc3["total_trades"])
                    st.markdown("**Posizioni aperte:**")
                    pos3 = get_positions(wallet3)
                    if pos3:
                        for p in pos3[:8]:
                            slug = p.get("slug", p.get("eventSlug", ""))
                            link = "https://polymarket.com/event/" + slug if slug else poly_url3
                            st.markdown("- [{}]({}) - **{}** @ {:.0f}%".format(
                                str(p.get("title", "N/A"))[:40], link,
                                p.get("outcome", "N/A"), float(p.get("curPrice", 0)) * 100))
                    else:
                        st.info("Nessuna posizione aperta.")

with tab4:
    st.markdown("Trova quali top trader hanno una posizione aperta su un certo mercato.")
    keyword = st.text_input("Cerca mercato (es: Trump, Bitcoin, election...)")

    if keyword:
        df_raw4 = st.session_state.get("df_raw", pd.DataFrame())
        nomi4 = df_raw4["userName"].dropna().tolist() if "userName" in df_raw4.columns else []

        if not nomi4:
            st.info("Carica prima la leaderboard.")
        else:
            with st.spinner("Scansione in corso..."):
                risultati = []
                progress = st.progress(0)
                for i, name in enumerate(nomi4):
                    w4 = get_wallet(name, df_raw4)
                    if not w4:
                        continue
                    for p in get_positions(w4):
                        title = p.get("title", "")
                        if keyword.lower() in title.lower():
                            slug = p.get("slug", p.get("eventSlug", ""))
                            link = "https://polymarket.com/event/" + slug if slug else "https://polymarket.com/profile/" + w4
                            risultati.append({
                                "Trader": name,
                                "Mercato": title,
                                "Esito": p.get("outcome", "N/A"),
                                "Prezzo": "{:.0f}%".format(float(p.get("curPrice", 0)) * 100),
                                "Valore": fmt_usd(p.get("currentValue", p.get("curValue", 0))),
                                "PnL": fmt_usd(p.get("cashPnl", 0)),
                                "Link": link,
                            })
                    progress.progress((i + 1) / len(nomi4))
                progress.empty()

            if risultati:
                st.success("Trovati {} trader con posizioni su \"{}\"".format(len(risultati), keyword))
                df_ris = pd.DataFrame(risultati)
                st.dataframe(df_ris.drop(columns=["Link"]), use_container_width=True, hide_index=True)
                st.subheader("Vai al mercato per copiare")
                for r in risultati:
                    ca4, cb4 = st.columns([5, 1])
                    ca4.write("**{}** - {} ({}) @ {}".format(
                        r["Trader"], r["Mercato"][:50], r["Esito"], r["Prezzo"]))
                    cb4.markdown("[Copia]({})".format(r["Link"]))
            else:
                st.warning("Nessun trader in classifica ha posizioni su \"{}\".".format(keyword))
