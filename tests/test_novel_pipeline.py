"""Unit and end-to-end tests for NovelCacheManager and NovelTranslationPipeline."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.config import AppConfig
from src.cache.novel_cache_manager import NovelCacheManager
from src.models import (
    NovelManifest,
    ChapterManifest,
    ChunkRecord
)
from src.pipeline.novel_pipeline import NovelTranslationPipeline
from src.pipeline.translation_pipeline import PipelineExecutionError
from src.translation.ollama_client import OllamaClient


class TestNovelCacheManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_cache_dir = Path(self.temp_dir.name)
        self.ncode = "n1234ab"
        self.cache = NovelCacheManager(self.base_cache_dir, self.ncode)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_novel_manifest_lifecycle(self):
        manifest = NovelManifest(
            ncode=self.ncode,
            title="魔法の世界",
            source_url="https://ncode.syosetu.com/n1234ab/",
            total_chapters=10,
            crawled_chapters=10
        )
        self.assertIsNone(self.cache.load_novel_manifest())
        self.cache.save_novel_manifest(manifest)

        loaded = self.cache.load_novel_manifest()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "魔法の世界")
        self.assertEqual(loaded.total_chapters, 10)

    def test_chapter_manifest_lifecycle(self):
        ch_manifest = ChapterManifest(
            chapter_id=f"{self.ncode}_0001",
            chapter_index=1,
            chapter_title="第1章",
            source_file="input/n1234ab/chapters/0001.txt",
            source_hash="hash_ch1",
            total_chunks=3,
            completed_chunks=3,
            status="translated"
        )
        self.assertIsNone(self.cache.load_chapter_manifest(1))
        self.cache.save_chapter_manifest(1, ch_manifest)

        loaded = self.cache.load_chapter_manifest(1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chapter_title, "第1章")
        self.assertTrue(self.cache.is_chapter_translated(1))

    def test_chunk_records_and_retrieval(self):
        record = ChunkRecord(
            chunk_id=1,
            source_text="日本の文章",
            source_hash="hash_c1",
            translation="Câu văn tiếng Nhật",
            status="completed"
        )
        self.cache.save_chunk(chapter_index=2, record=record)

        self.assertTrue(self.cache.is_chunk_completed(2, 1, "hash_c1"))
        self.assertFalse(self.cache.is_chunk_completed(2, 1, "wrong_hash"))
        self.assertFalse(self.cache.is_chunk_completed(2, 2))

        all_ok, records, missing = self.cache.get_all_chapter_chunks(chapter_index=2, total_chunks=2)
        self.assertFalse(all_ok)
        self.assertEqual(missing, [2])


class TestNovelTranslationPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)

        # Directories
        (self.root_dir / "config").mkdir(parents=True)
        (self.root_dir / "input").mkdir(parents=True)
        (self.root_dir / "output").mkdir(parents=True)
        (self.root_dir / "cache").mkdir(parents=True)
        (self.root_dir / "logs").mkdir(parents=True)

        # Prompt and glossary
        (self.root_dir / "config" / "prompt.txt").write_text(
            "GLOSSARY:\n{GLOSSARY}\nCONTEXT:\n{CONTEXT}\nTEXT:\n{TEXT}\nOUTPUT:",
            encoding="utf-8"
        )
        (self.root_dir / "config" / "glossary.txt").write_text(
            "勇者 = dũng giả\n魔王 = ma vương\n",
            encoding="utf-8"
        )

        # Settings
        settings_yaml = f"""
ollama:
  host: "http://localhost:11434"
  model: "translategemma:4b"
  timeout_seconds: 60

translation:
  chunk_size: 40
  context_size: 20
  temperature: 0.1
  max_retries: 2
  retry_backoff: 1.0

paths:
  input_dir: "{self.root_dir / 'input'}"
  output_dir: "{self.root_dir / 'output'}"
  cache_dir: "{self.root_dir / 'cache'}"
  logs_dir: "{self.root_dir / 'logs'}"
  prompt_path: "{self.root_dir / 'config' / 'prompt.txt'}"
  glossary_path: "{self.root_dir / 'config' / 'glossary.txt'}"
"""
        (self.root_dir / "config" / "settings.yaml").write_text(settings_yaml, encoding="utf-8")
        self.config = AppConfig(
            project_root=self.root_dir,
            settings_path=self.root_dir / "config" / "settings.yaml"
        )

        # Setup crawled novel in input/n1234ab/
        self.ncode = "n1234ab"
        self.novel_in_dir = self.root_dir / "input" / self.ncode
        self.chapters_in_dir = self.novel_in_dir / "chapters"
        self.chapters_in_dir.mkdir(parents=True)

        novel_metadata = {
            "ncode": self.ncode,
            "title": "異世界冒険記",
            "source_url": f"https://ncode.syosetu.com/{self.ncode}/",
            "chapter_count": 2,
            "crawler": "syosetu"
        }
        (self.novel_in_dir / "novel.json").write_text(
            json.dumps(novel_metadata, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # Chapter 1
        (self.chapters_in_dir / "0001.txt").write_text(
            "第1章：旅立ちの朝。\n\n勇者は剣を持ち、村の門を出発しました。",
            encoding="utf-8"
        )
        # Chapter 2
        (self.chapters_in_dir / "0002.txt").write_text(
            "第2章：森の遭遇。\n\n魔王の手下が森の奥で待ち伏せしていました。",
            encoding="utf-8"
        )

        # Mock Ollama Client
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.model = "translategemma:4b"
        self.mock_client.verify_ready.return_value = None
        self.mock_client.generate.side_effect = self._fake_generate
        self.generation_count = 0

    def tearDown(self):
        self.temp_dir.cleanup()

    def _fake_generate(self, prompt: str, temperature: float = 0.1, system=None) -> str:
        self.generation_count += 1
        lines = []
        if "第1章" in prompt or "旅立ち" in prompt:
            lines.append("Chương 1: Buổi sáng lên đường.")
        if "勇者" in prompt:
            lines.append("Dũng giả mang theo kiếm, rời khỏi cổng làng.")
        if "第2章" in prompt or "遭遇" in prompt:
            lines.append("Chương 2: Cuộc chạm trán trong rừng.")
        if "魔王" in prompt:
            lines.append("Tay sai của ma vương đang phục kích sâu trong rừng.")
        return "\n\n".join(lines) if lines else "Bản dịch giả lập cho chương."

    def test_novel_translation_end_to_end(self):
        pipeline = NovelTranslationPipeline(config=self.config, ollama_client=self.mock_client)
        summary = pipeline.run(ncode_or_dir=self.ncode, chunk_size=50)

        self.assertEqual(summary["ncode"], self.ncode)
        self.assertEqual(summary["total_chapters"], 2)
        self.assertEqual(summary["translated_chapters"], 2)

        out_ch1 = self.root_dir / "output" / self.ncode / "chapters" / "0001.txt"
        out_ch2 = self.root_dir / "output" / self.ncode / "chapters" / "0002.txt"
        out_json = self.root_dir / "output" / self.ncode / "novel.json"

        self.assertTrue(out_ch1.exists())
        self.assertTrue(out_ch2.exists())
        self.assertTrue(out_json.exists())

        ch1_content = out_ch1.read_text(encoding="utf-8")
        self.assertIn("Chương 1", ch1_content)
        self.assertIn("Dũng giả", ch1_content)

        ch2_content = out_ch2.read_text(encoding="utf-8")
        self.assertIn("Chương 2", ch2_content)
        self.assertIn("ma vương", ch2_content)

    def test_chapter_and_chunk_level_resume(self):
        pipeline = NovelTranslationPipeline(config=self.config, ollama_client=self.mock_client)

        # Run 1: translate both chapters
        pipeline.run(ncode_or_dir=self.ncode, chunk_size=50)
        first_run_calls = self.generation_count
        self.assertGreater(first_run_calls, 0)

        # Run 2: without force, should skip both chapters completely!
        pipeline.run(ncode_or_dir=self.ncode, chunk_size=50)
        self.assertEqual(
            self.generation_count,
            first_run_calls,
            "Completed chapters must be completely skipped without calling Ollama!"
        )

    def test_partial_failure_chunk_level_resume(self):
        # Create pipeline with client that fails on second chapter
        call_tracker = {"count": 0}

        def _fail_on_ch2(prompt: str, temperature: float = 0.1, system=None) -> str:
            call_tracker["count"] += 1
            if "森の遭遇" in prompt:
                raise RuntimeError("Simulated Ollama error in Chapter 2")
            return "Bản dịch thành công chương 1."

        failing_client = MagicMock(spec=OllamaClient)
        failing_client.model = "translategemma:4b"
        failing_client.verify_ready.return_value = None
        failing_client.generate.side_effect = _fail_on_ch2

        pipeline = NovelTranslationPipeline(config=self.config, ollama_client=failing_client)

        # First run: should translate Chapter 1, then fail at Chapter 2
        with self.assertRaises(PipelineExecutionError):
            pipeline.run(ncode_or_dir=self.ncode, chunk_size=50)

        ch1_calls = call_tracker["count"]
        self.assertGreater(ch1_calls, 0)

        # Verify Chapter 1 was saved
        out_ch1 = self.root_dir / "output" / self.ncode / "chapters" / "0001.txt"
        self.assertTrue(out_ch1.exists(), "Chapter 1 output should be merged and saved")

        # Now resume with working client
        working_pipeline = NovelTranslationPipeline(config=self.config, ollama_client=self.mock_client)
        self.generation_count = 0
        summary = working_pipeline.run(ncode_or_dir=self.ncode, chunk_size=50)

        self.assertEqual(summary["translated_chapters"], 2)
        out_ch2 = self.root_dir / "output" / self.ncode / "chapters" / "0002.txt"
        self.assertTrue(out_ch2.exists())


if __name__ == "__main__":
    unittest.main()
