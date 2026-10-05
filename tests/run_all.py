import sys
import subprocess
from pathlib import Path

def main():
    test_dir = Path(__file__).parent
    test_files = list(test_dir.glob("test_*.py")) + [test_dir / "smoke_offline.py"]
    
    any_failed = False
    for f in sorted(test_files):
        if not f.exists():
            continue
        try:
            res = subprocess.run([sys.executable, str(f)], capture_output=True, text=True, check=True)
            print(f"PASS {f.name}")
        except subprocess.CalledProcessError as e:
            print(f"FAIL {f.name}")
            print("--- STDOUT ---")
            print(e.stdout)
            print("--- STDERR ---")
            print(e.stderr)
            any_failed = True
            
    if any_failed:
        print("Summary: SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("Summary: ALL TESTS PASSED")

if __name__ == "__main__":
    main()
