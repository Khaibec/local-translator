"""Translation pipeline orchestrating document reading, chunking, translation, caching, and assembly."""

import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from tqdm import tqdm

from src.config import AppConfig
from src.models import Chunk, ChunkRecord, JobManifest
from src.document.reader import get_reader
from src.document.writer import get_writer
from src.document.chunker import JapaneseDocumentChunker
from src.translation.ollama_client import OllamaClient
from src.translation.prompt_builder import PromptBuilder
from src.translation.translator import Translator
from src.cache.cache_manager import CacheManager
from src.utils.text_utils import compute_file_hash, compute_text_hash


class PipelineExecutionError(Exception):
    """Raised when pipeline execution fails."""
    pass


class TranslationPipeline:
    """Orchestrates end-to-end local translation with resume and cache support."""

    def __init__(
        self,
        config: AppConfig,
        ollama_client: Optional[OllamaClient] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.logger = logger or logging.getLogger("translator")
        self.client = ollama_client or OllamaClient(
            host=self.config.ollama_host,
            model=self.config.ollama_model,
            timeout=self.config.ollama_timeout,
            max_retries=self.config.max_retries,
            retry_backoff=self.config.retry_backoff,
            logger=self.logger
        )

    def run(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        force: bool = False,
        continue_on_error: Optional[bool] = None,
        chunk_size: Optional[int] = None,
        context_size: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute the translation pipeline for the given input document."""
        start_time = time.time()
        input_file = Path(input_path).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Determine output path if not provided
        if output_path is None:
            stem = input_file.stem
            suffix = input_file.suffix
            output_file = self.config.output_dir / f"{stem}_vi{suffix}"
        else:
            output_file = Path(output_path).resolve()

        effective_chunk_size = chunk_size or self.config.chunk_size
        effective_context_size = context_size or self.config.context_size
        effective_temperature = temperature if temperature is not None else self.config.temperature
        effective_continue_on_error = (
            continue_on_error if continue_on_error is not None else self.config.continue_on_error
        )

        self.logger.info(f"Starting translation job for: {input_file.name}")
        self.logger.info(f"Target output file: {output_file}")
        self.logger.info(f"Model: {self.client.model} | Chunk size: {effective_chunk_size}")

        # Step 1: Verify Ollama server and model readiness
        self.logger.info("Verifying Ollama service and model readiness...")
        self.client.verify_ready()
        self.logger.info("Ollama is ready.")

        # Step 2: Read document
        reader = get_reader(input_file)
        document_text = reader.read(input_file)
        if not document_text.strip():
            raise PipelineExecutionError(f"Input document '{input_file.name}' is empty.")

        source_file_hash = compute_file_hash(input_file)
        total_source_chars = len(document_text)

        # Step 3: Chunk document
        chunker = JapaneseDocumentChunker(chunk_size=effective_chunk_size)
        chunks: List[Chunk] = chunker.chunk_document(document_text)
        total_chunks = len(chunks)
        self.logger.info(f"Document chunked into {total_chunks} chunk(s) ({total_source_chars:,} characters).")

        if total_chunks == 0:
            raise PipelineExecutionError("No chunks were generated from the input document.")

        # Step 4: Setup Prompt and Glossary
        prompt_template = self.config.get_prompt_template()
        prompt_hash = self.config.get_prompt_hash()

        glossary_raw = self.config.get_glossary_content()
        glossary_dict = PromptBuilder.parse_glossary_content(glossary_raw)
        glossary_formatted = PromptBuilder.format_glossary(glossary_dict)
        glossary_hash = self.config.get_glossary_hash()

        prompt_builder = PromptBuilder(
            template=prompt_template,
            context_size=effective_context_size
        )
        translator = Translator(
            client=self.client,
            prompt_builder=prompt_builder,
            glossary_formatted=glossary_formatted,
            temperature=effective_temperature,
            logger=self.logger
        )

        # Step 5: Setup Cache & Job Manifest
        job_id = f"{input_file.stem}_{source_file_hash[:8]}"
        cache_manager = CacheManager(self.config.cache_dir, job_id=job_id)

        manifest = JobManifest(
            job_id=job_id,
            source_file=str(input_file),
            output_file=str(output_file),
            source_hash=source_file_hash,
            model=self.client.model,
            chunk_size=effective_chunk_size,
            context_size=effective_context_size,
            temperature=effective_temperature,
            prompt_hash=prompt_hash,
            glossary_hash=glossary_hash,
            total_chunks=total_chunks,
            completed_chunks=0,
            status="in_progress"
        )

        if force:
            self.logger.info("Force flag specified. Clearing existing cache for this job.")
            cache_manager.clear_job()
            cache_manager.save_manifest(manifest)
        else:
            incompatibilities = cache_manager.check_cache_compatibility(manifest)
            if incompatibilities:
                for inc in incompatibilities:
                    self.logger.warning(f"Cache parameter discrepancy: {inc}")
                self.logger.warning(
                    "Continuing with existing cache. Use --force to invalidate cache and start fresh."
                )
            if not cache_manager.manifest_exists():
                cache_manager.save_manifest(manifest)

        # Step 6: Process chunks sequentially
        prev_translation: Optional[str] = None
        failed_chunks: List[int] = []

        self.logger.info(f"Processing {total_chunks} chunk(s)...")

        with tqdm(
            total=total_chunks,
            desc="Translating",
            unit="chunk",
            dynamic_ncols=True
        ) as pbar:
            for chunk in chunks:
                pbar.set_postfix({
                    "chunk": f"{chunk.chunk_id}/{total_chunks}",
                    "chars": f"{chunk.char_count:,}",
                    "model": self.client.model
                })

                # Check if already completed in cache
                if not force and cache_manager.is_chunk_completed(chunk.chunk_id, chunk.text_hash):
                    cached_record = cache_manager.get_chunk(chunk.chunk_id)
                    if cached_record and cached_record.status == "completed":
                        prev_translation = cached_record.translation
                        pbar.update(1)
                        continue

                # Translate chunk
                chunk_start = time.time()
                try:
                    translation, warnings = translator.translate_chunk(
                        source_text=chunk.text,
                        prev_translation=prev_translation
                    )
                    duration = time.time() - chunk_start

                    record = ChunkRecord(
                        chunk_id=chunk.chunk_id,
                        source_text=chunk.text,
                        source_hash=chunk.text_hash,
                        translation=translation,
                        status="completed",
                        model=self.client.model,
                        duration_seconds=duration,
                        warnings=warnings
                    )
                    cache_manager.save_chunk(record)
                    prev_translation = translation

                except Exception as e:
                    duration = time.time() - chunk_start
                    err_msg = str(e)
                    self.logger.error(f"Error translating chunk {chunk.chunk_id}: {err_msg}")

                    failed_record = ChunkRecord(
                        chunk_id=chunk.chunk_id,
                        source_text=chunk.text,
                        source_hash=chunk.text_hash,
                        translation="",
                        status="failed",
                        model=self.client.model,
                        duration_seconds=duration,
                        error_message=err_msg
                    )
                    cache_manager.save_chunk(failed_record)
                    failed_chunks.append(chunk.chunk_id)

                    if not effective_continue_on_error:
                        manifest.status = "failed"
                        manifest.completed_chunks = cache_manager.count_completed_chunks()
                        cache_manager.save_manifest(manifest)
                        raise PipelineExecutionError(
                            f"Translation halted at chunk {chunk.chunk_id}/{total_chunks} due to error: {err_msg}\n"
                            "Use --continue-on-error to proceed despite errors, or resume by running again."
                        )

                pbar.update(1)

        # Step 7: Verification and Assembly
        all_completed, records, missing_ids = cache_manager.get_all_chunks(total_chunks)
        completed_count = sum(1 for r in records if r and r.status == "completed")

        manifest.completed_chunks = completed_count

        if not all_completed:
            manifest.status = "failed"
            cache_manager.save_manifest(manifest)
            raise PipelineExecutionError(
                f"Translation incomplete: {len(missing_ids)} chunk(s) missing or failed ({missing_ids}). "
                "Output document was not assembled."
            )

        # Assemble final document
        translated_sections = [r.translation for r in records if r is not None]
        final_text = "\n\n".join(translated_sections)

        writer = get_writer(output_file)
        writer.write(output_file, final_text)

        if not output_file.exists():
            raise PipelineExecutionError(f"Failed to verify output file creation at: {output_file}")

        manifest.status = "completed"
        cache_manager.save_manifest(manifest)

        elapsed = time.time() - start_time
        summary = {
            "job_id": job_id,
            "input_file": str(input_file),
            "output_file": str(output_file),
            "model": self.client.model,
            "total_chunks": total_chunks,
            "completed_chunks": completed_count,
            "failed_chunks": len(failed_chunks),
            "source_characters": total_source_chars,
            "elapsed_seconds": round(elapsed, 2)
        }

        self.logger.info("Translation job completed successfully.")
        return summary
