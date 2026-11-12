"""Central place that builds AI providers from configuration.

Model choice comes from ``.env`` (connection/defaults) and ``config/settings.json``
(non-secret tuning). Adding a provider = implement the ABC + add a branch here.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.ai.base import LLMProvider, TranscriptionProvider
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.whisper_provider import FasterWhisperProvider


class AIProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        ai_cfg = settings.load_json_config("settings.json").get("ai", {})
        self._default_llm = ai_cfg.get("default_llm_provider", "ollama")
        self._llm_cfg: dict = ai_cfg.get("providers", {})
        self._llms: dict[str, LLMProvider] = {}

    def llm(self, name: str | None = None) -> LLMProvider:
        name = name or self._default_llm
        if name not in self._llms:
            self._llms[name] = self._build_llm(name)
        return self._llms[name]

    def _build_llm(self, name: str) -> LLMProvider:
        cfg = self._llm_cfg.get(name, {})
        if name == "ollama":
            return OllamaProvider(
                base_url=self._settings.ollama_base_url,
                # .env wins over settings.json so deployments can override without editing files
                default_model=self._settings.ollama_default_model or cfg.get("default_model", "qwen2.5:7b"),
                timeout=float(cfg.get("request_timeout_seconds", 120)),
            )
        raise ValueError(f"Unknown LLM provider: {name}")

    def transcription(self) -> TranscriptionProvider:
        s = self._settings
        return FasterWhisperProvider(s.whisper_model_size, s.whisper_device, s.whisper_compute_type)
