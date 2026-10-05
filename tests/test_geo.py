import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

import geo

def run_tests():
    landmarks = [
        {"id": "1", "name": "Velachery", "lat": 13.0, "lon": 80.0, "aliases": ["velachery signal", "valachery"]},
        {"id": "2", "name": "Anna Nagar", "lat": 13.1, "lon": 80.1, "aliases": ["anna nagar tower", "annanagar"]},
        {"id": "3", "name": "T Nagar", "lat": 13.2, "lon": 80.2, "aliases": ["tnagar", "pondy bazaar"]},
        {"id": "4", "name": "Tambaram", "lat": 13.3, "lon": 80.3, "aliases": ["tambaram east", "west tambaram"]},
        {"id": "5", "name": "Mudichur", "lat": 13.4, "lon": 80.4, "aliases": ["mudichur road"]},
        {"id": "6", "name": "Madipakkam", "lat": 13.5, "lon": 80.5, "aliases": ["madipakkam koot road"]}
    ]
    
    checks = 0
    
    # 1 "Velachery signal pakkam" -> Velachery, method exact
    res1 = geo.resolve("Velachery signal pakkam", landmarks)
    assert res1 and res1["name"] == "Velachery" and res1["method"] == "exact", f"Failed 1: {res1}"
    checks += 1
    
    # 2 "valachery" -> Velachery
    res2 = geo.resolve("valachery", landmarks)
    assert res2 and res2["name"] == "Velachery", "Failed 2"
    checks += 1
    
    # 3 "Valacheri" -> Velachery, method fuzzy
    res3 = geo.resolve("Valacheri", landmarks)
    assert res3 and res3["name"] == "Velachery" and res3["method"] == "fuzzy", "Failed 3"
    checks += 1
    
    # 4 "signal" -> None, "road" -> None, "Nagar" -> None
    assert geo.resolve("signal", landmarks) is None, "Failed 4a"
    assert geo.resolve("road", landmarks) is None, "Failed 4b"
    assert geo.resolve("Nagar", landmarks) is None, "Failed 4c"
    checks += 1
    
    # 5 "Anna Nagar Tower" -> Anna Nagar (not T Nagar)
    res5 = geo.resolve("Anna Nagar Tower", landmarks)
    assert res5 and res5["name"] == "Anna Nagar", f"Failed 5: {res5}"
    checks += 1
    
    # 6 "Kotturpuram near bridge" -> None
    assert geo.resolve("Kotturpuram near bridge", landmarks) is None, "Failed 6"
    checks += 1
    
    # 7 "Mudichur road Tambaram west side" -> Mudichur
    res7 = geo.resolve("Mudichur road Tambaram west side", landmarks)
    assert res7 and res7["name"] == "Mudichur", "Failed 7"
    checks += 1
    
    # 8 "T Nagar Pondy Bazaar" -> T Nagar
    res8 = geo.resolve("T Nagar Pondy Bazaar", landmarks)
    assert res8 and res8["name"] == "T Nagar", "Failed 8"
    checks += 1
    
    # 9 "Madipakkam koot road near temple" -> Madipakkam
    res9 = geo.resolve("Madipakkam koot road near temple", landmarks)
    assert res9 and res9["name"] == "Madipakkam", "Failed 9"
    checks += 1
    
    # 10 spread: 3 requests at one landmark -> first keeps the exact coordinates, the other two differ and stay within 0.002 degrees
    reqs = [{"lat": 10.0, "lon": 20.0}, {"lat": 10.0, "lon": 20.0}, {"lat": 10.0, "lon": 20.0}]
    spread_reqs = geo.spread(reqs)
    assert spread_reqs[0]["map_lat"] == 10.0 and spread_reqs[0]["map_lon"] == 20.0, "Failed 10a"
    assert spread_reqs[1]["map_lat"] != 10.0 or spread_reqs[1]["map_lon"] != 20.0, "Failed 10b"
    assert abs(spread_reqs[1]["map_lat"] - 10.0) < 0.002, "Failed 10c"
    checks += 1
    
    # 11 if packs/tamil_nadu/landmarks.csv exists, load_landmarks returns >= 15 rows
    csv_landmarks = geo.load_landmarks()
    csv_path = Path(geo.__file__).resolve().parent.parent.joinpath("packs", "tamil_nadu", "landmarks.csv")
    if csv_path.exists() and csv_path.stat().st_size > 0:
        assert len(csv_landmarks) >= 15, f"Failed 11, got {len(csv_landmarks)}"
    checks += 1
    
    print(f"PASS {checks}")

if __name__ == "__main__":
    run_tests()
