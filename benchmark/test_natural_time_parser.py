import unittest
from datetime import datetime, timedelta
from natural_time_parser import NaturalTimeParser

class TestNaturalTimeParser(unittest.TestCase):
    def setUp(self):
        self.fixed_now = datetime(2025, 1, 24, 12, 0, 0)
        self.parser = NaturalTimeParser(now=self.fixed_now)

    def test_cases(self):
        test_cases = [
            # Relative times
            ("5 minutes ago", self.fixed_now - timedelta(minutes=5)),
            ("30 seconds ago", self.fixed_now - timedelta(seconds=30)),
            ("in 1 hour", self.fixed_now + timedelta(hours=1)),
            ("2 hours from now", self.fixed_now + timedelta(hours=2)),
            ("3 days ago", self.fixed_now - timedelta(days=3)),
            ("1 week ago", self.fixed_now - timedelta(weeks=1)),
            ("next month", self.fixed_now + timedelta(days=30)),
            ("in 15 minutes", self.fixed_now + timedelta(minutes=15)),
            ("10 years from now", self.fixed_now + timedelta(days=10*365)),

            # Absolute times
            ("5pm", self.fixed_now.replace(hour=17, minute=0)),
            ("17:30", self.fixed_now.replace(hour=17, minute=30)),
            ("12:45am", self.fixed_now.replace(hour=0, minute=45)),
            ("midnight", self.fixed_now.replace(hour=0, minute=0)),
            ("noon", self.fixed_now.replace(hour=12, minute=0)),

            # Combined date/time
            ("tomorrow at 5pm", self.fixed_now + timedelta(days=1, hours=5)),
            ("yesterday at 09:00", self.fixed_now - timedelta(days=1, hours=3)),
            ("next Monday at 09:00", datetime(2025, 1, 27, 9, 0)),  # Jan 24 is Friday
            ("last Wednesday at 15:30", datetime(2025, 1, 22, 15, 30)),

            # Day of week references
            ("next Friday", datetime(2025, 1, 31, 12, 0)),
            ("this Tuesday", datetime(2025, 1, 28, 12, 0)),
            ("last Saturday", datetime(2025, 1, 18, 12, 0)),

            # Special cases
            ("tomorrow", self.fixed_now + timedelta(days=1)),
            ("yesterday", self.fixed_now - timedelta(days=1)),
            ("now", self.fixed_now),
            ("today 3pm", self.fixed_now.replace(hour=15, minute=0)),
        ]

        for input_str, expected in test_cases:
            with self.subTest(input=input_str):
                result = self.parser.parse(input_str)
                self.assertEqual(result, expected, f"Failed for '{input_str}': {result} != {expected}")

    def test_invalid_formats(self):
        invalid_cases = [
            "banana time",
            "32 o'clock",
            "next someday",
            "in eleventy minutes",
            "last purple-day",
        ]

        for input_str in invalid_cases:
            with self.subTest(input=input_str):
                with self.assertRaises(ValueError):
                    self.parser.parse(input_str)

if __name__ == '__main__':
    unittest.main()
