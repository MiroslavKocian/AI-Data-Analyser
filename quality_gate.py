"""Run Ruff and pytest before starting Streamlit."""

import subprocess
import sys

import pytest


def run_startup_quality() -> int:
    """
    Run the same checks as GitHub Actions (Ruff + pytest with coverage).

    Returns a process exit code (0 means all checks passed).
    """
    lint_steps = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
    ]
    for command in lint_steps:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode

    return int(pytest.main(["-q"]))
