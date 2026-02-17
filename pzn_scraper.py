import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# --- KONFIGURATION ---
st.set_page_config(page_title="PZN Scraper", page_icon="💊", layout="wide")

st.title("💊 PZN Apotheken Scraper")
st.markdown("Kopiere deine PZNs in das Feld. Erlaubt sind Listen **untereinander** oder mit **Komma** getrennt.")

# --- EINGABE ---
# Beispiel: Mix aus Zeilenumbruch und Komma
default_pzns = "40554, 3161577\n18661452"

col1, col2 = st.columns([1, 2])

with col1:
    pzn_input = st.text_area("PZNs eingeben:", value=default_pzns, height=300)
    start_button = st.button("🚀 Daten abrufen", type="primary", use_container_width=True)

# --- LOGIK ---
if start_button:
    # 1. Schritt: Wir machen die Eingabe flexibel.
    # Wir ersetzen alle Kommas durch Zeilenumbrüche.
    normalized_input = pzn_input.replace(',', '\n')
    
    # 2. Schritt: Wir zerlegen den Text anhand der Zeilenumbrüche und säubern Leerzeichen.
    pzns = [line.strip() for line in normalized_input.split('\n') if line.strip()]
    
    if not pzns:
        st.error("Bitte gib mindestens eine PZN ein.")
    else:
        with col2:
            st.info(f"Bearbeite {len(pzns)} Produkte...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        results = []
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for i, pzn in enumerate(pzns):
            # URL bauen
            url = f"https://www.shop-apotheke.com/arzneimittel/{pzn}"
            status_text.text(f"Lade PZN {pzn} ({i+1}/{len(pzns)})...")
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # 1. Name
                    name_tag = soup.find("h1")
                    name = name_tag.text.strip() if name_tag else "Nicht gefunden"
                    
                    # 2. Brand
                    brand_tag = soup.select_one(".font-normal a")
                    brand = brand_tag.text.strip() if brand_tag else "n.a."
                    
                    # 3. Menge (bereinigt)
                    menge_tag = soup.select_one("div.leading-l")
                    if menge_tag:
                        # Entfernt "Packungsgröße:" und Leerzeichen
                        menge = menge_tag.text.replace("Packungsgröße:", "").strip()
                    else:
                        menge = "n.a."
                    
                    results.append({
                        "PZN": pzn,
                        "Name": name,
                        "Brand": brand,
                        "Menge": menge,
                        "Link": url
                    })
                elif response.status_code == 404:
                    results.append({"PZN": pzn, "Name": "❌ Nicht gefunden", "Brand": "-", "Menge": "-", "Link": url})
                else:
                    results.append({"PZN": pzn, "Name": f"Fehler {response.status_code}", "Brand": "-", "Menge": "-", "Link": url})

            except Exception as e:
                results.append({"PZN": pzn, "Name": "Fehler", "Brand": "-", "Menge": str(e), "Link": url})
            
            # Fortschritt
            progress_bar.progress((i + 1) / len(pzns))
            time.sleep(random.uniform(0.5, 1.5)) 

        status_text.text("✅ Fertig!")
        
        # --- ERGEBNIS & DOWNLOAD ---
        df = pd.DataFrame(results)
        
        # Spalten ordnen
        cols = ["PZN", "Name", "Brand", "Menge", "Link"]
        final_cols = [c for c in cols if c in df.columns]
        df = df[final_cols]
        
        st.divider()
        st.dataframe(df, use_container_width=True)
        
        # CSV Export
        csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode('utf-8-sig')
        st.download_button(
            label="💾 CSV Herunterladen",
            data=csv,
            file_name="pzn_export_final.csv",
            mime="text/csv",
        )
