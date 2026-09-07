"""Japanese document chunker with paragraph and sentence boundary preservation."""

import re
from typing import List
from src.models import Chunk
from src.utils.text_utils import (
    normalize_line_endings,
    split_japanese_sentences,
    compute_text_hash
)


class JapaneseDocumentChunker:
    """Chunks Japanese documents respecting paragraphs, sentences, and character limits."""

    def __init__(self, chunk_size: int = 1800):
        if chunk_size < 10:
            raise ValueError(f"chunk_size must be at least 10 characters, got {chunk_size}")
        self.chunk_size = chunk_size

    def chunk_document(self, text: str) -> List[Chunk]:
        """Split document text into a list of sensibly sized Chunks."""
        normalized = normalize_line_endings(text).strip()
        if not normalized:
            return []

        # Collapse 3 or more consecutive newlines into 2 (standard paragraph break)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        # If entire text is within chunk_size, return it as a single chunk
        if len(normalized) <= self.chunk_size:
            return [
                Chunk(
                    chunk_id=1,
                    text=normalized,
                    char_count=len(normalized),
                    text_hash=compute_text_hash(normalized)
                )
            ]

        # Split into initial paragraph blocks preserving empty lines structure
        raw_paragraphs = normalized.split("\n\n")

        chunks_text: List[str] = []
        current_buffer = ""

        for para in raw_paragraphs:
            para = para.strip()
            if not para:
                continue

            # Case 1: Paragraph fits in current buffer
            separator = "\n\n" if current_buffer else ""
            if len(current_buffer) + len(separator) + len(para) <= self.chunk_size:
                current_buffer += separator + para
                continue

            # Case 2: Paragraph does not fit in current buffer, but itself is <= chunk_size
            if len(para) <= self.chunk_size:
                if current_buffer:
                    chunks_text.append(current_buffer)
                current_buffer = para
                continue

            # Case 3: Paragraph itself is larger than chunk_size -> split by sentences
            if current_buffer:
                chunks_text.append(current_buffer)
                current_buffer = ""

            sentences = split_japanese_sentences(para)
            sentence_buffer = ""

            for sentence in sentences:
                if not sentence:
                    continue

                # If sentence fits in sentence_buffer
                if len(sentence_buffer) + len(sentence) <= self.chunk_size:
                    sentence_buffer += sentence
                    continue

                # If sentence_buffer has text, flush it
                if sentence_buffer:
                    chunks_text.append(sentence_buffer)
                    sentence_buffer = ""

                # If the individual sentence is still larger than chunk_size
                if len(sentence) > self.chunk_size:
                    # Fallback: slice on character boundaries
                    for i in range(0, len(sentence), self.chunk_size):
                        sub_slice = sentence[i:i + self.chunk_size]
                        if sub_slice:
                            chunks_text.append(sub_slice)
                else:
                    sentence_buffer = sentence

            if sentence_buffer:
                current_buffer = sentence_buffer

        if current_buffer:
            chunks_text.append(current_buffer)

        # Convert to Chunk objects with 1-based indexing
        chunks: List[Chunk] = []
        for idx, c_text in enumerate(chunks_text, start=1):
            chunks.append(
                Chunk(
                    chunk_id=idx,
                    text=c_text,
                    char_count=len(c_text),
                    text_hash=compute_text_hash(c_text)
                )
            )

        return chunks
