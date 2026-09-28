"""Start Streamlit (`python run_app.py`)."""

import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "main.py"],
        check=False,
    )


if __name__ == "__main__":
    main()
