import os
import json
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from dateutil import parser
from groq import Groq, APIStatusError, APIConnectionError

# Constants
LLM_MODEL = "llama-3.1-8b-instant"

@st.cache_resource
def verify_groq_connection(_client, api_key):
    """Verifies connection without re-hashing the client."""
    if not api_key:
        return False, "No API Key provided."
    try:
        _client.models.list()
        return True, "API Connection Active"
    except Exception as e:
        return False, f"Connection Error: {str(e)}"

def try_parse_date(date_val):
    """Parses various date formats and returns None for empty/invalid values."""
    if not date_val or str(date_val).lower() in ['nan', 'none', 'null', '', '0']:
        return None
    try:
        return parser.parse(str(date_val)).date()
    except (ValueError, TypeError):
        return None

def ai_clean_agent(client, df):
    """Strict Parser: Fixes Region casing and prevents category hallucinations."""
    data_records = df.fillna("").astype(str).to_dict(orient='records')
    
    prompt = f"""
    You are a Data Engineering Agent. Clean this messy data into JSON.
    
    INPUT: {json.dumps(data_records)}
    
    STRICT RULES:
    1. REGION CASING: 'SOUTH' or 'south' MUST become 'South'. Always use Proper Case for Regions.
    2. NO GUESSING (GLOBAL): If ANY cell is empty or 'nan', return null for that field. 
       DO NOT invent dates, DO NOT invent categories, and DO NOT copy values from previous rows.
    3. DATE: 'March 10, 2026' -> '2026-03-10'.
    4. ALIGNMENT: Move '5' from Category to Units_Sold if it was shifted.
    5. SCHEMA: ["Date", "Region", "Product_Category", "Units_Sold", "Unit_Price"]
    Return ONLY JSON with a 'records' key.
    """
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=LLM_MODEL,
        temperature=0,  
        response_format={"type": "json_object"}
    )
    clean_output = json.loads(response.choices[0].message.content)
    return pd.DataFrame(clean_output.get("records", []))

def main():
    # --- 1. Setup & Configuration ---
    st.set_page_config(page_title="AI Sales Analyser", page_icon="🚀", layout="wide")
    st.title("🚀 Enterprise AI Data Warehouse")

    load_dotenv(override=True)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")

    if not GROQ_API_KEY:
        st.error("🔑 API Key Missing! Please check your configuration.")
        st.stop()
    
    client = Groq(api_key=GROQ_API_KEY)
    is_healthy, health_message = verify_groq_connection(client, GROQ_API_KEY)

    if not is_healthy:
        st.error(f"**Connection Error:** {health_message}")
        st.stop()

    # Initialize Session States
    if 'cleaned_df' not in st.session_state:
        st.session_state.cleaned_df = None
    if 'active_df' not in st.session_state:
        st.session_state.active_df = None

    # --- 2. UI Layout & Ingestion ---
    st.markdown("---")
    st.sidebar.header("📂 Data Ingestion")

    # File uploader with no visible text label
    uploaded_file = st.sidebar.file_uploader("", type=['xlsx'], label_visibility="collapsed")

    # Load Sample Data Button
    if st.sidebar.button("🧪 Load Sample Data"):
        sample_data = [
            {"Date": "2026-01-15", "Region": "North", "Product_Category": "Electronics", "Units_Sold": "10", "Unit_Price": "500"},
            {"Date": "15/02/2026", "Region": "SOUTH", "Product_Category": "Furniture", "Units_Sold": "5 pieces", "Unit_Price": "1200"},
            {"Date": "March 10, 2026", "Region": "West", "Product_Category": "N/A", "Units_Sold": "15", "Unit_Price": "300"},
            {"Date": "2026.04.12", "Region": "East", "Product_Category": "", "Units_Sold": "20", "Unit_Price": "150"},
            {"Date": "", "Region": "North", "Product_Category": "Appliances", "Units_Sold": "8", "Unit_Price": "Check with Finance"}
        ]
        st.session_state.active_df = pd.DataFrame(sample_data)
        st.session_state.cleaned_df = None  # Reset cleaning for new data source

    # Handle file upload persistence
    if uploaded_file:
        st.session_state.active_df = pd.read_excel(uploaded_file).fillna("")
        st.session_state.cleaned_df = None

    # --- 3. Processing & Display ---
    if st.session_state.active_df is not None:
        raw_df = st.session_state.active_df
        st.subheader("⚠️ Raw Legacy Input (Review)")
        st.dataframe(raw_df.astype(str), width=1200)

        if st.sidebar.button("🪄 Run AI Cleaning & SQL Import"):
            with st.spinner("Processing..."):
                try:
                    # Run AI Cleaning
                    df = ai_clean_agent(client, raw_df)
                    df.columns = [str(c).strip().title() for c in df.columns]
                    
                    # 1. Precise Date Parsing
                    if 'Date' in df.columns:
                        df['Date'] = df['Date'].apply(try_parse_date)
                    
                    # 2. Number Conversion
                    for col in ['Units_Sold', 'Unit_Price']:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
                    df['Total_Revenue'] = df['Units_Sold'] * df['Unit_Price']
                    
                    # 3. Display Formatting
                    display_df = df.copy()
                    if 'Date' in display_df.columns:
                        display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')

                    # Scrub all versions of 'nan/none' for clean UI visibility
                    display_df = display_df.astype(str).replace(['nan', 'NaN', 'None', 'NaT', 'None'], '')
                    st.session_state.cleaned_df = display_df

                    # 4. Store in SQL
                    conn = sqlite3.connect('sales_intelligence.db')
                    df.to_sql('sales', conn, if_exists='replace', index=False)
                    conn.close()
                    
                    st.success("Analysis Ready!")
                except Exception as e:
                    st.error(f"Error: {e}")

        # Show Cleaned Table and AI SQL Analyst
        if st.session_state.cleaned_df is not None:
            st.subheader("✅ Cleaned & Structured Data")
            st.dataframe(st.session_state.cleaned_df, width=1200)

            st.markdown("---")
            st.subheader("🗣️ AI SQL Analyst")
            user_query = st.text_input("Ask a question (e.g., 'Total revenue for East region'):")

            if user_query:
                sql_prompt = f"Table 'sales' has [Date, Region, Product_Category, Units_Sold, Unit_Price, Total_Revenue]. Convert to SQLite: {user_query}. Return ONLY SQL code."
                sql_gen = client.chat.completions.create(messages=[{"role": "user", "content": sql_prompt}], model=LLM_MODEL)
                query = sql_gen.choices[0].message.content.strip().replace('```sql', '').replace('```', '')
                
                try:
                    conn = sqlite3.connect('sales_intelligence.db')
                    result = pd.read_sql_query(query, conn).fillna("")
                    st.code(query, language="sql")
                    st.dataframe(result, width=1200)
                    conn.close()
                except Exception as e:
                    st.error(f"SQL Error: {e}")

if __name__ == "__main__":
    main()