"""Streamlit application entry flow."""

import streamlit as st

from startup import bootstrap_application
from ui_renderer import UIRenderer


def main() -> None:
    """Render the upload, cleaning, and SQL analyst workflow."""
    UIRenderer.setup_page()
    ai_engine = bootstrap_application()

    UIRenderer.handle_sidebar_ingestion()

    if st.session_state.raw_data is not None:
        UIRenderer.handle_raw_data_view(ai_engine)

    if st.session_state.processed_data is not None:
        UIRenderer.handle_analytics_view(ai_engine)
