import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="PZN Scraper Tool", page_icon="💊", layout="wide")

# --- SECURITY / PASSWORD PROTECTION ---
# Change "Secret2026" to whatever password you want to give your colleague
password = st.sidebar.text_input("🔒 Enter Password:", type="password")

if password != "yadayada26":
    st.info("Please enter the correct password in the sidebar to access the tool.")
    st.stop()  # Stops the script here until the correct password is entered

# --- MAIN APP ---
st.title("💊 PZN Pharmacy Scraper")
st.markdown("Paste your list of PZNs below. The tool automatically fetches Name, Brand, and Quantity from Shop-Apotheke.")

# --- INPUT ---
# Example input (mixed format)
default_pzns = "40554, 3161577\n18661452"

col1, col2 = st.columns([1, 2])

with col1:
    pzn_input = st.text_area("Enter PZNs (one per line or comma-separated):", value=default_pzns, height=300)
    start_button = st.button("🚀 Fetch Data", type="primary", use_container_width=True)

# --- LOGIC ---
if start_button:
    # 1. Normalize input: Replace commas with newlines
    normalized_input = pzn_input.replace(',', '\n')
    
    # 2. Clean list: Remove whitespace and empty lines
    pzns = [line.strip() for line in normalized_input.split('\n') if line.strip()]
    
    if not pzns:
        st.error("Please enter at least one PZN.")
    else:
        with col2:
            st.info(f"Processing {len(pzns)} products...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        results = []
        
        # User-Agent to mimic a real browser
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
                    
                    # 1. Name
                    name_tag = soup.find("h1")
                    name = name_tag.text.strip() if name_tag else "Not found"
                    
                    # 2. Brand
                    brand_tag = soup.select_one(".font-normal a")
                    brand = brand_tag.text.strip() if brand_tag else "n.a."
                    
                    # 3. Quantity (Cleaned)
                    menge_tag = soup.select_one("div.leading-l")
                    if menge_tag:
                        # We remove the German text "Packungsgröße:" to keep it clean
                        menge = menge_tag.text.replace("Packungsgröße:", "").strip()
                    else:
                        menge = "n.a."
                    
                    results.append({
                        "PZN": pzn,
                        "Name": name,
                        "Brand": brand,
                        "Quantity": menge,
                        "Link": url
                    })
                elif response.status_code == 404:
                    results.append({"PZN": pzn, "Name": "❌ Not found", "Brand": "-", "Quantity": "-", "Link": url})
                else:
                    results.append({"PZN": pzn, "Name": f"Error {response.status_code}", "Brand": "-", "Quantity": "-", "Link": url})

            except Exception as e:
                results.append({"PZN": pzn, "Name": "Error", "Brand": "-", "Quantity": str(e), "Link": url})
            
            # Update Progress
            progress_bar.progress((i + 1) / len(pzns))
            # Human-like delay
            time.sleep(random.uniform(0.5, 1.5)) 

        status_text.text("✅ Finished!")
        
        # --- RESULTS & DOWNLOAD ---
        df = pd.DataFrame(results)
        
        # Reorder columns
        cols = ["PZN", "Name", "Brand", "Quantity", "Link"]
        final_cols = [c for c in cols if c in df.columns]
        df = df[final_cols]
        
        st.divider()
        st.subheader("Results")
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode('utf-8-sig')
        st.download_button(
            label="💾 Download CSV",
            data=csv,
            file_name="pzn_export_final.csv",
            mime="text/csv",
        )
