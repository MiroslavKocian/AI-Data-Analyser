"""Load the built-in messy Excel demo file."""

from pathlib import Path

import pandas as pd

from config import SAMPLE_EXCEL_PATH


def load_sample_excel(path: Path | None = None) -> pd.DataFrame:
    """Read the repository sample workbook for the demo button."""
    file_path = path or SAMPLE_EXCEL_PATH
    return pd.read_excel(file_path, keep_default_na=False)
