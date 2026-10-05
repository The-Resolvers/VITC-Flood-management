import os
import tempfile
import sys
from pathlib import Path

def run_tests():
    checks = 0
    try:
        import streamlit.testing.v1 as st_test
    except ImportError:
        print("SKIP")
        return
        
    if not hasattr(st_test, "AppTest"):
        print("SKIP")
        return
        
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    os.environ["SANKAT_DB"] = temp_db
    os.environ["GEMINI_API_KEY"] = "test-key"
    
    try:
        app = st_test.AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))
        app.run()
        
        assert not app.exception, f"Exception occurred: {app.exception}"
        info_shown = any("Upload a WhatsApp export" in info.value for info in app.info)
        assert info_shown, "Info message not found"
        checks += 1
        
        print(f"PASS {checks}")
    finally:
        os.remove(temp_db)

if __name__ == "__main__":
    run_tests()
