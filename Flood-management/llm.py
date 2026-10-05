import os
import json
import hashlib
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()
MODEL = os.environ.get("SANKAT_MODEL", "gemma-4-26b-a4b-it")

def extract_json(raw: str) -> list | None:
    """Extract JSON array from raw LLM output."""
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "")
    try:
        start = raw.index("[")
        end = raw.rindex("]")
        return json.loads(raw[start:end + 1])
    except Exception:
        return None

def extract_reports(messages: list[dict]) -> list[dict]:
    """Process messages in batches and extract data."""
    from prompts import SYS_EXTRACT
    results = []
    
    for i in range(0, len(messages), 8):
        batch = messages[i:i + 8]
        user_content = json.dumps([{"report_id": m["report_id"], "text": m["text"]} for m in batch], ensure_ascii=False)
        
        resp = client.models.generate_content(
            model=MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(system_instruction=SYS_EXTRACT)
        )
        parsed = extract_json(resp.text)
        
        if parsed is None:
            resp = client.models.generate_content(
                model=MODEL,
                contents=user_content + "\n\nReturn only valid JSON array. No markdown. No explanation.",
                config=types.GenerateContentConfig(system_instruction=SYS_EXTRACT)
            )
            parsed = extract_json(resp.text)
            
        if parsed is None:
            for m in batch:
                results.append({"report_id": m["report_id"], "request_type": "extraction_failed"})
        else:
            results.extend(parsed)
            
    return results

if __name__ == "__main__":
    test = [
        {"report_id": "r1", "text": "Velachery signal pakkam 4 per irukkom. Thanni chest level. Oru paati irukkanga. 9000000001"},
        {"report_id": "r2", "text": "Stay safe everyone. Prayers for all affected."}
    ]
    import json
    result = extract_reports(test)
    print(json.dumps(result, indent=2, ensure_ascii=False))
