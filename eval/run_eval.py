import os
import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import llm
from wa_parser import parse_export, mask_phones

def run_eval():
    key = os.environ.get("GEMINI_API_KEY")
    if not key or key == "your_key_here":
        print("GEMINI_API_KEY missing or not set")
        sys.exit(1)
        
    demo_path = Path(__file__).resolve().parents[1] / "demo" / "demo_data_tn.txt"
    if not demo_path.exists():
        print("SKIP")
        sys.exit(0)
        
    gold_path = Path(__file__).resolve().parent / "gold_tn.json"
    if not gold_path.exists():
        print("gold_tn.json missing")
        sys.exit(1)
        
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)
        
    raw_text = demo_path.read_text(encoding="utf-8")
    messages = parse_export(raw_text)
    
    llm_messages = []
    for m in messages:
        rid = f"r{m['report_id']}"
        llm_text = mask_phones(m["text"])
        llm_messages.append({"report_id": rid, "text": llm_text})
        
    results = llm.extract_reports(llm_messages)
    
    fields = ["request_type", "water_level", "people_count", "vulnerable"]
    correct = {f: 0 for f in fields}
    total = {f: 0 for f in fields}
    mismatches = []
    failed_extractions = 0
    
    res_dict = {r["report_id"]: r for r in results}
    
    for rid, expected in gold.items():
        if rid == "_note":
            continue
            
        got = res_dict.get(rid, {})
        
        if got.get("request_type") == "extraction_failed":
            failed_extractions += 1
            continue
            
        for f in fields:
            if f in expected:
                total[f] += 1
                e_val = expected[f]
                g_val = got.get(f)
                
                if f == "vulnerable":
                    e_val = set(e_val) if isinstance(e_val, list) else set()
                    g_val = set(g_val) if isinstance(g_val, list) else set()
                    
                if e_val == g_val:
                    correct[f] += 1
                else:
                    mismatches.append({
                        "report_id": rid,
                        "field": f,
                        "expected": list(e_val) if isinstance(e_val, set) else e_val,
                        "got": list(g_val) if isinstance(g_val, set) else g_val
                    })
                    
    print(f"Failed extractions: {failed_extractions}")
    print("Accuracies:")
    for f in fields:
        acc = (correct[f] / total[f]) * 100 if total[f] > 0 else 0
        print(f"  {f}: {acc:.2f}% ({correct[f]}/{total[f]})")
        
    if mismatches:
        print("Mismatches:")
        for m in mismatches:
            print(f"  {m['report_id']} - {m['field']}: expected {m['expected']}, got {m['got']}")
            
    out_path = Path(__file__).resolve().parent / "last_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "accuracies": {f: (correct[f] / total[f]) if total[f] > 0 else 0 for f in fields},
            "failed_extractions": failed_extractions,
            "mismatches": mismatches
        }, f, indent=2)

if __name__ == "__main__":
    run_eval()
