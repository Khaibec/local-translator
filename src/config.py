"""Configuration management module."""

import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


class AppConfig:
    """Application configuration container."""

    def __init__(self, project_root: Optional[Path] = None, settings_path: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self.settings_path = settings_path or (self.project_root / "config" / "settings.yaml")

        self.raw_data: Dict[str, Any] = self._load_yaml(self.settings_path)

        # Ollama settings
        ollama = self.raw_data.get("ollama", {})
        self.ollama_host: str = ollama.get("host", "http://localhost:11434")
        self.ollama_model: str = ollama.get("model", "translategemma:4b")
        self.ollama_timeout: int = int(ollama.get("timeout_seconds", 600))

        # Translation settings
        trans = self.raw_data.get("translation", {})
        self.source_language: str = trans.get("source_language", "Japanese")
        self.target_language: str = trans.get("target_language", "Vietnamese")
        self.chunk_size: int = int(trans.get("chunk_size", 1800))
        self.context_size: int = int(trans.get("context_size", 600))
        self.temperature: float = float(trans.get("temperature", 0.1))
        self.max_retries: int = int(trans.get("max_retries", 3))
        self.retry_backoff: float = float(trans.get("retry_backoff", 2.0))
        self.continue_on_error: bool = bool(trans.get("continue_on_error", False))
        self.concurrency: int = int(trans.get("concurrency", 1))

        # Paths
        paths = self.raw_data.get("paths", {})
        self.input_dir: Path = self._resolve_path(paths.get("input_dir", "input"))
        self.output_dir: Path = self._resolve_path(paths.get("output_dir", "output"))
        self.cache_dir: Path = self._resolve_path(paths.get("cache_dir", "cache"))
        self.logs_dir: Path = self._resolve_path(paths.get("logs_dir", "logs"))
        self.prompt_path: Path = self._resolve_path(paths.get("prompt_path", "config/prompt.txt"))
        self.glossary_path: Path = self._resolve_path(paths.get("glossary_path", "config/glossary.txt"))

        # Ensure directory creation
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            return p
        return (self.project_root / p).resolve()

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def get_prompt_template(self) -> str:
        """Read and return translation prompt template."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found at: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    def get_prompt_hash(self) -> str:
        """Compute SHA256 of prompt template."""
        content = self.get_prompt_template().strip()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_glossary_content(self) -> str:
        """Read and return glossary content."""
        if not self.glossary_path.exists():
            return ""
        return self.glossary_path.read_text(encoding="utf-8")

    def get_glossary_hash(self) -> str:
        """Compute SHA256 of glossary content."""
        content = self.get_glossary_content().strip()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_config(project_root: Optional[Path] = None, settings_path: Optional[Path] = None) -> AppConfig:
    return AppConfig(project_root=project_root, settings_path=settings_path)
