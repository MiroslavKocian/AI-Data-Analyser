"""Application constants and paths."""

from pathlib import Path

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = PACKAGE_ROOT.parent
SAMPLE_EXCEL_PATH: Path = REPO_ROOT / "examples" / "messy_sales_example.xlsx"

# Groq free-tier limits: https://console.groq.com/docs/rate-limits
LLM_MODEL: str = "openai/gpt-oss-20b"
LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
DB_NAME: str = "sales_intelligence.db"
SALES_TABLE: str = "sales"
BATCH_SIZE: int = 10
