"""Tests for cache manager and resume logic."""

import tempfile
import unittest
from pathlib import Path
from src.cache.cache_manager import CacheManager
from src.models import ChunkRecord, JobManifest


class TestCacheManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_cache_dir = Path(self.temp_dir.name)
        self.job_id = "test_job_123"
        self.cache_manager = CacheManager(self.base_cache_dir, self.job_id)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_manifest(self):
        manifest = JobManifest(
            job_id=self.job_id,
            source_file="input/doc.txt",
            output_file="output/doc_vi.txt",
            source_hash="hash123",
            model="translategemma:4b",
            chunk_size=1800,
            context_size=600,
            temperature=0.1,
            prompt_hash="p_hash",
            glossary_hash="g_hash",
            total_chunks=10,
            completed_chunks=0
        )
        self.assertFalse(self.cache_manager.manifest_exists())
        self.cache_manager.save_manifest(manifest)
        self.assertTrue(self.cache_manager.manifest_exists())

        loaded = self.cache_manager.load_manifest()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.job_id, self.job_id)
        self.assertEqual(loaded.source_hash, "hash123")
        self.assertEqual(loaded.total_chunks, 10)

    def test_save_and_get_chunk(self):
        record = ChunkRecord(
            chunk_id=1,
            source_text="日本語テキスト",
            source_hash="chunk_hash_abc",
            translation="Văn bản tiếng Nhật",
            status="completed",
            model="translategemma:4b",
            duration_seconds=1.23,
            warnings=[]
        )
        self.cache_manager.save_chunk(record)

        loaded = self.cache_manager.get_chunk(1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.chunk_id, 1)
        self.assertEqual(loaded.translation, "Văn bản tiếng Nhật")
        self.assertEqual(loaded.status, "completed")

    def test_is_chunk_completed(self):
        record = ChunkRecord(
            chunk_id=2,
            source_text="テスト",
            source_hash="correct_hash",
            translation="Kiểm thử",
            status="completed"
        )
        self.cache_manager.save_chunk(record)

        # Correct hash
        self.assertTrue(self.cache_manager.is_chunk_completed(2, "correct_hash"))
        # Incorrect hash
        self.assertFalse(self.cache_manager.is_chunk_completed(2, "wrong_hash"))
        # Missing chunk
        self.assertFalse(self.cache_manager.is_chunk_completed(99))

    def test_failed_chunk_not_completed(self):
        record = ChunkRecord(
            chunk_id=3,
            source_text="エラー",
            source_hash="hash_err",
            translation="",
            status="failed",
            error_message="Ollama timeout"
        )
        self.cache_manager.save_chunk(record)
        self.assertFalse(self.cache_manager.is_chunk_completed(3))

    def test_get_all_chunks_and_missing(self):
        for cid in [1, 2, 4]:
            self.cache_manager.save_chunk(
                ChunkRecord(
                    chunk_id=cid,
                    source_text=f"Text {cid}",
                    source_hash=f"hash_{cid}",
                    translation=f"Dịch {cid}",
                    status="completed"
                )
            )

        all_ok, records, missing_ids = self.cache_manager.get_all_chunks(total_chunks=4)
        self.assertFalse(all_ok)
        self.assertEqual(missing_ids, [3])
        self.assertEqual(len(records), 4)
        self.assertIsNone(records[2])  # index 2 corresponds to chunk 3

    def test_cache_compatibility_check(self):
        manifest1 = JobManifest(
            job_id=self.job_id,
            source_file="doc.txt",
            output_file="doc_vi.txt",
            source_hash="src_v1",
            model="translategemma:4b",
            chunk_size=1800,
            context_size=600,
            temperature=0.1,
            prompt_hash="p_v1",
            glossary_hash="g_v1"
        )
        self.cache_manager.save_manifest(manifest1)

        # Same settings -> no warnings
        warnings = self.cache_manager.check_cache_compatibility(manifest1)
        self.assertEqual(len(warnings), 0)

        # Modified prompt & model
        manifest2 = JobManifest(
            job_id=self.job_id,
            source_file="doc.txt",
            output_file="doc_vi.txt",
            source_hash="src_v1",
            model="qwen:7b",
            chunk_size=1800,
            context_size=600,
            temperature=0.1,
            prompt_hash="p_v2",
            glossary_hash="g_v1"
        )
        warnings2 = self.cache_manager.check_cache_compatibility(manifest2)
        self.assertEqual(len(warnings2), 2)
        self.assertTrue(any("Model changed" in w for w in warnings2))
        self.assertTrue(any("prompt template" in w for w in warnings2))


if __name__ == "__main__":
    unittest.main()
