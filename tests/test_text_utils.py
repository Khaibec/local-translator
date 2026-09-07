"""Tests for text utility functions."""

import tempfile
import unittest
from pathlib import Path
from src.utils.text_utils import (
    normalize_line_endings,
    split_japanese_sentences,
    compute_text_hash,
    compute_file_hash,
    extract_special_patterns
)


class TestTextUtils(unittest.TestCase):

    def test_normalize_line_endings(self):
        text = "line1\r\nline2\rline3\n"
        normalized = normalize_line_endings(text)
        self.assertEqual(normalized, "line1\nline2\nline3\n")

    def test_split_japanese_sentences(self):
        para = "これは最初の文です。次は二番目の文です！「引用文ですね？」はい。"
        sentences = split_japanese_sentences(para)
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], "これは最初の文です。")
        self.assertEqual(sentences[1], "次は二番目の文です！")
        self.assertEqual(sentences[2], "「引用文ですね？」")
        self.assertEqual(sentences[3], "はい。")

    def test_split_japanese_sentences_empty(self):
        self.assertEqual(split_japanese_sentences(""), [])
        self.assertEqual(split_japanese_sentences("   "), [])

    def test_compute_text_hash(self):
        h1 = compute_text_hash("人工知能")
        h2 = compute_text_hash("人工知能")
        h3 = compute_text_hash("機械学習")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_compute_file_hash(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write("テスト内容")
            temp_path = Path(f.name)
        try:
            h = compute_file_hash(temp_path)
            expected = compute_text_hash("テスト内容")
            self.assertEqual(h, expected)
        finally:
            temp_path.unlink()

    def test_extract_special_patterns(self):
        text = (
            "詳細は https://example.com/ai を参照してください。"
            "連絡先は info@domain.jp です。"
            "```python\nprint('hello')\n```"
        )
        patterns = extract_special_patterns(text)
        self.assertIn("https://example.com/ai", patterns["urls"])
        self.assertIn("info@domain.jp", patterns["emails"])
        self.assertEqual(len(patterns["code_blocks"]), 1)


if __name__ == "__main__":
    unittest.main()
