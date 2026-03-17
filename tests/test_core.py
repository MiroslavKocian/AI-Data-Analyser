import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from main import (
    AIProvider,
    Config,
    DataTransformer,
    PipelineManager,
    Repository,
    StateManager,
    UIRenderer,
)


# =============================================================================
# DataTransformer.parse_date_safely
# =============================================================================

class TestParseDateSafely:

    def test_iso_format(self):
        assert str(DataTransformer.parse_date_safely("2026-01-15")) == "2026-01-15"

    def test_european_slash(self):
        assert str(DataTransformer.parse_date_safely("15/01/2026")) == "2026-01-15"

    def test_written_month(self):
        assert str(DataTransformer.parse_date_safely("March 10, 2026")) == "2026-03-10"

    def test_dot_separator(self):
        assert str(DataTransformer.parse_date_safely("2026.04.12")) == "2026-04-12"

    def test_none_returns_none(self):
        assert DataTransformer.parse_date_safely(None) is None

    def test_empty_string_returns_none(self):
        assert DataTransformer.parse_date_safely("") is None

    def test_nan_string_returns_none(self):
        assert DataTransformer.parse_date_safely("NaN") is None

    def test_null_string_returns_none(self):
        assert DataTransformer.parse_date_safely("null") is None

    def test_none_string_returns_none(self):
        assert DataTransformer.parse_date_safely("none") is None

    def test_zero_string_returns_none(self):
        assert DataTransformer.parse_date_safely("0") is None

    def test_garbage_returns_none(self):
        assert DataTransformer.parse_date_safely("Not a date at all") is None

    def test_impossible_date_returns_none(self):
        assert DataTransformer.parse_date_safely("2026-02-30") is None

    def test_returns_date_object_not_string(self):
        import datetime
        result = DataTransformer.parse_date_safely("2026-01-15")
        assert isinstance(result, datetime.date)


# =============================================================================
# DataTransformer.scrub_for_display
# =============================================================================

class TestScrubForDisplay:

    def test_nan_string_replaced(self):
        df = pd.DataFrame({'col': ['hello', 'nan', 'NaN']})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[1]['col'] == ""
        assert result.iloc[2]['col'] == ""

    def test_none_string_replaced(self):
        df = pd.DataFrame({'col': ['ok', 'None', 'null']})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[1]['col'] == ""
        assert result.iloc[2]['col'] == ""

    def test_nat_string_replaced(self):
        df = pd.DataFrame({'col': ['2026-01-01', 'NaT']})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[1]['col'] == ""

    def test_valid_values_preserved(self):
        df = pd.DataFrame({'col': ['alpha', 'beta']})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[0]['col'] == "alpha"
        assert result.iloc[1]['col'] == "beta"

    def test_numeric_columns_become_strings(self):
        df = pd.DataFrame({'col': [1, 2, 3]})
        result = DataTransformer.scrub_for_display(df)
        assert result['col'].dtype == object

    def test_float_nan_replaced(self):
        df = pd.DataFrame({'col': [1.0, float('nan'), 3.0]})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[1]['col'] == ""

    def test_empty_dataframe_returns_empty(self):
        result = DataTransformer.scrub_for_display(pd.DataFrame())
        assert result.empty

    def test_multiple_columns(self):
        df = pd.DataFrame({'a': ['nan', 'ok'], 'b': ['None', 'val']})
        result = DataTransformer.scrub_for_display(df)
        assert result.iloc[0]['a'] == ""
        assert result.iloc[0]['b'] == ""
        assert result.iloc[1]['a'] == "ok"
        assert result.iloc[1]['b'] == "val"


# =============================================================================
# Repository
# =============================================================================

class TestRepository:

    def test_saves_rows(self, tmp_path):
        tmp = str(tmp_path / "test.db")
        df = pd.DataFrame({'col_a': [1, 2], 'col_b': ['x', 'y']})
        with patch('main.Config.DB_NAME', tmp):
            Repository.save_to_sqlite(df)
        with sqlite3.connect(tmp) as conn:
            saved = pd.read_sql("SELECT * FROM sales", conn)
        assert len(saved) == 2
        assert list(saved['col_b']) == ['x', 'y']

    def test_replaces_on_second_save(self, tmp_path):
        tmp = str(tmp_path / "test.db")
        with patch('main.Config.DB_NAME', tmp):
            Repository.save_to_sqlite(pd.DataFrame({'val': ['old1', 'old2']}))
            Repository.save_to_sqlite(pd.DataFrame({'val': ['new1']}))
        with sqlite3.connect(tmp) as conn:
            saved = pd.read_sql("SELECT * FROM sales", conn)
        assert len(saved) == 1
        assert saved.iloc[0]['val'] == 'new1'

    def test_saves_empty_dataframe(self, tmp_path):
        tmp = str(tmp_path / "test.db")
        with patch('main.Config.DB_NAME', tmp):
            Repository.save_to_sqlite(pd.DataFrame({'col': []}))  # must not raise

    def test_column_names_preserved(self, tmp_path):
        tmp = str(tmp_path / "test.db")
        df = pd.DataFrame({'First Name': ['Alice'], 'Score %': [99]})
        with patch('main.Config.DB_NAME', tmp):
            Repository.save_to_sqlite(df)
        with sqlite3.connect(tmp) as conn:
            saved = pd.read_sql("SELECT * FROM sales", conn)
        assert 'First Name' in saved.columns
        assert 'Score %' in saved.columns


# =============================================================================
# AIProvider.generate_sql
# =============================================================================

class TestGenerateSQL:

    @pytest.mark.parametrize("raw_response, expected", [
        ("```sql\nSELECT * FROM sales;\n```", "SELECT * FROM sales;"),
        ("SELECT * FROM sales WHERE x = 'y';", "SELECT * FROM sales WHERE x = 'y';"),
        ("```SELECT 1;```", "SELECT 1;"),
    ])
    def test_strips_markdown_fences(self, raw_response, expected):
        with patch('main.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = raw_response
            result = AIProvider(api_key="fake").generate_sql("show totals", ["col_a"])
            assert result.strip() == expected.strip()

    def test_column_list_reaches_prompt(self):
        with patch('main.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = "SELECT 1;"
            AIProvider(api_key="fake").generate_sql(
                "count rows", ["Alpha", "Beta", "Gamma"]
            )
            prompt = mock_openai.return_value.chat.completions.create \
                .call_args[1]['messages'][0]['content']
            assert "Alpha" in prompt
            assert "Beta" in prompt
            assert "Gamma" in prompt

    def test_user_query_reaches_prompt(self):
        with patch('main.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = "SELECT 1;"
            AIProvider(api_key="fake").generate_sql(
                "how many contracts per region", ["col"]
            )
            prompt = mock_openai.return_value.chat.completions.create \
                .call_args[1]['messages'][0]['content']
            assert "how many contracts per region" in prompt

    def test_returns_string(self):
        with patch('main.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = "SELECT 1;"
            result = AIProvider(api_key="fake").generate_sql("q", ["c"])
            assert isinstance(result, str)


# =============================================================================
# AIProvider.clean_data_with_ai
# =============================================================================

class TestCleanDataWithAI:

    def test_returns_empty_df_on_api_error(self):
        with patch('main.OpenAI') as mock_openai, patch('main.st') as mock_st:
            mock_openai.return_value.chat.completions.create.side_effect = Exception(
                "API down"
            )
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"x": "1"}])
            )
            assert result.empty
            mock_st.error.assert_called_once()

    def test_returns_dataframe_on_success(self):
        fake_content = json.dumps({"records": [{"name": "Alice", "score": "10"}]})
        with patch('main.OpenAI') as mock_openai, patch('main.st'):
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = fake_content
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"name": "Alice", "score": "10"}])
            )
            assert not result.empty
            assert "name" in result.columns

    def test_batches_large_dataframe(self):
        fake_content = json.dumps({"records": [{"Col": str(i)} for i in range(10)]})
        with patch('main.OpenAI') as mock_openai, patch('main.st'):
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = fake_content
            AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"col": str(i)} for i in range(25)])
            )
            assert mock_openai.return_value.chat.completions.create.call_count == 3

    def test_continues_after_one_batch_error(self):
        good = json.dumps({"records": [{"Col": "ok"}]})

        good_response = MagicMock()
        good_response.choices[0].message.content = good

        responses = [
            Exception("batch 1 failed"),
            good_response,
            good_response,
        ]
        with patch('main.OpenAI') as mock_openai, patch('main.st') as mock_st:
            mock_openai.return_value.chat.completions.create.side_effect = responses
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"col": str(i)} for i in range(25)])
            )
            mock_st.error.assert_called_once()
            assert not result.empty

    def test_empty_records_response_gives_empty_df(self):
        fake_content = json.dumps({"records": []})
        with patch('main.OpenAI') as mock_openai, patch('main.st'):
            mock_openai.return_value.chat.completions.create \
                .return_value.choices[0].message.content = fake_content
            result = AIProvider(api_key="fake").clean_data_with_ai(
                pd.DataFrame([{"col": "a"}])
            )
            assert result.empty


# =============================================================================
# PipelineManager
# =============================================================================

class TestPipelineManager:

    def test_calls_all_services(self):
        with patch('main.Repository.save_to_sqlite') as mock_save, \
             patch('main.DataTransformer.scrub_for_display',
                   return_value=pd.DataFrame({'x': ['clean']})), \
             patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            mock_ai = MagicMock()
            mock_ai.clean_data_with_ai.return_value = pd.DataFrame({'x': [1]})
            PipelineManager.execute_cleaning_pipeline(mock_ai, pd.DataFrame())
            mock_ai.clean_data_with_ai.assert_called_once()
            mock_save.assert_called_once()
            mock_st.success.assert_called_once_with("Analysis Ready!")

    def test_stores_result_in_session_state(self):
        scrubbed = pd.DataFrame({'x': ['clean']})
        with patch('main.Repository.save_to_sqlite'), \
             patch('main.DataTransformer.scrub_for_display', return_value=scrubbed), \
             patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            mock_ai = MagicMock()
            mock_ai.clean_data_with_ai.return_value = pd.DataFrame({'x': [1]})
            PipelineManager.execute_cleaning_pipeline(mock_ai, pd.DataFrame())
            assert mock_st.session_state.processed_data.equals(scrubbed)

    def test_raw_df_passed_to_ai(self):
        raw = pd.DataFrame({'col': ['dirty', 'data']})
        with patch('main.Repository.save_to_sqlite'), \
             patch('main.DataTransformer.scrub_for_display',
                   return_value=pd.DataFrame()), \
             patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            mock_ai = MagicMock()
            mock_ai.clean_data_with_ai.return_value = pd.DataFrame()
            PipelineManager.execute_cleaning_pipeline(mock_ai, raw)
            assert mock_ai.clean_data_with_ai.call_args[0][0].equals(raw)


# =============================================================================
# StateManager
# =============================================================================

class TestStateManager:

    def test_load_sets_raw_data(self):
        with patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            df = pd.DataFrame({'x': [1]})
            StateManager.load_new_data(df, "file.xlsx")
            assert mock_st.session_state.raw_data.equals(df)

    def test_load_clears_processed(self):
        with patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            StateManager.load_new_data(pd.DataFrame({'x': [1]}), "file.xlsx")
            assert mock_st.session_state.processed_data is None

    def test_load_sets_current_file(self):
        with patch('main.st') as mock_st:
            mock_st.session_state = MagicMock()
            StateManager.load_new_data(pd.DataFrame(), "report.xlsx")
            assert mock_st.session_state.current_file == "report.xlsx"

    def test_initialize_creates_all_keys(self):
        class FakeState(dict):
            def __getattr__(self, k):
                try: return self[k]
                except KeyError: raise AttributeError(k)
            def __setattr__(self, k, v): self[k] = v

        with patch('main.st') as mock_st:
            mock_st.session_state = FakeState()
            StateManager.initialize()
            assert mock_st.session_state['raw_data'] is None
            assert mock_st.session_state['processed_data'] is None
            assert mock_st.session_state['current_file'] is None
            assert mock_st.session_state['last_uploaded_file_id'] is None

    def test_initialize_does_not_overwrite_existing(self):
        class FakeState(dict):
            def __getattr__(self, k):
                try: return self[k]
                except KeyError: raise AttributeError(k)
            def __setattr__(self, k, v): self[k] = v

        existing = pd.DataFrame({'x': [42]})
        with patch('main.st') as mock_st:
            mock_st.session_state = FakeState({
                'raw_data': existing,
                'processed_data': None,
                'current_file': 'old.xlsx',
                'last_uploaded_file_id': 'abc123',
            })
            StateManager.initialize()
            assert mock_st.session_state['raw_data'].equals(existing)
            assert mock_st.session_state['current_file'] == 'old.xlsx'
            assert mock_st.session_state['last_uploaded_file_id'] == 'abc123'


# =============================================================================
# UIRenderer
# =============================================================================

class TestUIRenderer:

    def test_sample_questions_displayed_for_sample_data(self):
        mock_ai = MagicMock()
        with patch('main.st') as mock_st:
            mock_st.session_state.processed_data = pd.DataFrame()
            mock_st.session_state.current_file = "sample_data"

            UIRenderer.handle_analytics_view(mock_ai)

            mock_st.expander.assert_any_call(
                "📝 Sample Questions & Answers (for this dataset)"
            )

            # Verify markdown content inside
            args_list = [args[0] for args, _ in mock_st.markdown.call_args_list]
            assert any("Revenue Analysis" in str(arg) for arg in args_list)

    def test_sample_questions_hidden_for_user_files(self):
        mock_ai = MagicMock()
        with patch('main.st') as mock_st:
            mock_st.session_state.processed_data = pd.DataFrame()
            mock_st.session_state.current_file = "user_upload.xlsx"

            UIRenderer.handle_analytics_view(mock_ai)

            for args, _ in mock_st.expander.call_args_list:
                assert "Sample Questions" not in args[0]