"""SQLite persistence for cleaned sales data."""

import sqlite3

import pandas as pd

from config import DB_NAME, SALES_TABLE


def save_to_sqlite(df: pd.DataFrame, db_path: str = DB_NAME) -> None:
    """Replace the sales table with the given DataFrame."""
    with sqlite3.connect(db_path) as conn:
        df.to_sql(SALES_TABLE, conn, if_exists="replace", index=False)
