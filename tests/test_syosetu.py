"""Unit tests for Syosetu crawler."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.crawler.syosetu import SyosetuCrawler
from src.crawler.base import (
    CrawlerError,
    CrawlerHTTPError,
    CrawlerParseError,
    CrawlerConnectionError
)


SAMPLE_SERIALIZED_INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>魔法世界の冒険 - 小説家になろう</title></head>
<body>
<p class="novel_title">魔法世界の冒険</p>
<div class="index_box">
  <dl class="novel_sublist2">
    <dd class="subtitle">
      <a href="/n1234ab/1/">第1話：旅立ち</a>
    </dd>
  </dl>
  <dl class="novel_sublist2">
    <dd class="subtitle">
      <a href="/n1234ab/2/">第2話：最初の仲間</a>
    </dd>
  </dl>
  <dl class="novel_sublist2">
    <dd class="subtitle">
      <a href="/n1234ab/3/">第3話：ダンジョンの試練</a>
    </dd>
  </dl>
</div>
</body>
</html>
"""

SAMPLE_PAGINATED_INDEX_P1_HTML = """
<!DOCTYPE html>
<html>
<body>
<p class="novel_title">長編大作</p>
<div class="p-novel-pager">
  <a href="/n9999zz/?p=1">1</a>
  <a href="/n9999zz/?p=2">2</a>
</div>
<div class="index_box">
  <a href="/n9999zz/1/">第1章</a>
  <a href="/n9999zz/2/">第2章</a>
</div>
</body>
</html>
"""

SAMPLE_PAGINATED_INDEX_P2_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="index_box">
  <a href="/n9999zz/3/">第3章</a>
</div>
</body>
</html>
"""

SAMPLE_TANPEN_HTML = """
<!DOCTYPE html>
<html>
<head><title>一本道の物語</title></head>
<body>
<h1 class="novel_title">一本道の物語</h1>
<div id="novel_honbun">
  <p id="L1">昔々、あるところに魔法使いが住んでいました。</p>
  <p id="L2">彼は毎日呪文の練習をしていました。</p>
</div>
</body>
</html>
"""

SAMPLE_CHAPTER_HTML = """
<!DOCTYPE html>
<html>
<body>
<p class="novel_subtitle">第1話：旅立ち</p>
<div id="novel_honbun">
  <p id="L1">朝日が<ruby>昇<rp>(</rp><rt>のぼ</rt><rp>)</rp></ruby>る。</p>
  <p id="L2">少年は剣を手に取り、村を出発した。</p>
</div>
</body>
</html>
"""


class TestSyosetuCrawler(unittest.TestCase):

    def setUp(self):
        self.crawler = SyosetuCrawler(timeout_seconds=5, max_retries=2, delay_seconds=0.0)

    def test_extract_novel_id(self):
        cases = [
            ("https://ncode.syosetu.com/n1234ab/", "n1234ab"),
            ("https://ncode.syosetu.com/n1234ab", "n1234ab"),
            ("http://ncode.syosetu.com/N1234AB/", "n1234ab"),
            ("https://ncode.syosetu.com/n1234ab/15/", "n1234ab"),
            ("ncode.syosetu.com/n5678cd", "n5678cd"),
            ("n9999zz", "n9999zz"),
        ]
        for url, expected in cases:
            self.assertEqual(self.crawler.extract_novel_id(url), expected)

    def test_extract_novel_id_invalid(self):
        with self.assertRaises(CrawlerError):
            self.crawler.extract_novel_id("https://example.com/not_syosetu")

    @patch.object(SyosetuCrawler, "_request_with_retry")
    def test_discover_serialized_novel(self, mock_request):
        mock_request.return_value = SAMPLE_SERIALIZED_INDEX_HTML
        meta, chapters = self.crawler.discover_chapters("https://ncode.syosetu.com/n1234ab/")

        self.assertEqual(meta.ncode, "n1234ab")
        self.assertEqual(meta.title, "魔法世界の冒険")
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0].index, 1)
        self.assertEqual(chapters[0].title, "第1話：旅立ち")
        self.assertEqual(chapters[1].index, 2)
        self.assertEqual(chapters[2].index, 3)

    @patch.object(SyosetuCrawler, "_request_with_retry")
    def test_discover_paginated_novel(self, mock_request):
        # Return page 1 then page 2
        mock_request.side_effect = [SAMPLE_PAGINATED_INDEX_P1_HTML, SAMPLE_PAGINATED_INDEX_P2_HTML]
        meta, chapters = self.crawler.discover_chapters("https://ncode.syosetu.com/n9999zz/")

        self.assertEqual(len(chapters), 3)
        self.assertEqual([ch.index for ch in chapters], [1, 2, 3])

    @patch.object(SyosetuCrawler, "_request_with_retry")
    def test_discover_short_story_tanpen(self, mock_request):
        mock_request.return_value = SAMPLE_TANPEN_HTML
        meta, chapters = self.crawler.discover_chapters("https://ncode.syosetu.com/n0001aa/")

        self.assertEqual(meta.chapter_count, 1)
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].index, 1)
        self.assertEqual(chapters[0].title, "一本道の物語")

    @patch.object(SyosetuCrawler, "_request_with_retry")
    def test_fetch_chapter_ruby_sanitization(self, mock_request):
        mock_request.return_value = SAMPLE_CHAPTER_HTML
        title, content = self.crawler.fetch_chapter("https://ncode.syosetu.com/n1234ab/1/")

        self.assertEqual(title, "第1話：旅立ち")
        # Ensure ruby furigana (のぼ) and rp brackets are removed, keeping clean kanji 昇
        self.assertIn("朝日が昇る。", content)
        self.assertNotIn("のぼ", content)
        self.assertNotIn("<rt>", content)
        self.assertIn("少年は剣を手に取り、村を出発した。", content)

    @patch.object(SyosetuCrawler, "_request_with_retry")
    def test_fetch_chapter_missing_body_raises(self, mock_request):
        mock_request.return_value = "<html><body><p>No body element here</p></body></html>"
        with self.assertRaises(CrawlerParseError):
            self.crawler.fetch_chapter("https://ncode.syosetu.com/n1234ab/1/")

    @patch("requests.Session.get")
    def test_retry_on_server_error_and_succeed(self, mock_get):
        # First call fails 500, second call succeeds 200
        mock_err = MagicMock()
        mock_err.status_code = 500

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.text = "<html>OK</html>"

        mock_get.side_effect = [mock_err, mock_ok]

        crawler = SyosetuCrawler(timeout_seconds=2, max_retries=2, delay_seconds=0.0)
        html = crawler._request_with_retry("https://ncode.syosetu.com/test")
        self.assertEqual(html, "<html>OK</html>")
        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.Session.get")
    def test_no_retry_on_404(self, mock_get):
        mock_404 = MagicMock()
        mock_404.status_code = 404
        mock_get.return_value = mock_404

        crawler = SyosetuCrawler(timeout_seconds=2, max_retries=3, delay_seconds=0.0)
        with self.assertRaises(CrawlerHTTPError) as ctx:
            crawler._request_with_retry("https://ncode.syosetu.com/notfound")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(mock_get.call_count, 1)

    def test_crawl_end_to_end_with_resume(self):
        temp_dir = tempfile.TemporaryDirectory()
        input_base = Path(temp_dir.name) / "input"
        cache_base = Path(temp_dir.name) / "cache"

        try:
            with patch.object(self.crawler, "discover_chapters") as mock_discover, \
                 patch.object(self.crawler, "fetch_chapter") as mock_fetch:

                from src.models import NovelMetadata, ChapterItem
                meta = NovelMetadata(
                    ncode="n1234ab",
                    title="テスト小説",
                    source_url="https://ncode.syosetu.com/n1234ab/",
                    chapter_count=2
                )
                chapters = [
                    ChapterItem(index=1, title="第1章", url="http://n1234ab/1/"),
                    ChapterItem(index=2, title="第2章", url="http://n1234ab/2/")
                ]
                mock_discover.return_value = (meta, chapters)
                mock_fetch.side_effect = [
                    ("第1章", "第1章本文"),
                    ("第2章", "第2章本文"),
                ]

                # First Crawl: should fetch both chapters
                res = self.crawler.crawl(
                    novel_url="https://ncode.syosetu.com/n1234ab/",
                    input_base_dir=input_base,
                    cache_base_dir=cache_base
                )

                self.assertEqual(res.ncode, "n1234ab")
                ch1_file = input_base / "n1234ab" / "chapters" / "0001.txt"
                ch2_file = input_base / "n1234ab" / "chapters" / "0002.txt"
                novel_json = input_base / "n1234ab" / "novel.json"

                self.assertTrue(ch1_file.exists())
                self.assertTrue(ch2_file.exists())
                self.assertTrue(novel_json.exists())
                self.assertEqual(mock_fetch.call_count, 2)

                # Second Crawl without force: should skip both chapters!
                mock_fetch.reset_mock()
                self.crawler.crawl(
                    novel_url="https://ncode.syosetu.com/n1234ab/",
                    input_base_dir=input_base,
                    cache_base_dir=cache_base
                )
                self.assertEqual(mock_fetch.call_count, 0, "Already crawled chapters must be skipped!")

        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
