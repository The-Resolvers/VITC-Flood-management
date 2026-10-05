from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractedSOS(BaseModel):
    location_text: str = ""
    people_count: Optional[int] = 1
    vulnerable_tags: List[str] = Field(default_factory=list)
    water_level: str = "unknown"
    contact: Optional[str] = None
    raw_text: str = ""
    timestamp: Optional[str] = None


class RequestItem(BaseModel):
    id: str
    location_text: str
    lat: float
    lon: float
    tier: str  # CRITICAL, HIGH, MEDIUM, LOW
    score: int
    people_count: int
    vulnerable_tags: List[str] = Field(default_factory=list)
    water_level: str
    status: str = "new"  # new, contacted, resolved
    duplicate_count: int = 0
    contact: Optional[str] = None
    landmark_matched: Optional[str] = None
    timestamp: Optional[str] = None
    raw_excerpt: Optional[str] = None
    is_exact_address: bool = True
    address_note: Optional[str] = "Exact address pinpointed"


class RequestsResponse(BaseModel):
    total: int
    duplicates_filtered: int
    critical_count: int
    high_count: int
    requests: List[RequestItem]


class UploadSummary(BaseModel):
    messages_processed: int
    unique_requests_created: int
    duplicates_merged: int
    critical_cases: int
