from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from ..config import Settings
from . import ollama as ollama_client


class ProviderAdapter(Protocol):
    async def chat_completion(self, payload: dict) -> httpx.Response:
        ...


@dataclass(frozen=True)
class OllamaAdapter:
    base_url: str

    async def chat_completion(self, payload: dict) -> httpx.Response:
        return await ollama_client.chat_completion(self.base_url, payload)


@dataclass(frozen=True)
class AzureOpenAIAdapter:
    endpoint: str | None
    deployment: str | None

    async def chat_completion(self, payload: dict) -> httpx.Response:
        raise NotImplementedError(
            "Azure OpenAI adapter is a placeholder. Set LLM_PROVIDER=ollama for now."
        )


def build_adapter(settings: Settings) -> ProviderAdapter:
    provider = settings.llm_provider.strip().lower()
    if provider == "ollama":
        return OllamaAdapter(base_url=settings.ollama_base_url)
    if provider in {"azure", "azure_openai"}:
        return AzureOpenAIAdapter(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
