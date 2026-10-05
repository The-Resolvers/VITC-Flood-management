import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import pipeline

def fake_extract(llm_messages):
    results = []
    for m in llm_messages:
        text = m.get("text", "")
        if "chest" in text:
            results.append({"report_id": m["report_id"], "request_type": "rescue", "water_level": "chest", "location_text": "Anna Nagar"})
        elif "Prayers" in text:
            results.append({"report_id": m["report_id"], "request_type": "chatter"})
        elif "boat available" in text:
            results.append({"report_id": m["report_id"], "request_type": "info_offer"})
        elif "FAIL" in text:
            pass # Return nothing for this, should trigger extraction_failed
        else:
            results.append({"report_id": m["report_id"], "request_type": "supplies", "location_text": "Anna Nagar"})
    return results

raw_text = """12/04/25, 10:15 AM - +91 90000 00001: chest deep water here
12/04/25, 10:16 AM - +91 90000 00001: chest deep water here
12/04/25, 10:17 AM - Name: Prayers for all
12/04/25, 10:18 AM - +91 90000 00002: boat available near temple
12/04/25, 10:19 AM - Name: FAIL this one
12/04/25, 10:20 AM - +91 98765 43210: need food, call 9876543210
12/04/25, 10:21 AM - Sender No Phone: please help
"""

def run_tests():
    checks = 0
    
    captured_messages = []
    def spy_extract(llm_messages):
        captured_messages.extend(llm_messages)
        return fake_extract(llm_messages)
        
    items = pipeline.extract_items(raw_text, "test", extract_fn=spy_extract)
    
    # 1 the llm input texts contain "[PHONE]" and no raw 10-digit number
    food_msg = next(m for m in captured_messages if "food" in m["text"])
    assert "[PHONE]" in food_msg["text"], "Phone not masked"
    assert "9876543210" not in food_msg["text"], "Raw phone found"
    checks += 1
    
    # 2 contact_source is "message" for the phone-in-body item and "sender" for the sender-only item
    food_item = next(i for i in items if "food" in i.get("original_text", ""))
    assert food_item["contact"] == "+919876543210"
    assert food_item["contact_source"] == "message"
    
    chest_item = next(i for i in items if "chest" in i.get("original_text", ""))
    assert chest_item["contact"] == "+919000000001"
    assert chest_item["contact_source"] == "sender"
    checks += 1
    
    # build view
    landmarks = [{"id": "1", "name": "Anna Nagar", "lat": 13.0, "lon": 80.0, "aliases": ["anna nagar"]}]
    view = pipeline.build_view(items, landmarks, {"test-r1": "dispatched"})
    
    # 3 the invariant holds
    all_ids = set()
    for req in view["requests"]:
        all_ids.update(req["merged_ids"])
    for off in view["offers"]:
        all_ids.add(off["report_id"])
    for ch in view["chatter"]:
        all_ids.add(ch["report_id"])
    for f in view["failed"]:
        all_ids.add(f["report_id"])
    
    expected_ids = {i["report_id"] for i in items}
    assert all_ids == expected_ids, "Invariant failed"
    checks += 1
    
    # 4 the duplicate pair appears as one request with duplicate_count 1
    chest_reqs = [r for r in view["requests"] if r.get("water_level") == "chest"]
    assert len(chest_reqs) == 1
    assert chest_reqs[0]["duplicate_count"] == 1
    checks += 1
    
    # 5 requests are sorted CRITICAL first
    assert view["requests"][0]["tier"] == "CRITICAL"
    checks += 1
    
    # 6 the forced failure appears in view["failed"] and retry_failed with a working fake recovers it
    assert len(view["failed"]) == 1
    assert "FAIL" in view["failed"][0]["original_text"]
    
    def working_extract(llm_messages):
        return [{"report_id": m["report_id"], "request_type": "rescue"} for m in llm_messages]
        
    retried_items = pipeline.retry_failed(items, extract_fn=working_extract)
    assert len([i for i in retried_items if i.get("request_type") == "extraction_failed"]) == 0
    checks += 1
    
    # 7 status_map {id: "dispatched"} on one merged member makes the merged request status "dispatched"
    assert chest_reqs[0]["status"] == "dispatched"
    checks += 1
    
    # 8 offers are not in requests
    assert len(view["offers"]) == 1
    offer_ids = {o["report_id"] for o in view["offers"]}
    req_merged_ids = set()
    for r in view["requests"]:
        req_merged_ids.update(r["merged_ids"])
    assert len(offer_ids.intersection(req_merged_ids)) == 0
    checks += 1
    
    print(f"PASS {checks}")

if __name__ == "__main__":
    run_tests()
