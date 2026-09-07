"""Background QThread workers for crawling and translation jobs."""

import time
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QThread, Signal

from src.config import AppConfig
from src.models import (
    Chunk, ChunkRecord, ChapterManifest, NovelManifest, NovelMetadata
)
from src.crawler import get_crawler_for_url, CrawlerError
from src.document.reader import get_reader
from src.document.writer import get_writer
from src.document.chunker import JapaneseDocumentChunker
from src.translation.ollama_client import OllamaClient
from src.translation.prompt_builder import PromptBuilder
from src.translation.translator import Translator
from src.cache.cache_manager import CacheManager
from src.cache.novel_cache_manager import NovelCacheManager
from src.utils.text_utils import compute_file_hash, compute_text_hash


class CrawlWorker(QThread):
    """Background worker for crawling web novels."""

    progress = Signal(int, int, str)  # current, total, message
    status_changed = Signal(str)
    log_message = Signal(str, str)  # level, text
    finished = Signal(dict)  # metadata dict
    error = Signal(str)

    def __init__(
        self,
        url: str,
        config: AppConfig,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None,
        force: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.url = url
        self.config = config
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self.force = force
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            self.status_changed.emit("Connecting to website...")
            self.log_message.emit("INFO", f"Connecting to Syosetu URL: {self.url}")

            crawler = get_crawler_for_url(
                url=self.url,
                timeout_seconds=self.config.crawler_timeout,
                delay_seconds=self.config.crawler_delay,
                user_agent=self.config.crawler_user_agent
            )

            # Discover chapters
            metadata, chapters = crawler.discover_chapters(self.url)
            discovered_total = len(chapters)

            # Filter by chapter range if requested
            if self.start_chapter is not None:
                chapters = [ch for ch in chapters if ch.index >= self.start_chapter]
            if self.end_chapter is not None:
                chapters = [ch for ch in chapters if ch.index <= self.end_chapter]

            total = len(chapters)
            self.log_message.emit(
                "INFO",
                f"Discovered novel: '{metadata.title}' (total {discovered_total} chapters, downloading {total} in range)."
            )

            ncode = metadata.ncode
            novel_input_dir = self.config.input_dir / ncode
            chapters_input_dir = novel_input_dir / "chapters"
            chapters_input_dir.mkdir(parents=True, exist_ok=True)

            cache_manager = NovelCacheManager(self.config.cache_dir, ncode=ncode)
            novel_manifest = NovelManifest(
                ncode=ncode,
                title=metadata.title,
                source_url=metadata.source_url,
                crawler=metadata.crawler,
                total_chapters=total,
                crawled_chapters=0,
                crawl_status="crawling"
            )
            cache_manager.save_novel_manifest(novel_manifest)

            # Save novel.json
            with open(novel_input_dir / "novel.json", "w", encoding="utf-8") as f:
                import json
                json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

            self.status_changed.emit("Downloading chapters...")
            crawled_count = 0

            for i, item in enumerate(chapters, start=1):
                if self._cancel_requested:
                    self.log_message.emit("WARNING", "Crawl cancelled by user.")
                    self.status_changed.emit("Crawl cancelled.")
                    return

                chapter_file = chapters_input_dir / f"{item.index:04d}.txt"

                # Check resume
                existing_manifest = cache_manager.load_chapter_manifest(item.index)
                if (
                    not self.force
                    and chapter_file.exists()
                    and existing_manifest
                    and existing_manifest.status in ["crawled", "translating", "translated"]
                ):
                    actual_hash = compute_file_hash(chapter_file)
                    if actual_hash == existing_manifest.source_hash:
                        crawled_count += 1
                        self.progress.emit(i, total, f"Skipping {item.index:04d} (cached)")
                        continue

                self.progress.emit(i, total, f"Downloading {item.index:04d}/{total}: {item.title[:20]}")
                crawler._sleep_polite()

                ch_title, ch_text = crawler.fetch_chapter(item.url)

                temp_f = chapter_file.with_suffix(".tmp")
                with open(temp_f, "w", encoding="utf-8") as f:
                    f.write(ch_text)
                temp_f.replace(chapter_file)

                ch_manifest = ChapterManifest(
                    chapter_id=f"{ncode}_{item.index:04d}",
                    chapter_index=item.index,
                    chapter_title=ch_title or item.title,
                    source_file=str(chapter_file),
                    source_hash=compute_text_hash(ch_text),
                    status="crawled"
                )
                cache_manager.save_chapter_manifest(item.index, ch_manifest)

                crawled_count += 1
                self.log_message.emit("INFO", f"Downloaded Chapter {item.index:04d}: {item.title}")

            novel_manifest.crawled_chapters = crawled_count
            novel_manifest.crawl_status = "crawled"
            cache_manager.save_novel_manifest(novel_manifest)

            self.status_changed.emit("Crawl completed.")
            self.log_message.emit("INFO", f"Crawl finished: {crawled_count}/{total} chapters saved.")
            self.finished.emit(metadata.to_dict())

        except Exception as e:
            self.log_message.emit("ERROR", f"Crawl failed: {e}")
            self.status_changed.emit("Crawl failed.")
            self.error.emit(str(e))


class NovelTranslationWorker(QThread):
    """Background worker for chapter/chunk novel translation with pause and cancel support."""

    chapter_progress = Signal(int, int, str)  # current_ch, total_chs, ch_title
    chunk_progress = Signal(int, int, int)    # current_chunk, total_chunks, chars
    overall_progress = Signal(int, str)       # percent (0-100), message
    status_changed = Signal(str)
    chapter_finished = Signal(int, str)       # ch_idx, out_path
    job_finished = Signal(dict)               # summary dict
    job_error = Signal(str)
    paused = Signal()
    log_message = Signal(str, str)

    def __init__(
        self,
        ncode_or_dir: str,
        config: AppConfig,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None,
        selected_chapters: Optional[List[int]] = None,
        force: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.ncode_or_dir = ncode_or_dir
        self.config = config
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self.selected_chapters = selected_chapters
        self.force = force

        self._pause_requested = False
        self._cancel_requested = False

    def pause(self):
        self._pause_requested = True
        self.log_message.emit("INFO", "Pause requested. Will finish active chunk and pause...")

    def resume_translation(self):
        self._pause_requested = False
        self.log_message.emit("INFO", "Resuming translation...")

    def cancel(self):
        self._cancel_requested = True
        self._pause_requested = False
        self.log_message.emit("WARNING", "Cancel requested. Stopping safely after current chunk...")

    def run(self):
        try:
            self.status_changed.emit("Initializing translation...")
            client = OllamaClient(
                host=self.config.ollama_host,
                model=self.config.ollama_model,
                timeout=self.config.ollama_timeout,
                max_retries=self.config.max_retries,
                retry_backoff=self.config.retry_backoff
            )

            # Check Ollama
            self.log_message.emit("INFO", "Checking Ollama readiness...")
            client.verify_ready()
            self.log_message.emit("INFO", f"Ollama ready with model: {client.model}")

            # Resolve paths
            input_p = Path(self.ncode_or_dir)
            if input_p.is_dir() and (input_p / "novel.json").exists():
                novel_in_dir = input_p.resolve()
                ncode = novel_in_dir.name.lower()
            else:
                ncode = self.ncode_or_dir.strip("/\\").split("/")[-1].split("\\")[-1].lower()
                novel_in_dir = (self.config.input_dir / ncode).resolve()

            if not novel_in_dir.exists():
                raise FileNotFoundError(f"Novel folder not found: {novel_in_dir}")

            import json
            with open(novel_in_dir / "novel.json", "r", encoding="utf-8") as f:
                novel_meta = NovelMetadata.from_dict(json.load(f))

            chapters_in_dir = novel_in_dir / "chapters"
            novel_out_dir = (self.config.output_dir / ncode).resolve()
            chapters_out_dir = novel_out_dir / "chapters"
            chapters_out_dir.mkdir(parents=True, exist_ok=True)

            # Cache Manager
            cache_manager = NovelCacheManager(self.config.cache_dir, ncode=ncode)
            novel_manifest = cache_manager.load_novel_manifest() or NovelManifest(
                ncode=ncode,
                title=novel_meta.title,
                source_url=novel_meta.source_url,
                total_chapters=novel_meta.chapter_count,
                translation_status="translating"
            )

            # Prompt & Translator
            prompt_template = self.config.get_prompt_template()
            glossary_raw = self.config.get_glossary_content()
            glossary_dict = PromptBuilder.parse_glossary_content(glossary_raw)
            glossary_formatted = PromptBuilder.format_glossary(glossary_dict)

            prompt_builder = PromptBuilder(template=prompt_template, context_size=self.config.context_size)
            translator = Translator(
                client=client,
                prompt_builder=prompt_builder,
                glossary_formatted=glossary_formatted,
                temperature=self.config.temperature
            )

            chunker = JapaneseDocumentChunker(chunk_size=self.config.chunk_size)

            # Find chapters to translate
            all_files = sorted(chapters_in_dir.glob("*.txt"))
            target_files = []
            for cf in all_files:
                try:
                    num = int(cf.stem)
                except ValueError:
                    continue
                if self.start_chapter is not None and num < self.start_chapter:
                    continue
                if self.end_chapter is not None and num > self.end_chapter:
                    continue
                if self.selected_chapters and num not in self.selected_chapters:
                    continue
                target_files.append((num, cf))

            total_target = len(target_files)
            self.log_message.emit("INFO", f"Translating {total_target} chapter(s) for '{novel_meta.title}'...")

            start_time = time.time()
            translated_session_chunks = 0

            for ch_idx, (num, cf) in enumerate(target_files, start=1):
                if self._cancel_requested:
                    self.status_changed.emit("Cancelled")
                    self.log_message.emit("WARNING", "Translation stopped by user.")
                    return

                out_file = chapters_out_dir / f"{num:04d}.txt"

                # Check chapter resume
                if not self.force and out_file.exists() and cache_manager.is_chapter_translated(num):
                    self.log_message.emit("INFO", f"Skipping completed Chapter {num:04d} (cached)")
                    pct = int((ch_idx / total_target) * 100)
                    self.overall_progress.emit(pct, f"Chapter {num:04d} already translated.")
                    self.chapter_progress.emit(ch_idx, total_target, f"Chapter {num:04d} (Cached)")
                    continue

                chapter_text = cf.read_text(encoding="utf-8")
                chunks = chunker.chunk_document(chapter_text)
                total_chunks = len(chunks)

                self.chapter_progress.emit(ch_idx, total_target, f"Chapter {num:04d}")
                self.status_changed.emit(f"Translating Chapter {num:04d} ({total_chunks} chunks)...")

                ch_manifest = cache_manager.load_chapter_manifest(num) or ChapterManifest(
                    chapter_id=f"{ncode}_{num:04d}",
                    chapter_index=num,
                    chapter_title=f"Chapter {num}",
                    source_file=str(cf),
                    source_hash=compute_text_hash(chapter_text),
                    total_chunks=total_chunks,
                    status="translating"
                )
                ch_manifest.total_chunks = total_chunks
                ch_manifest.status = "translating"
                cache_manager.save_chapter_manifest(num, ch_manifest)

                prev_translation: Optional[str] = None

                for chunk in chunks:
                    # Check pause
                    while self._pause_requested and not self._cancel_requested:
                        self.status_changed.emit("Paused")
                        self.paused.emit()
                        self.msleep(200)

                    if self._cancel_requested:
                        self.status_changed.emit("Cancelled")
                        return

                    # Check chunk resume
                    if not self.force and cache_manager.is_chunk_completed(num, chunk.chunk_id, chunk.text_hash):
                        rec = cache_manager.get_chunk(num, chunk.chunk_id)
                        if rec and rec.status == "completed":
                            prev_translation = rec.translation
                            self.chunk_progress.emit(chunk.chunk_id, total_chunks, chunk.char_count)
                            continue

                    self.chunk_progress.emit(chunk.chunk_id, total_chunks, chunk.char_count)
                    self.log_message.emit(
                        "INFO",
                        f"[Chapter {num:04d}] Translating Chunk {chunk.chunk_id}/{total_chunks} ({chunk.char_count} chars)..."
                    )

                    c_start = time.time()
                    translation, warnings = translator.translate_chunk(chunk.text, prev_translation)
                    dur = time.time() - c_start

                    rec = ChunkRecord(
                        chunk_id=chunk.chunk_id,
                        source_text=chunk.text,
                        source_hash=chunk.text_hash,
                        translation=translation,
                        status="completed",
                        model=client.model,
                        duration_seconds=dur,
                        warnings=warnings
                    )
                    cache_manager.save_chunk(num, rec)
                    prev_translation = translation
                    translated_session_chunks += 1

                # Merge chapter
                all_done, records, missing = cache_manager.get_all_chapter_chunks(num, total_chunks)
                if all_done:
                    merged = "\n\n".join(r.translation for r in records if r)
                    temp_f = out_file.with_suffix(".tmp")
                    with open(temp_f, "w", encoding="utf-8") as f:
                        f.write(merged)
                    temp_f.replace(out_file)

                    ch_manifest.completed_chunks = total_chunks
                    ch_manifest.status = "translated"
                    cache_manager.save_chapter_manifest(num, ch_manifest)

                    self.chapter_finished.emit(num, str(out_file))
                    self.log_message.emit("INFO", f"Chapter {num:04d} completed and merged.")

                pct = int((ch_idx / total_target) * 100)
                self.overall_progress.emit(pct, f"Completed Chapter {num:04d}/{total_target}")

            # Update novel manifest
            translated_count = cache_manager.count_translated_chapters(len(all_files))
            novel_manifest.translated_chapters = translated_count
            if translated_count >= len(all_files):
                novel_manifest.translation_status = "translated"
            cache_manager.save_novel_manifest(novel_manifest)

            # Copy novel.json to output
            shutil.copy2(novel_in_dir / "novel.json", novel_out_dir / "novel.json")

            elapsed = round(time.time() - start_time, 1)
            self.status_changed.emit("Novel translation completed.")
            self.log_message.emit("INFO", f"Novel translation completed in {elapsed}s.")

            summary = {
                "ncode": ncode,
                "title": novel_meta.title,
                "total_chapters": len(all_files),
                "translated_chapters": translated_count,
                "output_dir": str(novel_out_dir),
                "elapsed_seconds": elapsed
            }
            self.job_finished.emit(summary)

        except Exception as e:
            self.log_message.emit("ERROR", f"Translation error: {e}")
            self.status_changed.emit("Translation error.")
            self.job_error.emit(str(e))


class SingleDocTranslationWorker(QThread):
    """Background worker for translating a single local document (.txt, .docx, .pdf)."""

    chunk_progress = Signal(int, int, int)
    overall_progress = Signal(int, str)
    status_changed = Signal(str)
    job_finished = Signal(dict)
    job_error = Signal(str)
    paused = Signal()
    log_message = Signal(str, str)

    def __init__(self, file_path: Path, config: AppConfig, force: bool = False, parent=None):
        super().__init__(parent)
        self.file_path = Path(file_path).resolve()
        self.config = config
        self.force = force

        self._pause_requested = False
        self._cancel_requested = False

    def pause(self):
        self._pause_requested = True
        self.log_message.emit("INFO", "Pause requested...")

    def resume_translation(self):
        self._pause_requested = False
        self.log_message.emit("INFO", "Resuming translation...")

    def cancel(self):
        self._cancel_requested = True
        self._pause_requested = False
        self.log_message.emit("WARNING", "Cancelling translation...")

    def run(self):
        try:
            self.status_changed.emit("Reading document...")
            self.log_message.emit("INFO", f"Reading document: {self.file_path.name}")

            client = OllamaClient(
                host=self.config.ollama_host,
                model=self.config.ollama_model,
                timeout=self.config.ollama_timeout
            )
            client.verify_ready()

            reader = get_reader(self.file_path)
            doc_text = reader.read(self.file_path)
            if not doc_text.strip():
                raise ValueError("Source document is empty.")

            chunker = JapaneseDocumentChunker(chunk_size=self.config.chunk_size)
            chunks = chunker.chunk_document(doc_text)
            total = len(chunks)

            src_hash = compute_file_hash(self.file_path)
            job_id = f"{self.file_path.stem}_{src_hash[:8]}"
            cache_manager = CacheManager(self.config.cache_dir, job_id=job_id)

            stem = self.file_path.stem
            suffix = self.file_path.suffix if self.file_path.suffix.lower() != ".pdf" else ".txt"
            output_file = self.config.output_dir / f"{stem}_vi{suffix}"

            prompt_builder = PromptBuilder(
                template=self.config.get_prompt_template(),
                context_size=self.config.context_size
            )
            glossary_dict = PromptBuilder.parse_glossary_content(self.config.get_glossary_content())
            translator = Translator(
                client=client,
                prompt_builder=prompt_builder,
                glossary_formatted=PromptBuilder.format_glossary(glossary_dict),
                temperature=self.config.temperature
            )

            prev_translation: Optional[str] = None
            start_time = time.time()

            self.status_changed.emit(f"Translating {total} chunks...")

            for chunk in chunks:
                while self._pause_requested and not self._cancel_requested:
                    self.status_changed.emit("Paused")
                    self.paused.emit()
                    self.msleep(200)

                if self._cancel_requested:
                    self.status_changed.emit("Cancelled")
                    return

                if not self.force and cache_manager.is_chunk_completed(chunk.chunk_id, chunk.text_hash):
                    rec = cache_manager.get_chunk(chunk.chunk_id)
                    if rec and rec.status == "completed":
                        prev_translation = rec.translation
                        pct = int((chunk.chunk_id / total) * 100)
                        self.overall_progress.emit(pct, f"Chunk {chunk.chunk_id} (Cached)")
                        self.chunk_progress.emit(chunk.chunk_id, total, chunk.char_count)
                        continue

                self.chunk_progress.emit(chunk.chunk_id, total, chunk.char_count)
                self.log_message.emit("INFO", f"Translating Chunk {chunk.chunk_id}/{total} ({chunk.char_count} chars)...")

                c_start = time.time()
                translation, warnings = translator.translate_chunk(chunk.text, prev_translation)
                dur = time.time() - c_start

                rec = ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    source_text=chunk.text,
                    source_hash=chunk.text_hash,
                    translation=translation,
                    status="completed",
                    model=client.model,
                    duration_seconds=dur,
                    warnings=warnings
                )
                cache_manager.save_chunk(rec)
                prev_translation = translation

                pct = int((chunk.chunk_id / total) * 100)
                self.overall_progress.emit(pct, f"Chunk {chunk.chunk_id}/{total}")

            # Assemble
            all_ok, records, missing = cache_manager.get_all_chunks(total)
            if not all_ok:
                raise ValueError(f"Incomplete chunks: {missing}")

            final_text = "\n\n".join(r.translation for r in records if r)
            writer = get_writer(output_file)
            writer.write(output_file, final_text)

            elapsed = round(time.time() - start_time, 1)
            self.status_changed.emit("Translation completed.")
            self.log_message.emit("INFO", f"Document saved: {output_file.name} in {elapsed}s")

            summary = {
                "input_file": str(self.file_path),
                "output_file": str(output_file),
                "total_chunks": total,
                "elapsed_seconds": elapsed
            }
            self.job_finished.emit(summary)

        except Exception as e:
            self.log_message.emit("ERROR", f"Document translation error: {e}")
            self.status_changed.emit("Error")
            self.job_error.emit(str(e))
