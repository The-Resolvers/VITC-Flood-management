def calculate_priority(ext: dict) -> dict:
    """Calculate priority tier and score from extraction data."""
    WATER_ORDER = ["unknown", "ankle", "knee", "waist", "chest", "above_head_roof"]
    
    water = ext.get("water_level")
    if water not in WATER_ORDER:
        water = "unknown"
        
    vulnerable = ext.get("vulnerable")
    if vulnerable is None:
        vulnerable = []
    elif isinstance(vulnerable, str):
        vulnerable = [vulnerable]
    elif not isinstance(vulnerable, list):
        vulnerable = []
        
    hazards = ext.get("hazards")
    if hazards is None:
        hazards = []
    elif isinstance(hazards, str):
        hazards = [hazards]
    elif not isinstance(hazards, list):
        hazards = []
        
    people_val = ext.get("people_count")
    try:
        people = float(people_val)
        if people < 0 or not people.is_integer():
            people = 0
    except (ValueError, TypeError):
        people = 0
        
    rtype = ext.get("request_type")
    if rtype is None:
        rtype = ""
    else:
        rtype = str(rtype)

    water_rank = WATER_ORDER.index(water)
    
    reasons = []

    if (water in ["chest", "above_head_roof"] or
        "medical_dependency" in vulnerable or
        (any(v in vulnerable for v in ["child_infant", "pregnant", "bedridden_disabled"]) and water_rank >= 3) or
        ("live_wire" in hazards and water_rank >= 2)):
        tier = "CRITICAL"
        if water in ["chest", "above_head_roof"]:
            reasons.append("water at chest level")
        if "medical_dependency" in vulnerable:
            reasons.append("medical dependency")
        if any(v in vulnerable for v in ["child_infant", "pregnant", "bedridden_disabled"]) and water_rank >= 3:
            reasons.append("pregnant/infant/bedridden with water at waist or above")
        if "live_wire" in hazards and water_rank >= 2:
            reasons.append("live wire with water at knee or above")
    elif (water == "waist" or
          (any(v in vulnerable for v in ["elderly", "child_infant"]) and water_rank >= 2) or
          (rtype == "rescue" and water == "unknown" and len(vulnerable) > 0)):
        tier = "HIGH"
        if water == "waist":
            reasons.append("water at waist")
        if any(v in vulnerable for v in ["elderly", "child_infant"]) and water_rank >= 2:
            reasons.append("elderly or infant with water at knee or above")
        if rtype == "rescue" and water == "unknown" and len(vulnerable) > 0:
            reasons.append("rescue request with unknown water and vulnerable people")
    elif rtype in ["rescue", "medical", "supplies"]:
        tier = "MODERATE"
        reasons.append("actionable request type")
    else:
        tier = "LOW"
        reasons.append("no actionable request")

    water_pts = {"unknown": 10, "ankle": 0, "knee": 8, "waist": 18, "chest": 30, "above_head_roof": 40}.get(water, 0)
    vuln_map = {"elderly": 8, "child_infant": 10, "pregnant": 12, "bedridden_disabled": 10, "medical_dependency": 12}
    vuln_pts = min(sum(vuln_map.get(v, 0) for v in vulnerable), 25)
    people_pts = min(people * 1.5, 15)
    hazard_map = {"live_wire": 10, "structural": 8, "strong_current": 5}
    hazard_pts = min(sum(hazard_map.get(h, 0) for h in hazards), 12)
    score = min(int(water_pts + vuln_pts + people_pts + hazard_pts), 100)

    breakdown = {"water": water_pts, "vulnerable": vuln_pts, "people": people_pts, "hazards": hazard_pts}
    return {"tier": tier, "score": score, "breakdown": breakdown, "reasons": reasons}

def review_flags(ext: dict) -> list[str]:
    flags = []
    
    conf = ext.get("confidence")
    try:
        conf_val = float(conf)
    except (TypeError, ValueError):
        conf_val = None
    if conf_val is None or conf_val < 0.6:
        flags.append("low_confidence")
        
    loc = ext.get("location_text")
    if not loc or str(loc).strip() == "":
        flags.append("no_location")
        
    if loc and str(loc).strip() != "" and ext.get("lat") is None:
        flags.append("unmapped_location")
        
    if ext.get("request_type") == "rescue" and ext.get("water_level") == "unknown":
        flags.append("water_unknown")
        
    contact = ext.get("contact")
    if not contact or str(contact).strip() == "":
        flags.append("no_contact")
        
    if ext.get("escalated"):
        flags.append("escalated_by_duplicate")
        
    if ext.get("photo_conflict"):
        flags.append("photo_conflict")
        
    return flags

if __name__ == "__main__":
    test = {"report_id":"r1","request_type":"rescue","water_level":"chest","vulnerable":["elderly"],"people_count":4,"hazards":[]}
    import json
    print(json.dumps(calculate_priority(test), indent=2))
