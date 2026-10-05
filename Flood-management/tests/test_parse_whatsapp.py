import unittest
from sankat.parse_whatsapp import parse_whatsapp_text


class TestParseWhatsapp(unittest.TestCase):
    def test_parse_standard_ios_format(self):
        raw = "[05/10/26, 10:15:23 AM] Harish: URGENT: Water entering ground floor in Velachery, 4 people trapped."
        messages = parse_whatsapp_text(raw)
        self.assertEqual(len(messages), 1)
        self.assertIn("Velachery", messages[0]["text"])
        self.assertEqual(messages[0]["sender"], "Harish")

    def test_parse_android_format(self):
        raw = "05/10/2026, 14:30 - Akash: 5 people trapped on terrace in Mudichur road near bus stand. Water waist deep."
        messages = parse_whatsapp_text(raw)
        self.assertEqual(len(messages), 1)
        self.assertIn("Mudichur", messages[0]["text"])
        self.assertEqual(messages[0]["sender"], "Akash")

    def test_multi_line_continuation(self):
        raw = """05/10/2026, 11:00 - Citizen: Emergency in Kolathur Kumaran Nagar.
Water is waist deep.
Elderly person needing insulin. Call 9840123456."""
        messages = parse_whatsapp_text(raw)
        self.assertEqual(len(messages), 1)
        self.assertIn("Kolathur Kumaran Nagar", messages[0]["text"])
        self.assertIn("Elderly person needing insulin", messages[0]["text"])

    def test_plain_forward_without_headers(self):
        raw = "SOS: 3 people on roof top in Perumbakkam Cheran Nagar. Water rising."
        messages = parse_whatsapp_text(raw)
        self.assertEqual(len(messages), 1)
        self.assertIn("Perumbakkam", messages[0]["text"])


if __name__ == "__main__":
    unittest.main()
