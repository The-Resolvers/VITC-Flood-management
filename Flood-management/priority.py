"""
Priority calculation module — delegates to sankat.priority PriorityEngine.
"""
from sankat.priority import priority_engine, PriorityEngine


def calculate_priority(ext: dict) -> dict:
    """Calculate priority tier and score using SANKAT's deterministic priority engine."""
    water = ext.get("water_level", "unknown")
    vulnerable = ext.get("vulnerable") or []
    people = ext.get("people_count") or 1
    dupe_count = ext.get("duplicate_count", 0)

    score, tier = priority_engine.calculate(
        water_level=water,
        people_count=people,
        vulnerable_tags=vulnerable,
        duplicate_count=dupe_count
    )

    water_pts = priority_engine.water_weights.get(water, 10)
    vuln_pts = sum(priority_engine.vulnerability_weights.get(str(v).lower(), 10) for v in vulnerable)
    people_pts = min(priority_engine.people_cap, int((people or 1) * priority_engine.people_multiplier))
    breakdown = {
        "water": water_pts,
        "vulnerable": vuln_pts,
        "people": people_pts,
        "hazards": 0
    }

    return {"tier": tier, "score": score, "breakdown": breakdown}


if __name__ == "__main__":
    test = {
        "report_id": "r1",
        "request_type": "rescue",
        "water_level": "chest",
        "vulnerable": ["elderly"],
        "people_count": 4,
        "hazards": []
    }
    import json
    print(json.dumps(calculate_priority(test), indent=2))
