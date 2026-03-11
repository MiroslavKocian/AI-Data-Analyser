import streamlit as st                                               # Framework for building the web interface and dashboard
import pandas as pd                                                  # Library for high-performance data manipulation and analysis
import sqlite3                                                       # Built-in SQL database engine for local data warehousing
import json                                                          # Module for parsing and formatting JSON data for AI exchange
import re                                                            # Regular expression module for advanced text and numeric cleaning
from groq import Groq, APIStatusError, APIConnectionError            # Official client for interacting with the Groq Cloud AI inference API
from dateutil import parser                                          # Robust fuzzy date utility to handle messy "Month Day, Year" formats
import os                                                            # Interface for interacting with the operating system and file paths
from dotenv import load_dotenv                                       # Utility to securely load environment variables from a .env file

# 1. Page Configuration
st.set_page_config(page_title="AI Sales Analyser", page_icon="🚀", layout="wide")

# 2. API Key Configuration
# Load variables from .env. `override=True` ensures the .env file takes
# precedence over any system-level environment variables.

# 1. Try to load from local .env file
load_dotenv(override=True)

GROQ_API_KEY = None
key_source = None

# Check if .env file ACTUALLY exists on the disk
if os.path.exists(".env"):
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    if GROQ_API_KEY:
        key_source = ".env file"

# 2. If no .env file, check Streamlit Secrets
if not GROQ_API_KEY:
    try:
        GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
        if GROQ_API_KEY:
            key_source = "Streamlit Secrets"
    except Exception:
        pass
    
# 3. Final Fallback (System Environment)
if not GROQ_API_KEY:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    if GROQ_API_KEY:
        key_source = "System Environment"

if not GROQ_API_KEY:
    st.error("🔑 API Key Missing! Please check your .env file or Streamlit Secrets.")
    st.stop()
else:
    client = Groq(api_key=GROQ_API_KEY)

    # Check if the API key is valid
    @st.cache_resource
    def verify_groq_connection():
        """Standard try-except block to verify the API key is actually working."""
        try:
            # Lightweight call to verify connectivity and key validity
            client.models.list()
            return True, "API Connection Active"
        except APIStatusError as e:
            if e.status_code == 401:
                return False, "Invalid API Key. Please check your credentials."
            return False, f"Groq API Error: {e.status_code}"
        except APIConnectionError:
            return False, "Could not connect to Groq. Check your internet."
        except Exception as e:
            return False, f"Unexpected Error: {str(e)}"

    is_healthy, health_message = verify_groq_connection()

    if is_healthy:
        st.sidebar.success(f"✅ {health_message} ({key_source})")
    else:
        st.sidebar.error(f"❌ {health_message}")
        st.error("The Groq API is unreachable or the key provided is invalid.")
        st.stop()

# Initialize the client with the successfully found key
client = Groq(api_key=GROQ_API_KEY.strip())

if 'cleaned_df' not in st.session_state:
    st.session_state.cleaned_df = None

def flexible_date_search(date_val):
    """Parses 'March 10, 2026' and returns None for truly empty cells."""
    if not date_val or str(date_val).lower() in ['nan', 'none', 'null', '', '0']:
        return None
    try:
        # parser.parse is highly effective for 'Month Day, Year' formats
        return parser.parse(str(date_val)).date()
    except:
        return None

def ai_clean_agent(df):
    """Strict Parser: Fixes Region casing and stops hallucinations in Product_Category."""
    data_records = df.fillna("").astype(str).to_dict(orient='records')
    
    prompt = f"""
    You are a Data Engineering Agent. Clean this messy data into JSON.
    
    INPUT: {json.dumps(data_records)}
    
    STRICT RULES:
    1. REGION CASING: 'SOUTH' or 'south' MUST become 'South'. Always use Proper Case for Regions.
    2. NO GUESSING (GLOBAL): If ANY cell is empty or 'nan', return null for that field. 
       DO NOT invent dates (like '2026-01-01'), DO NOT invent categories (like 'Electronics'), 
       and DO NOT copy values from previous rows.
    3. DATE: 'March 10, 2026' -> '2026-03-10'.
    4. ALIGNMENT: Move '5' from Category to Units_Sold if it was shifted.
    5. SCHEMA: ["Date", "Region", "Product_Category", "Units_Sold", "Unit_Price"]
    Return ONLY JSON with a 'records' key.
    """
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0,  # This 1 line stops the "creativity" and guessing
        response_format={"type": "json_object"}
    )
    clean_output = json.loads(response.choices[0].message.content)
    return pd.DataFrame(clean_output.get("records", []))

def main():
    st.title("🚀 Enterprise AI Data Warehouse")
    st.markdown("---")

    st.sidebar.header("📂 Data Ingestion")
    uploaded_file = st.sidebar.file_uploader("Upload excel", type=['xlsx'])

    if uploaded_file:
        # Keep empty cells empty by filling NaNs with empty strings immediately
        raw_df = pd.read_excel(uploaded_file).fillna("")
        st.subheader("⚠️ Raw Legacy Input (Direct from File)")
        st.dataframe(raw_df.astype(str), width=1200)

        if st.sidebar.button("🪄 Run AI Cleaning & SQL Import"):
            with st.spinner("Processing..."):
                try:
                    df = ai_clean_agent(raw_df)
                    df.columns = [str(c).strip().title() for c in df.columns]
                    # --- THE REGION PART ---
                    # This ensures "SOUTH" becomes "South" and removes extra spaces
                    if 'Region' in df.columns:
                        df['Region'] = df['Region'].astype(str).str.strip().str.title()
                        # Clean up any 'Nan' strings that might have slipped through
                        df['Region'] = df['Region'].replace('Nan', '')                    
                    
                    # 1. Precise Date Parsing
                    if 'Date' in df.columns:
                        df['Date'] = df['Date'].apply(flexible_date_search)
                    
                    # 2. Number Conversion (keeps 0 for math, but keeps display clean)
                    for col in ['Units_Sold', 'Unit_Price']:
                        if col in df.columns:
                            df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
                    df['Total_Revenue'] = df['Units_Sold'] * df['Unit_Price']
                    
                    # Final display cleanup: ensure local and cloud show the same clean results
                    display_df = df.copy()

                    # 1. Force Date to a consistent string format
                    if 'Date' in display_df.columns:
                        display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')

                    # 2. Convert entire DF to string and scrub all versions of "nan"
                    # This is the "Force" part that removes the text you see in the browser
                    display_df = display_df.astype(str).replace(['nan', 'NaN', 'None', 'NaT'], '')
                    
                    st.session_state.cleaned_df = display_df

                    # 3. Store in SQL (SQL handles actual NULLs better than 'nan' strings)
                    conn = sqlite3.connect('sales_intelligence.db')
                    df.to_sql('sales', conn, if_exists='replace', index=False)
                    conn.close()
                    
                    st.success("Analysis Ready: Empty cells preserved and dates fixed!")
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.cleaned_df is not None:
            st.subheader("✅ Cleaned & Structured Data")
            st.dataframe(st.session_state.cleaned_df, width=1200)

            st.markdown("---")
            st.subheader("🗣️ AI SQL Analyst")
            user_query = st.text_input("Ask a question (e.g., 'Total revenue for March'):")

            if user_query:
                sql_prompt = f"Table 'sales' has [Date, Region, Product_Category, Units_Sold, Unit_Price, Total_Revenue]. Convert to SQLite: {user_query}. Return ONLY SQL code."
                sql_gen = client.chat.completions.create(messages=[{"role": "user", "content": sql_prompt}], model="llama-3.1-8b-instant")
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
        st.session_state.cleaned_df = None

if __name__ == "__main__":
    main()