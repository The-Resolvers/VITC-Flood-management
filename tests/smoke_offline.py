import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import pipeline
import geo
from wa_parser import parse_export

def fake_extract(messages):
    results = []
    for m in messages:
        text = m.get("text", "").lower()
        res = {
            "report_id": m["report_id"],
            "request_type": "rescue" if "help" in text or "rescue" in text else "chatter",
            "location_text": "Anna Nagar" if "anna nagar" in text else None,
            "people_count": 2 if "2" in text else None,
            "water_level": "chest" if "chest" in text else "unknown",
            "vulnerable": ["elderly"] if "elderly" in text else [],
            "hazards": ["live_wire"] if "wire" in text else []
        }
        results.append(res)
    return results

def main():
    demo_path = Path(__file__).resolve().parents[1] / "demo" / "demo_data_tn.txt"
    if not demo_path.exists():
        print("SKIP")
        return
        
    raw_text = demo_path.read_text(encoding="utf-8")
    items = pipeline.extract_items(raw_text, "demo", extract_fn=fake_extract)
    
    landmarks = geo.load_landmarks()
    view = pipeline.build_view(items, landmarks, {})
    
    assert len(items) == 53, f"Expected 53 items, got {len(items)}"
    for idx, item in enumerate(items):
        expected_id = f"demo-r{idx+1}"
        assert item["report_id"] == expected_id, f"Invalid report_id: expected {expected_id}, got {item['report_id']}"
        
    reqs = view["requests"]
    assert any(r.get("tier") == "CRITICAL" for r in reqs), "No CRITICAL request found"
    assert view["merged_total"] > 0, "No duplicate merged"
    assert reqs[0]["tier"] == "CRITICAL", "requests[0] is not CRITICAL"
    
    print(f"Total: {view['total']}, Requests: {len(reqs)}, Offers: {len(view['offers'])}, Chatter: {len(view['chatter'])}, Failed: {len(view['failed'])}, Merged: {view['merged_total']}, Critical: {sum(1 for r in reqs if r.get('tier') == 'CRITICAL')}")
    print("PASS")

if __name__ == "__main__":
    main()
