# Arrotondamento profitto
df_clean['Profitto ($)'\] = df\_clean\['Profitto ($)'].apply(lambda x: f"${x:,.2f}")

st.dataframe(df_clean, use_container_width=True, hide_index=True)

# --- SEZIONE 2: ANALISI DETTAGLIATA ---
st.divider()
st.subheader("🕵️ Spia un Portafoglio")

selected_name = st.selectbox("Scegli un trader dalla lista:", df_clean['Trader'])
wallet = df_clean[df_clean['Trader'] == selected_name]['Indirizzo Wallet'].values[0]

if st.button(f"Vedi cosa possiede {selected_name}"):
    pos_url = f"https://data-api.polymarket.com/positions?user={wallet}"
    positions = fetch_data(pos_url)
    
    if positions:
        st.success(f"Trovate {len(positions)} posizioni attive")
        
        # Creazione lista posizioni
        pos_data = []
        for p in positions:
            pos_data.append({
                "Asset": p.get('asset', 'N/A'),
                "Quantità": p.get('size', 0),
                "Valore Attuale ($)": f"${p.get('curValue', 0):,.2f}",
                "Prezzo Medio": f"${p.get('avgPrice', 0):.2f}"
            })
        
        st.table(pd.DataFrame(pos_data))
    else:
        st.info("Questo trader non ha posizioni aperte al momento.")
