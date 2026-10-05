import sys
import os
from pathlib import Path

# Setup sys.path
sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

from prompts import SYS_EXTRACT

def run_tests():
    checks = 0
    # 1. contains "hazards", "live_wire" and "Examples (illustrations only"
    assert "hazards" in SYS_EXTRACT
    assert "live_wire" in SYS_EXTRACT
    assert "Examples (illustrations only" in SYS_EXTRACT
    checks += 1
    
    # 2. contains the Tamil word for water
    assert "\u0ba4\u0ba3\u0bcd\u0ba3\u0bc0\u0bb0\u0bcd" in SYS_EXTRACT
    checks += 1
    
    # 3. contains the Tamil word for waist
    assert "\u0b87\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bb3\u0bb5\u0bc1" in SYS_EXTRACT
    checks += 1
    
    # 4. no replacement character \uFFFD and no "?" followed by a placeholder
    assert "\uFFFD" not in SYS_EXTRACT
    assert "?" not in SYS_EXTRACT
    checks += 1
    
    # 5. ends with
    assert SYS_EXTRACT.endswith("No explanation. No markdown.")
    checks += 1
    
    print("PASS")

if __name__ == "__main__":
    run_tests()
