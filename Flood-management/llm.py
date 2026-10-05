import os
import json
import hashlib
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()
MODEL = os.environ.get("SANKAT_MODEL", "gemma-4-26b-a4b-it")
BATCH_SIZE = 8
_NO_SYSTEM = False

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

def normalize_item(item, report_id) -> dict:
    req_type = str(item.get("request_type", "")).strip().lower()
    if req_type == "info": req_type = "info_offer"
    if req_type == "offer": req_type = "info_offer"
    if req_type not in ["rescue", "supplies", "medical", "info_offer", "chatter"]:
        return {"report_id": report_id, "request_type": "extraction_failed", "error": "invalid request_type"}

    loc = item.get("location_text")
    if isinstance(loc, str):
        loc = loc.strip()
        if loc.lower() in ["", "null", "none", "n/a"]: loc = None
    else:
        loc = None

    people = item.get("people_count")
    if people is not None:
        try:
            val = float(people)
            if val.is_integer() and 1 <= val <= 500:
                people = int(val)
            else:
                people = None
        except (ValueError, TypeError):
            people = None

    def norm_list(val, mapping, allowed):
        if val is None:
            return []
        if isinstance(val, str):
            val = val.replace(',', ' ').split()
        elif not isinstance(val, list):
            return []
            
        res = []
        for x in val:
            x = str(x).lower().strip()
            mapped = mapping.get(x, x)
            if mapped in allowed and mapped not in res:
                res.append(mapped)
        return res

    vul_map = {
        "child": "child_infant", "children": "child_infant", "kids": "child_infant", "kid": "child_infant", "infant": "child_infant", "baby": "child_infant",
        "old": "elderly", "senior": "elderly", "aged": "elderly",
        "disabled": "bedridden_disabled", "bedridden": "bedridden_disabled",
        "medical": "medical_dependency", "dialysis": "medical_dependency", "oxygen": "medical_dependency"
    }
    vul_allowed = {"elderly", "child_infant", "pregnant", "bedridden_disabled", "medical_dependency"}
    vul_list = norm_list(item.get("vulnerable"), vul_map, vul_allowed)

    water_allowed = {"unknown", "ankle", "knee", "waist", "chest", "above_head_roof"}
    water = str(item.get("water_level", "")).strip().lower()
    if water not in water_allowed:
        water = "unknown"

    haz_allowed = {"live_wire", "structural", "strong_current"}
    haz_list = norm_list(item.get("hazards"), {}, haz_allowed)

    conf = item.get("confidence")
    if conf is not None:
        try:
            conf = float(conf)
            conf = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            conf = None

    ev = item.get("evidence")
    if isinstance(ev, str):
        ev = ev.strip()
        if ev:
            ev = " ".join(ev.split()[:12])
        else:
            ev = None
    else:
        ev = None

    return {
        "report_id": report_id,
        "request_type": req_type,
        "location_text": loc,
        "people_count": people,
        "vulnerable": vul_list,
        "water_level": water,
        "hazards": haz_list,
        "contact": None,
        "confidence": conf,
        "evidence": ev
    }

def _call(contents: str) -> str:
    global _NO_SYSTEM
    from prompts import SYS_EXTRACT
    try:
        if _NO_SYSTEM:
            new_contents = SYS_EXTRACT + "\n\nMESSAGES:\n" + contents
            resp = client.models.generate_content(
                model=MODEL,
                contents=new_contents,
                config=types.GenerateContentConfig(temperature=0.0)
            )
        else:
            resp = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYS_EXTRACT, temperature=0.0)
            )
        return resp.text or ""
    except Exception as e:
        if "developer instruction" in str(e).lower() and not _NO_SYSTEM:
            _NO_SYSTEM = True
            new_contents = SYS_EXTRACT + "\n\nMESSAGES:\n" + contents
            resp = client.models.generate_content(
                model=MODEL,
                contents=new_contents,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return resp.text or ""
        raise

def extract_reports(messages: list[dict]) -> list[dict]:
    from prompts import SYS_EXTRACT
    cache_dir = os.environ.get("SANKAT_CACHE_DIR", "Flood-management/.cache")
    no_cache = os.environ.get("SANKAT_NO_CACHE", "") == "1"

    if not no_cache and not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    results = []
    
    for i in range(0, len(messages), BATCH_SIZE):
        batch = messages[i:i+BATCH_SIZE]
        user_content = json.dumps([{"report_id": m["report_id"], "text": m["text"]} for m in batch], ensure_ascii=False)
        
        cache_key = None
        cache_file = None
        if not no_cache:
            cache_key = hashlib.sha256((MODEL + "\n" + SYS_EXTRACT + "\n" + user_content).encode("utf-8")).hexdigest()
            cache_file = os.path.join(cache_dir, f"{cache_key}.json")
            
        raw_resp = None
        parsed = None
        if not no_cache and os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                raw_resp = f.read()
            parsed = extract_json(raw_resp)

        raised_err = None
        if parsed is None and not (not no_cache and os.path.exists(cache_file)):
            try:
                raw_resp = _call(user_content)
            except Exception as e:
                time.sleep(2)
                try:
                    raw_resp = _call(user_content)
                except Exception as e2:
                    raised_err = e2
            
            if raised_err is None:
                parsed = extract_json(raw_resp)
                if parsed is not None and not no_cache:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        f.write(raw_resp)
                
        batch_ids = [str(m["report_id"]) for m in batch]
        parsed_dict = {}

        if raised_err is not None:
            err_msg = str(raised_err)[:150]
            err_type = type(raised_err).__name__
            for rid in batch_ids:
                parsed_dict[rid] = {"report_id": rid, "request_type": "extraction_failed", "error": f"{err_type}: {err_msg}"}
        else:
            if parsed is not None:
                for item in parsed:
                    if isinstance(item, dict):
                        rid = str(item.get("report_id"))
                        if rid in batch_ids and rid not in parsed_dict:
                            parsed_dict[rid] = item

            missing_ids = [rid for rid in batch_ids if rid not in parsed_dict]
            if missing_ids:
                missing_msgs = [m for m in batch if str(m["report_id"]) in missing_ids]
                retry_content = json.dumps(missing_msgs, ensure_ascii=False) + "\n\nReturn only a valid JSON array. No markdown. No explanation."
                
                raised_retry_err = None
                try:
                    retry_resp = _call(retry_content)
                except Exception as e:
                    time.sleep(2)
                    try:
                        retry_resp = _call(retry_content)
                    except Exception as e2:
                        raised_retry_err = e2
                
                if raised_retry_err is not None:
                    err_msg = str(raised_retry_err)[:150]
                    err_type = type(raised_retry_err).__name__
                    for rid in missing_ids:
                        parsed_dict[rid] = {"report_id": rid, "request_type": "extraction_failed", "error": f"{err_type}: {err_msg}"}
                else:
                    retry_parsed = extract_json(retry_resp)
                    if retry_parsed is not None:
                        for item in retry_parsed:
                            if isinstance(item, dict):
                                rid = str(item.get("report_id"))
                                if rid in missing_ids and rid not in parsed_dict:
                                    parsed_dict[rid] = item

        for m in batch:
            rid = str(m["report_id"])
            if rid not in parsed_dict:
                item = {"report_id": rid, "request_type": "extraction_failed", "error": "not returned by model"}
            else:
                item = parsed_dict[rid]
                if item.get("request_type") != "extraction_failed":
                    item = normalize_item(item, rid)
            results.append(item)

    return results

if __name__ == "__main__":
    test = [
        {"report_id": "r1", "text": "Velachery signal pakkam 4 per irukkom. Thanni chest level. Oru paati irukkanga. 9000000001"},
        {"report_id": "r2", "text": "Stay safe everyone. Prayers for all affected."}
    ]
    import json
    result = extract_reports(test)
    print(json.dumps(result, indent=2, ensure_ascii=False))
