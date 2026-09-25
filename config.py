"""Application constants and paths."""

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent
SAMPLE_EXCEL_PATH: Path = PROJECT_ROOT / "examples" / "messy_sales_example.xlsx"

LLM_MODEL: str = "mistral-small-latest"
DB_NAME: str = "sales_intelligence.db"
SALES_TABLE: str = "sales"
BATCH_SIZE: int = 10
MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
