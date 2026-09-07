"""Pipeline execution module."""

from src.pipeline.translation_pipeline import TranslationPipeline
from src.pipeline.novel_pipeline import NovelTranslationPipeline

__all__ = ["TranslationPipeline", "NovelTranslationPipeline"]
