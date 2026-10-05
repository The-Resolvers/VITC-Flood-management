import sys
import time
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "Flood-management"))

import streamlit as st
import pandas as pd
import pydeck as pdk

import pipeline
import store
import geo
import vision
from wa_parser import parse_export

st.set_page_config(layout="wide", page_title="RescueGrid - Flood Triage", page_icon="⬢")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within { border-color: #ef4444 !important; box-shadow: 0 0 0 1px #ef4444 !important; }
    [data-testid="stSidebar"] { background-color: #09090b !important; border-right: 1px solid #27272a !important; }
    .stMultiSelect span[data-baseweb="tag"] { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 4px !important; }

    /* Kill Streamlit branding */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    .stDataFrame {border: 1px solid #1e293b; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);}
</style>
""", unsafe_allow_html=True)

st.markdown('''
<div style="background: linear-gradient(90deg, #7f1d1d 0%, #991b1b 100%); padding: 12px 24px; border-radius: 4px; border-left: 4px solid #f87171; color: white; font-weight: 700; letter-spacing: 2px; font-size: 14px; text-transform: uppercase; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.15); margin-bottom: 24px;">
    SYSTEM ACTIVE // RescueGrid Live Triage Console // HUMAN VERIFICATION REQUIRED
</div>
''', unsafe_allow_html=True)

store.init()

@st.cache_resource
def load_landmarks():
    return geo.load_landmarks()

LANDMARKS = load_landmarks()

with st.sidebar:
    st.header("RescueGrid Control Room")
    operator_name = st.text_input("Operator name", value="operator")
    uploaded = st.file_uploader("Upload WhatsApp .txt export", type=["txt"])
    st.markdown("---")
    single_text = st.text_area("Paste single SOS message")
    process_btn = st.button("Process Single Message")
    st.markdown("---")
    if st.button("Clear All Data"):
        store.clear_all()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

if uploaded:
    raw = uploaded.getvalue()
    h = hashlib.md5(raw).hexdigest()
    if st.session_state.get("last_uploaded_hash") != h:
        if not store.has_run(h):
            raw_str = raw.decode("utf-8", errors="ignore")
            n = len(parse_export(raw_str))
            with st.spinner(f"Gemma 4 extracting {n} messages..."):
                try:
                    items = pipeline.extract_items(raw_str, "f" + h[:6])
                except Exception as e:
                    st.error(str(e))
                    st.stop()
                if items and all(i.get("request_type") == "extraction_failed" for i in items):
                    st.error(items[0].get("error", "Unknown error"))
                elif items:
                    store.add_items(items, "f" + h[:6], file_hash=h)
        st.session_state["last_uploaded_hash"] = h
        st.rerun()

elif process_btn and single_text.strip():
    raw_str = single_text.strip()
    n = len(parse_export(raw_str))
    label = "s" + str(int(time.time() * 1000))[-8:]
    with st.spinner(f"Gemma 4 extracting {n} messages..."):
        try:
            items = pipeline.extract_items(raw_str, label)
        except Exception as e:
            st.error(str(e))
            st.stop()
        if items and all(i.get("request_type") == "extraction_failed" for i in items):
            st.error(items[0].get("error", "Unknown error"))
        elif items:
            store.add_items(items, label)

items = store.load_items()
if not items:
    st.info("Upload a WhatsApp export or paste a message to begin.")
    st.stop()

status_map = store.get_status_map()
view = pipeline.build_view(items, LANDMARKS, status_map)

if view["failed"]:
    st.warning(f"{len(view['failed'])} messages could not be extracted - review manually")
    if st.button("Retry failed"):
        retried = pipeline.retry_failed(items)
        for i in retried:
            store.update_item(i["report_id"], i)
        st.rerun()
    with st.expander("Failed messages"):
        for f in view["failed"]:
            st.text(f.get("original_text", ""))
            st.error(f.get("error", ""))

with st.sidebar:
    st.markdown("---")
    st.subheader("Photo evidence")
    photo_upload = st.file_uploader("Upload photo", type=["png", "jpg", "jpeg"])
    
    target_options = []
    for r in view.get("requests", []):
        target_options.append({
            "label": f"{r.get('tier')} | {r.get('location_text')} | {r.get('report_id')}",
            "report_id": r.get("report_id")
        })
    
    selected_target = st.selectbox("Target request", options=target_options, format_func=lambda x: x["label"]) if target_options else None
    
    if st.button("Analyze photo") and photo_upload:
        with st.spinner("Analyzing photo..."):
            res = vision.analyze_photo(photo_upload.getvalue(), photo_upload.type)
            st.session_state.last_photo_result = res
            
    if "last_photo_result" in st.session_state:
        res = st.session_state.last_photo_result
        if "error" in res:
            st.error(res["error"])
        else:
            st.json(res)
            
        if st.button("Apply to selected request") and selected_target:
            if "error" not in res:
                store.update_item(selected_target["report_id"], {"photo": res})
                del st.session_state.last_photo_result
                st.rerun()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Messages", view["total"])
c2.metric("Chatter Filtered", len(view["chatter"]))
c3.metric("Active Requests", len(view["requests"]))
c4.metric("Duplicates Merged", view["merged_total"])
c5.metric("Failed", len(view["failed"]))
critical_count = sum(1 for r in view["requests"] if r.get("tier") == "CRITICAL")
if critical_count > 0:
    c6.markdown(f'<div style="background:#b91c1c;padding:12px;border-radius:8px;text-align:center"><span style="font-size:2em;color:white">{critical_count}</span><br><span style="color:#fca5a5">CRITICAL</span></div>', unsafe_allow_html=True)
else:
    c6.metric("Critical", 0)

st.markdown("---")
f_col1, f_col2, f_col3 = st.columns(3)
selected_tiers = f_col1.multiselect("Tier", ["CRITICAL", "HIGH", "MODERATE", "LOW"], default=["CRITICAL", "HIGH", "MODERATE", "LOW"])
selected_statuses = f_col2.multiselect("Status", ["new", "verified", "dispatched", "rescued"], default=["new", "verified", "dispatched"])
search_query = f_col3.text_input("Search (location or text)")

if not view.get("requests"):
    view["requests"] = []
filtered_requests = []
for r in view["requests"]:
    if r.get("tier") not in selected_tiers:
        continue
    if r.get("status") not in selected_statuses:
        continue
    if search_query:
        sq = search_query.lower()
        loc = str(r.get("location_text", "")).lower()
        orig = str(r.get("original_text", "")).lower()
        merged = " ".join([m.get("text", "") for m in r.get("merged_texts", [])]).lower()
        if sq not in loc and sq not in orig and sq not in merged:
            continue
    filtered_requests.append(r)

map_col, table_col = st.columns([1, 1])
TIER_COLOR = {"CRITICAL": "#FF0000", "HIGH": "#FF8C00", "MODERATE": "#FFD700", "LOW": "#00CC44"}

with map_col:
    st.subheader("Live Triage Map")
    # FIX: Changed map_lat to lat and map_lon to lon
    map_rows = [r for r in filtered_requests if r.get("lat") and r.get("lon")]
    if map_rows:
        df_map = pd.DataFrame(map_rows)
        # Create RGBA colors for the glow effect
        color_map = {
            "CRITICAL": [239, 68, 68, 200],  # Red
            "HIGH": [249, 115, 22, 200],     # Orange
            "MODERATE": [234, 179, 8, 200],  # Yellow
            "LOW": [34, 197, 94, 200]        # Green
        }
        df_map["color"] = df_map["tier"].map(color_map).fillna([100, 100, 100, 200])
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_map,
            get_position="[map_lon, map_lat]",
            get_color="color",
            get_radius="tier == 'CRITICAL' ? 300 : 150",
            pickable=True,
            filled=True,
            opacity=0.8
        )
        
        view_state = pdk.ViewState(
            latitude=df_map["map_lat"].mean(),
            longitude=df_map["map_lon"].mean(),
            zoom=11,
            pitch=45,  # 3D tilt
            bearing=0
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"html": "<b>{tier}</b> | {location_text}<br/>People: {people_count}<br/>Water: {water_level}"}
        ))
    else:
        # Default empty map of Chennai if no data is present
        view_state = pdk.ViewState(
            latitude=13.0827,
            longitude=80.2707,
            zoom=11,
            pitch=45,
            bearing=0
        )
        st.pydeck_chart(pdk.Deck(
            initial_view_state=view_state
        ))
    
    st.markdown("**Legend:** <span style='color:#FF0000'>CRITICAL</span> | <span style='color:#FF8C00'>HIGH</span> | <span style='color:#FFD700'>MODERATE</span> | <span style='color:#00CC44'>LOW</span>", unsafe_allow_html=True)
    unmapped = sum(1 for r in filtered_requests if not r.get("lat"))
    if unmapped > 0:
        st.caption(f"{unmapped} requests have no map location")

with table_col:
    st.subheader("Priority Queue")
    if filtered_requests:
        rows = []
        for r in filtered_requests:
            rows.append({
                "Tier": r.get("tier"),
                "Score": r.get("score"),
                "Status": r.get("status"),
                "Location": r.get("location_text"),
                "Mapped": "Yes" if r.get("map_lat") else "No",
                "People": r.get("people_count"),
                "Water": r.get("water_level"),
                "Vulnerable": ", ".join(r.get("vulnerable", [])),
                "Contact": r.get("contact"),
                "Reports": r.get("duplicate_count", 0) + 1,
                "Flags": ", ".join(r.get("flags", [])),
                "Why": "; ".join(r.get("reasons", [])),
                "Evidence": r.get("evidence")
            })
        df_table = pd.DataFrame(rows)
        st.dataframe(
            df_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score",
                    help="Triage severity score",
                    format="%f",
                    min_value=0,
                    max_value=100,
                ),
                "Tier": st.column_config.TextColumn("Tier"),
                "Water": st.column_config.TextColumn("Water Level"),
                "People": st.column_config.NumberColumn("People", format="%d")
            }
        )
            
        csv_rows = []
        for r in filtered_requests:
            csv_rows.append({
                "tier": r.get("tier"),
                "score": r.get("score"),
                "status": r.get("status"),
                "location_text": r.get("location_text"),
                "geo_name": r.get("geo_name"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "people_count": r.get("people_count"),
                "water_level": r.get("water_level"),
                "vulnerable": ", ".join(r.get("vulnerable", [])),
                "hazards": ", ".join(r.get("hazards", [])),
                "contact": r.get("contact"),
                "contact_source": r.get("contact_source"),
                "reports": r.get("duplicate_count", 0) + 1,
                "flags": ", ".join(r.get("flags", [])),
                "reasons": "; ".join(r.get("reasons", [])),
                "evidence": r.get("evidence"),
                "original_text": r.get("original_text"),
                "merged_texts": " || ".join([m.get("text", "") for m in r.get("merged_texts", [])])
            })
        csv_data = pd.DataFrame(csv_rows).to_csv(index=False)
        st.download_button("Export CSV", csv_data, "rescuegrid_export.csv", "text/csv", type="primary")


with st.expander(f"Offers of help ({len(view['offers'])})"):
    for o in view["offers"]:
        st.text(o.get("original_text", ""))

with st.expander(f"Chatter filtered ({len(view['chatter'])}) - check nothing urgent was filtered"):
    for c in view["chatter"]:
        st.text(c.get("original_text", ""))

with st.expander("Status audit log"):
    st.dataframe(pd.DataFrame(store.get_status_log()))
