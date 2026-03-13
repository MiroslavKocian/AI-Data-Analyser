import pandas as pd
import sys
import os
import sqlite3
import tempfile
from unittest.mock import patch

# Add parent directory to path so we can import 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import DataTransformer, Repository, Config

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
    
    # Create a temporary file to act as the database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        # Patch the Config.DB_NAME to use our temp file instead of the real DB
        with patch('main.Config.DB_NAME', tmp_db.name):
            Repository.save_to_sqlite(df)
            
            # Connect to temp DB and verify data
            with sqlite3.connect(tmp_db.name) as conn:
                saved_df = pd.read_sql("SELECT * FROM sales", conn)
                assert len(saved_df) == 2
                assert saved_df.iloc[0]['val'] == 'a'
        
        # Cleanup
        try:
            os.remove(tmp_db.name)
        except PermissionError:
            pass