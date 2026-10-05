import csv
import re
from typing import Tuple, Optional, List, Dict
from rapidfuzz import fuzz
from .config import LANDMARKS_CSV

# Fallback centroid: Chennai Central / Guindy Main Hub
DEFAULT_LAT = 13.0067
DEFAULT_LON = 80.2025


class GeoResolver:
    def __init__(self, csv_path=LANDMARKS_CSV):
        self.landmarks: List[Dict] = []
        self._load_landmarks(csv_path)

    def _load_landmarks(self, path):
        if not path.exists():
            return
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aliases = [a.strip().lower() for a in row.get("aliases", "").split(";") if a.strip()]
                name = row["name"].strip()
                aliases.append(name.lower())
                # Sort aliases by length descending
                aliases.sort(key=lambda s: len(s), reverse=True)
                self.landmarks.append({
                    "name": name,
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "aliases": aliases
                })

    def check_is_exact(self, text: str) -> bool:
        """
        Determines whether the victim message provides a specific address
        (e.g., street, road, floor, near landmark, cross, avenue, flat)
        or just a vague/broad area mention.
        """
        lower = text.lower()

        exact_tokens = [
            "road", "rd", "street", "st", "lane", "cross", "nagar", "colony",
            "avenue", "salai", "near", "opp", "opposite", "behind", "backside",
            "bus stand", "bus stop", "signal", "bridge", "temple", "church", "mosque",
            "school", "hospital", "mall", "flat", "apartment", "ground floor",
            "1st floor", "2nd floor", "terrace", "roof", "block", "door", "no.", "house"
        ]

        has_specific_number = bool(re.search(r"\b(\d{1,3}(?:st|nd|rd|th)?\s*(?:street|st|cross|lane|road|block|ft|feet))\b", lower))
        has_token = any(re.search(r"\b" + re.escape(t) + r"\b", lower) for t in exact_tokens)
        words = len(text.strip().split())

        return has_specific_number or (has_token and words >= 2)

    def resolve(self, text: str) -> Tuple[float, float, str, bool, str]:
        """
        Matches text against Chennai landmarks.
        Prioritizes the longest, most specific matching landmark/alias phrase first.
        Returns: (lat, lon, matched_landmark_name, is_exact_address, address_note)
        """
        if not text or len(text.strip()) < 3:
            return DEFAULT_LAT, DEFAULT_LON, "Chennai Central", False, "Not exact address provided (Centered on Chennai Main Hub)"

        query = text.lower()

        # Step 1: Longest specific alias/name match across all landmarks
        best_exact_match = None
        longest_alias_len = 0

        for lm in self.landmarks:
            for alias in lm["aliases"]:
                if re.search(r"\b" + re.escape(alias) + r"\b", query):
                    if len(alias) > longest_alias_len:
                        longest_alias_len = len(alias)
                        best_exact_match = lm

        if best_exact_match and longest_alias_len >= 3:
            is_exact = self.check_is_exact(text)
            note = f"Exact address pinpointed: {best_exact_match['name']}" if is_exact else f"Not exact address provided (Centered on Main Area: {best_exact_match['name']})"
            return best_exact_match["lat"], best_exact_match["lon"], best_exact_match["name"], is_exact, note

        # Step 2: Fuzzy matching fallback
        best_fuzzy = None
        highest_score = 0.0

        for lm in self.landmarks:
            for alias in lm["aliases"]:
                score = fuzz.token_set_ratio(alias, query)
                if score > highest_score:
                    highest_score = score
                    best_fuzzy = lm

        if best_fuzzy and highest_score >= 65.0:
            is_exact = self.check_is_exact(text)
            note = f"Exact address pinpointed: {best_fuzzy['name']}" if is_exact else f"Not exact address provided (Centered on Main Area: {best_fuzzy['name']})"
            return best_fuzzy["lat"], best_fuzzy["lon"], best_fuzzy["name"], is_exact, note

        # Fallback to main central area
        return DEFAULT_LAT, DEFAULT_LON, "Chennai Main Hub", False, "Not exact address provided (Centered on Main Hub — Call victim for street details)"


geo_resolver = GeoResolver()
