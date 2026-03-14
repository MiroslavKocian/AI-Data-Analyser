import subprocess
import sys

import pytest


def main():
    print("\n🧪 --- RUNNING AUTOMATED TESTS ---")

    exit_code = pytest.main(["-v"])

    if exit_code != 0:
        print("\n❌ TESTS FAILED. Application startup aborted.")
        sys.exit(1)

    print("\n✅ TESTS PASSED. Starting application...\n")
    print("🚀 --- LAUNCHING STREAMLIT ---")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "main.py"])


if __name__ == "__main__":
    main()