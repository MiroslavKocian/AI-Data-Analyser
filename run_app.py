import subprocess
import sys

def main():
    print("\n🧪 --- RUNNING AUTOMATED TESTS ---")
    # Run pytest using the current Python interpreter
    test_result = subprocess.run([sys.executable, "-m", "pytest"])
    
    # If tests fail (return code is not 0), stop everything
    if test_result.returncode != 0:
        print("\n❌ TESTS FAILED. Application startup aborted.")
        sys.exit(1)
        
    print("\n✅ TESTS PASSED. Starting application...\n")
    print("🚀 --- LAUNCHING STREAMLIT ---")
    # Run Streamlit using the current Python interpreter
    subprocess.run([sys.executable, "-m", "streamlit", "run", "main.py"])

if __name__ == "__main__":
    main()