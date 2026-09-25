"""Start Streamlit (quality checks run inside main.py before the app loads)."""

import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "main.py"],
        check=False,
    )


if __name__ == "__main__":
    main()
