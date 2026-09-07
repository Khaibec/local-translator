"""Data models for local translation pipeline."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Chunk:
    """Represents a chunk of text to be translated."""
    chunk_id: int
    text: str
    char_count: int
    text_hash: str


@dataclass
class ChunkRecord:
    """Persistent representation of a chunk translation."""
    chunk_id: int
    source_text: str
    source_hash: str
    translation: str = ""
    status: str = "pending"  # "pending", "completed", "failed"
    model: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRecord":
        return cls(**data)


@dataclass
class JobManifest:
    """Metadata and status tracking for a translation job."""
    job_id: str
    source_file: str
    output_file: str
    source_hash: str
    model: str
    chunk_size: int
    context_size: int
    temperature: float
    prompt_hash: str
    glossary_hash: str
    total_chunks: int = 0
    completed_chunks: int = 0
    status: str = "in_progress"  # "in_progress", "completed", "failed"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobManifest":
        return cls(**data)


@dataclass
class ValidationResult:
    """Result of validating translated text output."""
    is_valid: bool
    cleaned_text: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class ChapterItem:
    """Represents a discovered chapter entry in a novel's table of contents."""
    index: int
    title: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterItem":
        return cls(**data)


@dataclass
class NovelMetadata:
    """Metadata describing a crawled web novel."""
    ncode: str
    title: str
    source_url: str
    chapter_count: int
    crawler: str = "syosetu"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelMetadata":
        return cls(**data)


@dataclass
class ChapterManifest:
    """Status and progress tracking for an individual chapter."""
    chapter_id: str
    chapter_index: int
    chapter_title: str
    source_file: str
    source_hash: str
    total_chunks: int = 0
    completed_chunks: int = 0
    status: str = "pending"  # "pending", "translating", "translated", "failed"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterManifest":
        return cls(**data)


@dataclass
class NovelManifest:
    """Status and progress tracking for an entire novel."""
    ncode: str
    title: str
    source_url: str
    crawler: str = "syosetu"
    total_chapters: int = 0
    crawled_chapters: int = 0
    translated_chapters: int = 0
    crawl_status: str = "pending"  # "pending", "crawling", "crawled", "failed"
    translation_status: str = "pending"  # "pending", "translating", "translated", "failed"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelManifest":
        return cls(**data)
