import unittest
from ape import APE

class TestParseVariations(unittest.TestCase):
    def setUp(self):
        self.ape = APE()

    def test_valid_parsing(self):
        content = """{"variation": 1, "content": "First variation"}
{"variation": 2, "content": "Second variation"}
{"variation": 3, "content": "Third variation"}"""
        expected = ["First variation", "Second variation", "Third variation"]
        self.assertEqual(self.ape.parse_variations(content, 3), expected)

    def test_extra_newlines(self):
        content = """{"variation": 1, "content": "First variation"}\n\n{"variation": 2, "content": "Second variation"}\n{"variation": 3, "content": "Third variation"}"""
        expected = ["First variation", "Second variation", "Third variation"]
        self.assertEqual(self.ape.parse_variations(content, 3), expected)

    def test_trailing_whitespace(self):
        content = """{"variation": 1, "content": "First variation   "}\n{"variation": 2, "content": "Second variation"}\n{"variation": 3, "content": "Third variation  "}"""
        expected = ["First variation", "Second variation", "Third variation"]
        self.assertEqual(self.ape.parse_variations(content, 3), expected)

    def test_partial_content(self):
        content = """{"variation": 1, "content": "First variation"}
{"variation": 2, "content": "Second variation"}"""
        expected = ["First variation", "Second variation"]
        self.assertEqual(self.ape.parse_variations(content, 2), expected)

    def test_content_with_no_variations(self):
        content = ""
        expected = []
        self.assertEqual(self.ape.parse_variations(content, 0), expected)

    def test_content_with_numbers_in_text(self):
        content = """{"variation": 1, "content": "First variation with number 2.5"}
{"variation": 2, "content": "Second variation"}
{"variation": 3, "content": "Third variation"}"""
        expected = ["First variation with number 2.5", "Second variation", "Third variation"]
        self.assertEqual(self.ape.parse_variations(content, 3), expected)

if __name__ == '__main__':
    unittest.main()
