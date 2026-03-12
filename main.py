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
    if not api_key:
        return False, "No API Key provided."
    try:
        _client.models.list()
        return True, "API Connection Active"
    except APIStatusError as e:
        if e.status_code == 401:
            return False, "Invalid GROQ_API_KEY."
        return False, f"Groq API Error: {e.status_code}"
    except APIConnectionError:
        return False, "Could not connect to Groq. Check your internet."
    except Exception as e:
        return False, f"Unexpected Error: {str(e)}"

def try_parse_date(date_val):
    if not date_val or str(date_val).lower() in ['nan', 'none', 'null', '', '0']:
        return None
    try:
        return parser.parse(str(date_val)).date()
    except (ValueError, TypeError):
        return None

def ai_clean_agent(client, df):
    data_records = df.fillna("").astype(str).to_dict(orient='records')
    
    prompt = f"""
    You are a Data Engineering Agent. Clean this messy data into JSON.
    
    INPUT: {json.dumps(data_records)}
    
    STRICT RULES:
    1. REGION CASING: 'SOUTH' or 'south' MUST become 'South'. Always use Proper Case for Regions.
    2. NO GUESSING (GLOBAL): If ANY cell is empty or 'nan', return null for that field. 
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
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    # Simple Fallback for Secrets
    if not GROQ_API_KEY:
        try:
            GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
        except:
            GROQ_API_KEY = None

    if not GROQ_API_KEY:
        st.error("🔑 API Key Missing!")
        st.stop()
    
    client = Groq(api_key=GROQ_API_KEY)
    is_healthy, health_message = verify_groq_connection(client, GROQ_API_KEY)

    if not is_healthy:
        st.error(f"**Connection Error:** {health_message}")
        st.stop()

    # Session State for Data Persistence
    if 'cleaned_df' not in st.session_state:
        st.session_state.cleaned_df = None
    if 'active_df' not in st.session_state:
        st.session_state.active_df = None

    st.markdown("---")

    # --- 2. Ingestion Sidebar ---
    st.sidebar.header("📂 Data Ingestion")
    uploaded_file = st.sidebar.file_uploader("", type=['xlsx'])

    # The Button: Load Sample Data
    if st.sidebar.button("🧪 Load Sample Data"):
        sample_data = [
            ["Date", "Region", "Product_Category", "Units_Sold", "Unit_Price"],
            ["2026-01-15", "North", "Electronics", "10", "500"],
            ["15/02/2026", "SOUTH", "Furniture", "5 pieces", "1200"],
            ["March 10, 2026", "West", "N/A", "15", "300"],
            ["2026.04.12", "East", "Electronics", "", "150"],
            ["", "North", "Appliances", "8", "Check with Finance"]
        ]
        st.session_state.active_df = pd.DataFrame(sample_data[1:], columns=sample_data[0])
        st.session_state.cleaned_df = None # Reset previous cleaning

    # Handle Uploaded File (Overrides sample if new file uploaded)
    if uploaded_file:
        st.session_state.active_df = pd.read_excel(uploaded_file).fillna("")
        st.session_state.cleaned_df = None

    # --- 3. Processing Logic (Shared between File and Sample) ---
    if st.session_state.active_df is not None:
        raw_df = st.session_state.active_df
        st.subheader("⚠️ Raw Legacy Input (Preview)")
        st.dataframe(raw_df.astype(str), width=1200)

        if st.sidebar.button("🪄 Run AI Cleaning & SQL Import"):
            with st.spinner("Processing..."):
                try:
                    df = ai_clean_agent(client, raw_df)
                    df.columns = [str(c).strip().title() for c in df.columns]
                    
                    if 'Date' in df.columns:
                        df['Date'] = df['Date'].apply(try_parse_date)
                    
                    for col in ['Units_Sold', 'Unit_Price']:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
                    df['Total_Revenue'] = df['Units_Sold'] * df['Unit_Price']
                    
                    # Display Cleanup
                    display_df = df.copy()
                    if 'Date' in display_df.columns:
                        display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')

                    display_df = display_df.astype(str).replace(['nan', 'NaN', 'None', 'NaT'], '')
                    st.session_state.cleaned_df = display_df

                    # SQL Store
                    conn = sqlite3.connect('sales_intelligence.db')
                    df.to_sql('sales', conn, if_exists='replace', index=False)
                    conn.close()
                    
                    st.success("Analysis Ready!")
                except Exception as e:
                    st.error(f"Error: {e}")

        # --- 4. Analytics Interface ---
        if st.session_state.cleaned_df is not None:
            st.subheader("✅ Cleaned & Structured Data")
            st.dataframe(st.session_state.cleaned_df, width=1200)

            st.markdown("---")
            st.subheader("🗣️ AI SQL Analyst")
            user_query = st.text_input("Ask a question:")

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
    else:
        st.info("Please upload an Excel file or click 'Load Sample Data' in the sidebar to begin.")

if __name__ == "__main__":
    main()