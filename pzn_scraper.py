import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="PZN Scraper Tool", page_icon="💊", layout="wide")

# --- AUTHENTICATION LOGIC (SECURE) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    try:
        # Versucht das Passwort aus den Secrets zu holen
        secret_pw = st.secrets["app_password"]
        
        if st.session_state.password_input == secret_pw:
            st.session_state.authenticated = True
            del st.session_state.password_input
        else:
            st.error("❌ Wrong password")
    except FileNotFoundError:
        # Fallback für lokales Testen ohne Secrets-Datei
        if st.session_state.password_input == "Secret2026":
            st.session_state.authenticated = True
        else:
            st.error("⚠️ Secrets not configured & Wrong fallback password.")
    except KeyError:
        st.error("⚠️ Key Error. Make sure 'app_password' is set in Streamlit Secrets.")

# Show Login if not authenticated
if not st.session_state.authenticated:
    st.title("🔒 Login Required")
    st.text_input("Please enter the password:", type="password", key="password_input", on_change=check_password)
    st.stop()

# =========================================================
#  ⬇️ MAIN TOOL ⬇️
# =========================================================

st.title("💊 PZN Pharmacy Scraper")
st.markdown("Paste your list of PZNs below.")

default_pzns = "40554, 3161577\n18661452"
col1, col2 = st.columns([1, 2])

with col1:
    pzn_input = st.text_area("Enter PZNs (one per line or comma-separated):", value=default_pzns, height=300)
    start_button = st.button("🚀 Fetch Data", type="primary", use_container_width=True)

if start_button:
    # 1. Input Normalization
    normalized_input = pzn_input.replace(',', '\n')
    pzns = [line.strip() for line in normalized_input.split('\n') if line.strip()]
    
    if not pzns:
        st.error("Please enter at least one PZN.")
    else:
        with col2:
            st.info(f"Processing {len(pzns)} products...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        results = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for i, pzn in enumerate(pzns):
            url = f"https://www.shop-apotheke.com/arzneimittel/{pzn}"
            status_text.text(f"Fetching PZN {pzn} ({i+1}/{len(pzns)})...")
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # --- 1. NAME (BEREINIGT) ---
                    name_tag = soup.find("h1")
                    name = name_tag.text.strip() if name_tag else "Not found"
                    
                    # HIER IST DIE NEUE LOGIK: Entferne alles ab " - Jetzt"
                    if " - Jetzt" in name:
                        name = name.split(" - Jetzt")[0].strip()
                    
                    # --- 2. BRAND ---
                    brand_tag = soup.select_one(".font-normal a")
                    brand = brand_tag.text.strip() if brand_tag else "n.a."
                    
                    # --- 3. MENGE (BEREINIGT) ---
                    menge_tag = soup.select_one("div.leading-l")
                    menge = menge_tag.text.replace("Packungsgröße:", "").strip() if menge_tag else "n.a."
                    
                    results.append({"PZN": pzn, "Name": name, "Brand": brand, "Quantity": menge, "Link": url})
                elif response.status_code == 404:
                    results.append({"PZN": pzn, "Name": "❌ Not found", "Brand": "-", "Quantity": "-", "Link": url})
                else:
                    results.append({"PZN": pzn, "Name": f"Error {response.status_code}", "Brand": "-", "Quantity": "-", "Link": url})
            except Exception as e:
                results.append({"PZN": pzn, "Name": "Error", "Brand": "-", "Quantity": str(e), "Link": url})
            
            progress_bar.progress((i + 1) / len(pzns))
            time.sleep(random.uniform(0.5, 1.5)) 

        status_text.text("✅ Finished!")
        df = pd.DataFrame(results)
        
        # Spalten sortieren
        cols = ["PZN", "Name", "Brand", "Quantity", "Link"]
        final_cols = [c for c in cols if c in df.columns]
        df = df[final_cols]
        
        st.divider()
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode('utf-8-sig')
        st.download_button(label="💾 Download CSV", data=csv, file_name="pzn_export_clean.csv", mime="text/csv")
