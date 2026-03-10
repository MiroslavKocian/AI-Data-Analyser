import streamlit as st
import pandas as pd
import sqlite3
import json
import re
from groq import Groq

# 1. Page Configuration
st.set_page_config(page_title="AI Sales Intelligence 2026", page_icon="🚀", layout="wide")

# 2. API Key Configuration
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# --- NEW: INITIALIZE SESSION STATE ---
if 'cleaned_df' not in st.session_state:
    st.session_state.cleaned_df = None

def ai_clean_agent(df):
    """Strict Parser: Converts messy records into JSON without guessing."""
    data_records = df.astype(str).to_dict(orient='records')
    prompt = f"""
    You are a Data Engineering Parser. Convert these messy records into a JSON object with a 'records' key.
    
    INPUT DATA:
    {json.dumps(data_records)}
    
    STRICT TRANSFORMATION RULES:
    1. DATE: Be literal. '2026.04.12' -> '2026-04-12'. '15/01/2026' -> '2026-01-15'.
    2. UNKNOWN DATES: If a row has no clear date, use null. NEVER guess '2026-01-01'.
    3. NUMBERS: Extract digits ONLY. '12 pieces' -> 12. 'Check with Finance' -> 0.
    4. SCHEMA: ["Date", "Region", "Product_Category", "Units_Sold", "Unit_Price"]
    5. Return ONLY JSON with a 'records' key.
    """
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"}
    )
    clean_output = json.loads(response.choices[0].message.content)
    return pd.DataFrame(clean_output.get("records", []))

def main():
    st.title("🚀 Enterprise AI Data Warehouse")
    st.markdown("---")

    # --- SIDEBAR: INGESTION ---
    st.sidebar.header("📂 Data Ingestion")
    uploaded_file = st.sidebar.file_uploader("Upload excel", type=['xlsx'])

    if uploaded_file:
        raw_df = pd.read_excel(uploaded_file)
        st.subheader("⚠️ Raw Legacy Input (Direct from File)")
        st.dataframe(raw_df.astype(str), width=1200)

        if st.sidebar.button("🪄 Run AI Cleaning & SQL Import"):
            with st.spinner("Executing strict cleaning protocol..."):
                try:
                    # AI Cleaning
                    df = ai_clean_agent(raw_df)
                    df.columns = [str(c).strip().title() for c in df.columns]
                    
                    # Python Formatting & Safety
                    df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True, errors='coerce').dt.date
                    df['Region'] = df.get('Region', pd.Series()).astype(str).str.strip().str.title()
                    for col in ['Units_Sold', 'Unit_Price']:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
                    df['Total_Revenue'] = df['Units_Sold'] * df['Unit_Price']

                    # SAVE TO SESSION STATE
                    st.session_state.cleaned_df = df

                    # Database Storage
                    conn = sqlite3.connect('sales_intelligence.db')
                    df.to_sql('sales', conn, if_exists='replace', index=False)
                    conn.close()
                    
                    st.success("Cleaned Data Stored Successfully!")
                except Exception as e:
                    st.error(f"Cleaning Error: {str(e)}")

        # --- NEW: PERSISTENT DISPLAY ---
        if st.session_state.cleaned_df is not None:
            st.subheader("✅ Cleaned & Structured Data (SQL Ready)")
            st.dataframe(st.session_state.cleaned_df, width=1200)

            st.markdown("---")
            st.subheader("🗣️ Natural Language SQL Analyst")
            user_query = st.text_input("Ask a question:", placeholder="e.g., List all sales where total revenue is over 10000")

            if user_query:
                sql_prompt = f"""
                Table Name: 'sales'
                Columns: [Date, Region, Product_Category, Units_Sold, Unit_Price, Total_Revenue]
                Task: Convert this question to a SINGLE valid SQLite query: "{user_query}"
                
                STRICT RULES:
                1. ONLY filter by columns mentioned in the user query.
                2. If no date is mentioned, do NOT add a WHERE clause for Date.
                3. DO NOT use placeholder strings like 'YYYY-MM-%' in the output.
                4. Return ONLY the SQL query string.
                """
                
                with st.spinner("Translating to SQL..."):
                    sql_gen = client.chat.completions.create(
                        messages=[{"role": "user", "content": sql_prompt}], 
                        model="llama-3.1-8b-instant",
                        temperature=0 
                    )
                    query = sql_gen.choices[0].message.content.strip().replace('```sql', '').replace('```', '').split(';')[0]
                    
                    try:
                        conn = sqlite3.connect('sales_intelligence.db')
                        result_df = pd.read_sql_query(query, conn)
                        conn.close()
                        
                        st.code(query, language="sql")
                        st.write("**Query Result:**")
                        st.dataframe(result_df, width=1200)
                    except Exception as e:
                        st.error(f"SQL Error: {e}")
    else:
        # Clear state if file is removed
        st.session_state.cleaned_df = None
        st.warning("Please upload the legacy file in the sidebar to begin.")

if __name__ == "__main__":
    main()