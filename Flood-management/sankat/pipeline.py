import uuid
import concurrent.futures
from typing import List, Dict, Tuple
from .models import RequestItem, UploadSummary, ExtractedSOS
from .parse_whatsapp import parse_whatsapp_text
from .extract import extract_sos_from_text
from .geo import geo_resolver
from .dedupe import find_duplicate, merge_duplicate
from .priority import priority_engine
from .db import get_all_requests, save_or_update_request, get_total_duplicate_count


def process_raw_sos_message(raw_text: str, timestamp_str: str = None) -> Tuple[RequestItem, bool]:
    """
    Processes a single raw text SOS forward through the complete SANKAT pipeline.
    Returns: (request_item, is_duplicate)
    """
    # 1. AI Extraction
    extracted = extract_sos_from_text(raw_text)
    if timestamp_str:
        extracted.timestamp = timestamp_str

    # 2. Existing requests for dedupe check
    existing = get_all_requests()

    # 3. Deduplication check via RapidFuzz
    matched_req, sim_score = find_duplicate(extracted, existing)
    if matched_req:
        updated = merge_duplicate(matched_req, extracted, sim_score)
        return updated, True

    # 4. Geo-Resolution
    lat, lon, matched_name, is_exact, address_note = geo_resolver.resolve(extracted.location_text)

    # 5. Deterministic Priority Scoring
    score, tier = priority_engine.calculate(
        water_level=extracted.water_level,
        people_count=extracted.people_count or 1,
        vulnerable_tags=extracted.vulnerable_tags,
        duplicate_count=0
    )

    # 6. Create new ticket
    new_id = f"req_{uuid.uuid4().hex[:6]}"
    item = RequestItem(
        id=new_id,
        location_text=extracted.location_text or matched_name,
        lat=lat,
        lon=lon,
        tier=tier,
        score=score,
        people_count=extracted.people_count or 1,
        vulnerable_tags=extracted.vulnerable_tags,
        water_level=extracted.water_level,
        status="new",
        duplicate_count=0,
        contact=extracted.contact,
        landmark_matched=matched_name,
        timestamp=extracted.timestamp,
        raw_excerpt=raw_text[:140],
        is_exact_address=is_exact,
        address_note=address_note
    )

    save_or_update_request(item)
    return item, False


def ingest_whatsapp_dump(raw_file_content: str) -> UploadSummary:
    """
    Full batch ingestion of a WhatsApp .txt export with parallel extraction
    and deterministic deduplication.
    """
    messages = parse_whatsapp_text(raw_file_content)
    total_msgs = len(messages)
    if total_msgs == 0:
        return UploadSummary(
            messages_processed=0,
            unique_requests_created=0,
            duplicates_merged=0,
            critical_cases=0
        )

    # 1. Concurrent Extraction across thread pool for speed
    def _extract_task(msg_dict):
        raw = msg_dict["text"]
        ts = msg_dict.get("timestamp")
        extracted = extract_sos_from_text(raw)
        if ts:
            extracted.timestamp = ts
        return extracted, raw

    # Use 8 workers to complete all extractions in 1-2 seconds
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        extracted_pairs = list(executor.map(_extract_task, messages))

    # 2. Sequential In-Memory Deduplication & Persistence
    existing_requests = get_all_requests()
    unique_count = 0
    dupes_merged = 0

    for extracted, raw_text in extracted_pairs:
        matched_req, sim_score = find_duplicate(extracted, existing_requests)
        if matched_req:
            updated = merge_duplicate(matched_req, extracted, sim_score)
            dupes_merged += 1
            # Update in-memory reference
            for i, r in enumerate(existing_requests):
                if r.id == updated.id:
                    existing_requests[i] = updated
                    break
        else:
            lat, lon, matched_name, is_exact, address_note = geo_resolver.resolve(extracted.location_text)
            score, tier = priority_engine.calculate(
                water_level=extracted.water_level,
                people_count=extracted.people_count or 1,
                vulnerable_tags=extracted.vulnerable_tags,
                duplicate_count=0
            )
            new_id = f"req_{uuid.uuid4().hex[:6]}"
            new_item = RequestItem(
                id=new_id,
                location_text=extracted.location_text or matched_name,
                lat=lat,
                lon=lon,
                tier=tier,
                score=score,
                people_count=extracted.people_count or 1,
                vulnerable_tags=extracted.vulnerable_tags,
                water_level=extracted.water_level,
                status="new",
                duplicate_count=0,
                contact=extracted.contact,
                landmark_matched=matched_name,
                timestamp=extracted.timestamp,
                raw_excerpt=raw_text[:140],
                is_exact_address=is_exact,
                address_note=address_note
            )
            save_or_update_request(new_item)
            existing_requests.append(new_item)
            unique_count += 1

    all_reqs = get_all_requests()
    critical_cases = sum(1 for r in all_reqs if r.tier == "CRITICAL")

    return UploadSummary(
        messages_processed=total_msgs,
        unique_requests_created=unique_count,
        duplicates_merged=dupes_merged,
        critical_cases=critical_cases
    )
