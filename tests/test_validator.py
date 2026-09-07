"""Tests for translation output validation safeguards."""

import unittest
from src.utils.validator import (
    strip_markdown_fences,
    strip_commentary_prefix,
    detect_repetition,
    validate_translation
)


class TestValidator(unittest.TestCase):

    def test_strip_markdown_fences(self):
        wrapped = "```vietnamese\nĐây là bản dịch tiếng Việt.\n```"
        cleaned, stripped = strip_markdown_fences(wrapped)
        self.assertTrue(stripped)
        self.assertEqual(cleaned, "Đây là bản dịch tiếng Việt.")

        # Standard text without fences
        plain = "Không có code fence ở đây."
        cleaned, stripped = strip_markdown_fences(plain)
        self.assertFalse(stripped)
        self.assertEqual(cleaned, plain)

    def test_strip_commentary_prefix(self):
        cases = [
            ("Dưới đây là bản dịch:\nNội dung chính.", "Nội dung chính."),
            ("Đây là bản dịch tiếng Việt:\nNội dung chính.", "Nội dung chính."),
            ("Here is the translation:\nMain content.", "Main content."),
        ]
        for raw, expected in cases:
            cleaned, modified = strip_commentary_prefix(raw)
            self.assertTrue(modified)
            self.assertEqual(cleaned, expected)

    def test_detect_repetition(self):
        normal_text = "Dòng một.\nDòng hai.\nDòng ba.\nDòng bốn.\nDòng năm."
        self.assertFalse(detect_repetition(normal_text, threshold=5))

        repeated_text = "Lặp lại dòng này liên tục.\n" * 6
        self.assertTrue(detect_repetition(repeated_text, threshold=5))

    def test_validate_translation_empty(self):
        res = validate_translation(source_text="日本語テキスト", raw_translation="   ")
        self.assertFalse(res.is_valid)
        self.assertTrue(any("empty" in w for w in res.warnings))

    def test_validate_translation_prompt_echo(self):
        echoed = "You are a professional Japanese to Vietnamese translator.\nBản dịch."
        res = validate_translation(source_text="テスト", raw_translation=echoed)
        self.assertTrue(any("echoed prompt" in w for w in res.warnings))

    def test_validate_translation_unusually_short(self):
        source = "あ" * 300
        res = validate_translation(source_text=source, raw_translation="Ngắn.")
        self.assertTrue(any("unusually short" in w for w in res.warnings))

    def test_validate_translation_normal(self):
        source = "人工知能と自然言語処理の進化についての報告書です。"
        translation = "Báo cáo về sự tiến hóa của trí tuệ nhân tạo và xử lý ngôn ngữ tự nhiên."
        res = validate_translation(source_text=source, raw_translation=translation)
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.warnings), 0)
        self.assertEqual(res.cleaned_text, translation)


if __name__ == "__main__":
    unittest.main()
