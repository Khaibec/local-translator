"""Syosetu (ncode.syosetu.com) crawler implementation."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.crawler.base import (
    BaseCrawler,
    CrawlerError,
    CrawlerParseError,
    CrawlerHTTPError
)
from src.models import NovelMetadata, ChapterItem, ChapterManifest, NovelManifest
from src.cache.novel_cache_manager import NovelCacheManager
from src.utils.text_utils import compute_text_hash, compute_file_hash, normalize_line_endings


class SyosetuCrawler(BaseCrawler):
    """Crawler specifically designed for ncode.syosetu.com web novels."""

    def extract_novel_id(self, url: str) -> str:
        """Extract ncode from Syosetu URL (e.g. https://ncode.syosetu.com/n1234ab/ -> n1234ab)."""
        match = re.search(r"(?:ncode\.syosetu\.com/)?([nN]\d{4}[a-zA-Z]{1,2})", url)
        if not match:
            raise CrawlerError(f"Could not extract a valid Syosetu ncode from URL: '{url}'")
        return match.group(1).lower()

    def _canonical_url(self, ncode: str) -> str:
        return f"https://ncode.syosetu.com/{ncode}/"

    def discover_chapters(self, novel_url: str) -> Tuple[NovelMetadata, List[ChapterItem]]:
        """Discover novel title and full list of chapter URLs."""
        ncode = self.extract_novel_id(novel_url)
        base_url = self._canonical_url(ncode)

        self.logger.info(f"Connecting to Syosetu novel page: {base_url}")
        html = self._request_with_retry(base_url)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Novel Title
        title = ""
        title_el = (
            soup.find("p", class_="novel_title")
            or soup.find("h1", class_="novel_title")
            or soup.find("h1", class_="p-novel__title")
            or soup.find("a", class_="novel_title")
        )
        if title_el:
            title = title_el.get_text().strip()
        elif soup.title:
            title = soup.title.get_text().split(" - ")[0].strip()

        if not title:
            title = f"Syosetu Novel {ncode}"

        # 2. Check if this is a single-episode short story (tanpen)
        body_el = soup.find(id="novel_honbun") or soup.find(class_="p-novel__body")
        index_box = soup.find(class_="index_box") or soup.find(class_="p-eplist")

        if body_el and not index_box:
            self.logger.info(f"Novel '{title}' is a single-episode short story (tanpen).")
            chapter_item = ChapterItem(index=1, title=title, url=base_url)
            metadata = NovelMetadata(
                ncode=ncode,
                title=title,
                source_url=base_url,
                chapter_count=1,
                crawler="syosetu"
            )
            return metadata, [chapter_item]

        # 3. Serialized novel: Extract chapters from all index pages
        chapter_items: List[ChapterItem] = []
        seen_indices = set()

        # Check total index pages (pagination)
        max_page = 1
        pager_links = soup.find_all("a", href=re.compile(rf"\?p=(\d+)"))
        for link in pager_links:
            m = re.search(r"\?p=(\d+)", link.get("href", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))

        self.logger.info(f"Discovered {max_page} index page(s) for novel '{title}'.")

        for page in range(1, max_page + 1):
            if page > 1:
                page_url = f"{base_url}?p={page}"
                self._sleep_polite()
                page_html = self._request_with_retry(page_url)
                page_soup = BeautifulSoup(page_html, "html.parser")
            else:
                page_soup = soup

            # Match chapter links like /{ncode}/1/ or /{ncode}/1
            ch_links = page_soup.find_all("a", href=re.compile(rf"/{ncode}/(\d+)/?"))
            for a in ch_links:
                href = a.get("href", "")
                m = re.search(rf"/{ncode}/(\d+)/?", href)
                if not m:
                    continue
                ch_idx = int(m.group(1))
                if ch_idx in seen_indices:
                    continue

                ch_title = a.get_text().strip()
                full_url = f"https://ncode.syosetu.com/{ncode}/{ch_idx}/"
                seen_indices.add(ch_idx)
                chapter_items.append(ChapterItem(index=ch_idx, title=ch_title, url=full_url))

        # Sort by chapter index
        chapter_items.sort(key=lambda x: x.index)
        self.logger.info(f"Discovered {len(chapter_items)} total chapter(s) for novel '{title}'.")

        if not chapter_items:
            raise CrawlerParseError(f"No chapters found on novel page: {base_url}")

        metadata = NovelMetadata(
            ncode=ncode,
            title=title,
            source_url=base_url,
            chapter_count=len(chapter_items),
            crawler="syosetu"
        )
        return metadata, chapter_items

    def fetch_chapter(self, chapter_url: str) -> Tuple[str, str]:
        """Fetch and extract (chapter_title, cleaned_text) from a chapter URL."""
        html = self._request_with_retry(chapter_url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract Chapter Subtitle
        subtitle_el = (
            soup.find("p", class_="novel_subtitle")
            or soup.find(class_="p-novel__title")
            or soup.find(class_="novel_subtitle")
        )
        chapter_title = subtitle_el.get_text().strip() if subtitle_el else ""

        # Extract Honbun (Chapter Body)
        body_el = soup.find(id="novel_honbun") or soup.find(class_="p-novel__body")
        if not body_el:
            raise CrawlerParseError(f"Could not locate 'novel_honbun' element on page: {chapter_url}")

        # Sanitize Ruby: remove <rp> and <rt> annotations to keep clean kanji
        for tag in body_el.find_all(["rp", "rt"]):
            tag.decompose()

        # Extract paragraphs
        paragraphs = []
        p_tags = body_el.find_all("p")
        if p_tags:
            for p in p_tags:
                text = p.get_text().strip()
                if text:
                    paragraphs.append(text)
            body_text = "\n\n".join(paragraphs)
        else:
            # Fallback if no <p> tags
            for br in body_el.find_all("br"):
                br.replace_with("\n")
            body_text = body_el.get_text().strip()

        body_text = normalize_line_endings(body_text)
        body_text = re.sub(r"\n{3,}", "\n\n", body_text)

        # Assemble clean full chapter text
        if chapter_title:
            full_chapter_text = f"{chapter_title}\n\n{body_text}"
        else:
            full_chapter_text = body_text

        return chapter_title, full_chapter_text

    def crawl(
        self,
        novel_url: str,
        input_base_dir: Path,
        cache_base_dir: Path,
        force: bool = False,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None
    ) -> NovelMetadata:
        """Crawl the novel (or a range of chapters), saving chapters to disk with manifest-based resume."""
        metadata, chapters = self.discover_chapters(novel_url)
        ncode = metadata.ncode

        # Filter chapters if range is provided
        if start_chapter is not None:
            chapters = [ch for ch in chapters if ch.index >= start_chapter]
        if end_chapter is not None:
            chapters = [ch for ch in chapters if ch.index <= end_chapter]

        novel_input_dir = Path(input_base_dir) / ncode
        chapters_input_dir = novel_input_dir / "chapters"
        chapters_input_dir.mkdir(parents=True, exist_ok=True)

        cache_manager = NovelCacheManager(cache_base_dir, ncode=ncode)

        novel_manifest = cache_manager.load_novel_manifest() or NovelManifest(
            ncode=ncode,
            title=metadata.title,
            source_url=metadata.source_url,
            crawler=metadata.crawler,
            total_chapters=metadata.chapter_count,
            crawled_chapters=0,
            crawl_status="crawling"
        )
        novel_manifest.crawl_status = "crawling"
        cache_manager.save_novel_manifest(novel_manifest)

        # Save novel.json in input/<ncode>/
        novel_json_path = novel_input_dir / "novel.json"
        with open(novel_json_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

        self.logger.info(f"Downloading {len(chapters)} chapter(s) for novel '{metadata.title}'...")

        crawled_count = 0

        with tqdm(
            total=len(chapters),
            desc=f"Crawling {ncode}",
            unit="ch",
            dynamic_ncols=True
        ) as pbar:
            for item in chapters:
                chapter_file = chapters_input_dir / f"{item.index:04d}.txt"
                pbar.set_postfix({"ch": f"{item.index}/{len(chapters)}"})

                # Check resume: do not re-crawl if already completed in cache
                existing_ch_manifest = cache_manager.load_chapter_manifest(item.index)
                if (
                    not force
                    and chapter_file.exists()
                    and existing_ch_manifest
                    and existing_ch_manifest.status in ["crawled", "translating", "translated"]
                ):
                    # Verify file integrity matches
                    actual_hash = compute_file_hash(chapter_file)
                    if actual_hash == existing_ch_manifest.source_hash:
                        self.logger.info(f"Skipping already crawled chapter {item.index:04d}")
                        crawled_count += 1
                        pbar.update(1)
                        continue

                # Fetch chapter with polite delay
                self._sleep_polite()
                try:
                    ch_title, ch_text = self.fetch_chapter(item.url)
                except Exception as e:
                    self.logger.error(f"Failed to fetch chapter {item.index} ({item.url}): {e}")
                    raise

                # Save chapter text atomically
                temp_file = chapter_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(ch_text)
                temp_file.replace(chapter_file)

                # Save chapter manifest in cache
                source_hash = compute_text_hash(ch_text)
                ch_manifest = ChapterManifest(
                    chapter_id=f"{ncode}_{item.index:04d}",
                    chapter_index=item.index,
                    chapter_title=ch_title or item.title,
                    source_file=str(chapter_file),
                    source_hash=source_hash,
                    status="crawled"
                )
                cache_manager.save_chapter_manifest(item.index, ch_manifest)

                crawled_count += 1
                pbar.update(1)

        novel_manifest.crawled_chapters = crawled_count
        novel_manifest.crawl_status = "crawled"
        cache_manager.save_novel_manifest(novel_manifest)

        # Update novel.json
        metadata.updated_at = datetime.now().isoformat()
        with open(novel_json_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

        self.logger.info(f"Novel crawl completed: {crawled_count}/{len(chapters)} chapter(s) saved to {novel_input_dir}")
        return metadata
