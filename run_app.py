"""Start Streamlit (`python run_app.py`)."""

import subprocess
import sys


def main() -> None:
    command = [sys.executable, "-m", "streamlit", "run", "main.py"]
    try:
        result = subprocess.run(command, check=False)
    except KeyboardInterrupt:
        # Ctrl+C: harmless Streamlit shutdown noise on Windows is OK.
        raise SystemExit(0) from None
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
