"""Crawler package for Japanese web novels."""

from src.crawler.base import (
    BaseCrawler,
    CrawlerError,
    CrawlerConnectionError,
    CrawlerHTTPError,
    CrawlerParseError
)
from src.crawler.syosetu import SyosetuCrawler


def get_crawler_for_url(url: str, **kwargs) -> BaseCrawler:
    """Factory to retrieve appropriate crawler instance based on novel URL."""
    url_lower = url.lower()
    if "syosetu.com" in url_lower or url_lower.startswith("n"):
        return SyosetuCrawler(**kwargs)
    else:
        # Default to Syosetu if matching ncode pattern
        return SyosetuCrawler(**kwargs)


__all__ = [
    "BaseCrawler",
    "SyosetuCrawler",
    "CrawlerError",
    "CrawlerConnectionError",
    "CrawlerHTTPError",
    "CrawlerParseError",
    "get_crawler_for_url",
]
