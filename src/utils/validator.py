"""Translation output validation and sanitization safeguards."""

import re
from typing import List
from src.models import ValidationResult


# Common preamble phrases models might emit before translation
_COMMENTARY_PREFIXES = [
    r"^(?:dưới đây|đây)\s+là\s+bản\s+dịch(?:\s+tiếng\s+việt)?[\s:：\-]*",
    r"^bản\s+dịch(?:\s+tiếng\s+việt)?[\s:：\-]*",
    r"^tôi\s+xin\s+gửi\s+bản\s+dịch(?:\s+tiếng\s+việt)?[\s:：\-]*",
    r"^here\s+is\s+the\s+translation[\s:：\-]*",
    r"^translation[\s:：\-]*",
    r"^sure,?\s+here\s+is[\s\S]*?:\s*",
]

# Prompt instruction fragments to detect echo
_PROMPT_ECHO_FRAGMENTS = [
    "You are a professional Japanese",
    "GENERAL RULES:",
    "Preserve the original meaning",
    "CONTEXT FROM PREVIOUS CHUNK:",
    "TEXT TO TRANSLATE:",
    "OUTPUT:\nReturn only",
]


def strip_markdown_fences(text: str) -> tuple[str, bool]:
    """Strip outermost markdown code fence if the model wrapped the entire output in it.

    e.g. ```markdown ... ``` or ```vietnamese ... ``` or ``` ... ```
    """
    stripped = text.strip()
    fence_pattern = re.compile(r"^```(?:[a-zA-Z0-9_\-]+)?\n([\s\S]*?)\n```$", re.DOTALL)
    match = fence_pattern.match(stripped)
    if match:
        return match.group(1).strip(), True
    return stripped, False


def strip_commentary_prefix(text: str) -> tuple[str, bool]:
    """Remove common introductory commentary lines if followed by a newline."""
    cleaned = text
    modified = False
    for pattern in _COMMENTARY_PREFIXES:
        m = re.match(pattern, cleaned, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            cleaned = cleaned[m.end():].lstrip()
            modified = True
            break
    return cleaned, modified


def detect_repetition(text: str, threshold: int = 5) -> bool:
    """Detect if the text exhibits severe degeneration (repeated identical lines/phrases)."""
    lines = [line.strip() for line in text.split("\n") if len(line.strip()) > 10]
    if len(lines) < threshold:
        return False

    # Check for consecutive identical lines
    consecutive_count = 1
    for i in range(1, len(lines)):
        if lines[i] == lines[i - 1]:
            consecutive_count += 1
            if consecutive_count >= threshold:
                return True
        else:
            consecutive_count = 1

    return False


def validate_translation(source_text: str, raw_translation: str) -> ValidationResult:
    """Validate and sanitize translated model output.

    Returns ValidationResult with cleaned text and list of warning messages.
    """
    warnings: List[str] = []

    # Step 1: Strip markdown fences if present
    cleaned_text, fenced = strip_markdown_fences(raw_translation)
    if fenced:
        warnings.append("Stripped outer markdown code fences from model output.")

    # Step 2: Strip commentary prefix
    cleaned_text, had_commentary = strip_commentary_prefix(cleaned_text)
    if had_commentary:
        warnings.append("Stripped introductory commentary prefix from model output.")

    # Step 3: Check empty
    if not cleaned_text.strip():
        warnings.append("Translation output is empty.")
        return ValidationResult(is_valid=False, cleaned_text=cleaned_text, warnings=warnings)

    # Step 4: Check prompt echo
    for fragment in _PROMPT_ECHO_FRAGMENTS:
        if fragment in cleaned_text:
            warnings.append(f"Model echoed prompt instructions: '{fragment}' detected in output.")
            break

    # Step 5: Check relative length ratio
    src_len = len(source_text.strip())
    trans_len = len(cleaned_text.strip())
    if src_len > 100 and trans_len < src_len * 0.15:
        warnings.append(
            f"Translation output is unusually short ({trans_len} chars vs {src_len} source chars)."
        )

    # Step 6: Check infinite repetition
    if detect_repetition(cleaned_text):
        warnings.append("Detected potential degeneration / severe repeated content in translation.")

    is_valid = len(warnings) == 0 or (len(cleaned_text.strip()) > 0 and not any("empty" in w for w in warnings))

    return ValidationResult(
        is_valid=is_valid,
        cleaned_text=cleaned_text,
        warnings=warnings
    )
