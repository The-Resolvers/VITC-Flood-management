import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import priority

def run_tests():
    checks = 0
    
    # 1 the __main__ example (chest, elderly, 4 people, rescue) -> CRITICAL, score 44, breakdown water 30, vulnerable 8, people 6.0, hazards 0
    r1 = {"report_id": "r1", "request_type": "rescue", "water_level": "chest", "vulnerable": ["elderly"], "people_count": 4, "hazards": []}
    res1 = priority.calculate_priority(r1)
    assert res1["tier"] == "CRITICAL"
    assert res1["score"] == 44
    assert res1["breakdown"] == {"water": 30, "vulnerable": 8, "people": 6.0, "hazards": 0}
    checks += 1
    
    # 2 medical_dependency only, water unknown, no people -> CRITICAL, score 22
    r2 = {"vulnerable": ["medical_dependency"]}
    res2 = priority.calculate_priority(r2)
    assert res2["tier"] == "CRITICAL"
    assert res2["score"] == 22
    checks += 1
    
    # 3 pregnant + waist -> CRITICAL; child_infant + knee -> HIGH; child_infant + waist -> CRITICAL
    res3a = priority.calculate_priority({"vulnerable": ["pregnant"], "water_level": "waist"})
    assert res3a["tier"] == "CRITICAL"
    res3b = priority.calculate_priority({"vulnerable": ["child_infant"], "water_level": "knee"})
    assert res3b["tier"] == "HIGH"
    res3c = priority.calculate_priority({"vulnerable": ["child_infant"], "water_level": "waist"})
    assert res3c["tier"] == "CRITICAL"
    checks += 1
    
    # 4 elderly + knee (rescue) -> HIGH; elderly + ankle (rescue) -> MODERATE
    res4a = priority.calculate_priority({"vulnerable": ["elderly"], "water_level": "knee", "request_type": "rescue"})
    assert res4a["tier"] == "HIGH"
    res4b = priority.calculate_priority({"vulnerable": ["elderly"], "water_level": "ankle", "request_type": "rescue"})
    assert res4b["tier"] == "MODERATE"
    checks += 1
    
    # 5 live_wire + knee -> CRITICAL; live_wire + ankle (rescue) -> MODERATE
    res5a = priority.calculate_priority({"hazards": ["live_wire"], "water_level": "knee"})
    assert res5a["tier"] == "CRITICAL"
    res5b = priority.calculate_priority({"hazards": ["live_wire"], "water_level": "ankle", "request_type": "rescue"})
    assert res5b["tier"] == "MODERATE"
    checks += 1
    
    # 6 rescue + unknown + ["elderly"] -> HIGH; rescue + unknown + [] -> MODERATE
    res6a = priority.calculate_priority({"request_type": "rescue", "water_level": "unknown", "vulnerable": ["elderly"]})
    assert res6a["tier"] == "HIGH"
    res6b = priority.calculate_priority({"request_type": "rescue", "water_level": "unknown", "vulnerable": []})
    assert res6b["tier"] == "MODERATE"
    checks += 1
    
    # 7 supplies -> MODERATE; chatter -> LOW; info_offer -> LOW
    res7a = priority.calculate_priority({"request_type": "supplies"})
    assert res7a["tier"] == "MODERATE"
    res7b = priority.calculate_priority({"request_type": "chatter"})
    assert res7b["tier"] == "LOW"
    res7c = priority.calculate_priority({"request_type": "info_offer"})
    assert res7c["tier"] == "LOW"
    checks += 1
    
    # 8 people_count "4" counts as 4; "abc" counts as 0; vulnerable "elderly" works as ["elderly"]; {} returns tier LOW without raising
    res8a = priority.calculate_priority({"people_count": "4"})
    assert res8a["breakdown"]["people"] == 6.0
    res8b = priority.calculate_priority({"people_count": "abc"})
    assert res8b["breakdown"]["people"] == 0
    res8c = priority.calculate_priority({"vulnerable": "elderly"})
    assert res8c["breakdown"]["vulnerable"] == 8
    res8d = priority.calculate_priority({})
    assert res8d["tier"] == "LOW"
    checks += 1
    
    # 9 reasons is a non-empty list for every tier
    assert len(res1["reasons"]) > 0
    assert len(res2["reasons"]) > 0
    assert len(res4a["reasons"]) > 0
    assert len(res7a["reasons"]) > 0
    assert len(res7b["reasons"]) > 0
    checks += 1
    
    # 10 review_flags returns the expected flags for a low-confidence, unmapped, no-contact rescue
    flags = priority.review_flags({
        "confidence": 0.5,
        "location_text": "Somewhere",
        "lat": None,
        "request_type": "rescue",
        "water_level": "unknown",
        "contact": None
    })
    expected = ["low_confidence", "unmapped_location", "water_unknown", "no_contact"]
    assert flags == expected, f"Expected {expected}, got {flags}"
    checks += 1
    
    print(f"PASS {checks}")

if __name__ == "__main__":
    run_tests()
