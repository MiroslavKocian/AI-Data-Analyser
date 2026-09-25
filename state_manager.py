"""Streamlit session state helpers."""

import pandas as pd
import streamlit as st


def initialize() -> None:
    """Create session keys without overwriting existing values."""
    if "raw_data" not in st.session_state:
        st.session_state.raw_data = None
    if "processed_data" not in st.session_state:
        st.session_state.processed_data = None
    if "current_file" not in st.session_state:
        st.session_state.current_file = None
    if "last_uploaded_file_id" not in st.session_state:
        st.session_state.last_uploaded_file_id = None


def load_new_data(df: pd.DataFrame, source_id: str) -> None:
    """Store a new upload and clear any previous AI output."""
    st.session_state.raw_data = df
    st.session_state.processed_data = None
    st.session_state.current_file = source_id
