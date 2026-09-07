"""Novel translation pipeline orchestrating chapter-by-chapter and chunk-by-chunk translation."""

import json
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from tqdm import tqdm

from src.config import AppConfig
from src.models import (
    Chunk,
    ChunkRecord,
    ChapterManifest,
    NovelManifest,
    NovelMetadata
)
from src.document.chunker import JapaneseDocumentChunker
from src.translation.ollama_client import OllamaClient
from src.translation.prompt_builder import PromptBuilder
from src.translation.translator import Translator
from src.cache.novel_cache_manager import NovelCacheManager
from src.utils.text_utils import compute_file_hash, compute_text_hash
from src.pipeline.translation_pipeline import PipelineExecutionError


class NovelTranslationPipeline:
    """Orchestrates novel translation: Novel -> Chapter -> Chunk -> Merge."""

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
        ncode_or_dir: str,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None,
        force: bool = False,
        continue_on_error: Optional[bool] = None,
        chunk_size: Optional[int] = None,
        context_size: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Translate all or selected chapters of a crawled novel."""
        start_time = time.time()

        # Resolve novel directory
        input_path = Path(ncode_or_dir)
        if input_path.is_dir() and (input_path / "novel.json").exists():
            novel_input_dir = input_path.resolve()
            ncode = novel_input_dir.name.lower()
        else:
            # Treat as ncode inside input_dir
            ncode = ncode_or_dir.strip("/\\").split("/")[-1].split("\\")[-1].lower()
            novel_input_dir = (self.config.input_dir / ncode).resolve()

        if not novel_input_dir.exists():
            raise FileNotFoundError(
                f"Novel directory not found at: {novel_input_dir}\n"
                f"Did you run 'python -m src.main crawl <URL>' first?"
            )

        novel_json_path = novel_input_dir / "novel.json"
        if not novel_json_path.exists():
            raise FileNotFoundError(f"Missing 'novel.json' in {novel_input_dir}")

        with open(novel_json_path, "r", encoding="utf-8") as f:
            novel_meta = NovelMetadata.from_dict(json.load(f))

        chapters_input_dir = novel_input_dir / "chapters"
        if not chapters_input_dir.exists():
            raise FileNotFoundError(f"Missing 'chapters' directory in {novel_input_dir}")

        # Output directory
        novel_output_dir = (self.config.output_dir / ncode).resolve()
        chapters_output_dir = novel_output_dir / "chapters"
        chapters_output_dir.mkdir(parents=True, exist_ok=True)

        effective_chunk_size = chunk_size or self.config.chunk_size
        effective_context_size = context_size or self.config.context_size
        effective_temperature = temperature if temperature is not None else self.config.temperature
        effective_continue_on_error = (
            continue_on_error if continue_on_error is not None else self.config.continue_on_error
        )

        self.logger.info(f"Starting novel translation for '{novel_meta.title}' ({ncode})")
        self.logger.info(f"Model: {self.client.model} | Chunk size: {effective_chunk_size} chars")

        # Step 1: Verify Ollama Readiness
        self.logger.info("Verifying Ollama service readiness...")
        self.client.verify_ready()
        self.logger.info("Ollama is ready.")

        # Step 2: Setup Prompt and Glossary (reusing Phase 1 components)
        prompt_template = self.config.get_prompt_template()
        glossary_raw = self.config.get_glossary_content()
        glossary_dict = PromptBuilder.parse_glossary_content(glossary_raw)
        glossary_formatted = PromptBuilder.format_glossary(glossary_dict)

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

        # Step 3: Setup Cache Manager
        cache_manager = NovelCacheManager(self.config.cache_dir, ncode=ncode)

        novel_manifest = cache_manager.load_novel_manifest() or NovelManifest(
            ncode=ncode,
            title=novel_meta.title,
            source_url=novel_meta.source_url,
            crawler=novel_meta.crawler,
            total_chapters=novel_meta.chapter_count,
            crawled_chapters=novel_meta.chapter_count,
            translation_status="translating"
        )

        # Discover chapter files
        chapter_files = sorted(chapters_input_dir.glob("*.txt"))
        if not chapter_files:
            raise PipelineExecutionError(f"No chapter text files found in: {chapters_input_dir}")

        total_discovered = len(chapter_files)
        novel_manifest.total_chapters = total_discovered

        # Filter chapters if range specified
        filtered_files = []
        for cf in chapter_files:
            try:
                ch_num = int(cf.stem)
            except ValueError:
                continue
            if start_chapter and ch_num < start_chapter:
                continue
            if end_chapter and ch_num > end_chapter:
                continue
            filtered_files.append(cf)

        self.logger.info(f"Selected {len(filtered_files)} of {total_discovered} chapter(s) for translation.")

        chunker = JapaneseDocumentChunker(chunk_size=effective_chunk_size)
        total_translated_chunks_session = 0
        total_translated_chars_session = 0

        # Step 4: Process each chapter
        for cf in filtered_files:
            ch_num = int(cf.stem)
            out_file = chapters_output_dir / f"{ch_num:04d}.txt"

            # Check chapter-level resume
            if not force and out_file.exists() and cache_manager.is_chapter_translated(ch_num):
                self.logger.info(f"Skipping completed chapter {ch_num:04d} (already translated)")
                continue

            chapter_text = cf.read_text(encoding="utf-8")
            if not chapter_text.strip():
                self.logger.warning(f"Chapter {ch_num:04d} is empty. Skipping.")
                continue

            chapter_hash = compute_text_hash(chapter_text)

            # Chunk chapter
            chunks: List[Chunk] = chunker.chunk_document(chapter_text)
            total_chunks = len(chunks)

            ch_manifest = cache_manager.load_chapter_manifest(ch_num) or ChapterManifest(
                chapter_id=f"{ncode}_{ch_num:04d}",
                chapter_index=ch_num,
                chapter_title=f"Chapter {ch_num}",
                source_file=str(cf),
                source_hash=chapter_hash,
                total_chunks=total_chunks,
                completed_chunks=0,
                status="translating"
            )
            ch_manifest.total_chunks = total_chunks
            ch_manifest.status = "translating"
            cache_manager.save_chapter_manifest(ch_num, ch_manifest)

            self.logger.info(
                f"[Novel {ncode}] Starting Chapter {ch_num:04d}/{total_discovered:04d} "
                f"({total_chunks} chunk(s), {len(chapter_text):,} chars)"
            )

            # Process chunks of this chapter
            prev_translation: Optional[str] = None

            with tqdm(
                total=total_chunks,
                desc=f"Ch {ch_num:04d}",
                unit="chunk",
                dynamic_ncols=True
            ) as pbar:
                for chunk in chunks:
                    pbar.set_postfix({
                        "chunk": f"{chunk.chunk_id}/{total_chunks}",
                        "chars": f"{chunk.char_count:,}",
                        "model": self.client.model
                    })

                    # Check chunk-level resume
                    if not force and cache_manager.is_chunk_completed(ch_num, chunk.chunk_id, chunk.text_hash):
                        cached_rec = cache_manager.get_chunk(ch_num, chunk.chunk_id)
                        if cached_rec and cached_rec.status == "completed":
                            prev_translation = cached_rec.translation
                            pbar.update(1)
                            continue

                    self.logger.info(
                        f"[Novel {ncode}] [Chapter {ch_num:04d}/{total_discovered:04d}] "
                        f"[Chunk {chunk.chunk_id:02d}/{total_chunks:02d}] Translating..."
                    )

                    chunk_start = time.time()
                    try:
                        translation, warnings = translator.translate_chunk(
                            source_text=chunk.text,
                            prev_translation=prev_translation
                        )
                        duration = time.time() - chunk_start

                        rec = ChunkRecord(
                            chunk_id=chunk.chunk_id,
                            source_text=chunk.text,
                            source_hash=chunk.text_hash,
                            translation=translation,
                            status="completed",
                            model=self.client.model,
                            duration_seconds=duration,
                            warnings=warnings
                        )
                        cache_manager.save_chunk(ch_num, rec)
                        prev_translation = translation

                        total_translated_chunks_session += 1
                        total_translated_chars_session += chunk.char_count

                    except Exception as e:
                        duration = time.time() - chunk_start
                        err_msg = str(e)
                        self.logger.error(
                            f"Error translating Chapter {ch_num:04d} Chunk {chunk.chunk_id}: {err_msg}"
                        )

                        failed_rec = ChunkRecord(
                            chunk_id=chunk.chunk_id,
                            source_text=chunk.text,
                            source_hash=chunk.text_hash,
                            translation="",
                            status="failed",
                            model=self.client.model,
                            duration_seconds=duration,
                            error_message=err_msg
                        )
                        cache_manager.save_chunk(ch_num, failed_rec)

                        ch_manifest.status = "failed"
                        cache_manager.save_chapter_manifest(ch_num, ch_manifest)

                        novel_manifest.translation_status = "failed"
                        cache_manager.save_novel_manifest(novel_manifest)

                        if not effective_continue_on_error:
                            raise PipelineExecutionError(
                                f"Novel translation halted at Chapter {ch_num:04d} Chunk {chunk.chunk_id}: {err_msg}\n"
                                f"Use --continue-on-error to skip failures, or re-run to resume."
                            )

                    pbar.update(1)

            # Check if all chunks for this chapter are completed
            all_done, records, missing_ids = cache_manager.get_all_chapter_chunks(ch_num, total_chunks)
            if not all_done:
                self.logger.warning(
                    f"Chapter {ch_num:04d} has missing/failed chunks {missing_ids}. Not merging."
                )
                continue

            # Merge chunks into complete chapter
            merged_chapter_text = "\n\n".join(r.translation for r in records if r)
            temp_out = out_file.with_suffix(".tmp")
            with open(temp_out, "w", encoding="utf-8") as f:
                f.write(merged_chapter_text)
            temp_out.replace(out_file)

            ch_manifest.completed_chunks = total_chunks
            ch_manifest.status = "translated"
            cache_manager.save_chapter_manifest(ch_num, ch_manifest)
            self.logger.info(f"Chapter {ch_num:04d} successfully translated and merged -> {out_file.name}")

        # Update novel manifest
        translated_count = cache_manager.count_translated_chapters(total_discovered)
        novel_manifest.translated_chapters = translated_count
        if translated_count >= total_discovered:
            novel_manifest.translation_status = "translated"
        else:
            novel_manifest.translation_status = "translating"

        cache_manager.save_novel_manifest(novel_manifest)

        # Copy novel.json to output
        shutil.copy2(novel_json_path, novel_output_dir / "novel.json")

        elapsed = time.time() - start_time
        summary = {
            "ncode": ncode,
            "title": novel_meta.title,
            "total_chapters": total_discovered,
            "translated_chapters": translated_count,
            "translated_chunks_session": total_translated_chunks_session,
            "translated_chars_session": total_translated_chars_session,
            "output_dir": str(novel_output_dir),
            "elapsed_seconds": round(elapsed, 2)
        }

        self.logger.info(
            f"Novel '{novel_meta.title}' translation completed: "
            f"{translated_count}/{total_discovered} chapter(s) translated in {round(elapsed, 1)}s"
        )
        return summary
