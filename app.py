import sys, os, json, csv, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "Flood-management"))
import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import llm, priority

st.set_page_config(layout="wide", page_title="SANKAT - Flood Triage", page_icon="\U0001F6A8")
st.markdown('<div style="background:#b91c1c;padding:8px;border-radius:4px;color:white;font-weight:bold">\u26A0 Decision support only. Human operator verifies all actions. All demo data is synthetic.</div>', unsafe_allow_html=True)
st.markdown("")

def load_landmarks():
    rows = []
    with open("packs/tamil_nadu/landmarks.csv") as f:
        for row in csv.DictReader(f):
            row["aliases_list"] = row["aliases"].split("|")
            rows.append(row)
    return rows
LANDMARKS = load_landmarks()

def resolve_geo(location_text):
    if not location_text:
        return None, None
    best_score, best_row = 0, None
    for row in LANDMARKS:
        candidates = [row["name"]] + row["aliases_list"]
        for c in candidates:
            s = fuzz.token_set_ratio(location_text.lower(), c.lower())
            if s > best_score:
                best_score, best_row = s, row
    if best_score >= 70:
        return float(best_row["lat"]), float(best_row["lon"])
    return None, None

with st.sidebar:
    st.header("SANKAT Control Room")
    uploaded = st.file_uploader("Upload WhatsApp .txt export", type=["txt"])
    st.markdown("---")
    single_text = st.text_area("Paste single SOS message")
    process_btn = st.button("Process Single Message")

if "requests" not in st.session_state:
    st.session_state.requests = []
if "status_map" not in st.session_state:
    st.session_state.status_map = {}

messages = []
file_hash = None
if uploaded:
    raw = uploaded.getvalue()
    file_hash = hashlib.md5(raw).hexdigest()
    lines = raw.decode("utf-8", errors="ignore").splitlines()
    skip_patterns = ["end-to-end encrypted", "Messages omitted", "<Media omitted>"]
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or any(p in line for p in skip_patterns):
            continue
        messages.append({"report_id": f"r{i+1}", "text": line})
elif process_btn and single_text.strip():
    messages = [{"report_id": "r1", "text": single_text.strip()}]
if not uploaded:
    st.session_state.last_hash = None

is_new = bool(messages) and (file_hash is None or file_hash != st.session_state.get("last_hash"))
if is_new:
    with st.spinner(f"Gemma 4 extracting {len(messages)} messages..."):
        try:
            extractions = llm.extract_reports(messages)
        except Exception as e:
            st.error(f"LLM error: {e}")
            st.stop()
    requests = []
    for ext in extractions:
        if ext.get("request_type") in ["chatter", "extraction_failed"]:
            continue
        pri = priority.calculate_priority(ext)
        lat, lon = resolve_geo(ext.get("location_text"))
        original = next((m["text"] for m in messages if m["report_id"] == ext["report_id"]), "")
        requests.append({**ext, **pri, "lat": lat, "lon": lon, "original_text": original})
    st.session_state.requests = requests
    st.session_state.last_hash = file_hash
    st.session_state.total_msgs = len(messages)
    st.session_state.chatter_count = len([e for e in extractions if e.get("request_type") == "chatter"])

TIER_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
TIER_COLOR = {"CRITICAL": "#FF0000", "HIGH": "#FF8C00", "MODERATE": "#FFD700", "LOW": "#00CC44"}

reqs = sorted(st.session_state.requests, key=lambda x: (TIER_ORDER.get(x.get("tier","LOW"),3), -x.get("score",0)))

total_msgs = st.session_state.get("total_msgs", 0)
chatter_count = st.session_state.get("chatter_count", 0)
critical_count = len([r for r in reqs if r.get("tier") == "CRITICAL"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Messages", total_msgs)
c2.metric("Chatter Filtered", chatter_count)
c3.metric("Active Requests", len(reqs))
if critical_count > 0:
    c4.markdown(f'<div style="background:#b91c1c;padding:12px;border-radius:8px;text-align:center"><span style="font-size:2em;color:white">{critical_count}</span><br><span style="color:#fca5a5">CRITICAL</span></div>', unsafe_allow_html=True)
else:
    c4.metric("Critical", 0)

st.markdown("---")
map_col, table_col = st.columns([1, 1])

with map_col:
    st.subheader("Live Triage Map")
    map_rows = [r for r in reqs if r.get("lat")]
    if map_rows:
        df_map = pd.DataFrame(map_rows)[["lat","lon","tier"]]
        df_map["color"] = df_map["tier"].map(TIER_COLOR).fillna("#888888")
        st.map(df_map, latitude="lat", longitude="lon", color="color", size=100)
    else:
        st.info("No geo-resolved locations yet.")

with table_col:
    st.subheader("Priority Queue")
    if reqs:
        df_table = pd.DataFrame(reqs)[["tier","score","location_text","people_count","water_level","vulnerable","evidence"]]
        df_table.columns = ["Tier","Score","Location","People","Water","Vulnerable","Evidence"]
        st.dataframe(df_table, use_container_width=True, hide_index=True)
        csv_data = df_table.to_csv(index=False)
        st.download_button("Export CSV", csv_data, "sankat_export.csv", "text/csv")

st.markdown("---")
st.subheader("Request Details")
for i, req in enumerate(reqs):
    label = f"{req.get('tier','?')} | {req.get('location_text','Unknown location')} | Score {req.get('score',0)}"
    with st.expander(label):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Original Message:**")
            st.text(req.get("original_text",""))
            st.markdown("**Extraction JSON:**")
            st.json({k: req.get(k) for k in ["request_type","location_text","people_count","water_level","vulnerable","contact","confidence","evidence"]})
        with col2:
            st.markdown("**Score Breakdown:**")
            st.json(req.get("breakdown", {}))
