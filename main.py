import os  # Import the OS library to read computer settings like API keys.
import json  # Import JSON to handle data formatted as JavaScript Object Notation (text data).
import sqlite3  # Import SQLite3 to create and manage a small database file on your disk.
import pandas as pd  # Import Pandas, a powerful tool for working with data tables (like Excel in code).
import streamlit as st  # Import Streamlit, the framework that builds the web interface.
from dotenv import load_dotenv  # Import load_dotenv to read passwords/keys from a hidden .env file.
from dateutil import parser  # Import parser to smartly figure out messy date formats.
from groq import Groq  # Import the Groq client to talk to the AI model.

# --- 1. CONFIGURATION ---
# This class acts as a settings container. It holds values used throughout the app.
class Config:
    # The name of the AI model we want to use (Llama 3.1 8B is fast and smart).
    LLM_MODEL = "llama-3.1-8b-instant"
    # The name of the file where we will save our database.
    DB_NAME = 'sales_intelligence.db'
    
    # A small list of fake data to use if the user clicks "Load Sample Data".
    SAMPLE_RECORDS = [
        {"Timestamp": "2026-01-15", "Territory": "North", "Revenue": "5000"},
        {"Timestamp": "15/02/2026", "Territory": "SOUTH", "Revenue": "6000"},
        {"Timestamp": "March 10, 2026", "Territory": "West", "Revenue": "4500"}
    ]

# --- 2. CORE SERVICES ---
# This class handles saving data to the hard drive (Database).
class Repository:
    # A static method means we can use this function without creating a 'Repository' object first.
    @staticmethod
    def save_to_sqlite(df: pd.DataFrame):
        # Open a connection to the SQLite database file defined in Config.
        with sqlite3.connect(Config.DB_NAME) as conn:
            # Save the Pandas DataFrame (our table) into the database as a table named 'sales'.
            # 'if_exists="replace"' means if the table exists, overwrite it completely.
            df.to_sql('sales', conn, if_exists='replace', index=False)

# This class handles fixing messy data formats (Dates and Text).
class DataTransformer:
    @staticmethod
    def parse_date_safely(value):
        # Check if the value is empty, None, or looks like "nan" (Not a Number).
        if not value or str(value).lower() in ['nan', 'none', 'null', '', '0']:
            return None # If it's bad data, return nothing (None).
        try:
            # Try to use the date parser to convert the text into a real Date object.
            return parser.parse(str(value)).date()
        except:
            # If the parser crashes (e.g., input is "Banana"), just return None.
            return None

    @staticmethod
    def scrub_for_display(df: pd.DataFrame) -> pd.DataFrame:
        # Convert everything to text and replace computer codes for "empty" (nan, NaN) with an empty string "" so it looks clean.
        return df.astype(str).replace(['nan', 'NaN', 'None', 'NaT', 'null'], '')

# This class manages the conversation with the Artificial Intelligence (Groq).
class AIProvider:
    # The __init__ runs when we start this class. It needs an API Key (password) to talk to Groq.
    def __init__(self, api_key: str):
        # Create the connection to Groq using the provided key.
        self.client = Groq(api_key=api_key)

    # This function asks the AI to clean up the messy data table.
    def clean_data_with_ai(self, df: pd.DataFrame) -> pd.DataFrame:
        # Convert the data table to a dictionary (JSON format) and remove "N/A" text so the AI isn't confused.
        input_data = df.astype(str).replace(['N/A', 'n/a', 'nan', 'NaN'], "").to_dict(orient='records')
        # Get a list of the column names (headers) from the file, trimmed of spaces and Title Cased.
        schema_columns = [c.strip().title() for c in df.columns]

        # Prepare the message (Prompt) for the AI. We give it rules on how to clean the data.
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
        # Send the message to the AI model.
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}], # The user message is the prompt.
            model=Config.LLM_MODEL, # Use the model name from our Config.
            temperature=0, # Temperature 0 means "be exact, don't be creative".
            response_format={"type": "json_object"} # Force the AI to reply in JSON computer format.
        )
        # Parse the AI's answer (text) back into a Python list of records.
        records = json.loads(response.choices[0].message.content).get("records", [])
        # Convert those records back into a Pandas DataFrame (table) and return it.
        return pd.DataFrame(records, columns=schema_columns)

    # This function asks the AI to write a Database Query (SQL) based on a human question.
    def generate_sql(self, user_query: str, columns: list) -> str:
        # Prepare the prompt for the SQL expert AI.
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
        # Send the prompt to the AI.
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=Config.LLM_MODEL
        )
        # Get the text answer, remove any extra spaces or markdown code blocks (```sql), and return the clean SQL.
        return response.choices[0].message.content.strip().replace('```sql', '').replace('```', '')

# --- 3. STATE MANAGEMENT ---
# Streamlit reloads the whole script every time you click a button.
# This class handles "Session State", which is the app's short-term memory.
class StateManager:
    @staticmethod
    def initialize():
        # If 'raw_data' isn't in memory yet, create it as empty (None).
        if 'raw_data' not in st.session_state: st.session_state.raw_data = None
        # If 'processed_data' isn't in memory yet, create it as empty.
        if 'processed_data' not in st.session_state: st.session_state.processed_data = None
        # Track the name of the current file being worked on.
        if 'current_file' not in st.session_state: st.session_state.current_file = None
        # Track the ID of the last uploaded file to detect new uploads vs reloads.
        if 'last_uploaded_file_id' not in st.session_state: st.session_state.last_uploaded_file_id = None

    @staticmethod
    def load_new_data(df: pd.DataFrame, source_id: str):
        # Save the new data table into the app's memory.
        st.session_state.raw_data = df
        # Clear out any old processed data because we have new raw data now.
        st.session_state.processed_data = None
        # Remember the name/ID of this new file.
        st.session_state.current_file = source_id

# --- 4. UI COMPONENTS ---
# This class handles drawing the Visuals (buttons, titles, tables) on the screen.
class UIRenderer:
    @staticmethod
    def setup_page():
        # Configure the web page title and set layout to 'wide' for better data viewing.
        st.set_page_config(page_title="AI Sales Analyser", layout="wide")
        # Display the main title header on the page.
        st.title("🚀 AI Sales Analyser")

    @staticmethod
    def handle_sidebar_ingestion():
        # Create a sidebar section for loading data.
        st.sidebar.header("📂 Data Ingestion")
        # Create a file upload widget that accepts Excel files (.xlsx).
        file = st.sidebar.file_uploader("", type=['xlsx'], label_visibility="collapsed")
        
        # Check if the "Load Sample Data" button is clicked.
        if st.sidebar.button("🧪 Load Sample Data"):
            # If clicked, load the fake sample records defined in Config.
            StateManager.load_new_data(pd.DataFrame(Config.SAMPLE_RECORDS), "sample_data")
        
        # If a file is uploaded AND it has a different ID than the last one we processed...
        elif file and file.file_id != st.session_state.last_uploaded_file_id:
            # Update the last uploaded file ID in memory.
            st.session_state.last_uploaded_file_id = file.file_id
            # Read the Excel file into a Pandas DataFrame.
            raw_df = pd.read_excel(file, keep_default_na=False)
            # Save this new data into the app's memory.
            StateManager.load_new_data(raw_df, file.name)

    @staticmethod
    def handle_raw_data_view(ai_engine: AIProvider):
        # Display a subheader for the raw data section.
        st.subheader("⚠️ Raw Legacy Input")
        # Show the raw data table in the app.
        st.dataframe(st.session_state.raw_data, use_container_width=True)

        # Create a button to start the AI cleaning process.
        if st.sidebar.button("🪄 Run AI Process"):
            # If clicked, show a "Processing..." spinner while the code runs.
            with st.spinner("Processing..."):
                # Call the pipeline manager to execute the cleaning logic.
                PipelineManager.execute_cleaning_pipeline(ai_engine, st.session_state.raw_data)

    @staticmethod
    def handle_analytics_view(ai_engine: AIProvider):
        # Display a subheader for the clean data section.
        st.subheader("✅ Cleaned & Structured Data")
        # Show the cleaned data table.
        st.dataframe(st.session_state.processed_data, use_container_width=True)
        
        # Draw a horizontal line separator.
        st.divider()
        # Display a subheader for the chat section.
        st.subheader("🗣️ AI SQL Analyst")
        # Create a text box for the user to type a question.
        query = st.text_input("Ask a question about your data:")
        
        # If the user typed a query...
        if query:
            # Get the list of column names from the processed data.
            db_columns = st.session_state.processed_data.columns.tolist()
            # Ask the AI to generate SQL code for this query.
            sql_code = ai_engine.generate_sql(query, db_columns)
            # Display the generated SQL code in a code box.
            st.code(sql_code, language="sql")
            # Connect to the SQLite database.
            with sqlite3.connect(Config.DB_NAME) as conn:
                try:
                    # Run the SQL query against the database and get the results.
                    res = pd.read_sql_query(sql_code, conn)
                    # Display the results in a table.
                    st.dataframe(res, use_container_width=True)
                except Exception as e:
                    # If the SQL fails, show an error message.
                    st.error(f"SQL Error: {e}")

# --- 5. BUSINESS LOGIC PIPELINE ---
# This class acts as a coordinator, chaining together the AI and Database steps.
class PipelineManager:
    @staticmethod
    def execute_cleaning_pipeline(ai_engine: AIProvider, raw_df: pd.DataFrame):
        # Step 1: Send raw data to AI to get it cleaned.
        df = ai_engine.clean_data_with_ai(raw_df)

        # Step 2: Save the clean data to the SQLite database for querying later.
        Repository.save_to_sqlite(df)
        # Step 3: Update the app's memory with the display-friendly version of the clean data.
        st.session_state.processed_data = DataTransformer.scrub_for_display(df)
        # Step 4: Show a success message to the user.
        st.success("Analysis Ready!")

# --- 6. MAIN ORCHESTRATOR ---
# This function sets up the app before drawing anything.
def initialize_application() -> AIProvider:
    # Load environment variables (keys) from the .env file.
    load_dotenv(override=True)
    # Try to get the Groq API key from the environment or Streamlit secrets.
    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    # If the key is missing, show an error and stop the app.
    if not api_key:
        st.error("API Key Missing"); st.stop()
    
    # Initialize the session state (memory).
    StateManager.initialize()
    # Return a ready-to-use AI provider.
    return AIProvider(api_key)

# The main function is the entry point of the script.
def main():
    # Setup the page title and layout.
    UIRenderer.setup_page()
    # Initialize the AI engine and getting the API key.
    ai_engine = initialize_application()
    
    # Render the sidebar for file uploads.
    UIRenderer.handle_sidebar_ingestion()
    
    # If there is raw data loaded, show the raw data view.
    if st.session_state.raw_data is not None:
        UIRenderer.handle_raw_data_view(ai_engine)
        
    # If there is processed data ready, show the analytics view.
    if st.session_state.processed_data is not None:
        UIRenderer.handle_analytics_view(ai_engine)

# This check ensures the main function only runs if this file is executed directly.
if __name__ == "__main__":
    main()