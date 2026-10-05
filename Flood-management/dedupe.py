import re
from datetime import datetime
from rapidfuzz import fuzz

WATER_LEVELS = ["unknown", "ankle", "knee", "waist", "chest", "above_head_roof"]

def normalize(text):
    if not text: return ""
    t = text.lower()
    t = re.sub(r'[^a-z0-9]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def parse_ts(ts):
    if not ts: return None
    if isinstance(ts, datetime): return ts
    try:
        return datetime.fromisoformat(str(ts))
    except ValueError:
        return None

def match_place(a, b):
    ga = a.get("geo_name")
    gb = b.get("geo_name")
    if ga and gb:
        return ga == gb
    if not ga and not gb:
        la = a.get("location_text")
        lb = b.get("location_text")
        if not la or not lb:
            return False
        if not la.strip() or not lb.strip():
            return False
        score = fuzz.token_sort_ratio(normalize(la), normalize(lb))
        return score >= 88
    return False

def match_time(a, b, window_hours):
    ts_a = parse_ts(a.get("ts"))
    ts_b = parse_ts(b.get("ts"))
    if ts_a and ts_b:
        diff = abs((ts_a - ts_b).total_seconds()) / 3600.0
        if diff > window_hours:
            return False
    return True

def is_strong_match(a, b, window_hours):
    if not match_place(a, b): return False
    if not match_time(a, b, window_hours): return False
    c_a, c_b = a.get("contact"), b.get("contact")
    sa, sb = a.get("contact_source"), b.get("contact_source")
    if c_a and c_b and c_a == c_b and sa == "message" and sb == "message":
        return True
    return False

def is_match(a, b, window_hours):
    if is_strong_match(a, b, window_hours):
        return True
        
    if not match_place(a, b): return False
    if not match_time(a, b, window_hours): return False
    
    rta = a.get("request_type")
    rtb = b.get("request_type")
    if rta != rtb and not (rta in ["rescue", "medical"] and rtb in ["rescue", "medical"]):
        return False
        
    wa = a.get("water_level") or "unknown"
    wb = b.get("water_level") or "unknown"
    if wa != wb and wa != "unknown" and wb != "unknown":
        return False
        
    pa = a.get("people_count")
    pb = b.get("people_count")
    if pa != pb and pa is not None and pb is not None:
        return False
        
    va = set(a.get("vulnerable") or [])
    vb = set(b.get("vulnerable") or [])
    if va != vb and va and vb and not va.intersection(vb):
        return False
        
    return True

def info_score(r):
    score = 0
    if r.get("people_count") is not None: score += 1
    if r.get("location_text"): score += 1
    if r.get("water_level") not in [None, "unknown"]: score += 1
    if r.get("vulnerable"): score += 1
    if r.get("contact") is not None: score += 1
    return score

def sort_key(r):
    ts = parse_ts(r.get("ts"))
    ts_val = ts.isoformat() if ts else "9999"
    rid = str(r.get("report_id", ""))
    return (-info_score(r), ts_val, rid)

def merge_cluster(cl):
    primary = sorted(cl, key=sort_key)[0]
    merged = dict(primary)
    
    pcs = [m.get("people_count") for m in cl if m.get("people_count") is not None]
    merged["people_count"] = max(pcs) if pcs else None
    
    wls = [m.get("water_level") or "unknown" for m in cl]
    best_wl = "unknown"
    best_idx = 0
    for w in wls:
        idx = WATER_LEVELS.index(w) if w in WATER_LEVELS else 0
        if idx > best_idx:
            best_idx = idx
            best_wl = w
    merged["water_level"] = best_wl
    
    vul = []
    haz = []
    for m in cl:
        for v in (m.get("vulnerable") or []):
            if v not in vul: vul.append(v)
        for h in (m.get("hazards") or []):
            if h not in haz: haz.append(h)
    merged["vulnerable"] = vul
    merged["hazards"] = haz
    
    if not merged.get("contact"):
        for m in cl:
            if m.get("contact"):
                merged["contact"] = m["contact"]
                merged["contact_source"] = m.get("contact_source")
                break
                
    if not merged.get("evidence"):
        for m in cl:
            if m.get("evidence"):
                merged["evidence"] = m["evidence"]
                break
                
    geo_fields = ["location_text", "geo_name", "lat", "lon", "geo_score", "geo_method"]
    for gf in geo_fields:
        if not merged.get(gf):
            for m in cl:
                if m.get(gf):
                    merged[gf] = m[gf]
                    break
                    
    if any(m.get("request_type") == "medical" for m in cl):
        merged["request_type"] = "medical"
        
    def sort_member(m):
        ts = parse_ts(m.get("ts"))
        return (ts.isoformat() if ts else "", str(m.get("report_id", "")))
        
    sorted_members = sorted(cl, key=sort_member)
    merged["merged_ids"] = [m["report_id"] for m in sorted_members]
    merged["merged_texts"] = [{
        "report_id": m["report_id"],
        "ts": m.get("ts"),
        "sender": m.get("sender"),
        "text": m.get("original_text")
    } for m in sorted_members]
    
    merged["duplicate_count"] = len(cl) - 1
    
    valid_m = [m for m in cl if parse_ts(m.get("ts")) is not None]
    if valid_m:
        merged["first_seen"] = min(valid_m, key=lambda m: parse_ts(m.get("ts")))["ts"]
        merged["last_seen"] = max(valid_m, key=lambda m: parse_ts(m.get("ts")))["ts"]
    else:
        merged["first_seen"] = None
        merged["last_seen"] = None
        
    if len(cl) == 1:
        merged["merge_confidence"] = "single"
    else:
        contacts = [m.get("contact") for m in cl]
        sources = [m.get("contact_source") for m in cl]
        if all(c is not None for c in contacts) and len(set(contacts)) == 1 and all(s == "message" for s in sources):
            merged["merge_confidence"] = "high"
        else:
            pcs_all = [m.get("people_count") for m in cl]
            wls_all = [m.get("water_level") or "unknown" for m in cl]
            if all(p is not None for p in pcs_all) and len(set(pcs_all)) == 1 and \
               all(w != "unknown" for w in wls_all) and len(set(wls_all)) == 1:
                merged["merge_confidence"] = "high"
            else:
                merged["merge_confidence"] = "possible"
                
    p_wl = primary.get("water_level") or "unknown"
    p_idx = WATER_LEVELS.index(p_wl) if p_wl in WATER_LEVELS else 0
    m_idx = WATER_LEVELS.index(merged["water_level"]) if merged["water_level"] in WATER_LEVELS else 0
    merged["escalated"] = m_idx > p_idx
    
    return merged

def cluster(requests, window_hours=6):
    clusters = []
    for req in requests:
        matched_cluster = None
        for cl in clusters:
            if all(is_match(req, m, window_hours) for m in cl):
                matched_cluster = cl
                break
        if matched_cluster is not None:
            matched_cluster.append(req)
        else:
            clusters.append([req])
            
    merged_results = []
    for cl in clusters:
        merged_results.append(merge_cluster(cl))
        
    def primary_index(m_req):
        primary_id = m_req["report_id"]
        for i, r in enumerate(requests):
            if r["report_id"] == primary_id:
                return i
        return 0
        
    merged_results.sort(key=primary_index)
    return merged_results
