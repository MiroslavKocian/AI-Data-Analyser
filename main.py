import os
import json
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from dateutil import parser
from groq import Groq

# --- 1. CONFIGURATION ---
class Config:
    LLM_MODEL = "llama-3.1-8b-instant"
    DB_NAME = 'sales_intelligence.db'
    REQUIRED_COLUMNS = ["Date", "Region", "Product_Category", "Units_Sold", "Unit_Price"]
    
    SAMPLE_RECORDS = [
        {"Date": "2026-01-15", "Region": "North", "Product_Category": "Electronics", "Units_Sold": "10", "Unit_Price": "500"},
        {"Date": "15/02/2026", "Region": "SOUTH", "Product_Category": "Furniture", "Units_Sold": "5", "Unit_Price": "1200"},
        {"Date": "March 10, 2026", "Region": "West", "Product_Category": "N/A", "Units_Sold": "15", "Unit_Price": "300"},
        {"Date": "2026.04.12", "Region": "East", "Product_Category": "", "Units_Sold": "20", "Unit_Price": "150"},
        {"Date": "", "Region": "North", "Product_Category": "Appliances", "Units_Sold": "8", "Unit_Price": "0"}
    ]

# --- 2. CORE SERVICES ---
class Repository:
    @staticmethod
    def save_to_sqlite(df: pd.DataFrame):
        with sqlite3.connect(Config.DB_NAME) as conn:
            df.to_sql('sales', conn, if_exists='replace', index=False)

class DataTransformer:
    @staticmethod
    def parse_date_safely(value):
        if not value or str(value).lower() in ['nan', 'none', 'null', '', '0']:
            return None
        try: return parser.parse(str(value)).date()
        except: return None

    @staticmethod
    def scrub_for_display(df: pd.DataFrame) -> pd.DataFrame:
        return df.astype(str).replace(['nan', 'NaN', 'None', 'NaT', 'null'], '')

class AIProvider:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def clean_data_with_ai(self, df: pd.DataFrame) -> pd.DataFrame:
        # Pre AI interne vyčistíme N/A, aby nehalucinovalo
        input_data = df.astype(str).replace(['N/A', 'n/a', 'nan', 'NaN'], "").to_dict(orient='records')
        prompt = f"""
        Clean this sales data into JSON.
        STRICT: Proper Case Regions. No guessing categories—if empty, return null.
        SCHEMA: {Config.REQUIRED_COLUMNS}
        INPUT: {json.dumps(input_data)}
        Return ONLY JSON with 'records' key.
        """
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Config.LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"}
        )
        records = json.loads(response.choices[0].message.content).get("records", [])
        return pd.DataFrame(records)

    def generate_sql(self, user_query: str) -> str:
        prompt = f"Table 'sales' columns: {Config.REQUIRED_COLUMNS}. Convert to SQLite: {user_query}. Return ONLY SQL."
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Config.LLM_MODEL
        )
        return response.choices[0].message.content.strip().replace('```sql', '').replace('```', '')

# --- 3. STATE MANAGEMENT ---
class StateManager:
    @staticmethod
    def initialize():
        if 'raw_data' not in st.session_state: st.session_state.raw_data = None
        if 'processed_data' not in st.session_state: st.session_state.processed_data = None
        if 'current_file' not in st.session_state: st.session_state.current_file = None

    @staticmethod
    def load_new_data(df: pd.DataFrame, source_id: str):
        st.session_state.raw_data = df
        st.session_state.processed_data = None
        st.session_state.current_file = source_id

# --- 4. UI COMPONENTS ---
class UIRenderer:
    @staticmethod
    def setup_page():
        st.set_page_config(page_title="AI Sales Analyser", layout="wide")
        st.title("🚀 Enterprise AI Data Warehouse")

    @staticmethod
    def handle_sidebar_ingestion():
        st.sidebar.header("📂 Data Ingestion")
        file = st.sidebar.file_uploader("", type=['xlsx'], label_visibility="collapsed")
        
        if st.sidebar.button("🧪 Load Sample Data"):
            StateManager.load_new_data(pd.DataFrame(Config.SAMPLE_RECORDS), "sample_data")
        
        elif file and st.session_state.current_file != file.name:
            # KLÚČOVÁ ZMENA: keep_default_na=False zabezpečí, že N/A zostane ako text "N/A"
            raw_df = pd.read_excel(file, keep_default_na=False)
            StateManager.load_new_data(raw_df, file.name)

    @staticmethod
    def handle_raw_data_view(ai_engine: AIProvider):
        st.subheader("⚠️ Raw Legacy Input")
        st.dataframe(st.session_state.raw_data, use_container_width=True)

        if st.sidebar.button("🪄 Run AI Process"):
            with st.spinner("Processing..."):
                PipelineManager.execute_cleaning_pipeline(ai_engine, st.session_state.raw_data)

    @staticmethod
    def handle_analytics_view(ai_engine: AIProvider):
        st.subheader("✅ Cleaned & Structured Data")
        st.dataframe(st.session_state.processed_data, use_container_width=True)
        
        st.divider()
        st.subheader("🗣️ AI SQL Analyst")
        query = st.text_input("Ask a question about your data:")
        
        if query:
            sql_code = ai_engine.generate_sql(query)
            st.code(sql_code, language="sql")
            with sqlite3.connect(Config.DB_NAME) as conn:
                try:
                    res = pd.read_sql_query(sql_code, conn)
                    st.dataframe(res, use_container_width=True)
                except Exception as e:
                    st.error(f"SQL Error: {e}")

# --- 5. BUSINESS LOGIC PIPELINE ---
class PipelineManager:
    @staticmethod
    def execute_cleaning_pipeline(ai_engine: AIProvider, raw_df: pd.DataFrame):
        df = ai_engine.clean_data_with_ai(raw_df)
        
        df.columns = [c.strip().title() for c in df.columns]
        if 'Date' in df.columns:
            df['Date'] = df['Date'].apply(DataTransformer.parse_date_safely)
        
        for col in ['Units_Sold', 'Unit_Price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        
        df['Total_Revenue'] = df['Units_Sold'] * df['Unit_Price']
        
        Repository.save_to_sqlite(df)
        st.session_state.processed_data = DataTransformer.scrub_for_display(df)
        st.success("Analysis Ready!")

# --- 6. MAIN ORCHESTRATOR ---
def initialize_application() -> AIProvider:
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    if not api_key:
        st.error("API Key Missing"); st.stop()
    
    StateManager.initialize()
    return AIProvider(api_key)

def main():
    UIRenderer.setup_page()
    ai_engine = initialize_application()
    
    UIRenderer.handle_sidebar_ingestion()
    
    if st.session_state.raw_data is not None:
        UIRenderer.handle_raw_data_view(ai_engine)
        
    if st.session_state.processed_data is not None:
        UIRenderer.handle_analytics_view(ai_engine)

if __name__ == "__main__":
    main()