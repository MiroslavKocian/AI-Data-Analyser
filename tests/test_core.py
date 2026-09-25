"""Unit tests for application modules (no real LLM or Streamlit runtime)."""

import datetime
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ai_provider import (
    AIProvider,
    build_cleaning_prompt,
    build_sql_prompt,
    strip_sql_markdown,
)
from app import main as app_main
from data_transformer import parse_date_safely, scrub_for_display
from pipeline_manager import execute_cleaning_pipeline
from repository import save_to_sqlite
from sample_loader import load_sample_excel
from sql_runner import run_select_query
from startup import (
    bootstrap_application,
    require_groq_api_key,
    resolve_groq_api_key,
)
from state_manager import initialize, load_new_data
from ui_renderer import SAMPLE_SOURCE_ID, UIRenderer


class TestParseDateSafely:
    def test_iso_format(self):
        assert str(parse_date_safely("2026-01-15")) == "2026-01-15"

    def test_impossible_date_returns_none(self):
        assert parse_date_safely("2026-02-30") is None

    def test_returns_date_object(self):
        assert isinstance(parse_date_safely("2026-01-15"), datetime.date)


class TestScrubForDisplay:
    def test_nan_string_replaced(self):
        df = pd.DataFrame({"col": ["hello", "nan"]})
        result = scrub_for_display(df)
        assert result.iloc[1]["col"] == ""


class TestRepository:
    def test_saves_rows(self, tmp_path):
        db = str(tmp_path / "test.db")
        save_to_sqlite(pd.DataFrame({"col_a": [1], "col_b": ["x"]}), db_path=db)
        with sqlite3.connect(db) as conn:
            saved = pd.read_sql("SELECT * FROM sales", conn)
        assert len(saved) == 1


class TestGenerateSQL:
    @pytest.mark.parametrize(
        "raw_response, expected",
        [
            ("```sql\nSELECT 1;\n```", "SELECT 1;"),
            ("SELECT 1;", "SELECT 1;"),
        ],
    )
    def test_strips_markdown_fences(self, raw_response, expected):
        with patch("ai_provider.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = raw_response
            result = AIProvider(api_key="fake").generate_sql("q", ["col"])
            assert result.strip() == expected.strip()


class TestCleanDataWithAI:
    def test_returns_empty_df_on_api_error(self):
        with patch("ai_provider.OpenAI") as mock_openai, patch("ai_provider.st"):
            mock_openai.return_value.chat.completions.create.side_effect = Exception(
                "API down",
            )
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"x": "1"}]),
            )
            assert result.empty

    def test_concatenates_multiple_batches(self):
        payload = json.dumps({"records": [{"col": "a"}]})
        with patch("ai_provider.OpenAI") as mock_openai, patch("ai_provider.st"):
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = payload
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"col": str(i)} for i in range(11)]),
            )
            assert len(result) == 2


class TestPromptHelpers:
    def test_build_cleaning_prompt_contains_columns(self):
        prompt = build_cleaning_prompt(["Date", "Amount"], [{"Date": "1"}])
        assert "Date" in prompt and "Amount" in prompt

    def test_build_sql_prompt_contains_query(self):
        prompt = build_sql_prompt("total sales", ["Region"])
        assert "total sales" in prompt

    def test_strip_sql_markdown(self):
        assert strip_sql_markdown("```sql\nSELECT 1\n```").strip() == "SELECT 1"


class TestPipelineManager:
    def test_calls_all_services(self):
        with (
            patch("pipeline_manager.save_to_sqlite") as mock_save,
            patch(
                "pipeline_manager.scrub_for_display",
                return_value=pd.DataFrame({"x": ["clean"]}),
            ),
            patch("pipeline_manager.st") as mock_st,
        ):
            mock_st.session_state = MagicMock()
            mock_ai = MagicMock()
            mock_ai.clean_data_with_ai.return_value = pd.DataFrame({"x": [1]})
            execute_cleaning_pipeline(mock_ai, pd.DataFrame())
            mock_save.assert_called_once()


class TestStateManager:
    def test_load_sets_raw_data(self):
        with patch("state_manager.st") as mock_st:
            mock_st.session_state = MagicMock()
            df = pd.DataFrame({"x": [1]})
            load_new_data(df, "file.xlsx")
            assert mock_st.session_state.raw_data.equals(df)


class TestStartup:
    def test_resolve_from_env(self):
        with (
            patch("startup.load_dotenv"),
            patch.dict(
                "os.environ",
                {"GROQ_API_KEY": "from-env"},
                clear=False,
            ),
        ):
            assert resolve_groq_api_key() == "from-env"

    def test_resolve_from_secrets(self):
        with (
            patch("startup.load_dotenv"),
            patch.dict(
                "os.environ",
                {},
                clear=True,
            ),
        ):
            with patch("startup.st") as mock_st:
                mock_st.secrets.get.return_value = "from-secrets"
                assert resolve_groq_api_key() == "from-secrets"

    def test_resolve_returns_none_when_missing(self):
        with patch("startup.load_dotenv"), patch.dict("os.environ", {}, clear=True):
            with patch("startup.st") as mock_st:
                mock_st.secrets.get.side_effect = KeyError("missing")
                assert resolve_groq_api_key() is None

    def test_require_returns_key_when_present(self):
        with patch("startup.resolve_groq_api_key", return_value="secret-key"):
            assert require_groq_api_key() == "secret-key"

    def test_require_stops_when_missing(self):
        with (
            patch("startup.resolve_groq_api_key", return_value=None),
            patch(
                "startup.st",
            ) as mock_st,
        ):
            mock_st.stop.side_effect = SystemExit
            with pytest.raises(SystemExit):
                require_groq_api_key()
            mock_st.error.assert_called_once()

    def test_bootstrap_returns_provider(self):
        with (
            patch("startup.require_groq_api_key", return_value="key"),
            patch(
                "startup.initialize",
            ),
            patch("startup.AIProvider") as mock_provider,
        ):
            bootstrap_application()
            mock_provider.assert_called_once_with("key")


class TestSampleLoader:
    def test_load_sample_excel(self):
        df = load_sample_excel()
        assert not df.empty
        assert "Date" in df.columns


class TestSqlRunner:
    def test_run_select_query(self, tmp_path):
        db = str(tmp_path / "test.db")
        save_to_sqlite(pd.DataFrame({"val": [7]}), db_path=db)
        result = run_select_query("SELECT val FROM sales", db_path=db)
        assert result.iloc[0]["val"] == 7


class TestUIRenderer:
    def test_setup_page(self):
        with patch("ui_renderer.st") as mock_st:
            UIRenderer.setup_page()
            mock_st.set_page_config.assert_called_once()

    def test_sample_questions_for_sample_data(self):
        mock_ai = MagicMock()
        with patch("ui_renderer.st") as mock_st:
            mock_st.session_state.processed_data = pd.DataFrame()
            mock_st.session_state.current_file = SAMPLE_SOURCE_ID
            UIRenderer.handle_analytics_view(mock_ai)
            mock_st.expander.assert_called()

    def test_sql_query_success(self):
        mock_ai = MagicMock()
        mock_ai.generate_sql.return_value = "SELECT 1 AS one"
        with (
            patch("ui_renderer.st") as mock_st,
            patch(
                "ui_renderer.run_select_query",
                return_value=pd.DataFrame({"one": [1]}),
            ),
        ):
            mock_st.session_state.processed_data = pd.DataFrame({"a": [1]})
            mock_st.session_state.current_file = "user.xlsx"
            mock_st.text_input.return_value = "count"
            UIRenderer.handle_analytics_view(mock_ai)
            mock_st.dataframe.assert_called()

    def test_sql_query_error(self):
        mock_ai = MagicMock()
        mock_ai.generate_sql.return_value = "BAD SQL"
        with (
            patch("ui_renderer.st") as mock_st,
            patch(
                "ui_renderer.run_select_query",
                side_effect=Exception("syntax"),
            ),
        ):
            mock_st.session_state.processed_data = pd.DataFrame({"a": [1]})
            mock_st.session_state.current_file = "user.xlsx"
            mock_st.text_input.return_value = "q"
            UIRenderer.handle_analytics_view(mock_ai)
            mock_st.error.assert_called()


class TestAppMain:
    def test_main_renders_flow(self):
        with (
            patch("app.UIRenderer.setup_page"),
            patch("app.bootstrap_application", return_value=MagicMock()),
            patch("app.UIRenderer.handle_sidebar_ingestion"),
            patch("app.st") as mock_st,
        ):
            mock_st.session_state.raw_data = None
            mock_st.session_state.processed_data = None
            app_main()
            mock_st.session_state.raw_data = pd.DataFrame({"a": [1]})
            mock_st.session_state.processed_data = pd.DataFrame({"a": [1]})
            app_main()
