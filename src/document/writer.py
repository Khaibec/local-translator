"""Document writer abstraction and implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from src.utils.text_utils import normalize_line_endings


class BaseDocumentWriter(ABC):
    """Abstract base class for document writers."""

    @abstractmethod
    def write(self, file_path: Path, content: str) -> None:
        """Write content to file_path."""
        pass


class TxtWriter(BaseDocumentWriter):
    """Writer for UTF-8 text files."""

    def write(self, file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = normalize_line_endings(content)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(normalized)


class DocxWriter(BaseDocumentWriter):
    """Writer for Word (.docx) documents."""

    def write(self, file_path: Path, content: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import docx
        except ImportError:
            raise ImportError("python-docx is required to write DOCX files. Install it with: pip install python-docx")

        doc = docx.Document()
        normalized = normalize_line_endings(content)
        paragraphs = normalized.split("\n\n")

        for para in paragraphs:
            para_text = para.strip()
            if para_text:
                doc.add_paragraph(para_text)

        doc.save(file_path)


def get_writer(file_path: Path) -> BaseDocumentWriter:
    """Factory to retrieve appropriate document writer based on file suffix."""
    suffix = file_path.suffix.lower()
    if suffix in [".txt", ".text", ".md"]:
        return TxtWriter()
    elif suffix == ".docx":
        return DocxWriter()
    else:
        # Default to TxtWriter
        return TxtWriter()
