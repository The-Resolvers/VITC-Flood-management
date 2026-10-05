import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

from wa_parser import parse_export, find_phones, mask_phones

def run_tests():
    checks = 0

    # 1. android 12h line
    txt = "12/04/25, 10:15 AM - +91 90000 00001: Hello world"
    msgs = parse_export(txt)
    assert len(msgs) == 1, msgs
    assert msgs[0]["sender"] == "+91 90000 00001"
    assert msgs[0]["text"] == "Hello world"
    assert msgs[0]["ts"] == "2025-04-12T10:15"
    checks += 1
    print("PASS android 12h")

    # 2. multi-line
    txt = "12/04/25, 10:15 AM - Name: Line1\nLine2\n  Line3"
    msgs = parse_export(txt)
    assert msgs[0]["text"] == "Line1 Line2 Line3", msgs[0]["text"]
    checks += 1
    print("PASS multi-line")

    # 3. system line skipped, media omitted
    txt = "12/04/25, 10:15 AM - Messages to this group are now secured with end-to-end encryption.\n12/04/25, 10:16 AM - Name: <Media omitted>\n12/04/25, 10:17 AM - Name: Good"
    msgs = parse_export(txt)
    assert len(msgs) == 1, msgs
    assert msgs[0]["text"] == "Good"
    checks += 1
    print("PASS system/media")

    # 4. iOS bracket
    txt = "[12/04/25, 10:15:30 AM] iOS User: Bracket format"
    msgs = parse_export(txt)
    assert len(msgs) == 1
    assert msgs[0]["ts"] == "2025-04-12T10:15", msgs[0]["ts"]
    checks += 1
    print("PASS iOS bracket")

    # 5. 24h
    txt = "12/04/25, 22:15 - Name: 24h format"
    msgs = parse_export(txt)
    assert msgs[0]["ts"] == "2025-04-12T22:15", msgs[0]["ts"]
    checks += 1
    print("PASS 24h format")

    # 6. U+202F before PM
    txt = "12/04/25, 10:15\u202fPM - Name: unicode space"
    msgs = parse_export(txt)
    assert msgs[0]["ts"] == "2025-04-12T22:15", msgs[0]["ts"]
    checks += 1
    print("PASS U+202F space")

    # 7. Tamil body preserved
    txt = "12/04/25, 10:15 AM - Name: \u0ba4\u0bae\u0bbf\u0bb4\u0bcd"
    msgs = parse_export(txt)
    assert msgs[0]["text"] == "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd"
    checks += 1
    print("PASS Tamil body")

    # 8. fallback
    msgs = parse_export("Velachery 4 per stuck")
    assert len(msgs) == 1
    assert msgs[0]["sender"] is None
    assert msgs[0]["ts"] is None
    checks += 1
    print("PASS fallback")

    # 9. find_phones
    assert find_phones("+91 90000 00011") == ["+919000000011"]
    assert find_phones("90000-00011") == ["+919000000011"]
    assert find_phones("9000000012") == ["+919000000012"]
    assert find_phones("Rs 5000 per family 12/04/25") == []
    checks += 1
    print("PASS find_phones")

    # 10. mask_phones
    assert mask_phones("Call 90000-00011 now") == "Call [PHONE] now"
    checks += 1
    print("PASS mask_phones")

    # 11. demo
    demo_path = Path(__file__).resolve().parents[1] / "Flood-management" / "demo" / "demo_data_tn.txt"
    if demo_path.exists():
        with open(demo_path, "r", encoding="utf-8", errors="ignore") as f:
            demo_msgs = parse_export(f.read())
        assert len(demo_msgs) == 53
        assert demo_msgs[0]["sender"] == "+91 90000 00011"
        cuddalore_msg = next(m for m in demo_msgs if m["sender"] == "+91 90000 00044")
        assert "Cuddalore" in cuddalore_msg["text"]
        checks += 1
        print("PASS demo file")
    else:
        print("SKIP demo file")
        checks += 1

    print(f"DONE {checks}")
    
if __name__ == '__main__':
    run_tests()
