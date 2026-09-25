"""Streamlit entrypoint (`streamlit run main.py` or `python run_app.py`)."""

import os
import sys


def _should_run_startup_quality() -> bool:
    """Avoid recursive pytest when this module is imported during test runs."""
    if os.getenv("_AI_QUALITY_GATE_DONE") == "1":
        return False
    if "pytest" in sys.modules:
        return False
    return True


def run_import_time_quality_gate() -> None:
    """Run Ruff + pytest before Streamlit loads (once per server process)."""
    if not _should_run_startup_quality():
        return
    from quality_gate import run_startup_quality

    exit_code = run_startup_quality()
    if exit_code != 0:
        raise SystemExit(exit_code)
    os.environ["_AI_QUALITY_GATE_DONE"] = "1"


run_import_time_quality_gate()

from app import main

if __name__ == "__main__":
    main()
