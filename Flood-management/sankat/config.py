import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "Flood-management" / ".env")

PACK_DIR = BASE_DIR / "packs" / "tamil_nadu"
LANDMARKS_CSV = PACK_DIR / "landmarks.csv"
PRIORITY_YAML = PACK_DIR / "priority.yaml"
DB_PATH = BASE_DIR / "sankat.db"

# LLM Configuration
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

# Deduplication Thresholds
DEDUPE_SIMILARITY_THRESHOLD = 85.0
DEDUPE_WINDOW_HOURS = 6.0
