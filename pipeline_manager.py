"""Orchestrate cleaning, persistence, and UI state updates."""

import pandas as pd
import streamlit as st

from ai_provider import AIProvider
from data_transformer import scrub_for_display
from repository import save_to_sqlite


def execute_cleaning_pipeline(ai_engine: AIProvider, raw_df: pd.DataFrame) -> None:
    """Run the LLM cleaner, save to SQLite, and store display-ready data."""
    cleaned = ai_engine.clean_data_with_ai(raw_df)
    save_to_sqlite(cleaned)
    st.session_state.processed_data = scrub_for_display(cleaned)
    st.success("Analysis Ready!")
