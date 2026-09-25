"""Mistral LLM calls for data cleaning and natural-language SQL."""

import json
import logging

import pandas as pd
import streamlit as st
from openai import OpenAI

from config import BATCH_SIZE, LLM_MODEL, MISTRAL_BASE_URL

logger = logging.getLogger(__name__)


def build_cleaning_prompt(schema_columns: list[str], input_data: list[dict]) -> str:
    """Build the batch-cleaning prompt sent to the LLM."""
    columns_text = ", ".join(schema_columns)
    return f"""
Clean and structure this data into a valid JSON object following these rules:
1. The output MUST be a JSON object with a single key 'records', containing a list
   of objects.
2. Each object in the list MUST use these exact keys, unchanged: {columns_text}.
3. Date columns: Parse dates and format as YYYY-MM-DD. If invalid/missing, use null.
4. Numeric columns: Strip currency symbols and units, keep only the number
   (e.g., '$1,200.50' -> 1200.50, '15 units' -> 15). If non-numeric or missing,
   use null.
5. All other columns: If a value is empty or missing (like 'N/A', 'n/a', '-',
   ''), use null. Do not change, guess, or reformat the data in any other way.

INPUT DATA: {json.dumps(input_data)}

Return ONLY the JSON object.
"""


def build_sql_prompt(user_query: str, columns: list[str]) -> str:
    """Build the natural-language-to-SQL prompt."""
    return f"""
Act as an expert SQLite Data Analyst.
Table 'sales' has columns: {columns}.

Goal: Generate a valid SQLite SELECT query to answer: "{user_query}"

Guidelines:
1. For questions about trends or changes over time, SELECT the Date and the
   relevant metric column, and ORDER BY Date. Do NOT attempt to calculate
   row-by-row differences unless explicitly requested.
2. Column names with spaces or special characters (like %, $) MUST be enclosed
   in double quotes (e.g., "Unit Price", "Voda %").
3. If a JOIN is strictly necessary, EVERY column in the SELECT clause MUST be
   prefixed with its table alias to avoid ambiguity.
4. Return ONLY the raw SQL string (no markdown, no explanations).
"""


def strip_sql_markdown(raw_sql: str) -> str:
    """Remove markdown fences models sometimes add around SQL."""
    return raw_sql.strip().replace("```sql", "").replace("```", "")


class AIProvider:
    """OpenAI-compatible client pointed at Mistral."""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key, base_url=MISTRAL_BASE_URL)

    def clean_data_with_ai(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize messy rows via the LLM in fixed-size batches."""
        schema_columns = [str(column).strip() for column in df.columns]
        cleaned_frames: list[pd.DataFrame] = []
        total_rows = len(df)
        progress_bar = st.progress(0.0, text="AI is analyzing data batches...")

        for start in range(0, total_rows, BATCH_SIZE):
            chunk = df.iloc[start : start + BATCH_SIZE]
            input_data = (
                chunk.astype(str)
                .replace(["N/A", "n/a", "nan", "NaN"], "")
                .to_dict(orient="records")
            )
            prompt = build_cleaning_prompt(schema_columns, input_data)
            try:
                response = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=LLM_MODEL,
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
                records = json.loads(content).get("records", [])
                if records:
                    cleaned_frames.append(
                        pd.DataFrame(records, columns=schema_columns),
                    )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                logger.warning("Batch JSON parse failed: %s", exc)
                st.error(f"Batch processing error: {exc}")
            except Exception as exc:
                logger.exception("Batch LLM call failed: %s", exc)
                st.error(f"Batch processing error: {exc}")

            if total_rows > 0:
                progress_bar.progress(
                    min((start + BATCH_SIZE) / total_rows, 1.0),
                )

        progress_bar.empty()
        if cleaned_frames:
            return pd.concat(cleaned_frames, ignore_index=True)
        return pd.DataFrame(columns=schema_columns)

    def generate_sql(self, user_query: str, columns: list[str]) -> str:
        """Return a single SELECT statement for the user question."""
        prompt = build_sql_prompt(user_query, columns)
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
        )
        raw = response.choices[0].message.content or ""
        return strip_sql_markdown(raw)
