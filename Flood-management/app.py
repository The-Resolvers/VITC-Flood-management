import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from sankat.db import (
    init_db, clear_db, get_all_requests,
    get_total_duplicate_count, update_status
)
from sankat.models import RequestsResponse, UploadSummary
from sankat.pipeline import ingest_whatsapp_dump
from sankat.extract import analyze_flood_image

app = FastAPI(
    title="SANKAT — AI Flood Triage & Caller Guidance System",
    description="Deterministic flood triage engine with Gemma 4 extraction and RapidFuzz deduplication.",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEMO_FILE = Path(__file__).resolve().parent / "demo" / "sample_whatsapp.txt"


@app.on_event("startup")
def on_startup():
    init_db()
    current = get_all_requests()
    if not current and DEMO_FILE.exists():
        with open(DEMO_FILE, "r", encoding="utf-8") as f:
            ingest_whatsapp_dump(f.read())


@app.get("/api/requests", response_model=RequestsResponse)
def get_requests():
    reqs = get_all_requests()
    total_dupes = get_total_duplicate_count()
    crit = sum(1 for r in reqs if r.tier == "CRITICAL")
    high = sum(1 for r in reqs if r.tier == "HIGH")

    return RequestsResponse(
        total=len(reqs),
        duplicates_filtered=total_dupes,
        critical_count=crit,
        high_count=high,
        requests=reqs
    )


@app.post("/api/upload")
async def upload_whatsapp_file(
    file: UploadFile = File(...),
    clear_existing: str = Form("true")
):
    fn = (file.filename or "").lower()
    if not (fn.endswith(".txt") or fn.endswith(".csv") or fn.endswith(".log")):
        raise HTTPException(status_code=400, detail="Please upload a .txt WhatsApp export file.")

    clear_flag = str(clear_existing).lower() in ("true", "1", "yes")
    if clear_flag:
        clear_db()

    content_bytes = await file.read()
    text = content_bytes.decode("utf-8", errors="ignore")

    summary = ingest_whatsapp_dump(text)
    return {
        "status": "success",
        "summary": summary.dict(),
        "message": f"Successfully ingested {summary.messages_processed} messages: {summary.unique_requests_created} verified locations mapped, {summary.duplicates_merged} viral duplicates filtered out!"
    }


@app.post("/api/demo-load")
def load_demo_data():
    if not DEMO_FILE.exists():
        raise HTTPException(status_code=404, detail="Demo file not found.")
    clear_db()
    with open(DEMO_FILE, "r", encoding="utf-8") as f:
        summary = ingest_whatsapp_dump(f.read())
    return {
        "status": "success",
        "summary": summary.dict()
    }


@app.post("/api/reset")
def reset_database():
    clear_db()
    return {"status": "cleared", "total": 0}


@app.post("/api/dispatch/{req_id}")
def mark_dispatched(req_id: str):
    success = update_status(req_id, "contacted")
    if not success:
        raise HTTPException(status_code=404, detail="Request not found.")
    return {"status": "success", "req_id": req_id, "new_status": "contacted"}


@app.post("/api/analyze-photo")
async def analyze_photo_endpoint(file: UploadFile = File(...)):
    content_bytes = await file.read()
    result = analyze_flood_image(content_bytes, file.filename)
    return {
        "status": "success",
        "filename": file.filename,
        "analysis": result
    }


# Ensure static directory exists
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "SANKAT API is live. Place index.html in static/"}
