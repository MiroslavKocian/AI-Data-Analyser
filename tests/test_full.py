"""Additional tests for full branch and edge-case coverage."""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ai_provider import AIProvider
from data_transformer import parse_date_safely, scrub_for_display
from pipeline_manager import execute_cleaning_pipeline
from repository import save_to_sqlite
from state_manager import initialize, load_new_data
from ui_renderer import UIRenderer


class TestParseDateSafelyExtended:
    def test_european_slash(self):
        assert str(parse_date_safely("15/01/2026")) == "2026-01-15"

    def test_none_returns_none(self):
        assert parse_date_safely(None) is None

    def test_empty_string_returns_none(self):
        assert parse_date_safely("") is None

    def test_garbage_returns_none(self):
        assert parse_date_safely("not a date") is None


class TestScrubExtended:
    def test_valid_values_preserved(self):
        df = pd.DataFrame({"col": ["alpha"]})
        assert scrub_for_display(df).iloc[0]["col"] == "alpha"


class TestRepositoryExtended:
    def test_replaces_on_second_save(self, tmp_path):
        db = str(tmp_path / "test.db")
        save_to_sqlite(pd.DataFrame({"val": ["old"]}), db_path=db)
        save_to_sqlite(pd.DataFrame({"val": ["new"]}), db_path=db)
        with sqlite3.connect(db) as conn:
            saved = pd.read_sql("SELECT * FROM sales", conn)
        assert len(saved) == 1


class TestAIProviderExtended:
    def test_success_single_batch(self):
        payload = json.dumps({"records": [{"name": "Alice"}]})
        with patch("ai_provider.OpenAI") as mock_openai, patch("ai_provider.st"):
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = payload
            result = AIProvider("k").clean_data_with_ai(
                pd.DataFrame([{"name": "Alice"}]),
            )
            assert not result.empty

    def test_json_decode_error(self):
        with patch("ai_provider.OpenAI") as mock_openai, patch("ai_provider.st"):
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = "not-json"
            result = AIProvider("k").clean_data_with_ai(pd.DataFrame([{"x": "1"}]))
            assert result.empty

    def test_empty_records(self):
        payload = json.dumps({"records": []})
        with patch("ai_provider.OpenAI") as mock_openai, patch("ai_provider.st"):
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = payload
            result = AIProvider("k").clean_data_with_ai(pd.DataFrame([{"x": "1"}]))
            assert result.empty

    def test_sql_prompt_reaches_model(self):
        with patch("ai_provider.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value.choices[
                0
            ].message.content = "SELECT 1;"
            AIProvider("k").generate_sql("count rows", ["Region"])
            prompt = mock_openai.return_value.chat.completions.create.call_args[1][
                "messages"
            ][0]["content"]
            assert "count rows" in prompt


class TestStateExtended:
    def test_initialize_creates_keys(self):
        class FakeState(dict):
            def __getattr__(self, key):
                return self[key]

            def __setattr__(self, key, value):
                self[key] = value

        with patch("state_manager.st") as mock_st:
            mock_st.session_state = FakeState()
            initialize()
            assert mock_st.session_state["raw_data"] is None

    def test_load_clears_processed(self):
        with patch("state_manager.st") as mock_st:
            mock_st.session_state = MagicMock()
            load_new_data(pd.DataFrame({"x": [1]}), "f.xlsx")
            assert mock_st.session_state.processed_data is None


class TestPipelineExtended:
    def test_stores_scrubbed_data(self):
        scrubbed = pd.DataFrame({"x": ["clean"]})
        with (
            patch("pipeline_manager.save_to_sqlite"),
            patch("pipeline_manager.scrub_for_display", return_value=scrubbed),
            patch("pipeline_manager.st") as mock_st,
        ):
            mock_st.session_state = MagicMock()
            mock_ai = MagicMock()
            mock_ai.clean_data_with_ai.return_value = pd.DataFrame({"x": [1]})
            execute_cleaning_pipeline(mock_ai, pd.DataFrame())
            assert mock_st.session_state.processed_data.equals(scrubbed)


class TestUIExtended:
    def test_sidebar_sample_button(self):
        with (
            patch("ui_renderer.st") as mock_st,
            patch(
                "ui_renderer.load_sample_excel",
                return_value=pd.DataFrame({"a": [1]}),
            ),
            patch("ui_renderer.load_new_data") as mock_load,
        ):
            mock_st.sidebar.button.side_effect = [True, False]
            mock_st.sidebar.file_uploader.return_value = None
            UIRenderer.handle_sidebar_ingestion()
            mock_load.assert_called_once()

    def test_sidebar_file_upload(self):
        fake_file = MagicMock()
        fake_file.file_id = "id-1"
        fake_file.name = "data.xlsx"
        with (
            patch("ui_renderer.st") as mock_st,
            patch(
                "ui_renderer.pd.read_excel",
                return_value=pd.DataFrame({"a": [1]}),
            ),
            patch("ui_renderer.load_new_data") as mock_load,
        ):
            mock_st.session_state.last_uploaded_file_id = None
            mock_st.sidebar.button.return_value = False
            mock_st.sidebar.file_uploader.return_value = fake_file
            UIRenderer.handle_sidebar_ingestion()
            mock_load.assert_called_once()

    def test_raw_view_runs_pipeline(self):
        mock_ai = MagicMock()
        with (
            patch("ui_renderer.st") as mock_st,
            patch(
                "ui_renderer.execute_cleaning_pipeline",
            ) as mock_pipe,
        ):
            mock_st.session_state.raw_data = pd.DataFrame({"a": [1]})
            mock_st.sidebar.button.return_value = True
            UIRenderer.handle_raw_data_view(mock_ai)
            mock_pipe.assert_called_once()

    def test_sample_questions_hidden_for_user_file(self):
        mock_ai = MagicMock()
        with patch("ui_renderer.st") as mock_st:
            mock_st.session_state.processed_data = pd.DataFrame()
            mock_st.session_state.current_file = "user.xlsx"
            mock_st.text_input.return_value = ""
            UIRenderer.handle_analytics_view(mock_ai)
            for args, _ in mock_st.expander.call_args_list:
                assert "Sample questions" not in args[0]
