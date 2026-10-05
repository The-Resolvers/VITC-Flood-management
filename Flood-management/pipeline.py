import copy
from typing import List, Dict, Any

from wa_parser import parse_export, mask_phones, find_phones
import geo
import dedupe
import priority

def extract_items(raw_text: str, label: str, extract_fn=None) -> List[Dict[str, Any]]:
    messages = parse_export(raw_text)
    if not messages:
        return []

    llm_messages = []
    for m in messages:
        rid = f"{label}-{m['report_id']}"
        llm_messages.append({
            "report_id": rid,
            "text": mask_phones(m["text"])
        })
        
    if extract_fn is None:
        import llm
        extract_fn = llm.extract_reports
        
    results_list = extract_fn(llm_messages)
    results_map = {res["report_id"]: res for res in results_list if "report_id" in res}
    
    items = []
    for m, llm_m in zip(messages, llm_messages):
        rid = llm_m["report_id"]
        res = results_map.get(rid)
        if not res:
            res = {"report_id": rid, "request_type": "extraction_failed", "error": "no result"}
            
        item = copy.deepcopy(res)
        item["label"] = label
        item["sender"] = m.get("sender")
        item["ts"] = m.get("ts")
        item["original_text"] = m["text"]
        
        phones_body = find_phones(m["text"])
        phones_sender = find_phones(m.get("sender") or "")
        
        if phones_body:
            item["contact"] = phones_body[0]
            item["contact_source"] = "message"
        elif phones_sender:
            item["contact"] = phones_sender[0]
            item["contact_source"] = "sender"
        else:
            item["contact"] = None
            item["contact_source"] = None
            
        items.append(item)
        
    return items

def retry_failed(items: List[Dict[str, Any]], extract_fn=None) -> List[Dict[str, Any]]:
    failed_items = [i for i in items if i.get("request_type") == "extraction_failed"]
    if not failed_items:
        return copy.deepcopy(items)
        
    llm_messages = []
    for item in failed_items:
        llm_messages.append({
            "report_id": item["report_id"],
            "text": mask_phones(item["original_text"])
        })
        
    if extract_fn is None:
        import llm
        extract_fn = llm.extract_reports
        
    results_list = extract_fn(llm_messages)
    results_map = {res["report_id"]: res for res in results_list if "report_id" in res}
    
    new_items = []
    for item in items:
        if item.get("request_type") == "extraction_failed":
            rid = item["report_id"]
            res = results_map.get(rid)
            if res and res.get("request_type") != "extraction_failed":
                new_item = copy.deepcopy(res)
                for k in ["label", "sender", "ts", "original_text", "contact", "contact_source"]:
                    new_item[k] = item.get(k)
                new_items.append(new_item)
            else:
                new_items.append(copy.deepcopy(item))
        else:
            new_items.append(copy.deepcopy(item))
            
    return new_items

def build_view(items: List[Dict[str, Any]], landmarks: List[Dict[str, Any]], status_map=None) -> Dict[str, Any]:
    items = copy.deepcopy(items)
    status_map = status_map or {}
    
    failed = []
    chatter = []
    offers = []
    actionable = []
    
    for item in items:
        rt = item.get("request_type")
        if rt == "extraction_failed":
            failed.append(item)
        elif rt == "chatter":
            chatter.append(item)
        elif rt == "info_offer":
            offers.append(item)
        elif rt in ["rescue", "supplies", "medical"]:
            actionable.append(item)
        else:
            failed.append(item)
            
    for lst in [actionable, offers]:
        for item in lst:
            photo = item.get("photo")
            if photo and isinstance(photo, dict):
                p_water = photo.get("water_level")
                t_water = item.get("water_level", "unknown")
                WATER_ORDER = ["unknown", "ankle", "knee", "waist", "chest", "above_head_roof"]
                p_rank = WATER_ORDER.index(p_water) if p_water in WATER_ORDER else 0
                t_rank = WATER_ORDER.index(t_water) if t_water in WATER_ORDER else 0
                
                if t_water == "unknown":
                    if p_water and p_water != "unknown":
                        item["water_level"] = p_water
                elif p_water and p_water != "unknown":
                    if p_rank > t_rank:
                        item["water_level"] = p_water
                        item["photo_conflict"] = True
                    elif p_rank < t_rank:
                        item["photo_conflict"] = True
                
                p_hazards = photo.get("hazards", [])
                t_hazards = item.get("hazards", [])
                if isinstance(t_hazards, list) and isinstance(p_hazards, list):
                    item["hazards"] = list(set(t_hazards + p_hazards))
                    
                item["photo_evidence"] = photo.get("evidence")

            loc_text = item.get("location_text") or ""
            geo_res = geo.resolve(loc_text, landmarks)
            if geo_res:
                item["geo_name"] = geo_res.get("name")
                item["lat"] = geo_res.get("lat")
                item["lon"] = geo_res.get("lon")
                item["geo_score"] = geo_res.get("score")
                item["geo_method"] = geo_res.get("method")
            else:
                item["geo_name"] = None
                item["lat"] = None
                item["lon"] = None
                item["geo_score"] = None
                item["geo_method"] = None

    requests = dedupe.cluster(actionable, window_hours=6)
    geo.spread(requests)
    
    STATUSES = ["new", "verified", "dispatched", "rescued"]
    status_rank = {s: i for i, s in enumerate(STATUSES)}
    
    for req in requests:
        pri = priority.calculate_priority(req)
        req["tier"] = pri["tier"]
        req["score"] = pri["score"]
        req["breakdown"] = pri["breakdown"]
        req["reasons"] = pri.get("reasons", [])
        req["flags"] = priority.review_flags(req)
        
        merged_ids = req.get("merged_ids", [])
        highest_status = "new"
        highest_rank = -1
        for mid in merged_ids:
            st = status_map.get(mid, "new")
            rank = status_rank.get(st, -1)
            if rank > highest_rank:
                highest_rank = rank
                highest_status = st
        req["status"] = highest_status
        
    TIER_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    requests.sort(key=lambda r: (
        TIER_ORDER.get(r.get("tier"), 4),
        -r.get("score", 0),
        r.get("first_seen") or ""
    ))
    
    merged_total = sum(r.get("duplicate_count", 0) for r in requests)
    
    return {
        "requests": requests,
        "offers": offers,
        "chatter": chatter,
        "failed": failed,
        "total": len(items),
        "merged_total": merged_total
    }
