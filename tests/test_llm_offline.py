import sys
import os
import json
from types import SimpleNamespace
from pathlib import Path

# Setup sys.path
sys.path.append(str(Path(__file__).resolve().parents[1] / "Flood-management"))

# Environment for test
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["SANKAT_CACHE_DIR"] = "test_llm_cache"
import shutil
if os.path.exists("test_llm_cache"):
    shutil.rmtree("test_llm_cache")

import llm

class FakeModels:
    def __init__(self):
        self.call_count = 0
        self.last_contents = None
        self.raise_on_next = None
        self.responses = []
        self.raise_every_time = False
        self.raise_developer_instruction_once = False
        
    def generate_content(self, model, contents, config):
        self.call_count += 1
        self.last_contents = contents
        
        if self.raise_every_time:
            raise RuntimeError("API Error")
            
        if self.raise_developer_instruction_once:
            self.raise_developer_instruction_once = False
            raise RuntimeError("some Developer instruction error")
            
        if self.raise_on_next:
            err = self.raise_on_next
            self.raise_on_next = None
            raise err
            
        if self.responses:
            return SimpleNamespace(text=self.responses.pop(0))
            
        return SimpleNamespace(text="[]")

def run_tests():
    fake = FakeModels()
    llm.client = SimpleNamespace(models=fake)
    checks = 0

    # 1 10 messages gives 2 API calls (8 + 2) and 10 results in order
    fake.call_count = 0
    fake.responses = [
        json.dumps([{"report_id": f"r{i}", "request_type": "info"} for i in range(1, 9)]),
        json.dumps([{"report_id": f"r{i}", "request_type": "info"} for i in range(9, 11)])
    ]
    msgs = [{"report_id": f"r{i}", "text": "msg"} for i in range(1, 11)]
    # run with no_cache=1 so we actually do calls
    os.environ["SANKAT_NO_CACHE"] = "1"
    res = llm.extract_reports(msgs)
    assert fake.call_count == 2, fake.call_count
    assert len(res) == 10
    for i in range(1, 11):
        assert res[i-1]["report_id"] == f"r{i}"
    checks += 1
    print("PASS 10 msgs 2 calls")

    # 2 JSON wrapped in prose and code fences parses
    os.environ["SANKAT_NO_CACHE"] = "1"
    fake.responses = [
        "Here is the result:\n```json\n" + json.dumps([{"report_id": "r1", "request_type": "chatter"}]) + "\n```\nHope it helps!"
    ]
    res = llm.extract_reports([{"report_id": "r1", "text": "a"}])
    assert res[0]["request_type"] == "chatter"
    checks += 1
    print("PASS JSON wrapped")

    # 3 one id missing from the response is recovered by the single retry
    fake.responses = [
        json.dumps([{"report_id": "r1", "request_type": "chatter"}]), # misses r2
        json.dumps([{"report_id": "r2", "request_type": "chatter"}])
    ]
    fake.call_count = 0
    res = llm.extract_reports([{"report_id": "r1", "text": "a"}, {"report_id": "r2", "text": "b"}])
    assert fake.call_count == 2
    assert len(res) == 2
    assert res[0]["report_id"] == "r1"
    assert res[1]["report_id"] == "r2"
    checks += 1
    print("PASS one id missing recovered")

    # 4 an id missing twice becomes extraction_failed with error "not returned by model"
    fake.responses = [
        json.dumps([{"report_id": "r1", "request_type": "chatter"}]), # misses r2
        json.dumps([]) # misses r2 again
    ]
    res = llm.extract_reports([{"report_id": "r1", "text": "a"}, {"report_id": "r2", "text": "b"}])
    assert len(res) == 2
    assert res[1]["report_id"] == "r2"
    assert res[1]["request_type"] == "extraction_failed"
    assert res[1]["error"] == "not returned by model"
    checks += 1
    print("PASS missing twice")

    # 5 normalization
    fake.responses = [
        json.dumps([{
            "report_id": "r1",
            "people_count": "4",
            "vulnerable": "elderly, child",
            "water_level": "knee-deep",
            "request_type": " Rescue ",
            "evidence": "a b c d e f g h i j k l m n o"
        }, {
            "report_id": "r2",
            "people_count": "four",
            "request_type": "chatter"
        }])
    ]
    res = llm.extract_reports([{"report_id": "r1", "text": "a"}, {"report_id": "r2", "text": "b"}])
    assert res[0]["people_count"] == 4, res[0]["people_count"]
    assert res[0]["vulnerable"] == ["elderly", "child_infant"], res[0]["vulnerable"]
    assert res[0]["water_level"] == "unknown", res[0]["water_level"]
    assert res[0]["request_type"] == "rescue", res[0]["request_type"]
    assert res[0]["evidence"] == "a b c d e f g h i j k l"
    assert res[1]["people_count"] is None
    checks += 1
    print("PASS normalization")

    # 6 an API exception on every call gives all extraction_failed and no raised exception
    fake.raise_every_time = True
    fake.call_count = 0
    res = llm.extract_reports([{"report_id": "r1", "text": "a"}])
    assert len(res) == 1
    assert res[0]["request_type"] == "extraction_failed"
    assert "RuntimeError" in res[0]["error"]
    assert fake.call_count == 2 # initial + 1 retry
    fake.raise_every_time = False
    checks += 1
    print("PASS API exception")

    # 7 a second identical call makes 0 API calls (cache hit)
    os.environ["SANKAT_NO_CACHE"] = "" # enable cache
    fake.call_count = 0
    fake.responses = [json.dumps([{"report_id": "r1", "request_type": "chatter"}])]
    res1 = llm.extract_reports([{"report_id": "r1", "text": "cachetest"}])
    assert fake.call_count == 1
    fake.responses = [json.dumps([{"report_id": "r1", "request_type": "should_not_see"}])]
    res2 = llm.extract_reports([{"report_id": "r1", "text": "cachetest"}])
    assert fake.call_count == 1 # still 1
    assert res2[0]["request_type"] == "chatter"
    checks += 1
    print("PASS cache hit")

    # 8 first call raises an error containing "Developer instruction" -> fallback path succeeds, and the retried contents begin with the system prompt text
    llm._NO_SYSTEM = False
    fake.raise_developer_instruction_once = True
    fake.responses = [json.dumps([{"report_id": "r1", "request_type": "rescue"}])]
    os.environ["SANKAT_NO_CACHE"] = "1"
    res = llm.extract_reports([{"report_id": "r1", "text": "devinstrtest"}])
    assert "MESSAGES:" in fake.last_contents, fake.last_contents
    assert res[0]["request_type"] == "rescue"
    assert llm._NO_SYSTEM == True
    checks += 1
    print("PASS developer instruction")

    print(f"DONE {checks}")

if __name__ == "__main__":
    run_tests()
