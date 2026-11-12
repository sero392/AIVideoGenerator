"""Ollama connector (local Qwen models). Connection-level only: no analysis logic yet."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.ai.base import LLMProvider, LLMResponse, ProviderHealth

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        default_model: str,
        *,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._timeout = timeout
        self._transport = transport  # injectable for tests

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout or self._timeout, transport=self._transport)

    async def list_models(self) -> list[str]:
        async with self._client(timeout=3.0) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]

    async def health_check(self) -> ProviderHealth:
        try:
            models = await self.list_models()
        except httpx.HTTPError as exc:
            logger.debug("Ollama unreachable at %s: %s", self.base_url, exc)
            return ProviderHealth(self.name, "unavailable", f"Ollama not reachable at {self.base_url}")
        if self.default_model not in models:
            return ProviderHealth(
                self.name, "ok", f"Connected, but default model '{self.default_model}' is not pulled", models
            )
        return ProviderHealth(self.name, "ok", "Connected", models)

    async def generate(self, prompt: str, *, model: str | None = None, options: dict[str, Any] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {"model": model or self.default_model, "prompt": prompt, "stream": False}
        if options:
            payload["options"] = options
        async with self._client() as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return LLMResponse(model=data.get("model", payload["model"]), text=data.get("response", ""), raw=data)
