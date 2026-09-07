"""Tests for prompt builder module."""

import unittest
from src.translation.prompt_builder import PromptBuilder

SAMPLE_TEMPLATE = """ROLE: Translator
GLOSSARY:
{GLOSSARY}
CONTEXT:
{CONTEXT}
TEXT:
{TEXT}
"""


class TestPromptBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = PromptBuilder(template=SAMPLE_TEMPLATE, context_size=50)

    def test_glossary_parsing(self):
        content = """
        # Comment line
        機械学習 = học máy
        深層学習 = học sâu
        invalid line without equals
        """
        parsed = PromptBuilder.parse_glossary_content(content)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed["機械学習"], "học máy")
        self.assertEqual(parsed["深層学習"], "học sâu")

    def test_glossary_formatting(self):
        glossary = {"機械学習": "học máy", "人工知能": "trí tuệ nhân tạo"}
        formatted = PromptBuilder.format_glossary(glossary)
        self.assertIn("- 人工知能 = trí tuệ nhân tạo", formatted)
        self.assertIn("- 機械学習 = học máy", formatted)

    def test_empty_glossary_formatting(self):
        formatted = PromptBuilder.format_glossary({})
        self.assertIn("Không có", formatted)

    def test_context_preparation_empty(self):
        ctx1 = self.builder.prepare_context(None)
        ctx2 = self.builder.prepare_context("")
        ctx3 = self.builder.prepare_context("   ")
        self.assertIn("Đầu tài liệu", ctx1)
        self.assertIn("Đầu tài liệu", ctx2)
        self.assertIn("Đầu tài liệu", ctx3)

    def test_context_preparation_short(self):
        prev = "Đây là đoạn văn trước ngắn hơn 50 ký tự."
        ctx = self.builder.prepare_context(prev)
        self.assertEqual(ctx, prev)

    def test_context_preparation_long_truncation(self):
        # String of 100 characters
        prev = "A" * 100
        ctx = self.builder.prepare_context(prev)
        # Should start with "..." and have length 3 + 50 = 53
        self.assertTrue(ctx.startswith("..."))
        self.assertEqual(len(ctx), 53)
        self.assertEqual(ctx[3:], "A" * 50)

    def test_build_prompt_full(self):
        prompt = self.builder.build_prompt(
            text_to_translate="テスト本文",
            prev_translation="Ngữ cảnh trước.",
            glossary_formatted="- AI = Trí tuệ nhân tạo"
        )
        self.assertIn("- AI = Trí tuệ nhân tạo", prompt)
        self.assertIn("Ngữ cảnh trước.", prompt)
        self.assertIn("テスト本文", prompt)
        self.assertNotIn("{GLOSSARY}", prompt)
        self.assertNotIn("{CONTEXT}", prompt)
        self.assertNotIn("{TEXT}", prompt)


if __name__ == "__main__":
    unittest.main()
