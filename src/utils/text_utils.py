"""Text manipulation, sentence segmentation, and hashing utilities."""

import hashlib
import re
from pathlib import Path
from typing import List


def normalize_line_endings(text: str) -> str:
    """Normalize Windows/Mac line endings to standard LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file incrementally to conserve memory."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# Japanese sentence terminators with potential closing quotes/brackets
_JA_SENTENCE_PATTERN = re.compile(r"([。！？\n]+[」』）\)\]\"']*|\. |\! |\? )")


def split_japanese_sentences(paragraph: str) -> List[str]:
    """Split a Japanese paragraph into individual sentences.

    Preserves sentence terminators (。, ！, ？) and closing brackets.
    """
    if not paragraph.strip():
        return []

    # Split while retaining delimiters
    tokens = _JA_SENTENCE_PATTERN.split(paragraph)
    sentences: List[str] = []
    current = ""

    for i in range(0, len(tokens)):
        token = tokens[i]
        if not token:
            continue
        current += token
        # If this token is a delimiter or if we are at the end
        if _JA_SENTENCE_PATTERN.fullmatch(token):
            sentences.append(current)
            current = ""

    if current:
        sentences.append(current)

    return sentences


def extract_special_patterns(text: str) -> dict:
    """Detect special content like URLs, emails, and code fences."""
    return {
        "urls": re.findall(r"https?://[^\s<>\"'）)]+", text),
        "emails": re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text),
        "code_blocks": re.findall(r"```[\s\S]*?```", text)
    }
