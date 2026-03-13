import pandas as pd
import sys
import os

# Add parent directory to path so we can import 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import DataTransformer

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