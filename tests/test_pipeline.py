"""End-to-end tests for translation pipeline using mocked Ollama client."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.config import AppConfig
from src.pipeline.translation_pipeline import TranslationPipeline, PipelineExecutionError
from src.translation.ollama_client import OllamaClient


class TestPipelineWithMockClient(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        # Create necessary directories
        (self.project_dir / "config").mkdir(parents=True)
        (self.project_dir / "input").mkdir(parents=True)
        (self.project_dir / "output").mkdir(parents=True)
        (self.project_dir / "cache").mkdir(parents=True)
        (self.project_dir / "logs").mkdir(parents=True)

        # Create prompt.txt
        prompt_content = "GLOSSARY:\n{GLOSSARY}\nCONTEXT:\n{CONTEXT}\nTEXT:\n{TEXT}\nOUTPUT:"
        (self.project_dir / "config" / "prompt.txt").write_text(prompt_content, encoding="utf-8")

        # Create glossary.txt
        glossary_content = "人工知能 = trí tuệ nhân tạo\n"
        (self.project_dir / "config" / "glossary.txt").write_text(glossary_content, encoding="utf-8")

        # Create settings.yaml
        settings_yaml = f"""
ollama:
  host: "http://localhost:11434"
  model: "translategemma:4b"
  timeout_seconds: 60

translation:
  source_language: "Japanese"
  target_language: "Vietnamese"
  chunk_size: 50
  context_size: 20
  temperature: 0.1
  max_retries: 2
  retry_backoff: 1.0

paths:
  input_dir: "{self.project_dir / 'input'}"
  output_dir: "{self.project_dir / 'output'}"
  cache_dir: "{self.project_dir / 'cache'}"
  logs_dir: "{self.project_dir / 'logs'}"
  prompt_path: "{self.project_dir / 'config' / 'prompt.txt'}"
  glossary_path: "{self.project_dir / 'config' / 'glossary.txt'}"
"""
        (self.project_dir / "config" / "settings.yaml").write_text(settings_yaml, encoding="utf-8")

        self.config = AppConfig(
            project_root=self.project_dir,
            settings_path=self.project_dir / "config" / "settings.yaml"
        )

        # Create sample input file
        self.input_file = self.project_dir / "input" / "test_doc.txt"
        self.doc_content = (
            "第一段落：人工知能の発展についてです。\n\n"
            "第二段落：深層学習とニューラルネットワークの進化です。\n\n"
            "第三段落：今後の展望と課題についてです。"
        )
        self.input_file.write_text(self.doc_content, encoding="utf-8")

        # Create Mock OllamaClient
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
        if "第一段落" in prompt:
            lines.append("Đoạn 1: Về sự phát triển của trí tuệ nhân tạo.")
        if "第二段落" in prompt:
            lines.append("Đoạn 2: Sự tiến hóa của học sâu và mạng nơ-ron.")
        if "第三段落" in prompt:
            lines.append("Đoạn 3: Triển vọng và thách thức trong tương lai.")
        return "\n\n".join(lines) if lines else "Bản dịch giả lập cho đoạn văn."

    def test_end_to_end_pipeline(self):
        pipeline = TranslationPipeline(
            config=self.config,
            ollama_client=self.mock_client
        )

        output_file = self.project_dir / "output" / "test_doc_vi.txt"
        summary = pipeline.run(
            input_path=self.input_file,
            output_path=output_file,
            chunk_size=60
        )

        self.assertTrue(output_file.exists())
        self.assertGreater(summary["total_chunks"], 1)
        self.assertEqual(summary["completed_chunks"], summary["total_chunks"])
        self.assertEqual(summary["failed_chunks"], 0)

        # Verify output content
        translated_text = output_file.read_text(encoding="utf-8")
        self.assertIn("Đoạn 1", translated_text)
        self.assertIn("Đoạn 2", translated_text)
        self.assertIn("Đoạn 3", translated_text)

    def test_resume_skips_cached_chunks(self):
        pipeline = TranslationPipeline(
            config=self.config,
            ollama_client=self.mock_client
        )
        output_file = self.project_dir / "output" / "test_doc_vi.txt"

        # First run
        summary1 = pipeline.run(input_path=self.input_file, output_path=output_file, chunk_size=60)
        first_gen_calls = self.generation_count
        self.assertGreater(first_gen_calls, 0)

        # Second run without --force -> should reuse all cached chunks!
        summary2 = pipeline.run(input_path=self.input_file, output_path=output_file, chunk_size=60)
        self.assertEqual(self.generation_count, first_gen_calls, "Should not invoke client for cached chunks")
        self.assertEqual(summary2["completed_chunks"], summary1["total_chunks"])

    def test_force_flag_retranslates(self):
        pipeline = TranslationPipeline(
            config=self.config,
            ollama_client=self.mock_client
        )
        output_file = self.project_dir / "output" / "test_doc_vi.txt"

        # First run
        pipeline.run(input_path=self.input_file, output_path=output_file, chunk_size=60)
        first_calls = self.generation_count

        # Second run WITH force -> should retranslate all chunks
        pipeline.run(input_path=self.input_file, output_path=output_file, force=True, chunk_size=60)
        self.assertEqual(self.generation_count, first_calls * 2)

    def test_pipeline_error_handling(self):
        failing_client = MagicMock(spec=OllamaClient)
        failing_client.model = "translategemma:4b"
        failing_client.verify_ready.return_value = None
        failing_client.generate.side_effect = RuntimeError("Ollama connection failed")

        pipeline = TranslationPipeline(
            config=self.config,
            ollama_client=failing_client
        )
        output_file = self.project_dir / "output" / "test_doc_vi.txt"

        with self.assertRaises(PipelineExecutionError):
            pipeline.run(input_path=self.input_file, output_path=output_file)


if __name__ == "__main__":
    unittest.main()
