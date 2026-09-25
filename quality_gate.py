"""Run Ruff and pytest before starting Streamlit."""

import subprocess
import sys


def run_startup_quality() -> int:
    """
    Run the same checks as GitHub Actions (Ruff + pytest with coverage).

    Uses a subprocess for pytest so coverage is not skewed when this runs
    from main.py before Streamlit starts (for example in Docker).

    Returns a process exit code (0 means all checks passed).
    """
    steps = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    for command in steps:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0
