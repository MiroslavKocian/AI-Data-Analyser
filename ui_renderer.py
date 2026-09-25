"""Streamlit layout and user interactions."""

import pandas as pd
import streamlit as st

from ai_provider import AIProvider
from pipeline_manager import execute_cleaning_pipeline
from data_transformer import scrub_for_display
from sample_loader import load_sample_excel
from sql_runner import run_select_query
from state_manager import load_new_data

SAMPLE_SOURCE_ID: str = "sample_data"


class UIRenderer:
    """All Streamlit widgets live here to keep other modules testable."""

    @staticmethod
    def setup_page() -> None:
        st.set_page_config(page_title="AI Data Analyser", layout="wide")
        st.title("AI Data Analyser")

    @staticmethod
    def handle_sidebar_ingestion() -> None:
        st.sidebar.header("Data ingestion")
        uploaded = st.sidebar.file_uploader(
            "Upload Excel file",
            type=["xlsx"],
            label_visibility="collapsed",
        )

        if st.sidebar.button("Load sample data"):
            load_new_data(load_sample_excel(), SAMPLE_SOURCE_ID)
            return

        if (
            uploaded is not None
            and uploaded.file_id != st.session_state.last_uploaded_file_id
        ):
            st.session_state.last_uploaded_file_id = uploaded.file_id
            raw_df = pd.read_excel(uploaded, keep_default_na=False)
            load_new_data(raw_df, uploaded.name)

    @staticmethod
    def handle_raw_data_view(ai_engine: AIProvider) -> None:
        st.subheader("Raw input")
        # All columns as strings so Streamlit/Arrow does not choke on values
        # like "5 pieces" in numeric-looking columns.
        st.dataframe(
            scrub_for_display(st.session_state.raw_data),
            use_container_width=True,
        )

        if st.sidebar.button("Run AI process"):
            with st.spinner("Processing..."):
                execute_cleaning_pipeline(ai_engine, st.session_state.raw_data)

    @staticmethod
    def handle_analytics_view(ai_engine: AIProvider) -> None:
        st.subheader("Cleaned data")
        st.dataframe(st.session_state.processed_data, use_container_width=True)

        st.download_button(
            label="Download cleaned data as CSV",
            data=st.session_state.processed_data.to_csv(index=False).encode(
                "utf-8",
            ),
            file_name="cleaned_data.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("AI SQL analyst")
        query = st.text_input("Ask a question about your data:")

        if st.session_state.current_file == SAMPLE_SOURCE_ID:
            with st.expander("Sample questions for the demo dataset"):
                st.markdown(
                    """
**Revenue** — "What is the total revenue?"

**Region** — "Which region sold the most units?"

**Category** — "Show me all Electronics sales"
""",
                )

        if query:
            columns = st.session_state.processed_data.columns.tolist()
            sql_code = ai_engine.generate_sql(query, columns)
            st.code(sql_code, language="sql")
            try:
                result = run_select_query(sql_code)
                st.dataframe(result, use_container_width=True)
            except Exception as exc:
                st.error(f"SQL error: {exc}")
