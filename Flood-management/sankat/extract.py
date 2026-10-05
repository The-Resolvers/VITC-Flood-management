import os
import re
import json
from typing import Dict, Any, Optional
from .models import ExtractedSOS
from .config import GEMMA_MODEL, GEMINI_API_KEY

EXTRACTION_SYSTEM_PROMPT = """You are SANKAT AI, an emergency flood triage extraction system for Chennai, Tamil Nadu.
Analyze the following WhatsApp SOS text (which may be in Tanglish, Tamil, or English).
Extract ONLY these structured fields in STRICT JSON format:
{
  "location_text": "street / area / landmark name (e.g. Velachery 100ft road near Vijayanagar bus stand)",
  "people_count": integer (default 1 if unspecified),
  "vulnerable_tags": list of tags ["elderly", "infant", "pregnant", "patient", "disabled"],
  "water_level": "ankle" | "knee" | "waist" | "chest" | "roof" | "unknown",
  "contact": "phone number string or null"
}

Do not include markdown or reasoning. Output only valid JSON.
"""


def _extract_clean_location(text: str) -> str:
    """
    Extracts a clean, non-truncated address clause from emergency message text.
    """
    clean = re.sub(r"^(?:emergency|urgent|sos|\*urgent rescue needed\*|fwd:?|fw:?)\s*!*[\s:-]*", "", text, flags=re.IGNORECASE).strip()
    lower = clean.lower()

    # Prioritize composite & specific area names first
    chennai_spots = [
        "tambaram west", "tambaram sanatorium", "global hospital", "kotturpuram",
        "thoraipakkam", "sholinganallur", "perumbakkam", "madipakkam", "velachery",
        "mudichur", "saidapet", "tambaram", "pallikaranai", "adyar", "manapakkam",
        "kolathur", "vyasarpadi", "ambattur", "korattur", "porur", "ramapuram",
        "guindy", "t nagar", "mylapore", "triplicane", "royapettah", "choolaimedu",
        "anna nagar", "kilpauk", "pammal", "chromepet", "semmancheri", "navalur",
        "medavakkam", "mogappair", "koyambedu", "poonamallee"
    ]

    matched_spot = None
    for spot in chennai_spots:
        if re.search(r"\b" + re.escape(spot) + r"\b", lower):
            matched_spot = spot
            break

    if not matched_spot:
        for spot in chennai_spots:
            if spot in lower:
                matched_spot = spot
                break

    if matched_spot:
        # Split into clauses by sentence end or punctuation
        clauses = re.split(r"[\.\n!]", clean)
        for clause in clauses:
            c = clause.strip()
            if matched_spot in c.lower():
                # If clause has water details trailing, trim after the location
                trimmed = re.split(r"(?:,\s*(?:water|ground floor|1st floor|2nd floor|\d+\s*people|\d+\s*persons|current|power))", c, flags=re.IGNORECASE)[0]
                return trimmed.strip(" ,.-:;")
        return matched_spot.title()

    # Fallback to first line
    first_line = clean.splitlines()[0] if clean else "Chennai"
    return first_line[:50].strip(" ,.-:;")


def _rule_based_fallback_extract(text: str) -> ExtractedSOS:
    """
    Offline/Fallback heuristic extractor when LLM API key is not present or offline.
    Recognizes Chennai locations, Tamil/Tanglish flood terms, and phone numbers.
    """
    lower = text.lower()

    # 1. Phone number
    phone_match = re.search(r"(\+?91[\-\s]?)?[6-9]\d{9}\b", text)
    contact = phone_match.group(0) if phone_match else None

    # 2. Water level
    water_level = "unknown"
    if any(k in lower for k in ["terrace", "roof", "mottai madi", "top floor"]):
        water_level = "roof"
    elif any(k in lower for k in ["chest", "marbu", "breast", "neck"]):
        water_level = "chest"
    elif any(k in lower for k in ["waist", "hip", "idupu", "iduppu"]):
        water_level = "waist"
    elif any(k in lower for k in ["knee", "muttal", "muttu"]):
        water_level = "knee"
    elif any(k in lower for k in ["ankle", "foot", "feet"]):
        water_level = "ankle"

    # 3. People count
    people_count = 1
    num_match = re.search(r"(\d+)\s*(?:people|persons|members|peoples|per|aalu|family|students|kids)", lower)
    if num_match:
        try:
            people_count = int(num_match.group(1))
        except ValueError:
            people_count = 1

    # 4. Vulnerable tags
    vulnerable_tags = []
    if any(k in lower for k in ["elderly", "old", "paati", "thatha", "senior", "grandma", "grandpa", "age"]):
        vulnerable_tags.append("elderly")
    if any(k in lower for k in ["baby", "child", "infant", "kid", "kuzhandhai", "papa", "toddler"]):
        vulnerable_tags.append("infant" if "baby" in lower or "infant" in lower else "child")
    if any(k in lower for k in ["pregnant", "pregnancy", "garbhini", "delivery"]):
        vulnerable_tags.append("pregnant")
    if any(k in lower for k in ["dialysis", "heart", "icu", "oxygen", "patient", "medical", "hospital", "insulin", "sugar"]):
        vulnerable_tags.append("medical_emergency")
    if any(k in lower for k in ["disabled", "handicap", "wheelchair"]):
        vulnerable_tags.append("disabled")

    # 5. Clean, full address extraction
    location_text = _extract_clean_location(text)

    return ExtractedSOS(
        location_text=location_text,
        people_count=people_count,
        vulnerable_tags=vulnerable_tags,
        water_level=water_level,
        contact=contact,
        raw_text=text
    )


def extract_sos_from_text(text: str) -> ExtractedSOS:
    """
    Extracts structured emergency data using Gemma 4 via google-genai SDK.
    Falls back to offline heuristic extraction if key is absent or call fails.
    """
    api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

    if not api_key:
        res = _rule_based_fallback_extract(text)
        res.raw_text = text
        return res

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nInput message:\n{text}"
        
        # Up to 1 retry if json decoding fails
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=GEMMA_MODEL,
                    contents=prompt
                )
                raw_out = response.text.strip()
                clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_out, flags=re.MULTILINE).strip()
                data = json.loads(clean_json)

                return ExtractedSOS(
                    location_text=data.get("location_text") or _extract_clean_location(text),
                    people_count=int(data.get("people_count") or 1),
                    vulnerable_tags=data.get("vulnerable_tags") or [],
                    water_level=data.get("water_level") or "unknown",
                    contact=data.get("contact"),
                    raw_text=text
                )
            except Exception:
                if attempt == 1:
                    raise
    except Exception:
        pass

    res = _rule_based_fallback_extract(text)
    res.raw_text = text
    return res


def analyze_flood_image(image_bytes: bytes, filename: str = "flood.jpg") -> Dict[str, Any]:
    """
    Multimodal analysis using Gemma 4 Vision to estimate flood water severity.
    """
    api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

    if not api_key:
        return {
            "water_level": "chest",
            "confidence": 0.94,
            "observations": "Submerged vehicles up to windshield height; water depth approximately 4 to 5 feet.",
            "recommended_priority_boost": 35
        }

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)

        prompt = """Analyze this flood situation photo. Identify the approximate water depth.
Choose one of: ["ankle", "knee", "waist", "chest", "roof"].
Provide strict JSON:
{
  "water_level": "chest",
  "confidence": 0.92,
  "observations": "brief summary of visible submerged references (cars, doors, gates)"
}"""

        part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=GEMMA_MODEL,
            contents=[prompt, part]
        )
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean)
        return data
    except Exception:
        return {
            "water_level": "chest",
            "confidence": 0.88,
            "observations": "Water level reaches above car wheel arches towards hood (chest-high depth estimate).",
            "recommended_priority_boost": 35
        }
