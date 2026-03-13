import pytest
import pandas as pd
import sys
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import DataTransformer, Repository, Config, AIProvider, PipelineManager, StateManager

# --- Test DataTransformer ---
# This ensures your date cleaning logic handles messy Enterprise inputs correctly.

def test_parse_date_safely_standard():
    """Test that standard YYYY-MM-DD works."""
    result = DataTransformer.parse_date_safely("2026-01-15")
    assert str(result) == "2026-01-15"

def test_parse_date_safely_european():
    """Test that European DD/MM/YYYY works."""
    result = DataTransformer.parse_date_safely("15/01/2026")
    assert str(result) == "2026-01-15"

def test_parse_date_safely_text():
    """Test that written text dates work."""
    result = DataTransformer.parse_date_safely("March 10, 2026")
    assert str(result) == "2026-03-10"

def test_parse_date_safely_invalid():
    """Test that garbage input returns None instead of crashing."""
    assert DataTransformer.parse_date_safely("Not a date") is None
    assert DataTransformer.parse_date_safely(None) is None
    assert DataTransformer.parse_date_safely("NaN") is None
    assert DataTransformer.parse_date_safely("") is None

def test_parse_date_safely_impossible_dates():
    """Test that impossible calendar dates don't crash the parser."""
    # parser.parse might raise an error or handle it, our function catches exceptions and returns None
    assert DataTransformer.parse_date_safely("2026-02-30") is None

def test_scrub_for_display():
    """Test that we hide 'nan' and 'None' strings from the user."""
    # Create a messy dataframe
    df = pd.DataFrame({
        'A': ['Hello', 'nan', 'None'],
        'B': [1, None, float('nan')]
    })
    
    # Run the scrubber
    clean_df = DataTransformer.scrub_for_display(df)
    
    # Assertions
    assert clean_df.iloc[1]['A'] == ""  # 'nan' string should become empty
    assert clean_df.iloc[2]['A'] == ""  # 'None' string should become empty

def test_scrub_for_display_empty():
    """Test that an empty dataframe is returned safely."""
    df = pd.DataFrame()
    clean_df = DataTransformer.scrub_for_display(df)
    assert clean_df.empty

# --- Test Repository ---

def test_repository_save_to_sqlite():
    """Test that data is correctly saved to a SQLite database."""
    # Create dummy data
    df = pd.DataFrame({'id': [1, 2], 'val': ['a', 'b']})
    
    # Create a temporary file name but close it immediately so SQLite can access it (Windows fix)
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_name = tmp.name

    try:
        # Patch the Config.DB_NAME to use our temp file instead of the real DB
        with patch('main.Config.DB_NAME', tmp_name):
            Repository.save_to_sqlite(df)
            
            # Connect to temp DB and verify data
            with sqlite3.connect(tmp_name) as conn:
                saved_df = pd.read_sql("SELECT * FROM sales", conn)
                assert len(saved_df) == 2
                assert saved_df.iloc[0]['val'] == 'a'
    finally:
        # Cleanup
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass

# --- Test AIProvider ---

@pytest.mark.parametrize("raw_response, expected", [
    ("```sql\nSELECT * FROM sales;\n```", "SELECT * FROM sales;"),
    ("SELECT * FROM sales WHERE Territory = 'North';", "SELECT * FROM sales WHERE Territory = 'North';"),
    ("```SELECT 1;```", "SELECT 1;")
])
def test_ai_provider_generate_sql_strips_markdown(raw_response, expected):
    """Test that the generate_sql method correctly removes SQL markdown fences."""
    with patch('main.OpenAI') as mock_openai:
        # Setup mock client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = raw_response
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Instantiate AIProvider (it will get the mock client)
        ai_provider = AIProvider(api_key="fake_key")
        result = ai_provider.generate_sql("any query", ["any_column"])

        assert result.strip() == expected.strip()

def test_ai_provider_clean_data_handles_api_error():
    """Test that clean_data_with_ai returns an empty DataFrame on API error."""
    with patch('main.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API is down")
        mock_openai.return_value = mock_client
        
        # Patch the entire st module to prevent errors from st.progress
        with patch('main.st') as mock_st:
            ai_provider = AIProvider(api_key="fake_key")
            df = pd.DataFrame([{"col1": "a"}])
            result = ai_provider.clean_data_with_ai(df)
            
            assert result.empty
            # Check that st.error was called
            mock_st.error.assert_called_once()

# --- Test Pipeline & State ---

def test_pipeline_manager_calls_services_in_order():
    """Verify the cleaning pipeline calls AI, Repository, and Transformer."""
    with patch('main.Repository.save_to_sqlite') as mock_save, \
         patch('main.DataTransformer.scrub_for_display') as mock_scrub, \
         patch('main.st') as mock_st:

        # Ensure session_state is a Mock that accepts assignment
        mock_st.session_state = MagicMock()

        # Create a mock AI engine
        mock_ai_engine = MagicMock()
        # Setup the mock to return a dummy dataframe
        mock_ai_engine.clean_data_with_ai.return_value = pd.DataFrame({'A': [1]})
        
        # Execute the pipeline
        PipelineManager.execute_cleaning_pipeline(mock_ai_engine, pd.DataFrame())

        # Assert that each step was called once
        mock_ai_engine.clean_data_with_ai.assert_called_once()
        mock_save.assert_called_once()
        mock_scrub.assert_called_once()
        mock_st.success.assert_called_once_with("Analysis Ready!")

def test_state_manager_load_new_data():
    """Test that loading new data correctly updates the session state."""
    # Patch 'main.st' instead of 'session_state' directly for better stability
    with patch('main.st') as mock_st:
        # Setup session_state as a MagicMock
        mock_st.session_state = MagicMock()
        
        df = pd.DataFrame({'A': [1]})
        StateManager.load_new_data(df, "test_file.xlsx")
        
        assert mock_st.session_state.raw_data.equals(df)
        assert mock_st.session_state.processed_data is None
        assert mock_st.session_state.current_file == "test_file.xlsx"