import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

from dedupe import cluster

def run_tests():
    checks = 0
    
    # 1 two Velachery reports (4 people, chest, elderly), one in Tamil text -> 1 cluster, duplicate_count 1
    r1 = {"report_id": "r1", "geo_name": "Velachery", "people_count": 4, "water_level": "chest", "vulnerable": ["elderly"], "request_type": "rescue"}
    r2 = {"report_id": "r2", "geo_name": "Velachery", "people_count": 4, "water_level": "chest", "vulnerable": ["elderly"], "request_type": "rescue"}
    res1 = cluster([r1, r2])
    assert len(res1) == 1 and res1[0]["duplicate_count"] == 1
    checks += 1
    
    # 2 a Velachery follow-up (people None, chest, elderly) joins that cluster -> duplicate_count 2
    r3 = {"report_id": "r3", "geo_name": "Velachery", "people_count": None, "water_level": "chest", "vulnerable": ["elderly"], "request_type": "rescue"}
    res2 = cluster([r1, r2, r3])
    assert len(res2) == 1 and res2[0]["duplicate_count"] == 2
    checks += 1
    
    # 3 a Velachery report with 6 people and waist water stays separate
    r4 = {"report_id": "r4", "geo_name": "Velachery", "people_count": 6, "water_level": "waist", "vulnerable": [], "request_type": "rescue"}
    res3 = cluster([r1, r4])
    assert len(res3) == 2
    checks += 1
    
    # 4 Madipakkam (waist, dialysis -> medical_dependency) and Madipakkam live-wire (knee) stay separate
    r5 = {"report_id": "r5", "geo_name": "Madipakkam", "water_level": "waist", "vulnerable": ["medical_dependency"], "request_type": "medical"}
    r6 = {"report_id": "r6", "geo_name": "Madipakkam", "water_level": "knee", "hazards": ["live_wire"], "request_type": "rescue"}
    res4 = cluster([r5, r6])
    assert len(res4) == 2
    checks += 1
    
    # 5 two Pallikaranai reports (6 people, above_head_roof, child_infant) merge
    r7 = {"report_id": "r7", "geo_name": "Pallikaranai", "people_count": 6, "water_level": "above_head_roof", "vulnerable": ["child_infant"], "request_type": "rescue"}
    r8 = {"report_id": "r8", "geo_name": "Pallikaranai", "people_count": 6, "water_level": "above_head_roof", "vulnerable": ["child_infant"], "request_type": "rescue"}
    res5 = cluster([r7, r8])
    assert len(res5) == 1
    checks += 1
    
    # 6 two reports with no location never merge
    r9 = {"report_id": "r9", "geo_name": None, "location_text": "", "people_count": 2, "request_type": "rescue"}
    r10 = {"report_id": "r10", "geo_name": None, "location_text": "", "people_count": 2, "request_type": "rescue"}
    res6 = cluster([r9, r10])
    assert len(res6) == 2
    checks += 1
    
    # 7 same message-contact and same place, people 3 vs 5 -> merged, merge_confidence "high"
    r11 = {"report_id": "r11", "geo_name": "Adyar", "people_count": 3, "contact": "999", "contact_source": "message", "request_type": "rescue"}
    r12 = {"report_id": "r12", "geo_name": "Adyar", "people_count": 5, "contact": "999", "contact_source": "message", "request_type": "rescue"}
    res7 = cluster([r11, r12])
    assert len(res7) == 1 and res7[0]["merge_confidence"] == "high"
    checks += 1
    
    # 8 same fields but ts 10 hours apart -> separate
    r13 = {"report_id": "r13", "geo_name": "Adyar", "people_count": 3, "ts": "2025-01-01T10:00:00", "request_type": "rescue"}
    r14 = {"report_id": "r14", "geo_name": "Adyar", "people_count": 3, "ts": "2025-01-01T21:00:00", "request_type": "rescue"}
    res8 = cluster([r13, r14])
    assert len(res8) == 2
    checks += 1
    
    # 9 primary water "unknown" plus member "chest" -> merged water "chest" and escalated True
    r15 = {"report_id": "r15", "geo_name": "Guindy", "water_level": "unknown", "people_count": 1, "request_type": "rescue", "location_text": "Guindy bridge"}
    r16 = {"report_id": "r16", "geo_name": "Guindy", "water_level": "chest", "people_count": 1, "request_type": "rescue"}
    res9 = cluster([r15, r16])
    assert len(res9) == 1 and res9[0]["water_level"] == "chest" and res9[0]["escalated"] is True
    checks += 1
    
    # 10 the invariant holds on a mixed list of 12 requests
    reqs = [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12]
    res10 = cluster(reqs)
    merged_ids = []
    for c in res10:
        merged_ids.extend(c["merged_ids"])
    input_ids = [r["report_id"] for r in reqs]
    assert sorted(merged_ids) == sorted(input_ids)
    assert len(set(merged_ids)) == len(input_ids)
    checks += 1
    
    print(f"PASS {checks}")

if __name__ == "__main__":
    run_tests()
