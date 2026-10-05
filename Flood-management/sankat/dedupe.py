from typing import Optional, Tuple, List
from rapidfuzz import fuzz
from .config import DEDUPE_SIMILARITY_THRESHOLD
from .models import RequestItem, ExtractedSOS
from .db import get_all_requests, log_dedupe, save_or_update_request
from .priority import priority_engine


def find_duplicate(
    candidate: ExtractedSOS,
    existing_requests: List[RequestItem]
) -> Tuple[Optional[RequestItem], float]:
    """
    Checks if the incoming SOS matches an existing request by >= threshold.
    Returns: (matching_request, similarity_score)
    """
    if not existing_requests:
        return None, 0.0

    cand_loc = (candidate.location_text or "").strip().lower()
    cand_contact = (candidate.contact or "").strip()
    cand_raw = (candidate.raw_text or "").strip().lower()

    best_match: Optional[RequestItem] = None
    highest_score = 0.0

    for req in existing_requests:
        req_loc = (req.location_text or "").strip().lower()
        req_contact = (req.contact or "").strip()
        req_raw = (req.raw_excerpt or "").strip().lower()

        # 1. Exact contact match + moderate location match
        if cand_contact and req_contact and cand_contact == req_contact:
            loc_sim = fuzz.token_set_ratio(cand_loc, req_loc)
            if loc_sim >= 60.0:
                return req, 98.0

        # 2. High text similarity (Forwarded viral message)
        raw_sim = fuzz.token_set_ratio(cand_raw, req_raw)
        if raw_sim >= DEDUPE_SIMILARITY_THRESHOLD:
            return req, raw_sim

        # 3. High location text similarity
        loc_sim = fuzz.token_set_ratio(cand_loc, req_loc)
        if loc_sim >= DEDUPE_SIMILARITY_THRESHOLD:
            if loc_sim > highest_score:
                highest_score = loc_sim
                best_match = req

    if best_match and highest_score >= DEDUPE_SIMILARITY_THRESHOLD:
        return best_match, highest_score

    return None, 0.0


def merge_duplicate(primary: RequestItem, incoming: ExtractedSOS, sim_score: float) -> RequestItem:
    """
    Increments duplicate counter, merges missing info (like vulnerability tags or higher water level),
    and recalculates priority score deterministically.
    """
    primary.duplicate_count += 1
    log_dedupe(primary.id, incoming.raw_text, sim_score)

    # Merge vulnerable tags
    for tag in incoming.vulnerable_tags:
        if tag not in primary.vulnerable_tags:
            primary.vulnerable_tags.append(tag)

    # People count (take max if reported higher)
    if incoming.people_count and incoming.people_count > primary.people_count:
        primary.people_count = incoming.people_count

    # Contact number update if previously missing
    if not primary.contact and incoming.contact:
        primary.contact = incoming.contact

    # Water level severity update
    severity_order = {"unknown": 0, "ankle": 1, "knee": 2, "waist": 3, "chest": 4, "roof": 5}
    if severity_order.get(incoming.water_level, 0) > severity_order.get(primary.water_level, 0):
        primary.water_level = incoming.water_level

    # Recalculate deterministic score
    score, tier = priority_engine.calculate(
        water_level=primary.water_level,
        people_count=primary.people_count,
        vulnerable_tags=primary.vulnerable_tags,
        duplicate_count=primary.duplicate_count
    )
    primary.score = score
    primary.tier = tier

    save_or_update_request(primary)
    return primary
