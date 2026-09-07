"""Tests for Japanese document chunker."""

import unittest
from src.document.chunker import JapaneseDocumentChunker


class TestJapaneseChunker(unittest.TestCase):

    def setUp(self):
        self.chunker = JapaneseDocumentChunker(chunk_size=1800)

    def test_empty_text(self):
        chunks = self.chunker.chunk_document("")
        self.assertEqual(len(chunks), 0)

        chunks_ws = self.chunker.chunk_document("   \n\n   ")
        self.assertEqual(len(chunks_ws), 0)

    def test_text_shorter_than_chunk_size(self):
        text = "これは短い日本語のテキストです。段落は一つだけです。"
        chunks = self.chunker.chunk_document(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, 1)
        self.assertEqual(chunks[0].text, text)
        self.assertEqual(chunks[0].char_count, len(text))
        self.assertTrue(len(chunks[0].text_hash) > 0)

    def test_multiple_paragraphs_within_limit(self):
        text = "第一段落です。\n\n第二段落です。\n\n第三段落です。"
        chunks = self.chunker.chunk_document(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, text)

    def test_chunking_across_paragraphs(self):
        # Create chunker with small chunk_size to test paragraph splitting
        small_chunker = JapaneseDocumentChunker(chunk_size=50)
        p1 = "これは最初の段落です。ここには二十文字程度の日本語が含まれます。"  # 32 chars
        p2 = "これは二番目の段落です。こちらも二十文字程度です。"             # 25 chars
        text = f"{p1}\n\n{p2}"

        chunks = small_chunker.chunk_document(text)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].text, p1)
        self.assertEqual(chunks[1].text, p2)
        self.assertEqual(chunks[0].chunk_id, 1)
        self.assertEqual(chunks[1].chunk_id, 2)

    def test_very_long_paragraph_sentence_splitting(self):
        small_chunker = JapaneseDocumentChunker(chunk_size=40)
        s1 = "これは最初の文です。"      # 10 chars
        s2 = "これは二番目の文です。"    # 11 chars
        s3 = "これは三番目の文です。"    # 11 chars
        s4 = "これは四番目の文です。"    # 11 chars
        long_para = f"{s1}{s2}{s3}{s4}"  # 43 chars, larger than 40

        chunks = small_chunker.chunk_document(long_para)
        self.assertGreater(len(chunks), 1)
        # Verify all sentences are accounted for
        reconstructed = "".join(c.text for c in chunks)
        self.assertEqual(reconstructed, long_para)

    def test_unbroken_long_sentence_fallback(self):
        small_chunker = JapaneseDocumentChunker(chunk_size=100)
        # Sentence without any punctuation
        massive_text = "あ" * 250
        chunks = small_chunker.chunk_document(massive_text)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].char_count, 100)
        self.assertEqual(chunks[1].char_count, 100)
        self.assertEqual(chunks[2].char_count, 50)
        self.assertEqual("".join(c.text for c in chunks), massive_text)

    def test_empty_lines_handling(self):
        text = "段落一。\n\n\n\n\n\n段落二。"
        chunks = self.chunker.chunk_document(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "段落一。\n\n段落二。")

    def test_unicode_preservation(self):
        text = "🤖 AIと機械学習の未来：深層学習（Deep Learning）🚀"
        chunks = self.chunker.chunk_document(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, text)


if __name__ == "__main__":
    unittest.main()
