"""Minimal Ollama HTTP client for chat and embeddings."""

from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Raised when Ollama cannot serve a request."""


class OllamaClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
        self.chat_model = str(config.get("chat_model", ""))
        self.embedding_model = str(config.get("embedding_model", ""))
        self.temperature = float(config.get("temperature", 0.1))
        self.timeout = float(config.get("timeout_seconds", 120))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("Ollama is unavailable or returned an invalid response") from exc
        if not isinstance(body, dict):
            raise OllamaError("Ollama returned an invalid response")
        return body

    def chat(self, system_prompt: str, user_message: str) -> str:
        if not self.chat_model:
            raise OllamaError("No chat model is configured")
        body = self._post(
            "/api/chat",
            {
                "model": self.chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
                "options": {"temperature": self.temperature},
            },
        )
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned no chat content")
        return content.strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_model:
            raise OllamaError("No embedding model is configured")
        result: list[list[float]] = []
        for text in texts:
            body = self._post(
                "/api/embed",
                {"model": self.embedding_model, "input": text},
            )
            embeddings = body.get("embeddings")
            if not isinstance(embeddings, list) or not embeddings or not isinstance(embeddings[0], list):
                raise OllamaError("Ollama returned no embedding")
            result.append([float(value) for value in embeddings[0]])
        return result
