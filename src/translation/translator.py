"""Translator coordination and execution module."""

import logging
from typing import Optional, List, Tuple
from src.translation.ollama_client import OllamaClient
from src.translation.prompt_builder import PromptBuilder
from src.utils.validator import validate_translation


class Translator:
    """Orchestrates prompt generation, model invocation, and validation for chunks."""

    def __init__(
        self,
        client: OllamaClient,
        prompt_builder: PromptBuilder,
        glossary_formatted: str = "",
        temperature: float = 0.1,
        logger: Optional[logging.Logger] = None
    ):
        self.client = client
        self.prompt_builder = prompt_builder
        self.glossary_formatted = glossary_formatted
        self.temperature = temperature
        self.logger = logger or logging.getLogger(__name__)

    def translate_chunk(
        self,
        source_text: str,
        prev_translation: Optional[str] = None
    ) -> Tuple[str, List[str]]:
        """Translate a single chunk of text with validation and return (translation, warnings)."""
        prompt = self.prompt_builder.build_prompt(
            text_to_translate=source_text,
            prev_translation=prev_translation,
            glossary_formatted=self.glossary_formatted
        )

        raw_output = self.client.generate(prompt=prompt, temperature=self.temperature)

        # Validate and sanitize response
        validation = validate_translation(source_text=source_text, raw_translation=raw_output)

        for w in validation.warnings:
            self.logger.warning(w)

        return validation.cleaned_text, validation.warnings
