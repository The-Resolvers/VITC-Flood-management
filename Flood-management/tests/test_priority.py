import unittest
from sankat.priority import PriorityEngine


class TestPriority(unittest.TestCase):
    def test_priority_calculation(self):
        engine = PriorityEngine()

        # Critical tier case: Chest water + infant + elderly
        score, tier = engine.calculate(
            water_level="chest",
            people_count=5,
            vulnerable_tags=["infant", "elderly"],
            duplicate_count=2
        )
        self.assertEqual(tier, "CRITICAL")
        self.assertGreaterEqual(score, 70)

        # Low/Medium tier case: Ankle water + 1 person
        score_low, tier_low = engine.calculate(
            water_level="ankle",
            people_count=1,
            vulnerable_tags=[],
            duplicate_count=0
        )
        self.assertIn(tier_low, ("LOW", "MEDIUM"))
        self.assertLess(score_low, 50)


if __name__ == "__main__":
    unittest.main()
