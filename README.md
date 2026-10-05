# SANKAT: Flood Triage System

## 1. Problem
During the 2015 Chennai floods, volunteers retyped WhatsApp SOS messages into sheets manually. 

## 2. Who it is for
Control-room operators (TN 1070/1077 style helplines), not victims.

## 3. What it does
Raw WhatsApp export in; extraction, geo, dedupe, scoring and a human-confirmed triage queue and map out.

## 4. Architecture
The actual flow: `wa_parser` -> `llm` -> `geo` -> `dedupe` -> `priority` -> Streamlit + SQLite. 
Principle: the AI extracts, plain Python decides.

## 5. Gemma usage
- Model name from `SANKAT_MODEL`.
- Batches of 8.
- System instruction with a few-shot glossary prompt.
- Temperature 0.
- Output validation.
- Phone numbers masked before sending.
- Photo evidence support via `vision.py`.

## 6. Safety design
- Human verifies every action.
- Null policy.
- Nothing is silently dropped (failed, chatter and offers all reviewable).
- Review flags.
- Status audit log.

## 7. Scoring
The rules use point values from `priority.py` to assign a score (out of 100) and tier (CRITICAL, HIGH, MODERATE, LOW):
- Water Level: unknown (10 pts), ankle (0 pts), knee (8 pts), waist (18 pts), chest (30 pts), above_head_roof (40 pts). Unknown water scores 10 points as an uncertainty premium.
- Vulnerabilities: elderly (8 pts), child_infant (10 pts), pregnant (12 pts), bedridden_disabled (10 pts), medical_dependency (12 pts) — max 25 pts.
- People Count: count × 1.5, max 15 pts.
- Hazards: live_wire (10 pts), structural (8 pts), strong_current (5 pts) — max 12 pts.

## 8. Evaluation
Not yet run

## 9. Limitations
Synthetic data, no pilot, landmark-level approximate geo, hosted API needs connectivity, dedupe heuristics can merge distinct households (merged reports stay visible), Tamil-script place names are not geo-matched.

## 10. Quickstart
pip install -r requirements.txt
copy .env.example to .env and set the key
python tests/run_all.py
streamlit run app.py (from the project root)

## 11. Data credits
packs/tamil_nadu/landmarks.csv is team-compiled approximate coordinates.

## 12. AI disclosure
TODO(team): confirm AI-assistance statement before submission

## 13. License
TODO(team): license mismatch
