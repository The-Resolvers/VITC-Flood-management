"""
LLM Extraction module — delegates to sankat.extract using Gemma / Gemini models with regex fallbacks.
"""
from typing import List, Dict, Any, Optional
from sankat.extract import extract_sos_from_text, analyze_flood_image


def extract_reports(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process messages and extract structured flood SOS data."""
    results = []
    for m in messages:
        text = m.get("text", "")
        extracted = extract_sos_from_text(text)
        is_chatter = not extracted.location_text and extracted.water_level == "unknown" and extracted.people_count == 1
        
        results.append({
            "report_id": m.get("report_id", ""),
            "location_text": extracted.location_text,
            "people_count": extracted.people_count or 1,
            "vulnerable": extracted.vulnerable_tags,
            "water_level": extracted.water_level,
            "contact": extracted.contact,
            "request_type": "chatter" if is_chatter else "rescue",
            "confidence": 0.95 if extracted.location_text else 0.70,
            "evidence": text[:100]
        })
    return results


if __name__ == "__main__":
    test = [
        {"report_id": "r1", "text": "Velachery signal pakkam 4 per irukkom. Thanni chest level. Oru paati irukkanga. 9000000001"},
        {"report_id": "r2", "text": "Stay safe everyone. Prayers for all affected."}
    ]
    import json
    print(json.dumps(extract_reports(test), indent=2))
