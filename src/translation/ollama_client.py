"""Ollama HTTP API client."""

import time
import logging
from typing import Dict, Any, List, Optional
import requests


class OllamaError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when Ollama server cannot be reached."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Raised when requested model is not pulled in Ollama."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when translation request times out."""
    pass


class OllamaClient:
    """HTTP Client for communicating with a local Ollama instance."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "translategemma:4b",
        timeout: int = 600,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.logger = logger or logging.getLogger(__name__)

    def is_reachable(self, timeout_sec: float = 3.0) -> bool:
        """Check if Ollama service is reachable."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=timeout_sec)
            return resp.status_code == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Fetch list of models currently installed in Ollama."""
        url = f"{self.host}/api/tags"
        try:
            resp = requests.get(url, timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                if name:
                    models.append(name)
            return models
        except requests.exceptions.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at '{self.host}'.\n"
                "Please make sure Ollama is running.\n"
                "You can start Ollama or check with: ollama list"
            )
        except Exception as e:
            raise OllamaError(f"Failed to query Ollama models: {e}")

    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        """Check if target model is present in Ollama."""
        target = (model_name or self.model).lower()
        try:
            installed = self.list_installed_models()
        except OllamaConnectionError:
            raise
        except Exception:
            return False

        for item in installed:
            item_lower = item.lower()
            # Match exact 'translategemma:4b' or 'translategemma:4b-latest' or tag variations
            if item_lower == target or item_lower.startswith(f"{target}:"):
                return True
            # Also handle if target has no tag (e.g. 'translategemma' matches 'translategemma:4b')
            if ":" not in target and item_lower.split(":")[0] == target:
                return True
            if ":" in target and item_lower == f"{target}:latest":
                return True

        return False

    def verify_ready(self) -> None:
        """Verify Ollama is reachable and target model is installed.

        Raises clear human-friendly exceptions if anything is missing.
        """
        if not self.is_reachable():
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at '{self.host}'.\n"
                "Please ensure the Ollama service is running.\n"
                "Test in PowerShell/CMD with: ollama list"
            )

        if not self.is_model_installed(self.model):
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' was not found in Ollama.\n"
                f"Please install it by running:\n\n"
                f"    ollama pull {self.model}\n"
            )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        system: Optional[str] = None
    ) -> str:
        """Send prompt to Ollama /api/generate with exponential backoff retries."""
        url = f"{self.host}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        if system:
            payload["system"] = system

        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(
                    f"Sending generation request to Ollama ({self.model}), attempt {attempt}/{self.max_retries}"
                )
                resp = requests.post(url, json=payload, timeout=self.timeout)

                if resp.status_code == 404:
                    raise OllamaModelNotFoundError(
                        f"Model '{self.model}' not found on Ollama server. Pull with: ollama pull {self.model}"
                    )

                resp.raise_for_status()
                data = resp.json()
                output = data.get("response", "")
                return output

            except requests.exceptions.Timeout as e:
                last_exception = OllamaTimeoutError(
                    f"Request timed out after {self.timeout}s on attempt {attempt}/{self.max_retries}"
                )
                self.logger.warning(str(last_exception))
            except requests.exceptions.ConnectionError as e:
                last_exception = OllamaConnectionError(
                    f"Connection to Ollama failed on attempt {attempt}/{self.max_retries}: {e}"
                )
                self.logger.warning(str(last_exception))
            except OllamaModelNotFoundError:
                raise
            except requests.exceptions.RequestException as e:
                last_exception = OllamaError(f"HTTP request error: {e}")
                self.logger.warning(f"Ollama request error on attempt {attempt}/{self.max_retries}: {e}")

            if attempt < self.max_retries:
                sleep_sec = self.retry_backoff ** attempt
                self.logger.info(f"Retrying in {sleep_sec:.1f} seconds...")
                time.sleep(sleep_sec)

        raise last_exception or OllamaError(f"Generation failed after {self.max_retries} attempts.")
