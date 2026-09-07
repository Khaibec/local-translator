"""Prompt construction with template placeholders, glossary formatting, and context slicing."""

from typing import Dict, Optional


class PromptBuilder:
    """Builds full translation prompts by injecting glossary, context, and source text."""

    def __init__(self, template: str, context_size: int = 600):
        self.template = template
        self.context_size = context_size

    @staticmethod
    def parse_glossary_content(content: str) -> Dict[str, str]:
        """Parse 'Japanese = Vietnamese' glossary content into a dictionary."""
        glossary: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                parts = line.split("=", 1)
                ja = parts[0].strip()
                vi = parts[1].strip()
                if ja and vi:
                    glossary[ja] = vi
        return glossary

    @staticmethod
    def format_glossary(glossary: Dict[str, str]) -> str:
        """Format glossary dictionary into lines for the prompt."""
        if not glossary:
            return "(Không có thuật ngữ cụ thể)"
        lines = [f"- {ja} = {vi}" for ja, vi in sorted(glossary.items())]
        return "\n".join(lines)

    def prepare_context(self, prev_translation: Optional[str]) -> str:
        """Slice the tail of the previous translation to supply recent context."""
        if not prev_translation or not prev_translation.strip():
            return "(Đầu tài liệu - Không có ngữ cảnh trước)"

        clean = prev_translation.strip()
        if len(clean) <= self.context_size:
            return clean

        # Slice the last context_size characters
        return "..." + clean[-self.context_size:]

    def build_prompt(
        self,
        text_to_translate: str,
        prev_translation: Optional[str] = None,
        glossary_formatted: Optional[str] = None
    ) -> str:
        """Substitute {GLOSSARY}, {CONTEXT}, and {TEXT} into the template."""
        context_str = self.prepare_context(prev_translation)
        glossary_str = glossary_formatted if glossary_formatted is not None else "(Không có)"

        prompt = self.template
        prompt = prompt.replace("{GLOSSARY}", glossary_str)
        prompt = prompt.replace("{CONTEXT}", context_str)
        prompt = prompt.replace("{TEXT}", text_to_translate)
        return prompt
