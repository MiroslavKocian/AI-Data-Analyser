"""Run validated read-only SELECT statements against SQLite."""

import re
import sqlite3
from pathlib import Path

import pandas as pd

from ai_data_analyser.config import DB_NAME

_FORBIDDEN_KEYWORD_PATTERN = re.compile(
    r"\b("
    r"ATTACH|ALTER|CREATE|DELETE|DROP|INSERT|PRAGMA|UPDATE|"
    r"VACUUM|REINDEX|TRUNCATE"
    r")\b",
    re.IGNORECASE,
)
_SELECT_START_PATTERN = re.compile(r"^(WITH\b.+)?SELECT\b", re.IGNORECASE | re.DOTALL)


class SqlValidationError(ValueError):
    """Raised when generated SQL fails read-only SELECT validation."""


def _remove_sql_comments(sql: str) -> str:
    """Strip block and line comments before validation."""
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    lines: list[str] = []
    for line in without_block.splitlines():
        if "--" in line:
            line = line[: line.index("--")]
        lines.append(line)
    return "\n".join(lines)


def normalize_sql(sql_code: str) -> str:
    """Collapse whitespace and remove a single trailing semicolon."""
    cleaned = _remove_sql_comments(sql_code.strip())
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    if collapsed.endswith(";"):
        collapsed = collapsed[:-1].strip()
    return collapsed


def validate_read_only_select(sql_code: str) -> str:
    """
    Accept exactly one read-only SELECT (optional WITH … SELECT).

    Returns normalized SQL for execution.
    """
    normalized = normalize_sql(sql_code)
    if not normalized:
        raise SqlValidationError("SQL is empty.")
    if ";" in normalized:
        raise SqlValidationError("Only one SQL statement is allowed.")
    if _FORBIDDEN_KEYWORD_PATTERN.search(normalized):
        raise SqlValidationError("SQL contains disallowed keywords.")
    if not _SELECT_START_PATTERN.match(normalized):
        raise SqlValidationError("Only SELECT queries are allowed.")
    return normalized


def _read_only_database_uri(db_path: str) -> str:
    resolved = Path(db_path).resolve()
    return f"file:{resolved.as_posix()}?mode=ro"


def run_select_query(sql_code: str, db_path: str = DB_NAME) -> pd.DataFrame:
    """Execute a validated SELECT and return rows as a DataFrame."""
    validated_sql = validate_read_only_select(sql_code)
    uri = _read_only_database_uri(db_path)
    with sqlite3.connect(uri, uri=True) as conn:
        return pd.read_sql_query(validated_sql, conn)
