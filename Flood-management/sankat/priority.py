import yaml
from typing import Tuple, List
from .config import PRIORITY_YAML


class PriorityEngine:
    def __init__(self, config_path=PRIORITY_YAML):
        self.water_weights = {
            "roof": 50,
            "chest": 35,
            "waist": 22,
            "knee": 12,
            "ankle": 5,
            "unknown": 10
        }
        self.vulnerability_weights = {
            "infant": 18,
            "child": 14,
            "pregnant": 20,
            "elderly": 16,
            "medical_emergency": 25,
            "disabled": 18,
            "dialysis": 25
        }
        self.people_multiplier = 2.5
        self.people_cap = 25
        self.duplicate_multiplier = 2.0
        self.duplicate_cap = 10

        self.threshold_critical = 70
        self.threshold_high = 45
        self.threshold_medium = 25

        self._load_config(config_path)

    def _load_config(self, path):
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if "water_level_weights" in data:
                    self.water_weights.update(data["water_level_weights"])
                if "vulnerability_weights" in data:
                    self.vulnerability_weights.update(data["vulnerability_weights"])
                if "thresholds" in data:
                    self.threshold_critical = data["thresholds"].get("critical", 70)
                    self.threshold_high = data["thresholds"].get("high", 45)
                    self.threshold_medium = data["thresholds"].get("medium", 25)
        except Exception:
            pass

    def calculate(
        self,
        water_level: str,
        people_count: int,
        vulnerable_tags: List[str],
        duplicate_count: int = 0
    ) -> Tuple[int, str]:
        """
        Deterministic scoring:
        Score = Water Level + People Count + Vulnerability Tags + Duplicate Corroboration
        Returns: (score, tier)
        """
        score = 0

        # 1. Water Level
        wl = (water_level or "").lower().strip()
        score += self.water_weights.get(wl, self.water_weights.get("unknown", 10))

        # 2. People Count
        p_count = max(1, people_count or 1)
        p_score = min(self.people_cap, int(p_count * self.people_multiplier))
        score += p_score

        # 3. Vulnerability Tags
        for tag in vulnerable_tags:
            tag_clean = tag.lower().strip()
            score += self.vulnerability_weights.get(tag_clean, 10)

        # 4. Duplicate Corroboration (More people reporting validates urgency)
        dupe_score = min(self.duplicate_cap, int(duplicate_count * self.duplicate_multiplier))
        score += dupe_score

        # Determine Tier
        if score >= self.threshold_critical:
            tier = "CRITICAL"
        elif score >= self.threshold_high:
            tier = "HIGH"
        elif score >= self.threshold_medium:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        return score, tier


priority_engine = PriorityEngine()
