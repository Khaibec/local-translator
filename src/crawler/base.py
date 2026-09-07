"""Base crawler abstraction and common exceptions."""

import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Optional
import requests

from src.models import NovelMetadata, ChapterItem


class CrawlerError(Exception):
    """Base exception for crawler errors."""
    pass


class CrawlerConnectionError(CrawlerError):
    """Raised when website cannot be reached."""
    pass


class CrawlerHTTPError(CrawlerError):
    """Raised when server returns an HTTP error code (e.g. 404, 403, 503)."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class CrawlerParseError(CrawlerError):
    """Raised when HTML parsing fails to extract expected elements."""
    pass


class BaseCrawler(ABC):
    """Abstract base class for all web novel crawlers."""

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        delay_seconds: float = 1.0,
        user_agent: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _sleep_polite(self) -> None:
        """Sleep between requests to observe respectful rate limiting."""
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

    def _request_with_retry(self, url: str) -> str:
        """Fetch URL content with timeout and exponential backoff retry."""
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Fetching {url} (attempt {attempt}/{self.max_retries})")
                resp = self.session.get(url, timeout=self.timeout_seconds)

                if resp.status_code == 404:
                    raise CrawlerHTTPError(404, f"Page not found at: {url}")
                if resp.status_code == 403:
                    raise CrawlerHTTPError(403, f"Access forbidden (possible anti-bot or geo-block) at: {url}")
                if resp.status_code >= 500:
                    raise CrawlerHTTPError(resp.status_code, f"Server error at: {url}")

                resp.raise_for_status()

                # Prefer UTF-8 encoding
                resp.encoding = "utf-8"
                return resp.text

            except CrawlerHTTPError as e:
                # Do not retry on 404 or 403
                if e.status_code in [404, 403]:
                    raise
                last_exception = e
            except requests.exceptions.Timeout as e:
                last_exception = CrawlerConnectionError(f"Request timeout after {self.timeout_seconds}s for {url}")
            except requests.exceptions.RequestException as e:
                last_exception = CrawlerConnectionError(f"Connection error fetching {url}: {e}")

            if attempt < self.max_retries:
                backoff = 2.0 ** attempt
                self.logger.warning(f"Request failed ({last_exception}). Retrying in {backoff:.1f}s...")
                time.sleep(backoff)

        raise last_exception or CrawlerError(f"Failed to fetch {url} after {self.max_retries} attempts.")

    @abstractmethod
    def extract_novel_id(self, url: str) -> str:
        """Extract unique novel identifier (e.g. ncode) from URL."""
        pass

    @abstractmethod
    def discover_chapters(self, novel_url: str) -> Tuple[NovelMetadata, List[ChapterItem]]:
        """Discover novel title, metadata, and sequential list of chapter items."""
        pass

    @abstractmethod
    def fetch_chapter(self, chapter_url: str) -> Tuple[str, str]:
        """Fetch and extract (chapter_title, chapter_text) from a chapter URL."""
        pass

    @abstractmethod
    def crawl(
        self,
        novel_url: str,
        input_base_dir: Path,
        cache_base_dir: Path,
        force: bool = False,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None
    ) -> NovelMetadata:
        """Crawl the novel, saving to input_base_dir and caching progress."""
        pass
