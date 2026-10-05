import csv
import math
import re
from pathlib import Path
from rapidfuzz import fuzz

GENERIC = {"road", "street", "main", "cross", "nagar", "colony", "area", "near", 
           "side", "bridge", "signal", "bus", "stand", "junction", "tower", "temple", 
           "tank", "lake", "river", "bank", "bazaar", "market", "flyover", "station", 
           "park", "school", "hospital", "apartment", "apartments", "ground", "floor", 
           "east", "west", "north", "south", "old", "new", "town", "city", "village", 
           "beach", "harbour", "port", "industrial", "estate", "toll", "gate", "subway", 
           "marsh", "creek", "camp", "layout", "extension"}

def normalize(text):
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[^a-z0-9]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def load_landmarks(path=None):
    if path is None:
        root = Path(__file__).resolve().parent.parent
        path = root / "packs" / "tamil_nadu" / "landmarks.csv"
    
    landmarks = []
    if not Path(path).exists():
        return landmarks
        
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (ValueError, KeyError):
                continue
            
            aliases_raw = row.get("aliases", "").split("|")
            aliases = [a.strip().lower() for a in aliases_raw if a.strip()]
            
            landmarks.append({
                "id": row.get("landmark_id"),
                "name": row.get("name", "").strip(),
                "lat": lat,
                "lon": lon,
                "aliases": aliases
            })
    return landmarks

def resolve(location_text, landmarks):
    t = normalize(location_text)
    if not t:
        return None
        
    best_exact = None
    best_exact_len = -1
    
    for lm in landmarks:
        candidates = [normalize(lm["name"])] + [normalize(a) for a in lm["aliases"]]
        for cand in candidates:
            if len(cand) >= 4:
                pattern = r'\b' + re.escape(cand) + r'\b'
                if re.search(pattern, t):
                    if len(cand) > best_exact_len:
                        best_exact_len = len(cand)
                        best_exact = lm
                        
    if best_exact:
        return {
            "name": best_exact["name"],
            "lat": best_exact["lat"],
            "lon": best_exact["lon"],
            "score": 100,
            "method": "exact",
            "precision": "landmark"
        }
        
    t_tokens = [tok for tok in t.split() if len(tok) >= 5 and tok not in GENERIC]
    if not t_tokens:
        return None
        
    best_fuzzy = None
    best_score = -1
    
    for lm in landmarks:
        candidates = [normalize(lm["name"])] + [normalize(a) for a in lm["aliases"]]
        for cand in candidates:
            cand_tokens = [tok for tok in cand.split() if len(tok) >= 5 and tok not in GENERIC]
            for c_tok in cand_tokens:
                for t_tok in t_tokens:
                    score = fuzz.ratio(t_tok, c_tok)
                    if score > best_score:
                        best_score = score
                        best_fuzzy = lm
                        
    if best_score >= 85 and best_fuzzy:
        return {
            "name": best_fuzzy["name"],
            "lat": best_fuzzy["lat"],
            "lon": best_fuzzy["lon"],
            "score": best_score,
            "method": "fuzzy",
            "precision": "landmark"
        }
        
    return None

def spread(requests):
    groups = {}
    for req in requests:
        lat = req.get("lat")
        lon = req.get("lon")
        if lat is not None and lon is not None:
            groups.setdefault((lat, lon), []).append(req)
        else:
            req["map_lat"] = None
            req["map_lon"] = None
            
    for (lat, lon), group in groups.items():
        for k, req in enumerate(group):
            if k == 0:
                req["map_lat"] = lat
                req["map_lon"] = lon
            else:
                angle = k * 2.399963
                radius = 0.00035 * math.sqrt(k)
                req["map_lat"] = lat + radius * math.sin(angle)
                req["map_lon"] = lon + radius * math.cos(angle)
                
    return requests
