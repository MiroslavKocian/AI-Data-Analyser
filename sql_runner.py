"""Run generated SELECT statements against the SQLite sales table."""

import sqlite3

import pandas as pd

from config import DB_NAME


def run_select_query(sql_code: str, db_path: str = DB_NAME) -> pd.DataFrame:
    """Execute a read-only SQL string and return rows as a DataFrame."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql_code, conn)
