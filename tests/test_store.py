import sys
import os
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import store

def run_tests():
    checks = 0
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    os.environ["SANKAT_DB"] = temp_db
    
    try:
        store.init()
        
        # 1 add_items then load_items round-trips Tamil text unchanged
        items = [{"report_id": "r1", "text": "தமிழ்"}]
        store.add_items(items, "label1")
        loaded = store.load_items()
        assert len(loaded) == 1
        assert loaded[0]["text"] == "தமிழ்"
        checks += 1
        
        # 2 has_run is False before and True after add_items with a file_hash
        assert store.has_run("hash1") is False
        store.add_items([{"report_id": "r2", "text": "hello"}], "label2", file_hash="hash1")
        assert store.has_run("hash1") is True
        checks += 1
        
        # 3 set_status for two ids writes status and two log rows with correct old/new values
        store.set_status(["r1", "r2"], "verified", operator="op1")
        sm = store.get_status_map()
        assert sm["r1"] == "verified"
        assert sm["r2"] == "verified"
        logs = store.get_status_log()
        assert len(logs) == 2
        assert logs[0]["old_status"] == "new" and logs[0]["new_status"] == "verified"
        assert logs[1]["old_status"] == "new" and logs[1]["new_status"] == "verified"
        checks += 1
        
        # 4 an invalid status raises ValueError
        try:
            store.set_status(["r1"], "invalid_status")
            assert False, "Should raise ValueError"
        except ValueError:
            checks += 1
            
        # 5 update_item merges a patch without losing other fields
        store.update_item("r1", {"lat": 12.3})
        loaded2 = store.load_items()
        r1_item = next(i for i in loaded2 if i["report_id"] == "r1")
        assert r1_item["text"] == "தமிழ்"
        assert r1_item["lat"] == 12.3
        checks += 1
        
        # 6 clear_all empties everything
        store.clear_all()
        assert len(store.load_items()) == 0
        assert len(store.get_status_map()) == 0
        assert len(store.get_status_log()) == 0
        assert store.has_run("hash1") is False
        checks += 1
        
        print(f"PASS {checks}")
    finally:
        os.remove(temp_db)

if __name__ == "__main__":
    run_tests()
