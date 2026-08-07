"""
AI Sales Analyser
------------------
A Streamlit app that ingests messy sales spreadsheets (inconsistent date
formats, currency symbols mixed into numbers, blank/"N/A" values, etc.),
uses an LLM (Mistral, via the OpenAI-compatible client) to clean and
normalize the data into a strict schema, persists the result to SQLite,
and lets the user query it with plain-English questions that the LLM
translates into SQL.

Architecture: the file is deliberately organised in layers - Config ->
core services (Repository / DataTransformer / AIProvider) -> state
management -> UI components -> pipeline orchestration -> entry point.
Keeping Streamlit's UI code separate from the business logic is what
makes most of this file unit-testable (see tests/test_core.py) without
needing a running Streamlit session.
"""
import json
import os
import sqlite3

import pandas as pd
import streamlit as st
from dateutil import parser
from dotenv import load_dotenv
from openai import OpenAI

# --- 1. CONFIGURATION ---
# Central place for constants and demo data, so magic values and sample
# records aren't scattered throughout the rest of the file.
class Config:
    LLM_MODEL = "mistral-small-latest"
    DB_NAME = 'sales_intelligence.db'
    
    # Deliberately messy/inconsistent sample rows (mixed date formats,
    # units baked into numeric strings, blanks, "N/A") used by the
    # "Load Sample Data" button so the AI cleaning step can be demoed
    # end-to-end without requiring the user to supply their own file.
    SAMPLE_RECORDS = [
        {
            "Date": "2026-01-15",
            "Region": "North",
            "Product_Category": "Electronics",
            "Units_Sold": "10",
            "Unit_Price": "500",
        },
        {
            "Date": "15/02/2026",
            "Region": "South",
            "Product_Category": "Furniture",
            "Units_Sold": "5 pieces",
            "Unit_Price": "1200 USD",
        },
        {
            "Date": "March 10, 2026",
            "Region": "West",
            "Product_Category": "N/A",
            "Units_Sold": "15",
            "Unit_Price": "300",
        },
        {
            "Date": "2026.04.12",
            "Region": "East",
            "Product_Category": "",
            "Units_Sold": "20",
            "Unit_Price": "150",
        },
        {
            "Date": "",
            "Region": "North",
            "Product_Category": "Appliances",
            "Units_Sold": "8",
            "Unit_Price": "0",
        },
    ]

# --- 2. CORE SERVICES ---
# Stateless service classes (mostly @staticmethod) holding the app's
# core business logic, kept independent of Streamlit where possible so
# they can be tested in isolation (see test_core.py).
class Repository:
    # Thin data-access layer: wraps the raw SQLite write so callers
    # never need to touch sqlite3 directly.
    @staticmethod
    def save_to_sqlite(df: pd.DataFrame):
        """Persists the DataFrame to the SQLite database, replacing existing data."""
        # if_exists='replace' keeps the demo simple: each new run fully
        # overwrites the previous table instead of appending, so the AI
        # SQL Analyst always queries the latest cleaned dataset.
        with sqlite3.connect(Config.DB_NAME) as conn:
            df.to_sql('sales', conn, if_exists='replace', index=False)

class DataTransformer:
    # Pure data-cleaning helpers with no side effects - easy to unit
    # test in isolation (see TestParseDateSafely / TestScrubForDisplay).
    @staticmethod
    def parse_date_safely(value):
        """
        Attempts to parse a date string into a date object, returning None on failure.
        """
        # Treat common "empty-ish" representations as missing up front,
        # since dateutil would otherwise happily mis-parse something
        # like "0" into an actual date instead of flagging it as missing.
        if not value or str(value).lower() in ['nan', 'none', 'null', '', '0']:
            return None
        try:
            return parser.parse(str(value)).date()
        except Exception:
            return None

    @staticmethod
    def scrub_for_display(df: pd.DataFrame) -> pd.DataFrame:
        """Converts DataFrame to string and replaces nan/None with empty strings."""
        # After casting to str, pandas' various "missing" markers show up
        # as the literal strings 'nan', 'NaN', 'None', 'NaT', 'null'.
        # Normalize all of them to '' so the table looks clean to the user.
        return df.astype(str).replace(['nan', 'NaN', 'None', 'NaT', 'null'], '')

class AIProvider:
    # Wraps every LLM call (data cleaning + natural-language-to-SQL)
    # behind a single client instance.
    def __init__(self, api_key: str):
        # Mistral exposes an OpenAI-compatible API, so the standard
        # OpenAI SDK can be pointed at Mistral's endpoint via base_url.
        self.client = OpenAI(api_key=api_key, base_url="https://api.mistral.ai/v1")

    def clean_data_with_ai(self, df: pd.DataFrame) -> pd.DataFrame:
        """Uses LLM to normalize data into a strict JSON structure."""
        # Normalize column names once up front so they can be reused
        # consistently both in the prompt and when rebuilding the
        # cleaned DataFrame from the model's JSON response.
        schema_columns = [c.strip() for c in df.columns]
        cleaned_dfs = []
        # Batch requests instead of sending the whole file in one call:
        # keeps individual prompts small/reliable and lets the progress
        # bar give the user real-time feedback on larger uploads.
        BATCH_SIZE = 10
        total_rows = len(df)
        progress_bar = st.progress(0, text="AI is analyzing data batches...")

        # Walk the DataFrame in fixed-size chunks.
        for i in range(0, total_rows, BATCH_SIZE):
            chunk = df.iloc[i : i + BATCH_SIZE]
            input_data = (
                chunk.astype(str)
                .replace(['N/A', 'n/a', 'nan', 'NaN'], "")
                .to_dict(orient='records')
            )

            # Strict, numbered rules keep the LLM's output deterministic
            # and in the exact schema/format the rest of the pipeline
            # (DataFrame reconstruction, SQLite persistence) expects.
            prompt = f"""
            Clean and structure this data into a valid JSON object following these 
            rules:
            1. The output MUST be a JSON object with a single key 'records', containing
               a list of objects.
            2. Each object in the list MUST use these exact keys, unchanged:
               {schema_columns}.
            3. Date columns: Parse dates and format as YYYY-MM-DD. If invalid/missing,
               use null.
            4. Numeric columns: Strip currency symbols and units, keep only the number
               (e.g., '$1,200.50' -> 1200.50, '15 units' -> 15). If non-numeric or
               missing, use null.
            5. All other columns: If a value is empty or missing (like 'N/A', 'n/a',
               '-', ''), use null. Do not change, guess, or reformat the data in any
               other way.

            INPUT DATA: {json.dumps(input_data)}

            Return ONLY the JSON object.
            """
            try:
                # temperature=0 and response_format=json_object minimize
                # randomness and guarantee the response is parseable JSON.
                response = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=Config.LLM_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                records = json.loads(
                    response.choices[0].message.content
                ).get("records", [])
                if records:
                    cleaned_dfs.append(pd.DataFrame(records, columns=schema_columns))
            except Exception as e:
                # A single bad batch (API error, malformed JSON, etc.)
                # shouldn't crash the whole run - surface it and keep
                # processing the remaining batches.
                st.error(f"Batch processing error: {e}")
            
            # Advance the progress bar in proportion to rows processed so far.
            progress_bar.progress(min((i + BATCH_SIZE) / total_rows, 1.0))
            
        progress_bar.empty()
        # If every batch failed, still return an (empty) DataFrame with
        # the right columns rather than None, so downstream code doesn't
        # need extra null-checks before using the result.
        return (
            pd.concat(cleaned_dfs, ignore_index=True)
            if cleaned_dfs
            else pd.DataFrame(columns=schema_columns)
        )

    def generate_sql(self, user_query: str, columns: list) -> str:
        """
        Asks the LLM to translate a natural-language question into a single
        SQLite SELECT statement against the 'sales' table, given the list of
        available columns. Returns the raw SQL string with any markdown code
        fences stripped, ready to execute directly.
        """
        # Explicit SQLite quoting/aliasing rules reduce syntax errors on
        # real-world column names (spaces, %, $) and on any joins.
        prompt = f"""
        Act as an expert SQLite Data Analyst.
        Table 'sales' has columns: {columns}.
        
        Goal: Generate a valid SQLite SELECT query to answer: "{user_query}"
        
        Guidelines:
        1. For questions about trends or changes over time, SELECT the Date and the
           relevant metric column, and ORDER BY Date. Do NOT attempt to calculate
           row-by-row differences unless explicitly requested.
        2. Column names with spaces or special characters (like %, $) MUST be enclosed
           in double quotes (e.g., "Unit Price", "Voda %").
        3. If a JOIN is strictly necessary, EVERY column in the SELECT clause MUST be
           prefixed with its table alias to avoid ambiguity.
        4. Return ONLY the raw SQL string (no markdown, no explanations).
        """
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Config.LLM_MODEL
        )
        # Models often wrap SQL in markdown fences even when told not
        # to; strip them defensively so the string can be executed as-is.
        return (
            response.choices[0].message.content.strip()
            .replace('```sql', '')
            .replace('```', '')
        )

# --- 3. STATE MANAGEMENT ---
# Centralizes all access to Streamlit's st.session_state so the rest of
# the app doesn't poke at session_state directly.
class StateManager:
    @staticmethod
    def initialize():
        # Guard each key individually so calling initialize() on every
        # rerun never clobbers state the user has already built up -
        # Streamlit reruns this whole script top-to-bottom on every
        # interaction (button click, file upload, etc.).
        if 'raw_data' not in st.session_state:
            st.session_state.raw_data = None
        if 'processed_data' not in st.session_state:
            st.session_state.processed_data = None
        if 'current_file' not in st.session_state:
            st.session_state.current_file = None
        if 'last_uploaded_file_id' not in st.session_state:
            st.session_state.last_uploaded_file_id = None

    @staticmethod
    def load_new_data(df: pd.DataFrame, source_id: str):
        # Loading new data always clears processed_data, forcing a
        # fresh AI cleaning run on the new source instead of showing
        # stale results from a previous file/sample.
        st.session_state.raw_data = df
        st.session_state.processed_data = None
        st.session_state.current_file = source_id

# --- 4. UI COMPONENTS ---
# Pure Streamlit rendering code, kept separate from CORE SERVICES so the
# business logic above stays framework-agnostic and unit-testable.
class UIRenderer:
    @staticmethod
    def setup_page():
        st.set_page_config(page_title="AI Sales Analyser", layout="wide")
        st.title("🚀 AI Sales Analyser")

    @staticmethod
    def handle_sidebar_ingestion():
        st.sidebar.header("📂 Data Ingestion")
        file = st.sidebar.file_uploader(
            "Upload Excel File", type=['xlsx'], label_visibility="collapsed"
        )
        
        # Two independent entry points into the app: a one-click sample
        # dataset for demos, or the user's own uploaded file.
        if st.sidebar.button("🧪 Load Sample Data"):
            StateManager.load_new_data(
                pd.DataFrame(Config.SAMPLE_RECORDS), "sample_data"
            )
        
        # Guard against Streamlit's rerun-on-every-interaction model
        # re-processing the same uploaded file more than once.
        elif file and file.file_id != st.session_state.last_uploaded_file_id:
            st.session_state.last_uploaded_file_id = file.file_id
            raw_df = pd.read_excel(file, keep_default_na=False)
            StateManager.load_new_data(raw_df, file.name)

    @staticmethod
    def handle_raw_data_view(ai_engine: AIProvider):
        # Shows the untouched upload so the user can see exactly what
        # the AI is about to clean, before triggering the pipeline.
        st.subheader("⚠️ Raw Legacy Input")
        st.dataframe(st.session_state.raw_data, use_container_width=True)

        if st.sidebar.button("🪄 Run AI Process"):
            with st.spinner("Processing..."):
                PipelineManager.execute_cleaning_pipeline(
                    ai_engine, st.session_state.raw_data
                )

    @staticmethod
    def handle_analytics_view(ai_engine: AIProvider):
        st.subheader("✅ Cleaned & Structured Data")
        st.dataframe(st.session_state.processed_data, use_container_width=True)

        # Let the user take the cleaned data with them, independent of
        # the natural-language SQL analyst below.
        st.download_button(
            label="⬇️ Download Cleaned Data as CSV",
            data=st.session_state.processed_data.to_csv(index=False).encode('utf-8'),
            file_name="cleaned_data.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("🗣️ AI SQL Analyst")
        query = st.text_input("Ask a question about your data:")
        
        # Only show canned example Q&A for the built-in sample dataset,
        # where the "correct" answers are known ahead of time - showing
        # these for arbitrary user data would be misleading.
        if st.session_state.current_file == "sample_data":
            with st.expander("📝 Sample Questions & Answers (for this dataset)"):
                st.markdown(
                    """
                    **1. Revenue Analysis**
                    - ❓ *Question:* "What is the total revenue?"
                    - 💡 *Answer:* 18,500 (Calculated as sum of Units * Price)

                    **2. Regional Performance**
                    - ❓ *Question:* "Which region sold the most units?"
                    - 💡 *Answer:* East (20 units sold)

                    **3. Category Search**
                    - ❓ *Question:* "Show me all Electronics sales"
                    - 💡 *Answer:* Returns the transaction from 2026-01-15
                    """
                )

        # Every question triggers a fresh LLM call to generate SQL, then
        # executes that SQL live against the persisted 'sales' table.
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
# Ties the core services together into the single "clean -> persist ->
# update UI state" workflow triggered by the "Run AI Process" button.
class PipelineManager:
    @staticmethod
    def execute_cleaning_pipeline(ai_engine: AIProvider, raw_df: pd.DataFrame):
        df = ai_engine.clean_data_with_ai(raw_df)

        # Order matters here: persist the AI-cleaned data first, then
        # scrub it for display, so the SQL Analyst always queries the
        # same clean values the user sees in the table above it.
        Repository.save_to_sqlite(df)
        st.session_state.processed_data = DataTransformer.scrub_for_display(df)
        st.success("Analysis Ready!")

# --- 6. MAIN ORCHESTRATOR ---
# Wires everything together: app startup/initialization and the
# top-level render flow that Streamlit re-executes on every interaction.
def initialize_application() -> AIProvider:
    # override=True ensures a locally edited .env always wins over any
    # stale environment variable left over from a previous run.
    load_dotenv(override=True)
    # Support both local development (.env) and deployment on Streamlit
    # Community Cloud (st.secrets).
    api_key = os.getenv("MISTRAL_API_KEY") or st.secrets.get("MISTRAL_API_KEY")
    if not api_key:
        # Fail fast with a clear message rather than letting a later API
        # call raise a confusing authentication error deep in the pipeline.
        st.error("MISTRAL_API_KEY is missing. Please add it to your .env file.")
        st.stop()
    
    StateManager.initialize()
    return AIProvider(api_key)

def main():
    UIRenderer.setup_page()
    ai_engine = initialize_application()
    
    UIRenderer.handle_sidebar_ingestion()
    
    # Each view only renders once its prerequisite data exists, forming
    # a simple linear flow: upload/sample -> raw preview -> cleaned data
    # & SQL analyst. State persists across reruns via st.session_state.
    if st.session_state.raw_data is not None:
        UIRenderer.handle_raw_data_view(ai_engine)
        
    if st.session_state.processed_data is not None:
        UIRenderer.handle_analytics_view(ai_engine)

# Standard guard so this module can also be imported (e.g. by the test
# suite) without launching the Streamlit app as a side effect.
if __name__ == "__main__":
    main()
