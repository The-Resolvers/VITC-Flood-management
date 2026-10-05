def calculate_priority(ext: dict) -> dict:
    """Calculate priority tier and score from extraction data."""
    water = ext.get("water_level", "unknown")
    vulnerable = ext.get("vulnerable") or []
    hazards = ext.get("hazards") or []
    people = ext.get("people_count") or 0
    rtype = ext.get("request_type", "")

    WATER_ORDER = ["unknown", "ankle", "knee", "waist", "chest", "above_head_roof"]
    water_rank = WATER_ORDER.index(water) if water in WATER_ORDER else 0

    if (water in ["chest", "above_head_roof"] or
        "medical_dependency" in vulnerable or
        (any(v in vulnerable for v in ["child_infant", "pregnant", "bedridden_disabled"]) and water_rank >= 3) or
        ("live_wire" in hazards and water_rank >= 2)):
        tier = "CRITICAL"
    elif (water == "waist" or
          (any(v in vulnerable for v in ["elderly", "child_infant"]) and water_rank >= 2) or
          (rtype == "rescue" and water == "unknown" and len(vulnerable) > 0)):
        tier = "HIGH"
    elif rtype in ["rescue", "medical", "supplies"]:
        tier = "MODERATE"
    else:
        tier = "LOW"

    water_pts = {"unknown": 10, "ankle": 0, "knee": 8, "waist": 18, "chest": 30, "above_head_roof": 40}.get(water, 0)
    vuln_map = {"elderly": 8, "child_infant": 10, "pregnant": 12, "bedridden_disabled": 10, "medical_dependency": 12}
    vuln_pts = min(sum(vuln_map.get(v, 0) for v in vulnerable), 25)
    people_pts = min(people * 1.5, 15)
    hazard_map = {"live_wire": 10, "structural": 8, "strong_current": 5}
    hazard_pts = min(sum(hazard_map.get(h, 0) for h in hazards), 12)
    score = min(int(water_pts + vuln_pts + people_pts + hazard_pts), 100)

    breakdown = {"water": water_pts, "vulnerable": vuln_pts, "people": people_pts, "hazards": hazard_pts}
    return {"tier": tier, "score": score, "breakdown": breakdown}

if __name__ == "__main__":
    test = {"report_id":"r1","request_type":"rescue","water_level":"chest","vulnerable":["elderly"],"people_count":4,"hazards":[]}
    import json
    print(json.dumps(calculate_priority(test), indent=2))
