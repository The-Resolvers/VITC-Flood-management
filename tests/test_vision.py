import sys
from pathlib import Path
import io

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

from PIL import Image
import vision
import pipeline

def create_test_image():
    img = Image.new("RGB", (100, 100), color="red")
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def run_tests():
    checks = 0
    img_bytes = create_test_image()
    
    # 1 a valid tiny generated PNG with a fake JSON reply gives the expected dict
    def fake_client(b):
        return '```json\n{"water_level": "chest", "hazards": ["strong_current"], "confidence": 0.9, "evidence": "car submerged"}\n```'
        
    res1 = vision.analyze_photo(img_bytes, "image/png", client=fake_client)
    assert res1.get("water_level") == "chest"
    assert "strong_current" in res1.get("hazards")
    assert res1.get("confidence") == 0.9
    assert res1.get("evidence") == "car submerged"
    checks += 1
    
    # 2 invalid image bytes give {"error": ...}
    res2 = vision.analyze_photo(b"not an image", "image/png", client=fake_client)
    assert "error" in res2
    checks += 1
    
    # 3 an API exception gives {"error": ...}
    def failing_client(b):
        raise RuntimeError("API failed")
    res3 = vision.analyze_photo(img_bytes, "image/png", client=failing_client)
    assert "error" in res3
    assert "RuntimeError" in res3["error"]
    checks += 1
    
    # 4 an invalid water_level from the model becomes "unknown"
    def fake_client_invalid(b):
        return '{"water_level": "very_deep", "hazards": []}'
    res4 = vision.analyze_photo(img_bytes, "image/png", client=fake_client_invalid)
    assert res4.get("water_level") == "unknown"
    checks += 1
    
    # 5 build_view applies a photo override and sets photo_conflict correctly for both higher and lower cases
    items = [
        {"report_id": "r1", "request_type": "rescue", "water_level": "knee", "photo": {"water_level": "chest", "evidence": "pic1"}},
        {"report_id": "r2", "request_type": "rescue", "water_level": "chest", "photo": {"water_level": "knee", "evidence": "pic2"}},
        {"report_id": "r3", "request_type": "rescue", "water_level": "unknown", "photo": {"water_level": "waist", "evidence": "pic3"}}
    ]
    view = pipeline.build_view(items, [])
    reqs = view["requests"]
    
    r1 = next(r for r in reqs if r.get("photo_evidence") == "pic1")
    assert r1["water_level"] == "chest"
    assert r1.get("photo_conflict") is True
    
    r2 = next(r for r in reqs if r.get("photo_evidence") == "pic2")
    assert r2["water_level"] == "chest"
    assert r2.get("photo_conflict") is True
    
    r3 = next(r for r in reqs if r.get("photo_evidence") == "pic3")
    assert r3["water_level"] == "waist"
    assert r3.get("photo_conflict") is not True
    
    checks += 1
    print(f"PASS {checks}")

if __name__ == "__main__":
    run_tests()
