import unittest
from sankat.models import RequestItem, ExtractedSOS
from sankat.dedupe import find_duplicate, merge_duplicate


class TestDedupe(unittest.TestCase):
    def test_find_duplicate_matches(self):
        existing_item = RequestItem(
            id="req_101",
            location_text="Velachery 100ft Road near Vijayanagar bus stop",
            lat=12.9750,
            lon=80.2200,
            tier="CRITICAL",
            score=85,
            people_count=4,
            vulnerable_tags=["elderly"],
            water_level="chest",
            status="new",
            duplicate_count=0,
            contact="9840123456",
            landmark_matched="Velachery",
            timestamp="10:00 AM",
            raw_excerpt="Velachery 100ft road near Vijayanagar bus stand 4 people",
            is_exact_address=True
        )

        incoming = ExtractedSOS(
            location_text="Velachery 100ft Rd near Vijayanagar Bus Stop",
            people_count=4,
            vulnerable_tags=["elderly"],
            water_level="chest",
            contact="9840123456",
            raw_text="Fwd: Urgent rescue Velachery 100ft Rd near Vijayanagar Bus Stop 4 people trapped"
        )

        match, score = find_duplicate(incoming, [existing_item])
        self.assertIsNotNone(match)
        self.assertGreaterEqual(score, 80)
        self.assertEqual(match.id, "req_101")

    def test_merge_duplicate(self):
        existing_item = RequestItem(
            id="req_101",
            location_text="Velachery 100ft Road",
            lat=12.9750,
            lon=80.2200,
            tier="HIGH",
            score=65,
            people_count=2,
            vulnerable_tags=[],
            water_level="waist",
            status="new",
            duplicate_count=0,
            contact=None,
            landmark_matched="Velachery",
            timestamp="10:00 AM",
            raw_excerpt="Velachery 100ft road waist deep",
            is_exact_address=False
        )

        incoming = ExtractedSOS(
            location_text="Velachery 100ft Road",
            people_count=4,
            vulnerable_tags=["infant"],
            water_level="chest",
            contact="9840199999",
            raw_text="Velachery 100ft road chest deep infant inside"
        )

        merged = merge_duplicate(existing_item, incoming, 95.0)
        self.assertEqual(merged.duplicate_count, 1)
        self.assertEqual(merged.water_level, "chest")
        self.assertEqual(merged.people_count, 4)
        self.assertIn("infant", merged.vulnerable_tags)
        self.assertEqual(merged.contact, "9840199999")


if __name__ == "__main__":
    unittest.main()
