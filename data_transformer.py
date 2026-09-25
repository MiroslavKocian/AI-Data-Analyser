"""Display helpers and local date parsing (non-LLM)."""

from datetime import date

import pandas as pd
from dateutil import parser
from dateutil.parser import ParserError

_EMPTY_TOKENS: frozenset[str] = frozenset(
    {"nan", "none", "null", "", "0"},
)


def parse_date_safely(value: object) -> date | None:
    """Parse a messy date string, or return None when missing or invalid."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _EMPTY_TOKENS:
        return None
    try:
        return parser.parse(text).date()
    except (ValueError, TypeError, OverflowError, ParserError):
        return None


def scrub_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Show empty cells as blank strings in Streamlit tables."""
    return df.astype(str).replace(
        ["nan", "NaN", "None", "NaT", "null"],
        "",
    )
