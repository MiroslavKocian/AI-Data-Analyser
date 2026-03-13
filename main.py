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
    
    SAMPLE_RECORDS = [
        {"Timestamp": "2026-01-15", "Territory": "North", "Revenue": "5000"},
        {"Timestamp": "15/02/2026", "Territory": "SOUTH", "Revenue": "6000"},
        {"Timestamp": "March 10, 2026", "Territory": "West", "Revenue": "4500"}
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
        input_data = df.astype(str).replace(['N/A', 'n/a', 'nan', 'NaN'], "").to_dict(orient='records')
        schema_columns = [c.strip().title() for c in df.columns]

        prompt = f"""
        Clean and structure this data into a valid JSON object following these rules:
        1. The output MUST be a JSON object with a single key 'records', containing a list of objects.
        2. Each object in the list MUST use these keys, exactly as written in TitleCase: {schema_columns}.
        3. Date columns: Parse dates and format as YYYY-MM-DD. If invalid/missing, use null.
        4. Numeric columns: Extract only numbers (e.g., from '$1,200.50' or '15 units'). If non-numeric/missing, use 0.
        5. Region columns: Trim whitespace and convert to Title Case (e.g., ' south ' becomes 'South').
        6. Other text columns: If a value is empty or missing (like 'N/A'), use null. Do not guess data.

        INPUT DATA: {json.dumps(input_data)}

        Return ONLY the JSON object.
        """
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Config.LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"}
        )
        records = json.loads(response.choices[0].message.content).get("records", [])
        return pd.DataFrame(records, columns=schema_columns)

    def generate_sql(self, user_query: str, columns: list) -> str:
        prompt = f"""
        Act as an expert SQLite Data Analyst.
        Table 'sales' has columns: {columns}.
        
        Goal: Generate a valid SQLite SELECT query to answer: "{user_query}"
        
        Guidelines:
        1. For questions about trends or changes over time, SELECT the Date and the relevant metric column, and ORDER BY Date. Do NOT attempt to calculate row-by-row differences unless explicitly requested.
        2. Column names with spaces or special characters (like %, $) MUST be enclosed in double quotes (e.g., "Unit Price", "Voda %").
        3. If a JOIN is strictly necessary, EVERY column in the SELECT clause MUST be prefixed with its table alias to avoid ambiguity.
        4. Return ONLY the raw SQL string (no markdown, no explanations).
        """
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
        if 'last_uploaded_file_id' not in st.session_state: st.session_state.last_uploaded_file_id = None

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
        st.title("🚀 AI Sales Analyser")

    @staticmethod
    def handle_sidebar_ingestion():
        st.sidebar.header("📂 Data Ingestion")
        file = st.sidebar.file_uploader("", type=['xlsx'], label_visibility="collapsed")
        
        if st.sidebar.button("🧪 Load Sample Data"):
            StateManager.load_new_data(pd.DataFrame(Config.SAMPLE_RECORDS), "sample_data")
        
        # The original condition `st.session_state.current_file != file.name` was flawed.
        # It would become true after loading sample data, causing the previously uploaded
        # file to be reloaded unexpectedly. The new condition below fixes this.
        elif file and file.file_id != st.session_state.last_uploaded_file_id:
            # A new file has been uploaded. Store its unique ID and load the data.
            st.session_state.last_uploaded_file_id = file.file_id
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
            db_columns = st.session_state.processed_data.columns.tolist()
            sql_code = ai_engine.generate_sql(query, db_columns)
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