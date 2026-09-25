"""Run pytest, then start Streamlit when tests pass."""

import subprocess
import sys

import pytest


def main() -> None:
    print("\n--- Running automated tests ---\n")
    exit_code = pytest.main(["-q"])
    if exit_code != 0:
        print("\nTests failed. Application startup aborted.\n")
        sys.exit(1)

    print("\nTests passed. Starting Streamlit...\n")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "main.py"],
        check=False,
    )


if __name__ == "__main__":
    main()
