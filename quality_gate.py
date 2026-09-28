"""Run Ruff and pytest locally (same steps as GitHub Actions)."""

import subprocess
import sys


def run_quality_checks() -> int:
    """
    Run the same checks as GitHub Actions (Ruff + pytest with coverage).

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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_quality_checks())
