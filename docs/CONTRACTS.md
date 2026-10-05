# SANKAT contracts (all later steps must follow these)

## Rules
R1 Read existing files before editing; change only what the step asks.
R2 Use only the standard library plus installed packages. No pytest: tests are plain scripts in tests/ using assert, run as `python tests/test_x.py`, printing "PASS <name>" per check and exiting non-zero on failure.
R3 Tests never call the real model API; use fakes. Tests must set os.environ.setdefault("GEMINI_API_KEY","test-key") before importing llm, and add Flood-management/ to sys.path via Path(__file__).resolve().parents[1].
R4 Every .py file must be pure ASCII. Non-ASCII (Tamil, emoji) goes only in UTF-8 .txt/.json data files, or as \u escapes in code.
R5 Always open files with encoding="utf-8". Write files with your file-edit tool, never with PowerShell redirection.
R6 Never print, log or commit secrets.
R7 Never run git commit or git push.
R8 Do not rename or remove existing public functions unless the step says so.
R9 After each step, run its acceptance commands and fix until green.

## Enums
REQUEST_TYPES: rescue, supplies, medical, info_offer, chatter (code adds extraction_failed)
WATER_LEVELS (low to high): unknown, ankle, knee, waist, chest, above_head_roof
VULNERABLE: elderly, child_infant, pregnant, bedridden_disabled, medical_dependency
HAZARDS: live_wire, structural, strong_current
STATUSES (low to high): new, verified, dispatched, rescued
TIERS: CRITICAL, HIGH, MODERATE, LOW

## Modules (all in Flood-management/ unless noted)
wa_parser.parse_export(text) -> list[message]
  message = {report_id: "r<N>" sequential over kept messages, sender: str|None, ts: "YYYY-MM-DDTHH:MM"|None, text: str}
wa_parser.find_phones(text) -> list[str] normalized "+91XXXXXXXXXX"; wa_parser.mask_phones(text) -> str ("[PHONE]")
llm.extract_reports(messages) -> list[dict]
  input items {report_id, text}. Output: exactly one dict per input, same order:
  {report_id, request_type, location_text, people_count (int|None), vulnerable (list), water_level, hazards (list), contact (always None), confidence (float|None), evidence (str|None)}
  failure item: {report_id, request_type: "extraction_failed", error: str}
item (stored in DB, produced by pipeline.extract_items) = llm output plus
  {label, contact (str|None), contact_source ("message"|"sender"|None), sender, ts, original_text}
  report_id in an item is f"{label}-{parser report_id}", e.g. "f1a2b3-r12".
geo.load_landmarks(path=None) -> list[{id, name, lat: float, lon: float, aliases: list[str]}]
geo.resolve(location_text, landmarks) -> {name, lat, lon, score, method ("exact"|"fuzzy"), precision: "landmark"} | None
geo.spread(requests) -> adds map_lat/map_lon so pins sharing a landmark do not stack
dedupe.cluster(requests, window_hours=6) -> list[request] (merged primaries; never drops a report)
priority.calculate_priority(ext) -> {tier, score: int, breakdown: {water, vulnerable, people, hazards}, reasons: list[str]}
priority.review_flags(ext) -> list[str]
store.* : SQLite persistence (see Step 8)
pipeline.extract_items(raw_text, label, extract_fn=None) -> list[item]
pipeline.retry_failed(items, extract_fn=None) -> list[item]
pipeline.build_view(items, landmarks, status_map=None) -> {requests, offers, chatter, failed, total, merged_total}
request (in view["requests"]) = item fields plus
  {lat, lon, geo_name, geo_score, geo_method, map_lat, map_lon, tier, score, breakdown, reasons, flags,
   duplicate_count, merged_ids, merged_texts: [{report_id, ts, sender, text}], merge_confidence, first_seen, last_seen, status}
