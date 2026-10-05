import os
import json
import io
from PIL import Image

SYS_VISION = "You analyze one flood photo. Output ONLY one JSON object with keys: water_level (one of unknown, ankle, knee, waist, chest, above_head_roof), hazards (list from live_wire, structural, strong_current), confidence (0.0-1.0), evidence (one short sentence). Judge water depth only against visible reference objects (people, cars, doors, steps, poles). If no reference object is visible, water_level is unknown. Use null or [] when unsure. No markdown. Output ONLY a raw JSON object. Do not include markdown formatting, code fences, or any conversational text. Use this exact schema: {\"water_level\": string, \"hazards\": [string], \"people_visible\": int or null, \"confidence\": float}."

WATER_LEVELS = ["unknown", "ankle", "knee", "waist", "chest", "above_head_roof"]
HAZARDS = ["live_wire", "structural", "strong_current"]

def analyze_photo(image_bytes: bytes, mime_type: str, client=None) -> dict:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        
        img = Image.open(io.BytesIO(image_bytes))
        
        max_size = 1024
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size))
            
        out_bytes = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_bytes, format="JPEG")
        jpeg_bytes = out_bytes.getvalue()
        
        if client is None:
            import llm
            from google.genai import types
            
            model_name = os.environ.get("SANKAT_VISION_MODEL", llm.MODEL)
            
            response = llm.client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                    "Analyze this flood photo."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYS_VISION,
                    temperature=0.0
                )
            )
            text = response.text
        else:
            text = client(jpeg_bytes)
            
        try:
            data = json.loads(text)
        except Exception:
            text_clean = text.replace("```json", "").replace("```", "").strip()
            start = text_clean.find("{")
            end = text_clean.rfind("}")
            if start != -1 and end != -1:
                try:
                    data = json.loads(text_clean[start:end+1])
                except Exception:
                    data = {}
            else:
                data = {}
        
        water_level = data.get("water_level")
        if water_level not in WATER_LEVELS:
            water_level = "unknown"
            
        hazards = data.get("hazards") or []
        if isinstance(hazards, str):
            hazards = [hazards]
        elif not isinstance(hazards, list):
            hazards = []
        hazards = [h for h in hazards if h in HAZARDS]
        
        confidence = data.get("confidence")
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = None
            
        evidence = data.get("evidence")
        if evidence is not None:
            evidence = str(evidence).strip()
            
        return {
            "water_level": water_level,
            "hazards": hazards,
            "confidence": confidence,
            "evidence": evidence
        }
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)}"
        return {"error": msg[:150]}
